from __future__ import annotations

import asyncio
import json
import logging
import subprocess
from datetime import datetime, timezone
from pathlib import Path

from sqlalchemy import select

from app.core.config import get_settings
from app.media.align_service import _resolve
from app.models.core import (
    Episode,
    EpisodeStatus,
    LineAudio,
    NodeRun,
    NodeStatus,
    ScriptLine,
)
from app.storyboard.spec_service import build_episode_render_spec
from app.workflow.celery_app import celery_app
from app.workflow.db import run_async, task_session
from app.workflow.render_service import start_render
from app.workflow.state_machine import transition_episode

logger = logging.getLogger(__name__)


async def _mark_failed(episode_id: str, node_run_id: str, error: str) -> None:
    async with task_session() as session:
        node = await session.get(NodeRun, node_run_id)
        if node is not None:
            node.status = NodeStatus.FAILED
            node.finished_at = datetime.now(timezone.utc)
            node.error = error[:4000]
        episode = await session.get(Episode, episode_id)
        if episode is not None:
            episode.health = "FAILED"
            episode.current_node = None
        await session.commit()


def _run_aligner(
    input_path: Path, output_path: Path, model_dir: Path
) -> None:
    settings = get_settings()
    script = _resolve(settings.align_script)
    python = _resolve(settings.align_python)
    repo = _resolve(settings.align_repo)
    if not script.is_file():
        raise RuntimeError(f"align script not found: {script}")
    if not python.is_file():
        raise RuntimeError(f"align python not found: {python}")
    cmd = [
        str(python),
        str(script),
        "--input",
        str(input_path),
        "--output",
        str(output_path),
        "--model-dir",
        str(model_dir),
        "--device",
        settings.align_device,
    ]
    if repo.is_dir():
        cmd.extend(["--repo", str(repo)])
    if settings.align_use_normalizer:
        cmd.append("--normalize")
    result = subprocess.run(
        cmd,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        timeout=settings.align_timeout_s,
        cwd=str(_resolve(".")),
    )
    if result.returncode != 0:
        detail = (result.stderr or result.stdout or "").strip()[-3000:]
        raise RuntimeError(f"aligner failed ({result.returncode}): {detail}")


async def _align_episode(episode_id: str, node_run_id: str) -> None:
    settings = get_settings()
    model_dir = _resolve(settings.align_model_dir)

    async with task_session() as session:
        episode = await session.get(Episode, episode_id)
        node = await session.get(NodeRun, node_run_id)
        if episode is None or node is None:
            raise RuntimeError(f"episode/node not found: {episode_id}/{node_run_id}")
        if episode.status != EpisodeStatus.ALIGNING:
            raise RuntimeError(
                f"episode status {episode.status.value} is not ALIGNING"
            )
        if not episode.audio_meta or not episode.audio_meta.get("lines"):
            raise RuntimeError("episode has no sentence alignment")

        lines = list(
            await session.scalars(
                select(ScriptLine)
                .where(ScriptLine.episode_id == episode_id)
                .order_by(ScriptLine.seq)
            )
        )
        audios = list(
            await session.scalars(
                select(LineAudio).where(LineAudio.episode_id == episode_id)
            )
        )
        audio_by_line = {audio.script_line_id: audio for audio in audios}
        line_by_id = {line.id: line for line in lines}
        entries = episode.audio_meta["lines"]
        if len(entries) != len(lines):
            raise RuntimeError("sentence alignment is out of date")

        payload_lines = []
        for entry in entries:
            line = line_by_id.get(entry["script_line_id"])
            if line is None:
                raise RuntimeError(f"unknown line in alignment: {entry['script_line_id']}")
            audio = audio_by_line.get(line.id)
            if audio is None or not Path(audio.path).is_file():
                raise RuntimeError(f"line audio missing for seq {line.seq}")
            payload_lines.append(
                {
                    "id": line.id,
                    "seq": line.seq,
                    "text": line.text,
                    "audio_path": audio.path,
                    "start_ms": int(entry["start_ms"]),
                    "end_ms": int(entry["end_ms"]),
                }
            )

        now = datetime.now(timezone.utc)
        node.status = NodeStatus.RUNNING
        node.started_at = node.started_at or now
        node.heartbeat_at = now
        node.error = None
        episode.current_node = "align.episode"
        episode.health = "OK"
        await session.commit()

        episode_dir = _resolve(settings.audio_root) / "episodes" / episode_id
        episode_dir.mkdir(parents=True, exist_ok=True)
        input_path = episode_dir / "align_input.json"
        output_path = episode_dir / "align_output.json"
        input_path.write_text(
            json.dumps({"lines": payload_lines}, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )

    await asyncio.to_thread(
        _run_aligner, input_path, output_path, model_dir
    )

    aligned = json.loads(output_path.read_text(encoding="utf-8"))
    by_id = {item["id"]: item for item in aligned.get("lines", [])}

    async with task_session() as session:
        episode = await session.get(Episode, episode_id)
        node = await session.get(NodeRun, node_run_id)
        if episode is None or node is None:
            raise RuntimeError("episode/node disappeared during alignment")
        if not episode.audio_meta or not episode.audio_meta.get("lines"):
            raise RuntimeError("audio_meta disappeared during alignment")

        meta = dict(episode.audio_meta)
        meta_lines = list(meta["lines"])
        relative: dict[str, list[dict]] = {}
        for entry in meta_lines:
            item = by_id.get(entry["script_line_id"])
            if item is None:
                raise RuntimeError(
                    f"aligner returned no result for {entry['script_line_id']}"
                )
            chars = item.get("chars", [])
            if len(chars) != len(entry["text"]):
                raise RuntimeError(
                    f"aligned char count mismatch for seq {entry['seq']}"
                )
            offset = int(entry["start_ms"])
            relative_chars = []
            for char in chars:
                raw_start = int(char["start_ms"])
                raw_end = int(char["end_ms"])
                start = max(0, raw_start - offset)
                end = max(0, raw_end - offset)
                if raw_end > raw_start:
                    end = max(start + 1, end)
                else:
                    end = start
                relative_chars.append(
                    {"text": char["text"], "start_ms": start, "end_ms": end}
                )
            entry["chars"] = chars
            entry["normalized"] = item.get("normalized", "")
            relative[entry["script_line_id"]] = relative_chars

        meta["lines"] = meta_lines
        meta["alignment_granularity"] = "char"
        meta["aligned_at"] = datetime.now(timezone.utc).isoformat()
        alignment_path = _resolve(settings.audio_root) / "episodes" / episode_id / "alignment.json"
        alignment_path.write_text(
            json.dumps(
                {
                    "granularity": "char",
                    "total_ms": meta.get("total_ms"),
                    "lines": meta_lines,
                },
                ensure_ascii=False,
                indent=2,
            ),
            encoding="utf-8",
        )
        meta["alignment_path"] = str(alignment_path)
        episode.audio_meta = meta

        spec = await build_episode_render_spec(
            session, episode, char_timings_by_line=relative
        )
        episode.render_spec = spec.model_dump()
        episode.version += 1

        node.status = NodeStatus.SUCCESS
        node.finished_at = datetime.now(timezone.utc)
        node.heartbeat_at = node.finished_at
        node.output_ref = str(alignment_path)
        node.error = None
        await session.commit()

    async with task_session() as session:
        episode = await session.get(Episode, episode_id)
        if episode is not None:
            episode.current_node = None
            episode.health = "OK"
        await session.commit()

    logger.info("alignment ready episode=%s lines=%d", episode_id, len(meta_lines))

    if settings.voice_auto_render:
        try:
            async with task_session() as session:
                await transition_episode(
                    session, episode_id, EpisodeStatus.RENDERING
                )
                await session.commit()
            async with task_session() as session:
                await start_render(session, episode_id)
                await session.commit()
            logger.info("auto render queued episode=%s", episode_id)
        except Exception:
            logger.exception("auto render queue failed episode=%s", episode_id)
            async with task_session() as session:
                episode = await session.get(Episode, episode_id)
                if episode is not None:
                    episode.health = "FAILED"
                    episode.current_node = None
                await session.commit()


@celery_app.task(name="align.episode", bind=True, max_retries=1)
def align_episode_task(self, episode_id: str, node_run_id: str):
    try:
        run_async(_align_episode(episode_id, node_run_id))
    except Exception as exc:
        logger.exception("alignment failed episode=%s", episode_id)
        if self.request.retries < self.max_retries:
            raise self.retry(exc=exc, countdown=10)
        run_async(_mark_failed(episode_id, node_run_id, str(exc)))
        raise

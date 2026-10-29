from __future__ import annotations

import json
import logging
from datetime import datetime, timezone
from pathlib import Path

from sqlalchemy import select

from app.core.config import get_settings
from app.media.align_service import start_align
from app.media.audio import assemble_audio, sha256_file
from app.media.service import (
    MODEL,
    PROVIDER,
    _resolve,
    text_hash,
    voice_identity,
)
from app.models.core import (
    Episode,
    EpisodeStatus,
    LineAudio,
    NodeRun,
    NodeStatus,
    ScriptLine,
    Shot,
)
from app.providers.tts import build_tts_provider
from app.storyboard.spec_service import build_episode_render_spec
from app.workflow.celery_app import celery_app
from app.workflow.db import run_async, task_session
from app.workflow.render_service import start_render
from app.workflow.state_machine import transition_episode

logger = logging.getLogger(__name__)

MIN_LINE_MS = 300
MAX_SHOT_MS = 15000
MIN_SHOT_MS = 1500


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


async def _find_audio(
    session, line: ScriptLine, voice_key: str
) -> LineAudio | None:
    return await session.scalar(
        select(LineAudio).where(
            LineAudio.script_line_id == line.id,
            LineAudio.text_hash == text_hash(line.text),
            LineAudio.voice_key == voice_key,
        )
    )


async def _voice_episode(episode_id: str, node_run_id: str) -> None:
    settings = get_settings()
    provider = build_tts_provider()
    voice_key, ref_audio = voice_identity()

    async with task_session() as session:
        episode = await session.get(Episode, episode_id)
        node = await session.get(NodeRun, node_run_id)
        if episode is None or node is None:
            raise RuntimeError(f"episode/node not found: {episode_id}/{node_run_id}")
        if episode.status != EpisodeStatus.VOICING:
            raise RuntimeError(
                f"episode status {episode.status.value} is not VOICING"
            )
        lines = list(
            await session.scalars(
                select(ScriptLine)
                .where(ScriptLine.episode_id == episode_id)
                .order_by(ScriptLine.seq)
            )
        )
        shots = list(
            await session.scalars(
                select(Shot).where(Shot.episode_id == episode_id).order_by(Shot.seq)
            )
        )
        if not lines or not shots:
            raise RuntimeError("episode has no lines or shots")
        shot_by_line = {shot.script_line_id: shot for shot in shots}
        if len(shot_by_line) != len(lines):
            raise RuntimeError("each script line must have exactly one shot")

        now = datetime.now(timezone.utc)
        node.status = NodeStatus.RUNNING
        node.started_at = node.started_at or now
        node.heartbeat_at = now
        node.error = None
        episode.current_node = "voice.episode"
        episode.health = "OK"
        await session.commit()

        line_dir = _resolve(settings.audio_root) / "lines" / voice_key[:16]
        line_dir.mkdir(parents=True, exist_ok=True)

        parts: list[tuple[Path, int]] = []
        alignment: list[dict] = []
        cursor_ms = 0

        for line in lines:
            shot = shot_by_line.get(line.id)
            if shot is None:
                raise RuntimeError(f"script line {line.seq} has no shot")
            stored = await _find_audio(session, line, voice_key)
            if stored is not None and Path(stored.path).is_file():
                clip = Path(stored.path)
                duration_ms = stored.duration_ms
            else:
                digest = text_hash(line.text)
                clip = line_dir / f"{digest[:16]}.wav"
                result = provider.synthesize(line.text, clip)
                duration_ms = result.duration_ms
                checksum = sha256_file(clip)
                if stored is None:
                    stored = LineAudio(
                        episode_id=episode_id,
                        script_line_id=line.id,
                        line_version=line.version,
                        speaker=line.speaker,
                        text_hash=digest,
                        voice_key=voice_key,
                        provider=PROVIDER,
                        model=MODEL,
                        ref_audio=str(ref_audio),
                        path=str(clip),
                        duration_ms=duration_ms,
                        sample_rate=result.sample_rate,
                        checksum=checksum,
                    )
                    session.add(stored)
                else:
                    stored.line_version = line.version
                    stored.speaker = line.speaker
                    stored.path = str(clip)
                    stored.duration_ms = duration_ms
                    stored.sample_rate = result.sample_rate
                    stored.checksum = checksum
                await session.flush()

            if not MIN_LINE_MS <= duration_ms <= MAX_SHOT_MS:
                raise RuntimeError(
                    f"line {line.seq} audio duration {duration_ms}ms is out of range"
                )

            shot_ms = duration_ms + settings.voice_pause_ms
            shot_ms = max(MIN_SHOT_MS, shot_ms)
            if shot_ms > MAX_SHOT_MS:
                raise RuntimeError(
                    f"line {line.seq} needs {shot_ms}ms, exceeds {MAX_SHOT_MS}ms; "
                    "split the line"
                )
            gap_ms = shot_ms - duration_ms
            shot.duration_ms = shot_ms

            alignment.append(
                {
                    "script_line_id": line.id,
                    "seq": line.seq,
                    "speaker": line.speaker,
                    "text": line.text,
                    "start_ms": cursor_ms,
                    "end_ms": cursor_ms + duration_ms,
                    "shot_end_ms": cursor_ms + shot_ms,
                    "duration_ms": duration_ms,
                    "shot_duration_ms": shot_ms,
                }
            )
            parts.append((clip, gap_ms))
            cursor_ms += shot_ms
            await session.commit()

        episode = await session.get(Episode, episode_id)
        episode_dir = _resolve(settings.audio_root) / "episodes" / episode_id
        episode_dir.mkdir(parents=True, exist_ok=True)
        audio_path = episode_dir / "audio.wav"
        total_ms = assemble_audio(parts, audio_path)
        if abs(total_ms - cursor_ms) > 500:
            raise RuntimeError(
                f"audio length {total_ms}ms does not match timeline {cursor_ms}ms"
            )

        alignment_path = episode_dir / "alignment.json"
        alignment_path.write_text(
            json.dumps(
                {
                    "granularity": "sentence",
                    "total_ms": cursor_ms,
                    "lines": alignment,
                },
                ensure_ascii=False,
                indent=2,
            ),
            encoding="utf-8",
        )

        episode.audio_path = str(audio_path)
        episode.audio_meta = {
            "provider": PROVIDER,
            "model": MODEL,
            "voice_key": voice_key,
            "ref_audio": str(ref_audio),
            "sample_rate": 48000,
            "pause_ms": settings.voice_pause_ms,
            "total_ms": total_ms,
            "alignment_path": str(alignment_path),
            "alignment_granularity": "sentence",
            "lines": alignment,
            "generated_at": datetime.now(timezone.utc).isoformat(),
        }
        spec = await build_episode_render_spec(session, episode)
        episode.render_spec = spec.model_dump()
        episode.version += 1

        node.status = NodeStatus.SUCCESS
        node.finished_at = datetime.now(timezone.utc)
        node.heartbeat_at = node.finished_at
        node.output_ref = str(audio_path)
        node.error = None
        await session.commit()

    async with task_session() as session:
        await transition_episode(session, episode_id, EpisodeStatus.ALIGNING)
        episode = await session.get(Episode, episode_id)
        episode.current_node = None
        episode.health = "OK"
        await session.commit()

    logger.info(
        "voice ready episode=%s lines=%d total_ms=%d",
        episode_id,
        len(lines),
        total_ms,
    )

    if settings.voice_auto_align:
        try:
            async with task_session() as session:
                await start_align(session, episode_id)
                await session.commit()
            logger.info("auto alignment queued episode=%s", episode_id)
        except Exception:
            logger.exception("auto alignment queue failed episode=%s", episode_id)
            async with task_session() as session:
                episode = await session.get(Episode, episode_id)
                if episode is not None:
                    episode.health = "FAILED"
                    episode.current_node = None
                await session.commit()
    elif settings.voice_auto_render:
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


@celery_app.task(name="voice.episode", bind=True, max_retries=1)
def voice_episode_task(self, episode_id: str, node_run_id: str):
    try:
        run_async(_voice_episode(episode_id, node_run_id))
    except Exception as exc:
        logger.exception("voice generation failed episode=%s", episode_id)
        if self.request.retries < self.max_retries:
            raise self.retry(exc=exc, countdown=10)
        run_async(_mark_failed(episode_id, node_run_id, str(exc)))
        raise

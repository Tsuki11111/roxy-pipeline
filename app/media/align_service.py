from __future__ import annotations

import hashlib
import json
from pathlib import Path

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.models.core import (
    Episode,
    EpisodeStatus,
    LineAudio,
    NodeRun,
    NodeStatus,
    ScriptLine,
)
from app.workflow.outbox import enqueue_outbox

PROJECT_ROOT = Path(__file__).resolve().parents[2]


class AlignRequestError(Exception):
    pass


class AlignConflict(AlignRequestError):
    pass


def _resolve(value: str) -> Path:
    path = Path(value).expanduser()
    return path if path.is_absolute() else (PROJECT_ROOT / path).resolve()


async def start_align(
    session: AsyncSession,
    episode_id: str,
    *,
    retry: bool = False,
) -> tuple[Episode, NodeRun]:
    episode = await session.get(Episode, episode_id, with_for_update=True)
    if episode is None:
        raise LookupError(f"episode not found: {episode_id}")
    if episode.status != EpisodeStatus.ALIGNING:
        raise AlignConflict(
            f"episode status {episode.status.value} is not ALIGNING"
        )
    if retry and episode.health != "FAILED":
        raise AlignConflict("only a failed alignment run can be retried")
    if not episode.audio_path or not Path(episode.audio_path).is_file():
        raise AlignRequestError("episode has no assembled audio")
    if not episode.audio_meta or not episode.audio_meta.get("lines"):
        raise AlignRequestError("episode has no sentence alignment")

    lines = list(
        await session.scalars(
            select(ScriptLine)
            .where(ScriptLine.episode_id == episode_id)
            .order_by(ScriptLine.seq)
        )
    )
    if not lines:
        raise AlignRequestError("episode has no script lines")
    entries = episode.audio_meta["lines"]
    if len(entries) != len(lines):
        raise AlignRequestError("sentence alignment is out of date")
    audios = list(
        await session.scalars(
            select(LineAudio).where(LineAudio.episode_id == episode_id)
        )
    )
    audio_by_line = {audio.script_line_id: audio for audio in audios}
    missing = [line.seq for line in lines if line.id not in audio_by_line]
    if missing:
        raise AlignRequestError(f"missing line audio for seq {missing}")

    settings = get_settings()
    model_dir = _resolve(settings.align_model_dir)
    if not model_dir.is_dir():
        raise AlignRequestError(f"alignment model not found: {model_dir}")
    digest_source = {
        "episode_id": episode.id,
        "lines": [
            {
                "id": line.id,
                "text": line.text,
                "checksum": audio_by_line[line.id].checksum,
                "start_ms": entry["start_ms"],
            }
            for line, entry in zip(
                lines, episode.audio_meta["lines"], strict=False
            )
        ],
        "model": str(model_dir),
        "device": settings.align_device,
    }
    digest = hashlib.sha256(
        json.dumps(digest_source, ensure_ascii=False, sort_keys=True).encode("utf-8")
    ).hexdigest()

    node = await session.scalar(
        select(NodeRun)
        .where(
            NodeRun.episode_id == episode.id,
            NodeRun.node_key == "align.episode",
            NodeRun.input_hash == digest,
        )
        .with_for_update()
    )
    if node is None:
        node = NodeRun(
            episode_id=episode.id,
            node_key="align.episode",
            status=NodeStatus.PENDING,
            input_hash=digest,
        )
        session.add(node)
    elif node.status in {NodeStatus.PENDING, NodeStatus.RUNNING}:
        raise AlignConflict("alignment is already queued or running")
    elif node.status == NodeStatus.SUCCESS:
        raise AlignConflict("this alignment input already produced a result")
    else:
        node.status = NodeStatus.PENDING
        node.attempt += 1
        node.error = None

    episode.current_node = "align.episode"
    episode.health = "OK"
    await session.flush()
    await enqueue_outbox(
        session,
        "align.episode",
        {"episode_id": episode.id, "node_run_id": node.id},
        episode_id=episode.id,
    )
    return episode, node

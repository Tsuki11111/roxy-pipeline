from __future__ import annotations

import hashlib
import json
from pathlib import Path

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.voice.audio import sha256_file
from app.models.core import (
    Episode,
    EpisodeStatus,
    NodeRun,
    NodeStatus,
    ScriptLine,
    Shot,
    ShotLine,
)
from app.workflow.outbox import enqueue_outbox
from app.storage.paths import PROJECT_ROOT

PROVIDER = "indextts2"
MODEL = "IndexTTS-2"


class VoiceRequestError(Exception):
    pass


class VoiceConflict(VoiceRequestError):
    pass


def _resolve(value: str) -> Path:
    path = Path(value).expanduser()
    return path if path.is_absolute() else (PROJECT_ROOT / path).resolve()


def voice_identity() -> tuple[str, Path]:
    ref_audio = _resolve(get_settings().tts_indextts_ref_audio)
    if not ref_audio.is_file():
        raise VoiceRequestError(f"reference audio not found: {ref_audio}")
    raw = f"{PROVIDER}|{MODEL}|{sha256_file(ref_audio)}"
    return hashlib.sha256(raw.encode("utf-8")).hexdigest(), ref_audio


def text_hash(text: str) -> str:
    return hashlib.sha256(text.strip().encode("utf-8")).hexdigest()


async def _load_lines_shots(
    session: AsyncSession, episode_id: str
) -> tuple[list[ScriptLine], list[Shot], list[ShotLine]]:
    lines = list(
        await session.scalars(
            select(ScriptLine)
            .where(ScriptLine.episode_id == episode_id)
            .order_by(ScriptLine.seq)
        )
    )
    shots = list(
        await session.scalars(
            select(Shot)
            .where(Shot.episode_id == episode_id)
            .order_by(Shot.seq)
        )
    )
    shot_lines = list(
        await session.scalars(
            select(ShotLine)
            .where(ShotLine.episode_id == episode_id)
            .order_by(ShotLine.shot_id, ShotLine.seq)
        )
    )
    return lines, shots, shot_lines


def shot_line_map(
    shots: list[Shot], shot_lines: list[ShotLine]
) -> dict[str, list[str]]:
    mapping: dict[str, list[str]] = {}
    for row in shot_lines:
        mapping.setdefault(row.shot_id, []).append(row.script_line_id)
    for shot in shots:
        mapping.setdefault(shot.id, [shot.script_line_id])
    return mapping


def validate_line_coverage(
    lines: list[ScriptLine], shots: list[Shot], shot_lines: list[ShotLine]
) -> dict[str, list[str]]:
    mapping = shot_line_map(shots, shot_lines)
    covered = [line_id for ids in mapping.values() for line_id in ids]
    if sorted(covered) != sorted(line.id for line in lines):
        raise VoiceRequestError(
            "script lines must be covered exactly once by shots"
        )
    return mapping


async def start_voice(
    session: AsyncSession,
    episode_id: str,
    *,
    retry: bool = False,
) -> tuple[Episode, NodeRun]:
    episode = await session.get(Episode, episode_id, with_for_update=True)
    if episode is None:
        raise LookupError(f"episode not found: {episode_id}")
    if episode.status != EpisodeStatus.VOICING:
        raise VoiceConflict(
            f"episode status {episode.status.value} is not VOICING"
        )
    if retry and episode.health != "FAILED":
        raise VoiceConflict("only a failed voice run can be retried")

    lines, shots, shot_lines = await _load_lines_shots(session, episode.id)
    if not lines:
        raise VoiceRequestError("episode has no script lines")
    if not shots:
        raise VoiceRequestError("episode has no shots")
    line_map = validate_line_coverage(lines, shots, shot_lines)

    settings = get_settings()
    voice_key, ref_audio = voice_identity()
    digest_source = {
        "episode_id": episode.id,
        "lines": [
            {
                "id": line.id,
                "version": line.version,
                "speaker": line.speaker,
                "text": line.text,
            }
            for line in lines
        ],
        "voice_key": voice_key,
        "ref_audio": str(ref_audio),
        "shots": [
            {"id": shot.id, "lines": line_map.get(shot.id, [])}
            for shot in shots
        ],
        "pause_ms": settings.voice_pause_ms,
        "auto_render": settings.voice_auto_render,
    }
    digest = hashlib.sha256(
        json.dumps(digest_source, ensure_ascii=False, sort_keys=True).encode("utf-8")
    ).hexdigest()

    node = await session.scalar(
        select(NodeRun)
        .where(
            NodeRun.episode_id == episode.id,
            NodeRun.node_key == "voice.episode",
            NodeRun.input_hash == digest,
        )
        .with_for_update()
    )
    if node is None:
        node = NodeRun(
            episode_id=episode.id,
            node_key="voice.episode",
            status=NodeStatus.PENDING,
            input_hash=digest,
            cache_key=voice_key,
        )
        session.add(node)
    elif node.status in {NodeStatus.PENDING, NodeStatus.RUNNING}:
        raise VoiceConflict("voice generation is already queued or running")
    elif node.status == NodeStatus.SUCCESS:
        raise VoiceConflict("this voice input already produced audio")
    else:
        node.status = NodeStatus.PENDING
        node.attempt += 1
        node.error = None

    episode.current_node = "voice.episode"
    episode.health = "OK"
    await session.flush()

    await enqueue_outbox(
        session,
        "voice.episode",
        {"episode_id": episode.id, "node_run_id": node.id},
        episode_id=episode.id,
    )
    return episode, node

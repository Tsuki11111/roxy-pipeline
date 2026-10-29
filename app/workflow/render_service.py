from __future__ import annotations

import hashlib
import json

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from pydantic import ValidationError

from app.models.core import Episode, EpisodeStatus, NodeRun, NodeStatus
from app.render.models import EpisodeSpec
from app.render.stage import build_stage_payload
from app.render.timeline import build_timeline
from app.workflow.outbox import enqueue_outbox


class RenderRequestError(Exception):
    pass


class RenderConflict(RenderRequestError):
    pass


def spec_hash(spec: EpisodeSpec) -> str:
    raw = json.dumps(spec.model_dump(), ensure_ascii=False, sort_keys=True)
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


async def start_render(
    session: AsyncSession, episode_id: str
) -> tuple[Episode, NodeRun]:
    """Queue a manual render for M1.2.

    The normal human gates (topic/script) and the TTS/alignment stages are not
    implemented yet, so this path sets RENDERING directly. It is replaced by the
    normal ALIGNING -> RENDERING transition once those stages exist.
    """
    episode = await session.get(Episode, episode_id, with_for_update=True)
    if episode is None:
        raise LookupError(f"episode not found: {episode_id}")
    if episode.status in {EpisodeStatus.READY, EpisodeStatus.PUBLISHED}:
        raise RenderConflict("episode is already finished")
    if episode.status == EpisodeStatus.CANCELLED:
        raise RenderConflict("episode is cancelled")
    if episode.render_spec is None:
        raise RenderRequestError("episode has no render_spec")

    try:
        spec = EpisodeSpec.model_validate(episode.render_spec)
        timeline = build_timeline(spec)
        build_stage_payload(spec, timeline)  # fail fast on missing assets/cards
    except ValidationError as exc:
        raise RenderRequestError(f"invalid render_spec: {exc}") from exc

    digest = spec_hash(spec)

    node = await session.scalar(
        select(NodeRun)
        .where(
            NodeRun.episode_id == episode.id,
            NodeRun.node_key == "render.episode",
            NodeRun.input_hash == digest,
        )
        .with_for_update()
    )
    if node is None:
        node = NodeRun(
            episode_id=episode.id,
            node_key="render.episode",
            status=NodeStatus.PENDING,
            input_hash=digest,
        )
        session.add(node)
    elif node.status in {NodeStatus.PENDING, NodeStatus.RUNNING}:
        raise RenderConflict("render is already queued or running")
    elif node.status == NodeStatus.SUCCESS:
        raise RenderConflict("this render spec already produced a video")
    else:
        node.status = NodeStatus.PENDING
        node.attempt += 1
        node.error = None

    episode.status = EpisodeStatus.RENDERING
    episode.current_node = "render.episode"
    episode.health = "OK"
    episode.version += 1
    await session.flush()

    await enqueue_outbox(
        session,
        "render.episode",
        {
            "episode_id": episode.id,
            "node_run_id": node.id,
            "spec": spec.model_dump(),
            "audio_path": episode.audio_path,
        },
        episode_id=episode.id,
    )
    return episode, node

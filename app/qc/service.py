from __future__ import annotations

import hashlib
import json
from pathlib import Path

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.voice.audio import sha256_file
from app.models.core import Episode, EpisodeStatus, NodeRun, NodeStatus
from app.workflow.outbox import enqueue_outbox


class QcRequestError(Exception):
    pass


class QcConflict(QcRequestError):
    pass


async def start_qc(
    session: AsyncSession,
    episode_id: str,
    *,
    retry: bool = False,
) -> tuple[Episode, NodeRun]:
    episode = await session.get(Episode, episode_id, with_for_update=True)
    if episode is None:
        raise LookupError(f"episode not found: {episode_id}")
    if episode.status != EpisodeStatus.QC:
        raise QcConflict(f"episode status {episode.status.value} is not QC")
    if retry and episode.health != "FAILED":
        raise QcConflict("only a failed QC run can be retried")
    if not episode.output_path or not Path(episode.output_path).is_file():
        raise QcRequestError("episode has no rendered video")
    if not episode.render_spec:
        raise QcRequestError("episode has no render spec")

    settings = get_settings()
    spec_raw = json.dumps(episode.render_spec, ensure_ascii=False, sort_keys=True)
    digest = hashlib.sha256(
        json.dumps(
            {
                "episode_id": episode.id,
                "video": sha256_file(Path(episode.output_path)),
                "spec": hashlib.sha256(spec_raw.encode("utf-8")).hexdigest(),
                "frames_per_shot": settings.qc_frames_per_shot,
                "frame_scale": settings.qc_frame_scale,
                "vision_model": settings.deepseek_model,
            },
            ensure_ascii=False,
            sort_keys=True,
        ).encode("utf-8")
    ).hexdigest()

    node = await session.scalar(
        select(NodeRun)
        .where(
            NodeRun.episode_id == episode.id,
            NodeRun.node_key == "qc.episode",
            NodeRun.input_hash == digest,
        )
        .with_for_update()
    )
    if node is None:
        node = NodeRun(
            episode_id=episode.id,
            node_key="qc.episode",
            status=NodeStatus.PENDING,
            input_hash=digest,
        )
        session.add(node)
    elif node.status in {NodeStatus.PENDING, NodeStatus.RUNNING}:
        raise QcConflict("QC is already queued or running")
    elif node.status == NodeStatus.SUCCESS:
        if retry and episode.health == "FAILED":
            node.status = NodeStatus.PENDING
            node.attempt += 1
            node.error = None
        else:
            raise QcConflict("this video already passed through QC")
    else:
        node.status = NodeStatus.PENDING
        node.attempt += 1
        node.error = None

    episode.current_node = "qc.episode"
    episode.health = "OK"
    await session.flush()
    await enqueue_outbox(
        session,
        "qc.episode",
        {"episode_id": episode.id, "node_run_id": node.id},
        episode_id=episode.id,
    )
    return episode, node

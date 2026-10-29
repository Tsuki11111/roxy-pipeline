from __future__ import annotations

import hashlib
import json

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.core import (
    Episode,
    EpisodeStatus,
    NodeRun,
    NodeStatus,
    ScriptLine,
    Series,
)
from app.agents.storyboard.prompts import STORYBOARD_GRAPH_VERSION, prompt_hash
from app.workflow.outbox import enqueue_outbox


class StoryboardRequestError(Exception):
    pass


class StoryboardConflict(StoryboardRequestError):
    pass


async def start_storyboard(
    session: AsyncSession,
    episode_id: str,
    *,
    regenerate: bool = False,
    retry: bool = False,
) -> tuple[Episode, NodeRun]:
    episode = await session.get(Episode, episode_id, with_for_update=True)
    if episode is None:
        raise LookupError(f"episode not found: {episode_id}")
    if episode.status != EpisodeStatus.STORYBOARDING:
        raise StoryboardConflict(
            f"episode status {episode.status.value} is not STORYBOARDING"
        )
    if retry and episode.health != "FAILED":
        raise StoryboardConflict("only a failed storyboard generation can be retried")

    lines = list(
        await session.scalars(
            select(ScriptLine)
            .where(ScriptLine.episode_id == episode.id)
            .order_by(ScriptLine.seq)
        )
    )
    if not lines:
        raise StoryboardRequestError("episode has no script lines")

    series = await session.get(Series, episode.series_id)
    labels = (
        list(series.section_labels)
        if series is not None and series.section_labels
        else []
    )
    if regenerate:
        episode.version += 1

    digest_source = {
        "episode_id": episode.id,
        "lines": [
            {"seq": line.seq, "section": line.section, "text": line.text}
            for line in lines
        ],
        "section_labels": labels,
        "version": episode.version,
        "graph_version": STORYBOARD_GRAPH_VERSION,
        "prompt_hash": prompt_hash(),
    }
    digest = hashlib.sha256(
        json.dumps(digest_source, ensure_ascii=False, sort_keys=True).encode("utf-8")
    ).hexdigest()

    node = await session.scalar(
        select(NodeRun)
        .where(
            NodeRun.episode_id == episode.id,
            NodeRun.node_key == "storyboard.generate",
            NodeRun.input_hash == digest,
        )
        .with_for_update()
    )
    if node is None:
        node = NodeRun(
            episode_id=episode.id,
            node_key="storyboard.generate",
            status=NodeStatus.PENDING,
            input_hash=digest,
            cache_key=prompt_hash(),
        )
        session.add(node)
    elif node.status in {NodeStatus.PENDING, NodeStatus.RUNNING}:
        raise StoryboardConflict("storyboard generation is already queued or running")
    elif node.status == NodeStatus.SUCCESS:
        raise StoryboardConflict("this storyboard input already produced a result")
    else:
        node.status = NodeStatus.PENDING
        node.attempt += 1
        node.error = None

    episode.current_node = "storyboard.generate"
    episode.health = "OK"
    await session.flush()

    await enqueue_outbox(
        session,
        "storyboard.generate",
        {"episode_id": episode.id, "node_run_id": node.id},
        episode_id=episode.id,
    )
    return episode, node

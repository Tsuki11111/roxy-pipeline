from __future__ import annotations

import hashlib
import json

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.agents.script.prompts import SCRIPT_GRAPH_VERSION, prompt_hash
from app.agents.script.validation import DEFAULT_SECTION_LABELS
from app.models.core import Episode, EpisodeStatus, NodeRun, NodeStatus, Series
from app.workflow.outbox import enqueue_outbox


class ScriptRequestError(Exception):
    pass


class ScriptConflict(ScriptRequestError):
    pass


async def start_script(
    session: AsyncSession,
    episode_id: str,
    *,
    regenerate: bool = False,
    retry: bool = False,
) -> tuple[Episode, NodeRun]:
    episode = await session.get(Episode, episode_id, with_for_update=True)
    if episode is None:
        raise LookupError(f"episode not found: {episode_id}")

    if retry:
        if episode.status != EpisodeStatus.SCRIPTING or episode.health != "FAILED":
            raise ScriptConflict("only a failed script generation can be retried")
    else:
        expected = (
            EpisodeStatus.SCRIPT_REVIEW
            if regenerate
            else EpisodeStatus.TOPIC_CONFIRMED
        )
        if episode.status != expected:
            raise ScriptConflict(
                f"episode status {episode.status.value} cannot start script "
                f"(expected {expected.value})"
            )

    series = await session.get(Series, episode.series_id)
    labels = (
        list(series.section_labels)
        if series is not None and series.section_labels
        else list(DEFAULT_SECTION_LABELS)
    )
    if regenerate:
        episode.version += 1

    digest_source = {
        "episode_id": episode.id,
        "title": episode.title,
        "topic": episode.topic,
        "target_duration_s": episode.target_duration_s,
        "section_labels": labels,
        "version": episode.version,
        "graph_version": SCRIPT_GRAPH_VERSION,
        "prompt_hash": prompt_hash(),
    }
    digest = hashlib.sha256(
        json.dumps(digest_source, ensure_ascii=False, sort_keys=True).encode("utf-8")
    ).hexdigest()

    node = await session.scalar(
        select(NodeRun)
        .where(
            NodeRun.episode_id == episode.id,
            NodeRun.node_key == "script.generate",
            NodeRun.input_hash == digest,
        )
        .with_for_update()
    )
    if node is None:
        node = NodeRun(
            episode_id=episode.id,
            node_key="script.generate",
            status=NodeStatus.PENDING,
            input_hash=digest,
            cache_key=prompt_hash(),
        )
        session.add(node)
    elif node.status in {NodeStatus.PENDING, NodeStatus.RUNNING}:
        raise ScriptConflict("script generation is already queued or running")
    elif node.status == NodeStatus.SUCCESS:
        raise ScriptConflict("this script input already produced a result")
    else:
        node.status = NodeStatus.PENDING
        node.attempt += 1
        node.error = None

    episode.status = EpisodeStatus.SCRIPTING
    episode.current_node = "script.generate"
    episode.health = "OK"
    await session.flush()

    await enqueue_outbox(
        session,
        "script.generate",
        {"episode_id": episode.id, "node_run_id": node.id},
        episode_id=episode.id,
    )
    return episode, node

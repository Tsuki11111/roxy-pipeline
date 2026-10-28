from __future__ import annotations

import logging
from datetime import datetime, timezone

from sqlalchemy import delete

from app.agents.prompts import SCRIPT_GRAPH_VERSION, prompt_hash
from app.agents.script_graph import run_script_graph
from app.agents.script_validation import (
    DEFAULT_SECTION_LABELS,
    ScriptLineData,
    target_chars_for_duration,
    validate_script,
)
from app.core.config import get_settings
from app.models.core import (
    Episode,
    EpisodeStatus,
    NodeRun,
    NodeStatus,
    ScriptLine,
    Series,
)
from app.providers.llm import build_llm
from app.workflow.celery_app import celery_app
from app.workflow.db import run_async, task_session

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


async def _generate_script(episode_id: str, node_run_id: str) -> None:
    settings = get_settings()
    async with task_session() as session:
        episode = await session.get(Episode, episode_id)
        node = await session.get(NodeRun, node_run_id)
        if episode is None or node is None:
            raise RuntimeError(f"episode/node not found: {episode_id}/{node_run_id}")
        series = await session.get(Series, episode.series_id)
        section_labels = (
            list(series.section_labels)
            if series is not None and series.section_labels
            else list(DEFAULT_SECTION_LABELS)
        )
        title = episode.title
        topic = episode.topic or episode.title
        target_duration_s = episode.target_duration_s

        now = datetime.now(timezone.utc)
        node.status = NodeStatus.RUNNING
        node.started_at = node.started_at or now
        node.heartbeat_at = now
        node.error = None
        episode.status = EpisodeStatus.SCRIPTING
        episode.current_node = "script.generate"
        episode.health = "OK"
        await session.commit()

    target_chars = target_chars_for_duration(
        target_duration_s, settings.script_target_chars_per_minute
    )

    try:
        state = await run_script_graph(
            episode_id=episode_id,
            title=title,
            topic=topic,
            target_duration_s=target_duration_s,
            target_chars=target_chars,
            section_labels=section_labels,
            thread_id=f"{episode_id}:script:{node_run_id}",
            llm=build_llm(),
        )
        lines = [ScriptLineData(**line) for line in state.get("lines", [])]
        validation = validate_script(
            lines,
            target_duration_s=target_duration_s,
            section_labels=section_labels,
            target_chars_per_minute=settings.script_target_chars_per_minute,
            roxy_ratio_min=settings.script_roxy_ratio_min,
            roxy_ratio_max=settings.script_roxy_ratio_max,
            min_lines_for_ratio=settings.script_min_lines_for_ratio,
        )
    except Exception as exc:
        logger.exception("script generation failed episode=%s", episode_id)
        await _mark_failed(episode_id, node_run_id, str(exc))
        raise

    async with task_session() as session:
        episode = await session.get(Episode, episode_id)
        node = await session.get(NodeRun, node_run_id)
        if episode is None or node is None:
            raise RuntimeError(f"episode/node disappeared: {episode_id}/{node_run_id}")

        await session.execute(
            delete(ScriptLine).where(ScriptLine.episode_id == episode_id)
        )
        for line in lines:
            session.add(
                ScriptLine(
                    episode_id=episode_id,
                    seq=line.seq,
                    speaker=line.speaker,
                    section=line.section,
                    text=line.text,
                    char_count=len(line.text),
                    version=1,
                )
            )

        episode.script_meta = {
            "outline": state.get("outline", {}),
            "sections": state.get("sections", []),
            "validation": validation.model_dump(),
            "graph_version": SCRIPT_GRAPH_VERSION,
            "prompt_hash": prompt_hash(),
            "line_count": len(lines),
            "generated_at": datetime.now(timezone.utc).isoformat(),
        }
        episode.status = EpisodeStatus.SCRIPT_REVIEW
        episode.current_node = None
        episode.health = "OK" if validation.valid else "WARNING"
        episode.version += 1

        node.status = NodeStatus.SUCCESS
        node.finished_at = datetime.now(timezone.utc)
        node.heartbeat_at = node.finished_at
        node.output_ref = f"script:{len(lines)}"
        node.error = None
        await session.commit()

    logger.info(
        "script generated episode=%s lines=%d valid=%s",
        episode_id,
        len(lines),
        validation.valid,
    )


@celery_app.task(name="script.generate", bind=True, max_retries=1)
def generate_script_task(self, episode_id: str, node_run_id: str):
    try:
        run_async(_generate_script(episode_id, node_run_id))
    except Exception as exc:
        if self.request.retries < self.max_retries:
            raise self.retry(exc=exc, countdown=10)
        raise

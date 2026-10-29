from __future__ import annotations

import logging
from datetime import datetime, timezone

from sqlalchemy import delete, select

from app.models.core import (
    Episode,
    NodeRun,
    NodeStatus,
    ScriptLine,
    Series,
    Shot,
)
from app.providers.llm import build_llm
from app.agents.storyboard.grammar import load_character_assets
from app.agents.storyboard.graph import run_storyboard_graph
from app.agents.storyboard.prompts import STORYBOARD_GRAPH_VERSION, prompt_hash
from app.agents.storyboard.spec_builder import shot_cache_key
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


async def _generate_storyboard(episode_id: str, node_run_id: str) -> None:
    async with task_session() as session:
        episode = await session.get(Episode, episode_id)
        node = await session.get(NodeRun, node_run_id)
        if episode is None or node is None:
            raise RuntimeError(f"episode/node not found: {episode_id}/{node_run_id}")
        series = await session.get(Series, episode.series_id)
        if series is None or not series.section_labels:
            raise RuntimeError("series has no section labels")
        lines = list(
            await session.scalars(
                select(ScriptLine)
                .where(ScriptLine.episode_id == episode_id)
                .order_by(ScriptLine.seq)
            )
        )
        if not lines:
            raise RuntimeError("episode has no script lines")
        section_labels = list(series.section_labels)
        pack = series.character_pack_id or None
        template_version = series.template_version or "v1"

        now = datetime.now(timezone.utc)
        node.status = NodeStatus.RUNNING
        node.started_at = node.started_at or now
        node.heartbeat_at = now
        node.error = None
        episode.current_node = "storyboard.generate"
        episode.health = "OK"
        await session.commit()

    line_payload = [
        {
            "seq": line.seq,
            "section": line.section,
            "speaker": line.speaker,
            "text": line.text,
        }
        for line in lines
    ]

    try:
        state = await run_storyboard_graph(
            episode_id=episode_id,
            section_labels=section_labels,
            lines=line_payload,
            thread_id=f"{episode_id}:storyboard:{node_run_id}",
            llm=build_llm(),
            catalog=load_character_assets(pack),
        )
    except Exception as exc:
        logger.exception("storyboard generation failed episode=%s", episode_id)
        await _mark_failed(episode_id, node_run_id, str(exc))
        raise

    shots = state.get("shots", [])
    report = state.get("report", {})
    line_by_seq = {line.seq: line for line in lines}

    try:
        async with task_session() as session:
            episode = await session.get(Episode, episode_id)
            node = await session.get(NodeRun, node_run_id)
            if episode is None or node is None:
                raise RuntimeError(
                    f"episode/node disappeared: {episode_id}/{node_run_id}"
                )

            await session.execute(delete(Shot).where(Shot.episode_id == episode_id))
            section_order: list[str] = []
            for item in shots:
                line = line_by_seq.get(int(item["line_seq"]))
                if line is None:
                    continue
                section_new = line.section not in section_order
                if section_new:
                    section_order.append(line.section)
                move = "none"
                if section_new and item.get("character_image"):
                    move = (
                        "slide_in_left"
                        if len(section_order) % 2 == 1
                        else "slide_in_right"
                    )
                payload = {
                    "style": item.get("card_style", ""),
                    "text": line.text,
                    "motion": item.get("motion", "idle_breathe"),
                    "move": move,
                }
                session.add(
                    Shot(
                        episode_id=episode_id,
                        script_line_id=line.id,
                        seq=int(item["seq"]),
                        duration_ms=int(item["duration_ms"]),
                        card_type=item["card_type"],
                        card_payload=payload,
                        character_image=item.get("character_image"),
                        character_position=item.get("character_position", "left"),
                        bg=item.get("bg", "paper"),
                        transition=item.get("transition", "cut"),
                        cache_key=shot_cache_key(
                            text=line.text,
                            card_type=item["card_type"],
                            card_payload=payload,
                            character_image=item.get("character_image"),
                            template_version=template_version,
                        ),
                        template_version=template_version,
                    )
                )

            episode.storyboard_meta = {
                "rhythm": report,
                "graph_version": STORYBOARD_GRAPH_VERSION,
                "prompt_hash": prompt_hash(),
                "generated_at": datetime.now(timezone.utc).isoformat(),
                "shot_count": len(shots),
            }
            episode.current_node = None
            episode.health = "OK" if report.get("valid") else "WARNING"
            episode.version += 1

            node.status = NodeStatus.SUCCESS
            node.finished_at = datetime.now(timezone.utc)
            node.heartbeat_at = node.finished_at
            node.output_ref = f"storyboard:{len(shots)}"
            node.error = None
            await session.commit()
    except Exception as exc:
        logger.exception("storyboard persistence failed episode=%s", episode_id)
        await _mark_failed(episode_id, node_run_id, str(exc))
        raise

    logger.info(
        "storyboard generated episode=%s shots=%d valid=%s",
        episode_id,
        len(shots),
        report.get("valid"),
    )


@celery_app.task(name="storyboard.generate", bind=True, max_retries=1)
def generate_storyboard_task(self, episode_id: str, node_run_id: str):
    try:
        run_async(_generate_storyboard(episode_id, node_run_id))
    except Exception as exc:
        if self.request.retries < self.max_retries:
            raise self.retry(exc=exc, countdown=10)
        raise

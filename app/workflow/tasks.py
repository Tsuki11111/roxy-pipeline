"""Celery 任务：outbox 派发与 stale 节点回收。"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

from celery.utils.log import get_task_logger
from sqlalchemy import select

from app.core.config import get_settings
from app.models.core import Episode, EpisodeStatus, NodeRun, NodeStatus
from app.workflow.celery_app import celery_app
from app.db.task import run_async, task_session
from app.workflow.outbox import dispatch_pending
from app.workflow.cleanup import cleanup_temp_dirs

logger = get_task_logger(__name__)


async def _reconcile_stale() -> list[str]:
    settings = get_settings()
    cutoff = datetime.now(timezone.utc) - timedelta(
        seconds=settings.reconciler_stale_s
    )
    stale: list[str] = []
    async with task_session() as session:
        nodes = list(
            await session.scalars(
                select(NodeRun).where(
                    NodeRun.status == NodeStatus.RUNNING,
                    NodeRun.heartbeat_at.is_not(None),
                    NodeRun.heartbeat_at < cutoff,
                )
            )
        )
        for node in nodes:
            episode = await session.get(Episode, node.episode_id)
            if episode is None or episode.status in {
                EpisodeStatus.PUBLISHED,
                EpisodeStatus.CANCELLED,
                EpisodeStatus.READY,
            }:
                continue
            node.status = NodeStatus.FAILED
            node.finished_at = datetime.now(timezone.utc)
            node.error = (
                f"stale heartbeat: no update for {settings.reconciler_stale_s}s"
            )
            if episode.current_node == node.node_key:
                episode.health = "FAILED"
                episode.current_node = None
            stale.append(node.id)
        await session.commit()
    return stale


@celery_app.task(name="workflow.reconcile_nodes")
def reconcile_nodes_task():
    stale = run_async(_reconcile_stale())
    if stale:
        logger.warning("marked %d stale node(s): %s", len(stale), stale)
    return {"stale": stale}


@celery_app.task(name="workflow.dispatch_outbox")
def dispatch_outbox_task(limit: int = 50):
    async def _dispatch():
        async with task_session() as session:
            events = await dispatch_pending(session, limit=limit)
            return [event.id for event in events]

    dispatched = run_async(_dispatch())
    if dispatched:
        logger.info("dispatched %d outbox events", len(dispatched))
    return {"dispatched": dispatched}


@celery_app.task(name="workflow.cleanup")
def cleanup_temp_task():
    async def _cleanup():
        async with task_session() as session:
            return await cleanup_temp_dirs(session)

    result = run_async(_cleanup())
    logger.info(
        "temp cleanup removed %d dir(s), skipped %d",
        len(result.get("deleted", [])),
        len(result.get("skipped", [])),
    )
    return result

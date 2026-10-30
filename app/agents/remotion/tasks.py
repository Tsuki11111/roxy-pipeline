from __future__ import annotations

import logging
from datetime import datetime, timezone

from app.agents.remotion.service import RemotionError, generate_remotion_code
from app.models.core import Episode, NodeRun, NodeStatus
from app.workflow.cancel import TaskCancelled, ensure_not_cancelled
from app.workflow.celery_app import celery_app
from app.workflow.db import run_async, task_session

logger = logging.getLogger(__name__)


async def _run(episode_id: str, node_run_id: str, shot_ids: list[str] | None) -> None:
    async with task_session() as session:
        episode = await session.get(Episode, episode_id)
        node = await session.get(NodeRun, node_run_id)
        if episode is None or node is None:
            raise RemotionError("episode/node not found")
        await ensure_not_cancelled(session, episode_id)
        node.status = NodeStatus.RUNNING
        node.started_at = node.started_at or datetime.now(timezone.utc)
        node.heartbeat_at = datetime.now(timezone.utc)
        node.error = None
        episode.current_node = "remotion.generate"
        episode.health = "OK"
        await session.commit()

        try:
            result = await generate_remotion_code(
                session, episode_id, node_run_id, shot_ids=shot_ids
            )
        except Exception as exc:
            await session.rollback()
            async with task_session() as failed:
                episode = await failed.get(Episode, episode_id)
                node = await failed.get(NodeRun, node_run_id)
                now = datetime.now(timezone.utc)
                if node is not None:
                    node.status = NodeStatus.FAILED
                    node.finished_at = now
                    node.heartbeat_at = now
                    node.error = str(exc)[:4000]
                if episode is not None:
                    episode.current_node = None
                    episode.health = "WARNING"
                    meta = dict(episode.remotion_meta or {})
                    meta["status"] = "failed"
                    meta["error"] = str(exc)[:2000]
                    episode.remotion_meta = meta
                await failed.commit()
            raise

        episode = await session.get(Episode, episode_id)
        node = await session.get(NodeRun, node_run_id)
        now = datetime.now(timezone.utc)
        if node is not None:
            node.status = NodeStatus.SUCCESS
            node.finished_at = now
            node.heartbeat_at = now
            node.error = None
            node.output_ref = str(result.get("meta", {}).get("work_dir") or "")
        if episode is not None:
            episode.current_node = None
            episode.health = "OK" if result.get("meta", {}).get("enabled") else "WARNING"
        await session.commit()
        logger.info(
            "remotion codegen done episode=%s enabled=%s",
            episode_id,
            result.get("meta", {}).get("enabled"),
        )


@celery_app.task(name="remotion.generate", bind=True)
def remotion_generate_task(
    self,
    episode_id: str,
    node_run_id: str,
    shot_ids: list[str] | None = None,
):
    try:
        run_async(_run(episode_id, node_run_id, shot_ids))
    except TaskCancelled:
        logger.info("remotion codegen cancelled episode=%s", episode_id)
        raise

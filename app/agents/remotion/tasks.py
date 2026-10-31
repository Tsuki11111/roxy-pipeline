from __future__ import annotations

import logging
from datetime import datetime, timezone

from app.agents.remotion.service import (
    RemotionError,
    _codegen_cancelled,
    generate_remotion_code,
)
from app.core.config import get_settings
from app.models.core import Episode, NodeRun, NodeStatus
from app.workflow.cancel import TaskCancelled, ensure_not_cancelled
from app.workflow.celery_app import celery_app
from app.workflow.db import run_async, task_session

logger = logging.getLogger(__name__)


async def _mark_interrupted(episode_id: str, node_run_id: str) -> None:
    async with task_session() as session:
        episode = await session.get(Episode, episode_id)
        node = await session.get(NodeRun, node_run_id)
        now = datetime.now(timezone.utc)
        if node is not None:
            node.status = NodeStatus.INTERRUPTED
            node.error = "cancelled by user"
            node.finished_at = now
            node.heartbeat_at = now
        if episode is not None:
            episode.current_node = None
            meta = dict(episode.remotion_meta or {})
            meta.pop("cancel_requested", None)
            meta["status"] = "ready" if meta.get("enabled") else "cancelled"
            meta["error"] = "cancelled by user"
            episode.remotion_meta = meta
            episode.health = "OK" if meta.get("enabled") else "WARNING"
        await session.commit()


async def _mark_no_render(episode_id: str, reason: str) -> None:
    async with task_session() as session:
        episode = await session.get(Episode, episode_id)
        if episode is not None:
            episode.health = "FAILED"
            episode.current_node = None
            meta = dict(episode.remotion_meta or {})
            meta["error"] = reason[:2000]
            episode.remotion_meta = meta
        await session.commit()


async def _queue_render(episode_id: str) -> None:
    from app.render.service import start_render

    async with task_session() as session:
        try:
            await start_render(session, episode_id)
            await session.commit()
            logger.info("auto render queued after remotion codegen episode=%s", episode_id)
        except Exception:
            logger.exception(
                "auto render queue failed after remotion codegen episode=%s",
                episode_id,
            )
            await session.rollback()
            async with task_session() as failed:
                episode = await failed.get(Episode, episode_id)
                if episode is not None:
                    episode.health = "FAILED"
                    episode.current_node = None
                await failed.commit()


async def _run(
    episode_id: str,
    node_run_id: str,
    shot_ids: list[str] | None,
    auto_render: bool = False,
) -> None:
    async with task_session() as session:
        episode = await session.get(Episode, episode_id)
        node = await session.get(NodeRun, node_run_id)
        if episode is None or node is None:
            raise RemotionError("episode/node not found")
        if node.status not in {NodeStatus.PENDING, NodeStatus.RUNNING}:
            logger.info(
                "skip remotion codegen node=%s status=%s", node_run_id, node.status
            )
            return
        await ensure_not_cancelled(session, episode_id)
        if await _codegen_cancelled(episode_id):
            await session.rollback()
            await _mark_interrupted(episode_id, node_run_id)
            return
        node.status = NodeStatus.RUNNING
        node.started_at = node.started_at or datetime.now(timezone.utc)
        node.heartbeat_at = datetime.now(timezone.utc)
        node.error = None
        episode.current_node = "remotion.generate"
        episode.health = "OK"
        await session.commit()

        try:
            result = await generate_remotion_code(
                session,
                episode_id,
                node_run_id,
                shot_ids=shot_ids,
                cancel_check=lambda: _codegen_cancelled(episode_id),
            )
        except TaskCancelled:
            await session.rollback()
            await _mark_interrupted(episode_id, node_run_id)
            raise
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
            if auto_render:
                if get_settings().remotion_only:
                    await _mark_no_render(
                        episode_id,
                        f"Remotion codegen failed; Playwright disabled: {exc}",
                    )
                else:
                    await _queue_render(episode_id)
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
        if auto_render:
            if get_settings().remotion_only and not result.get("meta", {}).get(
                "enabled"
            ):
                await _mark_no_render(
                    episode_id,
                    "Remotion code is not READY for every shot; Playwright disabled",
                )
            else:
                await _queue_render(episode_id)


@celery_app.task(name="remotion.generate", bind=True)
def remotion_generate_task(
    self,
    episode_id: str,
    node_run_id: str,
    shot_ids: list[str] | None = None,
    auto_render: bool = False,
):
    try:
        run_async(_run(episode_id, node_run_id, shot_ids, auto_render))
    except TaskCancelled:
        logger.info("remotion codegen cancelled episode=%s", episode_id)
        raise

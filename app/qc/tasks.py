from __future__ import annotations

import asyncio
import json
import logging
from datetime import datetime, timezone
from pathlib import Path

from sqlalchemy import delete, select

from app.core.config import get_settings
from app.models.core import (
    Episode,
    EpisodeStatus,
    NodeRun,
    NodeStatus,
    Review,
    ReviewLevel,
)
from app.providers.llm import build_llm
from app.qc.frames import extract_frames
from app.qc.rules import run_rules
from app.qc.vision import check_frames
from app.render.models import EpisodeSpec
from app.workflow.celery_app import celery_app
from app.workflow.cancel import TaskCancelled, ensure_not_cancelled
from app.workflow.db import run_async, task_session
from app.workflow.memory import release_memory
from app.workflow.state_machine import transition_episode

logger = logging.getLogger(__name__)

PROJECT_ROOT = Path(__file__).resolve().parents[2]


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


def _summary_level(issues: list[dict]) -> ReviewLevel:
    levels = {str(issue.get("level", "WARNING")).upper() for issue in issues}
    if "ERROR" in levels:
        return ReviewLevel.ERROR
    if "WARNING" in levels:
        return ReviewLevel.WARNING
    return ReviewLevel.PASS


async def _qc_episode(episode_id: str, node_run_id: str) -> None:
    settings = get_settings()
    qc_root = PROJECT_ROOT / "tmp" / "qc" / episode_id

    async with task_session() as session:
        episode = await session.get(Episode, episode_id)
        node = await session.get(NodeRun, node_run_id)
        if episode is None or node is None:
            raise RuntimeError(f"episode/node not found: {episode_id}/{node_run_id}")
        if episode.status != EpisodeStatus.QC:
            raise RuntimeError(
                f"episode status {episode.status.value} is not QC"
            )
        await ensure_not_cancelled(session, episode_id)
        if not episode.output_path:
            raise RuntimeError("episode has no output video")
        spec = EpisodeSpec.model_validate(episode.render_spec)
        video = Path(episode.output_path)

        now = datetime.now(timezone.utc)
        node.status = NodeStatus.RUNNING
        node.started_at = node.started_at or now
        node.heartbeat_at = now
        node.error = None
        episode.current_node = "qc.episode"
        episode.health = "OK"
        await session.commit()

    rules = await asyncio.to_thread(run_rules, episode, spec, video)
    frames = await asyncio.to_thread(
        extract_frames,
        video,
        spec,
        qc_root / "frames",
        per_shot=settings.qc_frames_per_shot,
        max_frames=settings.qc_max_frames,
        scale=settings.qc_frame_scale,
    )

    vision: list[dict] = []
    if frames:
        llm = build_llm()
        vision = await check_frames(
            frames,
            llm,
            batch_size=settings.qc_vision_batch,
            max_tokens=settings.qc_vision_max_tokens,
            timeout_s=settings.qc_vision_timeout_s,
            blocking=settings.qc_vision_blocking,
        )

    issues = rules + vision
    level = _summary_level(issues)
    errors = sum(1 for issue in issues if str(issue.get("level")).upper() == "ERROR")
    warnings = sum(
        1 for issue in issues if str(issue.get("level")).upper() == "WARNING"
    )
    summary = {
        "run_at": datetime.now(timezone.utc).isoformat(),
        "level": level.value,
        "errors": errors,
        "warnings": warnings,
        "frame_count": len(frames),
        "vision_model": settings.deepseek_model if frames else None,
        "issues": issues,
        "video_path": str(video),
    }

    async with task_session() as session:
        episode = await session.get(Episode, episode_id)
        node = await session.get(NodeRun, node_run_id)
        if episode is None or node is None:
            raise RuntimeError("episode/node disappeared during QC")

        await session.execute(delete(Review).where(Review.episode_id == episode_id))
        for issue in issues:
            issue_level = str(issue.get("level", "WARNING")).upper()
            review_level = (
                ReviewLevel.ERROR
                if issue_level == "ERROR"
                else ReviewLevel.WARNING
            )
            session.add(
                Review(
                    episode_id=episode_id,
                    check_item=str(issue.get("check_item", "qc")),
                    level=review_level,
                    detail={
                        "message": issue.get("message", ""),
                        "suggestion": (issue.get("detail") or {}).get(
                            "suggestion", ""
                        ),
                        **(issue.get("detail") or {}),
                    },
                    evidence_path=issue.get("evidence_path"),
                )
            )
        session.add(
            Review(
                episode_id=episode_id,
                check_item="qc.summary",
                level=level,
                detail={
                    "errors": errors,
                    "warnings": warnings,
                    "frame_count": len(frames),
                    "vision_model": settings.deepseek_model if frames else None,
                },
            )
        )

        episode.qc_meta = summary
        episode.current_node = None
        if errors:
            episode.health = "FAILED"
        elif warnings:
            episode.health = "WARNING"
        else:
            episode.health = "OK"

        node.status = NodeStatus.SUCCESS
        node.finished_at = datetime.now(timezone.utc)
        node.heartbeat_at = node.finished_at
        node.output_ref = f"qc:{level.value}:{errors}/{warnings}"
        node.error = None
        await session.commit()

    if not errors:
        async with task_session() as session:
            await transition_episode(session, episode_id, EpisodeStatus.READY)
            await session.commit()

    logger.info(
        "qc done episode=%s level=%s errors=%d warnings=%d frames=%d",
        episode_id,
        level.value,
        errors,
        warnings,
        len(frames),
    )


@celery_app.task(name="qc.episode", bind=True, max_retries=1)
def qc_episode_task(self, episode_id: str, node_run_id: str):
    try:
        run_async(_qc_episode(episode_id, node_run_id))
    except TaskCancelled:
        run_async(_mark_failed(episode_id, node_run_id, "cancelled"))
        raise
    except Exception as exc:
        logger.exception("QC failed episode=%s", episode_id)
        if self.request.retries < self.max_retries:
            raise self.retry(exc=exc, countdown=10)
        run_async(_mark_failed(episode_id, node_run_id, str(exc)))
        raise
    finally:
        release_memory()

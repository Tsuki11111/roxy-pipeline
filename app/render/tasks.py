from __future__ import annotations

import asyncio
import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path

from celery import chord
from celery.utils.log import get_task_logger

from app.core.config import get_settings
from app.models.core import Episode, EpisodeStatus, NodeRun, NodeStatus
from app.render.capture import render_shot
from app.render.encode import concat_and_mux, get_ffmpeg
from app.render.models import EpisodeSpec
from app.render.stage import build_stage_payload
from app.render.timeline import build_timeline
from app.storage.output import export_episode_video
from app.workflow.celery_app import celery_app
from app.workflow.cancel import TaskCancelled, ensure_not_cancelled
from app.workflow.db import run_async, task_session

logger = get_task_logger(__name__)


def shot_render_hash(spec: EpisodeSpec, item) -> str:
    raw = json.dumps(
        {
            "shot": item.shot.model_dump(),
            "width": spec.width,
            "height": spec.height,
            "fps": spec.fps,
            "background": spec.background,
            "floor": spec.floor,
            "watermark": spec.watermark,
            "renderer_version": get_settings().renderer_version,
        },
        ensure_ascii=False,
        sort_keys=True,
    )
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


async def _mark_running(episode_id: str, node_run_id: str) -> None:
    async with task_session() as session:
        await ensure_not_cancelled(session, episode_id)
        node = await session.get(NodeRun, node_run_id)
        if node is not None:
            now = datetime.now(timezone.utc)
            node.status = NodeStatus.RUNNING
            node.started_at = node.started_at or now
            node.heartbeat_at = now
            node.error = None
        episode = await session.get(Episode, episode_id)
        if episode is not None:
            episode.current_node = "render.episode"
            episode.health = "OK"
        await session.commit()


async def _mark_success(
    episode_id: str, node_run_id: str, output_path: str
) -> None:
    async with task_session() as session:
        node = await session.get(NodeRun, node_run_id)
        episode = await session.get(Episode, episode_id)
        exported = await asyncio.to_thread(
            export_episode_video,
            Path(output_path),
            episode_id,
            title=episode.title if episode is not None else "",
        )
        final_path = exported["path"]
        if node is not None:
            now = datetime.now(timezone.utc)
            node.status = NodeStatus.SUCCESS
            node.finished_at = now
            node.heartbeat_at = now
            node.output_ref = final_path
            node.error = None
        qc_enabled = get_settings().qc_auto_run
        if episode is not None:
            episode.status = (
                EpisodeStatus.QC if qc_enabled else EpisodeStatus.READY
            )
            episode.current_node = "qc.episode" if qc_enabled else None
            episode.output_path = final_path
            episode.output_meta = exported["meta"]
            episode.health = "OK"
        await session.commit()

        if qc_enabled and episode is not None:
            try:
                from app.qc.service import start_qc

                await start_qc(session, episode_id)
                await session.commit()
            except Exception:
                logger.exception("failed to queue QC for episode=%s", episode_id)
                episode = await session.get(Episode, episode_id)
                if episode is not None:
                    episode.health = "FAILED"
                    episode.current_node = None
                await session.commit()


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


def mark_running(episode_id: str, node_run_id: str) -> None:
    run_async(_mark_running(episode_id, node_run_id))


def _assert_not_cancelled(episode_id: str) -> None:
    async def check():
        async with task_session() as session:
            await ensure_not_cancelled(session, episode_id)

    run_async(check())


def mark_success(episode_id: str, node_run_id: str, output_path: str) -> None:
    run_async(_mark_success(episode_id, node_run_id, output_path))


def mark_failed(episode_id: str, node_run_id: str, error: str) -> None:
    run_async(_mark_failed(episode_id, node_run_id, error))


@celery_app.task(name="render.episode")
def render_episode_task(
    episode_id: str,
    node_run_id: str,
    spec: dict,
    audio_path: str | None = None,
):
    settings = get_settings()
    try:
        episode_spec = EpisodeSpec.model_validate(spec)
        timeline = build_timeline(episode_spec)
        build_stage_payload(episode_spec, timeline)
    except Exception as exc:
        mark_failed(episode_id, node_run_id, f"invalid render spec: {exc}")
        raise

    out_dir = Path(settings.render_dir).resolve() / episode_id
    out_dir.mkdir(parents=True, exist_ok=True)
    mark_running(episode_id, node_run_id)

    header = [
        render_shot_task.s(
            episode_id=episode_id,
            node_run_id=node_run_id,
            spec=spec,
            seq=item.shot.seq,
            out_dir=str(out_dir),
        )
        for item in timeline.shots
    ]
    body = render_concat_task.s(
        episode_id=episode_id,
        node_run_id=node_run_id,
        total_ms=timeline.total_ms,
        out_path=str(out_dir / "episode.mp4"),
        audio_path=audio_path,
    )
    chord(header)(body)
    logger.info(
        "queued render episode=%s shots=%d node_run=%s",
        episode_id,
        len(header),
        node_run_id,
    )
    return {"episode_id": episode_id, "shots": len(header)}


@celery_app.task(name="render.shot", bind=True, max_retries=2)
def render_shot_task(
    self,
    episode_id: str,
    node_run_id: str,
    spec: dict,
    seq: int,
    out_dir: str,
):
    try:
        _assert_not_cancelled(episode_id)
        episode_spec = EpisodeSpec.model_validate(spec)
        timeline = build_timeline(episode_spec)
        payload = build_stage_payload(episode_spec, timeline)
        item = timeline.shots[seq - 1]
        if item.shot.seq != seq:
            raise RuntimeError(f"shot seq mismatch: expected {seq}, got {item.shot.seq}")

        digest = shot_render_hash(episode_spec, item)
        shots_dir = Path(out_dir) / "shots"
        segment = shots_dir / f"shot_{seq:04d}.mp4"
        first_frame = Path(out_dir) / "frames" / f"shot_{seq:04d}_first.png"
        meta_path = shots_dir / f"shot_{seq:04d}.json"
        if segment.is_file() and meta_path.is_file():
            try:
                meta = json.loads(meta_path.read_text(encoding="utf-8"))
            except (OSError, json.JSONDecodeError):
                meta = {}
            if meta.get("hash") == digest:
                logger.info("reused shot episode=%s seq=%d", episode_id, seq)
                return {
                    "seq": seq,
                    "segment": str(segment),
                    "first_frame": str(first_frame) if first_frame.is_file() else "",
                    "frame_count": item.frame_count,
                    "cached": True,
                }

        segment, first_frame = render_shot(
            payload,
            item,
            Path(out_dir),
            get_ffmpeg(),
            episode_spec.width,
            episode_spec.height,
            episode_spec.fps,
        )
        shots_dir.mkdir(parents=True, exist_ok=True)
        meta_path.write_text(
            json.dumps(
                {
                    "hash": digest,
                    "segment": str(segment),
                    "first_frame": str(first_frame),
                    "frame_count": item.frame_count,
                    "rendered_at": datetime.now(timezone.utc).isoformat(),
                },
                ensure_ascii=False,
                indent=2,
            ),
            encoding="utf-8",
        )
        logger.info("rendered shot episode=%s seq=%d", episode_id, seq)
        return {
            "seq": seq,
            "segment": str(segment),
            "first_frame": str(first_frame),
            "frame_count": item.frame_count,
            "cached": False,
        }
    except TaskCancelled:
        mark_failed(episode_id, node_run_id, "cancelled")
        raise
    except Exception as exc:
        logger.exception("shot render failed episode=%s seq=%d", episode_id, seq)
        if self.request.retries < self.max_retries:
            raise self.retry(exc=exc, countdown=5 * (self.request.retries + 1))
        mark_failed(episode_id, node_run_id, f"shot {seq} failed: {exc}")
        raise


@celery_app.task(name="render.concat")
def render_concat_task(
    results,
    episode_id: str,
    node_run_id: str,
    total_ms: int,
    out_path: str,
    audio_path: str | None = None,
):
    try:
        _assert_not_cancelled(episode_id)
        shots = sorted(
            (result for result in results if result),
            key=lambda result: result["seq"],
        )
        if not shots:
            raise RuntimeError("no shot results to concatenate")
        segments = [Path(result["segment"]) for result in shots]
        concat_and_mux(
            get_ffmpeg(),
            segments,
            Path(out_path),
            total_ms,
            Path(audio_path) if audio_path else None,
        )
        mark_success(episode_id, node_run_id, out_path)
        logger.info(
            "concat done episode=%s shots=%d out=%s",
            episode_id,
            len(segments),
            out_path,
        )
        return {"output_path": out_path, "shots": len(segments)}
    except TaskCancelled:
        mark_failed(episode_id, node_run_id, "cancelled")
        raise
    except Exception as exc:
        logger.exception("concat failed episode=%s", episode_id)
        mark_failed(episode_id, node_run_id, f"concat failed: {exc}")
        raise

from __future__ import annotations

from contextlib import asynccontextmanager
from pathlib import Path

from sqlalchemy import select

from app.core.config import get_settings
from app.models.core import (
    Asset,
    AssetStatus,
    AssetType,
    Episode,
    EpisodeStatus,
    NodeRun,
    OutboxEvent,
    Review,
    ReviewLevel,
)
from app.qc.service import start_qc
from app.qc.tasks import _qc_episode
from app.render.models import EpisodeSpec
from app.workflow.outbox import queue_for


def make_spec() -> EpisodeSpec:
    return EpisodeSpec(
        title="QC 测试",
        section_labels=["问题"],
        background="character_packs/placeholder/background.png",
        floor="character_packs/placeholder/floor.png",
        shots=[
            {
                "shot_id": "s1",
                "seq": 1,
                "section": "问题",
                "narration": "这是一句用于质检测试的台词。",
                "duration_ms": 2000,
                "card": {"type": "pure_text", "style": "conclusion", "text": "测试"},
            }
        ],
    )


async def seed_qc_episode(session, episode_id: str, video: Path) -> None:
    video.write_bytes(b"fake video")
    episode = await session.get(Episode, episode_id)
    episode.status = EpisodeStatus.QC
    episode.output_path = str(video)
    episode.render_spec = make_spec().model_dump()
    episode.audio_meta = {
        "alignment_granularity": "char",
        "lines": [
            {
                "seq": 1,
                "script_line_id": "line-1",
                "text": "这是一句用于质检测试的台词。",
                "start_ms": 0,
                "end_ms": 2000,
                "chars": [],
            }
        ],
    }
    await session.commit()


async def test_qc_action_queues_agent_task(
    client, episode, session, tmp_path
):
    _, ep = episode
    await seed_qc_episode(session, ep["id"], tmp_path / "episode.mp4")

    response = await client.post(f"/api/v1/episodes/{ep['id']}/actions/qc")
    assert response.status_code == 202, response.text
    accepted = response.json()
    assert accepted["node_key"] == "qc.episode"

    event = await session.scalar(select(OutboxEvent))
    assert event is not None
    assert event.event_type == "qc.episode"
    assert queue_for("qc.episode") == "agent"

    report = await client.get(f"/api/v1/episodes/{ep['id']}/qc")
    assert report.status_code == 200
    assert report.json()["reviews"] == []


async def test_qc_task_writes_warnings_and_ready(
    episode, session, db, monkeypatch, tmp_path
):
    _, ep = episode
    _, session_factory = db
    await seed_qc_episode(session, ep["id"], tmp_path / "episode.mp4")

    @asynccontextmanager
    async def fake_task_session():
        async with session_factory() as db_session:
            yield db_session

    monkeypatch.setattr("app.qc.tasks.task_session", fake_task_session)
    monkeypatch.setattr(
        "app.qc.tasks.run_rules",
        lambda *_args, **_kwargs: [
            {
                "check_item": "video.test",
                "level": "WARNING",
                "message": "测试警告",
                "detail": {"suggestion": "忽略"},
            }
        ],
    )
    monkeypatch.setattr("app.qc.tasks.extract_frames", lambda *_a, **_k: [])

    async with session_factory() as qc_session:
        _, node = await start_qc(qc_session, ep["id"])
        await qc_session.commit()
    await _qc_episode(ep["id"], node.id)

    async with session_factory() as check:
        episode_row = await check.get(Episode, ep["id"])
        assert episode_row.status == EpisodeStatus.READY
        assert episode_row.health == "WARNING"
        assert episode_row.qc_meta["warnings"] == 1
        reviews = list(
            await check.scalars(
                select(Review).where(Review.episode_id == ep["id"])
            )
        )
        assert len(reviews) == 2
        assert any(review.check_item == "qc.summary" for review in reviews)
        assert any(review.level == ReviewLevel.WARNING for review in reviews)


async def test_qc_task_errors_keep_qc_status(
    episode, session, db, monkeypatch, tmp_path
):
    _, ep = episode
    _, session_factory = db
    await seed_qc_episode(session, ep["id"], tmp_path / "episode.mp4")

    @asynccontextmanager
    async def fake_task_session():
        async with session_factory() as db_session:
            yield db_session

    monkeypatch.setattr("app.qc.tasks.task_session", fake_task_session)
    monkeypatch.setattr(
        "app.qc.tasks.run_rules",
        lambda *_args, **_kwargs: [
            {
                "check_item": "video.stream",
                "level": "ERROR",
                "message": "没有音轨",
                "detail": {},
            }
        ],
    )
    monkeypatch.setattr("app.qc.tasks.extract_frames", lambda *_a, **_k: [])

    async with session_factory() as qc_session:
        _, node = await start_qc(qc_session, ep["id"])
        await qc_session.commit()
    await _qc_episode(ep["id"], node.id)

    async with session_factory() as check:
        episode_row = await check.get(Episode, ep["id"])
        assert episode_row.status == EpisodeStatus.QC
        assert episode_row.health == "FAILED"
        assert episode_row.qc_meta["errors"] == 1
        summary = await check.scalar(
            select(Review).where(
                Review.episode_id == ep["id"],
                Review.check_item == "qc.summary",
            )
        )
        assert summary is not None
        assert summary.level == ReviewLevel.ERROR


async def test_asset_check_writes_meta(
    client, session, monkeypatch, tmp_path
):
    image = tmp_path / "asset.png"
    image.write_bytes(b"fake")
    asset = Asset(
        type=AssetType.CHARACTER,
        name="测试角色",
        reuse_key="test:character:qc",
        path=str(image),
        checksum="0" * 64,
        status=AssetStatus.CANDIDATE,
        tags=[],
        meta={},
    )
    session.add(asset)
    await session.commit()

    async def fake_check(path, llm, **kwargs):
        return {
            "pass": False,
            "issues": [
                {
                    "type": "crop",
                    "severity": "warning",
                    "detail": "角色脚部被裁切",
                    "suggestion": "重新构图",
                    "confidence": 0.9,
                }
            ],
        }

    monkeypatch.setattr(
        "app.api.routes.assets.check_image_asset", fake_check
    )
    response = await client.post(f"/api/v1/assets/{asset.id}/check")
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["passed"] is False
    assert body["meta"]["qc"]["issues"][0]["type"] == "crop"

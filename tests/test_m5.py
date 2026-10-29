from __future__ import annotations

import subprocess
from contextlib import asynccontextmanager
from datetime import datetime, timedelta, timezone
from pathlib import Path

from sqlalchemy import select

from app.core.config import get_settings
from app.publish.package import load_package
from app.render.encode import get_ffmpeg
from app.render.models import EpisodeSpec
from app.models.core import (
    Episode,
    EpisodeStatus,
    NodeRun,
    NodeStatus,
    OutboxEvent,
    ScriptLine,
    Shot,
)
from app.workflow.outbox import queue_for
from app.workflow.tasks import _reconcile_stale


async def seed_ready_episode(
    session, episode_id: str, tmp_path, monkeypatch
) -> list[ScriptLine]:
    reference = tmp_path / "reference.wav"
    reference.write_bytes(b"reference")
    monkeypatch.setattr(
        get_settings(), "tts_indextts_ref_audio", str(reference)
    )

    lines: list[ScriptLine] = []
    for index, text in enumerate(["第一句原台词", "第二句原台词"], start=1):
        line = ScriptLine(
            episode_id=episode_id,
            seq=index,
            speaker="narrator",
            section="问题" if index == 1 else "解决",
            text=text,
            char_count=len(text),
        )
        session.add(line)
        lines.append(line)
    await session.flush()
    for line in lines:
        session.add(
            Shot(
                episode_id=episode_id,
                script_line_id=line.id,
                seq=line.seq,
                duration_ms=2000,
                card_type="pure_text",
                card_payload={"style": "conclusion", "text": line.text},
                character_image=None,
                character_position="none",
                bg="paper",
                transition="cut",
                template_version="v1",
            )
        )
    episode = await session.get(Episode, episode_id)
    episode.status = EpisodeStatus.READY
    await session.commit()
    return lines


async def test_revise_line_restarts_voice(
    client, episode, session, tmp_path, monkeypatch
):
    _, ep = episode
    lines = await seed_ready_episode(session, ep["id"], tmp_path, monkeypatch)
    line = lines[0]

    response = await client.post(
        f"/api/v1/episodes/{ep['id']}/actions/revise-line",
        json={"line_id": line.id, "text": "第一句修改后的台词"},
    )
    assert response.status_code == 202, response.text
    body = response.json()
    assert body["line"]["text"] == "第一句修改后的台词"
    assert body["line"]["version"] == 2
    assert body["status"] == "VOICING"
    assert body["node_key"] == "voice.episode"

    event = await session.scalar(select(OutboxEvent))
    assert event is not None
    assert event.event_type == "voice.episode"
    assert queue_for("voice.episode") == "media"

    await session.refresh(line)
    assert line.text == "第一句修改后的台词"


async def test_revise_line_rejects_busy_episode(
    client, episode, session, tmp_path, monkeypatch
):
    _, ep = episode
    lines = await seed_ready_episode(session, ep["id"], tmp_path, monkeypatch)
    row = await session.get(Episode, ep["id"])
    row.status = EpisodeStatus.VOICING
    await session.commit()

    response = await client.post(
        f"/api/v1/episodes/{ep['id']}/actions/revise-line",
        json={"line_id": lines[0].id, "text": "修改"},
    )
    assert response.status_code == 409


async def test_resume_failed_voice(client, episode, session, tmp_path, monkeypatch):
    _, ep = episode
    await seed_ready_episode(session, ep["id"], tmp_path, monkeypatch)
    row = await session.get(Episode, ep["id"])
    row.status = EpisodeStatus.VOICING
    row.health = "FAILED"
    await session.commit()

    response = await client.post(f"/api/v1/episodes/{ep['id']}/actions/resume")
    assert response.status_code == 202, response.text
    body = response.json()
    assert body["node_key"] == "voice.episode"
    assert body["status"] == "VOICING"


async def test_reconciler_marks_stale_node_failed(
    episode, session, db, monkeypatch, tmp_path
):
    _, ep = episode
    await seed_ready_episode(session, ep["id"], tmp_path, monkeypatch)
    row = await session.get(Episode, ep["id"])
    row.status = EpisodeStatus.RENDERING
    row.current_node = "render.episode"
    node = NodeRun(
        episode_id=ep["id"],
        node_key="render.episode",
        status=NodeStatus.RUNNING,
        heartbeat_at=datetime.now(timezone.utc) - timedelta(hours=2),
    )
    session.add(node)
    await session.commit()

    _, session_factory = db

    @asynccontextmanager
    async def fake_task_session():
        async with session_factory() as db_session:
            yield db_session

    monkeypatch.setattr("app.workflow.tasks.task_session", fake_task_session)
    stale = await _reconcile_stale()
    assert stale == [node.id]

    async with session_factory() as check:
        node_row = await check.get(NodeRun, node.id)
        episode_row = await check.get(Episode, ep["id"])
        assert node_row.status == NodeStatus.FAILED
        assert "stale heartbeat" in (node_row.error or "")
        assert episode_row.health == "FAILED"


def _make_video(path: Path) -> None:
    result = subprocess.run(
        [
            get_ffmpeg(),
            "-y",
            "-loglevel",
            "error",
            "-f",
            "lavfi",
            "-i",
            "color=c=white:s=320x180:d=2",
            "-f",
            "lavfi",
            "-i",
            "sine=frequency=440:duration=2",
            "-c:v",
            "libx264",
            "-pix_fmt",
            "yuv420p",
            "-c:a",
            "aac",
            "-shortest",
            str(path),
        ],
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0, result.stderr


async def test_package_and_publish(
    client, episode, session, tmp_path, monkeypatch
):
    _, ep = episode
    await seed_ready_episode(session, ep["id"], tmp_path, monkeypatch)
    monkeypatch.setattr(
        get_settings(), "package_dir", str(tmp_path / "packages")
    )

    video = tmp_path / "episode.mp4"
    _make_video(video)
    spec = EpisodeSpec(
        title="M5 测试",
        section_labels=["问题", "解决"],
        background="character_packs/placeholder/background.png",
        floor="character_packs/placeholder/floor.png",
        shots=[
            {
                "shot_id": "s1",
                "seq": 1,
                "section": "问题",
                "narration": "发布包测试台词。",
                "duration_ms": 2000,
            }
        ],
    )
    row = await session.get(Episode, ep["id"])
    row.render_spec = spec.model_dump()
    row.output_path = str(video)
    await session.commit()

    response = await client.post(f"/api/v1/episodes/{ep['id']}/actions/package")
    assert response.status_code == 200, response.text
    body = response.json()
    assert Path(body["package_path"]).is_dir()
    assert {item["name"] for item in body["files"]} >= {
        "episode.mp4",
        "cover.jpg",
        "subtitles.srt",
        "script.txt",
        "metadata.json",
    }

    response = await client.post(f"/api/v1/episodes/{ep['id']}/actions/publish")
    assert response.status_code == 200, response.text
    assert response.json()["status"] == "PUBLISHED"
    assert load_package(ep["id"]) is not None

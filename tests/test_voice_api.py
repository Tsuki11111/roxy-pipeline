from __future__ import annotations

import wave
from contextlib import asynccontextmanager
from pathlib import Path

from sqlalchemy import select

from app.core.config import get_settings
from app.media.service import start_voice
from app.media.tasks import _voice_episode
from app.models.core import (
    Episode,
    EpisodeStatus,
    LineAudio,
    NodeRun,
    OutboxEvent,
    ScriptLine,
    Shot,
)
from app.providers.tts import TTSResult
from app.workflow.outbox import queue_for

LABELS = ["问题", "解决", "结尾"]


async def seed_voicing(session, episode_id: str) -> list[ScriptLine]:
    lines: list[ScriptLine] = []
    texts = ["第一句用于配音测试", "第二句用于配音测试"]
    for index, text in enumerate(texts, start=1):
        line = ScriptLine(
            episode_id=episode_id,
            seq=index,
            speaker="narrator",
            section=LABELS[index - 1],
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
                card_payload={
                    "style": "conclusion",
                    "text": line.text,
                    "motion": "idle_breathe",
                },
                character_image=None,
                character_position="none",
                bg="paper",
                transition="cut",
                template_version="v1",
            )
        )
    episode = await session.get(Episode, episode_id)
    episode.status = EpisodeStatus.VOICING
    await session.commit()
    return lines


def _use_test_reference(monkeypatch, tmp_path: Path) -> None:
    reference = tmp_path / "reference.wav"
    reference.write_bytes(b"reference")
    settings = get_settings()
    monkeypatch.setattr(settings, "tts_indextts_ref_audio", str(reference))


async def test_voice_action_queues_media_task(
    client, episode, session, monkeypatch, tmp_path
):
    _, ep = episode
    _use_test_reference(monkeypatch, tmp_path)
    await seed_voicing(session, ep["id"])

    response = await client.post(f"/api/v1/episodes/{ep['id']}/actions/voice")
    assert response.status_code == 202, response.text
    accepted = response.json()
    assert accepted["node_key"] == "voice.episode"
    assert accepted["status"] == "VOICING"

    event = await session.scalar(select(OutboxEvent))
    assert event is not None
    assert event.event_type == "voice.episode"
    assert queue_for("voice.episode") == "media"

    node = await session.get(NodeRun, accepted["operation_id"])
    assert node is not None
    assert node.status == "PENDING"

    response = await client.post(f"/api/v1/episodes/{ep['id']}/actions/voice")
    assert response.status_code == 409

    response = await client.get(f"/api/v1/episodes/{ep['id']}/audio")
    assert response.status_code == 200
    assert response.json()["lines"] == []


async def test_voice_action_requires_voicing(client, episode, monkeypatch, tmp_path):
    _, ep = episode
    _use_test_reference(monkeypatch, tmp_path)
    response = await client.post(f"/api/v1/episodes/{ep['id']}/actions/voice")
    assert response.status_code == 409


class FakeProvider:
    def synthesize(self, text, out_path, *, speed=1.0, emotion=None) -> TTSResult:
        out_path = Path(out_path)
        out_path.parent.mkdir(parents=True, exist_ok=True)
        frames = int(22050 * 0.8)
        with wave.open(str(out_path), "wb") as wav:
            wav.setnchannels(1)
            wav.setsampwidth(2)
            wav.setframerate(22050)
            wav.writeframes(b"\x00\x00" * frames)
        return TTSResult(
            audio_path=out_path, duration_ms=800, sample_rate=22050
        )


async def test_voice_episode_auto_queues_render(
    episode, session, db, monkeypatch, tmp_path
):
    _, ep = episode
    _, session_factory = db
    _use_test_reference(monkeypatch, tmp_path)
    settings = get_settings()
    monkeypatch.setattr(settings, "audio_root", str(tmp_path / "audio"))
    monkeypatch.setattr(settings, "voice_pause_ms", 100)
    monkeypatch.setattr(settings, "voice_auto_render", True)

    @asynccontextmanager
    async def fake_task_session():
        async with session_factory() as db_session:
            yield db_session

    monkeypatch.setattr("app.media.tasks.task_session", fake_task_session)
    monkeypatch.setattr(
        "app.media.tasks.build_tts_provider", lambda: FakeProvider()
    )

    await seed_voicing(session, ep["id"])
    _, node = await start_voice(session, ep["id"])
    await session.commit()

    await _voice_episode(ep["id"], node.id)

    async with session_factory() as check:
        episode_row = await check.get(Episode, ep["id"])
        assert episode_row.status == EpisodeStatus.RENDERING
        render_node = await check.scalar(
            select(NodeRun).where(NodeRun.node_key == "render.episode")
        )
        assert render_node is not None
        assert render_node.status == "PENDING"
        event = await check.scalar(
            select(OutboxEvent).where(OutboxEvent.event_type == "render.episode")
        )
        assert event is not None
        assert event.payload["audio_path"] == episode_row.audio_path


async def test_voice_episode_writes_audio_alignment_and_shots(
    episode, session, db, monkeypatch, tmp_path
):
    _, ep = episode
    _, session_factory = db
    _use_test_reference(monkeypatch, tmp_path)
    settings = get_settings()
    monkeypatch.setattr(settings, "audio_root", str(tmp_path / "audio"))
    monkeypatch.setattr(settings, "voice_pause_ms", 100)
    monkeypatch.setattr(settings, "voice_auto_render", False)

    @asynccontextmanager
    async def fake_task_session():
        async with session_factory() as db_session:
            yield db_session

    monkeypatch.setattr("app.media.tasks.task_session", fake_task_session)
    monkeypatch.setattr(
        "app.media.tasks.build_tts_provider", lambda: FakeProvider()
    )

    await seed_voicing(session, ep["id"])
    _, node = await start_voice(session, ep["id"])
    await session.commit()

    await _voice_episode(ep["id"], node.id)

    async with session_factory() as check:
        episode_row = await check.get(Episode, ep["id"])
        assert episode_row.status == EpisodeStatus.ALIGNING
        assert episode_row.audio_path is not None
        assert Path(episode_row.audio_path).is_file()
        assert episode_row.audio_meta["alignment_granularity"] == "sentence"
        assert len(episode_row.audio_meta["lines"]) == 2
        assert episode_row.render_spec is not None
        assert len(episode_row.render_spec["shots"]) == 2

        audios = list(await check.scalars(select(LineAudio)))
        assert len(audios) == 2
        assert all(Path(audio.path).is_file() for audio in audios)

        shots = list(
            await check.scalars(
                select(Shot).where(Shot.episode_id == ep["id"]).order_by(Shot.seq)
            )
        )
        # 800ms audio + 100ms pause, raised to the 1500ms shot floor.
        assert [shot.duration_ms for shot in shots] == [1500, 1500]

        with wave.open(episode_row.audio_path, "rb") as wav:
            duration_ms = round(wav.getnframes() * 1000 / wav.getframerate())
        assert duration_ms == 3000

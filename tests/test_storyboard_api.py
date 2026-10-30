from __future__ import annotations

from sqlalchemy import select

from app.core.config import get_settings
from app.models.core import (
    Episode,
    EpisodeStatus,
    NodeRun,
    OutboxEvent,
    ScriptLine,
    Shot,
)
from app.workflow.outbox import queue_for

LABELS = ["问题", "解决", "结尾"]
CARDS = ["chat_bubble", "terminal", "chat_bubble", "browser", "terminal", "chat_bubble", "icon", "pure_text"]
CHARACTER = "character_packs/placeholder/character.png"


async def seed_storyboard(session, episode_id: str):
    lines: list[ScriptLine] = []
    for label in LABELS:
        for _ in range(8):
            line = ScriptLine(
                episode_id=episode_id,
                seq=len(lines) + 1,
                speaker="narrator",
                section=label,
                text="这是一句用于测试脚本长度的台词",
                char_count=15,
            )
            session.add(line)
            lines.append(line)
    await session.flush()

    for index, line in enumerate(lines):
        card_type = CARDS[index % 8]
        session.add(
            Shot(
                episode_id=episode_id,
                script_line_id=line.id,
                seq=line.seq,
                duration_ms=2000,
                card_type=card_type,
                card_payload={
                    "style": "conclusion" if card_type == "pure_text" else "info",
                    "text": line.text,
                    "motion": "idle_breathe",
                },
                character_image=CHARACTER if line.seq % 3 != 0 else None,
                character_position="left" if line.seq % 3 != 0 else "none",
                bg="paper",
                transition="cut",
                template_version="v1",
            )
        )

    episode = await session.get(Episode, episode_id)
    episode.status = EpisodeStatus.STORYBOARDING
    await session.commit()
    return lines


async def test_generate_storyboard_queues_agent_task(client, episode, session):
    _, ep = episode
    lines = []
    for label in LABELS:
        for _ in range(2):
            lines.append((label, f"{label}测试"))
    for index, (label, text) in enumerate(lines, start=1):
        session.add(
            ScriptLine(
                episode_id=ep["id"],
                seq=index,
                speaker="narrator",
                section=label,
                text=text,
                char_count=len(text),
            )
        )
    episode_row = await session.get(Episode, ep["id"])
    episode_row.status = EpisodeStatus.STORYBOARDING
    await session.commit()

    response = await client.post(
        f"/api/v1/episodes/{ep['id']}/actions/generate-storyboard"
    )
    assert response.status_code == 202, response.text
    accepted = response.json()
    assert accepted["node_key"] == "storyboard.generate"
    assert accepted["status"] == "STORYBOARDING"

    event = await session.scalar(select(OutboxEvent))
    assert event is not None
    assert event.event_type == "storyboard.generate"
    assert queue_for("storyboard.generate") == "agent"

    node = await session.get(NodeRun, accepted["operation_id"])
    assert node is not None
    assert node.status == "PENDING"


async def test_get_validate_and_confirm_storyboard(client, episode, session):
    _, ep = episode
    await seed_storyboard(session, ep["id"])

    response = await client.get(f"/api/v1/episodes/{ep['id']}/storyboard")
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["rhythm"]["valid"] is True
    assert len(body["shots"]) == 24

    response = await client.post(f"/api/v1/episodes/{ep['id']}/storyboard/validate")
    assert response.status_code == 200
    assert response.json()["valid"] is True

    response = await client.post(
        f"/api/v1/episodes/{ep['id']}/actions/confirm-storyboard"
    )
    assert response.status_code == 200, response.text
    assert response.json()["status"] == "VOICING"


async def test_confirm_storyboard_blocks_invalid_rhythm(client, episode, session):
    _, ep = episode
    await seed_storyboard(session, ep["id"])
    shot = await session.scalar(select(Shot).where(Shot.episode_id == ep["id"], Shot.seq == 1))
    shot.card_type = "terminal"
    shot.seq = 1
    await session.commit()
    # Make the section-final shot a chat bubble.
    last = await session.scalar(
        select(Shot).where(Shot.episode_id == ep["id"], Shot.seq == 8)
    )
    last.card_type = "chat_bubble"
    await session.commit()

    response = await client.post(
        f"/api/v1/episodes/{ep['id']}/actions/confirm-storyboard"
    )
    assert response.status_code == 409
    assert response.json()["detail"]["message"] == "storyboard rhythm check failed"


async def test_patch_shot_and_build_render_spec(client, episode, session):
    _, ep = episode
    await seed_storyboard(session, ep["id"])
    shot = await session.scalar(select(Shot).where(Shot.episode_id == ep["id"], Shot.seq == 1))

    response = await client.patch(
        f"/api/v1/shots/{shot.id}",
        json={"duration_ms": 2500, "card_text": "编辑后的卡片文案"},
    )
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["shot"]["duration_ms"] == 2500
    assert body["shot"]["card_payload"]["text"] == "编辑后的卡片文案"
    assert body["rhythm"]["valid"] is True

    response = await client.patch(
        f"/api/v1/shots/{shot.id}",
        json={"duration_ms": 9000},
    )
    assert response.status_code == 422

    response = await client.patch(
        f"/api/v1/shots/{shot.id}",
        json={
            "overlay_image": "character_packs/placeholder/background.png",
            "overlay_position": "center",
            "overlay_width_px": 320,
            "overlay_bottom": 80,
            "overlay_opacity": 0.8,
            "overlay_blend": "multiply",
        },
    )
    assert response.status_code == 200, response.text
    overlay = response.json()["shot"]["card_payload"]["overlay"]
    assert overlay["image"] == "character_packs/placeholder/background.png"
    assert overlay["width_px"] == 320
    assert overlay["opacity"] == 0.8
    assert overlay["blend"] == "multiply"

    response = await client.post(
        f"/api/v1/episodes/{ep['id']}/actions/build-render-spec"
    )
    assert response.status_code == 200, response.text
    spec = response.json()["render_spec"]
    assert spec["title"] == "M1.2 测试期"
    assert len(spec["shots"]) == 24
    assert spec["shots"][0]["card"]["text"] == "编辑后的卡片文案"
    assert spec["shots"][0]["overlay"]["image"] == (
        "character_packs/placeholder/background.png"
    )

    response = await client.patch(
        f"/api/v1/shots/{shot.id}",
        json={"overlay_image": None},
    )
    assert response.status_code == 200
    assert "overlay" not in response.json()["shot"]["card_payload"]


async def test_rerender_ready_episode(client, episode, session):
    _, ep = episode
    await seed_storyboard(session, ep["id"])

    response = await client.post(
        f"/api/v1/episodes/{ep['id']}/actions/build-render-spec"
    )
    assert response.status_code == 200, response.text

    episode_row = await session.get(Episode, ep["id"])
    episode_row.status = EpisodeStatus.READY
    await session.commit()

    response = await client.post(f"/api/v1/episodes/{ep['id']}/actions/rerender")
    assert response.status_code == 202, response.text
    body = response.json()
    assert body["status"] == "RENDERING"
    assert body["node_key"] == "render.episode"

    await session.refresh(episode_row)
    assert episode_row.status == EpisodeStatus.RENDERING
    event = await session.scalar(
        select(OutboxEvent).where(OutboxEvent.event_type == "render.episode")
    )
    assert event is not None
    node = await session.get(NodeRun, body["operation_id"])
    assert node is not None
    assert node.status == "PENDING"


async def test_episode_video_route(client, episode, session, tmp_path, monkeypatch):
    _, ep = episode
    settings = get_settings()
    monkeypatch.setattr(settings, "output_root", str(tmp_path))
    video = tmp_path / "episode.mp4"
    video.write_bytes(b"fake-mp4")

    episode_row = await session.get(Episode, ep["id"])
    episode_row.output_path = str(video)
    await session.commit()

    response = await client.get(f"/api/v1/episodes/{ep['id']}/video")
    assert response.status_code == 200
    assert response.headers["content-type"].startswith("video/mp4")
    assert response.content == b"fake-mp4"

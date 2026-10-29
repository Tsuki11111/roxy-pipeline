from __future__ import annotations

from sqlalchemy import select

from app.models.core import Episode, EpisodeStatus, ScriptLine

LABELS = ["问题", "解决", "结尾"]


async def seed_lines(session, episode_id: str) -> list[ScriptLine]:
    lines: list[ScriptLine] = []
    for label in LABELS:
        for _ in range(7):
            text = "这是一句用于测试脚本长度的台词"
            lines.append(
                ScriptLine(
                    episode_id=episode_id,
                    seq=len(lines) + 1,
                    speaker="narrator",
                    section=label,
                    text=text,
                    char_count=len(text),
                )
            )
        lines.append(
            ScriptLine(
                episode_id=episode_id,
                seq=len(lines) + 1,
                speaker="roxy",
                section=label,
                text="原来如此",
                char_count=4,
            )
        )
    session.add_all(lines)
    await session.commit()
    return lines


async def test_get_script_and_confirm_script(client, episode, session):
    _, ep = episode
    await seed_lines(session, ep["id"])
    episode_row = await session.get(Episode, ep["id"])
    episode_row.status = EpisodeStatus.SCRIPT_REVIEW
    await session.commit()

    response = await client.get(f"/api/v1/episodes/{ep['id']}/script")
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["validation"]["valid"] is True
    assert len(body["lines"]) == 24

    response = await client.post(f"/api/v1/episodes/{ep['id']}/actions/confirm-script")
    assert response.status_code == 200, response.text
    assert response.json()["status"] == "STORYBOARDING"


async def test_confirm_script_blocks_invalid_script(client, episode, session):
    _, ep = episode
    for index, label in enumerate(LABELS, start=1):
        session.add(
            ScriptLine(
                episode_id=ep["id"],
                seq=index,
                speaker="narrator",
                section=label,
                text="太短",
                char_count=2,
            )
        )
    episode_row = await session.get(Episode, ep["id"])
    episode_row.status = EpisodeStatus.SCRIPT_REVIEW
    await session.commit()

    response = await client.post(f"/api/v1/episodes/{ep['id']}/actions/confirm-script")
    assert response.status_code == 409
    assert response.json()["detail"]["message"] == "script validation failed"


async def test_patch_line_recalculates_validation(client, episode, session):
    _, ep = episode
    lines = await seed_lines(session, ep["id"])
    line_id = lines[0].id
    long_text = "这是一句明显超过二十五个字的测试台词用来触发校验错误"

    response = await client.patch(
        f"/api/v1/script-lines/{line_id}",
        json={"text": long_text},
    )
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["line"]["char_count"] == len(long_text)
    assert body["validation"]["valid"] is False
    assert any("超过 25 字" in error for error in body["validation"]["errors"])

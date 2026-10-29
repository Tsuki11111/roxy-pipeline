from __future__ import annotations

from sqlalchemy import select

from app.agents.script.optimizer import optimize_script
from app.models.core import Episode, EpisodeStatus, ScriptLine, Series

LABELS = ["问题", "解决", "结尾"]


class FakeOptimizerLLM:
    async def chat_json(self, system, user, *, temperature=0.7, max_tokens=2000):
        return {
            "lines": [
                {"seq": 1, "speaker": "narrator", "text": "生活里的例子一讲就全都明白啦"},
            ]
        }


async def seed_script(session, episode_id: str) -> None:
    texts = ["这是用来测试润色流程的一句台词"] * 10
    sections = ["问题"] * 4 + ["解决"] * 3 + ["结尾"] * 3
    for index, (text, section) in enumerate(zip(texts, sections), start=1):
        session.add(
            ScriptLine(
                episode_id=episode_id,
                seq=index,
                speaker="narrator",
                section=section,
                text=text,
                char_count=len(text),
            )
        )
    episode = await session.get(Episode, episode_id)
    episode.status = EpisodeStatus.SCRIPT_REVIEW
    episode.target_duration_s = 30
    await session.commit()


async def test_optimize_script_applies_valid_rewrite(
    episode, session
):
    _, ep = episode
    await seed_script(session, ep["id"])

    result = await optimize_script(
        session, ep["id"], llm=FakeOptimizerLLM(), apply=True
    )
    assert result["applied"] is True
    assert result["changed_count"] == 1
    assert result["validation"]["valid"] is True

    line = await session.scalar(
        select(ScriptLine).where(
            ScriptLine.episode_id == ep["id"], ScriptLine.seq == 1
        )
    )
    assert line.text == "生活里的例子一讲就全都明白啦"
    episode_row = await session.get(Episode, ep["id"])
    assert episode_row.script_meta["optimization"]["changed_count"] == 1

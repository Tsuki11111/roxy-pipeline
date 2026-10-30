from __future__ import annotations

from app.agents.script.importer import import_article
from app.models.core import Episode, ScriptLine
from sqlalchemy import select


class FakeArticleLLM:
    async def chat_json(self, system, user, *, temperature=0.7, max_tokens=2000):
        text = "这是一句用于导入测试的口播台词"
        return {
            "summary": "测试文章摘要",
            "sections": [
                {
                    "label": "问题",
                    "question": "为什么会有这个问题？",
                    "goal": "提出生活问题",
                    "beats": ["现象", "疑问"],
                    "lines": [{"speaker": "narrator", "text": text}] * 4,
                },
                {
                    "label": "解决",
                    "question": "怎么解决？",
                    "goal": "解释原理",
                    "beats": ["原因", "方法"],
                    "lines": [{"speaker": "narrator", "text": text}] * 4,
                },
                {
                    "label": "结尾",
                    "question": "记住什么？",
                    "goal": "总结",
                    "beats": ["回顾"],
                    "lines": [{"speaker": "narrator", "text": text}] * 3,
                },
            ],
        }


async def test_import_article_builds_script(episode, session):
    _, ep = episode
    episode_row = await session.get(Episode, ep["id"])
    episode_row.target_duration_s = 30
    await session.commit()

    result = await import_article(
        session,
        ep["id"],
        "这是一篇用于测试的长文章，包含问题、解决和结尾三个部分。" * 5,
        llm=FakeArticleLLM(),
        optimize=False,
    )
    assert result["validation"]["valid"] is True
    assert result["status"].value == "SCRIPT_REVIEW"
    assert len(result["lines"]) == 11
    assert result["outline"][0]["question"] == "为什么会有这个问题？"

    rows = list(
        await session.scalars(
            select(ScriptLine).where(ScriptLine.episode_id == ep["id"])
        )
    )
    assert len(rows) == 11
    assert all(row.speaker == "roxy" for row in rows)
    assert rows[0].section == "问题"
    assert rows[-1].section == "结尾"

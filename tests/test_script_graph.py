from __future__ import annotations

from app.agents.script.graph import run_script_graph

LABELS = ["问题", "解决", "结尾"]


def valid_lines() -> list[dict]:
    lines: list[dict] = []
    for label in LABELS:
        for _ in range(7):
            text = "这是一句用于测试脚本长度的台词"
            lines.append({"speaker": "narrator", "section": label, "text": text})
        lines.append({"speaker": "roxy", "section": label, "text": "原来如此"})
    return lines


def section_lines() -> list[dict]:
    lines = [
        {"speaker": "narrator", "text": "这是一句用于测试脚本长度的台词"}
        for _ in range(7)
    ]
    lines.append({"speaker": "roxy", "text": "原来如此"})
    return lines


class FakeLLM:
    def __init__(self, *, repair: bool = False):
        self.repair = repair
        self.calls: list[str] = []

    async def chat_json(self, system, user, *, temperature=0.7, max_tokens=2000):
        if "请为每一章分配 target_chars" in user:
            self.calls.append("outline")
            return {
                "title_hook": "先说结论",
                "angle": "从一次翻车讲起",
                "sections": [
                    {"label": label, "goal": f"讲清楚{label}", "key_points": ["a"], "target_chars": 109}
                    for label in LABELS
                ],
            }
        if "请为每一章写 3–5 个叙事 beat" in user:
            self.calls.append("sections")
            return {
                "sections": [
                    {"label": label, "summary": f"{label}摘要", "beats": ["b1", "b2"]}
                    for label in LABELS
                ]
            }
        if "正在写章节" in user:
            self.calls.append("lines")
            if self.repair:
                return {"lines": [{"speaker": "narrator", "text": "太短"}]}
            return {"lines": section_lines()}
        if "确定性校验错误" in user:
            self.calls.append("repair")
            return {"lines": valid_lines()}
        raise AssertionError("unexpected prompt")


async def test_script_graph_valid_path():
    llm = FakeLLM()
    state = await run_script_graph(
        episode_id="ep-graph-valid",
        title="测试标题",
        topic="测试选题",
        target_duration_s=60,
        target_chars=327,
        section_labels=LABELS,
        thread_id="ep-graph-valid:script:run1",
        llm=llm,
    )
    assert state["validation"]["valid"] is True
    assert len(state["lines"]) == 24
    assert state["attempts"] == 0
    assert state["outline"]["sections"][0]["label"] == "问题"
    assert llm.calls.count("lines") == 3


async def test_script_graph_repairs_invalid_lines():
    llm = FakeLLM(repair=True)
    state = await run_script_graph(
        episode_id="ep-graph-repair",
        title="测试标题",
        topic="测试选题",
        target_duration_s=60,
        target_chars=327,
        section_labels=LABELS,
        thread_id="ep-graph-repair:script:run1",
        llm=llm,
    )
    assert state["attempts"] == 1
    assert state["validation"]["valid"] is True
    assert "repair" in llm.calls
    assert len(state["lines"]) == 24

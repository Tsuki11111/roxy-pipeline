from __future__ import annotations

from app.storyboard.graph import run_storyboard_graph

LABELS = ["问题", "解决", "结尾"]
CATALOG = [
    {
        "id": "placeholder_character",
        "path": "character_packs/placeholder/character.png",
        "expression": "neutral",
        "pose": "standing",
    }
]


class FakeLLM:
    async def chat_json(self, system, user, *, temperature=0.7, max_tokens=2000):
        if "请为每一句台词选择一个镜头" not in user:
            raise AssertionError("unexpected prompt")
        return {
            "shots": [
                {
                    "line_seq": seq,
                    "card_type": "chat_bubble",
                    "character_image": CATALOG[0]["path"],
                    "character_position": "left",
                    "bg": "paper",
                    "transition": "cut",
                    "motion": "idle_breathe",
                }
                for seq in range(1, 7)
            ]
        }


async def test_storyboard_graph_generates_one_shot_per_line():
    lines = []
    seq = 1
    for label in LABELS:
        for _ in range(2):
            lines.append(
                {
                    "seq": seq,
                    "section": label,
                    "speaker": "narrator",
                    "text": "这是一句测试台词",
                }
            )
            seq += 1

    state = await run_storyboard_graph(
        episode_id="ep-storyboard",
        section_labels=LABELS,
        lines=lines,
        thread_id="ep-storyboard:storyboard:run1",
        llm=FakeLLM(),
        catalog=CATALOG,
    )

    assert len(state["shots"]) == 6
    assert [shot["line_seq"] for shot in state["shots"]] == [1, 2, 3, 4, 5, 6]
    assert state["report"]["valid"] is True
    assert all(
        card in {"icon", "pure_text"}
        for card in state["report"]["section_last_cards"].values()
    )
    assert all(
        shot["duration_ms"] == 1500 for shot in state["shots"]
    )  # 8 chars / 5.5 ~= 1.45s, clamped to 1.5s

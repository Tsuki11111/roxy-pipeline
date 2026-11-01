from __future__ import annotations

from app.agents.storyboard.graph import run_storyboard_graph

LABELS = ["问题", "解决", "结尾"]
CATALOG = [
    {
        "id": "placeholder_character",
        "path": "character_packs/placeholder/character.png",
        "expression": "neutral",
        "pose": "standing",
    }
]

GROUPS = {
    "问题": [[1, 2]],
    "解决": [[3, 4]],
    "结尾": [[5, 6]],
}


class FakeLLM:
    async def chat_json(self, system, user, *, temperature=0.7, max_tokens=2000):
        if "请把这些台词编排成少量连贯的镜头" not in user:
            raise AssertionError("unexpected prompt")
        label = next(label for label in LABELS if f"章节：{label}" in user)
        return {
            "shots": [
                {
                    "line_seqs": group,
                    "card_type": "icon",
                    "character_image": CATALOG[0]["path"],
                    "character_position": "left",
                    "bg": "paper",
                    "transition": "cut",
                    "motion": "idle_breathe",
                    "continuity_group": f"{label}-1",
                    "scene": {
                        "setting": "暖纸舞台",
                        "entities": [
                            {"id": "demo", "name": "演示图", "appearance": "陶土色图形"}
                        ],
                    },
                }
                for group in GROUPS[label]
            ]
        }


async def test_storyboard_graph_groups_consecutive_lines():
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

    assert len(state["shots"]) == 3
    assert [shot["line_seqs"] for shot in state["shots"]] == [[1, 2], [3, 4], [5, 6]]
    assert state["report"]["valid"] is True
    assert all(
        card in {"icon", "pure_text"}
        for card in state["report"]["section_last_cards"].values()
    )
    assert all(3000 <= shot["duration_ms"] <= 4000 for shot in state["shots"])
    assert all(shot["continuity_group"] for shot in state["shots"])
    assert all(shot["scene"]["entities"] for shot in state["shots"])


async def test_storyboard_graph_falls_back_to_single_line_groups():
    class BadLLM(FakeLLM):
        async def chat_json(self, system, user, *, temperature=0.7, max_tokens=2000):
            return {
                "shots": [
                    {
                        "line_seqs": [1, 99],
                        "card_type": "chat_bubble",
                    }
                ]
            }

    lines = [
        {"seq": 1, "section": "问题", "speaker": "narrator", "text": "第一句"},
        {"seq": 2, "section": "问题", "speaker": "narrator", "text": "第二句"},
    ]
    state = await run_storyboard_graph(
        episode_id="ep-storyboard",
        section_labels=["问题"],
        lines=lines,
        thread_id="ep-storyboard:storyboard:run2",
        llm=BadLLM(),
        catalog=CATALOG,
    )
    assert [shot["line_seqs"] for shot in state["shots"]] == [[1], [2]]
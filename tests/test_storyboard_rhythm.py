from __future__ import annotations

from app.agents.storyboard.models import ShotDraft
from app.agents.storyboard.rhythm import apply_rhythm_fixes, validate_rhythm

LABELS = ["问题", "解决", "结尾"]
CARDS = ["chat_bubble", "terminal", "chat_bubble", "browser", "terminal", "chat_bubble", "pure_text"]
SCENE = {
    "setting": "暖纸舞台",
    "entities": [{"id": "demo", "name": "演示图", "appearance": "陶土色图形"}],
}


def make_shots() -> list[ShotDraft]:
    shots: list[ShotDraft] = []
    line_seq = 0
    for label in LABELS:
        for index in range(7):
            line_seq += 1
            if index == 0:
                line_seqs = [line_seq, line_seq + 1]
                line_seq += 1
            else:
                line_seqs = [line_seq]
            card_type = CARDS[index]
            shots.append(
                ShotDraft(
                    seq=len(shots) + 1,
                    line_seq=line_seqs[0],
                    line_seqs=line_seqs,
                    section=label,
                    speaker="narrator",
                    text="测试台词内容",
                    duration_ms=4000,
                    card_type=card_type,
                    character_image="character_packs/placeholder/character.png"
                    if len(shots) % 3 != 0
                    else None,
                    character_position="left" if len(shots) % 3 != 0 else "none",
                    continuity_group=f"{label}-1" if len(line_seqs) > 1 else "",
                    scene=SCENE if len(line_seqs) > 1 else {},
                )
            )
    return shots


def test_valid_storyboard_passes():
    report = validate_rhythm(make_shots(), LABELS)
    assert report.valid is True
    assert report.shot_count == 21
    assert report.section_last_cards == {label: "pure_text" for label in LABELS}


def test_three_same_cards_and_section_last_are_fixed():
    shots = make_shots()
    shots[1] = shots[1].model_copy(update={"card_type": "terminal"})
    shots[2] = shots[2].model_copy(update={"card_type": "terminal"})
    shots[3] = shots[3].model_copy(update={"card_type": "terminal"})
    shots[6] = shots[6].model_copy(update={"card_type": "chat_bubble"})

    report = validate_rhythm(shots, LABELS)
    assert any("连续 3 个" in error for error in report.errors)
    assert any("最后一个镜头" in error for error in report.errors)

    fixed = apply_rhythm_fixes(shots, LABELS)
    fixed_report = validate_rhythm(fixed, LABELS)
    assert fixed_report.valid is True
    assert fixed[6].card_type in {"icon", "pure_text"}


def test_character_run_and_duration_are_fixed():
    shots = make_shots()
    for index in range(5):
        shots[index] = shots[index].model_copy(
            update={
                "character_image": "character_packs/placeholder/character.png",
                "character_position": "left",
            }
        )
    shots[8] = shots[8].model_copy(update={"duration_ms": 25000})

    report = validate_rhythm(shots, LABELS)
    assert any("连续出现 5" in error for error in report.errors)
    assert any("超出 3–20 秒" in error for error in report.errors)

    fixed = apply_rhythm_fixes(shots, LABELS)
    fixed_report = validate_rhythm(fixed, LABELS)
    assert fixed_report.valid is True
    assert fixed[8].duration_ms == 20000


def test_grouped_shot_requires_scene_and_full_coverage():
    shots = make_shots()
    shots[0] = shots[0].model_copy(update={"scene": {}, "continuity_group": ""})
    shots[1] = shots[1].model_copy(update={"line_seqs": [1], "line_seq": 1})

    report = validate_rhythm(shots, LABELS)
    assert any("必须提供 scene" in error for error in report.errors)
    assert any("缺少 continuity_group" in error for error in report.errors)
    assert any("覆盖" in error or "对应了多个镜头" in error for error in report.errors)


def test_section_needs_grouped_shot():
    shots = make_shots()
    # Split the first grouped shot back into single-line shots.
    first = shots[0]
    shots[0] = first.model_copy(
        update={
            "line_seqs": [1],
            "line_seq": 1,
            "continuity_group": "",
            "scene": {},
        }
    )
    shots.insert(
        1,
        first.model_copy(
            update={
                "seq": 22,
                "line_seqs": [2],
                "line_seq": 2,
                "continuity_group": "",
                "scene": {},
            },
        ),
    )
    report = validate_rhythm(shots, LABELS)
    assert any("没有合并镜头" in error for error in report.errors)
from __future__ import annotations

from app.storyboard.models import ShotDraft
from app.storyboard.rhythm import apply_rhythm_fixes, validate_rhythm

LABELS = ["问题", "解决", "结尾"]
CARDS = ["chat_bubble", "terminal", "chat_bubble", "browser", "terminal", "chat_bubble", "icon", "pure_text"]


def make_shots() -> list[ShotDraft]:
    shots: list[ShotDraft] = []
    for label in LABELS:
        for index in range(8):
            seq = len(shots) + 1
            card_type = CARDS[index]
            if index == 7:
                card_type = "pure_text"
            shots.append(
                ShotDraft(
                    seq=seq,
                    line_seq=seq,
                    section=label,
                    speaker="narrator",
                    text="测试台词内容",
                    duration_ms=2000,
                    card_type=card_type,
                    character_image="character_packs/placeholder/character.png"
                    if seq % 3 != 0
                    else None,
                    character_position="left" if seq % 3 != 0 else "none",
                )
            )
    return shots


def test_valid_storyboard_passes():
    report = validate_rhythm(make_shots(), LABELS)
    assert report.valid is True
    assert report.shot_count == 24
    assert report.section_last_cards == {label: "pure_text" for label in LABELS}


def test_three_same_cards_and_section_last_are_fixed():
    shots = make_shots()
    shots[0] = shots[0].model_copy(update={"card_type": "terminal"})
    shots[1] = shots[1].model_copy(update={"card_type": "terminal"})
    shots[2] = shots[2].model_copy(update={"card_type": "terminal"})
    shots[7] = shots[7].model_copy(update={"card_type": "chat_bubble"})

    report = validate_rhythm(shots, LABELS)
    assert any("连续 3 个" in error for error in report.errors)
    assert any("最后一个镜头" in error for error in report.errors)

    fixed = apply_rhythm_fixes(shots, LABELS)
    fixed_report = validate_rhythm(fixed, LABELS)
    assert fixed_report.valid is True
    assert fixed[7].card_type in {"icon", "pure_text"}


def test_character_run_and_duration_are_fixed():
    shots = make_shots()
    for index in range(5):
        shots[index] = shots[index].model_copy(
            update={
                "character_image": "character_packs/placeholder/character.png",
                "character_position": "left",
            }
        )
    shots[8] = shots[8].model_copy(update={"duration_ms": 9000})

    report = validate_rhythm(shots, LABELS)
    assert any("连续出现 5" in error for error in report.errors)
    assert any("超出 1.5–6 秒" in error for error in report.errors)

    fixed = apply_rhythm_fixes(shots, LABELS)
    fixed_report = validate_rhythm(fixed, LABELS)
    assert fixed_report.valid is True
    assert fixed[8].duration_ms == 6000

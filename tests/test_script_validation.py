from __future__ import annotations

from app.agents.script.validation import (
    ScriptLineData,
    target_chars_for_duration,
    validate_script,
)

LABELS = ["问题", "解决", "结尾"]


def make_valid_lines() -> list[ScriptLineData]:
    lines: list[ScriptLineData] = []
    for label in LABELS:
        for _ in range(7):
            text = "这是一句用于测试脚本长度的台词"
            lines.append(
                ScriptLineData(
                    seq=len(lines) + 1,
                    section=label,
                    speaker="narrator",
                    text=text,
                    char_count=len(text),
                )
            )
        lines.append(
            ScriptLineData(
                seq=len(lines) + 1,
                section=label,
                speaker="roxy",
                text="原来如此",
                char_count=4,
            )
        )
    return lines


def test_target_chars():
    assert target_chars_for_duration(60) == 327
    assert target_chars_for_duration(600) == 3270


def test_valid_script_passes():
    result = validate_script(
        make_valid_lines(), target_duration_s=60, section_labels=LABELS
    )
    assert result.valid is True
    assert result.total_chars == 327
    assert result.target_chars == 327
    assert result.line_count == 24
    assert result.sections_present == LABELS


def test_long_line_and_missing_section():
    lines = make_valid_lines()
    lines[0] = lines[0].model_copy(
        update={"text": "这是一句明显超过二十五个字的测试台词用来触发校验错误", "char_count": 27}
    )
    lines = [line for line in lines if line.section != "结尾"]
    result = validate_script(lines, target_duration_s=60, section_labels=LABELS)
    assert result.valid is False
    assert any("超过 25 字" in error for error in result.errors)
    assert any("缺少章节：结尾" in error for error in result.errors)


def test_section_order_and_roxy_ratio():
    lines = make_valid_lines()
    lines[0] = lines[0].model_copy(update={"section": "结尾"})
    result = validate_script(lines, target_duration_s=60, section_labels=LABELS)
    assert any("章节顺序错误" in error for error in result.errors)

    roxy_lines = [
        ScriptLineData(
            seq=index + 1,
            section=LABELS[index % len(LABELS)],
            speaker="roxy",
            text="很短的话",
            char_count=4,
        )
        for index in range(24)
    ]
    roxy_result = validate_script(
        roxy_lines, target_duration_s=60, section_labels=LABELS
    )
    assert any("占比" in error for error in roxy_result.errors)


def test_forbidden_words():
    result = validate_script(
        make_valid_lines(),
        target_duration_s=60,
        section_labels=LABELS,
        forbidden_words=["测试脚本"],
    )
    assert any("禁止词" in error for error in result.errors)

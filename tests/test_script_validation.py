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
        update={
            "text": "这是一句明显超过五十个字的测试台词用来触发校验错误我们需要再补充一些内容让它足够长以确保超过限制并且继续增加文字",
            "char_count": 56,
        }
    )
    lines = [line for line in lines if line.section != "结尾"]
    result = validate_script(lines, target_duration_s=60, section_labels=LABELS)
    assert result.valid is False
    assert any("超过 50 字" in error for error in result.errors)
    assert any("缺少章节：结尾" in error for error in result.errors)


def test_section_order():
    lines = make_valid_lines()
    lines[0] = lines[0].model_copy(update={"section": "结尾"})
    result = validate_script(lines, target_duration_s=60, section_labels=LABELS)
    assert any("章节顺序错误" in error for error in result.errors)


def test_forbidden_words():
    result = validate_script(
        make_valid_lines(),
        target_duration_s=60,
        section_labels=LABELS,
        forbidden_words=["测试脚本"],
    )
    assert any("禁止词" in error for error in result.errors)

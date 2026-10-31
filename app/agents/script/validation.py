from __future__ import annotations

from collections.abc import Iterable, Sequence

from pydantic import BaseModel, Field

MAX_LINE_CHARS = 50
SPEAKERS = {"narrator", "roxy"}
DEFAULT_SECTION_LABELS = [
    "问题",
    "概念",
    "原理",
    "踩坑",
    "解决",
    "推广",
    "预告",
    "结尾",
]


class ScriptLineData(BaseModel):
    seq: int
    section: str
    speaker: str = "narrator"
    text: str
    char_count: int = 0


class ValidationResult(BaseModel):
    valid: bool
    errors: list[str] = Field(default_factory=list)
    total_chars: int
    target_chars: int
    line_count: int
    roxy_ratio: float
    sections_present: list[str] = Field(default_factory=list)


def target_chars_for_duration(
    target_duration_s: int, chars_per_minute: int = 327
) -> int:
    return max(1, round(target_duration_s / 60 * chars_per_minute))


def coerce_lines(rows: Iterable) -> list[ScriptLineData]:
    lines: list[ScriptLineData] = []
    for row in rows:
        if isinstance(row, ScriptLineData):
            lines.append(row)
        elif isinstance(row, dict):
            lines.append(ScriptLineData(**row))
        else:
            lines.append(
                ScriptLineData(
                    seq=row.seq,
                    section=row.section,
                    speaker=row.speaker,
                    text=row.text,
                    char_count=row.char_count,
                )
            )
    return lines


def normalize_lines(
    raw: Sequence[dict],
    section_labels: Sequence[str],
    *,
    default_section: str | None = None,
) -> list[ScriptLineData]:
    lines: list[ScriptLineData] = []
    for item in raw:
        text = str(item.get("text", "")).strip()
        if not text:
            continue
        section = str(item.get("section") or default_section or section_labels[0])
        speaker = str(item.get("speaker") or "narrator")
        lines.append(
            ScriptLineData(
                seq=len(lines) + 1,
                section=section,
                speaker=speaker,
                text=text,
                char_count=len(text),
            )
        )
    return lines


def validate_script(
    lines: Sequence[ScriptLineData],
    *,
    target_duration_s: int,
    section_labels: Sequence[str],
    target_chars_per_minute: int = 327,
    forbidden_words: Sequence[str] = (),
) -> ValidationResult:
    errors: list[str] = []
    target_chars = target_chars_for_duration(
        target_duration_s, target_chars_per_minute
    )
    total_chars = sum(len(line.text.strip()) for line in lines)
    roxy_count = sum(1 for line in lines if line.speaker == "roxy")
    roxy_ratio = roxy_count / len(lines) if lines else 0.0

    if not lines:
        errors.append("脚本为空")

    label_index = {label: index for index, label in enumerate(section_labels)}
    sections_present: list[str] = []
    highest_index = -1
    for line in lines:
        text = line.text.strip()
        if not text:
            errors.append(f"第 {line.seq} 句为空")
            continue
        if line.speaker not in SPEAKERS:
            errors.append(f"第 {line.seq} 句说话人非法：{line.speaker}")
        if len(text) > MAX_LINE_CHARS:
            errors.append(f"第 {line.seq} 句超过 50 字（{len(text)} 字）")
        if line.section not in label_index:
            errors.append(f"第 {line.seq} 句章节未知：{line.section}")
            continue
        index = label_index[line.section]
        if index < highest_index:
            errors.append(f"第 {line.seq} 句章节顺序错误：{line.section}")
        highest_index = max(highest_index, index)
        if line.section not in sections_present:
            sections_present.append(line.section)

    missing = [label for label in section_labels if label not in sections_present]
    if missing:
        errors.append("缺少章节：" + "、".join(missing))

    if total_chars:
        deviation = (total_chars - target_chars) / target_chars
        if abs(deviation) > 0.10:
            errors.append(
                f"全文字数 {total_chars}，目标 {target_chars}，偏差 {deviation:+.0%}"
            )

    for word in forbidden_words:
        if word and any(word in line.text for line in lines):
            errors.append(f"命中禁止词：{word}")

    return ValidationResult(
        valid=not errors,
        errors=errors,
        total_chars=total_chars,
        target_chars=target_chars,
        line_count=len(lines),
        roxy_ratio=round(roxy_ratio, 3),
        sections_present=sections_present,
    )

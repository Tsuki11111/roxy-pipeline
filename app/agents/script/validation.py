from __future__ import annotations

import re
from collections.abc import Iterable, Sequence

from pydantic import BaseModel, Field

MAX_LINE_CHARS = 50
SPEAKERS = {"narrator", "roxy"}
_NUMBER_TOKEN = re.compile(r"\d+(?:\.\d+)?%?")
_ENGLISH_TOKEN = re.compile(r"[A-Za-z][A-Za-z0-9+#.-]{1,}")
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
    target_chars: int | None = None
    estimated_duration_s: int | None = None
    line_count: int
    roxy_ratio: float
    sections_present: list[str] = Field(default_factory=list)


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
    section_labels: Sequence[str],
    estimated_duration_s: int | None = None,
    forbidden_words: Sequence[str] = (),
) -> ValidationResult:
    errors: list[str] = []
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

    for word in forbidden_words:
        if word and any(word in line.text for line in lines):
            errors.append(f"命中禁止词：{word}")

    return ValidationResult(
        valid=not errors,
        errors=errors,
        total_chars=total_chars,
        estimated_duration_s=estimated_duration_s,
        line_count=len(lines),
        roxy_ratio=round(roxy_ratio, 3),
        sections_present=sections_present,
    )


def _content_tokens(text: str) -> set[str]:
    return set(_NUMBER_TOKEN.findall(text)) | set(_ENGLISH_TOKEN.findall(text))


def validate_optimized_lines(
    original: Sequence[ScriptLineData],
    optimized: Sequence[ScriptLineData],
) -> list[str]:
    errors: list[str] = []
    if len(original) != len(optimized):
        errors.append(
            f"润色后句数 {len(optimized)} 与原文 {len(original)} 不一致"
        )
        return errors

    original_chars = sum(len(line.text.strip()) for line in original)
    optimized_chars = sum(len(line.text.strip()) for line in optimized)
    if original_chars and optimized_chars < original_chars * 0.90:
        errors.append(
            f"润色后总字数 {optimized_chars} 比原文 {original_chars} 少超过 10%，"
            "疑似省略内容"
        )
    if original_chars and optimized_chars > original_chars * 1.25:
        errors.append(
            f"润色后总字数 {optimized_chars} 比原文 {original_chars} 多超过 25%"
        )

    original_tokens: set[str] = set()
    for line in original:
        original_tokens |= _content_tokens(line.text)
    optimized_text = " ".join(line.text for line in optimized)
    missing = sorted(token for token in original_tokens if token not in optimized_text)
    if missing:
        errors.append("润色后丢失原文关键词/数字：" + "、".join(missing))

    for source, target in zip(original, optimized):
        source_chars = len(source.text.strip())
        target_chars = len(target.text.strip())
        if not target.text.strip():
            errors.append(f"第 {target.seq} 句润色后为空")
            continue
        if source.seq != target.seq:
            errors.append(
                f"润色后 seq 不连续：原文 {source.seq}，结果 {target.seq}"
            )
        if source_chars > 12 and target_chars < source_chars * 0.65:
            errors.append(
                f"第 {target.seq} 句从 {source_chars} 字缩到 {target_chars} 字，"
                "疑似省略内容"
            )

    return errors

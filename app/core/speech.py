"""中文口播时长估算。"""

from __future__ import annotations

from collections.abc import Iterable

CHARS_PER_SECOND = 5.2
MIN_LINE_MS = 1500


def estimate_text_ms(text: str) -> int:
    chars = len(" ".join(text.split()))
    return max(MIN_LINE_MS, round(chars / CHARS_PER_SECOND * 1000))


def estimate_lines_ms(texts: Iterable[str]) -> int:
    return sum(estimate_text_ms(text) for text in texts)


def estimate_duration_s(texts: Iterable[str]) -> int:
    return max(1, round(estimate_lines_ms(texts) / 1000))
from __future__ import annotations

from collections.abc import Sequence

from app.storyboard.grammar import (
    CARD_TYPES,
    DEFAULT_CARD_STYLES,
    MAX_DURATION_MS,
    MIN_DURATION_MS,
    POSITIONS,
)
from app.storyboard.models import RhythmReport, ShotDraft


def _section_last_indices(shots: Sequence[ShotDraft]) -> dict[str, int]:
    last: dict[str, int] = {}
    for index, shot in enumerate(shots):
        last[shot.section] = index
    return last


def validate_rhythm(
    shots: Sequence[ShotDraft], section_labels: Sequence[str]
) -> RhythmReport:
    errors: list[str] = []
    if not shots:
        errors.append("分镜为空")

    seqs = [shot.seq for shot in shots]
    if seqs != list(range(1, len(shots) + 1)):
        errors.append("shot.seq 必须从 1 连续递增")
    line_seqs = [shot.line_seq for shot in shots]
    if len(set(line_seqs)) != len(line_seqs):
        errors.append("同一句台词对应了多个镜头")

    for shot in shots:
        if shot.section not in section_labels:
            errors.append(f"镜头 {shot.seq} 章节未知：{shot.section}")
        if shot.card_type not in CARD_TYPES:
            errors.append(f"镜头 {shot.seq} 卡片类型非法：{shot.card_type}")
        if shot.character_position not in POSITIONS:
            errors.append(f"镜头 {shot.seq} 角色位置非法：{shot.character_position}")
        if not MIN_DURATION_MS <= shot.duration_ms <= MAX_DURATION_MS:
            errors.append(
                f"镜头 {shot.seq} 时长 {shot.duration_ms}ms 超出 1.5–6 秒"
            )

    for index in range(2, len(shots)):
        if (
            shots[index].card_type
            == shots[index - 1].card_type
            == shots[index - 2].card_type
        ):
            errors.append(
                f"镜头 {shots[index - 2].seq}–{shots[index].seq} "
                f"连续 3 个使用 {shots[index].card_type}"
            )

    run = 0
    for shot in shots:
        if shot.character_image:
            run += 1
            if run > 4:
                errors.append(f"镜头 {shot.seq} 前角色已连续出现 5 个镜头")
        else:
            run = 0

    last_indices = _section_last_indices(shots)
    section_last_cards: dict[str, str] = {}
    for label in section_labels:
        index = last_indices.get(label)
        if index is None:
            errors.append(f"缺少章节分镜：{label}")
            continue
        card_type = shots[index].card_type
        section_last_cards[label] = card_type
        if card_type not in {"icon", "pure_text"}:
            errors.append(
                f"章节「{label}」最后一个镜头必须是 icon/pure_text，当前为 {card_type}"
            )

    durations = [shot.duration_ms for shot in shots]
    character_count = sum(1 for shot in shots if shot.character_image)
    distribution: dict[str, int] = {}
    for shot in shots:
        distribution[shot.card_type] = distribution.get(shot.card_type, 0) + 1

    return RhythmReport(
        valid=not errors,
        errors=errors,
        shot_count=len(shots),
        avg_duration_ms=round(sum(durations) / len(durations), 1) if durations else 0,
        card_distribution=distribution,
        character_ratio=round(character_count / len(shots), 3) if shots else 0,
        section_last_cards=section_last_cards,
    )


def _different_card_type(used: set[str]) -> str:
    for card_type in CARD_TYPES:
        if card_type not in used:
            return card_type
    return "pure_text"


def apply_rhythm_fixes(
    shots: Sequence[ShotDraft], section_labels: Sequence[str]
) -> list[ShotDraft]:
    fixed = [shot.model_copy() for shot in shots]

    for shot in fixed:
        shot.duration_ms = max(
            MIN_DURATION_MS, min(MAX_DURATION_MS, shot.duration_ms)
        )

    for _ in range(4):
        last_indices = _section_last_indices(fixed)
        for label in section_labels:
            index = last_indices.get(label)
            if index is None:
                continue
            shot = fixed[index]
            if shot.card_type not in {"icon", "pure_text"}:
                used = {
                    fixed[i].card_type
                    for i in range(max(0, index - 2), index)
                }
                shot.card_type = "icon" if "icon" not in used else "pure_text"
                shot.card_style = DEFAULT_CARD_STYLES[shot.card_type]

        for index in range(2, len(fixed)):
            if (
                fixed[index].card_type
                == fixed[index - 1].card_type
                == fixed[index - 2].card_type
            ):
                used = {
                    fixed[index - 2].card_type,
                    fixed[index - 1].card_type,
                }
                fixed[index].card_type = _different_card_type(used)
                fixed[index].card_style = DEFAULT_CARD_STYLES[fixed[index].card_type]

        run = 0
        for shot in fixed:
            if shot.character_image:
                run += 1
                if run > 4:
                    shot.character_image = None
                    shot.character_position = "none"
                    run = 0
            else:
                run = 0

        if validate_rhythm(fixed, section_labels).valid:
            break

    return fixed

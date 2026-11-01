from __future__ import annotations

from collections.abc import Sequence

from app.agents.storyboard.grammar import (
    CARD_TYPES,
    DEFAULT_CARD_STYLES,
    MAX_GROUP_DURATION_MS,
    MAX_LINES_PER_SHOT,
    MIN_GROUP_DURATION_MS,
    POSITIONS,
)
from app.agents.storyboard.models import RhythmReport, ShotDraft


def _section_last_indices(shots: Sequence[ShotDraft]) -> dict[str, int]:
    last: dict[str, int] = {}
    for index, shot in enumerate(shots):
        last[shot.section] = index
    return last


def validate_rhythm(
    shots: Sequence[ShotDraft],
    section_labels: Sequence[str],
    *,
    legacy: bool = False,
) -> RhythmReport:
    errors: list[str] = []
    if not shots:
        errors.append("分镜为空")

    seqs = [shot.seq for shot in shots]
    if seqs != list(range(1, len(shots) + 1)):
        errors.append("shot.seq 必须从 1 连续递增")
    all_seqs: list[int] = []
    for shot in shots:
        seqs = list(shot.line_seqs) or [shot.line_seq]
        if not seqs:
            errors.append(f"镜头 {shot.seq} 没有台词")
            continue
        if sorted(seqs) != list(range(min(seqs), max(seqs) + 1)):
            errors.append(f"镜头 {shot.seq} 的台词不连续：{seqs}")
        if len(seqs) > MAX_LINES_PER_SHOT:
            errors.append(
                f"镜头 {shot.seq} 包含 {len(seqs)} 句，超过 {MAX_LINES_PER_SHOT} 句上限"
            )
        all_seqs.extend(seqs)
        if len(seqs) > 1:
            scene = shot.scene or {}
            entities = scene.get("entities") if isinstance(scene, dict) else None
            if not legacy and (not scene.get("setting") or not entities):
                errors.append(
                    f"镜头 {shot.seq} 是多句合并镜头，必须提供 scene.setting 和 entities"
                )
            if not legacy and not shot.continuity_group:
                errors.append(f"镜头 {shot.seq} 缺少 continuity_group")

    if len(set(all_seqs)) != len(all_seqs):
        errors.append("同一句台词对应了多个镜头")
    if all_seqs and sorted(all_seqs) != list(range(1, len(all_seqs) + 1)):
        errors.append("台词覆盖不完整：分镜必须覆盖每一句且顺序一致")

    group_bg: dict[str, str] = {}
    for shot in shots:
        if shot.continuity_group:
            previous = group_bg.get(shot.continuity_group)
            if previous is not None and previous != shot.bg:
                errors.append(
                    f"镜头 {shot.seq} 与同组镜头背景不一致：{shot.bg} != {previous}"
                )
            group_bg.setdefault(shot.continuity_group, shot.bg)

    section_line_counts: dict[str, int] = {}
    section_grouped: dict[str, bool] = {}
    for shot in shots:
        seqs = list(shot.line_seqs) or [shot.line_seq]
        section_line_counts[shot.section] = (
            section_line_counts.get(shot.section, 0) + len(seqs)
        )
        section_grouped[shot.section] = section_grouped.get(
            shot.section, False
        ) or len(seqs) > 1

    for shot in shots:
        if shot.section not in section_labels:
            errors.append(f"镜头 {shot.seq} 章节未知：{shot.section}")
        if shot.card_type not in CARD_TYPES:
            errors.append(f"镜头 {shot.seq} 卡片类型非法：{shot.card_type}")
        if shot.character_position not in POSITIONS:
            errors.append(f"镜头 {shot.seq} 角色位置非法：{shot.character_position}")
        min_duration = 1500 if legacy else MIN_GROUP_DURATION_MS
        if not min_duration <= shot.duration_ms <= MAX_GROUP_DURATION_MS:
            errors.append(
                f"镜头 {shot.seq} 时长 {shot.duration_ms}ms 超出 "
                f"{min_duration // 1000}–20 秒"
            )

    if not legacy:
        for label, count in section_line_counts.items():
            if count >= 4 and not section_grouped.get(label):
                errors.append(
                    f"章节「{label}」有 {count} 句台词，但没有合并镜头；"
                    "详细讲解应在一个动画内展开"
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
            MIN_GROUP_DURATION_MS,
            min(MAX_GROUP_DURATION_MS, shot.duration_ms),
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

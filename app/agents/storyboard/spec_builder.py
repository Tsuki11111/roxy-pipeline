from __future__ import annotations

import hashlib
import json

from app.core.speech import estimate_text_ms
from app.models.core import Episode, ScriptLine, Series, Shot, ShotLine
from app.render.models import (
    CardSpec,
    CharacterSpec,
    CharTiming,
    EpisodeSpec,
    OverlaySpec,
    RemotionRenderSpec,
    ShotLineSpec,
    ShotSpec,
)
from app.agents.storyboard.grammar import (
    BACKGROUNDS,
    CARD_TYPES,
    DEFAULT_CARD_STYLES,
    DEFAULT_FLOOR,
    MOTIONS,
    MOVES,
)

_CHARACTER_POSITIONS = {"left", "right", "center"}


def shot_cache_key(
    *,
    text: str,
    card_type: str,
    card_payload: dict,
    character_image: str | None,
    template_version: str,
) -> str:
    raw = json.dumps(
        {
            "text": text,
            "card_type": card_type,
            "card_payload": card_payload,
            "character_image": character_image,
            "template_version": template_version,
        },
        ensure_ascii=False,
        sort_keys=True,
    )
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


def build_episode_spec(
    episode: Episode,
    series: Series,
    lines: list[ScriptLine],
    shots: list[Shot],
    *,
    shot_lines_by_shot: dict[str, list[ShotLine]] | None = None,
    background: str | None = None,
    background_by_key: dict[str, str] | None = None,
    floor: str | None = None,
    char_timings_by_line: dict[str, list[dict]] | None = None,
    renderer: str = "remotion",
    remotion: RemotionRenderSpec | None = None,
) -> EpisodeSpec:
    background = background or BACKGROUNDS["paper"]
    floor = floor or DEFAULT_FLOOR
    if not series.section_labels:
        raise ValueError("series has no section labels")
    line_by_id = {line.id: line for line in lines}
    shot_lines_by_shot = shot_lines_by_shot or {}
    covered: list[str] = []
    spec_shots: list[ShotSpec] = []
    for shot in sorted(shots, key=lambda item: item.seq):
        group = shot_lines_by_shot.get(shot.id) or []
        if group:
            group = sorted(group, key=lambda row: row.seq)
            group_lines = [
                line_by_id[row.script_line_id]
                for row in group
                if row.script_line_id in line_by_id
            ]
        else:
            fallback = line_by_id.get(shot.script_line_id)
            group_lines = [fallback] if fallback is not None else []
        if not group_lines:
            raise ValueError(f"shot {shot.seq} references an unknown script line")
        covered.extend(line.id for line in group_lines)
        line = group_lines[0]

        payload = shot.card_payload or {}
        card_type = shot.card_type if shot.card_type in CARD_TYPES else "pure_text"
        style = str(payload.get("style") or DEFAULT_CARD_STYLES.get(card_type, ""))
        motion = payload.get("motion")
        if motion not in MOTIONS:
            motion = "idle_breathe"
        move = payload.get("move")
        if move not in MOVES:
            move = "none"

        character = None
        if shot.character_image:
            position = (
                shot.character_position
                if shot.character_position in _CHARACTER_POSITIONS
                else "left"
            )
            bust = "_bust_" in shot.character_image
            character = CharacterSpec(
                image=shot.character_image,
                position=position,
                height_px=1000,
                motion=motion,
                move=move,
                anchor_y=0 if bust else None,
            )

        overlay = None
        overlay_data = payload.get("overlay")
        if isinstance(overlay_data, dict) and overlay_data.get("image"):
            overlay_position = overlay_data.get("position")
            if overlay_position not in {"left", "center", "right"}:
                overlay_position = "center"
            try:
                overlay_width = int(overlay_data.get("width_px", 420))
            except (TypeError, ValueError):
                overlay_width = 420
            try:
                overlay_bottom = int(overlay_data.get("bottom", 120))
            except (TypeError, ValueError):
                overlay_bottom = 120
            try:
                overlay_opacity = float(overlay_data.get("opacity", 1.0))
            except (TypeError, ValueError):
                overlay_opacity = 1.0
            overlay_blend = overlay_data.get("blend")
            if overlay_blend not in {"normal", "multiply"}:
                overlay_blend = "normal"
            overlay = OverlaySpec(
                image=str(overlay_data["image"]),
                position=overlay_position,
                width_px=max(40, min(1900, overlay_width)),
                bottom=max(0, min(1080, overlay_bottom)),
                opacity=max(0.0, min(1.0, overlay_opacity)),
                blend=overlay_blend,
            )

        line_specs: list[ShotLineSpec] = []
        flat_timings: list[CharTiming] = []
        offset = 0
        for grouped in group_lines:
            timings = [
                CharTiming(
                    text=str(item["text"]),
                    start_ms=max(0, int(item["start_ms"])),
                    end_ms=max(0, int(item["end_ms"])),
                )
                for item in (char_timings_by_line or {}).get(grouped.id, [])
            ]
            duration = (
                max(timing.end_ms for timing in timings)
                if timings
                else estimate_text_ms(grouped.text)
            )
            line_specs.append(
                ShotLineSpec(
                    line_id=grouped.id,
                    seq=grouped.seq,
                    text=grouped.text,
                    duration_ms=duration,
                    char_timings=timings,
                )
            )
            flat_timings.extend(
                CharTiming(
                    text=timing.text,
                    start_ms=offset + timing.start_ms,
                    end_ms=offset + timing.end_ms,
                )
                for timing in timings
            )
            offset += duration

        narration = " ".join(item.text for item in group_lines)
        card_text = str(payload.get("text") or narration)
        spec_shots.append(
            ShotSpec(
                shot_id=shot.id,
                seq=shot.seq,
                section=line.section,
                narration=narration,
                duration_ms=shot.duration_ms,
                character=character,
                card=CardSpec(type=card_type, style=style, text=card_text),
                overlay=overlay,
                bg=(background_by_key or {}).get(shot.bg or "paper", background),
                floor=floor,
                template_version=shot.template_version,
                line_ids=[item.id for item in group_lines],
                lines=line_specs,
                continuity_group=shot.continuity_group,
                scene=shot.scene_meta,
                char_timings=flat_timings,
            )
        )

    if sorted(covered) != sorted(line_by_id):
        raise ValueError(
            "script lines are not covered exactly once by shots"
        )

    return EpisodeSpec(
        title=episode.title,
        fps=25,
        width=1920,
        height=1080,
        section_labels=list(series.section_labels),
        alignment_level="char" if char_timings_by_line else "sentence",
        renderer=renderer,
        remotion=remotion,
        background=background,
        floor=floor,
        watermark=series.watermark or "",
        shots=spec_shots,
    )

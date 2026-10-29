from __future__ import annotations

import hashlib
import json

from app.models.core import Episode, ScriptLine, Series, Shot
from app.render.models import (
    CardSpec,
    CharacterSpec,
    CharTiming,
    EpisodeSpec,
    ShotSpec,
)
from app.agents.storyboard.grammar import (
    BACKGROUNDS,
    CARD_TYPES,
    DEFAULT_CARD_STYLES,
    DEFAULT_FLOOR,
    MOTIONS,
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
    background: str | None = None,
    floor: str | None = None,
    char_timings_by_line: dict[str, list[dict]] | None = None,
) -> EpisodeSpec:
    background = background or BACKGROUNDS["paper"]
    floor = floor or DEFAULT_FLOOR
    if not series.section_labels:
        raise ValueError("series has no section labels")
    if len(shots) != len(lines):
        raise ValueError(
            f"shots ({len(shots)}) and script lines ({len(lines)}) do not match"
        )
    line_by_id = {line.id: line for line in lines}
    spec_shots: list[ShotSpec] = []
    for shot in sorted(shots, key=lambda item: item.seq):
        line = line_by_id.get(shot.script_line_id)
        if line is None:
            raise ValueError(f"shot {shot.seq} references an unknown script line")

        payload = shot.card_payload or {}
        card_type = shot.card_type if shot.card_type in CARD_TYPES else "pure_text"
        style = str(payload.get("style") or DEFAULT_CARD_STYLES.get(card_type, ""))
        motion = payload.get("motion")
        if motion not in MOTIONS:
            motion = "idle_breathe"

        character = None
        if shot.character_image:
            position = (
                shot.character_position
                if shot.character_position in _CHARACTER_POSITIONS
                else "left"
            )
            character = CharacterSpec(
                image=shot.character_image,
                position=position,
                height_px=1000,
                motion=motion,
            )

        spec_shots.append(
            ShotSpec(
                shot_id=shot.id,
                seq=shot.seq,
                section=line.section,
                narration=line.text,
                duration_ms=shot.duration_ms,
                character=character,
                card=CardSpec(type=card_type, style=style, text=line.text),
                bg=background,
                floor=floor,
                template_version=shot.template_version,
                char_timings=[
                    CharTiming(
                        text=str(item["text"]),
                        start_ms=max(0, int(item["start_ms"])),
                        end_ms=max(0, int(item["end_ms"])),
                    )
                    for item in (char_timings_by_line or {}).get(line.id, [])
                ],
            )
        )

    return EpisodeSpec(
        title=episode.title,
        fps=25,
        width=1920,
        height=1080,
        section_labels=list(series.section_labels),
        background=background,
        floor=floor,
        watermark=series.watermark or "",
        shots=spec_shots,
    )

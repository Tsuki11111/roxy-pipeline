from __future__ import annotations

from pathlib import Path
from urllib.parse import quote

from .cards import ROOT, render_card
from .models import EpisodeSpec
from .timeline import Timeline


def asset_url(path: str) -> str:
    candidate = (ROOT / path).resolve()
    if not candidate.is_relative_to(ROOT):
        raise ValueError(f"asset path escapes project root: {path}")
    if not candidate.is_file():
        raise FileNotFoundError(f"asset not found: {candidate}")
    relative = candidate.relative_to(ROOT).as_posix()
    return "/" + quote(relative, safe="/")


def build_stage_payload(spec: EpisodeSpec, timeline: Timeline) -> dict:
    shots: list[dict] = []
    for item in timeline.shots:
        shot = item.shot
        character = None
        if shot.character is not None:
            character = {
                "src": asset_url(shot.character.image),
                "position": shot.character.position,
                "height_px": shot.character.height_px,
                "motion": shot.character.motion,
            }
        shots.append(
            {
                "shot_id": shot.shot_id,
                "start_ms": item.start_ms,
                "end_ms": item.end_ms,
                "section_index": item.section_index,
                "character": character,
                "card_html": render_card(shot.card),
                "bg": asset_url(shot.bg) if shot.bg else None,
                "floor": asset_url(shot.floor) if shot.floor else None,
                "subtitle_chunks": [
                    {"text": chunk.text, "start_ms": chunk.start_ms, "end_ms": chunk.end_ms}
                    for chunk in item.chunks
                ],
            }
        )

    return {
        "title": spec.title,
        "width": spec.width,
        "height": spec.height,
        "fps": spec.fps,
        "background": asset_url(spec.background),
        "floor": asset_url(spec.floor),
        "watermark": spec.watermark,
        "section_labels": spec.section_labels,
        "shots": shots,
    }

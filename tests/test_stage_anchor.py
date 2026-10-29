from __future__ import annotations

import json
from pathlib import Path

import pytest
from pydantic import ValidationError

from app.render.models import CharacterSpec, EpisodeSpec
from app.render.stage import build_stage_payload
from app.render.timeline import build_timeline

SPEC_PATH = Path(__file__).resolve().parents[1] / "specs" / "demo_placeholder.json"


def test_stage_payload_carries_anchor():
    spec = EpisodeSpec.model_validate_json(SPEC_PATH.read_text(encoding="utf-8"))
    payload = build_stage_payload(spec, build_timeline(spec))
    character = payload["shots"][0]["character"]
    assert character["anchor_x"] == 0.33
    assert character["anchor_y"] == 52
    assert character["scale"] == 1.0


def test_stage_card_moves_opposite_character():
    raw = json.loads(SPEC_PATH.read_text(encoding="utf-8"))
    raw["shots"][0]["character"]["position"] = "right"
    spec = EpisodeSpec.model_validate(raw)
    payload = build_stage_payload(spec, build_timeline(spec))
    assert payload["shots"][0]["card_side"] == "left"


def test_character_anchor_validation():
    with pytest.raises(ValidationError):
        CharacterSpec(image="x.png", anchor_x=1.5)
    with pytest.raises(ValidationError):
        CharacterSpec(image="x.png", anchor_y=-1)
    with pytest.raises(ValidationError):
        CharacterSpec(image="x.png", scale=0)

from __future__ import annotations

from pathlib import Path

from PIL import Image, ImageChops

from app.render.capture import render_still
from app.render.models import EpisodeSpec
from app.render.stage import build_stage_payload
from app.render.timeline import build_timeline

ROOT = Path(__file__).resolve().parents[1]
SPEC_PATH = ROOT / "specs" / "demo_placeholder.json"
GOLDEN_PATH = Path(__file__).resolve().parent / "golden" / "placeholder_still.png"


def test_placeholder_frame_matches_golden(tmp_path):
    spec = EpisodeSpec.model_validate_json(SPEC_PATH.read_text(encoding="utf-8"))
    payload = build_stage_payload(spec, build_timeline(spec))
    out = tmp_path / "still.png"
    render_still(payload, out, 1000, spec.width, spec.height)

    assert GOLDEN_PATH.exists(), f"golden frame missing: {GOLDEN_PATH}"
    actual = Image.open(out).convert("RGB")
    golden = Image.open(GOLDEN_PATH).convert("RGB")
    assert actual.size == golden.size

    diff = ImageChops.difference(actual, golden).convert("L")
    histogram = diff.histogram()
    mean = sum(value * count for value, count in enumerate(histogram)) / (
        actual.width * actual.height
    )
    assert mean < 2.0, f"frame differs from golden: mean={mean:.3f}"

#!/usr/bin/env python3
"""Render the M1 demo episode: hand-written shots -> stage frames -> MP4."""

from __future__ import annotations

import argparse
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from app.render.capture import render_episode, render_still  # noqa: E402
from app.render.encode import concat_and_mux, get_ffmpeg  # noqa: E402
from app.render.models import EpisodeSpec  # noqa: E402
from app.render.stage import build_stage_payload  # noqa: E402
from app.render.timeline import build_timeline  # noqa: E402


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--spec", default="specs/demo_episode.json")
    parser.add_argument("--out", default="tmp/render_demo/demo_episode.mp4")
    parser.add_argument("--still-ms", type=int, default=2000)
    parser.add_argument("--still-out", default="tmp/render_demo/preview.png")
    parser.add_argument("--stills-only", action="store_true", help="render one PNG and exit")
    args = parser.parse_args()

    spec_path = (ROOT / args.spec).resolve()
    spec = EpisodeSpec.model_validate_json(spec_path.read_text(encoding="utf-8"))
    timeline = build_timeline(spec)
    payload = build_stage_payload(spec, timeline)

    out = (ROOT / args.out).resolve()
    out.parent.mkdir(parents=True, exist_ok=True)

    if args.stills_only:
        if args.still_ms < 0:
            raise SystemExit("--stills-only requires --still-ms >= 0")
        preview = (ROOT / args.still_out).resolve()
        render_still(payload, preview, args.still_ms, spec.width, spec.height)
        print(f"still: {preview}")
        return

    ffmpeg = get_ffmpeg()
    print(f"title: {spec.title}")
    print(f"shots: {len(spec.shots)}  duration: {timeline.total_ms / 1000:.1f}s  frames: {timeline.total_frames}")
    started = time.perf_counter()
    segments = render_episode(
        payload=payload,
        timeline=timeline,
        out_dir=out.parent,
        ffmpeg=ffmpeg,
        width=spec.width,
        height=spec.height,
        fps=spec.fps,
        still_ms=args.still_ms if args.still_ms >= 0 else None,
    )
    concat_and_mux(ffmpeg, segments, out, timeline.total_ms)
    elapsed = time.perf_counter() - started
    size_mb = out.stat().st_size / 1024 / 1024
    print(f"done: {out}  {size_mb:.2f} MB  {elapsed:.1f}s")


if __name__ == "__main__":
    main()

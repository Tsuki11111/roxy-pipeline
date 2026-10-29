from __future__ import annotations

import subprocess
from pathlib import Path

from app.render.encode import get_ffmpeg
from app.render.models import EpisodeSpec


def _frame_times(spec: EpisodeSpec, per_shot: int) -> list[dict]:
    frames: list[dict] = []
    cursor = 0
    for shot in spec.shots:
        duration = shot.duration_ms
        if per_shot <= 1:
            fractions = [0.25]
        elif per_shot == 2:
            fractions = [0.12, 0.55]
        else:
            fractions = [0.12, 0.5, 0.82][:per_shot]
        for index, fraction in enumerate(fractions, start=1):
            frames.append(
                {
                    "seq": shot.seq,
                    "section": shot.section,
                    "narration": shot.narration,
                    "card_type": shot.card.type if shot.card else "",
                    "time_ms": cursor + round(duration * fraction),
                    "frame_index": index,
                }
            )
        cursor += duration
    return frames


def extract_frames(
    video: Path,
    spec: EpisodeSpec,
    out_dir: Path,
    *,
    per_shot: int = 2,
    max_frames: int = 60,
    scale: int = 1280,
) -> list[dict]:
    frames = _frame_times(spec, per_shot)
    if len(frames) > max_frames:
        step = len(frames) / max_frames
        frames = [frames[int(index * step)] for index in range(max_frames)]

    out_dir.mkdir(parents=True, exist_ok=True)
    ffmpeg = get_ffmpeg()
    results: list[dict] = []
    for frame in frames:
        path = out_dir / (
            f"shot_{frame['seq']:04d}_{frame['frame_index']}.jpg"
        )
        result = subprocess.run(
            [
                ffmpeg,
                "-y",
                "-loglevel",
                "error",
                "-ss",
                f"{frame['time_ms'] / 1000:.3f}",
                "-i",
                str(video),
                "-frames:v",
                "1",
                "-vf",
                f"scale='min({scale},iw)':-2",
                "-q:v",
                "2",
                str(path),
            ],
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
        )
        if result.returncode != 0 or not path.is_file():
            raise RuntimeError(
                f"frame extraction failed at seq {frame['seq']}: "
                f"{result.stderr[-1000:]}"
            )
        results.append({**frame, "path": str(path)})
    return results

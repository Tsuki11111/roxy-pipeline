from __future__ import annotations

import subprocess
from pathlib import Path

from app.agents.remotion import docker
from app.core.config import get_settings
from app.render.encode import get_ffmpeg
from app.render.models import EpisodeSpec

PROJECT_ROOT = Path(__file__).resolve().parents[2]


def _workdir(spec: EpisodeSpec) -> Path:
    if spec.remotion is None:
        raise RuntimeError("episode has no remotion metadata")
    path = Path(spec.remotion.work_dir)
    if not path.is_absolute():
        path = PROJECT_ROOT / path
    return path.resolve()


def _normalize(
    raw: Path,
    out: Path,
    *,
    width: int,
    height: int,
    fps: int,
    frame_count: int,
) -> None:
    out.parent.mkdir(parents=True, exist_ok=True)
    ffmpeg = get_ffmpeg()
    command = [
        ffmpeg,
        "-y",
        "-i",
        str(raw),
        "-an",
        "-vf",
        f"scale={width}:{height}:force_original_aspect_ratio=decrease,"
        f"pad={width}:{height}:(ow-iw)/2:(oh-ih)/2:color=black,fps={fps}",
        "-frames:v",
        str(max(1, frame_count)),
        "-c:v",
        "libx264",
        "-preset",
        "medium",
        "-crf",
        "18",
        "-pix_fmt",
        "yuv420p",
        "-movflags",
        "+faststart",
        str(out),
    ]
    result = subprocess.run(
        command, capture_output=True, text=True, encoding="utf-8", errors="replace"
    )
    if result.returncode != 0:
        raise RuntimeError(f"ffmpeg normalize failed: {result.stderr[-3000:]}")


def _first_frame(segment: Path, out: Path) -> Path:
    out.parent.mkdir(parents=True, exist_ok=True)
    result = subprocess.run(
        [get_ffmpeg(), "-y", "-i", str(segment), "-frames:v", "1", str(out)],
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
    )
    if result.returncode != 0:
        raise RuntimeError(f"first frame failed: {result.stderr[-2000:]}")
    return out


def render_shot_remotion(
    spec: EpisodeSpec,
    *,
    shot_id: str,
    segment: Path,
    first_frame: Path,
    frame_count: int,
) -> tuple[Path, Path]:
    if spec.remotion is None:
        raise RuntimeError("episode has no remotion metadata")
    entry = spec.remotion.shots.get(shot_id)
    if entry is None:
        raise RuntimeError(f"no remotion composition for shot {shot_id}")
    workdir = _workdir(spec)
    settings = get_settings()
    raw_name = f"{entry.composition_id}.mp4"
    raw = docker.render_shot(workdir, entry.composition_id, raw_name)
    try:
        _normalize(
            raw,
            segment,
            width=spec.width,
            height=spec.height,
            fps=spec.fps,
            frame_count=frame_count,
        )
        _first_frame(segment, first_frame)
    finally:
        raw.unlink(missing_ok=True)
    if not segment.is_file() or segment.stat().st_size == 0:
        raise RuntimeError(f"remotion segment missing: {segment}")
    return segment, first_frame

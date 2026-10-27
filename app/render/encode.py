from __future__ import annotations

import subprocess
from functools import lru_cache
from pathlib import Path

import imageio_ffmpeg


@lru_cache(maxsize=1)
def get_ffmpeg() -> str:
    ffmpeg = imageio_ffmpeg.get_ffmpeg_exe()
    result = subprocess.run(
        [ffmpeg, "-hide_banner", "-encoders"],
        capture_output=True,
        text=True,
        check=True,
    )
    if "libx264" not in result.stdout:
        raise RuntimeError(
            "ffmpeg has no libx264 encoder; install a full ffmpeg build "
            "(imageio-ffmpeg should provide one)"
        )
    return ffmpeg


def start_segment(ffmpeg: str, out: Path, fps: int) -> subprocess.Popen:
    out.parent.mkdir(parents=True, exist_ok=True)
    return subprocess.Popen(
        [
            ffmpeg,
            "-y",
            "-loglevel",
            "error",
            "-f",
            "image2pipe",
            "-framerate",
            str(fps),
            "-i",
            "-",
            "-c:v",
            "libx264",
            "-preset",
            "veryfast",
            "-crf",
            "18",
            "-pix_fmt",
            "yuv420p",
            "-r",
            str(fps),
            "-g",
            str(fps * 2),
            "-keyint_min",
            str(fps),
            "-sc_threshold",
            "0",
            "-an",
            str(out),
        ],
        stdin=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )


def finish_segment(proc: subprocess.Popen) -> None:
    assert proc.stdin is not None
    proc.stdin.close()
    stderr = proc.stderr.read().decode("utf-8", "replace") if proc.stderr else ""
    if proc.wait() != 0:
        raise RuntimeError(f"ffmpeg segment failed:\n{stderr}")


def concat_and_mux(ffmpeg: str, segments: list[Path], out: Path, duration_ms: int) -> None:
    if not segments:
        raise ValueError("no segments to concat")
    list_file = out.parent / "segments.txt"
    lines = []
    for segment in segments:
        path = segment.resolve().as_posix().replace("'", "'\\''")
        lines.append(f"file '{path}'")
    list_file.write_text("\n".join(lines) + "\n", encoding="utf-8")

    video_only = out.parent / "video_only.mp4"
    concat = subprocess.run(
        [
            ffmpeg,
            "-y",
            "-loglevel",
            "error",
            "-f",
            "concat",
            "-safe",
            "0",
            "-i",
            str(list_file),
            "-c",
            "copy",
            str(video_only),
        ],
        capture_output=True,
        text=True,
    )
    if concat.returncode != 0:
        raise RuntimeError(f"ffmpeg concat failed:\n{concat.stderr[-2000:]}")

    duration_s = duration_ms / 1000
    mux = subprocess.run(
        [
            ffmpeg,
            "-y",
            "-loglevel",
            "error",
            "-i",
            str(video_only),
            "-f",
            "lavfi",
            "-i",
            "anullsrc=channel_layout=stereo:sample_rate=48000",
            "-t",
            f"{duration_s:.3f}",
            "-c:v",
            "copy",
            "-c:a",
            "aac",
            "-b:a",
            "192k",
            "-movflags",
            "+faststart",
            str(out),
        ],
        capture_output=True,
        text=True,
    )
    if mux.returncode != 0:
        raise RuntimeError(f"ffmpeg mux failed:\n{mux.stderr[-2000:]}")

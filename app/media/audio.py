from __future__ import annotations

import hashlib
import subprocess
import wave
from pathlib import Path

from app.render.encode import get_ffmpeg


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def wav_duration_ms(path: Path) -> int:
    with wave.open(str(path), "rb") as wav:
        rate = wav.getframerate()
        if rate <= 0:
            raise ValueError(f"invalid sample rate in {path}")
        return round(wav.getnframes() * 1000 / rate)


def _run(ffmpeg: str, args: list[str], label: str) -> None:
    result = subprocess.run(
        [ffmpeg, "-y", "-loglevel", "error", *args],
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
    )
    if result.returncode != 0:
        raise RuntimeError(f"ffmpeg {label} failed:\n{result.stderr[-2000:]}")


def _silence(ffmpeg: str, duration_ms: int, out: Path) -> None:
    _run(
        ffmpeg,
        [
            "-f",
            "lavfi",
            "-i",
            "anullsrc=r=22050:cl=mono",
            "-t",
            f"{duration_ms / 1000:.3f}",
            "-c:a",
            "pcm_s16le",
            str(out),
        ],
        "silence",
    )


def assemble_audio(
    parts: list[tuple[Path, int]],
    out_path: Path,
) -> int:
    """Concat per-line WAVs with trailing gaps, then loudnorm to -14 LUFS.

    Each part is (line audio, gap-after-line in ms). The gap makes the final
    track length equal to the sum of shot durations.
    """
    if not parts:
        raise ValueError("no audio parts to assemble")
    for clip, _ in parts:
        if not clip.is_file():
            raise FileNotFoundError(f"line audio not found: {clip}")

    ffmpeg = get_ffmpeg()
    out_path.parent.mkdir(parents=True, exist_ok=True)
    work_dir = out_path.parent / "concat"
    work_dir.mkdir(parents=True, exist_ok=True)

    silence_cache: dict[int, Path] = {}
    entries: list[Path] = []
    for index, (clip, gap_ms) in enumerate(parts, start=1):
        entries.append(clip)
        if gap_ms > 0:
            silence = silence_cache.get(gap_ms)
            if silence is None:
                silence = work_dir / f"silence_{gap_ms:05d}.wav"
                _silence(ffmpeg, gap_ms, silence)
                silence_cache[gap_ms] = silence
            entries.append(silence)

    list_file = work_dir / "audio_parts.txt"
    lines = [
        "file '{}'".format(path.resolve().as_posix().replace("'", "'\\''"))
        for path in entries
    ]
    list_file.write_text("\n".join(lines) + "\n", encoding="utf-8")

    _run(
        ffmpeg,
        [
            "-f",
            "concat",
            "-safe",
            "0",
            "-i",
            str(list_file),
            "-af",
            "loudnorm=I=-14:TP=-1.0:LRA=11",
            "-ar",
            "48000",
            "-ac",
            "2",
            "-c:a",
            "pcm_s16le",
            str(out_path),
        ],
        "audio assembly",
    )
    return wav_duration_ms(out_path)

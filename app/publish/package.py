from __future__ import annotations

import json
import shutil
import subprocess
from datetime import datetime, timezone
from pathlib import Path

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.voice.audio import sha256_file
from app.models.core import Episode, ScriptLine, Series
from app.render.encode import get_ffmpeg
from app.render.models import EpisodeSpec
from app.render.timeline import build_timeline

PROJECT_ROOT = Path(__file__).resolve().parents[2]


def _resolve(value: str) -> Path:
    path = Path(value).expanduser()
    return path if path.is_absolute() else (PROJECT_ROOT / path).resolve()


def _srt_time(ms: int) -> str:
    ms = max(0, ms)
    hours, remainder = divmod(ms, 3600_000)
    minutes, remainder = divmod(remainder, 60_000)
    seconds, millis = divmod(remainder, 1000)
    return f"{hours:02d}:{minutes:02d}:{seconds:02d},{millis:03d}"


def build_srt(spec: EpisodeSpec) -> str:
    timeline = build_timeline(spec)
    lines: list[str] = []
    index = 1
    for item in timeline.shots:
        for chunk in item.chunks:
            if not chunk.text.strip():
                continue
            lines.append(str(index))
            lines.append(
                f"{_srt_time(chunk.start_ms)} --> {_srt_time(chunk.end_ms)}"
            )
            lines.append(chunk.text.strip())
            lines.append("")
            index += 1
    return "\n".join(lines)


def _extract_cover(video: Path, out: Path) -> None:
    ffmpeg = get_ffmpeg()
    result = subprocess.run(
        [
            ffmpeg,
            "-y",
            "-loglevel",
            "error",
            "-ss",
            "1.000",
            "-i",
            str(video),
            "-frames:v",
            "1",
            "-q:v",
            "2",
            str(out),
        ],
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
    )
    if result.returncode != 0 or not out.is_file():
        raise RuntimeError(f"cover extraction failed: {result.stderr[-1000:]}")


def load_package(episode_id: str) -> dict | None:
    manifest = _resolve(get_settings().package_dir) / episode_id / "package.json"
    if not manifest.is_file():
        return None
    return json.loads(manifest.read_text(encoding="utf-8"))


async def build_package(session: AsyncSession, episode: Episode) -> dict:
    if not episode.output_path or not Path(episode.output_path).is_file():
        raise ValueError("episode has no rendered video")
    if not episode.render_spec:
        raise ValueError("episode has no render spec")
    series = await session.get(Series, episode.series_id)
    if series is None:
        raise LookupError("series not found")

    spec = EpisodeSpec.model_validate(episode.render_spec)
    timeline = build_timeline(spec)
    out_dir = _resolve(get_settings().package_dir) / episode.id
    out_dir.mkdir(parents=True, exist_ok=True)

    video = Path(episode.output_path)
    video_out = out_dir / "episode.mp4"
    shutil.copy2(video, video_out)

    cover = out_dir / "cover.jpg"
    _extract_cover(video, cover)

    srt = out_dir / "subtitles.srt"
    srt.write_text(build_srt(spec), encoding="utf-8")

    script = out_dir / "script.txt"
    lines = list(
        await session.scalars(
            select(ScriptLine)
            .where(ScriptLine.episode_id == episode.id)
            .order_by(ScriptLine.seq)
        )
    )
    script.write_text(
        "\n".join(
            f"{line.seq:04d} [{line.speaker}] {line.section}：{line.text}"
            for line in lines
        )
        + "\n",
        encoding="utf-8",
    )

    audio = None
    if episode.audio_path and Path(episode.audio_path).is_file():
        audio = out_dir / "audio.wav"
        shutil.copy2(episode.audio_path, audio)

    metadata = {
        "episode_id": episode.id,
        "series_id": series.id,
        "series_name": series.name,
        "title": episode.title,
        "duration_ms": timeline.total_ms,
        "fps": spec.fps,
        "width": spec.width,
        "height": spec.height,
        "voice_provider": (episode.audio_meta or {}).get("provider"),
        "voice_model": (episode.audio_meta or {}).get("model"),
        "alignment_granularity": (episode.audio_meta or {}).get(
            "alignment_granularity"
        ),
        "non_commercial": True,
        "copyright_notice": (
            "非商业同人作品；洛琪希等角色版权归原作者及版权方所有。"
        ),
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "local_only": True,
    }
    metadata_path = out_dir / "metadata.json"
    metadata_path.write_text(
        json.dumps(metadata, ensure_ascii=False, indent=2), encoding="utf-8"
    )

    files = [video_out, cover, srt, script, metadata_path]
    if audio is not None:
        files.append(audio)
    manifest = {
        **metadata,
        "package_path": str(out_dir),
        "files": [
            {
                "name": path.name,
                "path": str(path),
                "size": path.stat().st_size,
                "checksum": sha256_file(path),
            }
            for path in files
        ],
    }
    manifest_path = out_dir / "package.json"
    manifest_path.write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    return manifest

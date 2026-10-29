from __future__ import annotations

import re
import subprocess
from pathlib import Path

from app.models.core import Episode
from app.render.encode import get_ffmpeg
from app.render.models import EpisodeSpec
from app.render.timeline import build_timeline

PROJECT_ROOT = Path(__file__).resolve().parents[2]

_DURATION_RE = re.compile(r"Duration:\s*(\d+):(\d+):(\d+\.?\d*)")
_VIDEO_RE = re.compile(r"Stream #\d+:\d+.*Video:")
_AUDIO_RE = re.compile(r"Stream #\d+:\d+.*Audio:")
_MEAN_RE = re.compile(r"mean_volume:\s*(-?\d+\.?\d*) dB")
_MAX_RE = re.compile(r"max_volume:\s*(-?\d+\.?\d*) dB")


def _issue(
    check_item: str,
    level: str,
    message: str,
    **detail,
) -> dict:
    return {
        "check_item": check_item,
        "level": level,
        "message": message,
        "detail": detail,
    }


def _probe(video: Path) -> dict:
    ffmpeg = get_ffmpeg()
    result = subprocess.run(
        [ffmpeg, "-hide_banner", "-i", str(video)],
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
    )
    text = result.stderr
    duration_ms = None
    match = _DURATION_RE.search(text)
    if match:
        hours, minutes, seconds = match.groups()
        duration_ms = round(
            (int(hours) * 3600 + int(minutes) * 60 + float(seconds)) * 1000
        )
    return {
        "duration_ms": duration_ms,
        "has_video": bool(_VIDEO_RE.search(text)),
        "has_audio": bool(_AUDIO_RE.search(text)),
        "raw": text[-4000:],
    }


def _loudness(audio: Path) -> dict:
    ffmpeg = get_ffmpeg()
    result = subprocess.run(
        [
            ffmpeg,
            "-hide_banner",
            "-i",
            str(audio),
            "-af",
            "volumedetect",
            "-f",
            "null",
            "-",
        ],
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
    )
    text = result.stderr
    mean = _MEAN_RE.search(text)
    peak = _MAX_RE.search(text)
    return {
        "mean_db": float(mean.group(1)) if mean else None,
        "max_db": float(peak.group(1)) if peak else None,
    }


def _check_alignment(episode: Episode, spec: EpisodeSpec) -> list[dict]:
    issues: list[dict] = []
    meta = episode.audio_meta or {}
    lines = meta.get("lines") or []
    if not lines:
        return [
            _issue("alignment.timeline", "ERROR", "缺少句级对齐数据")
        ]
    shots = {shot.seq: shot for shot in spec.shots}
    previous_end = -1
    for entry in lines:
        start = int(entry.get("start_ms", -1))
        end = int(entry.get("end_ms", -1))
        seq = int(entry.get("seq", 0))
        if start < previous_end:
            issues.append(
                _issue(
                    "alignment.timeline",
                    "ERROR",
                    f"第 {seq} 句起点早于上一句终点",
                    seq=seq,
                    start_ms=start,
                    previous_end_ms=previous_end,
                )
            )
        if end <= start:
            issues.append(
                _issue(
                    "alignment.timeline",
                    "ERROR",
                    f"第 {seq} 句时间区间无效",
                    seq=seq,
                    start_ms=start,
                    end_ms=end,
                )
            )
        previous_end = max(previous_end, end)

        shot = shots.get(seq)
        if shot is not None and end - start > shot.duration_ms + 500:
            issues.append(
                _issue(
                    "alignment.timeline",
                    "ERROR",
                    f"第 {seq} 句音频超出镜头时长",
                    seq=seq,
                    audio_ms=end - start,
                    shot_ms=shot.duration_ms,
                )
            )

        chars = entry.get("chars") or []
        if chars and len(chars) != len(entry.get("text", "")):
            issues.append(
                _issue(
                    "alignment.chars",
                    "WARNING",
                    f"第 {seq} 句字级时间数量与文本不一致",
                    seq=seq,
                    chars=len(chars),
                    text_len=len(entry.get("text", "")),
                )
            )
        last = -1
        for char in chars:
            char_start = int(char.get("start_ms", 0))
            if char_start < last - 20:
                issues.append(
                    _issue(
                        "alignment.chars",
                        "WARNING",
                        f"第 {seq} 句字级时间非单调",
                        seq=seq,
                        start_ms=char_start,
                    )
                )
                break
            last = max(last, char_start)
    return issues


def _check_subtitles(spec: EpisodeSpec) -> list[dict]:
    timeline = build_timeline(spec)
    issues: list[dict] = []
    for item in timeline.shots:
        for chunk in item.chunks:
            if len(chunk.text) > 20:
                issues.append(
                    _issue(
                        "subtitle.length",
                        "WARNING",
                        f"镜头 {item.shot.seq} 字幕块超过 20 字",
                        seq=item.shot.seq,
                        text=chunk.text,
                        length=len(chunk.text),
                    )
                )
            if chunk.start_ms < item.start_ms or chunk.end_ms > item.end_ms:
                issues.append(
                    _issue(
                        "subtitle.timing",
                        "ERROR",
                        f"镜头 {item.shot.seq} 字幕超出镜头区间",
                        seq=item.shot.seq,
                        start_ms=chunk.start_ms,
                        end_ms=chunk.end_ms,
                    )
                )
    return issues


def _check_assets(spec: EpisodeSpec) -> list[dict]:
    issues: list[dict] = []
    for shot in spec.shots:
        if shot.character is None:
            continue
        path = Path(shot.character.image)
        if not path.is_absolute():
            path = PROJECT_ROOT / path
        if not path.is_file():
            issues.append(
                _issue(
                    "asset.character",
                    "ERROR",
                    f"镜头 {shot.seq} 角色图不存在",
                    seq=shot.seq,
                    path=str(path),
                )
            )
    return issues


def run_rules(
    episode: Episode,
    spec: EpisodeSpec,
    episode_video: Path,
) -> list[dict]:
    issues: list[dict] = []
    if not episode_video.is_file():
        return [
            _issue(
                "video.file",
                "ERROR",
                "成片文件不存在",
                path=str(episode_video),
            )
        ]

    timeline = build_timeline(spec)
    probe = _probe(episode_video)
    if not probe["has_video"]:
        issues.append(_issue("video.stream", "ERROR", "成片没有视频流"))
    if not probe["has_audio"]:
        issues.append(_issue("video.stream", "ERROR", "成片没有音轨"))
    duration = probe["duration_ms"]
    if duration is None:
        issues.append(_issue("video.stream", "ERROR", "无法读取成片时长"))
    elif abs(duration - timeline.total_ms) > 500:
        issues.append(
            _issue(
                "video.duration",
                "ERROR",
                "成片时长与时间线不一致",
                video_ms=duration,
                timeline_ms=timeline.total_ms,
            )
        )

    if episode.audio_path and Path(episode.audio_path).is_file():
        loud = _loudness(Path(episode.audio_path))
        mean = loud["mean_db"]
        peak = loud["max_db"]
        if mean is None:
            issues.append(_issue("audio.loudness", "WARNING", "无法读取音量"))
        elif mean < -32:
            issues.append(
                _issue(
                    "audio.loudness",
                    "ERROR",
                    "整体音量过低",
                    mean_db=mean,
                )
            )
        elif mean < -24:
            issues.append(
                _issue(
                    "audio.loudness",
                    "WARNING",
                    "整体音量偏低",
                    mean_db=mean,
                )
            )
        if peak is not None and peak > -0.1:
            issues.append(
                _issue(
                    "audio.clipping",
                    "WARNING",
                    "峰值可能削波",
                    max_db=peak,
                )
            )
    else:
        issues.append(_issue("audio.file", "ERROR", "音轨文件不存在"))

    issues.extend(_check_alignment(episode, spec))
    issues.extend(_check_subtitles(spec))
    issues.extend(_check_assets(spec))
    return issues

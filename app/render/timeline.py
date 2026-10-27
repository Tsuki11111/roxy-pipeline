from __future__ import annotations

from dataclasses import dataclass

from .models import EpisodeSpec, ShotSpec

_SENTENCE_END = set("。！？!?；;")
_SOFT_BREAK = set("，,、：:")


def split_subtitle(text: str, max_chars: int = 16) -> list[str]:
    text = " ".join(text.split())
    if not text:
        return []
    chunks: list[str] = []
    buffer = ""
    for char in text:
        buffer += char
        if len(buffer) >= max_chars or (
            char in _SENTENCE_END and len(buffer) >= 2
        ) or (char in _SOFT_BREAK and len(buffer) >= 4):
            if buffer.strip():
                chunks.append(buffer.strip())
            buffer = ""
    if buffer.strip():
        chunks.append(buffer.strip())

    # Merge a tiny tail into the previous chunk instead of flashing one or two chars.
    if len(chunks) > 1 and len(chunks[-1]) < 4:
        merged = chunks[-2] + chunks[-1]
        if len(merged) <= max_chars:
            chunks[-2:] = [merged]
    return chunks


@dataclass(frozen=True)
class SubtitleChunk:
    text: str
    start_ms: int
    end_ms: int


@dataclass(frozen=True)
class ShotTimeline:
    shot: ShotSpec
    start_ms: int
    end_ms: int
    frame_start: int
    frame_end: int
    section_index: int
    chunks: list[SubtitleChunk]

    @property
    def frame_count(self) -> int:
        return self.frame_end - self.frame_start


@dataclass(frozen=True)
class Timeline:
    shots: list[ShotTimeline]
    total_ms: int
    total_frames: int
    fps: int


def build_timeline(spec: EpisodeSpec) -> Timeline:
    cursor_ms = 0
    shots: list[ShotTimeline] = []

    for shot in spec.shots:
        start_ms = cursor_ms
        end_ms = start_ms + shot.duration_ms
        frame_start = round(start_ms * spec.fps / 1000)
        frame_end = round(end_ms * spec.fps / 1000)
        if frame_end <= frame_start:
            frame_end = frame_start + 1

        labels = split_subtitle(shot.narration)
        total_chars = max(1, sum(len(chunk) for chunk in labels))
        chunk_cursor = float(start_ms)
        chunks: list[SubtitleChunk] = []
        for index, text in enumerate(labels):
            share = shot.duration_ms * len(text) / total_chars
            chunk_start = round(chunk_cursor)
            chunk_end = round(chunk_cursor + share)
            if index == len(labels) - 1:
                chunk_end = end_ms
            chunk_end = max(chunk_start + 1, chunk_end)
            chunks.append(SubtitleChunk(text=text, start_ms=chunk_start, end_ms=chunk_end))
            chunk_cursor += share

        shots.append(
            ShotTimeline(
                shot=shot,
                start_ms=start_ms,
                end_ms=end_ms,
                frame_start=frame_start,
                frame_end=frame_end,
                section_index=spec.section_labels.index(shot.section),
                chunks=chunks,
            )
        )
        cursor_ms = end_ms

    total_ms = cursor_ms
    total_frames = round(total_ms * spec.fps / 1000)
    return Timeline(shots=shots, total_ms=total_ms, total_frames=total_frames, fps=spec.fps)

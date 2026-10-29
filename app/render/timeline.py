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
        if len(merged) <= max_chars or all(
            char in _SENTENCE_END or char in _SOFT_BREAK for char in chunks[-1]
        ):
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


def _proportional_chunks(
    labels: list[str], start_ms: int, end_ms: int
) -> list[SubtitleChunk]:
    duration_ms = end_ms - start_ms
    total_chars = max(1, sum(len(chunk) for chunk in labels))
    cursor = float(start_ms)
    chunks: list[SubtitleChunk] = []
    for index, text in enumerate(labels):
        share = duration_ms * len(text) / total_chars
        chunk_start = round(cursor)
        chunk_end = round(cursor + share)
        if index == len(labels) - 1:
            chunk_end = end_ms
        chunk_end = max(chunk_start + 1, chunk_end)
        chunks.append(
            SubtitleChunk(text=text, start_ms=chunk_start, end_ms=chunk_end)
        )
        cursor += share
    return chunks


def _timed_chunks(
    shot: ShotSpec, labels: list[str], start_ms: int, end_ms: int
) -> list[SubtitleChunk] | None:
    if not shot.char_timings:
        return None
    text = shot.narration
    cursor = 0
    chunks: list[SubtitleChunk] = []
    for label in labels:
        index = text.find(label, cursor)
        if index < 0:
            return None
        cursor = index + len(label)
        timings = [
            timing
            for timing in shot.char_timings[index:cursor]
            if timing.end_ms > timing.start_ms
        ]
        if not timings:
            return None
        chunk_start = max(start_ms, min(start_ms + timing.start_ms for timing in timings))
        chunk_end = min(end_ms, max(start_ms + timing.end_ms for timing in timings))
        chunk_end = max(chunk_start + 1, chunk_end)
        chunks.append(
            SubtitleChunk(text=label, start_ms=chunk_start, end_ms=chunk_end)
        )
    return chunks


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
        chunks = _timed_chunks(shot, labels, start_ms, end_ms)
        if chunks is None:
            chunks = _proportional_chunks(labels, start_ms, end_ms)

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

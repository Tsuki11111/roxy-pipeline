from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.assets.registry import resolve_background, resolve_floor
from app.models.core import Episode, ScriptLine, Series, Shot
from app.render.models import EpisodeSpec
from app.render.stage import build_stage_payload
from app.render.timeline import build_timeline
from app.storyboard.models import RhythmReport, ShotDraft
from app.storyboard.rhythm import validate_rhythm
from app.storyboard.spec_builder import build_episode_spec


async def load_script_lines(
    session: AsyncSession, episode_id: str
) -> list[ScriptLine]:
    result = await session.scalars(
        select(ScriptLine)
        .where(ScriptLine.episode_id == episode_id)
        .order_by(ScriptLine.seq)
    )
    return list(result)


async def load_shots(session: AsyncSession, episode_id: str) -> list[Shot]:
    result = await session.scalars(
        select(Shot).where(Shot.episode_id == episode_id).order_by(Shot.seq)
    )
    return list(result)


def shots_to_drafts(
    lines: list[ScriptLine], shots: list[Shot]
) -> list[ShotDraft]:
    line_by_id = {line.id: line for line in lines}
    drafts: list[ShotDraft] = []
    for shot in shots:
        line = line_by_id.get(shot.script_line_id)
        if line is None:
            continue
        payload = shot.card_payload or {}
        drafts.append(
            ShotDraft(
                seq=shot.seq,
                line_seq=line.seq,
                line_id=line.id,
                section=line.section,
                speaker=line.speaker,
                text=line.text,
                duration_ms=shot.duration_ms,
                card_type=shot.card_type,
                card_style=str(payload.get("style", "")),
                character_image=shot.character_image,
                character_position=shot.character_position,
                bg=shot.bg,
                transition=shot.transition,
                motion=str(payload.get("motion", "idle_breathe")),
            )
        )
    return drafts


def validate_storyboard(
    series: Series, lines: list[ScriptLine], shots: list[Shot]
) -> RhythmReport:
    labels = list(series.section_labels or [])
    return validate_rhythm(shots_to_drafts(lines, shots), labels)


def store_rhythm(episode: Episode, report: RhythmReport) -> None:
    meta = dict(episode.storyboard_meta or {})
    meta["rhythm"] = report.model_dump()
    episode.storyboard_meta = meta
    episode.health = "OK" if report.valid else "WARNING"


async def build_render_spec(
    session: AsyncSession, episode: Episode
) -> EpisodeSpec:
    series = await session.get(Series, episode.series_id)
    if series is None:
        raise LookupError("series not found")
    lines = await load_script_lines(session, episode.id)
    shots = await load_shots(session, episode.id)
    if not shots:
        raise ValueError("episode has no shots")
    background = await resolve_background(session, "paper")
    floor = await resolve_floor(session)
    spec = build_episode_spec(
        episode,
        series,
        lines,
        shots,
        background=background,
        floor=floor,
    )
    build_stage_payload(spec, build_timeline(spec))
    return spec

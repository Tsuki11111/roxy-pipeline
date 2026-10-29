from __future__ import annotations

from sqlalchemy.ext.asyncio import AsyncSession

from app.assets.registry import resolve_background, resolve_floor
from app.models.core import Episode, Series
from app.render.models import EpisodeSpec
from app.render.stage import build_stage_payload
from app.render.timeline import build_timeline
from app.storyboard.loaders import load_script_lines, load_shots
from app.storyboard.spec_builder import build_episode_spec


async def build_episode_render_spec(
    session: AsyncSession,
    episode: Episode,
    *,
    char_timings_by_line: dict[str, list[dict]] | None = None,
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
        char_timings_by_line=char_timings_by_line,
    )
    build_stage_payload(spec, build_timeline(spec))
    return spec

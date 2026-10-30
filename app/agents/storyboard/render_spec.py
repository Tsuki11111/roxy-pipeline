from __future__ import annotations

from sqlalchemy.ext.asyncio import AsyncSession

from app.assets.registry import resolve_background, resolve_floor
from app.models.core import Episode, Series
from app.render.models import EpisodeSpec, RemotionRenderSpec, RemotionShotSpec
from app.render.stage import build_stage_payload
from app.render.timeline import build_timeline
from app.agents.storyboard.loaders import load_script_lines, load_shots
from app.agents.storyboard.spec_builder import build_episode_spec


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
    bg_keys = {str(shot.bg or "paper") for shot in shots}
    background_by_key = {
        key: await resolve_background(session, key) for key in bg_keys
    }
    background = background_by_key.get("paper") or await resolve_background(
        session, "paper"
    )
    floor = await resolve_floor(session)
    remotion = None
    renderer = "playwright"
    meta = episode.remotion_meta or {}
    if meta.get("enabled"):
        shot_meta = meta.get("shots") or {}
        mapped = {}
        for shot in shots:
            entry = shot_meta.get(shot.id) or {}
            if entry.get("status") != "READY" or not entry.get("composition_id"):
                break
            mapped[shot.id] = RemotionShotSpec(
                composition_id=str(entry["composition_id"]),
                code_hash=str(entry.get("code_hash") or ""),
            )
        else:
            if len(mapped) == len(shots) and meta.get("work_dir") and meta.get("version"):
                renderer = "remotion"
                remotion = RemotionRenderSpec(
                    work_dir=str(meta["work_dir"]),
                    version=str(meta["version"]),
                    image_digest=meta.get("image_digest"),
                    shots=mapped,
                )
    spec = build_episode_spec(
        episode,
        series,
        lines,
        shots,
        background=background,
        background_by_key=background_by_key,
        floor=floor,
        char_timings_by_line=char_timings_by_line,
        renderer=renderer,
        remotion=remotion,
    )
    build_stage_payload(spec, build_timeline(spec))
    return spec

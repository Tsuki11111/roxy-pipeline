from __future__ import annotations

from sqlalchemy.ext.asyncio import AsyncSession

from app.models.core import Episode, ScriptLine, Series, Shot
from app.render.models import EpisodeSpec
from app.agents.storyboard.loaders import load_script_lines, load_shots
from app.agents.storyboard.models import RhythmReport, ShotDraft
from app.agents.storyboard.rhythm import validate_rhythm
from app.agents.storyboard.render_spec import build_episode_render_spec


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
    return await build_episode_render_spec(session, episode)

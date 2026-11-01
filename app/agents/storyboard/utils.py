from __future__ import annotations

from sqlalchemy.ext.asyncio import AsyncSession

from app.models.core import Episode, ScriptLine, Series, Shot, ShotLine
from app.render.models import EpisodeSpec
from app.schemas.core import ShotRead
from app.agents.storyboard.models import RhythmReport, ShotDraft
from app.agents.storyboard.rhythm import validate_rhythm
from app.agents.storyboard.render_spec import build_episode_render_spec


def shots_to_drafts(
    lines: list[ScriptLine],
    shots: list[Shot],
    shot_lines: list[ShotLine] | None = None,
) -> list[ShotDraft]:
    line_by_id = {line.id: line for line in lines}
    lines_by_shot: dict[str, list[ScriptLine]] = {}
    for row in shot_lines or []:
        line = line_by_id.get(row.script_line_id)
        if line is not None:
            lines_by_shot.setdefault(row.shot_id, []).append(line)
    drafts: list[ShotDraft] = []
    for shot in shots:
        group = sorted(lines_by_shot.get(shot.id, []), key=lambda item: item.seq)
        if not group:
            fallback = line_by_id.get(shot.script_line_id)
            group = [fallback] if fallback is not None else []
        if not group:
            continue
        payload = shot.card_payload or {}
        drafts.append(
            ShotDraft(
                seq=shot.seq,
                line_seq=group[0].seq,
                line_seqs=[line.seq for line in group],
                line_id=group[0].id,
                section=group[0].section,
                speaker=group[0].speaker,
                text=" ".join(line.text for line in group),
                duration_ms=shot.duration_ms,
                card_type=shot.card_type,
                card_style=str(payload.get("style", "")),
                character_image=shot.character_image,
                character_position=shot.character_position,
                bg=shot.bg,
                transition=shot.transition,
                motion=str(payload.get("motion", "idle_breathe")),
                continuity_group=shot.continuity_group or "",
                scene=shot.scene_meta or {},
            )
        )
    return drafts


def validate_storyboard(
    series: Series,
    lines: list[ScriptLine],
    shots: list[Shot],
    shot_lines: list[ShotLine] | None = None,
    *,
    legacy: bool = False,
) -> RhythmReport:
    labels = list(series.section_labels or [])
    return validate_rhythm(
        shots_to_drafts(lines, shots, shot_lines), labels, legacy=legacy
    )


def is_current_storyboard(episode: Episode) -> bool:
    from app.agents.storyboard.prompts import STORYBOARD_GRAPH_VERSION

    meta = episode.storyboard_meta or {}
    return meta.get("graph_version") == STORYBOARD_GRAPH_VERSION


def store_rhythm(episode: Episode, report: RhythmReport) -> None:
    meta = dict(episode.storyboard_meta or {})
    meta["rhythm"] = report.model_dump()
    episode.storyboard_meta = meta
    episode.health = "OK" if report.valid else "WARNING"


def shot_read(
    shot: Shot,
    shot_lines: list[ShotLine],
    line_by_id: dict[str, ScriptLine],
) -> ShotRead:
    rows = sorted(
        (row for row in shot_lines if row.shot_id == shot.id),
        key=lambda row: row.seq,
    )
    line_ids = [row.script_line_id for row in rows]
    if not line_ids:
        line_ids = [shot.script_line_id]
    line_seqs = [
        line_by_id[line_id].seq
        for line_id in line_ids
        if line_id in line_by_id
    ]
    return ShotRead.model_validate(shot).model_copy(
        update={
            "line_ids": line_ids,
            "line_seqs": line_seqs,
            "line_count": len(line_ids),
        }
    )


async def build_render_spec(
    session: AsyncSession, episode: Episode
) -> EpisodeSpec:
    return await build_episode_render_spec(session, episode)

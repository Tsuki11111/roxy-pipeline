"""分镜生成、校验、确认与 render spec 接口。"""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status
from jinja2 import TemplateNotFound
from sqlalchemy.ext.asyncio import AsyncSession

from app.agents.script.utils import load_series
from app.agents.storyboard.models import RhythmReport
from app.agents.storyboard.service import (
    StoryboardConflict,
    StoryboardRequestError,
    start_storyboard,
)
from app.agents.storyboard.loaders import (
    load_script_lines,
    load_shot_lines,
    load_shots,
)
from app.agents.storyboard.utils import (
    build_render_spec,
    is_current_storyboard,
    shot_read,
    store_rhythm,
    validate_storyboard,
)
from app.db.session import get_session
from app.models.core import Episode, EpisodeStatus
from app.schemas.core import (
    EpisodeActionAccepted,
    EpisodeRead,
    StoryboardRead,
)
from app.workflow.state_machine import InvalidTransition, transition_episode

router = APIRouter(prefix="/api/v1/episodes", tags=["episodes"])

async def _storyboard_action(
    session: AsyncSession,
    episode_id: str,
    *,
    regenerate: bool = False,
    retry: bool = False,
) -> EpisodeActionAccepted:
    try:
        episode, node = await start_storyboard(
            session, episode_id, regenerate=regenerate, retry=retry
        )
    except LookupError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except StoryboardConflict as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    except StoryboardRequestError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    await session.commit()
    await session.refresh(episode)
    return EpisodeActionAccepted(
        episode_id=episode.id,
        status=episode.status,
        node_key=node.node_key,
        operation_id=node.id,
    )


@router.post(
    "/{episode_id}/actions/generate-storyboard",
    response_model=EpisodeActionAccepted,
    status_code=status.HTTP_202_ACCEPTED,
)
async def generate_storyboard(
    episode_id: str,
    session: AsyncSession = Depends(get_session),
) -> EpisodeActionAccepted:
    return await _storyboard_action(session, episode_id)


@router.post(
    "/{episode_id}/actions/retry-storyboard",
    response_model=EpisodeActionAccepted,
    status_code=status.HTTP_202_ACCEPTED,
)
async def retry_storyboard(
    episode_id: str,
    session: AsyncSession = Depends(get_session),
) -> EpisodeActionAccepted:
    return await _storyboard_action(session, episode_id, retry=True)


@router.post(
    "/{episode_id}/actions/regenerate-storyboard",
    response_model=EpisodeActionAccepted,
    status_code=status.HTTP_202_ACCEPTED,
)
async def regenerate_storyboard(
    episode_id: str,
    session: AsyncSession = Depends(get_session),
) -> EpisodeActionAccepted:
    return await _storyboard_action(session, episode_id, regenerate=True)


@router.get("/{episode_id}/storyboard", response_model=StoryboardRead)
async def get_storyboard(
    episode_id: str,
    session: AsyncSession = Depends(get_session),
) -> StoryboardRead:
    episode = await session.get(Episode, episode_id)
    if episode is None:
        raise HTTPException(status_code=404, detail="episode not found")
    series = await load_series(session, episode)
    if series is None:
        raise HTTPException(status_code=404, detail="series not found")
    lines = await load_script_lines(session, episode_id)
    shots = await load_shots(session, episode_id)
    shot_lines = await load_shot_lines(session, episode_id)
    report = validate_storyboard(
        series, lines, shots, shot_lines, legacy=not is_current_storyboard(episode)
    )
    line_by_id = {line.id: line for line in lines}
    return StoryboardRead(
        episode_id=episode.id,
        status=episode.status,
        meta=episode.storyboard_meta,
        shots=[shot_read(shot, shot_lines, line_by_id) for shot in shots],
        rhythm=report,
    )


@router.post("/{episode_id}/storyboard/validate", response_model=RhythmReport)
async def validate_storyboard_action(
    episode_id: str,
    session: AsyncSession = Depends(get_session),
) -> RhythmReport:
    episode = await session.get(Episode, episode_id)
    if episode is None:
        raise HTTPException(status_code=404, detail="episode not found")
    series = await load_series(session, episode)
    if series is None:
        raise HTTPException(status_code=404, detail="series not found")
    lines = await load_script_lines(session, episode_id)
    shots = await load_shots(session, episode_id)
    shot_lines = await load_shot_lines(session, episode_id)
    report = validate_storyboard(
        series, lines, shots, shot_lines, legacy=not is_current_storyboard(episode)
    )
    store_rhythm(episode, report)
    await session.commit()
    return report


@router.post("/{episode_id}/actions/confirm-storyboard", response_model=EpisodeRead)
async def confirm_storyboard(
    episode_id: str,
    session: AsyncSession = Depends(get_session),
) -> Episode:
    episode = await session.get(Episode, episode_id, with_for_update=True)
    if episode is None:
        raise HTTPException(status_code=404, detail="episode not found")
    if episode.status != EpisodeStatus.STORYBOARDING:
        raise HTTPException(
            status_code=409,
            detail=f"episode status {episode.status.value} is not STORYBOARDING",
        )
    series = await load_series(session, episode)
    if series is None:
        raise HTTPException(status_code=404, detail="series not found")
    lines = await load_script_lines(session, episode_id)
    shots = await load_shots(session, episode_id)
    shot_lines = await load_shot_lines(session, episode_id)
    report = validate_storyboard(
        series, lines, shots, shot_lines, legacy=not is_current_storyboard(episode)
    )
    if not report.valid:
        raise HTTPException(
            status_code=409,
            detail={"message": "storyboard rhythm check failed", "errors": report.errors},
        )
    try:
        episode = await transition_episode(
            session, episode_id, EpisodeStatus.VOICING
        )
    except InvalidTransition as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    store_rhythm(episode, report)
    await session.commit()
    await session.refresh(episode)
    return episode


@router.post("/{episode_id}/actions/build-render-spec", response_model=EpisodeRead)
async def build_render_spec_action(
    episode_id: str,
    session: AsyncSession = Depends(get_session),
) -> Episode:
    episode = await session.get(Episode, episode_id)
    if episode is None:
        raise HTTPException(status_code=404, detail="episode not found")
    if episode.status == EpisodeStatus.RENDERING:
        raise HTTPException(status_code=409, detail="episode is rendering")
    try:
        spec = await build_render_spec(session, episode)
    except (LookupError, ValueError, FileNotFoundError, TemplateNotFound) as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    episode.render_spec = spec.model_dump()
    await session.commit()
    await session.refresh(episode)
    return episode

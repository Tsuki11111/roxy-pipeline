from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query, status
from jinja2 import TemplateNotFound
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_session
from app.models.core import Episode, EpisodeStatus, Series
from app.render.models import EpisodeSpec
from app.render.stage import build_stage_payload
from app.render.timeline import build_timeline
from app.schemas.core import EpisodeActionAccepted, EpisodeCreate, EpisodeRead
from app.workflow.render_service import (
    RenderConflict,
    RenderRequestError,
    start_render,
)
from app.workflow.state_machine import InvalidTransition, transition_episode

router = APIRouter(prefix="/api/v1/episodes", tags=["episodes"])


@router.post("", response_model=EpisodeRead, status_code=status.HTTP_201_CREATED)
async def create_episode(
    payload: EpisodeCreate,
    session: AsyncSession = Depends(get_session),
) -> Episode:
    series = await session.get(Series, payload.series_id)
    if series is None:
        raise HTTPException(status_code=404, detail="series not found")
    episode = Episode(
        series_id=payload.series_id,
        title=payload.title,
        topic=payload.topic,
        target_duration_s=payload.target_duration_s,
        status=EpisodeStatus.DRAFT,
    )
    session.add(episode)
    await session.commit()
    await session.refresh(episode)
    return episode


@router.get("", response_model=list[EpisodeRead])
async def list_episodes(
    status_filter: EpisodeStatus | None = Query(default=None, alias="status"),
    session: AsyncSession = Depends(get_session),
) -> list[Episode]:
    stmt = select(Episode).order_by(Episode.created_at.desc())
    if status_filter is not None:
        stmt = stmt.where(Episode.status == status_filter)
    result = await session.scalars(stmt)
    return list(result)


@router.get("/{episode_id}", response_model=EpisodeRead)
async def get_episode(
    episode_id: str,
    session: AsyncSession = Depends(get_session),
) -> Episode:
    episode = await session.get(Episode, episode_id)
    if episode is None:
        raise HTTPException(status_code=404, detail="episode not found")
    return episode


@router.put("/{episode_id}/render-spec", response_model=EpisodeRead)
async def put_render_spec(
    episode_id: str,
    spec: EpisodeSpec,
    session: AsyncSession = Depends(get_session),
) -> Episode:
    episode = await session.get(Episode, episode_id)
    if episode is None:
        raise HTTPException(status_code=404, detail="episode not found")
    if episode.status == EpisodeStatus.RENDERING:
        raise HTTPException(status_code=409, detail="episode is rendering")
    try:
        build_stage_payload(spec, build_timeline(spec))
    except (FileNotFoundError, ValueError, TemplateNotFound) as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    episode.render_spec = spec.model_dump()
    await session.commit()
    await session.refresh(episode)
    return episode


@router.post(
    "/{episode_id}/actions/render",
    response_model=EpisodeActionAccepted,
    status_code=status.HTTP_202_ACCEPTED,
)
async def render_episode_action(
    episode_id: str,
    session: AsyncSession = Depends(get_session),
) -> EpisodeActionAccepted:
    try:
        episode, node = await start_render(session, episode_id)
    except LookupError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except RenderConflict as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    except RenderRequestError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except (FileNotFoundError, ValueError, TemplateNotFound) as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    await session.commit()
    await session.refresh(episode)
    return EpisodeActionAccepted(
        episode_id=episode.id,
        status=episode.status,
        node_key=node.node_key,
        operation_id=node.id,
    )


async def _transition(
    session: AsyncSession, episode_id: str, target: EpisodeStatus
) -> Episode:
    try:
        episode = await transition_episode(session, episode_id, target)
    except LookupError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except InvalidTransition as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    await session.commit()
    await session.refresh(episode)
    return episode


@router.post("/{episode_id}/actions/confirm-topic", response_model=EpisodeRead)
async def confirm_topic(
    episode_id: str,
    session: AsyncSession = Depends(get_session),
) -> Episode:
    return await _transition(session, episode_id, EpisodeStatus.TOPIC_CONFIRMED)


@router.post("/{episode_id}/actions/confirm-script", response_model=EpisodeRead)
async def confirm_script(
    episode_id: str,
    session: AsyncSession = Depends(get_session),
) -> Episode:
    return await _transition(session, episode_id, EpisodeStatus.STORYBOARDING)


@router.post("/{episode_id}/actions/cancel", response_model=EpisodeRead)
async def cancel_episode(
    episode_id: str,
    session: AsyncSession = Depends(get_session),
) -> Episode:
    return await _transition(session, episode_id, EpisodeStatus.CANCELLED)


@router.post("/{episode_id}/actions/publish", response_model=EpisodeRead)
async def publish_episode(
    episode_id: str,
    session: AsyncSession = Depends(get_session),
) -> Episode:
    return await _transition(session, episode_id, EpisodeStatus.PUBLISHED)

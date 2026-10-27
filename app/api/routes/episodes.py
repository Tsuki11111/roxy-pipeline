from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_session
from app.models.core import Episode, EpisodeStatus, Series
from app.schemas.core import EpisodeCreate, EpisodeRead

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

"""视频期 CRUD、视频文件与删除。"""

from __future__ import annotations

from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException, Query, Response, status
from fastapi.responses import FileResponse
from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.db.session import get_session
from app.models.core import (
    Episode,
    EpisodeStatus,
    LineAudio,
    NodeRun,
    OutboxEvent,
    RemotionShot,
    Review,
    ScriptLine,
    Series,
    Shot,
    ShotLine,
)
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


@router.delete("/{episode_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_episode(
    episode_id: str,
    session: AsyncSession = Depends(get_session),
) -> Response:
    episode = await session.get(Episode, episode_id)
    if episode is None:
        raise HTTPException(status_code=404, detail="episode not found")
    running = {
        EpisodeStatus.SCRIPTING,
        EpisodeStatus.STORYBOARDING,
        EpisodeStatus.VOICING,
        EpisodeStatus.ALIGNING,
        EpisodeStatus.RENDERING,
        EpisodeStatus.QC,
    }
    if episode.status in running:
        raise HTTPException(
            status_code=409, detail="episode is running; cancel it first"
        )

    for model in (
        Review,
        LineAudio,
        OutboxEvent,
        NodeRun,
        RemotionShot,
        ShotLine,
        Shot,
        ScriptLine,
    ):
        await session.execute(delete(model).where(model.episode_id == episode_id))
    await session.delete(episode)
    await session.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.get("/{episode_id}", response_model=EpisodeRead)
async def get_episode(
    episode_id: str,
    session: AsyncSession = Depends(get_session),
) -> Episode:
    episode = await session.get(Episode, episode_id)
    if episode is None:
        raise HTTPException(status_code=404, detail="episode not found")
    return episode


@router.get("/{episode_id}/video")
async def get_episode_video(
    episode_id: str,
    session: AsyncSession = Depends(get_session),
) -> FileResponse:
    episode = await session.get(Episode, episode_id)
    if episode is None or not episode.output_path:
        raise HTTPException(status_code=404, detail="video not found")
    path = Path(episode.output_path).expanduser()
    if not path.is_absolute():
        path = (Path.cwd() / path).resolve()
    if not path.is_file():
        raise HTTPException(status_code=404, detail="video not found")
    root = Path(get_settings().output_root).expanduser().resolve()
    if not path.resolve().is_relative_to(root):
        raise HTTPException(status_code=404, detail="video not found")
    return FileResponse(
        path,
        media_type="video/mp4",
        headers={"Cache-Control": "no-store"},
    )

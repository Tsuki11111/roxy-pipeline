from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.core import Episode, EpisodeStatus


class TaskCancelled(Exception):
    pass


async def ensure_not_cancelled(session: AsyncSession, episode_id: str) -> None:
    status = await session.scalar(
        select(Episode.status).where(Episode.id == episode_id)
    )
    if status == EpisodeStatus.CANCELLED:
        raise TaskCancelled("episode was cancelled")

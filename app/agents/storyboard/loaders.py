from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.core import ScriptLine, Shot


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

from __future__ import annotations

from sqlalchemy.ext.asyncio import AsyncSession

from app.assets.store import find_reusable
from app.storyboard.grammar import (
    BACKGROUNDS,
    DEFAULT_BACKGROUND_KEY,
    DEFAULT_FLOOR,
)

BACKGROUND_REUSE_KEYS = {
    "paper": "bg:paper:light",
    "paper_dark": "bg:paper:dark",
    "desk": "bg:wood:table",
}
FLOOR_REUSE_KEY = "bg:floor:wood"


async def resolve_background(
    session: AsyncSession, key: str
) -> str:
    reuse_key = BACKGROUND_REUSE_KEYS.get(key, BACKGROUND_REUSE_KEYS[DEFAULT_BACKGROUND_KEY])
    asset = await find_reusable(session, reuse_key)
    return asset.path if asset is not None else BACKGROUNDS[DEFAULT_BACKGROUND_KEY]


async def resolve_floor(session: AsyncSession) -> str:
    asset = await find_reusable(session, FLOOR_REUSE_KEY)
    return asset.path if asset is not None else DEFAULT_FLOOR

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.script_utils import (
    load_lines,
    load_series,
    store_validation,
    validate_episode,
)
from app.db.session import get_session
from app.models.core import Episode, ScriptLine
from app.schemas.core import (
    ScriptLineRead,
    ScriptLineUpdate,
    ScriptLineUpdateResult,
)

router = APIRouter(prefix="/api/v1/script-lines", tags=["script"])


@router.patch("/{line_id}", response_model=ScriptLineUpdateResult)
async def update_script_line(
    line_id: str,
    payload: ScriptLineUpdate,
    session: AsyncSession = Depends(get_session),
) -> ScriptLineUpdateResult:
    line = await session.get(ScriptLine, line_id)
    if line is None:
        raise HTTPException(status_code=404, detail="script line not found")
    episode = await session.get(Episode, line.episode_id)
    if episode is None:
        raise HTTPException(status_code=404, detail="episode not found")

    text = payload.text.strip()
    if not text:
        raise HTTPException(status_code=422, detail="text must not be blank")
    line.text = text
    line.char_count = len(text)
    line.version += 1
    await session.flush()

    series = await load_series(session, episode)
    lines = await load_lines(session, episode.id)
    validation = validate_episode(episode, series, lines)
    store_validation(episode, validation)
    await session.commit()
    await session.refresh(line)
    return ScriptLineUpdateResult(
        line=ScriptLineRead.model_validate(line),
        validation=validation,
    )

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from app.agents.storyboard.utils import (
    load_script_lines,
    load_shots,
    store_rhythm,
    validate_storyboard,
)
from app.db.session import get_session
from app.models.core import Episode, ScriptLine, Series, Shot
from app.schemas.core import ShotRead, ShotUpdate, ShotUpdateResult
from app.agents.storyboard.grammar import (
    BACKGROUNDS,
    CARD_TYPES,
    DEFAULT_CARD_STYLES,
    POSITIONS,
    TRANSITIONS,
    MOTIONS,
    MOVES,
    PROJECT_ROOT,
)
from app.agents.storyboard.spec_builder import shot_cache_key

router = APIRouter(prefix="/api/v1/shots", tags=["storyboard"])


@router.patch("/{shot_id}", response_model=ShotUpdateResult)
async def update_shot(
    shot_id: str,
    payload: ShotUpdate,
    session: AsyncSession = Depends(get_session),
) -> ShotUpdateResult:
    shot = await session.get(Shot, shot_id)
    if shot is None:
        raise HTTPException(status_code=404, detail="shot not found")
    episode = await session.get(Episode, shot.episode_id)
    if episode is None:
        raise HTTPException(status_code=404, detail="episode not found")
    series = await session.get(Series, episode.series_id)
    if series is None:
        raise HTTPException(status_code=404, detail="series not found")
    line = await session.get(ScriptLine, shot.script_line_id)
    if line is None:
        raise HTTPException(status_code=404, detail="script line not found")

    fields = payload.model_fields_set
    card_payload = dict(shot.card_payload or {})

    if "card_type" in fields and payload.card_type is not None:
        if payload.card_type not in CARD_TYPES:
            raise HTTPException(status_code=422, detail="invalid card_type")
        shot.card_type = payload.card_type
        if "card_style" not in fields:
            card_payload["style"] = DEFAULT_CARD_STYLES.get(shot.card_type, "")
    if "card_style" in fields and payload.card_style is not None:
        card_payload["style"] = payload.card_style
    if "motion" in fields and payload.motion is not None:
        if payload.motion not in MOTIONS:
            raise HTTPException(status_code=422, detail="invalid motion")
        card_payload["motion"] = payload.motion
    if "move" in fields and payload.move is not None:
        if payload.move not in MOVES:
            raise HTTPException(status_code=422, detail="invalid move")
        card_payload["move"] = payload.move
    if "character_image" in fields:
        if payload.character_image:
            candidate = (PROJECT_ROOT / payload.character_image).resolve()
            if not candidate.is_relative_to(PROJECT_ROOT) or not candidate.is_file():
                raise HTTPException(status_code=422, detail="character_image not found")
        shot.character_image = payload.character_image or None
    if "character_position" in fields and payload.character_position is not None:
        if payload.character_position not in POSITIONS:
            raise HTTPException(status_code=422, detail="invalid character_position")
        shot.character_position = payload.character_position
    if "duration_ms" in fields and payload.duration_ms is not None:
        if not 1500 <= payload.duration_ms <= 6000:
            raise HTTPException(status_code=422, detail="duration_ms must be 1500–6000")
        shot.duration_ms = payload.duration_ms
    if "bg" in fields and payload.bg is not None:
        if payload.bg not in BACKGROUNDS:
            raise HTTPException(status_code=422, detail="invalid bg")
        shot.bg = payload.bg
    if "transition" in fields and payload.transition is not None:
        if payload.transition not in TRANSITIONS:
            raise HTTPException(status_code=422, detail="invalid transition")
        shot.transition = payload.transition

    if not shot.character_image:
        shot.character_position = "none"
    elif shot.character_position == "none":
        shot.character_position = "left"

    card_payload["text"] = line.text
    shot.card_payload = card_payload
    shot.cache_key = shot_cache_key(
        text=line.text,
        card_type=shot.card_type,
        card_payload=card_payload,
        character_image=shot.character_image,
        template_version=shot.template_version,
    )

    lines = await load_script_lines(session, episode.id)
    shots = await load_shots(session, episode.id)
    report = validate_storyboard(series, lines, shots)
    store_rhythm(episode, report)
    await session.commit()
    await session.refresh(shot)
    return ShotUpdateResult(
        shot=ShotRead.model_validate(shot),
        rhythm=report,
    )

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.agents.script.importer import (
    ArticleImportConflict,
    ArticleImportError,
    import_article,
)
from app.agents.script.optimizer import (
    ScriptOptimizeConflict,
    ScriptOptimizeError,
    ScriptOptimizeInvalid,
    optimize_script,
)
from app.agents.script.utils import (
    load_lines,
    load_series,
    store_validation,
    validate_episode,
)
from app.agents.script.validation import ValidationResult
from app.db.session import get_session
from app.models.core import Episode, EpisodeStatus
from app.schemas.core import (
    ArticleImportRead,
    ArticleImportRequest,
    EpisodeRead,
    ScriptLineRead,
    ScriptOptimizeRead,
    ScriptOptimizeRequest,
    ScriptRead,
)
from app.workflow.state_machine import InvalidTransition, transition_episode

router = APIRouter(prefix="/api/v1/episodes", tags=["episodes"])

@router.post("/{episode_id}/actions/confirm-script", response_model=EpisodeRead)
async def confirm_script(
    episode_id: str,
    session: AsyncSession = Depends(get_session),
) -> Episode:
    episode = await session.get(Episode, episode_id, with_for_update=True)
    if episode is None:
        raise HTTPException(status_code=404, detail="episode not found")
    if episode.status != EpisodeStatus.SCRIPT_REVIEW:
        raise HTTPException(
            status_code=409,
            detail=f"episode status {episode.status.value} is not SCRIPT_REVIEW",
        )
    series = await load_series(session, episode)
    lines = await load_lines(session, episode_id)
    validation = validate_episode(episode, series, lines)
    if not validation.valid:
        raise HTTPException(
            status_code=409,
            detail={
                "message": "script validation failed",
                "errors": validation.errors,
            },
        )
    try:
        episode = await transition_episode(
            session, episode_id, EpisodeStatus.STORYBOARDING
        )
    except InvalidTransition as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    store_validation(episode, validation)
    await session.commit()
    await session.refresh(episode)
    return episode


@router.get("/{episode_id}/script", response_model=ScriptRead)
async def get_script(
    episode_id: str,
    session: AsyncSession = Depends(get_session),
) -> ScriptRead:
    episode = await session.get(Episode, episode_id)
    if episode is None:
        raise HTTPException(status_code=404, detail="episode not found")
    series = await load_series(session, episode)
    lines = await load_lines(session, episode_id)
    validation = validate_episode(episode, series, lines)
    return ScriptRead(
        episode_id=episode.id,
        status=episode.status,
        meta=episode.script_meta,
        lines=[ScriptLineRead.model_validate(line) for line in lines],
        validation=validation,
    )


@router.post(
    "/{episode_id}/actions/import-script",
    response_model=ArticleImportRead,
)
async def import_episode_article(
    episode_id: str,
    payload: ArticleImportRequest,
    session: AsyncSession = Depends(get_session),
) -> ArticleImportRead:
    try:
        result = await import_article(
            session,
            episode_id,
            payload.article,
            optimize=payload.optimize,
            instructions=payload.instructions,
        )
    except LookupError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except ArticleImportConflict as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    except ArticleImportError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    await session.commit()
    return ArticleImportRead(**result)


@router.post(
    "/{episode_id}/actions/optimize-script",
    response_model=ScriptOptimizeRead,
)
async def optimize_episode_script(
    episode_id: str,
    payload: ScriptOptimizeRequest,
    session: AsyncSession = Depends(get_session),
) -> ScriptOptimizeRead:
    try:
        result = await optimize_script(
            session,
            episode_id,
            apply=payload.apply,
            instructions=payload.instructions,
        )
    except LookupError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except ScriptOptimizeConflict as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    except ScriptOptimizeInvalid as exc:
        raise HTTPException(
            status_code=422,
            detail={
                "message": "optimized script validation failed",
                "errors": exc.validation.errors,
            },
        ) from exc
    except ScriptOptimizeError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    await session.commit()
    return ScriptOptimizeRead(**result)


@router.post("/{episode_id}/script/validate", response_model=ValidationResult)
async def validate_script_action(
    episode_id: str,
    session: AsyncSession = Depends(get_session),
) -> ValidationResult:
    episode = await session.get(Episode, episode_id)
    if episode is None:
        raise HTTPException(status_code=404, detail="episode not found")
    series = await load_series(session, episode)
    lines = await load_lines(session, episode_id)
    validation = validate_episode(episode, series, lines)
    store_validation(episode, validation)
    await session.commit()
    return validation

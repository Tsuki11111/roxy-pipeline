from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_session
from app.models.core import Episode, EpisodeStatus
from app.publish.package import build_package, load_package
from app.qc.service import QcConflict, QcRequestError
from app.render.service import RenderConflict, RenderRequestError
from app.schemas.core import (
    EpisodeActionAccepted,
    EpisodeRead,
    LineRevisionAccepted,
    LineRevisionRequest,
    ScriptLineRead,
)
from app.voice.align_service import AlignConflict, AlignRequestError
from app.voice.service import VoiceConflict, VoiceRequestError
from app.workflow.revision import (
    RevisionConflict,
    RevisionRequestError,
    revise_line,
)
from app.workflow.resume import ResumeConflict, resume_episode
from app.workflow.state_machine import InvalidTransition, transition_episode

router = APIRouter(prefix="/api/v1/episodes", tags=["episodes"])

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
    episode = await session.get(Episode, episode_id, with_for_update=True)
    if episode is None:
        raise HTTPException(status_code=404, detail="episode not found")
    if episode.status != EpisodeStatus.READY:
        raise HTTPException(
            status_code=409,
            detail=f"episode status {episode.status.value} is not READY",
        )
    try:
        await build_package(session, episode)
        episode = await transition_episode(
            session, episode_id, EpisodeStatus.PUBLISHED
        )
    except InvalidTransition as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    except (ValueError, LookupError) as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    await session.commit()
    await session.refresh(episode)
    return episode


@router.post("/{episode_id}/actions/package", response_model=dict)
async def package_episode_action(
    episode_id: str,
    session: AsyncSession = Depends(get_session),
) -> dict:
    episode = await session.get(Episode, episode_id)
    if episode is None:
        raise HTTPException(status_code=404, detail="episode not found")
    if episode.status not in {EpisodeStatus.READY, EpisodeStatus.PUBLISHED}:
        raise HTTPException(
            status_code=409,
            detail=f"episode status {episode.status.value} cannot package",
        )
    try:
        return await build_package(session, episode)
    except (ValueError, LookupError, RuntimeError) as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc


@router.get("/{episode_id}/package", response_model=dict)
async def get_package(
    episode_id: str,
    session: AsyncSession = Depends(get_session),
) -> dict:
    episode = await session.get(Episode, episode_id)
    if episode is None:
        raise HTTPException(status_code=404, detail="episode not found")
    manifest = load_package(episode_id)
    if manifest is None:
        raise HTTPException(status_code=404, detail="package not built")
    return manifest


@router.post(
    "/{episode_id}/actions/resume",
    response_model=EpisodeActionAccepted,
    status_code=status.HTTP_202_ACCEPTED,
)
async def resume_episode_action(
    episode_id: str,
    session: AsyncSession = Depends(get_session),
) -> EpisodeActionAccepted:
    try:
        episode, node = await resume_episode(session, episode_id)
    except LookupError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except ResumeConflict as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    except (
        VoiceConflict,
        AlignConflict,
        QcConflict,
        RenderConflict,
    ) as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    except (
        VoiceRequestError,
        AlignRequestError,
        QcRequestError,
        RenderRequestError,
    ) as exc:
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
    "/{episode_id}/actions/revise-line",
    response_model=LineRevisionAccepted,
    status_code=status.HTTP_202_ACCEPTED,
)
async def revise_script_line(
    episode_id: str,
    payload: LineRevisionRequest,
    session: AsyncSession = Depends(get_session),
) -> LineRevisionAccepted:
    try:
        episode, line, node = await revise_line(
            session, episode_id, payload.line_id, payload.text
        )
    except LookupError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except RevisionConflict as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    except RevisionRequestError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except (VoiceConflict, VoiceRequestError) as exc:
        status_code = 409 if isinstance(exc, VoiceConflict) else 400
        raise HTTPException(status_code=status_code, detail=str(exc)) from exc
    await session.commit()
    await session.refresh(episode)
    await session.refresh(line)
    return LineRevisionAccepted(
        episode_id=episode.id,
        status=episode.status,
        node_key=node.node_key,
        operation_id=node.id,
        line=ScriptLineRead.model_validate(line),
    )

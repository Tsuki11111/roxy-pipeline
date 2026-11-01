from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.agents.asset.service import AssetAgentError, generate_assets_for_episode
from app.db.session import get_session
from app.models.core import Episode, LineAudio, Review, ScriptLine
from app.providers.imagegen import ImageGenError
from app.providers.llm import LLMError
from app.qc.service import QcConflict, QcRequestError, start_qc
from app.schemas.core import (
    AssetAgentItem,
    AssetGenerateResponse,
    AssetRead,
    EpisodeActionAccepted,
    EpisodeAssetGenerateRequest,
    EpisodeAudioRead,
    LineAudioRead,
    QcReport,
    ReviewRead,
)
from app.voice.align_service import AlignConflict, AlignRequestError, start_align
from app.voice.service import VoiceConflict, VoiceRequestError, start_voice

router = APIRouter(prefix="/api/v1/episodes", tags=["episodes"])

async def _voice_action(
    session: AsyncSession,
    episode_id: str,
    *,
    retry: bool = False,
) -> EpisodeActionAccepted:
    try:
        episode, node = await start_voice(session, episode_id, retry=retry)
    except LookupError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except VoiceConflict as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    except VoiceRequestError as exc:
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
    "/{episode_id}/actions/generate-assets",
    response_model=AssetGenerateResponse,
)
async def generate_episode_assets(
    episode_id: str,
    payload: EpisodeAssetGenerateRequest,
    session: AsyncSession = Depends(get_session),
) -> AssetGenerateResponse:
    try:
        result = await generate_assets_for_episode(
            session,
            episode_id,
            asset_type=payload.asset_type,
            count=payload.count,
            auto_approve=payload.auto_approve,
            check=payload.check,
            force=payload.force,
        )
    except LookupError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except AssetAgentError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except (ImageGenError, LLMError) as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc
    await session.commit()
    return AssetGenerateResponse(
        text=result["text"],
        episode_id=result.get("episode_id"),
        plans=result["plans"],
        items=[
            AssetAgentItem(
                status=item["status"],
                asset=AssetRead.model_validate(item["asset"]),
            )
            for item in result["items"]
        ],
    )


@router.post(
    "/{episode_id}/actions/voice",
    response_model=EpisodeActionAccepted,
    status_code=status.HTTP_202_ACCEPTED,
)
async def voice_episode_action(
    episode_id: str,
    session: AsyncSession = Depends(get_session),
) -> EpisodeActionAccepted:
    return await _voice_action(session, episode_id)


@router.post(
    "/{episode_id}/actions/retry-voice",
    response_model=EpisodeActionAccepted,
    status_code=status.HTTP_202_ACCEPTED,
)
async def retry_voice(
    episode_id: str,
    session: AsyncSession = Depends(get_session),
) -> EpisodeActionAccepted:
    return await _voice_action(session, episode_id, retry=True)


async def _align_action(
    session: AsyncSession,
    episode_id: str,
    *,
    retry: bool = False,
) -> EpisodeActionAccepted:
    try:
        episode, node = await start_align(session, episode_id, retry=retry)
    except LookupError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except AlignConflict as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    except AlignRequestError as exc:
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
    "/{episode_id}/actions/align",
    response_model=EpisodeActionAccepted,
    status_code=status.HTTP_202_ACCEPTED,
)
async def align_episode_action(
    episode_id: str,
    session: AsyncSession = Depends(get_session),
) -> EpisodeActionAccepted:
    return await _align_action(session, episode_id)


@router.post(
    "/{episode_id}/actions/retry-align",
    response_model=EpisodeActionAccepted,
    status_code=status.HTTP_202_ACCEPTED,
)
async def retry_align(
    episode_id: str,
    session: AsyncSession = Depends(get_session),
) -> EpisodeActionAccepted:
    return await _align_action(session, episode_id, retry=True)


async def _qc_action(
    session: AsyncSession,
    episode_id: str,
    *,
    retry: bool = False,
) -> EpisodeActionAccepted:
    try:
        episode, node = await start_qc(session, episode_id, retry=retry)
    except LookupError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except QcConflict as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    except QcRequestError as exc:
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
    "/{episode_id}/actions/qc",
    response_model=EpisodeActionAccepted,
    status_code=status.HTTP_202_ACCEPTED,
)
async def qc_episode_action(
    episode_id: str,
    session: AsyncSession = Depends(get_session),
) -> EpisodeActionAccepted:
    return await _qc_action(session, episode_id)


@router.post(
    "/{episode_id}/actions/retry-qc",
    response_model=EpisodeActionAccepted,
    status_code=status.HTTP_202_ACCEPTED,
)
async def retry_qc(
    episode_id: str,
    session: AsyncSession = Depends(get_session),
) -> EpisodeActionAccepted:
    return await _qc_action(session, episode_id, retry=True)


@router.get("/{episode_id}/qc", response_model=QcReport)
async def get_qc_report(
    episode_id: str,
    session: AsyncSession = Depends(get_session),
) -> QcReport:
    episode = await session.get(Episode, episode_id)
    if episode is None:
        raise HTTPException(status_code=404, detail="episode not found")
    reviews = list(
        await session.scalars(
            select(Review)
            .where(Review.episode_id == episode_id)
            .order_by(Review.created_at)
        )
    )
    return QcReport(
        episode_id=episode.id,
        status=episode.status,
        health=episode.health,
        meta=episode.qc_meta,
        reviews=[ReviewRead.model_validate(review) for review in reviews],
    )


@router.get("/{episode_id}/audio", response_model=EpisodeAudioRead)
async def get_episode_audio(
    episode_id: str,
    session: AsyncSession = Depends(get_session),
) -> EpisodeAudioRead:
    episode = await session.get(Episode, episode_id)
    if episode is None:
        raise HTTPException(status_code=404, detail="episode not found")
    rows = await session.execute(
        select(LineAudio, ScriptLine.seq)
        .join(ScriptLine, LineAudio.script_line_id == ScriptLine.id)
        .where(LineAudio.episode_id == episode_id)
        .order_by(ScriptLine.seq)
    )
    lines = [
        LineAudioRead.model_validate(audio).model_copy(update={"seq": seq})
        for audio, seq in rows.all()
    ]
    return EpisodeAudioRead(
        episode_id=episode.id,
        status=episode.status,
        audio_path=episode.audio_path,
        meta=episode.audio_meta,
        lines=lines,
    )

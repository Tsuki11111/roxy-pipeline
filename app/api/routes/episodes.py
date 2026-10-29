from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query, status
from jinja2 import TemplateNotFound
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.agents.script_service import ScriptConflict, ScriptRequestError, start_script
from app.agents.script_validation import ValidationResult
from app.api.script_utils import (
    load_lines,
    load_series,
    store_validation,
    validate_episode,
)
from app.api.storyboard_utils import (
    build_render_spec,
    load_script_lines,
    load_shots,
    store_rhythm,
    validate_storyboard,
)
from app.db.session import get_session
from app.media.align_service import (
    AlignConflict,
    AlignRequestError,
    start_align,
)
from app.media.service import (
    VoiceConflict,
    VoiceRequestError,
    start_voice,
)
from app.models.core import Episode, EpisodeStatus, LineAudio, ScriptLine, Series
from app.render.models import EpisodeSpec
from app.render.stage import build_stage_payload
from app.render.timeline import build_timeline
from app.schemas.core import (
    EpisodeActionAccepted,
    EpisodeAudioRead,
    EpisodeCreate,
    EpisodeRead,
    LineAudioRead,
    ScriptLineRead,
    ScriptRead,
    ShotRead,
    StoryboardRead,
)
from app.storyboard.models import RhythmReport
from app.storyboard.service import (
    StoryboardConflict,
    StoryboardRequestError,
    start_storyboard,
)
from app.workflow.render_service import (
    RenderConflict,
    RenderRequestError,
    start_render,
)
from app.workflow.state_machine import InvalidTransition, transition_episode

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


@router.put("/{episode_id}/render-spec", response_model=EpisodeRead)
async def put_render_spec(
    episode_id: str,
    spec: EpisodeSpec,
    session: AsyncSession = Depends(get_session),
) -> Episode:
    episode = await session.get(Episode, episode_id)
    if episode is None:
        raise HTTPException(status_code=404, detail="episode not found")
    if episode.status == EpisodeStatus.RENDERING:
        raise HTTPException(status_code=409, detail="episode is rendering")
    try:
        build_stage_payload(spec, build_timeline(spec))
    except (FileNotFoundError, ValueError, TemplateNotFound) as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    episode.render_spec = spec.model_dump()
    await session.commit()
    await session.refresh(episode)
    return episode


@router.post(
    "/{episode_id}/actions/render",
    response_model=EpisodeActionAccepted,
    status_code=status.HTTP_202_ACCEPTED,
)
async def render_episode_action(
    episode_id: str,
    session: AsyncSession = Depends(get_session),
) -> EpisodeActionAccepted:
    try:
        episode, node = await start_render(session, episode_id)
    except LookupError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except RenderConflict as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    except RenderRequestError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except (FileNotFoundError, ValueError, TemplateNotFound) as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    await session.commit()
    await session.refresh(episode)
    return EpisodeActionAccepted(
        episode_id=episode.id,
        status=episode.status,
        node_key=node.node_key,
        operation_id=node.id,
    )


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


async def _script_action(
    session: AsyncSession,
    episode_id: str,
    *,
    regenerate: bool = False,
    retry: bool = False,
) -> EpisodeActionAccepted:
    try:
        episode, node = await start_script(
            session, episode_id, regenerate=regenerate, retry=retry
        )
    except LookupError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except ScriptConflict as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    except ScriptRequestError as exc:
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
    "/{episode_id}/actions/confirm-topic",
    response_model=EpisodeActionAccepted,
    status_code=status.HTTP_202_ACCEPTED,
)
async def confirm_topic(
    episode_id: str,
    session: AsyncSession = Depends(get_session),
) -> EpisodeActionAccepted:
    episode = await session.get(Episode, episode_id, with_for_update=True)
    if episode is None:
        raise HTTPException(status_code=404, detail="episode not found")
    if episode.status == EpisodeStatus.DRAFT:
        episode.status = EpisodeStatus.TOPIC_CONFIRMED
    elif episode.status != EpisodeStatus.TOPIC_CONFIRMED:
        raise HTTPException(
            status_code=409,
            detail=f"episode status {episode.status.value} cannot confirm topic",
        )
    await session.flush()
    return await _script_action(session, episode_id)


@router.post(
    "/{episode_id}/actions/retry-script",
    response_model=EpisodeActionAccepted,
    status_code=status.HTTP_202_ACCEPTED,
)
async def retry_script(
    episode_id: str,
    session: AsyncSession = Depends(get_session),
) -> EpisodeActionAccepted:
    return await _script_action(session, episode_id, retry=True)


@router.post(
    "/{episode_id}/actions/regenerate-script",
    response_model=EpisodeActionAccepted,
    status_code=status.HTTP_202_ACCEPTED,
)
async def regenerate_script(
    episode_id: str,
    session: AsyncSession = Depends(get_session),
) -> EpisodeActionAccepted:
    return await _script_action(session, episode_id, regenerate=True)


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
    return await _transition(session, episode_id, EpisodeStatus.PUBLISHED)


async def _storyboard_action(
    session: AsyncSession,
    episode_id: str,
    *,
    regenerate: bool = False,
    retry: bool = False,
) -> EpisodeActionAccepted:
    try:
        episode, node = await start_storyboard(
            session, episode_id, regenerate=regenerate, retry=retry
        )
    except LookupError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except StoryboardConflict as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    except StoryboardRequestError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    await session.commit()
    await session.refresh(episode)
    return EpisodeActionAccepted(
        episode_id=episode.id,
        status=episode.status,
        node_key=node.node_key,
        operation_id=node.id,
    )


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


@router.post(
    "/{episode_id}/actions/generate-storyboard",
    response_model=EpisodeActionAccepted,
    status_code=status.HTTP_202_ACCEPTED,
)
async def generate_storyboard(
    episode_id: str,
    session: AsyncSession = Depends(get_session),
) -> EpisodeActionAccepted:
    return await _storyboard_action(session, episode_id)


@router.post(
    "/{episode_id}/actions/retry-storyboard",
    response_model=EpisodeActionAccepted,
    status_code=status.HTTP_202_ACCEPTED,
)
async def retry_storyboard(
    episode_id: str,
    session: AsyncSession = Depends(get_session),
) -> EpisodeActionAccepted:
    return await _storyboard_action(session, episode_id, retry=True)


@router.post(
    "/{episode_id}/actions/regenerate-storyboard",
    response_model=EpisodeActionAccepted,
    status_code=status.HTTP_202_ACCEPTED,
)
async def regenerate_storyboard(
    episode_id: str,
    session: AsyncSession = Depends(get_session),
) -> EpisodeActionAccepted:
    return await _storyboard_action(session, episode_id, regenerate=True)


@router.get("/{episode_id}/storyboard", response_model=StoryboardRead)
async def get_storyboard(
    episode_id: str,
    session: AsyncSession = Depends(get_session),
) -> StoryboardRead:
    episode = await session.get(Episode, episode_id)
    if episode is None:
        raise HTTPException(status_code=404, detail="episode not found")
    series = await load_series(session, episode)
    if series is None:
        raise HTTPException(status_code=404, detail="series not found")
    lines = await load_script_lines(session, episode_id)
    shots = await load_shots(session, episode_id)
    report = validate_storyboard(series, lines, shots)
    return StoryboardRead(
        episode_id=episode.id,
        status=episode.status,
        meta=episode.storyboard_meta,
        shots=[ShotRead.model_validate(shot) for shot in shots],
        rhythm=report,
    )


@router.post("/{episode_id}/storyboard/validate", response_model=RhythmReport)
async def validate_storyboard_action(
    episode_id: str,
    session: AsyncSession = Depends(get_session),
) -> RhythmReport:
    episode = await session.get(Episode, episode_id)
    if episode is None:
        raise HTTPException(status_code=404, detail="episode not found")
    series = await load_series(session, episode)
    if series is None:
        raise HTTPException(status_code=404, detail="series not found")
    lines = await load_script_lines(session, episode_id)
    shots = await load_shots(session, episode_id)
    report = validate_storyboard(series, lines, shots)
    store_rhythm(episode, report)
    await session.commit()
    return report


@router.post("/{episode_id}/actions/confirm-storyboard", response_model=EpisodeRead)
async def confirm_storyboard(
    episode_id: str,
    session: AsyncSession = Depends(get_session),
) -> Episode:
    episode = await session.get(Episode, episode_id, with_for_update=True)
    if episode is None:
        raise HTTPException(status_code=404, detail="episode not found")
    if episode.status != EpisodeStatus.STORYBOARDING:
        raise HTTPException(
            status_code=409,
            detail=f"episode status {episode.status.value} is not STORYBOARDING",
        )
    series = await load_series(session, episode)
    if series is None:
        raise HTTPException(status_code=404, detail="series not found")
    lines = await load_script_lines(session, episode_id)
    shots = await load_shots(session, episode_id)
    report = validate_storyboard(series, lines, shots)
    if not report.valid:
        raise HTTPException(
            status_code=409,
            detail={"message": "storyboard rhythm check failed", "errors": report.errors},
        )
    try:
        episode = await transition_episode(
            session, episode_id, EpisodeStatus.VOICING
        )
    except InvalidTransition as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    store_rhythm(episode, report)
    await session.commit()
    await session.refresh(episode)
    return episode


@router.post("/{episode_id}/actions/build-render-spec", response_model=EpisodeRead)
async def build_render_spec_action(
    episode_id: str,
    session: AsyncSession = Depends(get_session),
) -> Episode:
    episode = await session.get(Episode, episode_id)
    if episode is None:
        raise HTTPException(status_code=404, detail="episode not found")
    if episode.status == EpisodeStatus.RENDERING:
        raise HTTPException(status_code=409, detail="episode is rendering")
    try:
        spec = await build_render_spec(session, episode)
    except (LookupError, ValueError, FileNotFoundError, TemplateNotFound) as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    episode.render_spec = spec.model_dump()
    await session.commit()
    await session.refresh(episode)
    return episode

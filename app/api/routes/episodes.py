from __future__ import annotations

from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException, Query, Response, status
from fastapi.responses import FileResponse
from jinja2 import TemplateNotFound
from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings

from app.agents.asset.service import (
    AssetAgentError,
    generate_assets_for_episode,
)
from app.agents.script.optimizer import (
    ScriptOptimizeConflict,
    ScriptOptimizeError,
    ScriptOptimizeInvalid,
    optimize_script,
)
from app.agents.script.importer import (
    ArticleImportConflict,
    ArticleImportError,
    import_article,
)
from app.agents.script.validation import ValidationResult
from app.agents.script.utils import (
    load_lines,
    load_series,
    store_validation,
    validate_episode,
)
from app.agents.storyboard.utils import (
    build_render_spec,
    load_script_lines,
    load_shots,
    store_rhythm,
    validate_storyboard,
)
from app.db.session import get_session
from app.voice.align_service import (
    AlignConflict,
    AlignRequestError,
    start_align,
)
from app.voice.service import (
    VoiceConflict,
    VoiceRequestError,
    start_voice,
)
from app.models.core import (
    Episode,
    EpisodeStatus,
    LineAudio,
    NodeRun,
    OutboxEvent,
    Review,
    ScriptLine,
    Series,
    Shot,
)
from app.providers.imagegen import ImageGenError
from app.providers.llm import LLMError
from app.publish.package import build_package, load_package
from app.qc.service import QcConflict, QcRequestError, start_qc
from app.render.models import EpisodeSpec
from app.render.stage import build_stage_payload
from app.render.timeline import build_timeline
from app.schemas.core import (
    AssetAgentItem,
    AssetGenerateResponse,
    ArticleImportRead,
    ArticleImportRequest,
    EpisodeActionAccepted,
    EpisodeAssetGenerateRequest,
    EpisodeAudioRead,
    EpisodeCreate,
    EpisodeRead,
    LineAudioRead,
    LineRevisionAccepted,
    LineRevisionRequest,
    QcReport,
    ReviewRead,
    ScriptLineRead,
    ScriptOptimizeRead,
    ScriptOptimizeRequest,
    ScriptRead,
    ShotRead,
    StoryboardRead,
)
from app.agents.storyboard.models import RhythmReport
from app.agents.storyboard.service import (
    StoryboardConflict,
    StoryboardRequestError,
    start_storyboard,
)
from app.render.service import (
    RenderConflict,
    RenderRequestError,
    rerender_episode,
    start_render,
)
from app.workflow.revision import (
    RevisionConflict,
    RevisionRequestError,
    revise_line,
)
from app.workflow.resume import ResumeConflict, resume_episode
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

    for model in (Review, LineAudio, OutboxEvent, NodeRun, Shot, ScriptLine):
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


@router.post(
    "/{episode_id}/actions/rerender",
    response_model=EpisodeActionAccepted,
    status_code=status.HTTP_202_ACCEPTED,
)
async def rerender_episode_action(
    episode_id: str,
    session: AsyncSession = Depends(get_session),
) -> EpisodeActionAccepted:
    try:
        episode, node = await rerender_episode(session, episode_id)
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

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status
from jinja2 import TemplateNotFound
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.agents.remotion.docker import workdir_for as remotion_workdir
from app.agents.remotion.service import (
    RemotionConflict,
    RemotionRequestError,
    cancel_remotion_codegen,
    start_remotion_codegen,
)
from app.db.session import get_session
from app.models.core import Episode, EpisodeStatus, RemotionShot, Shot
from app.render.models import EpisodeSpec
from app.render.service import (
    RenderConflict,
    RenderRequestError,
    rerender_episode,
    start_render,
)
from app.render.timeline import build_timeline
from app.schemas.core import (
    EpisodeActionAccepted,
    EpisodeRead,
    RemotionCodeRead,
    RemotionEpisodeRead,
    RemotionGenerateRequest,
    RemotionShotRead,
)

router = APIRouter(prefix="/api/v1/episodes", tags=["episodes"])

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
        build_timeline(spec)
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


@router.post(
    "/{episode_id}/actions/generate-remotion",
    response_model=EpisodeActionAccepted,
    status_code=status.HTTP_202_ACCEPTED,
)
async def generate_remotion_action(
    episode_id: str,
    payload: RemotionGenerateRequest = RemotionGenerateRequest(),
    session: AsyncSession = Depends(get_session),
) -> EpisodeActionAccepted:
    try:
        episode, node = await start_remotion_codegen(
            session, episode_id, shot_ids=payload.shot_ids
        )
    except LookupError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except RemotionConflict as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    except RemotionRequestError as exc:
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
    "/{episode_id}/actions/cancel-remotion",
    response_model=EpisodeActionAccepted,
    status_code=status.HTTP_202_ACCEPTED,
)
async def cancel_remotion_action(
    episode_id: str,
    session: AsyncSession = Depends(get_session),
) -> EpisodeActionAccepted:
    try:
        episode, node = await cancel_remotion_codegen(session, episode_id)
    except LookupError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except RemotionConflict as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    await session.commit()
    await session.refresh(episode)
    return EpisodeActionAccepted(
        episode_id=episode.id,
        status=episode.status,
        node_key=node.node_key,
        operation_id=node.id,
    )


def _remotion_shot_read(row: RemotionShot, seq: int) -> RemotionShotRead:
    return RemotionShotRead(
        id=row.id,
        episode_id=row.episode_id,
        shot_id=row.shot_id,
        seq=seq,
        composition_id=row.composition_id,
        code_hash=row.code_hash,
        code_path=row.code_path,
        status=row.status,
        error=row.error,
        attempts=row.attempts,
        prompt_hash=row.prompt_hash,
        model=row.model,
        image_digest=row.image_digest,
    )


@router.get("/{episode_id}/remotion", response_model=RemotionEpisodeRead)
async def get_remotion(
    episode_id: str,
    session: AsyncSession = Depends(get_session),
) -> RemotionEpisodeRead:
    episode = await session.get(Episode, episode_id)
    if episode is None:
        raise HTTPException(status_code=404, detail="episode not found")
    rows = list(
        (
            await session.execute(
                select(RemotionShot, Shot.seq)
                .join(Shot, RemotionShot.shot_id == Shot.id)
                .where(RemotionShot.episode_id == episode_id)
                .order_by(Shot.seq)
            )
        ).all()
    )
    return RemotionEpisodeRead(
        episode_id=episode.id,
        status=episode.status,
        health=episode.health,
        meta=episode.remotion_meta,
        shots=[_remotion_shot_read(row, seq) for row, seq in rows],
    )


@router.get(
    "/{episode_id}/remotion/shots/{shot_id}",
    response_model=RemotionCodeRead,
)
async def get_remotion_code(
    episode_id: str,
    shot_id: str,
    session: AsyncSession = Depends(get_session),
) -> RemotionCodeRead:
    row = await session.scalar(
        select(RemotionShot).where(
            RemotionShot.episode_id == episode_id,
            RemotionShot.shot_id == shot_id,
        )
    )
    if row is None:
        raise HTTPException(status_code=404, detail="remotion shot not found")
    shot = await session.get(Shot, shot_id)
    if shot is None:
        raise HTTPException(status_code=404, detail="shot not found")
    workdir = remotion_workdir(episode_id)
    path = (workdir / row.code_path).resolve()
    code = ""
    if path.is_relative_to(workdir.resolve()) and path.is_file():
        code = path.read_text(encoding="utf-8", errors="replace")
    return RemotionCodeRead(shot=_remotion_shot_read(row, shot.seq), code=code)

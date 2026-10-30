from __future__ import annotations

import base64
import hashlib
import mimetypes
import uuid
from datetime import datetime, timezone
from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import FileResponse
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.agents.asset.service import AssetAgentError, generate_assets_from_text
from app.assets.store import ingest_asset, sha256_file
from app.core.config import get_settings
from app.db.session import get_session
from app.models.core import Asset, AssetStatus, AssetType
from app.providers.imagegen import ImageGenError, build_image_provider
from app.providers.llm import LLMError, build_llm
from app.qc.vision import check_image_asset
from app.schemas.core import (
    AssetAgentItem,
    AssetGenerateRequest,
    AssetGenerateResponse,
    AssetQcRead,
    AssetRead,
    AssetUploadRequest,
    ImagePromptRead,
    ImagePromptRequest,
    SeedreamGenerateRequest,
    SeedreamGenerateResponse,
)

PROJECT_ROOT = Path(__file__).resolve().parents[3]

router = APIRouter(prefix="/api/v1/assets", tags=["assets"])


@router.get("", response_model=list[AssetRead])
async def list_assets(
    asset_type: AssetType | None = Query(default=None, alias="type"),
    status: AssetStatus | None = None,
    tag: str | None = None,
    reuse_key: str | None = None,
    limit: int = Query(default=100, ge=1, le=500),
    session: AsyncSession = Depends(get_session),
) -> list[Asset]:
    stmt = select(Asset).order_by(Asset.created_at.desc()).limit(limit)
    if asset_type is not None:
        stmt = stmt.where(Asset.type == asset_type)
    if status is not None:
        stmt = stmt.where(Asset.status == status)
    if reuse_key is not None:
        stmt = stmt.where(Asset.reuse_key == reuse_key)
    result = await session.scalars(stmt)
    assets = list(result)
    if tag:
        assets = [asset for asset in assets if tag in (asset.tags or [])]
    return assets


@router.post("/generate", response_model=AssetGenerateResponse)
async def generate_assets(
    payload: AssetGenerateRequest,
    session: AsyncSession = Depends(get_session),
) -> AssetGenerateResponse:
    try:
        result = await generate_assets_from_text(
            session,
            payload.text,
            asset_type=payload.asset_type,
            count=payload.count,
            auto_approve=payload.auto_approve,
            check=payload.check,
            force=payload.force,
        )
    except AssetAgentError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except (ImageGenError, LLMError) as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc
    await session.commit()
    return AssetGenerateResponse(
        text=result["text"],
        plans=result["plans"],
        items=[
            AssetAgentItem(
                status=item["status"],
                asset=AssetRead.model_validate(item["asset"]),
            )
            for item in result["items"]
        ],
    )


@router.get("/file")
async def get_asset_file(path: str = Query(min_length=1)) -> FileResponse:
    candidate = (PROJECT_ROOT / path).resolve()
    if not candidate.is_relative_to(PROJECT_ROOT) or not candidate.is_file():
        raise HTTPException(status_code=404, detail="asset file not found")
    if candidate.suffix.lower() not in {".png", ".jpg", ".jpeg", ".webp"}:
        raise HTTPException(status_code=404, detail="asset file not found")
    media_type = mimetypes.guess_type(candidate.name)[0] or "application/octet-stream"
    return FileResponse(
        candidate,
        media_type=media_type,
        headers={"Cache-Control": "public, max-age=3600"},
    )


@router.post("/upload", response_model=AssetRead)
async def upload_asset(
    payload: AssetUploadRequest,
    session: AsyncSession = Depends(get_session),
) -> Asset:
    raw = payload.data_base64.split(",", 1)[-1]
    try:
        data = base64.b64decode(raw, validate=True)
    except Exception as exc:
        raise HTTPException(status_code=422, detail="invalid base64 image") from exc
    if not data or len(data) > 20 * 1024 * 1024:
        raise HTTPException(status_code=422, detail="image must be under 20MB")

    suffix = Path(payload.filename).suffix.lower()
    if suffix not in {".png", ".jpg", ".jpeg", ".webp"}:
        raise HTTPException(status_code=422, detail="unsupported image type")
    checksum = hashlib.sha256(data).hexdigest()
    tmp_dir = Path(get_settings().asset_agent_tmp_dir).resolve() / "uploads"
    tmp_dir.mkdir(parents=True, exist_ok=True)
    tmp_path = tmp_dir / f"{checksum[:16]}{suffix}"
    tmp_path.write_bytes(data)
    try:
        asset = await ingest_asset(
            session,
            tmp_path,
            asset_type=payload.asset_type,
            name=payload.name or Path(payload.filename).stem,
            reuse_key=f"upload:{checksum[:16]}",
            source="upload",
            status=AssetStatus.APPROVED,
            meta={"original_filename": payload.filename},
        )
    except Exception as exc:
        raise HTTPException(status_code=422, detail=f"invalid image: {exc}") from exc
    finally:
        tmp_path.unlink(missing_ok=True)
    await session.commit()
    await session.refresh(asset)
    return asset


PROMPT_WRITER_SYSTEM = (
    "你是科普视频素材的生图提示词写手。把用户的中文描述改写成适合 Seedream 的"
    "单张素材提示词：主体明确、构图和视角清楚、光线和风格具体；"
    "默认使用纯白背景，便于后期叠加到视频；"
    "不要出现文字、字幕、水印、边框或多个主体；"
    "不要生成已有版权角色或模仿具体画师；洛琪希等角色由用户提供，不在此生成。"
    '只输出 JSON：{"prompt":"最终提示词"}'
)


@router.post("/image-prompt", response_model=ImagePromptRead)
async def write_image_prompt(payload: ImagePromptRequest) -> ImagePromptRead:
    try:
        raw = await build_llm().chat_json(
            PROMPT_WRITER_SYSTEM,
            payload.description,
            temperature=0.6,
            max_tokens=600,
        )
    except LLMError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc
    prompt = str(raw.get("prompt", "")).strip()
    if not prompt:
        raise HTTPException(status_code=502, detail="prompt writer returned empty prompt")
    return ImagePromptRead(prompt=prompt)


@router.post("/seedream", response_model=SeedreamGenerateResponse)
async def generate_seedream_assets(
    payload: SeedreamGenerateRequest,
    session: AsyncSession = Depends(get_session),
) -> SeedreamGenerateResponse:
    settings = get_settings()
    provider = build_image_provider()
    out_dir = Path(settings.asset_agent_tmp_dir).resolve() / "seedream"
    out_dir.mkdir(parents=True, exist_ok=True)
    assets: list[Asset] = []
    for index in range(payload.count):
        out_path = out_dir / f"{uuid.uuid4().hex}.png"
        try:
            await provider.generate(payload.prompt, out_path, payload.size)
        except ImageGenError as exc:
            raise HTTPException(status_code=502, detail=str(exc)) from exc
        checksum = sha256_file(out_path)
        asset = await ingest_asset(
            session,
            out_path,
            asset_type=AssetType.PROP,
            name=f"Seedream 素材 {index + 1}",
            reuse_key=f"seedream:{checksum[:16]}",
            source="seedream",
            status=AssetStatus.CANDIDATE,
            provider="ark",
            model=settings.ark_image_model,
            prompt=payload.prompt,
            meta={"size": payload.size},
        )
        out_path.unlink(missing_ok=True)
        assets.append(asset)
    await session.commit()
    for asset in assets:
        await session.refresh(asset)
    return SeedreamGenerateResponse(
        prompt=payload.prompt,
        size=payload.size,
        assets=[AssetRead.model_validate(asset) for asset in assets],
    )


@router.get("/{asset_id}", response_model=AssetRead)
async def get_asset(
    asset_id: str,
    session: AsyncSession = Depends(get_session),
) -> Asset:
    asset = await session.get(Asset, asset_id)
    if asset is None:
        raise HTTPException(status_code=404, detail="asset not found")
    return asset


@router.post("/{asset_id}/approve", response_model=AssetRead)
async def approve_asset(
    asset_id: str,
    session: AsyncSession = Depends(get_session),
) -> Asset:
    asset = await session.get(Asset, asset_id)
    if asset is None:
        raise HTTPException(status_code=404, detail="asset not found")
    asset.status = AssetStatus.APPROVED
    await session.commit()
    await session.refresh(asset)
    return asset


@router.post("/{asset_id}/reject", response_model=AssetRead)
async def reject_asset(
    asset_id: str,
    session: AsyncSession = Depends(get_session),
) -> Asset:
    asset = await session.get(Asset, asset_id)
    if asset is None:
        raise HTTPException(status_code=404, detail="asset not found")
    asset.status = AssetStatus.REJECTED
    await session.commit()
    await session.refresh(asset)
    return asset


@router.post("/{asset_id}/check", response_model=AssetQcRead)
async def check_asset(
    asset_id: str,
    session: AsyncSession = Depends(get_session),
) -> AssetQcRead:
    asset = await session.get(Asset, asset_id)
    if asset is None:
        raise HTTPException(status_code=404, detail="asset not found")
    image = Path(asset.path)
    if not image.is_absolute():
        image = PROJECT_ROOT / image
    if not image.is_file():
        raise HTTPException(status_code=404, detail="asset image not found")

    context = (
        f"类型={asset.type.value}，名称={asset.name}，"
        f"reuse_key={asset.reuse_key}，prompt={asset.prompt or ''}"
    )
    try:
        verdict = await check_image_asset(
            image,
            build_llm(),
            context=context,
            timeout_s=get_settings().qc_vision_timeout_s,
        )
    except LLMError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc

    meta = dict(asset.meta or {})
    meta["qc"] = {
        "passed": verdict["pass"],
        "issues": verdict["issues"],
        "model": get_settings().deepseek_model,
        "checked_at": datetime.now(timezone.utc).isoformat(),
    }
    asset.meta = meta
    await session.commit()
    await session.refresh(asset)
    return AssetQcRead(
        asset_id=asset.id,
        passed=verdict["pass"],
        issues=verdict["issues"],
        meta=meta,
    )

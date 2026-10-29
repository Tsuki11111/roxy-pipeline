from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.agents.asset.service import AssetAgentError, generate_assets_from_text
from app.core.config import get_settings
from app.db.session import get_session
from app.models.core import Asset, AssetStatus, AssetType
from app.providers.imagegen import ImageGenError
from app.providers.llm import LLMError, build_llm
from app.qc.vision import check_image_asset
from app.schemas.core import (
    AssetAgentItem,
    AssetGenerateRequest,
    AssetGenerateResponse,
    AssetQcRead,
    AssetRead,
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

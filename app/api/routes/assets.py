from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_session
from app.models.core import Asset, AssetStatus, AssetType
from app.schemas.core import AssetRead

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

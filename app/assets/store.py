from __future__ import annotations

from pathlib import Path

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.models.core import Asset, AssetStatus, AssetType
from app.storage.assets import image_info, sha256_file, store_asset_file
from app.storage.paths import PROJECT_ROOT, relative_project_path


def asset_path(asset: Asset) -> Path:
    return (PROJECT_ROOT / asset.path).resolve()


async def find_reusable(
    session: AsyncSession, reuse_key: str
) -> Asset | None:
    return await session.scalar(
        select(Asset).where(
            Asset.reuse_key == reuse_key,
            Asset.status == AssetStatus.APPROVED,
        )
    )


async def ingest_asset(
    session: AsyncSession,
    source_path: Path,
    *,
    asset_type: AssetType,
    name: str,
    reuse_key: str,
    source: str = "manual",
    status: AssetStatus = AssetStatus.APPROVED,
    copy: bool = True,
    provider: str | None = None,
    model: str | None = None,
    prompt: str | None = None,
    seed: str | None = None,
    reference: str | None = None,
    tags: list[str] | None = None,
    meta: dict | None = None,
    root: Path | None = None,
) -> Asset:
    source_path = source_path.resolve()
    if not source_path.is_file():
        raise FileNotFoundError(source_path)

    existing = await session.scalar(
        select(Asset).where(Asset.reuse_key == reuse_key)
    )
    if existing is not None and existing.status == AssetStatus.APPROVED:
        return existing

    checksum = sha256_file(source_path)
    same_file = await session.scalar(
        select(Asset)
        .where(Asset.type == asset_type, Asset.checksum == checksum)
        .order_by(Asset.created_at)
        .limit(1)
    )
    if same_file is not None:
        stored_path = same_file.path
    elif copy:
        settings = get_settings()
        stored_path = store_asset_file(
            source_path,
            target_root=root or Path(settings.asset_root),
            asset_type=asset_type.value,
            checksum=checksum,
        )
    else:
        stored_path = relative_project_path(source_path)

    width, height, mime = image_info(source_path)
    fields = {
        "type": asset_type,
        "name": name,
        "reuse_key": reuse_key,
        "path": stored_path,
        "checksum": checksum,
        "width": width,
        "height": height,
        "mime": mime,
        "source": source,
        "provider": provider,
        "model": model,
        "prompt": prompt,
        "seed": seed,
        "reference": reference,
        "tags": tags or [],
        "meta": meta or {},
        "status": status,
    }
    if existing is None:
        asset = Asset(**fields)
        session.add(asset)
    else:
        asset = existing
        for key, value in fields.items():
            setattr(asset, key, value)
    await session.flush()
    return asset
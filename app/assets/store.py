from __future__ import annotations

import hashlib
import mimetypes
import shutil
from pathlib import Path

from PIL import Image
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.models.core import Asset, AssetStatus, AssetType

PROJECT_ROOT = Path(__file__).resolve().parents[2]


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def image_info(path: Path) -> tuple[int, int, str]:
    with Image.open(path) as image:
        width, height = image.size
    mime = mimetypes.guess_type(path.name)[0] or "image/png"
    return width, height, mime


def relative_project_path(path: Path) -> str:
    resolved = path.resolve()
    if not resolved.is_relative_to(PROJECT_ROOT):
        raise ValueError(f"asset path escapes project root: {path}")
    return resolved.relative_to(PROJECT_ROOT).as_posix()


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
        target_dir = (root or Path(settings.asset_root)).resolve() / asset_type.value
        target_dir.mkdir(parents=True, exist_ok=True)
        target = target_dir / f"{checksum[:16]}{source_path.suffix.lower()}"
        if not target.exists():
            shutil.copy2(source_path, target)
        stored_path = relative_project_path(target)
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

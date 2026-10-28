from __future__ import annotations

import shutil
import uuid
from pathlib import Path

from PIL import Image

from app.assets.registry import resolve_background, resolve_floor
from app.assets.store import PROJECT_ROOT, ingest_asset
from app.models.core import AssetStatus, AssetType


def make_png(path: Path) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    Image.new("RGB", (16, 9), "beige").save(path)
    return path


async def test_background_resolver_prefers_approved_asset(db, session):
    root = PROJECT_ROOT / "tmp" / f"asset_test_{uuid.uuid4().hex}"
    source = make_png(root.parent / f"bg_{uuid.uuid4().hex}.png")
    try:
        fallback = await resolve_background(session, "paper")
        assert fallback == "character_packs/placeholder/background.png"

        asset = await ingest_asset(
            session,
            source,
            asset_type=AssetType.BACKGROUND,
            name="paper",
            reuse_key="bg:paper:light",
            status=AssetStatus.APPROVED,
            copy=True,
            root=root,
        )
        await session.commit()
        resolved = await resolve_background(session, "paper")
        assert resolved == asset.path

        floor = await resolve_floor(session)
        assert floor == "character_packs/placeholder/floor.png"
    finally:
        shutil.rmtree(root, ignore_errors=True)
        source.unlink(missing_ok=True)

from __future__ import annotations

import shutil
import uuid
from pathlib import Path

from PIL import Image
from sqlalchemy import select

from app.assets.store import PROJECT_ROOT, find_reusable, ingest_asset
from app.models.core import Asset, AssetStatus, AssetType


def make_png(path: Path, color: str = "white") -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    Image.new("RGB", (32, 18), color).save(path)
    return path


async def test_ingest_reuses_reuse_key_and_checksum(db, session):
    root = PROJECT_ROOT / "tmp" / f"asset_test_{uuid.uuid4().hex}"
    source = make_png(root.parent / f"source_{uuid.uuid4().hex}.png")
    try:
        first = await ingest_asset(
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
        assert first.path.startswith("tmp/asset_test_")
        assert (PROJECT_ROOT / first.path).is_file()
        assert (first.width, first.height) == (32, 18)

        # Same reuse_key returns the existing row without a new file.
        again = await ingest_asset(
            session,
            source,
            asset_type=AssetType.BACKGROUND,
            name="paper-2",
            reuse_key="bg:paper:light",
            status=AssetStatus.APPROVED,
            copy=True,
            root=root,
        )
        assert again.id == first.id
        assert again.path == first.path

        # Different reuse_key but identical bytes reuses the stored file.
        copy = make_png(root.parent / f"copy_{uuid.uuid4().hex}.png")
        shutil.copyfile(source, copy)
        other = await ingest_asset(
            session,
            copy,
            asset_type=AssetType.BACKGROUND,
            name="paper-alias",
            reuse_key="bg:paper:alias",
            status=AssetStatus.APPROVED,
            copy=True,
            root=root,
        )
        await session.commit()
        assert other.path == first.path
        assert other.checksum == first.checksum

        found = await find_reusable(session, "bg:paper:light")
        assert found is not None
        assert found.id == first.id
    finally:
        shutil.rmtree(root, ignore_errors=True)
        source.unlink(missing_ok=True)
        if "copy" in locals():
            copy.unlink(missing_ok=True)


async def test_candidate_is_not_reusable(db, session):
    root = PROJECT_ROOT / "tmp" / f"asset_test_{uuid.uuid4().hex}"
    source = make_png(root.parent / f"candidate_{uuid.uuid4().hex}.png")
    try:
        await ingest_asset(
            session,
            source,
            asset_type=AssetType.PROP,
            name="candidate",
            reuse_key="prop:candidate",
            status=AssetStatus.CANDIDATE,
            copy=True,
            root=root,
        )
        await session.commit()
        assert await find_reusable(session, "prop:candidate") is None
        rows = list(await session.scalars(select(Asset)))
        assert len(rows) == 1
    finally:
        shutil.rmtree(root, ignore_errors=True)
        source.unlink(missing_ok=True)

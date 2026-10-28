#!/usr/bin/env python3
"""Index existing images into the persistent asset store.

Existing generated images are reused instead of regenerated. Generated
backgrounds/props are copied to data/assets; character packs stay in place and
are indexed by path.
"""

from __future__ import annotations

import argparse
import asyncio
import json
import sys
from pathlib import Path

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.pool import NullPool

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

import app.models  # noqa: E402,F401 - register tables
from app.assets.store import ingest_asset  # noqa: E402
from app.core.config import get_settings  # noqa: E402
from app.db.base import Base  # noqa: E402
from app.models.core import AssetStatus, AssetType  # noqa: E402

KNOWN_ASSETS = [
    ("tmp/seedream_assets/bg_paper_light_01_1920x1080.png", "bg:paper:light", AssetType.BACKGROUND, "paper_light"),
    ("tmp/seedream_assets/bg_wood_floor_02_1920x1080.png", "bg:floor:wood", AssetType.BACKGROUND, "wood_floor"),
    ("tmp/seedream_assets/bg_wood_table_01_1920x1080.png", "bg:wood:table", AssetType.BACKGROUND, "wood_table"),
]
KNOWN_STEMS = {
    "bg_paper_light_01",
    "bg_paper_light_01_1920x1080",
    "bg_wood_floor_02",
    "bg_wood_floor_02_1920x1080",
    "bg_wood_table_01",
    "bg_wood_table_01_1920x1080",
}


def sidecar(path: Path) -> dict:
    meta_path = Path(str(path) + ".json")
    if not meta_path.exists():
        return {}
    try:
        return json.loads(meta_path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return {}


async def ingest_seedream(session: AsyncSession, status: AssetStatus) -> int:
    ingested = 0
    for relative, reuse_key, asset_type, name in KNOWN_ASSETS:
        path = ROOT / relative
        if not path.exists():
            continue
        meta = sidecar(path)
        await ingest_asset(
            session,
            path,
            asset_type=asset_type,
            name=name,
            reuse_key=reuse_key,
            source="seedream",
            status=status,
            provider="volcengine",
            model=meta.get("model"),
            prompt=meta.get("prompt"),
            reference=meta.get("reference"),
            tags=["generated", "seedream"],
            meta=meta,
        )
        ingested += 1

    extras = []
    extras.extend(sorted((ROOT / "tmp/seedream_assets").glob("*.png")))
    extras.extend(sorted((ROOT / "tmp/seedream_assets/props").glob("*.png")))
    for path in extras:
        if path.stem in KNOWN_STEMS:
            continue
        prefix = "prop:" if path.stem.startswith("prop_") else "bg:"
        reuse_key = prefix + path.stem
        asset_type = AssetType.PROP if prefix == "prop:" else AssetType.BACKGROUND
        meta = sidecar(path)
        await ingest_asset(
            session,
            path,
            asset_type=asset_type,
            name=path.stem,
            reuse_key=reuse_key,
            source="seedream",
            status=status,
            provider="volcengine",
            model=meta.get("model"),
            prompt=meta.get("prompt"),
            reference=meta.get("reference"),
            tags=["generated", "seedream"],
            meta=meta,
        )
        ingested += 1
    return ingested


async def ingest_character_pack(
    session: AsyncSession, pack: str, status: AssetStatus
) -> int:
    manifest_path = ROOT / "character_packs" / pack / "manifest.json"
    if not manifest_path.exists():
        return 0
    data = json.loads(manifest_path.read_text(encoding="utf-8"))
    count = 0
    for item in data.get("assets", []):
        file_name = item.get("file")
        if not file_name:
            continue
        path = ROOT / "character_packs" / pack / file_name
        if not path.exists():
            continue
        await ingest_asset(
            session,
            path,
            asset_type=AssetType.CHARACTER,
            name=item.get("id") or path.stem,
            reuse_key=f"character:{pack}:{item.get('id') or path.stem}",
            source=item.get("source", "doubao" if pack == "roxy" else "placeholder"),
            status=status,
            copy=False,
            tags=[pack, item.get("expression", ""), item.get("pose", "")],
            meta=item,
        )
        count += 1
    return count


async def main_async(args) -> None:
    settings = get_settings()
    engine = create_async_engine(settings.database_url, poolclass=NullPool)
    if settings.database_url.startswith("sqlite"):
        async with engine.begin() as connection:
            await connection.run_sync(Base.metadata.create_all)
    factory = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    status = AssetStatus(args.status.upper())
    async with factory() as session:
        seedream = await ingest_seedream(session, status)
        characters = 0
        for pack in args.packs:
            characters += await ingest_character_pack(session, pack, status)
        await session.commit()
        print(
            f"assets ingested: seedream={seedream} characters={characters} "
            f"status={status.value}"
        )
    await engine.dispose()


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--status",
        choices=["approved", "candidate"],
        default="approved",
        help="new asset rows start as this status",
    )
    parser.add_argument(
        "--packs",
        nargs="*",
        default=["roxy", "placeholder"],
        help="character packs to index in place",
    )
    args = parser.parse_args()
    asyncio.run(main_async(args))


if __name__ == "__main__":
    main()

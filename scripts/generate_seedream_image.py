#!/usr/bin/env python3
"""Generate a single image with Volcengine Seedream and save it locally.

Usage:
    python scripts/generate_seedream_image.py \
        --prompt "warm off-white paper texture, no text" \
        --out tmp/seedream_assets/bg_paper_01.png \
        --size 1920x1088

Optional:
    --reference path/to/image.png   # image-to-image reference
    --model <model id>              # default from ARK_IMAGE_MODEL
"""

from __future__ import annotations

import argparse
import asyncio
import base64
import hashlib
import json
import mimetypes
import sys
import urllib.error
import urllib.request
from pathlib import Path

from PIL import Image

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))


def load_env(path: Path) -> dict[str, str]:
    env: dict[str, str] = {}
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if line and not line.startswith("#") and "=" in line:
            key, value = line.split("=", 1)
            env[key.strip()] = value.strip().strip('"').strip("'")
    return env


def data_uri(path: Path) -> str:
    mime = mimetypes.guess_type(path.name)[0] or "application/octet-stream"
    return f"data:{mime};base64," + base64.b64encode(path.read_bytes()).decode()


def auto_reuse_key(prompt: str, size: str, model: str, reference: Path | None) -> str:
    raw = json.dumps(
        {
            "prompt": prompt,
            "size": size,
            "model": model,
            "reference": str(reference) if reference else None,
        },
        ensure_ascii=False,
        sort_keys=True,
    )
    return "auto:" + hashlib.sha256(raw.encode("utf-8")).hexdigest()


async def find_existing(reuse_key: str) -> str | None:
    try:
        from app.assets.store import find_reusable, PROJECT_ROOT
        from app.db.session import SessionLocal

        async with SessionLocal() as session:
            asset = await find_reusable(session, reuse_key)
            if asset is None:
                return None
            return (PROJECT_ROOT / asset.path).as_posix()
    except Exception as exc:  # DB not migrated / not running: still allow generation
        print(f"asset lookup skipped: {exc}")
        return None


async def ingest_generated(
    path: Path,
    *,
    asset_type: str,
    name: str,
    reuse_key: str,
    status: str,
    model: str,
    prompt: str,
    reference: Path | None,
    meta: dict,
) -> str:
    from app.assets.store import ingest_asset
    from app.db.session import SessionLocal
    from app.models.core import AssetStatus, AssetType

    async with SessionLocal() as session:
        asset = await ingest_asset(
            session,
            path,
            asset_type=AssetType(asset_type),
            name=name,
            reuse_key=reuse_key,
            source="seedream",
            status=AssetStatus(status.upper()),
            provider="volcengine",
            model=model,
            prompt=prompt,
            reference=str(reference) if reference else None,
            tags=["generated", "seedream"],
            meta=meta,
        )
        await session.commit()
        return asset.path


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--prompt", required=True)
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--size", default="1920x1088")
    parser.add_argument("--model", default=None)
    parser.add_argument("--reference", type=Path, default=None)
    parser.add_argument("--env", type=Path, default=ROOT / ".env")
    parser.add_argument(
        "--reuse-key",
        default=None,
        help="stable key; if an APPROVED asset exists, reuse it without calling the API",
    )
    parser.add_argument(
        "--asset-type",
        choices=["background", "prop", "icon", "cover", "character"],
        default=None,
    )
    parser.add_argument("--asset-name", default=None)
    parser.add_argument(
        "--status",
        choices=["candidate", "approved"],
        default="candidate",
    )
    parser.add_argument("--force", action="store_true", help="ignore an existing asset")
    parser.add_argument("--no-ingest", action="store_true")
    args = parser.parse_args()

    env = load_env(args.env)
    model = args.model or env.get("ARK_IMAGE_MODEL", "doubao-seedream-5-0-pro-260628")
    base = env.get("ARK_BASE_URL", "https://ark.cn-beijing.volces.com/api/v3").rstrip("/")
    key = env["ARK_API_KEY"]

    reuse_key = args.reuse_key or auto_reuse_key(
        args.prompt, args.size, model, args.reference
    )
    if not args.force:
        existing = asyncio.run(find_existing(reuse_key))
        if existing:
            print(f"reused {reuse_key}: {existing}")
            return

    body: dict = {
        "model": model,
        "prompt": args.prompt,
        "size": args.size,
        "output_format": "png",
        "response_format": "url",
        "watermark": False,
    }
    if args.reference:
        body["image"] = data_uri(args.reference)

    req = urllib.request.Request(
        f"{base}/images/generations",
        data=json.dumps(body).encode(),
        headers={"Authorization": f"Bearer {key}", "Content-Type": "application/json"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=240) as resp:
            payload = json.loads(resp.read().decode("utf-8", "replace"))
    except urllib.error.HTTPError as exc:
        raw = exc.read().decode("utf-8", "replace")
        try:
            err = json.loads(raw).get("error", {})
            raise SystemExit(f"HTTP {exc.code} {err.get('code')}: {err.get('message', '')}")
        except json.JSONDecodeError:
            raise SystemExit(f"HTTP {exc.code}: {raw[:500]}")

    item = (payload.get("data") or [{}])[0]
    url, b64 = item.get("url"), item.get("b64_json")
    args.out.parent.mkdir(parents=True, exist_ok=True)
    if url:
        with urllib.request.urlopen(url, timeout=240) as resp:
            args.out.write_bytes(resp.read())
    elif b64:
        args.out.write_bytes(base64.b64decode(b64))
    else:
        raise SystemExit(f"no image in response: {json.dumps(item, ensure_ascii=False)[:400]}")

    with Image.open(args.out) as im:
        print(f"saved {args.out} {im.size} {im.mode}")

    meta = {
        "model": model,
        "prompt": args.prompt,
        "size": args.size,
        "reference": str(args.reference) if args.reference else None,
        "source": "volcengine-seedream",
    }
    args.out.with_suffix(args.out.suffix + ".json").write_text(
        json.dumps(meta, ensure_ascii=False, indent=2), encoding="utf-8"
    )

    asset_type = args.asset_type
    if asset_type is None:
        if args.out.stem.startswith("bg_"):
            asset_type = "background"
        elif args.out.stem.startswith("prop_"):
            asset_type = "prop"
    if not args.no_ingest and asset_type:
        try:
            stored = asyncio.run(
                ingest_generated(
                    args.out,
                    asset_type=asset_type,
                    name=args.asset_name or args.out.stem,
                    reuse_key=reuse_key,
                    status=args.status,
                    model=model,
                    prompt=args.prompt,
                    reference=args.reference,
                    meta=meta,
                )
            )
            print(f"ingested {reuse_key}: {stored}")
        except Exception as exc:  # DB not migrated / not running
            print(f"asset ingest skipped: {exc}")
    elif not args.no_ingest:
        print("asset ingest skipped: pass --asset-type for this filename")


if __name__ == "__main__":
    main()

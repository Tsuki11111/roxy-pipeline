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
import base64
import json
import mimetypes
import urllib.error
import urllib.request
from pathlib import Path

from PIL import Image

ROOT = Path(__file__).resolve().parents[1]


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


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--prompt", required=True)
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--size", default="1920x1088")
    parser.add_argument("--model", default=None)
    parser.add_argument("--reference", type=Path, default=None)
    parser.add_argument("--env", type=Path, default=ROOT / ".env")
    args = parser.parse_args()

    env = load_env(args.env)
    model = args.model or env.get("ARK_IMAGE_MODEL", "doubao-seedream-5-0-pro-260628")
    base = env.get("ARK_BASE_URL", "https://ark.cn-beijing.volces.com/api/v3").rstrip("/")
    key = env["ARK_API_KEY"]

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


if __name__ == "__main__":
    main()

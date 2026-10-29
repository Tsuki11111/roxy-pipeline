from __future__ import annotations

import base64
import json
from pathlib import Path
from typing import Protocol

import httpx
from PIL import Image, ImageDraw

from app.core.config import get_settings


class ImageGenError(RuntimeError):
    pass


class ImageProvider(Protocol):
    async def generate(self, prompt: str, out_path: Path, size: str) -> Path:
        ...


class SeedreamProvider:
    def __init__(self) -> None:
        settings = get_settings()
        self.api_key = settings.ark_api_key
        self.base_url = settings.ark_base_url.rstrip("/")
        self.model = settings.ark_image_model
        self.timeout_s = 240.0

    async def generate(self, prompt: str, out_path: Path, size: str) -> Path:
        if not self.api_key:
            raise ImageGenError("ARK_API_KEY 未配置")
        body = {
            "model": self.model,
            "prompt": prompt,
            "size": size,
            "output_format": "png",
            "response_format": "url",
            "watermark": False,
        }
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }
        async with httpx.AsyncClient(timeout=self.timeout_s) as client:
            response = await client.post(
                f"{self.base_url}/images/generations", headers=headers, json=body
            )
            if response.status_code >= 400:
                raise ImageGenError(
                    f"Seedream HTTP {response.status_code}: {response.text[:500]}"
                )
            payload = response.json()
            item = (payload.get("data") or [{}])[0]
            out_path.parent.mkdir(parents=True, exist_ok=True)
            if item.get("url"):
                image_response = await client.get(item["url"])
                if image_response.status_code >= 400:
                    raise ImageGenError(
                        f"image download HTTP {image_response.status_code}"
                    )
                out_path.write_bytes(image_response.content)
            elif item.get("b64_json"):
                out_path.write_bytes(base64.b64decode(item["b64_json"]))
            else:
                raise ImageGenError(
                    "Seedream returned no image: "
                    + json.dumps(item, ensure_ascii=False)[:400]
                )
        with Image.open(out_path) as image:
            image.verify()
        return out_path


class MockImageProvider:
    """Deterministic local placeholder used when IMAGE_PROVIDER=mock."""

    async def generate(self, prompt: str, out_path: Path, size: str) -> Path:
        try:
            width, height = (int(part) for part in size.lower().split("x", 1))
        except ValueError as exc:
            raise ImageGenError(f"invalid size: {size}") from exc
        out_path.parent.mkdir(parents=True, exist_ok=True)
        image = Image.new("RGB", (width, height), (232, 224, 206))
        draw = ImageDraw.Draw(image)
        draw.ellipse(
            (width * 0.25, height * 0.25, width * 0.75, height * 0.75),
            fill=(180, 150, 110),
            outline=(60, 50, 40),
            width=max(2, width // 200),
        )
        image.save(out_path, format="PNG")
        return out_path


def build_image_provider() -> ImageProvider:
    settings = get_settings()
    if settings.image_provider == "mock":
        return MockImageProvider()
    if settings.image_provider == "ark":
        return SeedreamProvider()
    raise ImageGenError(f"unsupported IMAGE_PROVIDER: {settings.image_provider}")

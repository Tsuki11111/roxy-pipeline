from __future__ import annotations

import asyncio
import base64
import io
import json
import logging
import re
import time
from pathlib import Path
from typing import Protocol

import httpx
from json_repair import repair_json
from PIL import Image

from app.core.config import get_settings

logger = logging.getLogger(__name__)


class LLMError(RuntimeError):
    pass


class LLMClient(Protocol):
    async def chat_json(
        self,
        system: str,
        user: str,
        *,
        temperature: float = 0.7,
        max_tokens: int = 2000,
    ) -> dict:
        ...

    async def chat_vision_json(
        self,
        system: str,
        user: str,
        image_paths: list[Path],
        *,
        temperature: float = 0.1,
        max_tokens: int = 2000,
        timeout_s: float | None = None,
    ) -> dict:
        ...


def extract_json(content: str) -> dict:
    text = content.strip()
    if text.startswith("```"):
        text = re.sub(r"^```(?:json)?\s*", "", text)
        text = re.sub(r"\s*```$", "", text)

    candidate = text
    start = text.find("{")
    end = text.rfind("}")
    if start >= 0 and end > start:
        candidate = text[start : end + 1]

    try:
        value = json.loads(candidate)
    except json.JSONDecodeError:
        value = repair_json(candidate, return_objects=True)

    if not isinstance(value, dict):
        raise ValueError("LLM response is not a JSON object")
    return value


def image_data_url(path: Path, max_side: int = 1280) -> str:
    with Image.open(path) as image:
        image = image.convert("RGB")
        image.thumbnail((max_side, max_side))
        buffer = io.BytesIO()
        image.save(buffer, format="JPEG", quality=85)
    encoded = base64.b64encode(buffer.getvalue()).decode("ascii")
    return f"data:image/jpeg;base64,{encoded}"


class DeepSeekClient:
    def __init__(
        self,
        api_key: str | None = None,
        base_url: str | None = None,
        model: str | None = None,
        timeout_s: float | None = None,
    ):
        settings = get_settings()
        self.api_key = api_key or settings.deepseek_api_key
        self.base_url = (base_url or settings.deepseek_base_url).rstrip("/")
        self.model = model or settings.deepseek_model
        self.timeout_s = timeout_s or settings.llm_timeout_s

    async def chat_json(
        self,
        system: str,
        user: str,
        *,
        temperature: float = 0.7,
        max_tokens: int = 2000,
    ) -> dict:
        if not self.api_key:
            raise LLMError("DEEPSEEK_API_KEY 未配置")
        if self.model != "deepseek-flash":
            raise LLMError(f"only deepseek-flash is enabled, got {self.model}")

        url = f"{self.base_url}/chat/completions"
        payload = {
            "model": self.model,
            "messages": [
                {"role": "system", "content": system},
                {"role": "user", "content": user},
            ],
            "temperature": temperature,
            "max_tokens": max_tokens,
            "response_format": {"type": "json_object"},
            "stream": False,
        }
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }

        last_error: Exception | None = None
        for attempt in range(3):
            started = time.perf_counter()
            try:
                async with httpx.AsyncClient(timeout=self.timeout_s) as client:
                    response = await client.post(url, headers=headers, json=payload)
            except httpx.TransportError as exc:
                last_error = exc
                if attempt == 2:
                    break
                await asyncio.sleep(2**attempt)
                continue

            if response.status_code in {401, 403}:
                raise LLMError(
                    f"DeepSeek auth failed ({response.status_code}); check DEEPSEEK_API_KEY"
                )
            if response.status_code == 429 or response.status_code >= 500:
                last_error = LLMError(
                    f"DeepSeek HTTP {response.status_code}: {response.text[:300]}"
                )
                if attempt == 2:
                    break
                await asyncio.sleep(2**attempt)
                continue
            if response.status_code >= 400:
                raise LLMError(
                    f"DeepSeek HTTP {response.status_code}: {response.text[:500]}"
                )

            data = response.json()
            try:
                content = data["choices"][0]["message"]["content"]
                result = extract_json(content)
            except Exception as exc:
                last_error = exc
                logger.warning(
                    "LLM returned invalid JSON (attempt %d): %s",
                    attempt + 1,
                    content[:500],
                )
                if attempt == 2:
                    break
                await asyncio.sleep(1)
                continue

            usage = data.get("usage") or {}
            logger.info(
                "llm model=%s latency_ms=%d prompt_tokens=%s completion_tokens=%s",
                self.model,
                (time.perf_counter() - started) * 1000,
                usage.get("prompt_tokens"),
                usage.get("completion_tokens"),
            )
            return result

        raise LLMError(f"DeepSeek call failed after retries: {last_error}")

    async def chat_vision_json(
        self,
        system: str,
        user: str,
        image_paths: list[Path],
        *,
        temperature: float = 0.1,
        max_tokens: int = 2000,
        timeout_s: float | None = None,
    ) -> dict:
        if not self.api_key:
            raise LLMError("DEEPSEEK_API_KEY 未配置")
        if not image_paths:
            raise LLMError("chat_vision_json requires at least one image")
        content: list[dict] = [{"type": "text", "text": user}]
        for path in image_paths:
            if not path.is_file():
                raise LLMError(f"image not found: {path}")
            content.append(
                {
                    "type": "image_url",
                    "image_url": {"url": image_data_url(path)},
                }
            )
        payload = {
            "model": self.model,
            "messages": [
                {"role": "system", "content": system},
                {"role": "user", "content": content},
            ],
            "temperature": temperature,
            "max_tokens": max_tokens,
            "response_format": {"type": "json_object"},
            "stream": False,
        }
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }
        timeout = timeout_s or self.timeout_s
        last_error: Exception | None = None
        for attempt in range(3):
            started = time.perf_counter()
            try:
                async with httpx.AsyncClient(timeout=timeout) as client:
                    response = await client.post(
                        f"{self.base_url}/chat/completions",
                        headers=headers,
                        json=payload,
                    )
            except httpx.TransportError as exc:
                last_error = exc
                if attempt == 2:
                    break
                await asyncio.sleep(2**attempt)
                continue

            if response.status_code in {401, 403}:
                raise LLMError(
                    f"DeepSeek auth failed ({response.status_code}); check DEEPSEEK_API_KEY"
                )
            if response.status_code == 429 or response.status_code >= 500:
                last_error = LLMError(
                    f"DeepSeek vision HTTP {response.status_code}: {response.text[:300]}"
                )
                if attempt == 2:
                    break
                await asyncio.sleep(2**attempt)
                continue
            if response.status_code >= 400:
                raise LLMError(
                    f"DeepSeek vision HTTP {response.status_code}: {response.text[:500]}"
                )

            data = response.json()
            try:
                message = data["choices"][0]["message"]
                result = extract_json(message["content"])
            except Exception as exc:
                last_error = exc
                logger.warning(
                    "DeepSeek vision returned invalid JSON (attempt %d): %s",
                    attempt + 1,
                    str(data)[:500],
                )
                if attempt == 2:
                    break
                await asyncio.sleep(1)
                continue

            usage = data.get("usage") or {}
            logger.info(
                "llm-vision model=%s images=%d latency_ms=%d "
                "prompt_tokens=%s completion_tokens=%s",
                self.model,
                len(image_paths),
                (time.perf_counter() - started) * 1000,
                usage.get("prompt_tokens"),
                usage.get("completion_tokens"),
            )
            return result

        raise LLMError(f"DeepSeek vision call failed after retries: {last_error}")


def build_llm() -> LLMClient:
    settings = get_settings()
    if settings.llm_provider != "deepseek":
        raise LLMError(f"unsupported LLM_PROVIDER: {settings.llm_provider}")
    return DeepSeekClient()

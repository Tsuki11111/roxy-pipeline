from __future__ import annotations

import asyncio
import json
import logging
import re
import time
from typing import Protocol

import httpx

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


def extract_json(content: str) -> dict:
    text = content.strip()
    if text.startswith("```"):
        text = re.sub(r"^```(?:json)?\s*", "", text)
        text = re.sub(r"\s*```$", "", text)
    try:
        value = json.loads(text)
    except json.JSONDecodeError:
        start = text.find("{")
        end = text.rfind("}")
        if start < 0 or end <= start:
            raise
        value = json.loads(text[start : end + 1])
    if not isinstance(value, dict):
        raise ValueError("LLM response is not a JSON object")
    return value


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


def build_llm() -> LLMClient:
    settings = get_settings()
    if settings.llm_provider != "deepseek":
        raise LLMError(f"unsupported LLM_PROVIDER: {settings.llm_provider}")
    return DeepSeekClient()

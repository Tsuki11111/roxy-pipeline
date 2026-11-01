from __future__ import annotations

from functools import lru_cache
from pathlib import Path
from string import Template

PROMPTS_DIR = Path(__file__).resolve().parents[3] / "prompts" / "asset"


@lru_cache(maxsize=8)
def _read(name: str) -> str:
    return (PROMPTS_DIR / name).read_text(encoding="utf-8")


def load_system_prompt() -> str:
    return _read("system.md")


def build_user_prompt(
    text: str,
    *,
    asset_type: str | None,
    count: int,
    existing: list[dict],
) -> str:
    forced = f"优先类型：{asset_type}" if asset_type else "类型由你判断"
    assets = "\n".join(
        f"- {item['reuse_key']} | {item['type']} | {item['name']} | {item['prompt']}"
        for item in existing
    ) or "（暂无已入库素材）"
    return Template(_read("generate.md")).substitute(
        text=text,
        count=count,
        forced=forced,
        assets=assets,
    )
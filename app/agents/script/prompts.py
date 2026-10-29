from __future__ import annotations

from functools import lru_cache
from pathlib import Path
from string import Template

PROMPTS_DIR = Path(__file__).resolve().parents[3] / "prompts" / "script"


@lru_cache(maxsize=16)
def _read(name: str) -> str:
    return (PROMPTS_DIR / name).read_text(encoding="utf-8")


def load_system_prompt() -> str:
    return _read("system.md")


def load_prompt(name: str, **values: object) -> str:
    return Template(_read(name)).substitute(values)

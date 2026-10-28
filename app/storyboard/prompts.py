from __future__ import annotations

import hashlib
from functools import lru_cache
from pathlib import Path
from string import Template

PROMPTS_DIR = Path(__file__).resolve().parents[2] / "prompts" / "storyboard"
STORYBOARD_GRAPH_VERSION = "storyboard-graph-1"


@lru_cache(maxsize=8)
def _read(name: str) -> str:
    return (PROMPTS_DIR / name).read_text(encoding="utf-8")


def load_system_prompt() -> str:
    return _read("system.md")


def load_prompt(name: str, **values: object) -> str:
    return Template(_read(name)).substitute(values)


def prompt_hash() -> str:
    digest = hashlib.sha256()
    for path in sorted(PROMPTS_DIR.glob("*.md")):
        digest.update(path.name.encode("utf-8"))
        digest.update(path.read_bytes())
    return digest.hexdigest()

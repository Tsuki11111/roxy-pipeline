from __future__ import annotations

import hashlib
from functools import lru_cache
from pathlib import Path
from string import Template

PROMPTS_DIR = Path(__file__).resolve().parents[3] / "prompts" / "remotion"
SKILL_PATH = (
    Path(__file__).resolve().parent / "skills" / "remotion_shot" / "SKILL.md"
)


@lru_cache(maxsize=8)
def _read(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def load_skill() -> str:
    return _read(SKILL_PATH)


def load_system_prompt() -> str:
    return _read(PROMPTS_DIR / "system.md") + "\n\n" + load_skill()


def load_prompt(name: str, **values: object) -> str:
    return Template(_read(PROMPTS_DIR / name)).substitute(values)


def prompt_hash() -> str:
    digest = hashlib.sha256()
    for path in sorted(PROMPTS_DIR.glob("*.md")):
        digest.update(path.name.encode("utf-8"))
        digest.update(path.read_bytes())
    digest.update(SKILL_PATH.name.encode("utf-8"))
    digest.update(SKILL_PATH.read_bytes())
    return digest.hexdigest()

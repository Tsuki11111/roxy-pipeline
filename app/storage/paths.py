"""项目根目录与路径解析。"""

from __future__ import annotations

from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[2]


def resolve_project_path(value: str | Path) -> Path:
    path = Path(value).expanduser()
    return path if path.is_absolute() else (PROJECT_ROOT / path).resolve()


def relative_project_path(path: Path) -> str:
    resolved = path.resolve()
    if not resolved.is_relative_to(PROJECT_ROOT):
        raise ValueError(f"path escapes project root: {path}")
    return resolved.relative_to(PROJECT_ROOT).as_posix()
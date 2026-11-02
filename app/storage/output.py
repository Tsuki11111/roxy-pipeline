"""成片输出到时间戳目录。"""

from __future__ import annotations

import json
import logging
import re
import shutil
from datetime import datetime, timezone
from pathlib import Path

from app.core.config import get_settings

logger = logging.getLogger(__name__)
PROJECT_ROOT = Path(__file__).resolve().parents[2]
_OUTPUT_DIR_RE = re.compile(r"^\d{8}-\d{6}_([0-9a-f]{8})(?:-\d{6})?$")


def _resolve(value: str) -> Path:
    path = Path(value).expanduser()
    return path if path.is_absolute() else (PROJECT_ROOT / path).resolve()


def prune_episode_outputs(
    episode_id: str,
    current_path: str | Path,
    *,
    keep: int | None = None,
) -> list[str]:
    """Delete superseded timestamped output directories for one episode."""
    settings = get_settings()
    root = _resolve(settings.output_root)
    current = Path(current_path).expanduser()
    if not current.is_absolute():
        current = (PROJECT_ROOT / current).resolve()
    else:
        current = current.resolve()
    if not current.is_relative_to(root):
        return []

    prefix = episode_id[:8]
    candidates: list[Path] = []
    if root.is_dir():
        for child in root.iterdir():
            if not child.is_dir() or not (child / "episode.mp4").is_file():
                continue
            match = _OUTPUT_DIR_RE.match(child.name)
            if match is None or match.group(1) != prefix:
                continue
            candidates.append(child.resolve())
    candidates.sort(key=lambda path: path.name, reverse=True)
    keep_count = max(1, int(settings.output_keep_versions if keep is None else keep))
    kept: list[Path] = []
    if current.parent in candidates:
        kept.append(current.parent)
    for child in candidates:
        if len(kept) >= keep_count:
            break
        if child not in kept:
            kept.append(child)

    deleted: list[str] = []
    for child in candidates:
        if child in kept:
            continue
        try:
            shutil.rmtree(child)
            deleted.append(child.name)
        except OSError:
            logger.exception("failed to prune output directory %s", child)
    if deleted:
        logger.info("pruned superseded outputs episode=%s dirs=%s", episode_id, deleted)
    return deleted


def export_episode_video(
    source: Path,
    episode_id: str,
    *,
    title: str = "",
) -> dict:
    settings = get_settings()
    root = _resolve(settings.output_root)
    stamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    out_dir = root / f"{stamp}_{episode_id[:8]}"
    if out_dir.exists():
        out_dir = root / f"{stamp}_{episode_id[:8]}-{datetime.now().microsecond:06d}"
    out_dir.mkdir(parents=True, exist_ok=True)
    final = out_dir / "episode.mp4"
    shutil.copy2(source, final)

    meta = {
        "episode_id": episode_id,
        "title": title,
        "exported_at": datetime.now(timezone.utc).isoformat(),
        "local_path": str(final),
        "relative_path": (
            final.relative_to(PROJECT_ROOT).as_posix()
            if final.is_relative_to(PROJECT_ROOT)
            else str(final)
        ),
    }

    (out_dir / "metadata.json").write_text(
        json.dumps(meta, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    return {"path": str(final), "meta": meta}

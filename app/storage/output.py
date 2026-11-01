from __future__ import annotations

import json
import shutil
from datetime import datetime, timezone
from pathlib import Path

from app.core.config import get_settings

PROJECT_ROOT = Path(__file__).resolve().parents[2]


def _resolve(value: str) -> Path:
    path = Path(value).expanduser()
    return path if path.is_absolute() else (PROJECT_ROOT / path).resolve()


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

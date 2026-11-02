"""临时产物清理：只删除可重建、且已过保留期的中间目录。"""

from __future__ import annotations

import logging
import shutil
from datetime import datetime, timezone
from pathlib import Path

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.models.core import Episode, EpisodeStatus
from app.storage.output import prune_episode_outputs
from app.storage.paths import PROJECT_ROOT

logger = logging.getLogger(__name__)

ACTIVE_STATUSES = {
    EpisodeStatus.SCRIPTING,
    EpisodeStatus.STORYBOARDING,
    EpisodeStatus.VOICING,
    EpisodeStatus.ALIGNING,
    EpisodeStatus.RENDERING,
    EpisodeStatus.QC,
}


def _resolve(value: str) -> Path:
    path = Path(value).expanduser()
    return path if path.is_absolute() else (PROJECT_ROOT / path).resolve()


async def cleanup_temp_dirs(
    session: AsyncSession,
    *,
    now: datetime | None = None,
    dry_run: bool = False,
) -> dict[str, list[str]]:
    settings = get_settings()
    now = now or datetime.now(timezone.utc)
    roots = (
        ("remotion", _resolve(settings.remotion_work_root), settings.tmp_remotion_retention_days),
        ("renders", _resolve(settings.render_dir), settings.tmp_renders_retention_days),
        ("qc", PROJECT_ROOT / "tmp" / "qc", settings.tmp_qc_retention_days),
    )
    episodes = {
        row.id: row
        for row in await session.scalars(select(Episode))
    }
    deleted: list[str] = []
    skipped: list[str] = []
    for label, root, retention_days in roots:
        if not root.is_dir():
            continue
        for child in root.iterdir():
            if not child.is_dir() or child.is_symlink():
                continue
            episode = episodes.get(child.name)
            if episode is not None and (
                episode.status in ACTIVE_STATUSES or episode.current_node
            ):
                skipped.append(f"{label}:{child.name}:active")
                continue
            age_days = (now.timestamp() - child.stat().st_mtime) / 86400
            if age_days < retention_days:
                skipped.append(f"{label}:{child.name}:young")
                continue
            target = f"{label}:{child.name}"
            if dry_run:
                deleted.append(target)
                continue
            try:
                shutil.rmtree(child)
                deleted.append(target)
            except OSError:
                logger.exception("failed to clean temp directory %s", child)
                skipped.append(f"{target}:error")
    for episode in episodes.values():
        if episode.status not in {EpisodeStatus.READY, EpisodeStatus.PUBLISHED}:
            continue
        if episode.current_node or not episode.output_path:
            continue
        try:
            removed = prune_episode_outputs(episode.id, episode.output_path)
            deleted.extend(f"output:{name}" for name in removed)
        except Exception:
            logger.exception("failed to prune outputs for episode=%s", episode.id)
            skipped.append(f"output:{episode.id}:error")
    if deleted:
        logger.info(
            "temp cleanup dry_run=%s deleted=%s", dry_run, ", ".join(deleted)
        )
    return {"deleted": deleted, "skipped": skipped}
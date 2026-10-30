from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.agents.script.validation import (
    DEFAULT_SECTION_LABELS,
    ValidationResult,
    coerce_lines,
    validate_script,
)
from app.core.config import get_settings
from app.models.core import Episode, ScriptLine, Series


async def load_lines(
    session: AsyncSession, episode_id: str
) -> list[ScriptLine]:
    result = await session.scalars(
        select(ScriptLine)
        .where(ScriptLine.episode_id == episode_id)
        .order_by(ScriptLine.seq)
    )
    return list(result)


async def load_series(
    session: AsyncSession, episode: Episode
) -> Series | None:
    return await session.get(Series, episode.series_id)


def section_labels_for(series: Series | None) -> list[str]:
    if series is not None and series.section_labels:
        return list(series.section_labels)
    return list(DEFAULT_SECTION_LABELS)


def validate_episode(
    episode: Episode,
    series: Series | None,
    lines: list[ScriptLine],
) -> ValidationResult:
    settings = get_settings()
    return validate_script(
        coerce_lines(lines),
        target_duration_s=episode.target_duration_s,
        section_labels=section_labels_for(series),
        target_chars_per_minute=settings.script_target_chars_per_minute,
    )


def store_validation(episode: Episode, validation: ValidationResult) -> None:
    meta = dict(episode.script_meta or {})
    meta["validation"] = validation.model_dump()
    episode.script_meta = meta
    episode.health = "OK" if validation.valid else "WARNING"

from __future__ import annotations

import json
from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.agents.script.prompts import load_prompt, load_system_prompt
from app.agents.script.utils import section_labels_for
from app.agents.script.validation import (
    ScriptLineData,
    ValidationResult,
    coerce_lines,
    validate_script,
)
from app.core.config import get_settings
from app.models.core import Episode, EpisodeStatus, ScriptLine, Series
from app.providers.llm import LLMClient, build_llm


class ScriptOptimizeError(Exception):
    pass


class ScriptOptimizeConflict(ScriptOptimizeError):
    pass


class ScriptOptimizeInvalid(ScriptOptimizeError):
    def __init__(self, validation: ValidationResult):
        self.validation = validation
        super().__init__(
            "optimized script validation failed: " + "; ".join(validation.errors)
        )


def _validate(
    lines: list[ScriptLineData],
    episode: Episode,
    series: Series | None,
    settings,
) -> ValidationResult:
    return validate_script(
        lines,
        target_duration_s=episode.target_duration_s,
        section_labels=section_labels_for(series),
        target_chars_per_minute=settings.script_target_chars_per_minute,
    )


async def optimize_script(
    session: AsyncSession,
    episode_id: str,
    *,
    llm: LLMClient | None = None,
    apply: bool = True,
    instructions: str = "",
) -> dict:
    settings = get_settings()
    episode = await session.get(Episode, episode_id, with_for_update=True)
    if episode is None:
        raise LookupError(f"episode not found: {episode_id}")
    if episode.status != EpisodeStatus.SCRIPT_REVIEW:
        raise ScriptOptimizeConflict(
            f"episode status {episode.status.value} is not SCRIPT_REVIEW"
        )

    lines = list(
        await session.scalars(
            select(ScriptLine)
            .where(ScriptLine.episode_id == episode_id)
            .order_by(ScriptLine.seq)
        )
    )
    if not lines:
        raise ScriptOptimizeError("episode has no script lines")
    series = await session.get(Series, episode.series_id)

    prompt = load_prompt(
        "optimize.md",
    ) + (
        "\n\n原始文稿：\n"
        + json.dumps(
            [
                {
                    "seq": line.seq,
                    "section": line.section,
                    "speaker": line.speaker,
                    "text": line.text,
                }
                for line in lines
            ],
            ensure_ascii=False,
            indent=2,
        )
        + f"\n\n额外要求：{instructions.strip() or '无'}"
    )
    raw = await (llm or build_llm()).chat_json(
        load_system_prompt(),
        prompt,
        temperature=0.55,
        max_tokens=max(1600, len(lines) * 120),
    )
    raw_lines = raw.get("lines")
    if not isinstance(raw_lines, list):
        raise ScriptOptimizeError("optimizer returned no lines list")

    rewritten: dict[int, str] = {}
    for item in raw_lines:
        if not isinstance(item, dict):
            continue
        try:
            seq = int(item.get("seq"))
        except (TypeError, ValueError):
            continue
        text = str(item.get("text", "")).strip()
        if text:
            rewritten[seq] = text

    result_lines: list[ScriptLineData] = []
    changed = 0
    for line in lines:
        text = rewritten.get(line.seq, line.text).strip() or line.text
        if text != line.text:
            changed += 1
        result_lines.append(
            ScriptLineData(
                seq=line.seq,
                section=line.section,
                speaker=line.speaker,
                text=text,
                char_count=len(text),
            )
        )

    validation = _validate(result_lines, episode, series, settings)
    if not validation.valid:
        raise ScriptOptimizeInvalid(validation)

    if apply:
        by_seq = {item.seq: item for item in result_lines}
        for line in lines:
            item = by_seq[line.seq]
            if item.text != line.text:
                line.text = item.text
                line.char_count = item.char_count
                line.version += 1
        meta = dict(episode.script_meta or {})
        meta["optimization"] = {
            "applied_at": datetime.now(timezone.utc).isoformat(),
            "model": settings.deepseek_model,
            "changed_count": changed,
            "instructions": instructions,
            "validation": validation.model_dump(),
        }
        meta["validation"] = validation.model_dump()
        episode.script_meta = meta
        episode.version += 1
        episode.health = "OK"

    return {
        "episode_id": episode.id,
        "applied": apply,
        "changed_count": changed,
        "lines": [item.model_dump() for item in result_lines],
        "validation": validation.model_dump(),
    }

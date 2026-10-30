from __future__ import annotations

import json
from datetime import datetime, timezone

from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.agents.script.optimizer import optimize_script
from app.agents.script.prompts import load_prompt, load_system_prompt
from app.agents.script.utils import (
    load_lines,
    section_labels_for,
    validate_episode,
)
from app.agents.script.validation import (
    ScriptLineData,
    ValidationResult,
    target_chars_for_duration,
    validate_script,
)
from app.core.config import get_settings
from app.models.core import Episode, EpisodeStatus, ScriptLine, Series
from app.providers.llm import LLMClient, build_llm


class ArticleImportError(Exception):
    pass


class ArticleImportConflict(ArticleImportError):
    pass


async def import_article(
    session: AsyncSession,
    episode_id: str,
    article: str,
    *,
    llm: LLMClient | None = None,
    optimize: bool = True,
    instructions: str = "",
) -> dict:
    settings = get_settings()
    episode = await session.get(Episode, episode_id, with_for_update=True)
    if episode is None:
        raise LookupError(f"episode not found: {episode_id}")
    if episode.status not in {
        EpisodeStatus.DRAFT,
        EpisodeStatus.TOPIC_CONFIRMED,
        EpisodeStatus.SCRIPT_REVIEW,
    }:
        raise ArticleImportConflict(
            f"episode status {episode.status.value} cannot import an article"
        )

    article = article.strip()
    if not article:
        raise ArticleImportError("article must not be empty")
    if len(article) > settings.script_article_max_chars:
        raise ArticleImportError(
            f"article is too long: {len(article)} chars "
            f"(max {settings.script_article_max_chars})"
        )

    series = await session.get(Series, episode.series_id)
    labels = section_labels_for(series)
    target_chars = target_chars_for_duration(
        episode.target_duration_s, settings.script_target_chars_per_minute
    )
    original_status = episode.status
    episode.status = EpisodeStatus.SCRIPTING
    episode.current_node = "script.import"
    episode.health = "OK"
    await session.flush()

    prompt = load_prompt(
        "article.md",
        title=episode.title,
        target_duration_s=episode.target_duration_s,
        target_chars=target_chars,
        section_labels="、".join(labels),
        article=article,
        instructions=instructions.strip() or "无",
    )
    try:
        raw = await (llm or build_llm()).chat_json(
            load_system_prompt(),
            prompt,
            temperature=0.55,
            max_tokens=max(5000, target_chars * 8),
        )
    except Exception:
        episode.status = original_status
        episode.current_node = None
        episode.health = "FAILED"
        raise

    sections = raw.get("sections")
    if not isinstance(sections, list):
        episode.status = original_status
        episode.current_node = None
        episode.health = "FAILED"
        raise ArticleImportError("article import returned no sections")

    section_by_label = {
        str(item.get("label")): item
        for item in sections
        if isinstance(item, dict)
    }
    outline: list[dict] = []
    lines: list[ScriptLineData] = []
    for label in labels:
        section = section_by_label.get(label, {})
        outline.append(
            {
                "label": label,
                "question": str(section.get("question", "")),
                "goal": str(section.get("goal", "")),
                "beats": section.get("beats") if isinstance(section.get("beats"), list) else [],
            }
        )
        for item in section.get("lines", []) if isinstance(section.get("lines"), list) else []:
            if not isinstance(item, dict):
                continue
            text = str(item.get("text", "")).strip()
            if not text:
                continue
            speaker = "roxy"
            lines.append(
                ScriptLineData(
                    seq=len(lines) + 1,
                    section=label,
                    speaker=speaker,
                    text=text,
                    char_count=len(text),
                )
            )

    if not lines:
        episode.status = original_status
        episode.current_node = None
        episode.health = "FAILED"
        raise ArticleImportError("article import produced no lines")

    validation = validate_script(
        lines,
        target_duration_s=episode.target_duration_s,
        section_labels=labels,
        target_chars_per_minute=settings.script_target_chars_per_minute,
    )

    await session.execute(
        delete(ScriptLine).where(ScriptLine.episode_id == episode_id)
    )
    for line in lines:
        session.add(
            ScriptLine(
                episode_id=episode_id,
                seq=line.seq,
                speaker=line.speaker,
                section=line.section,
                text=line.text,
                char_count=line.char_count,
                version=1,
            )
        )

    meta = dict(episode.script_meta or {})
    meta.update(
        {
            "source": "article",
            "summary": str(raw.get("summary", "")),
            "outline": outline,
            "article_chars": len(article),
            "imported_at": datetime.now(timezone.utc).isoformat(),
            "validation": validation.model_dump(),
        }
    )
    episode.script_meta = meta
    episode.status = EpisodeStatus.SCRIPT_REVIEW
    episode.current_node = None
    episode.health = "OK"
    episode.version += 1
    await session.flush()

    optimized = False
    optimization_error = None
    if optimize:
        try:
            await optimize_script(session, episode_id, llm=llm, apply=True)
            optimized = True
        except Exception as exc:
            optimization_error = str(exc)[:500]

    current_lines = await load_lines(session, episode_id)
    final_validation = validate_episode(episode, series, current_lines)
    meta = dict(episode.script_meta or {})
    meta["validation"] = final_validation.model_dump()
    episode.script_meta = meta
    episode.health = "OK" if final_validation.valid else "WARNING"
    return {
        "episode_id": episode.id,
        "status": episode.status,
        "summary": meta.get("summary", ""),
        "outline": outline,
        "validation": final_validation.model_dump(),
        "optimized": optimized,
        "optimization_error": optimization_error,
        "lines": [
            {
                "id": line.id,
                "episode_id": line.episode_id,
                "seq": line.seq,
                "speaker": line.speaker,
                "section": line.section,
                "text": line.text,
                "char_count": line.char_count,
                "version": line.version,
            }
            for line in current_lines
        ],
    }

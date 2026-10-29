from __future__ import annotations

import json
from functools import lru_cache
from typing import TypedDict

from langgraph.checkpoint.memory import MemorySaver
from langgraph.graph import END, START, StateGraph

from app.agents.script.prompts import load_prompt, load_system_prompt
from app.agents.script.validation import (
    ScriptLineData,
    validate_script,
)
from app.core.config import get_settings
from app.providers.llm import LLMClient


class ScriptState(TypedDict, total=False):
    episode_id: str
    title: str
    topic: str
    target_duration_s: int
    target_chars: int
    section_labels: list[str]
    outline: dict
    sections: list[dict]
    lines: list[dict]
    validation: dict
    errors: list[str]
    attempts: int


def _clean_list(value: object) -> list[str]:
    if not isinstance(value, list):
        return []
    return [str(item).strip() for item in value if str(item).strip()]


def normalize_outline(
    raw: dict,
    section_labels: list[str],
    target_chars: int,
) -> dict:
    raw_sections = raw.get("sections")
    by_label: dict[str, dict] = {}
    if isinstance(raw_sections, list):
        for item in raw_sections:
            if isinstance(item, dict) and item.get("label"):
                by_label[str(item["label"]).strip()] = item

    sections: list[dict] = []
    for label in section_labels:
        item = by_label.get(label, {})
        sections.append(
            {
                "label": label,
                "goal": str(item.get("goal") or f"讲清楚「{label}」这一部分。").strip(),
                "key_points": _clean_list(item.get("key_points"))[:4],
                "target_chars": max(1, int(item.get("target_chars") or 0)),
            }
        )

    total = sum(section["target_chars"] for section in sections)
    if total == 0:
        base = max(1, target_chars // max(1, len(sections)))
        for section in sections:
            section["target_chars"] = base
        total = base * len(sections)
    scale = target_chars / total
    for section in sections:
        section["target_chars"] = max(20, round(section["target_chars"] * scale))
    diff = target_chars - sum(section["target_chars"] for section in sections)
    sections[-1]["target_chars"] += diff

    return {
        "title_hook": str(raw.get("title_hook") or "").strip(),
        "angle": str(raw.get("angle") or "").strip(),
        "sections": sections,
    }


def normalize_sections(raw: dict, outline_sections: list[dict]) -> list[dict]:
    raw_sections = raw.get("sections")
    by_label: dict[str, dict] = {}
    if isinstance(raw_sections, list):
        for item in raw_sections:
            if isinstance(item, dict) and item.get("label"):
                by_label[str(item["label"]).strip()] = item

    sections: list[dict] = []
    for item in outline_sections:
        label = item["label"]
        raw_item = by_label.get(label, {})
        beats = _clean_list(raw_item.get("beats"))[:5]
        if not beats:
            beats = [item["goal"]]
        sections.append(
            {
                "label": label,
                "summary": str(raw_item.get("summary") or item["goal"]).strip(),
                "beats": beats,
                "goal": item["goal"],
                "key_points": item.get("key_points", []),
                "target_chars": item["target_chars"],
            }
        )
    return sections


def _context_for(sections: list[dict], index: int) -> str:
    parts: list[str] = []
    if index > 0:
        previous = sections[index - 1]
        parts.append(f"上一章「{previous['label']}」：{previous.get('summary', '')}")
    if index + 1 < len(sections):
        following = sections[index + 1]
        parts.append(f"下一章「{following['label']}」：{following['goal']}")
    return "；".join(parts) or "这是第一章/最后一章，注意开头和收尾。"


def _normalize_repaired_lines(
    raw_lines: object,
    old_lines: list[dict],
    section_labels: list[str],
) -> list[dict]:
    if not isinstance(raw_lines, list):
        return old_lines
    lines: list[dict] = []
    for index, item in enumerate(raw_lines):
        if not isinstance(item, dict):
            continue
        text = str(item.get("text", "")).strip()
        if not text:
            continue
        old_section = old_lines[index]["section"] if index < len(old_lines) else None
        section = str(item.get("section") or old_section or section_labels[0])
        speaker = str(item.get("speaker") or "narrator")
        lines.append(
            {
                "seq": len(lines) + 1,
                "section": section,
                "speaker": speaker,
                "text": text,
                "char_count": len(text),
            }
        )
    return lines


@lru_cache(maxsize=1)
def _checkpointer() -> MemorySaver:
    return MemorySaver()


def build_script_graph(llm: LLMClient, checkpointer: MemorySaver | None = None):
    settings = get_settings()
    system_prompt = load_system_prompt()

    async def outline_node(state: ScriptState) -> dict:
        prompt = load_prompt(
            "outline.md",
            title=state["title"],
            topic=state["topic"],
            target_duration_s=state["target_duration_s"],
            target_chars=state["target_chars"],
            section_labels="、".join(state["section_labels"]),
        )
        raw = await llm.chat_json(
            system_prompt, prompt, temperature=0.7, max_tokens=1600
        )
        outline = normalize_outline(
            raw, state["section_labels"], state["target_chars"]
        )
        return {"outline": outline}

    async def sections_node(state: ScriptState) -> dict:
        prompt = load_prompt(
            "sections.md",
            outline_json=json.dumps(
                state["outline"], ensure_ascii=False, indent=2
            ),
        )
        raw = await llm.chat_json(
            system_prompt, prompt, temperature=0.7, max_tokens=2200
        )
        sections = normalize_sections(raw, state["outline"]["sections"])
        return {"sections": sections}

    async def lines_node(state: ScriptState) -> dict:
        all_lines: list[dict] = []
        for index, section in enumerate(state["sections"]):
            prompt = load_prompt(
                "lines.md",
                section_label=section["label"],
                goal=section["goal"],
                beats="\n".join(f"- {beat}" for beat in section["beats"]),
                context=_context_for(state["sections"], index),
                target_chars=section["target_chars"],
            )
            raw = await llm.chat_json(
                system_prompt,
                prompt,
                temperature=0.7,
                max_tokens=max(900, section["target_chars"] * 3),
            )
            raw_lines = raw.get("lines")
            if not isinstance(raw_lines, list):
                continue
            for item in raw_lines:
                if not isinstance(item, dict):
                    continue
                text = str(item.get("text", "")).strip()
                if not text:
                    continue
                speaker = str(item.get("speaker") or "narrator")
                all_lines.append(
                    {
                        "seq": len(all_lines) + 1,
                        "section": section["label"],
                        "speaker": speaker,
                        "text": text,
                        "char_count": len(text),
                    }
                )
        return {"lines": all_lines}

    async def validate_node(state: ScriptState) -> dict:
        lines = [ScriptLineData(**line) for line in state.get("lines", [])]
        result = validate_script(
            lines,
            target_duration_s=state["target_duration_s"],
            section_labels=state["section_labels"],
            target_chars_per_minute=settings.script_target_chars_per_minute,
            roxy_ratio_min=settings.script_roxy_ratio_min,
            roxy_ratio_max=settings.script_roxy_ratio_max,
            min_lines_for_ratio=settings.script_min_lines_for_ratio,
        )
        return {
            "validation": result.model_dump(),
            "errors": result.errors,
        }

    async def repair_node(state: ScriptState) -> dict:
        errors = state.get("errors", [])
        attempts = state.get("attempts", 0) + 1
        if not errors:
            return {"attempts": attempts}
        prompt = load_prompt(
            "repair.md",
            lines_json=json.dumps(
                state.get("lines", []), ensure_ascii=False, indent=2
            ),
            errors="\n".join(f"- {error}" for error in errors),
            target_chars=state["target_chars"],
            section_labels="、".join(state["section_labels"]),
        )
        raw = await llm.chat_json(
            system_prompt, prompt, temperature=0.3, max_tokens=5000
        )
        repaired = _normalize_repaired_lines(
            raw.get("lines"), state.get("lines", []), state["section_labels"]
        )
        if repaired:
            return {"lines": repaired, "attempts": attempts}
        return {"attempts": attempts}

    def route_after_validate(state: ScriptState) -> str:
        if state.get("errors") and state.get("attempts", 0) < settings.script_max_repairs:
            return "repair"
        return "end"

    graph = StateGraph(ScriptState)
    graph.add_node("outline", outline_node)
    graph.add_node("sections", sections_node)
    graph.add_node("lines", lines_node)
    graph.add_node("validate", validate_node)
    graph.add_node("repair", repair_node)
    graph.add_edge(START, "outline")
    graph.add_edge("outline", "sections")
    graph.add_edge("sections", "lines")
    graph.add_edge("lines", "validate")
    graph.add_conditional_edges(
        "validate",
        route_after_validate,
        {"repair": "repair", "end": END},
    )
    graph.add_edge("repair", "validate")
    return graph.compile(checkpointer=checkpointer)


async def run_script_graph(
    *,
    episode_id: str,
    title: str,
    topic: str,
    target_duration_s: int,
    target_chars: int,
    section_labels: list[str],
    thread_id: str,
    llm: LLMClient,
) -> ScriptState:
    graph = build_script_graph(llm, _checkpointer())
    initial: ScriptState = {
        "episode_id": episode_id,
        "title": title,
        "topic": topic,
        "target_duration_s": target_duration_s,
        "target_chars": target_chars,
        "section_labels": section_labels,
        "outline": {},
        "sections": [],
        "lines": [],
        "validation": {},
        "errors": [],
        "attempts": 0,
    }
    result = await graph.ainvoke(
        initial,
        config={"configurable": {"thread_id": thread_id}},
    )
    return result

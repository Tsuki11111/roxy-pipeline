from __future__ import annotations

import json
from functools import lru_cache
from typing import TypedDict

from langgraph.checkpoint.memory import MemorySaver
from langgraph.graph import END, START, StateGraph

from app.core.config import get_settings
from app.providers.llm import LLMClient
from app.agents.storyboard.grammar import (
    CARD_TYPES,
    DEFAULT_CARD_STYLES,
    POSITIONS,
    TRANSITIONS,
    MOTIONS,
    catalog_text,
    default_character_image,
    estimate_duration_ms,
    load_character_assets,
)
from app.agents.storyboard.models import ShotDraft
from app.agents.storyboard.prompts import load_prompt, load_system_prompt
from app.agents.storyboard.rhythm import apply_rhythm_fixes, validate_rhythm


class StoryboardState(TypedDict, total=False):
    episode_id: str
    section_labels: list[str]
    lines: list[dict]
    catalog: list[dict]
    shots: list[dict]
    report: dict
    errors: list[str]
    attempts: int


def _normalize_shot(
    item: dict,
    line: dict,
    *,
    catalog_paths: set[str],
    default_image: str | None,
) -> dict:
    card_type = item.get("card_type")
    if card_type not in CARD_TYPES:
        card_type = "pure_text"
    position = item.get("character_position")
    if position not in POSITIONS:
        position = "left"
    image = item.get("character_image")
    if image not in catalog_paths:
        image = default_image
    if position == "none" or image is None:
        image = None
        position = "none"

    bg = item.get("bg")
    if bg not in {"paper", "paper_dark", "desk"}:
        bg = "paper"
    transition = item.get("transition")
    if transition not in TRANSITIONS:
        transition = "cut"
    motion = item.get("motion")
    if motion not in MOTIONS:
        motion = "idle_breathe"

    return {
        "seq": 0,
        "line_seq": int(line["seq"]),
        "section": line["section"],
        "speaker": line.get("speaker", "narrator"),
        "text": line["text"],
        "duration_ms": estimate_duration_ms(line["text"]),
        "card_type": card_type,
        "card_style": str(
            item.get("card_style") or DEFAULT_CARD_STYLES.get(card_type, "")
        ),
        "character_image": image,
        "character_position": position,
        "bg": bg,
        "transition": transition,
        "motion": motion,
    }


def _previous_summary(shots: list[dict]) -> str:
    if not shots:
        return "这是第一段，没有上一段。"
    last = shots[-1]
    character = "有角色" if last.get("character_image") else "无角色"
    return f"上一段最后一个镜头：card_type={last['card_type']}，{character}。"


@lru_cache(maxsize=1)
def _checkpointer() -> MemorySaver:
    return MemorySaver()


def build_storyboard_graph(
    llm: LLMClient,
    catalog: list[dict] | None = None,
    checkpointer: MemorySaver | None = None,
):
    settings = get_settings()
    assets = catalog if catalog is not None else load_character_assets()
    catalog_paths = {asset["path"] for asset in assets}
    default_image = default_character_image(assets)
    system_prompt = load_system_prompt()

    async def generate_node(state: StoryboardState) -> dict:
        section_labels = state["section_labels"]
        lines_by_section: dict[str, list[dict]] = {label: [] for label in section_labels}
        for line in state["lines"]:
            if line["section"] in lines_by_section:
                lines_by_section[line["section"]].append(line)

        shots: list[dict] = []
        for label in section_labels:
            section_lines = lines_by_section.get(label, [])
            if not section_lines:
                continue
            prompt = load_prompt(
                "generate.md",
                section_label=label,
                line_count=len(section_lines),
                lines_json=json.dumps(
                    [
                        {
                            "seq": line["seq"],
                            "speaker": line.get("speaker", "narrator"),
                            "text": line["text"],
                        }
                        for line in section_lines
                    ],
                    ensure_ascii=False,
                    indent=2,
                ),
                catalog=catalog_text(assets),
                previous=_previous_summary(shots),
            )
            raw = await llm.chat_json(
                system_prompt,
                prompt,
                temperature=0.4,
                max_tokens=max(2000, len(section_lines) * 220),
            )
            raw_shots = raw.get("shots")
            by_line: dict[int, dict] = {}
            if isinstance(raw_shots, list):
                for item in raw_shots:
                    if not isinstance(item, dict):
                        continue
                    try:
                        line_seq = int(item.get("line_seq"))
                    except (TypeError, ValueError):
                        continue
                    by_line[line_seq] = item
            for line in section_lines:
                shots.append(
                    _normalize_shot(
                        by_line.get(int(line["seq"]), {}),
                        line,
                        catalog_paths=catalog_paths,
                        default_image=default_image,
                    )
                )

        for index, shot in enumerate(shots, start=1):
            shot["seq"] = index
        return {"shots": shots}

    async def schema_check_node(state: StoryboardState) -> dict:
        try:
            drafts = [ShotDraft(**shot) for shot in state.get("shots", [])]
        except Exception as exc:
            return {"errors": [f"分镜 schema 校验失败：{exc}"]}
        if not drafts:
            return {"errors": ["分镜为空"]}
        return {"shots": [draft.model_dump() for draft in drafts], "errors": []}

    async def rhythm_check_node(state: StoryboardState) -> dict:
        drafts = [ShotDraft(**shot) for shot in state.get("shots", [])]
        report = validate_rhythm(drafts, state["section_labels"])
        return {"report": report.model_dump(), "errors": report.errors}

    async def repair_node(state: StoryboardState) -> dict:
        drafts = [ShotDraft(**shot) for shot in state.get("shots", [])]
        fixed = apply_rhythm_fixes(drafts, state["section_labels"])
        return {
            "shots": [shot.model_dump() for shot in fixed],
            "attempts": state.get("attempts", 0) + 1,
        }

    def route_after_rhythm(state: StoryboardState) -> str:
        if state.get("errors") and state.get("attempts", 0) < settings.storyboard_max_repairs:
            return "repair"
        return "end"

    graph = StateGraph(StoryboardState)
    graph.add_node("generate", generate_node)
    graph.add_node("schema_check", schema_check_node)
    graph.add_node("rhythm_check", rhythm_check_node)
    graph.add_node("repair", repair_node)
    graph.add_edge(START, "generate")
    graph.add_edge("generate", "schema_check")
    graph.add_edge("schema_check", "rhythm_check")
    graph.add_conditional_edges(
        "rhythm_check",
        route_after_rhythm,
        {"repair": "repair", "end": END},
    )
    graph.add_edge("repair", "rhythm_check")
    return graph.compile(checkpointer=checkpointer)


async def run_storyboard_graph(
    *,
    episode_id: str,
    section_labels: list[str],
    lines: list[dict],
    thread_id: str,
    llm: LLMClient,
    catalog: list[dict] | None = None,
) -> StoryboardState:
    graph = build_storyboard_graph(llm, catalog=catalog, checkpointer=_checkpointer())
    initial: StoryboardState = {
        "episode_id": episode_id,
        "section_labels": section_labels,
        "lines": lines,
        "catalog": catalog or [],
        "shots": [],
        "report": {},
        "errors": [],
        "attempts": 0,
    }
    return await graph.ainvoke(
        initial,
        config={"configurable": {"thread_id": thread_id}},
    )

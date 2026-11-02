"""LangGraph 分镜图：台词分组与镜头编排。"""

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
    MAX_GROUP_DURATION_MS,
    MAX_LINES_PER_SHOT,
    MIN_GROUP_DURATION_MS,
    POSITIONS,
    TRANSITIONS,
    MOTIONS,
    catalog_text,
    default_character_image,
    estimate_duration_ms,
    load_character_assets,
)
from app.agents.storyboard.continuity import canonicalize_continuity
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
    lines: list[dict],
    *,
    catalog_paths: set[str],
    default_image: str | None,
    group_id: str = "",
) -> dict:
    first = lines[0]
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

    scene = item.get("scene")
    if not isinstance(scene, dict):
        scene = {}
    continuity_group = str(item.get("continuity_group") or group_id or "")

    return {
        "seq": 0,
        "line_seq": int(first["seq"]),
        "line_seqs": [int(line["seq"]) for line in lines],
        "section": first["section"],
        "speaker": first.get("speaker", "narrator"),
        "text": " ".join(line["text"] for line in lines),
        "duration_ms": max(
            MIN_GROUP_DURATION_MS,
            min(
                MAX_GROUP_DURATION_MS,
                sum(estimate_duration_ms(line["text"]) for line in lines),
            ),
        ),
        "card_type": card_type,
        "card_style": str(
            item.get("card_style") or DEFAULT_CARD_STYLES.get(card_type, "")
        ),
        "character_image": image,
        "character_position": position,
        "bg": bg,
        "transition": transition,
        "motion": motion,
        "continuity_group": continuity_group,
        "scene": scene,
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
            by_seq = {int(line["seq"]): line for line in section_lines}
            groups: list[tuple[dict, list[dict]]] = []
            used: set[int] = set()
            if isinstance(raw_shots, list):
                for item in raw_shots:
                    if not isinstance(item, dict):
                        continue
                    raw_seqs = item.get("line_seqs")
                    if isinstance(raw_seqs, list):
                        seqs = []
                        for value in raw_seqs:
                            try:
                                seqs.append(int(value))
                            except (TypeError, ValueError):
                                continue
                    else:
                        try:
                            seqs = [int(item.get("line_seq"))]
                        except (TypeError, ValueError):
                            continue
                    seqs = [seq for seq in seqs if seq in by_seq]
                    seqs = list(dict.fromkeys(seqs))
                    if not seqs:
                        continue
                    contiguous = sorted(seqs) == list(
                        range(min(seqs), max(seqs) + 1)
                    )
                    if contiguous and len(seqs) <= MAX_LINES_PER_SHOT:
                        candidate_groups = [seqs]
                    else:
                        candidate_groups = [[seq] for seq in seqs]
                    for group_seqs in candidate_groups:
                        if any(seq in used for seq in group_seqs):
                            continue
                        used.update(group_seqs)
                        groups.append(
                            (item, [by_seq[seq] for seq in group_seqs])
                        )
            for line in section_lines:
                seq = int(line["seq"])
                if seq not in used:
                    used.add(seq)
                    groups.append(({}, [line]))
            groups.sort(key=lambda pair: int(pair[1][0]["seq"]))

            for index, (item, group_lines) in enumerate(groups, start=1):
                group_id = str(
                    item.get("continuity_group") or f"{label}-{index}"
                )
                shots.append(
                    _normalize_shot(
                        item,
                        group_lines,
                        catalog_paths=catalog_paths,
                        default_image=default_image,
                        group_id=group_id,
                    )
                )

        for index, shot in enumerate(shots, start=1):
            shot["seq"] = index
        canonicalize_continuity(shots)
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

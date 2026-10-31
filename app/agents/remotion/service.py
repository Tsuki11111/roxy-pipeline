from __future__ import annotations

import asyncio
import contextlib
import hashlib
import json
import logging
import re
import shutil
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from uuid import uuid4

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.agents.remotion import docker
from app.agents.remotion.models import (
    RemotionEpisodeMeta,
    RemotionShotMeta,
    ShotCodeOutput,
)
from app.agents.remotion.prompts import (
    load_prompt,
    load_skill,
    load_system_prompt,
    prompt_hash,
)
from app.agents.storyboard.render_spec import build_episode_render_spec
from app.core.config import get_settings
from app.models.core import (
    Episode,
    EpisodeStatus,
    NodeRun,
    NodeStatus,
    RemotionShot,
    ScriptLine,
    Series,
    Shot,
)
from app.providers.llm import build_llm
from app.render.service import _char_timings_from_audio
from app.render.timeline import build_timeline
from app.workflow.cancel import TaskCancelled
from app.workflow.db import task_session
from app.workflow.outbox import enqueue_outbox

logger = logging.getLogger(__name__)
PROJECT_ROOT = Path(__file__).resolve().parents[3]
TEMPLATE_DIR = Path(__file__).resolve().parent / "templates"


class RemotionError(RuntimeError):
    pass


class RemotionConflict(RemotionError):
    pass


class RemotionRequestError(RemotionError):
    pass


class RemotionPolicyError(RemotionError):
    pass


_CARD_RE = re.compile(r"from\s+['\"]\.\./components/Card['\"]|<Card\b")
_CAPTION_RE = re.compile(r"from\s+['\"]\.\./components/Caption['\"]|<Caption\b")
_LABEL_RE = re.compile(r"from\s+['\"]\.\./components/Label['\"]|<Label\b")
_BOARD_RE = re.compile(r"from\s+['\"]\.\./components/Board['\"]|<Board\b")
_TERMINAL_RE = re.compile(
    r"from\s+['\"]\.\./components/TerminalCard['\"]|<TerminalCard\b"
)

CARD_VARIANTS = ["note", "quote", "index", "letter", "sticky", "specimen"]
CARD_TONES = ["cream", "sand", "peach", "sage"]
CARD_TRANSITIONS = ["slide", "zoom", "flip", "drop", "reveal", "push"]
# 约 1/3 的镜头做纯演示，不给卡片。
CARD_PATTERN = [True, True, False, True, False]


def _card_style(seq: int) -> dict[str, str] | None:
    index = max(0, seq - 1)
    if not CARD_PATTERN[index % len(CARD_PATTERN)]:
        return None
    return {
        "variant": CARD_VARIANTS[index % len(CARD_VARIANTS)],
        "tone": CARD_TONES[index % len(CARD_TONES)],
        "transition": CARD_TRANSITIONS[index % len(CARD_TRANSITIONS)],
    }


def _check_character_motion(code: str, payload: dict) -> None:
    if not payload.get("character"):
        return
    if "components/Character" not in code:
        raise RemotionPolicyError(
            "输入有 character，必须画出 Roxy，并使用带动效的 Character 组件。"
        )
    block = re.search(r"<Character\b[\s\S]*?/>", code)
    if block is None:
        raise RemotionPolicyError("Character 必须是自闭合组件 <Character ... />。")
    attrs = block.group(0)
    for attr in ("offsetX", "opacity", "scale", "rotate"):
        match = re.search(rf"{attr}=\{{([^}}]*)\}}", attrs)
        if match and not re.fullmatch(
            r"\s*-?\d+(\.\d+)?\s*", match.group(1)
        ):
            return
    raise RemotionPolicyError(
        "角色不能静止：Character 必须加入场/呼吸/手势动效，"
        "offsetX/opacity/scale/rotate 使用 spring、interpolate 或 Math.sin 计算，"
        "不能只写 src/side/height。"
    )


def _sha_text(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def _sha_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


async def _codegen_cancelled(episode_id: str) -> bool:
    async with task_session() as session:
        episode = await session.get(Episode, episode_id)
        if episode is None:
            return True
        meta = episode.remotion_meta or {}
        return bool(
            episode.status == EpisodeStatus.CANCELLED
            or meta.get("cancel_requested")
        )


async def _wait_cancel(episode_id: str, cancel_check) -> None:
    while True:
        if await cancel_check():
            return
        await asyncio.sleep(3)


def _project_path(value: str) -> Path:
    path = Path(value).expanduser()
    if not path.is_absolute():
        path = PROJECT_ROOT / path
    path = path.resolve()
    if not path.is_relative_to(PROJECT_ROOT) or not path.is_file():
        raise RemotionRequestError(f"asset not found: {value}")
    return path


def _relative_workdir(workdir: Path) -> str:
    resolved = workdir.resolve()
    if resolved.is_relative_to(PROJECT_ROOT):
        return resolved.relative_to(PROJECT_ROOT).as_posix()
    return str(resolved)


def _component_name(seq: int) -> str:
    return f"Shot_{seq:04d}"


def _composition_id(seq: int) -> str:
    # Remotion composition IDs may not contain underscores.
    return f"Shot-{seq:04d}"


def _code_path(seq: int) -> str:
    return f"src/shots/shot_{seq:04d}.tsx"


def _asset_map(workdir: Path, spec) -> tuple[dict[str, str], dict[str, str]]:
    public = workdir / "public" / "assets"
    public.mkdir(parents=True, exist_ok=True)
    paths: set[str] = {spec.background, spec.floor}
    for shot in spec.shots:
        if shot.bg:
            paths.add(shot.bg)
        if shot.floor:
            paths.add(shot.floor)
        if shot.character:
            paths.add(shot.character.image)
        if shot.overlay:
            paths.add(shot.overlay.image)
    mapped: dict[str, str] = {}
    checksums: dict[str, str] = {}
    for raw in sorted(paths):
        source = _project_path(raw)
        checksum = _sha_file(source)
        suffix = source.suffix.lower() or ".png"
        name = f"{checksum[:16]}{suffix}"
        target = public / name
        if not target.exists() or _sha_file(target) != checksum:
            shutil.copy2(source, target)
        if raw == spec.background:
            shutil.copy2(source, public / "background.png")
        if raw == spec.floor:
            shutil.copy2(source, public / "floor.png")
        mapped[raw] = f"assets/{name}"
        checksums[raw] = checksum
    return mapped, checksums


def _prepare_workdir(episode_id: str) -> Path:
    workdir = docker.workdir_for(episode_id)
    workdir.mkdir(parents=True, exist_ok=True)
    shutil.copytree(TEMPLATE_DIR, workdir, dirs_exist_ok=True)
    (workdir / "public" / "assets").mkdir(parents=True, exist_ok=True)
    (workdir / "out").mkdir(parents=True, exist_ok=True)
    (workdir / "src" / "shots").mkdir(parents=True, exist_ok=True)
    return workdir


def _episode_context(episode: Episode) -> dict[str, Any]:
    meta = episode.script_meta or {}
    return {
        "title": episode.title,
        "topic": episode.topic,
        "summary": meta.get("summary", ""),
        "outline": json.dumps(meta.get("outline") or [], ensure_ascii=False, indent=2),
    }


def _shot_payload(
    item,
    *,
    spec,
    mapped: dict[str, str],
    checksums: dict[str, str],
    previous_tail: str,
) -> dict[str, Any]:
    shot = item.shot
    relevant: set[str] = {shot.bg or spec.background, shot.floor or spec.floor}
    character = None
    if shot.character is not None:
        relevant.add(shot.character.image)
        character = {
            "static_file": mapped[shot.character.image],
            "position": shot.character.position,
            "height_px": shot.character.height_px,
            "anchor_y": shot.character.anchor_y,
            "scale": shot.character.scale,
        }
    overlay = None
    if shot.overlay is not None:
        relevant.add(shot.overlay.image)
        overlay = {
            "static_file": mapped[shot.overlay.image],
            "position": shot.overlay.position,
            "width_px": shot.overlay.width_px,
            "bottom": shot.overlay.bottom,
            "opacity": shot.overlay.opacity,
            "blend": shot.overlay.blend,
        }
    assets = [
        {
            "source": raw,
            "static_file": mapped[raw],
            "checksum": checksums[raw],
        }
        for raw in sorted(relevant)
        if raw in mapped
    ]
    return {
        "component_name": _component_name(shot.seq),
        "composition_id": _composition_id(shot.seq),
        "shot_id": shot.shot_id,
        "seq": shot.seq,
        "section": shot.section,
        "narration": shot.narration,
        "duration_ms": shot.duration_ms,
        "frame_count": item.frame_count,
        "fps": spec.fps,
        "width": spec.width,
        "height": spec.height,
        "card": (
            {
                "type": shot.card.type,
                "text": shot.card.text,
                "style": shot.card.style,
            }
            if shot.card is not None
            else None
        ),
        "character": character,
        "overlay": overlay,
        "background": mapped.get(shot.bg or spec.background),
        "floor": mapped.get(shot.floor or spec.floor),
        "subtitle_chunks": [
            {"text": chunk.text, "start_ms": chunk.start_ms, "end_ms": chunk.end_ms}
            for chunk in item.chunks
        ],
        "previous_tail": previous_tail,
        "card_style": _card_style(shot.seq),
        "assets": assets,
    }


def _root_source(
    rows: list[RemotionShot],
    shot_by_id: dict[str, Shot],
    frame_counts: dict[str, int],
    spec,
    subtitles_by_shot: dict[str, list[dict]],
) -> str:
    imports: list[str] = []
    wrappers: list[str] = []
    compositions: list[str] = []
    needs_subtitles = False
    for row in sorted(rows, key=lambda item: shot_by_id[item.shot_id].seq):
        shot = shot_by_id[row.shot_id]
        name = _component_name(shot.seq)
        composition_id = _composition_id(shot.seq)
        imports.append(f"import {{{name}}} from './shots/shot_{shot.seq:04d}';")
        component = name
        chunks = subtitles_by_shot.get(row.shot_id) or []
        if chunks:
            needs_subtitles = True
            component = f"{name}Frame"
            wrappers.append(
                f"const {component} = () => (\n"
                f"  <>\n"
                f"    <{name} />\n"
                f"    <SubtitleTrack chunks={{{json.dumps(chunks, ensure_ascii=False)}}} />\n"
                f"  </>\n"
                f");"
            )
        frames = max(1, frame_counts.get(row.shot_id, 1))
        compositions.append(
            f'      <Composition id="{composition_id}" component={{{component}}} '
            f"durationInFrames={{{frames}}} fps={{{spec.fps}}} "
            f"width={{{spec.width}}} height={{{spec.height}}} />"
        )
    if needs_subtitles:
        imports.append("import {SubtitleTrack} from './components/SubtitleTrack';")
    return "\n".join(
        [
            "import {Composition} from 'remotion';",
            *imports,
            "",
            *wrappers,
            "export const RemotionRoot = () => (",
            "  <>",
            *compositions,
            "  </>",
            ");",
            "",
        ]
    )


async def _generate_one(
    llm,
    *,
    context: dict[str, Any],
    payload: dict[str, Any],
    skill: str,
    error_feedback: str = "",
) -> ShotCodeOutput:
    prompt = load_prompt(
        "generate_shot.md",
        skill=skill,
        title=context["title"],
        topic=context["topic"],
        summary=context["summary"],
        outline=context["outline"],
        shot_json=json.dumps(payload, ensure_ascii=False, indent=2),
        assets_json=json.dumps(payload["assets"], ensure_ascii=False, indent=2),
        previous_tail=payload["previous_tail"] or "无",
        error_feedback=error_feedback or "无",
        component_name=payload["component_name"],
    )
    raw = await llm.chat_json(
        load_system_prompt(),
        prompt,
        temperature=0.4,
        max_tokens=16384,
    )
    data = json.loads(raw) if isinstance(raw, str) else raw
    result = ShotCodeOutput.model_validate(data)
    if result.component_name != payload["component_name"]:
        raise RemotionError(
            f"component mismatch: {result.component_name} != {payload['component_name']}"
        )
    code = result.code.strip()
    if code.startswith("```"):
        code = code.split("\n", 1)[-1]
        if code.rstrip().endswith("```"):
            code = code.rstrip()[: -3]
    code = code.strip()
    if _CARD_RE.search(code):
        raise RemotionPolicyError(
            "不要使用 Card 组件；画面文字统一改用 PaperCard（Claude 纸卡风格）。"
        )
    if _CAPTION_RE.search(code):
        raise RemotionPolicyError(
            "不要使用 Caption；画面文字统一改用 PaperCard（Claude 纸卡风格）。"
        )
    if _LABEL_RE.search(code):
        raise RemotionPolicyError(
            "不要使用 Label 关键词标签；画面文字统一改用 PaperCard 长段纸卡。"
        )
    if _BOARD_RE.search(code):
        raise RemotionPolicyError(
            "不要使用 Board 黑板卡；画面文字统一改用 PaperCard（暖纸/墨字/陶土）。"
        )
    if _TERMINAL_RE.search(code):
        raise RemotionPolicyError(
            "不要使用 TerminalCard；画面文字统一改用 PaperCard"
            "（note/quote/index/letter/sticky/specimen，Claude 纸卡风格）。"
        )
    _check_character_motion(code, payload)
    style = payload.get("card_style")
    if style is None:
        if "components/PaperCard" in code:
            raise RemotionPolicyError(
                "本镜头的 card_style 为 null：不要使用 PaperCard，"
                "把这一镜做成纯图形/动画演示，不要放卡片。"
            )
        return result.model_copy(update={"code": code})
    if "components/PaperCard" in code:
        variants = re.findall(r"variant\s*=\s*['\"]([a-z]+)['\"]", code)
        tones = re.findall(r"tone\s*=\s*['\"]([a-z]+)['\"]", code)
        if not variants:
            variants = ["note"]
        if not tones:
            tones = ["cream"]
        required_variant = style.get("variant")
        required_tone = style.get("tone")
        if required_variant and required_variant not in variants:
            raise RemotionPolicyError(
                f"本镜头卡片必须使用 variant=\"{required_variant}\""
                f"（可用：{', '.join(variants)}）；请按 card_style 实现。"
            )
        if required_tone and required_tone not in tones:
            raise RemotionPolicyError(
                f"本镜头卡片必须使用 tone=\"{required_tone}\""
                f"（当前：{', '.join(tones)}）；请按 card_style 实现。"
            )
    return result.model_copy(update={"code": code})


async def _upsert_shot_row(
    session: AsyncSession,
    *,
    episode_id: str,
    shot_id: str,
    composition_id: str,
    code_hash: str,
    code_path: str,
    input_hash: str,
    prompt_hash_value: str,
    model: str,
    image_digest: str | None,
    status: str,
    error: str | None,
) -> RemotionShot:
    row = await session.scalar(
        select(RemotionShot).where(RemotionShot.shot_id == shot_id)
    )
    if row is None:
        row = RemotionShot(
            episode_id=episode_id,
            shot_id=shot_id,
            composition_id=composition_id,
            code_hash=code_hash,
            code_path=code_path,
            input_hash=input_hash,
            status=status,
            error=error,
            attempts=1,
            prompt_hash=prompt_hash_value,
            model=model,
            image_digest=image_digest,
        )
        session.add(row)
    else:
        row.composition_id = composition_id
        row.code_hash = code_hash
        row.code_path = code_path
        row.input_hash = input_hash
        row.status = status
        row.error = error
        row.attempts += 1
        row.prompt_hash = prompt_hash_value
        row.model = model
        row.image_digest = image_digest
    await session.flush()
    return row


def _write_root(
    workdir: Path,
    rows: list[RemotionShot],
    shot_by_id: dict[str, Shot],
    frame_counts: dict[str, int],
    spec,
    subtitles_by_shot: dict[str, list[dict]],
) -> None:
    ready = [row for row in rows if (workdir / row.code_path).is_file()]
    (workdir / "src" / "Root.tsx").write_text(
        _root_source(ready, shot_by_id, frame_counts, spec, subtitles_by_shot),
        encoding="utf-8",
    )


def _meta_from_rows(
    episode: Episode,
    rows: list[RemotionShot],
    workdir: Path,
    total_shots: int,
) -> RemotionEpisodeMeta:
    settings = get_settings()
    shot_meta = {
        row.shot_id: RemotionShotMeta(
            composition_id=row.composition_id,
            code_hash=row.code_hash,
            code_path=row.code_path,
            status=row.status,
            error=row.error,
            input_hash=row.input_hash,
            prompt_hash=row.prompt_hash,
            model=row.model,
            image_digest=row.image_digest,
        )
        for row in rows
    }
    all_ready = (
        len(rows) == total_shots
        and total_shots > 0
        and all(row.status == "READY" for row in rows)
    )
    return RemotionEpisodeMeta(
        enabled=all_ready,
        status="ready" if all_ready else "partial",
        work_dir=_relative_workdir(workdir),
        version=settings.remotion_version,
        image_digest=docker.image_digest(),
        model=settings.deepseek_model,
        skill_hash=hashlib.sha256(load_skill().encode("utf-8")).hexdigest(),
        prompt_hash=prompt_hash(),
        generated_at=datetime.now(timezone.utc).isoformat(),
        shots=shot_meta,
    )


async def generate_remotion_code(
    session: AsyncSession,
    episode_id: str,
    node_run_id: str,
    *,
    shot_ids: list[str] | None = None,
    cancel_check=None,
) -> dict:
    settings = get_settings()
    episode = await session.get(Episode, episode_id, with_for_update=True)
    node = await session.get(NodeRun, node_run_id)
    if episode is None or node is None:
        raise RemotionError("episode/node not found")
    if not settings.remotion_enabled:
        raise RemotionRequestError("Remotion rendering is disabled")

    series = await session.get(Series, episode.series_id)
    if series is None:
        raise RemotionError("series not found")
    lines = list(
        await session.scalars(
            select(ScriptLine)
            .where(ScriptLine.episode_id == episode_id)
            .order_by(ScriptLine.seq)
        )
    )
    shots = list(
        await session.scalars(
            select(Shot)
            .where(Shot.episode_id == episode_id)
            .order_by(Shot.seq)
        )
    )
    if not shots:
        raise RemotionError("episode has no shots")
    if len(shots) > settings.remotion_codegen_max_shots:
        raise RemotionRequestError(
            f"too many shots: {len(shots)} > {settings.remotion_codegen_max_shots}"
        )

    spec = await build_episode_render_spec(
        session,
        episode,
        char_timings_by_line=_char_timings_from_audio(episode),
    )
    timeline = build_timeline(spec)
    workdir = _prepare_workdir(episode_id)
    mapped, checksums = _asset_map(workdir, spec)
    context = _episode_context(episode)
    shot_by_id = {shot.id: shot for shot in shots}
    timeline_by_id = {item.shot.shot_id: item for item in timeline.shots}
    requested = set(shot_ids) if shot_ids else None
    existing_rows = list(
        await session.scalars(
            select(RemotionShot).where(RemotionShot.episode_id == episode_id)
        )
    )
    existing = {row.shot_id: row for row in existing_rows}
    prompt_hash_value = prompt_hash()
    model = settings.deepseek_model
    image_digest = docker.image_digest()

    payloads: list[dict] = []
    previous_tail = ""
    for item in timeline.shots:
        payload = _shot_payload(
            item,
            spec=spec,
            mapped=mapped,
            checksums=checksums,
            previous_tail=previous_tail,
        )
        if requested is None or item.shot.shot_id in requested:
            input_hash = _sha_text(
                json.dumps(
                    {
                        "payload": payload,
                        "context": context,
                        "prompt_hash": prompt_hash_value,
                        "model": model,
                        "version": settings.remotion_version,
                        "image_digest": image_digest,
                    },
                    ensure_ascii=False,
                    sort_keys=True,
                )
            )
            payload["input_hash"] = input_hash
            row = existing.get(item.shot.shot_id)
            code_path = workdir / _code_path(item.shot.seq)
            if (
                row is not None
                and row.status == "READY"
                and row.input_hash == input_hash
                and code_path.is_file()
            ):
                payload["skip"] = True
            else:
                payload["skip"] = False
                payloads.append(payload)
        previous_tail = item.shot.narration[-40:]

    llm = build_llm()
    semaphore = asyncio.Semaphore(max(1, settings.remotion_codegen_concurrency))
    skill = load_skill()

    async def generate(payload: dict):
        async with semaphore:
            try:
                result = await _generate_one(
                    llm, context=context, payload=payload, skill=skill
                )
                return payload, result, None
            except RemotionPolicyError as exc:
                try:
                    retry = await _generate_one(
                        llm,
                        context=context,
                        payload=payload,
                        skill=skill,
                        error_feedback=str(exc),
                    )
                    return payload, retry, None
                except Exception as retry_exc:
                    return payload, None, str(retry_exc)[:2000]
            except Exception as exc:
                return payload, None, str(exc)[:2000]

    async def cancelled() -> bool:
        return bool(cancel_check and await cancel_check())

    gather_task = asyncio.gather(*(generate(payload) for payload in payloads))
    watcher = (
        asyncio.create_task(_wait_cancel(episode_id, cancel_check))
        if cancel_check is not None
        else None
    )
    try:
        if watcher is not None:
            done, _ = await asyncio.wait(
                {gather_task, watcher}, return_when=asyncio.FIRST_COMPLETED
            )
            if watcher in done:
                gather_task.cancel()
                await asyncio.gather(gather_task, return_exceptions=True)
                raise TaskCancelled("remotion codegen cancelled by user")
        results = await gather_task
    finally:
        if watcher is not None:
            watcher.cancel()
            with contextlib.suppress(asyncio.CancelledError):
                await watcher

    if await cancelled():
        raise TaskCancelled("remotion codegen cancelled by user")
    failures: dict[str, str] = {}
    for payload, result, error in results:
        item = timeline_by_id[payload["shot_id"]]
        if error or result is None:
            failures[payload["shot_id"]] = error or "empty result"
            await _upsert_shot_row(
                session,
                episode_id=episode_id,
                shot_id=payload["shot_id"],
                composition_id=payload["composition_id"],
                code_hash="",
                code_path=_code_path(item.shot.seq),
                input_hash=payload["input_hash"],
                prompt_hash_value=prompt_hash_value,
                model=model,
                image_digest=image_digest,
                status="FAILED",
                error=error,
            )
            continue
        code_path = workdir / _code_path(item.shot.seq)
        code_path.write_text(result.code, encoding="utf-8")
        await _upsert_shot_row(
            session,
            episode_id=episode_id,
            shot_id=payload["shot_id"],
            composition_id=payload["composition_id"],
            code_hash=hashlib.sha256(result.code.encode("utf-8")).hexdigest(),
            code_path=_code_path(item.shot.seq),
            input_hash=payload["input_hash"],
            prompt_hash_value=prompt_hash_value,
            model=model,
            image_digest=image_digest,
            status="PENDING",
            error=None,
        )

    all_rows = list(
        await session.scalars(
            select(RemotionShot).where(RemotionShot.episode_id == episode_id)
        )
    )
    frame_counts = {item.shot.shot_id: item.frame_count for item in timeline.shots}
    subtitles_by_shot: dict[str, list[dict]] = {}
    for item in timeline.shots:
        duration_ms = item.end_ms - item.start_ms
        chunks: list[dict] = []
        for chunk in item.chunks:
            local_start = max(0, chunk.start_ms - item.start_ms)
            local_end = min(duration_ms, chunk.end_ms - item.start_ms)
            if local_end > local_start:
                chunks.append(
                    {
                        "text": chunk.text,
                        "start_ms": local_start,
                        "end_ms": local_end,
                    }
                )
        subtitles_by_shot[item.shot.shot_id] = chunks
    if await cancelled():
        raise TaskCancelled("remotion codegen cancelled by user")
    _write_root(workdir, all_rows, shot_by_id, frame_counts, spec, subtitles_by_shot)

    validation_error = None
    for attempt in range(2):
        if await cancelled():
            raise TaskCancelled("remotion codegen cancelled by user")
        try:
            docker.validate_workdir(workdir)
            validation_error = None
            break
        except docker.RemotionDockerError as exc:
            validation_error = str(exc)
            if attempt != 0 or not payloads:
                break
            affected = {
                payload["shot_id"]
                for payload in payloads
                if f"shot_{timeline_by_id[payload['shot_id']].shot.seq:04d}"
                in validation_error
            } or {payload["shot_id"] for payload in payloads}
            retry_payloads = [
                payload for payload in payloads if payload["shot_id"] in affected
            ]
            if await cancelled():
                raise TaskCancelled("remotion codegen cancelled by user")
            retry_results = await asyncio.gather(
                *(generate(payload) for payload in retry_payloads)
            )
            if await cancelled():
                raise TaskCancelled("remotion codegen cancelled by user")
            for payload, result, error in retry_results:
                item = timeline_by_id[payload["shot_id"]]
                if error or result is None:
                    failures[payload["shot_id"]] = error or "empty result"
                    await _upsert_shot_row(
                        session,
                        episode_id=episode_id,
                        shot_id=payload["shot_id"],
                        composition_id=payload["composition_id"],
                        code_hash="",
                        code_path=_code_path(item.shot.seq),
                        input_hash=payload["input_hash"],
                        prompt_hash_value=prompt_hash_value,
                        model=model,
                        image_digest=image_digest,
                        status="FAILED",
                        error=error,
                    )
                    continue
                (workdir / _code_path(item.shot.seq)).write_text(
                    result.code, encoding="utf-8"
                )
                await _upsert_shot_row(
                    session,
                    episode_id=episode_id,
                    shot_id=payload["shot_id"],
                    composition_id=payload["composition_id"],
                    code_hash=hashlib.sha256(result.code.encode("utf-8")).hexdigest(),
                    code_path=_code_path(item.shot.seq),
                    input_hash=payload["input_hash"],
                    prompt_hash_value=prompt_hash_value,
                    model=model,
                    image_digest=image_digest,
                    status="PENDING",
                    error=None,
                )
            all_rows = list(
                await session.scalars(
                    select(RemotionShot).where(RemotionShot.episode_id == episode_id)
                )
            )
            _write_root(
                workdir, all_rows, shot_by_id, frame_counts, spec, subtitles_by_shot
            )

    all_rows = list(
        await session.scalars(
            select(RemotionShot).where(RemotionShot.episode_id == episode_id)
        )
    )
    if await cancelled():
        raise TaskCancelled("remotion codegen cancelled by user")
    for row in all_rows:
        if row.status in {"PENDING", "GENERATED"}:
            row.status = "READY" if validation_error is None else "FAILED"
            row.error = validation_error
    await session.flush()

    meta = _meta_from_rows(episode, all_rows, workdir, len(shots))
    episode.remotion_meta = meta.model_dump()
    episode.current_node = None
    episode.health = "OK" if meta.enabled else "WARNING"
    episode.version += 1
    await session.flush()

    try:
        final_spec = await build_episode_render_spec(
            session,
            episode,
            char_timings_by_line=_char_timings_from_audio(episode),
        )
        episode.render_spec = final_spec.model_dump()
        await session.flush()
    except Exception:
        logger.exception(
            "failed to rebuild render spec after remotion codegen episode=%s",
            episode_id,
        )

    if validation_error and not any(row.status == "READY" for row in all_rows):
        raise RemotionError(f"Remotion validation failed: {validation_error}")
    return {"meta": meta.model_dump(), "failures": failures}


async def cancel_remotion_codegen(
    session: AsyncSession, episode_id: str
) -> tuple[Episode, NodeRun]:
    episode = await session.get(Episode, episode_id, with_for_update=True)
    if episode is None:
        raise LookupError(f"episode not found: {episode_id}")
    node = await session.scalar(
        select(NodeRun)
        .where(
            NodeRun.episode_id == episode_id,
            NodeRun.node_key == "remotion.codegen",
            NodeRun.status.in_([NodeStatus.PENDING, NodeStatus.RUNNING]),
        )
        .with_for_update()
    )
    if node is None:
        raise RemotionConflict("no running remotion codegen")
    now = datetime.now(timezone.utc)
    node.status = NodeStatus.INTERRUPTED
    node.error = "cancelled by user"
    node.finished_at = now
    node.heartbeat_at = now
    meta = dict(episode.remotion_meta or {})
    meta["cancel_requested"] = True
    meta["status"] = "ready" if meta.get("enabled") else "cancelled"
    meta["error"] = "cancelled by user"
    episode.remotion_meta = meta
    episode.current_node = None
    episode.health = "OK" if meta.get("enabled") else "WARNING"
    await session.flush()
    return episode, node


async def start_remotion_codegen(
    session: AsyncSession,
    episode_id: str,
    *,
    shot_ids: list[str] | None = None,
    auto_render: bool = False,
) -> tuple[Episode, NodeRun]:
    settings = get_settings()
    if not settings.remotion_enabled:
        raise RemotionRequestError("Remotion rendering is disabled")
    episode = await session.get(Episode, episode_id, with_for_update=True)
    if episode is None:
        raise LookupError(f"episode not found: {episode_id}")
    if episode.status not in {
        EpisodeStatus.READY,
        EpisodeStatus.PUBLISHED,
        EpisodeStatus.QC,
        EpisodeStatus.ALIGNING,
        EpisodeStatus.RENDERING,
    }:
        raise RemotionConflict(
            "episode must be ALIGNING/RENDERING/READY/QC/PUBLISHED before codegen"
        )
    shots = list(
        await session.scalars(select(Shot).where(Shot.episode_id == episode_id))
    )
    if not shots:
        raise RemotionRequestError("episode has no shots")
    if len(shots) > settings.remotion_codegen_max_shots:
        raise RemotionRequestError(
            f"too many shots: {len(shots)} > {settings.remotion_codegen_max_shots}"
        )
    running = await session.scalar(
        select(NodeRun).where(
            NodeRun.episode_id == episode_id,
            NodeRun.node_key == "remotion.codegen",
            NodeRun.status.in_([NodeStatus.PENDING, NodeStatus.RUNNING]),
        )
    )
    if running is not None:
        raise RemotionConflict("Remotion codegen is already queued or running")

    digest = _sha_text(
        json.dumps(
            {
                "episode": episode_id,
                "version": episode.version,
                "shots": sorted(shot_ids or [shot.id for shot in shots]),
                "prompt": prompt_hash(),
                "model": settings.deepseek_model,
                "nonce": uuid4().hex,
            },
            sort_keys=True,
        )
    )
    node = NodeRun(
        episode_id=episode_id,
        node_key="remotion.codegen",
        status=NodeStatus.PENDING,
        input_hash=digest,
    )
    session.add(node)
    meta = dict(episode.remotion_meta or {})
    meta["status"] = "generating"
    meta["error"] = None
    episode.remotion_meta = meta
    episode.current_node = "remotion.generate"
    episode.health = "OK"
    await session.flush()
    await enqueue_outbox(
        session,
        "remotion.generate",
        {
            "episode_id": episode_id,
            "node_run_id": node.id,
            "shot_ids": shot_ids,
            "auto_render": auto_render,
        },
        episode_id=episode_id,
    )
    return episode, node

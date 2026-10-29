from __future__ import annotations

import re
from datetime import datetime, timezone
from pathlib import Path
from uuid import uuid4

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.agents.asset.models import AssetKind, AssetPlan
from app.agents.asset.prompts import SYSTEM, build_user_prompt
from app.assets.store import asset_path, ingest_asset
from app.core.config import get_settings
from app.models.core import Asset, AssetStatus, AssetType
from app.providers.imagegen import ImageProvider, build_image_provider
from app.providers.llm import LLMClient, build_llm
from app.qc.vision import check_image_asset

ALLOWED_TYPES = {"background", "prop", "icon", "cover"}
DEFAULT_SIZES = {
    "background": "1920x1088",
    "prop": "1024x1024",
    "icon": "1024x1024",
    "cover": "1080x1920",
}
NO_TEXT_SUFFIX = (
    "画面中不要出现任何文字、字母、数字、水印、logo 或 UI 标签；"
    "不要出现动漫角色或版权人物。"
)


class AssetAgentError(RuntimeError):
    pass


def _slug(value: str, fallback: str) -> str:
    slug = re.sub(r"[^a-z0-9]+", "-", value.lower()).strip("-")
    return slug[:80] or fallback


def _normalize_key(raw: str | None, asset_type: str, name: str) -> str:
    key = (raw or "").strip().lower()
    key = re.sub(r"[^a-z0-9:_-]+", "-", key).strip("-:")
    if not key:
        key = f"{asset_type}:{_slug(name, 'asset')}"
    if not key.startswith(f"{asset_type}:"):
        key = f"{asset_type}:{key}"
    return key[:120]


def _normalize_size(raw: str | None, asset_type: str) -> str:
    value = (raw or "").strip().lower()
    if re.fullmatch(r"\d{3,4}x\d{3,4}", value):
        return value
    return DEFAULT_SIZES[asset_type]


async def _existing_context(session: AsyncSession) -> tuple[list[dict], set[str]]:
    assets = list(
        await session.scalars(
            select(Asset)
            .where(Asset.status.in_([AssetStatus.APPROVED, AssetStatus.CANDIDATE]))
            .order_by(Asset.created_at.desc())
            .limit(80)
        )
    )
    context = [
        {
            "reuse_key": asset.reuse_key,
            "type": asset.type.value,
            "name": asset.name,
            "prompt": (asset.prompt or "")[:120],
        }
        for asset in assets
    ]
    return context, {asset.reuse_key for asset in assets}


async def plan_assets(
    session: AsyncSession,
    text: str,
    *,
    asset_type: AssetKind | None = None,
    count: int = 1,
    llm: LLMClient | None = None,
) -> list[AssetPlan]:
    settings = get_settings()
    count = max(1, min(count, settings.asset_agent_max_count))
    text = text.strip()
    if not text:
        raise AssetAgentError("text must not be empty")

    existing, existing_keys = await _existing_context(session)
    llm = llm or build_llm()
    result = await llm.chat_json(
        SYSTEM,
        build_user_prompt(
            text, asset_type=asset_type, count=count, existing=existing
        ),
        temperature=0.2,
        max_tokens=2000,
    )
    raw_assets = result.get("assets")
    if not isinstance(raw_assets, list):
        raise AssetAgentError("asset planner returned no assets list")

    plans: dict[str, AssetPlan] = {}
    for item in raw_assets:
        if not isinstance(item, dict):
            continue
        kind = asset_type or str(item.get("type", "")).lower()
        if kind not in ALLOWED_TYPES:
            continue
        name = str(item.get("name", "")).strip() or kind
        prompt = str(item.get("prompt", "")).strip()
        if not prompt:
            continue
        key = _normalize_key(item.get("reuse_key"), kind, name)
        if key in existing_keys:
            for asset in existing:
                if asset["reuse_key"] == key:
                    kind = asset["type"]
                    name = asset["name"]
                    break
        prompt = f"{prompt.rstrip('。.')}。{NO_TEXT_SUFFIX}"
        plans[key] = AssetPlan(
            type=kind,
            name=name[:200],
            reuse_key=key,
            prompt=prompt[:2000],
            size=_normalize_size(item.get("size"), kind),
            reason=str(item.get("reason", ""))[:500],
        )
        if len(plans) >= count:
            break

    if not plans:
        raise AssetAgentError(
            "文本没有产生可生成的演示素材；角色立绘和含文字卡片不走图片生成"
        )
    return list(plans.values())


async def generate_assets_from_text(
    session: AsyncSession,
    text: str,
    *,
    asset_type: AssetKind | None = None,
    count: int = 1,
    auto_approve: bool = False,
    check: bool | None = None,
    force: bool = False,
    llm: LLMClient | None = None,
    image_provider: ImageProvider | None = None,
) -> dict:
    settings = get_settings()
    check = settings.asset_agent_auto_check if check is None else check
    llm = llm or build_llm()
    provider = image_provider or build_image_provider()
    plans = await plan_assets(
        session, text, asset_type=asset_type, count=count, llm=llm
    )

    out_dir = Path(settings.asset_agent_tmp_dir)
    if not out_dir.is_absolute():
        out_dir = Path(__file__).resolve().parents[3] / out_dir
    out_dir.mkdir(parents=True, exist_ok=True)

    items: list[dict] = []
    for plan in plans:
        existing = await session.scalar(
            select(Asset).where(Asset.reuse_key == plan.reuse_key)
        )
        if (
            existing is not None
            and not force
            and existing.status in {AssetStatus.APPROVED, AssetStatus.CANDIDATE}
        ):
            items.append(
                {
                    "status": (
                        "reused"
                        if existing.status == AssetStatus.APPROVED
                        else "existing_candidate"
                    ),
                    "asset": existing,
                }
            )
            continue

        out_path = out_dir / f"{uuid4().hex}.png"
        await provider.generate(plan.prompt, out_path, plan.size)
        meta = {
            "agent_text": text,
            "plan": plan.model_dump(),
            "generated_at": datetime.now(timezone.utc).isoformat(),
        }
        asset = await ingest_asset(
            session,
            out_path,
            asset_type=AssetType(plan.type),
            name=plan.name,
            reuse_key=plan.reuse_key,
            source="asset_agent",
            status=AssetStatus.CANDIDATE,
            provider="volcengine" if settings.image_provider == "ark" else "mock",
            model=settings.ark_image_model,
            prompt=plan.prompt,
            tags=["generated", "asset_agent", plan.type],
            meta=meta,
        )
        await session.flush()

        if check:
            try:
                verdict = await check_image_asset(
                    asset_path(asset),
                    llm,
                    context=f"资产生成 Agent：{plan.reason or text}",
                    timeout_s=settings.qc_vision_timeout_s,
                )
                meta["qc"] = {
                    "passed": verdict["pass"],
                    "issues": verdict["issues"],
                    "model": settings.deepseek_model,
                    "checked_at": datetime.now(timezone.utc).isoformat(),
                }
                asset.meta = meta
                if auto_approve and verdict["pass"]:
                    asset.status = AssetStatus.APPROVED
            except Exception as exc:
                meta["qc"] = {
                    "passed": False,
                    "issues": [],
                    "error": str(exc)[:500],
                    "checked_at": datetime.now(timezone.utc).isoformat(),
                }
                asset.meta = meta
        elif auto_approve:
            asset.status = AssetStatus.APPROVED

        await session.commit()
        items.append({"status": "generated", "asset": asset})

    return {"text": text, "items": items, "plans": [plan.model_dump() for plan in plans]}

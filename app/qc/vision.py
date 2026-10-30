from __future__ import annotations

from pathlib import Path

from app.providers.llm import LLMClient, LLMError

SYSTEM = (
    "你是严格的视频质检员。只输出 JSON，不要解释、不要 Markdown。"
    "重点检查：角色是否被裁切或明显变形、字幕/卡片文字是否溢出或遮挡、"
    "画面是否与台词语义明显不符、是否有水印或生成伪影。"
    "底部字幕条是按时间分块显示的，可能只显示整句的一部分，句末标点出现在下一块是正常的；"
    "不要因为字幕只显示半句或缺少句末标点就判定溢出。"
    "大字卡片允许自动换行，只要文字完整落在卡片边界内就不算溢出。"
    "如果某一帧明显处于入场/退场转场（卡片部分出画、运动模糊、淡出/白闪），"
    "不要按文字溢出、裁切或生成伪影报告；只检查稳定停留帧。"
)

FRAME_SCHEMA = (
    '{"issues":[{"frame_index":1,"shot_seq":1,"type":"character_crop",'
    '"severity":"warning|error","detail":"具体问题","suggestion":"修复建议",'
    '"confidence":0.8}]}。没有问题时输出 {"issues":[]}。'
)


def _frame_context(frames: list[dict]) -> str:
    lines = []
    for index, frame in enumerate(frames, start=1):
        narration = str(frame.get("narration", ""))[:80]
        lines.append(
            f"{index}. 第{frame['seq']}镜头，{frame['section']}，"
            f"{frame['time_ms']}ms，卡片 {frame.get('card_type', '')}，"
            f"台词：{narration}"
        )
    return "\n".join(lines)


async def check_frames(
    frames: list[dict],
    llm: LLMClient,
    *,
    batch_size: int = 4,
    max_tokens: int = 2000,
    timeout_s: float = 180.0,
    blocking: bool = False,
) -> list[dict]:
    issues: list[dict] = []
    for offset in range(0, len(frames), batch_size):
        batch = frames[offset : offset + batch_size]
        user = (
            f"以下是从同一成片抽出的 {len(batch)} 帧，按顺序编号：\n"
            f"{_frame_context(batch)}\n\n"
            "再次强调：底部字幕是分块显示，半句/缺句末标点是正常的；"
            "处于入场/退场转场的帧（卡片部分出画、模糊、淡出）不要报文字溢出/裁切/伪影；"
            "只报告稳定停留帧里肉眼可见的文字越出边框、遮挡、缺字、角色裁切或明显变形。\n"
            f"逐帧检查并只输出 JSON：{FRAME_SCHEMA}"
        )
        try:
            result = await llm.chat_vision_json(
                SYSTEM,
                user,
                [Path(frame["path"]) for frame in batch],
                temperature=0.1,
                max_tokens=max_tokens,
                timeout_s=timeout_s,
            )
        except LLMError as exc:
            issues.append(
                {
                    "check_item": "vision.api",
                    "level": "ERROR" if blocking else "WARNING",
                    "message": f"视觉质检调用失败：{exc}",
                    "detail": {"batch_offset": offset},
                }
            )
            continue

        raw_issues = result.get("issues") or []
        if not isinstance(raw_issues, list):
            raw_issues = []
        if result.get("verdict") == "error" and not raw_issues:
            raw_issues = [
                {
                    "type": "vision_error",
                    "severity": "error",
                    "detail": "模型判定为 error 但未给出原因",
                }
            ]
        for item in raw_issues:
            try:
                index = int(item.get("frame_index", 1)) - 1
            except (TypeError, ValueError):
                index = 0
            frame = batch[min(max(index, 0), len(batch) - 1)]
            severity = str(item.get("severity", "warning")).lower()
            level = (
                "ERROR"
                if blocking and severity == "error"
                else "WARNING"
            )
            issues.append(
                {
                    "check_item": f"vision.{item.get('type', 'frame')}",
                    "level": level,
                    "message": str(item.get("detail", "视觉质检发现问题")),
                    "evidence_path": frame["path"],
                    "detail": {
                        "shot_seq": frame["seq"],
                        "time_ms": frame["time_ms"],
                        "suggestion": str(item.get("suggestion", "")),
                        "confidence": item.get("confidence"),
                        "frame_index": item.get("frame_index"),
                    },
                }
            )
    return issues


ASSET_SCHEMA = (
    '{"pass":true,"issues":[{"type":"crop|watermark|text|style|character",'
    '"severity":"warning|error","detail":"具体问题","suggestion":"处理建议",'
    '"confidence":0.8}]}。没有问题时输出 {"pass":true,"issues":[]}。'
)


async def check_image_asset(
    image: Path,
    llm: LLMClient,
    *,
    context: str,
    max_tokens: int = 1200,
    timeout_s: float = 180.0,
) -> dict:
    user = (
        f"这是准备入库的图片资产。背景信息：{context or '无'}。\n"
        "检查角色是否完整、是否被裁切、是否有水印、是否有文字伪影、"
        f"风格是否适合科普视频。只输出 JSON：{ASSET_SCHEMA}"
    )
    result = await llm.chat_vision_json(
        SYSTEM,
        user,
        [image],
        temperature=0.1,
        max_tokens=max_tokens,
        timeout_s=timeout_s,
    )
    issues = result.get("issues") or []
    if not isinstance(issues, list):
        issues = []
    return {
        "pass": bool(result.get("pass", not issues)),
        "issues": issues,
    }

from __future__ import annotations

SYSTEM = """你是科普视频的视觉素材规划 Agent。
把输入文本转换成 1-3 个无文字的演示图片请求，供视频舞台使用。

硬约束：
- 只能选择 background、prop、icon、cover 四类；绝对不能生成角色立绘、动漫人物、洛琪希或任何版权角色。
- 画面中绝对不能出现文字、字母、数字、水印、logo、UI 标签；需要文字的信息卡片由 HTML 负责。
- 只生成可复用的通用素材：背景、桌面物件、图标、封面底图。
- 优先复用已有资产；如果语义匹配，直接使用已有 reuse_key。
- prompt 要描述构图、风格、颜色、留白和视角，并明确 no text / no watermark。
- 风格必须服务内容：先判断主题（科学/历史/计算机/自然等），再选色调、材质、线条和视角；不要给同一期素材混用冲突风格（写实照片 / 扁平插画 / 赛博霓虹）。
- 同一期素材保持统一的光线、材质和配色；默认延续项目的纸纹 + 木质舞台 + 手绘/扁平插画语言，除非内容明确要求其他场景。
- 只输出 JSON，不要 Markdown。"""


def build_user_prompt(
    text: str,
    *,
    asset_type: str | None,
    count: int,
    existing: list[dict],
) -> str:
    forced = f"优先类型：{asset_type}" if asset_type else "类型由你判断"
    assets = "\n".join(
        f"- {item['reuse_key']} | {item['type']} | {item['name']} | {item['prompt']}"
        for item in existing
    ) or "（暂无已入库素材）"
    return f"""输入文本：
{text}

生成数量：{count}
{forced}

已有资产（可按语义复用 reuse_key）：
{assets}

输出 JSON：
{{"assets":[{{"type":"prop","name":"简洁中文名","reuse_key":"prop:stable-semantic-key","prompt":"视觉描述，必须包含 no text, no letters, no watermark","size":"1024x1024","reason":"为什么需要这个素材/为什么复用"}}]}}

要求：
- reuse_key 使用小写英文/数字/连字符，并以类型前缀开头，例如 prop:blue-light-prism。
- 如果复用已有资产，reuse_key 必须与列表中的完全一致。
- size：background 用 1920x1088，prop/icon 用 1024x1024，cover 用 1080x1920。
- 不要输出任何角色、人物、动漫或版权形象。
- prompt 里写清与本期主题匹配的风格（色调、材质、线条、视角），同组素材保持一致，不要混用写实照片、扁平插画、赛博霓虹等冲突风格。"""

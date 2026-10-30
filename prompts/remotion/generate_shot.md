请根据下面的剧集上下文和镜头数据，生成 Remotion 镜头组件。

$skill

## 剧集上下文

标题：$title
主题：$topic
文章摘要：$summary
大纲：
$outline

## 镜头

$shot_json

## 可用资产

$assets_json

## 上一镜头结尾（用于衔接，可为空）

$previous_tail

## 校验错误（首次为空）

$error_feedback

## 卡片与动效硬规则

- 不使用 `Card`/`Label`/`Caption`/`Board`；画面文字统一用 `TerminalCard`。
- **卡片按需**：不是每个镜头都要卡片，纯演示镜头可以完全不放；一期至少 1/3 镜头不放卡，有卡镜头不超过 2/3。
- 输入 JSON 的 `card_style` 已排期：为 `null` 时**禁止使用 TerminalCard**，做纯演示镜头；非 null 时给出 `variant`/`tone`/`transition`，用卡必须严格遵守，也可以不用卡。
- 卡片风格轮换：`terminal`/`editor`/`hud`/`console`/`snippet`/`chat`；`tone` 在 `navy`/`purple`/`mint`/`rose` 中；按 `card_style` 实现，不要自己换。
- 同一时刻只显示一张卡；多段文本用嵌套 `<Sequence>` 依次切换。
- 切换动画至少 3 种配方：横向冲入、缩放冲击、翻转（rotateY）、坠落回弹、揭示（reveal wipe）、上推；连续卡片不重复同一种。
- 动效幅度下限：位移 ≥300px、缩放变化 ≥0.3、旋转 ≥5° 或 rotateY ≥45°；spring 允许过冲。
- 卡片文本 20–90 字，优先用 `narration`/`card.text`，用 `lines` 拆成 2–4 行；不得扩写原文，不新增事实/数字/结论。
- 卡片不要遮挡角色脸/手，不要压到 y 940–1080 字幕区；底部字幕由 Python 统一叠加，不要 import `Subtitle`。

## 风格硬规则

- 卡片统一用二次元终端/代码块语言（深色半透明玻璃、发光细边、圆角、网格/扫描线、少量星星），但演示图形仍要内容准确。
- 同一期保持同一套终端 UI 家族；variant/tone 可以变化，不要突然变成写实照片或手绘黑板。
- 终端霓虹只用于卡片与状态装饰，不要把演示主体做成与内容无关的赛博城市/故障条纹/机器人。
- 背景/贴图选语义最匹配的资产，不要只按颜色挑；图形优先抽象示意，不要伪造照片级细节。

请只输出 JSON：{"schema_version":"1","component_name":"$component_name","code":"完整 TSX 文件内容","summary":"一句话说明"}。

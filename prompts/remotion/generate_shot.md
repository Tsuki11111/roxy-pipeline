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

- 不使用 `TerminalCard`/`Card`/`Label`/`Caption`/`Board`；画面文字统一用 `PaperCard`（Claude 暖纸卡）。
- **卡片按需**：不是每个镜头都要卡片，纯演示镜头可以完全不放；一期至少 1/3 镜头不放卡，有卡镜头不超过 2/3。
- 输入 JSON 的 `card_style` 已排期：为 `null` 时**禁止使用 PaperCard**，做纯演示镜头；非 null 时给出 `variant`/`tone`/`transition`，用卡必须严格遵守，也可以不用卡。
- 卡片风格轮换：`note`/`quote`/`index`/`letter`/`sticky`/`specimen`；`tone` 在 `cream`/`sand`/`peach`/`sage` 中；按 `card_style` 实现，不要自己换。
- 同一时刻只显示一张卡；多段文本用嵌套 `<Sequence>` 依次切换。
- 切换动画至少 3 种配方：横向冲入、缩放冲击、翻转（rotateY）、坠落回弹、揭示（reveal wipe）、上推；连续卡片不重复同一种。
- 动效幅度下限：位移 ≥300px、缩放变化 ≥0.3、旋转 ≥5° 或 rotateY ≥45°；spring 允许过冲。
- 卡片文本 20–90 字，优先用 `narration`/`card.text`，用 `lines` 拆成 2–4 行；不得扩写原文，不新增事实/数字/结论。
- 卡片不要遮挡角色脸/手，不要压到 y 940–1080 字幕区；底部字幕由 Python 统一叠加，不要 import `Subtitle`。

## 角色动效硬规则

- 输入有 `character` 时必须画出 Roxy 并让它动起来；`<Character>` 不能只有 `src/side/height`。
- 入场从角色侧屏幕外冲入，280–360ms：`offsetX` ±(400–600)→0、`opacity` 0→1、`scale` 0.94→1、`rotate` ±2°→0，用 spring。
- 停留要有呼吸/轻摆（`offsetX` 用 `Math.sin(frame/18)*(4–10)`）；卡片或关键图形出现时至少做一次手势/前倾/让位（offsetX ±20–60 或 scale 1.01–1.04）。
- 角色可以被卡片局部遮挡，但不能盖住卡片文字；同一镜头只用一张角色图。

## 风格硬规则

- 卡片统一用 Claude 纸卡语言：暖纸、墨字、陶土/鼠尾草少量强调、宋体标题、细线、手绘星或下划线；不要深色玻璃、霓虹、终端 UI。
- 背景由 `Stage` 统一提供暖纸底色，不要传 `bg`/`floor`，不要木地板或深色舞台。
- 同一期保持纸/墨/陶土家族；variant/tone 可以变化，但不要突然变成写实照片或终端控制台。
- 演示图形仍要内容准确：讲天空就画天空/光谱，讲 Agent 就画节点/流程；图形优先抽象示意，不要伪造照片级细节。

请只输出 JSON：{"schema_version":"1","component_name":"$component_name","code":"完整 TSX 文件内容","summary":"一句话说明"}。

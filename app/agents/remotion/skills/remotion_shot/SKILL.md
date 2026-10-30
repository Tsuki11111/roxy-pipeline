---
name: remotion-shot
description: 为单个分镜生成可编译的 Remotion/React 镜头组件（自由 TSX，固定依赖宇宙）
---

# Remotion Shot Skill

## 目标

把 Python 传入的单个镜头（`shot`）写成一个 Remotion Composition 组件。你只写镜头画面，不写 Root、不写项目配置、不改依赖。

## 输出

只返回 JSON，不要 Markdown 代码块：

```json
{
  "schema_version": "1",
  "component_name": "Shot_0001",
  "code": "import ...; export const Shot_0001 = () => { ... }",
  "summary": "一句话说明这镜头怎么表达"
}
```

- `component_name` 必须与输入中的 `component_name` 完全一致。
- `code` 必须是完整 TSX 文件内容，导出同名 React 组件。
- 不要输出 `Root.tsx`、`index.ts`、`package.json` 或任何配置文件。

## 可用环境

- 1920×1080、25fps；`durationInFrames` 已由 Python 注入 Composition，组件只按 `useCurrentFrame()` 渲染。
- 可用依赖：`react`、`remotion`、`@remotion/*`、`../components/*`、`../theme`。
- 固定组件库（可选）：
  - `Stage`：背景、地板、children；支持 `bg`/`floor` props。
  - `Character`：立绘；`src` 用资产清单里的 `staticFile` 名，支持 side/height/bottom/offsetX/opacity/blur。
  - `TerminalCard`：**二次元终端/代码块卡**；`variant` 支持 `terminal`/`editor`/`hud`/`console`/`snippet`/`chat`，`tone` 支持 `navy`/`purple`/`mint`/`rose`；支持 `text`/`lines`/`title`/`filename`、`left`/`top`/`width`/`minHeight`、`opacity`/`scale`/`translateX`/`translateY`/`rotate`/`rotateY`/`reveal`、`accent`、`cursor`。
  - `Overlay`、`Progress`、`AgentLoop`、`ToolChips`、`RobotIcon`。
- **卡片不是每个镜头都必须有**：纯图形/演示镜头可以完全不放卡；按内容需要决定。
- **不要使用 `Label`/`Caption`/`Card`/`Board`**：画面文字统一用 `TerminalCard`，不要再用旧白卡、关键词标签或黑板卡。
- **不要自己画底部字幕**：Python 会在 Root 里统一叠加 `SubtitleTrack`（bottom 40）。生成代码不要 import `Subtitle`，也不要在 y > 940 放文字或图表。
- 资产只能使用输入 JSON 的 `assets` 列表中的 `static_file`，写法：`staticFile("assets/xxx.png")`。不要引用 `public/` 以外的路径，不要外链 URL。
- 不能新增 npm 依赖；不能使用 `node:*`、`fs`、`child_process`、`http`、`https`、`net`、`eval`、`Function`、动态 `import()` 或 `process`。
- 不能使用 `Date.now()`、`Math.random()`、CSS `@keyframes`/`transition`/`animation`；所有动画必须由 `useCurrentFrame()`、`interpolate()`、`spring()` 计算，保证确定性。

## 代码规模

- 单个镜头代码控制在 **240 行以内**，硬上限 320 行；`code` 字符串不超过 **9000 字符**。
- 输出超长会被截断，整镜头作废；宁可少画几个元素，也不要堆砌。
- 不要硬编码几十个坐标/粒子/路径点；用循环、公式或 `Array.from({length: n})` 生成。
- 只写这个镜头实际用到的代码，不留未使用的组件、变量或大段注释。

## 卡片使用（强约束）

- **卡片按需使用，不是每个镜头都要有**；纯图形/演示镜头可以完全不放卡，避免每段都变成“卡片切换”。
- 一期里至少 1/3 的镜头不做卡片，直接把演示画面做完整；有卡的镜头也不超过 2/3。
- 同一时刻只显示一张卡；多段文本用嵌套 `<Sequence>` 依次切换，不要叠卡。
- 卡片与演示可以交替（卡退场 → 演示入场），也可以并置（卡占一侧、演示占另一侧）；同一期两种都用。
- 底部 y 940–1080 只留给 Python 叠加的字幕，不放卡片/图形。

## 卡片风格（强约束）

`TerminalCard` 有 6 种样式，按内容轮换，不要整期只用一种：

- `terminal`：mac 三色圆点 + `roxy@terminal` 标题 + 命令行/输出；适合“执行、运行、结论”。
- `editor`：文件名 tab + 行号 + TSX 标签；适合“代码、步骤、配置”。
- `hud`：二次元全息面板，切角边框 + 状态字 + 星形装饰；适合“扫描、分析、数据”。
- `console`：`›` 前缀 + LIVE 标记 + 日志流；适合“过程、事件、连续输出”。
- `snippet`：紧凑代码块 + 文件名 + copy 标签；适合“短结论、关键一行”。
- `chat`：AI 头像 + 输出行；适合“对话、解释、自问自答”。

- 输入 JSON 的 `card_style` 由 Python 轮换指定：为 `null` 时**禁止使用 TerminalCard**，这一镜必须做纯演示；非 null 时给出 `variant`/`tone`/`transition`，用卡就必须严格遵守，不用卡也可以。
- 同一期至少用 **3 种 variant**、**2 种 tone**（`navy`/`purple`/`mint`/`rose`）；卡片分布由 Python 排期，不要给每个镜头都塞卡。
- 二次元终端画风：深色半透明玻璃、发光细边、圆角、细网格/扫描线、少量星星/贴纸；不要纯黑硬边或写实 UI。
- 卡片色调服务内容：天空/光学科普用蓝紫/薄荷，计算机主题用紫/青，避免整期只有一种颜色。

## 切换动效（强约束）

同一期至少用 **3 种不同切换配方**，连续两张卡不能重复同一种：

1. **横向冲入**：`translateX ±(400–600)` + `rotate ±6°` + spring。
2. **缩放冲击**：`scale 0.5 → 1.06 → 1`，配合 opacity 0→1。
3. **翻转**：`rotateY 70 → 0` + `translateX ±200`，带 perspective。
4. **坠落回弹**：`translateY -500 → 0`，spring 允许明显过冲。
5. **揭示**：`reveal 0 → 1`（clip wipe）+ `scale 0.94 → 1`。
6. **上推**：旧卡 `translateY -400` 退出，新卡从 `+400` 推入。

- 动效幅度下限：位移 ≥300px、缩放变化 ≥0.3、旋转 ≥5° 或 rotateY ≥45°。
- `card_style.transition` 对应：`slide`=横向冲入、`zoom`=缩放冲击、`flip`=翻转、`drop`=坠落回弹、`reveal`=揭示、`push`=上推；必须按指定配方实现。
- 文本卡与演示段错开 3–8 帧切换；卡内文字逐行 stagger（每行延迟 4–8 帧）。
- 同一镜头里至少两种不同缓动节奏，不要所有元素同一个 spring。

## 长段文本（强约束）

- 卡片文本用**长段**：优先放 `narration` 或 `card.text`，20–90 字；用 `lines` 拆成 2–4 行，不要缩成关键词。
- 超过 90 字拆成两张卡或两段场景；同一时刻仍只显示一张卡。
- **不得扩写原文**：可以拆句、换行、调序，但不要新增原文没有的事实、数字或结论；原句短就保持短。
- 卡片是文字的唯一载体；不要再加 `Label`/`Caption`/自绘关键词标签。
- `editor` 用行号，`console` 用 `›`，`chat` 用 `#`，`hud` 用状态标题；让文字看起来像终端输出而不是海报文案。



## 风格与内容（强约束）

- **先读标题、主题、摘要和大纲，再决定演示画面的视觉语言**：色调、材质、线条、图形风格都要服务内容。
- 卡片统一使用二次元终端/代码块语言（`TerminalCard`），但演示图形仍要内容准确：讲天空就画天空/光谱，讲 Agent 就画节点/终端/流程。
- 同一期保持同一套“终端 UI 家族”：同一组圆角、发光边、网格/扫描线、字体；variant/tone 可以变化，但不要突然变成写实照片或手绘黑板。
- 终端卡的霓虹/发光只用于卡片与状态装饰；不要把演示主体做成与内容无关的赛博城市、故障条纹或机器人。
- 背景、贴图、角色必须与当期主题匹配；资产清单里有多个背景时选语义最合适的那张，不要只按颜色挑。
- 图形优先做“抽象示意”（箭头、节点、光谱、几何），不要伪造照片级细节或与内容不符的真实场景。

## 配色与对比度（强约束）

- 背景默认是浅色纸纹（`PAPER` 约 `#f7f3ea`），正文色必须用 `INK`（深灰）或 `rgba(42,42,51,0.85)`。
- 白字/浅色字只能放在 **alpha ≥ 0.75 的深色实底**上（如 `#141824`、`rgba(20,24,36,0.88)`）；禁止把浅色文字直接铺在浅色背景或浅蓝半透明面板上。
- 卡片文字、坐标轴、注释同样适用：深色卡上用浅色字，浅色底上用深色字；浅底 + 浅字一律视为错误。
- 自绘面板二选一：浅色实底 + 深色字，或深色实底 + 浅色字；不要用低透明度面板托浅色字。
- 解释性文字优先放进 `TerminalCard`，不要手写大段浅色文字。

## 角色

- 输入 JSON 有 `character` 时必须画出 Roxy（`Character` 组件，可用 `src`/`side`/`height`/`offsetX`）；可以小幅位移或缩放，但不要让整个镜头没有角色。
- 只有输入 `character` 为 `null` 时才允许纯图形镜头。

## 视觉要求

1. 这是竖屏短视频里的一个镜头，所有元素必须在 1920×1080 安全区内；底部 y 940–1080 是字幕区，不要放内容。
2. 优先用画面表达输入里的概念：时间线、流程图、终端输出、浏览器步骤、工具 chip、角色动作，不要只堆文字。
3. 角色图、贴图和背景必须来自 `assets`；没有合适素材时用 React/SVG 画图形，不要引用外部图片。
4. 画面文字用 `TerminalCard` 承载长段文本；卡片按需，不是每个镜头都要有。
5. 使用 `spring`/`interpolate` 做自然入场；卡片切换幅度要大（位移 ≥300px、缩放变化 ≥0.3、旋转 ≥5° 或 rotateY ≥45°），并轮换不同切换配方。
6. 单镜头没有音频，不要尝试播放音频。

## 代码骨架

```tsx
import {Sequence, interpolate, spring, staticFile, useCurrentFrame, useVideoConfig} from 'remotion';
import {Stage} from '../components/Stage';
import {Character} from '../components/Character';
import {TerminalCard} from '../components/TerminalCard';

const CardScene = ({duration}: {duration: number}) => {
  const frame = useCurrentFrame();
  const {fps} = useVideoConfig();
  // 配方示例：坠落回弹；其他镜头可换横向冲入/缩放冲击/翻转/揭示
  const drop = spring({frame, fps, config: {damping: 10, stiffness: 90}});
  const exit = interpolate(frame, [duration - 10, duration], [0, 1], {
    extrapolateLeft: 'clamp',
    extrapolateRight: 'clamp',
  });
  return (
    <TerminalCard
      variant="editor"
      tone="purple"
      filename="why-blue.tsx"
      left={140}
      top={150}
      width={1180}
      lines={['太阳光看着是白的，', '其实是由七种颜色的光混合而成的。']}
      opacity={1 - exit}
      translateY={(1 - drop) * -520 - exit * 160}
      scale={0.7 + drop * 0.3}
      rotate={(1 - drop) * -5}
      cursor={false}
    />
  );
};

export const Shot_0001 = () => {
  const {durationInFrames} = useVideoConfig();
  const cardFrames = Math.round(durationInFrames * 0.5);

  return (
    <Stage>
      <Character src="assets/xxx.png" side="right" />
      <Sequence from={0} durationInFrames={cardFrames}>
        <CardScene duration={cardFrames} />
      </Sequence>
      <Sequence from={cardFrames - 4} durationInFrames={durationInFrames - cardFrames + 4}>
        <svg style={{position: 'absolute', left: 240, top: 180, width: 1440, height: 660}}>
          {/* 光谱/波形/流程演示；这个镜头也可以完全不放卡 */}
        </svg>
      </Sequence>
    </Stage>
  );
};
```

其他卡片镜头换用 `terminal`/`hud`/`console`/`snippet`/`chat`，并换一种切换配方；不要让整期都用同一种卡和同一种滑入。

## 常见错误

- 使用了资产列表外的图片 → 渲染失败。
- 导出了错误的组件名 → Root 找不到组件。
- 使用 CSS 动画/`Date.now`/随机数 → 渲染不可复现。
- 每个镜头都放卡片 → 纯演示镜头可以没有卡；一期至少 1/3 镜头不放卡。
- 整期只用 `terminal` 一种卡 → 至少 3 种 variant、2 种 tone，连续卡片不重复。
- 所有卡片都用同一种横向滑入 → 至少 3 种切换配方（冲入/缩放/翻转/坠落/揭示/上推）。
- 卡片切换位移 <300px、缩放变化 <0.3、没有旋转 → 动效幅度太小。
- 把长段台词缩成关键词 → 保留长段，用 `TerminalCard` 承载。
- 卡片遮挡角色脸/手或压到 y 940–1080 字幕区 → 调整位置或分段。
- 使用 `Card`/`Label`/`Caption`/`Board` 做画面文字 → 统一改用 `TerminalCard`；旧组件会被生成检查拦下。
- 把整段台词塞进一张卡导致溢出 → 拆成 2–3 行或两张卡，不要删成关键词。
- 引入未安装的包 → 编译失败。

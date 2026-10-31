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
  - `Stage`：Claude 暖纸背景（纸纹、底部浅阴影、手绘星）；直接包 children，不要传 `bg`/`floor`。
  - `Character`：立绘；`src` 用资产清单里的 `staticFile` 名，支持 `side`（left/center/right）/`height`/`bottom`/`offsetX`/`opacity`/`blur`/`scale`/`rotate`。
  - `PaperCard`：**Claude 纸卡**；`variant` 支持 `note`/`quote`/`index`/`letter`/`sticky`/`specimen`，`tone` 支持 `cream`/`sand`/`peach`/`sage`；支持 `text`/`lines`/`title`/`meta`/`mark`、`left`/`top`/`width`/`minHeight`、`opacity`/`scale`/`translateX`/`translateY`/`rotate`/`rotateY`/`reveal`、`accent`。
  - `Overlay`、`Progress`、`AgentLoop`、`ToolChips`、`RobotIcon`。
- **卡片不是每个镜头都必须有**：纯图形/演示镜头可以完全不放卡；按内容需要决定。
- **不要使用 `TerminalCard`/`Label`/`Caption`/`Card`/`Board`**：画面文字统一用 `PaperCard`；终端卡、旧白卡、关键词标签、黑板卡全部删掉。
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

`PaperCard` 有 6 种纸卡样式，按内容轮换，不要整期只用一种：

- `note`：暖纸解释卡，细墨线边框 + 手绘星；适合一段完整解释。
- `quote`：稍深的纸色 + 大号宋体引号；适合一句结论、引用或自问自答。
- `index`：顶部陶土短线 + 横向行线；适合步骤、清单、两三条要点。
- `letter`：信纸版式，左侧陶土边线和宽留白；适合叙述、回忆、较长段落。
- `sticky`：浅桃色便签，轻阴影；适合一句提醒或旁注。
- `specimen`：样本卡，上下细线与标题/字数；适合“概念样本、定义、对照”。

- 输入 JSON 的 `card_style` 由 Python 轮换指定：为 `null` 时**禁止使用 PaperCard**，这一镜必须做纯演示；非 null 时给出 `variant`/`tone`/`transition`，用卡就必须严格遵守，不用卡也可以。
- 同一期至少用 **3 种 variant**、**2 种 tone**（`cream`/`sand`/`peach`/`sage`）；卡片分布由 Python 排期，不要给每个镜头都塞卡。
- Claude 纸卡语言：暖纸、墨字、陶土强调、宋体标题、细线、手绘星/下划线；不要深色玻璃、霓虹、终端 UI、故障扫描线。
- 纸卡可以轻微旋转（-1.5°–1.5°）和错位投影，但不要每张都贴同一种胶带或贴纸。

## 背景与字幕

- 背景由 `Stage` 统一渲染：暖纸底色 + 细纸纹 + 底部一条浅阴影和手绘星；不要传 `bg`/`floor`，不要再用木地板或深色舞台。
- 底部字幕由 `SubtitleTrack` 统一叠加：暖纸底、墨字、左侧陶土短线；生成代码不画字幕。

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
- `note`/`letter` 用长段落；`index` 用 2–3 条短行；`quote` 用一句结论；`specimen` 用“定义 + 一句解释”；语气像笔记，不是海报文案。

## 风格与内容（强约束）

- **先读标题、主题、摘要和大纲，再决定演示画面的视觉语言**：色调、材质、线条、图形风格都要服务内容。
- 卡片统一使用 Claude 纸卡语言（`PaperCard`：暖纸、墨字、陶土强调、宋体标题、细线、手绘星）；演示图形仍要内容准确：讲天空就画天空/光谱，讲 Agent 就画节点/流程。
- 同一期保持同一套“纸 / 墨 / 陶土”家族：同一组纸色、边框、圆角、字体；variant/tone 可以变化，但不要突然变成深色终端、霓虹或写实照片。
- 手绘星、下划线、箭头只做少量点缀，不要堆满画面。
- 背景由 `Stage` 统一提供暖纸底色；不要再用 Wood/暗色舞台/终端网格。
- 图形优先做“抽象示意”（箭头、节点、光谱、几何），不要伪造照片级细节或与内容不符的真实场景。

## 配色与对比度（强约束）

- 背景是暖纸（`PAPER` 约 `#f3eee3`），正文用墨色 `INK`（`#23201b`）或 `INK_SOFT`（`#5f574b`）。
- 浅色纸卡上用深墨字；禁止在浅纸上用白字/浅色字。深色仅用于少量文字和线条，不做大块深色面板。
- 强调色只用陶土 `#bf5b3b` 和鼠尾草 `#77856f`，面积要小：下划线、短线、星形、单个词。
- 卡片文字、坐标轴、注释同样适用：纸底墨字，保持足够对比度。
- 解释性文字优先放进 `PaperCard`，不要手写大段浅色文字。

## 角色与动效（强约束）

- 输入 JSON 有 `character` 时必须画出 Roxy，并且**整镜不能静止**；`<Character>` 不能只写 `src/side/height`。
- 入场：从角色所在侧屏幕外冲入，280–360ms；`offsetX` 从 ±(400–600) 回到 0，`opacity` 0→1，`scale` 0.94→1，`rotate` ±2°→0；用 spring（damping 12–16）。
- 停留：保留呼吸/轻摆，`offsetX` 用 `Math.sin(frame / 18) * (4–10)`，`scale` 1±0.008；不要整镜定死。
- 动作节点：卡片或关键图形出现时，至少做一次手势/前倾/让位，例如 `offsetX` 再偏 ±(20–60) 或 `scale` 1.01–1.04，持续 8–16 帧。
- 角色默认 zIndex 3，卡片 zIndex 8；角色可以被卡片局部遮挡，但不能盖住卡片文字，也不要和卡片抢同一侧。
- 同一镜头只用一张角色图；换姿势靠不同镜头的 asset，不要在同一镜里切换 src。
- 只有输入 `character` 为 `null` 时才允许纯图形镜头。

```tsx
const enter = spring({frame, fps, config: {damping: 14, stiffness: 110}});
const idle = Math.sin(frame / 18) * 8;
const gesture = spring({frame: frame - 24, fps, config: {damping: 12, stiffness: 90}});

<Character
  src="assets/xxx.png"
  side="left"
  height={1000}
  offsetX={(1 - enter) * -440 + idle + gesture * 26}
  opacity={Math.min(1, enter * 1.6)}
  scale={0.94 + enter * 0.06 + gesture * 0.02}
  rotate={(1 - enter) * -2}
/>
```

## 视觉要求

1. 这是竖屏短视频里的一个镜头，所有元素必须在 1920×1080 安全区内；底部 y 940–1080 是字幕区，不要放内容。
2. 优先用画面表达输入里的概念：时间线、流程图、终端输出、浏览器步骤、工具 chip、角色动作，不要只堆文字。
3. 角色图和贴图必须来自 `assets`；背景由 `Stage` 统一提供，不要传 bg/floor；没有合适素材时用 React/SVG 画图形，不要引用外部图片。
4. 画面文字用 `PaperCard` 承载长段文本；卡片按需，不是每个镜头都要有。
5. 使用 `spring`/`interpolate` 做自然入场；卡片切换幅度要大（位移 ≥300px、缩放变化 ≥0.3、旋转 ≥5° 或 rotateY ≥45°），并轮换不同切换配方。
6. 单镜头没有音频，不要尝试播放音频。

## 代码骨架

```tsx
import {Sequence, interpolate, spring, staticFile, useCurrentFrame, useVideoConfig} from 'remotion';
import {Stage} from '../components/Stage';
import {Character} from '../components/Character';
import {PaperCard} from '../components/PaperCard';

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
    <PaperCard
      variant="note"
      tone="cream"
      title="为什么是蓝的？"
      left={140}
      top={150}
      width={1180}
      text="太阳光看着是白的，其实是由七种颜色的光混合而成的。"
      mark="七种颜色"
      opacity={1 - exit}
      translateY={(1 - drop) * -520 - exit * 160}
      scale={0.7 + drop * 0.3}
      rotate={(1 - drop) * -5}
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

其他卡片镜头换用 `note`/`quote`/`index`/`letter`/`sticky`/`specimen`，并换一种切换配方；不要让整期都用同一种纸卡和同一种滑入。

## 常见错误

- 使用了资产列表外的图片 → 渲染失败。
- 导出了错误的组件名 → Root 找不到组件。
- 使用 CSS 动画/`Date.now`/随机数 → 渲染不可复现。
- 每个镜头都放卡片 → 纯演示镜头可以没有卡；一期至少 1/3 镜头不放卡。
- 整期只用 `note` 一种纸卡 → 至少 3 种 variant、2 种 tone，连续卡片不重复。
- 使用深色终端/霓虹/玻璃卡 → 这一版统一 Claude 暖纸卡，用 `PaperCard`。
- 所有卡片都用同一种横向滑入 → 至少 3 种切换配方（冲入/缩放/翻转/坠落/揭示/上推）。
- 卡片切换位移 <300px、缩放变化 <0.3、没有旋转 → 动效幅度太小。
- 把长段台词缩成关键词 → 保留长段，用 `PaperCard` 承载。
- 卡片遮挡角色脸/手或压到 y 940–1080 字幕区 → 调整位置或分段。
- 使用 `TerminalCard`/`Card`/`Label`/`Caption`/`Board` 做画面文字 → 统一改用 `PaperCard`；旧组件会被生成检查拦下。
- 把整段台词塞进一张卡导致溢出 → 拆成 2–3 行或两张卡，不要删成关键词。
- 引入未安装的包 → 编译失败。

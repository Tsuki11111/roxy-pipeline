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
  - `Card`：`chat_bubble`/`terminal`/`browser`/`icon`/`pure_text`；支持 `lines`/`reveal`。
  - `Overlay`、`Subtitle`、`Progress`、`AgentLoop`、`ToolChips`、`RobotIcon`。
- 资产只能使用输入 JSON 的 `assets` 列表中的 `static_file`，写法：`staticFile("assets/xxx.png")`。不要引用 `public/` 以外的路径，不要外链 URL。
- 不能新增 npm 依赖；不能使用 `node:*`、`fs`、`child_process`、`http`、`https`、`net`、`eval`、`Function`、动态 `import()` 或 `process`。
- 不能使用 `Date.now()`、`Math.random()`、CSS `@keyframes`/`transition`/`animation`；所有动画必须由 `useCurrentFrame()`、`interpolate()`、`spring()` 计算，保证确定性。

## 代码规模

- 单个镜头代码控制在 **180 行以内**，硬上限 300 行；`code` 字符串不超过 **7000 字符**。
- 输出超长会被截断，整镜头作废；宁可少画几个元素，也不要堆砌。
- 不要硬编码几十个坐标/粒子/路径点；用循环、公式或 `Array.from({length: n})` 生成。
- 只写这个镜头实际用到的代码，不留未使用的组件、变量或大段注释。

## 配色与对比度（强约束）

- 背景默认是浅色纸纹（`PAPER` 约 `#f7f3ea`），正文色必须用 `INK`（深灰）或 `rgba(42,42,51,0.85)`。
- 白字/浅色字只能放在 **alpha ≥ 0.75 的深色实底**上（如 `#141824`、`rgba(20,24,36,0.88)`）；禁止把浅色文字直接铺在浅色背景或浅蓝半透明面板上。
- 标签、坐标轴、注释同样适用：要么深色字，要么加底板。浅底 + 浅字一律视为错误。
- 自绘面板二选一：浅色实底 + 深色字，或深色实底 + 浅色字；不要用低透明度面板托浅色字。
- 解释性文字优先放进 `Card` 组件（自带可读底色），不要手写大段浅色文字。

## 角色

- 输入 JSON 有 `character` 时必须画出 Roxy（`Character` 组件，可用 `src`/`side`/`height`/`offsetX`）；可以小幅位移或缩放，但不要让整个镜头没有角色。
- 只有输入 `character` 为 `null` 时才允许纯图形镜头。

## 视觉要求

1. 这是竖屏短视频里的一个镜头，所有元素必须在 1920×1080 安全区内，不遮挡字幕（底部 104px 以上留空）。
2. 优先用画面表达输入里的概念：时间线、流程图、终端输出、浏览器步骤、工具 chip、角色动作，不要只堆文字。
3. 角色图、贴图和背景必须来自 `assets`；没有合适素材时用 React/SVG 画图形，不要引用外部图片。
4. 字幕、卡片文案以输入为准，不要改事实、不要新增原文没有的数字或结论。
5. 使用 `spring`/`interpolate` 做自然入场；不要旋转/拉伸角色图像，不要做大幅位移遮挡主体。
6. 单镜头没有音频，不要尝试播放音频。

## 代码骨架

```tsx
import {AbsoluteFill, interpolate, spring, staticFile, useCurrentFrame, useVideoConfig} from 'remotion';
import {Stage} from '../components/Stage';
import {Character} from '../components/Character';
import {Card} from '../components/Card';

export const Shot_0001 = () => {
  const frame = useCurrentFrame();
  const {fps} = useVideoConfig();
  const enter = spring({frame, fps, config: {damping: 16, stiffness: 120}});
  return (
    <Stage>
      <Character src="assets/xxx.png" side="left" offsetX={(1 - enter) * 200} />
      <Card kind="terminal" side="right" lines={['> 目标', '> 计划']} reveal={Math.min(2, Math.floor(frame / 12))} />
    </Stage>
  );
};
```

## 常见错误

- 使用了资产列表外的图片 → 渲染失败。
- 导出了错误的组件名 → Root 找不到组件。
- 使用 CSS 动画/`Date.now`/随机数 → 渲染不可复现。
- 把长文本塞满屏幕 → 卡片溢出；拆成 `lines` 或分阶段 reveal。
- 引入未安装的包 → 编译失败。

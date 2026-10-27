# HANDOFF · Roxy Pipeline

> **读者**：下一个接手本项目的 Claude 会话
> **性质**：本项目**状态层的权威源** —— 做到哪、下一步做什么、踩过哪些坑。
> [README.md](README.md) 是它的**精简报告**（内容以本文为准，两者允许重复）；
> 需求、架构与选型理由见 [docs/](docs/)。
>
> **改动本项目时**：先改需求/架构/决策（设计变了才改），再改本文，最后同步 README。

---

## 0. 先读这些（按顺序）

1. **[README.md](README.md)** —— 项目是什么、当前阶段、技术栈、文档入口。**先读它。**
2. **本文件** —— 现在做到哪、下一步做什么、哪里有坑。
3. **[docs/AI科普视频Agent系统需求分析文档.md](docs/AI科普视频Agent系统需求分析文档.md)** —— 需求范围、验收标准、版权约束。
4. **[docs/AI科普视频Agent系统架构选型方案.md](docs/AI科普视频Agent系统架构选型方案.md)** —— 技术选型、模块/服务拆分、状态机、渲染流水线、接口。
5. **[docs/decisions-architecture.md](docs/decisions-architecture.md)** —— ADR：为什么这样选、代价是什么。

**动代码之前**，至少读架构方案的第 5（模块）、6（服务拆分）、9（状态机）、10（渲染）、11（AI 层）、12（接口）节。

---

## 1. 当前状态一句话

**架构设计完成，代码尚未开始（2026-10-26）。**

- 需求文档 v1.2、架构方案 v1.3、ADR-001～005 已写完。
- GitHub 仓库已创建：<https://github.com/Tsuki11111/roxy-pipeline>（Public）。
- 本地 initial commit 与文档规范化 commit 已推送到 `origin/main`（2026-10-26）。
- `.env`、洛琪希参考图、`tmp/` 已由 `.gitignore` 排除；仓库只提交 `.env.example`。
- 模型验证：
  - DeepSeek `deepseek-flash`：**PASS**。
  - 火山方舟 `doubao-seed-2-1-pro-260915` / `lite`：**PASS**；`turbo` 仍 `ModelNotOpen`。
  - 火山方舟 Seedream 5.0 Pro：**PASS**（关闭安全体验模式后，1024×1024 测试成功）。
  - 豆包视觉模型：当前账号无可用模型；视觉质检先走 DOM/几何规则。
  - 火山 TTS：**尚未配置**，M4 前需要 AppID + Access Token。
- 角色包：正式资产选用豆包版 `character_packs/roxy/roxy_calm_standing_01.png`（1080×1920 RGBA，水印已排除，本地，gitignored）；ChatGPT 版留在 `alternates/`。Seedream 不能生成洛琪希。
- Batch 1 已完成：R-02 疑惑、R-03 惊讶、R-04 无奈、R-05 得意、R-06 思考，共 6 张入库；首版最低 18 张，还差 12 张。
- Batch 2 已完成：R-07 专注、R-09 认真、R-11 指向、R-16 开口、R-17 讲解指向，共 11 张入库；首版最低 18 张，还差 7 张。
- Batch 3 已完成：R-08 害羞、R-12 震惊、R-13 微笑、R-14 沉思、R-15 气鼓鼓，共 16 张入库；首版最低 18 张，还差 2 张（R-10 坐姿 + 至少 1 个闭/开口变体）。
- Batch 4 已完成：R-10 坐姿、R-01v 平静开口（重生成替换闭嘴版）、R-02v 疑惑开口、R-16v 说话闭口、R-18 白板讲解，共 21 张；最低 18 张已达标。
- Batch 5 已完成：R-19 敲键盘、R-20 调试翻车、R-21 灵光一现、R-22 怀疑审视，共 25 张；剩余 AI 主题 R-23～R-28 共 6 张。
- R-19 待重做：旧站立版笔记本是悬空的，改为“坐在木桌前、笔记本放在桌上”的坐姿版 `roxy_typing_sitting_01.png`；旧图保留备用。
- Batch 6 已完成：R-23 戴眼镜、R-24 咖啡、R-25 摊手、R-26 数据展示、R-27 庆祝，共 30 张；只剩 R-28 被代码包围。
- M1 渲染链路原型已跑通：手写 3 镜头 JSON → 舞台 HTML → Playwright 逐帧 → ffmpeg；12 秒/300 帧/1920×1080/25fps/H.264/AAC，单进程约 160 秒。
- 资产分工（2026-10-27）：角色立绘由用户用 ChatGPT/豆包/自绘提供；背景、舞台层、演示物件由 Seedream 生成；含文字卡片仍用 HTML。
- 当前阶段只生成角色立绘，按 **5 张/批**推进；背景/舞台/演示物件暂停，等系统工作流实现后由 Seedream 按需求生成。
- AI 主题扩展：需求新增 R-17～R-28（讲解指向/白板/敲键盘/调试翻车/灵光一现/怀疑审视等），核心 6 个提示词在 `character_packs/roxy/ai_pose_prompts.md`（本地）。背景已出纸纹 + 木地板；道具在生成中。
- 代码：还没有 `app/`、`compose.yaml`、前端；M1 从零开始。

---

## 2. 下一步做什么

### 2.1 立即

1. **确认 initial commit 已推到 GitHub**：`git status -sb` 应显示 `main...origin/main`；没有就 `git push -u origin main`。
2. **确认运行环境**：本机 Docker Desktop/WSL2 是否可用；VM 是否已挂 ≥200GB 数据盘；8080/8443/9100/9101 是否空闲。
3. **确认 TTS 凭据**（不阻塞 M1）：火山语音 AppID + Access Token；如果换 MiniMax/阿里云，准备好对应凭据。
4. **角色立绘按 5 张/批推进**：Batch 1 = R-02～R-06；提示词已发；生成后处理入库。背景/道具暂停，等 M3 工作流实现后再生成。

### 2.2 M1：渲染链路打通

目标：手写一份脚本/镜头表 → 用占位角色包 → 输出 720P/12.5fps 粗剪 → 再跑 1080P/25fps。

建议顺序：

1. `compose.infra.yml`：Postgres、RabbitMQ、Redis、MinIO（MinIO 可选，先本地存储也可）。
2. `pyproject.toml` + `uv`；FastAPI skeleton；Alembic 初始迁移（`series` / `episode` / `script_line` / `shot` / `node_run`）。
3. `render-worker`：Playwright/Chromium + Jinja2 舞台模板 + ffmpeg 逐帧编码。
4. `character_packs/placeholder/`：先放 1 套占位立绘/背景，保证渲染链路能跑。
5. 手写 3–5 个镜头的 `shot.json`，跑通“卡片 → 镜头片段 → concat → 成片”。
6. golden frame 测试：同一输入重复渲染，像素差异在阈值内。

**已完成（2026-10-27）：**

- `pyproject.toml` + `uv` 环境；Playwright 钉在 1.59（复用本机 Chromium）。
- `app/render/`：models / timeline / cards / stage / capture / encode。
- 舞台模板 `templates/stage/` 与 5 类卡片模板 `templates/cards/`。
- `specs/demo_episode.json`：3 镜头、12 秒；`scripts/render_demo.py` 输出 `tmp/render_demo/demo_episode.mp4`。
- `uv run pytest` 4 条通过；demo 视频 1920×1080 / 25fps / H.264 / AAC 48kHz。

**还没做：**

- `compose.infra.yml`、FastAPI API、Alembic/数据库、Celery/RabbitMQ 队列。
- 独立 `render-worker` 进程与并行渲染（当前是单进程 CLI）。
- golden frame 回归测试（当前只验了单次渲染）。
- `character_packs/placeholder/` 与可公开复现的 demo 素材（当前引用本地 Roxy pack + tmp 背景）。

### 2.3 M1 之后再动

- **M2**：`script_graph`（LangGraph），DeepSeek `deepseek-flash` 生成大纲/分段/逐句。
- **M3**：`storyboard_graph` + 节奏规则；Seedream 素材候选 + 人工入库。
- **M4**：TTS/对齐/质检；视觉质检先用 DOM 规则。
- **M5**：局部重渲染、断点续跑、成本报表。

### 2.4 待决事项

| 编号 | 问题 | 现状/建议 |
|---|---|---|
| Q-05 | 2 期并行是否 M1 硬指标 | 先按单期串行；资源足够再开 2 期 |
| Q-06 | `TOPIC_CONFIRMED` 语义 | 按“选题已确认”实现，评审时确认 |
| Q-07 | 字幕与镜头是否严格 1:1 | 数据模型支持 1:N；MVP 先 1:1 |
| Q-08 | 是否自动上传平台 | 非目标；先做本地发布包 |
| Q-11 | Seedream 1080×1920 / 参考图 | 已确认 1024×1024 可用；立绘尺寸与参考图输入待测 |
| Q-12 | `deepseek-flash` JSON 能力 | 用 Pydantic + JSON 解析兜底；实测后记录 |

---

## 3. 项目结构

当前仓库（只有文档，没有代码）：

```text
roxy_pipline/
├─ CLAUDE.md
├─ HANDOFF.md
├─ README.md
├─ .env.example
├─ .gitignore
├─ docs/
│  ├─ AI科普视频Agent系统需求分析文档.md
│  ├─ AI科普视频Agent系统架构选型方案.md
│  ├─ decisions-architecture.md
│  └─ assets/roxy_reference.webp   # 本地保留，gitignore
├─ character_packs/
│  └─ roxy/                        # 本地洛琪希 pack，gitignore
│     ├─ manifest.json
│     ├─ checklist.md
│     ├─ ai_pose_prompts.md
│     ├─ roxy_calm_standing_01.png # 正式（豆包版，水印已排除）
│     └─ alternates/
│        └─ roxy_calm_standing_01_chatgpt.png
├─ app/
│  └─ render/                      # M1 渲染原型
│     ├─ models.py
│     ├─ timeline.py
│     ├─ cards.py
│     ├─ stage.py
│     ├─ capture.py
│     └─ encode.py
├─ templates/
│  ├─ stage/                       # stage.html/css/renderer.js
│  └─ cards/                       # 5 类卡片 HTML
├─ specs/
│  └─ demo_episode.json            # 3 镜头 12 秒 demo
├─ tests/
│  └─ test_timeline.py
├─ pyproject.toml
├─ uv.lock
└─ scripts/
   ├─ check_llm.py
   ├─ prepare_character_asset.py
   ├─ generate_seedream_image.py
   └─ render_demo.py               # 手写镜头 → MP4
```

M1 计划新增的目录见架构方案附录 A：`app/`（api/workflow/agents/domains/providers）、`templates/`、`prompts/`、`assets/`、`character_packs/`、`migrations/`、`tests/`、`web/`。

---

## 4. 环境与约定

### 4.1 模型与接口

| 用途 | 配置 | 状态 |
|---|---|---|
| 文本/代码主模型 | `DEEPSEEK_MODEL=deepseek-flash` | ✅ 可用 |
| 文本备选/A-B | `ARK_MODEL_STRONG=doubao-seed-2-1-pro-260915` | ✅ 可用 |
| 图像素材 | `ARK_IMAGE_MODEL=doubao-seedream-5-0-pro-260628` | ✅ 可用（原创角色/背景；洛琪希会被版权过滤） |
| 视觉质检 | `ARK_MODEL_VISION` | ❌ 无可用模型；先 DOM 规则 |
| TTS | `VOLC_TTS_APP_ID` / `VOLC_TTS_ACCESS_TOKEN` | ⏳ 待提供 |

- DeepSeek Base URL：`https://api.deepseek.com`
- 火山方舟 Base URL：`https://ark.cn-beijing.volces.com/api/v3`
- 校验脚本：`python scripts/check_llm.py --live`（DeepSeek 必检，Ark 可选）；`--require-ark` 把 Ark 当必检。
- 图像生成测试产物在 `tmp/seedream_probe.png`（gitignore）。

### 4.2 本地渲染环境（M1）

- 依赖安装（PyPI 直连容易卡，国内镜像更快）：
  `UV_DEFAULT_INDEX=https://pypi.tuna.tsinghua.edu.cn/simple uv sync`
- Playwright 钉在 **1.59.0**，复用本机 `chromium-1217`；升级 Playwright 前先确认对应 Chromium 已安装，否则 `uv run playwright install chromium`。
- ffmpeg 用 `imageio-ffmpeg` 自带二进制（`imageio-ffmpeg==0.6.0`，含 libx264/AAC），本机不需要系统 ffmpeg。
- 测试：`uv run pytest -q`
- 渲染成片：`uv run python scripts/render_demo.py`
- 只出静帧：`uv run python scripts/render_demo.py --stills-only --still-ms 2000 --still-out tmp/render_demo/still_2s.png`
- 当前单进程速度约 **0.53 秒/帧**；10 分钟片约 2.3 小时，后续必须并行 render worker。

### 4.3 Git 与提交

- Remote：`origin` → `https://github.com/Tsuki11111/roxy-pipeline.git`
- 分支：`main`
- 提交信息：Conventional Commits，描述中文；例：
  - `docs: 补充 M1 渲染链路设计`
  - `feat(render): 增加镜头级 ffmpeg 编码`
- **不要提交**：`.env`、`docs/assets/roxy_reference.webp`、`tmp/`、`data/`、私有 `character_packs/*`。

### 4.4 Docker 与端口

- 部署目标：Ubuntu 24.04 VM，Docker 29 / Compose 2.40。
- 本项目资源命名以 `roxy-` 开头；Postgres 库 `roxy`；Redis key 前缀 `roxy:`；MinIO bucket `roxy-*`。
- 端口：Nginx 8080/8443；MinIO 9100/9101；Postgres/Redis/RabbitMQ 仅在 Docker 网络。
- 现有 VM 已占用 8088/8001/8002/8003/9000/9002，避开。
- 根分区约 18GB 不够；数据盘挂 `/data`，`PGDATA`、`MINIO_DATA`、备份都指过去。
- MinIO 预签名 URL 要区分 `MINIO_INTERNAL_ENDPOINT`（容器内 `http://minio:9000`）与 `MINIO_PUBLIC_ENDPOINT`（浏览器可访问的外部地址）。

### 4.5 渲染约定

- 输出规格：1920×1080、25fps、H.264/AAC 48kHz。
- 所有动画由 `renderAt(tMs)` 计算，禁用 CSS animation / `Date.now()` / `Math.random()`；随机用固定 seed。
- 镜头片段编码参数必须完全一致，最终 `-c copy` 拼接。
- 含文字卡片用 HTML；Seedream 只做背景/舞台/演示物件（无文字空壳）。
- 背景/演示物件生成后固定资产化，不每期重生成。

### 4.6 资产生产分工

| 资产 | 生产者 | 说明 |
|---|---|---|
| 洛琪希等版权角色立绘 | 用户（ChatGPT/豆包/自绘） | 系统不调用 Seedream；pack 在 `character_packs/roxy/`，不提交公开仓库 |
| 背景/舞台层 | Seedream | 纸纹、木纹台面、桌面 |
| 演示物件 | Seedream | 终端/浏览器/气泡卡片外框、道具；只出无文字空壳 |
| 含文字信息卡片 | HTML/CSS | 文字和版式由代码控制 |
| 图标 | SVG 优先；需要 AI 版时 Seedream 图标表 | 统一线条风格 |
| 封面/片头片尾 | Seedream + 模板 | 复用背景，不每期重生成 |

Seedream 首版约 12–17 张：背景 3–4、演示物件 6–8、图标表 1、封面/片头片尾 2–4。

---

## 5. 踩过的坑 / 已知风险

### 5.1 GitHub 推送网络不稳

- `gh repo create` 可能返回 `unexpected EOF` / 500，但仓库实际已创建；先用 `gh repo view` 确认，再补 remote。
- `git push` 可能报 `schannel: server closed abruptly` / `Internal Server Error`；先 `git ls-remote origin main` 确认是否真的没推上去，再重试。
- 本机 GitHub SSH 未配置（`git@github.com: Permission denied (publickey)`），目前走 HTTPS。
- 若推送报错但 `gh repo view` 能看到 commit，按“实际成功”处理，不要重复 force push。

### 5.2 火山方舟模型状态

- `/models` 只返回平台目录，**不代表账号已开通**。
- `ModelNotOpen` = 模型存在，但未开通；去控制台「开通管理 / 模型广场」开通。
- `InvalidEndpointOrModel.NotFound` = 模型/接入点不存在，或当前账号无权限；换模型或找商务。
- Seedream 的 `SetLimitExceeded`（HTTP 429）= 账号处于“安全体验模式”且达到用量上限；在开通管理页调整/关闭安全体验模式。
- 换 Key 前先看错误码：`ModelNotOpen` 不是 Key 错误，别反复重置 Key。
- 当前账号无可用豆包视觉模型；视觉质检不要卡在它上面。

### 5.3 模型路由

- DeepSeek Key 只开放 `deepseek-flash`；不要调用 `deepseek-v4-pro`，即使 `/models` 里能看到。
- `deepseek-flash` 是文本/代码主模型，不是“廉价小模型”；豆包 Pro 仅备选/A-B。
- 不要把 Chromium/ffmpeg 放进 LangGraph 节点；图只做 AI 决策。
- 含文字卡片永远用 HTML，不要用图像模型生成。

### 5.4 素材与版权

- 公开仓库不提交洛琪希参考图/立绘；`docs/assets/roxy_reference.webp` 已 gitignore。
- Seedream 版权过滤：带“洛琪希”名字、参考图，或高度相似的“蓝发魔女 + 长风衣”描述，会返回 `OutputImageSensitiveContentDetected.PolicyViolation`；不要用改词/裁剪参考图的方式绕过。AI 生成只用于原创角色/背景/装饰；洛琪希 pack 自绘或外包。
- ChatGPT 在线生图可用于本地洛琪希候选（用户自用、非商业）；产物只放 `character_packs/roxy/`（gitignored），不要提交公开仓库。处理脚本：`scripts/prepare_character_asset.py`。
- 豆包生成图右下角有“豆包 AI 生成”水印；不要直接入成片。脚本可用 `--keep-largest-component` 排除孤立水印；使用前先确认豆包条款是否允许去除/隐藏水印。
- 原创角色/背景 AI 生成后必须人工筛选、去背景、统一尺寸、入库；不要每期重生成。
- AI 生成的洛琪希衍生图仍受 C-01～C-06 约束；生成服务条款也要看。
- 字体/BGM 只用 OFL 或已授权素材。

### 5.5 环境

- 本机 Python 可用；Docker Desktop/WSL2 尚未验证。
- VM 根分区 18GB 不能放 MinIO 数据；先挂数据盘。
- 2 期并行需要约 8–16 vCPU / 32GB；资源不足先单期串行。

### 5.6 M1 渲染环境

- PyPI 直连会卡住：`uv sync` 用 `UV_DEFAULT_INDEX=https://pypi.tuna.tsinghua.edu.cn/simple`。
- Playwright 1.64 需要新 Chromium（1248），本机只有 1217；把 `playwright` 钉在 `==1.59.0`，避免重下浏览器。
- 本机没有系统 ffmpeg；用 `imageio-ffmpeg` 自带二进制，已确认有 libx264/AAC。
- 单进程渲染约 0.53 秒/帧：300 帧 12 秒片约 160 秒；10 分钟片约 2.3 小时，必须并行化。
- `specs/demo_episode.json` 引用本地 `character_packs/roxy/` 和 `tmp/seedream_assets/`；这些不进公开仓库，公开复现需要 placeholder pack。
- Windows 控制台输出中文可能乱码，不影响文件；需要时设 `PYTHONUTF8=1`。

---

## 6. 历史记录

### 2026-10-26 · 架构定稿与仓库初始化

- 需求分析文档完成并更新到 v1.2：补充 AI 素材生成 F-43～F-45、A-18、C-06。
- 架构选型方案完成并更新到 v1.3：方案 A（Python 模块化单体 + 进程级拆分 + Celery）、LangGraph 边界、Seedream 素材生成、HTML 卡片边界。
- ADR-001～005 写入 `docs/decisions-architecture.md`。
- 模型验证：DeepSeek `deepseek-flash` PASS；火山 Seed 2.1 Pro/Lite PASS；Seedream 5.0 Pro PASS；Turbo 未开通；视觉模型无权限。
- GitHub 仓库 `Tsuki11111/roxy-pipeline` 创建（Public）；initial commit 与文档规范化 commit 已推送（网络曾中断，重试后成功）。
- `.gitignore` 排除 `.env`、洛琪希参考图、`tmp/`、私有 character pack。
- 新建 `CLAUDE.md` / `HANDOFF.md` / `README.md`，按 ItsMyGo 的文档分工规范化。

### 2026-10-27 · R-19 改为坐姿木桌版

- 旧版 R-19 是站立、笔记本悬空；用户要求改成人物坐在木桌前、笔记本电脑放在桌面上打字。
- 新资产命名 `roxy_typing_sitting_01.png`，提示词已更新到 `character_packs/roxy/ai_pose_prompts.md`。
- 旧 `roxy_typing_standing_01.png` 不再作为正式 R-19，保留在 pack 里备用。
- 开发暂停，等新立绘生成后继续 M1.1。

### 2026-10-27 · M1 渲染链路原型跑通

- 新建 `pyproject.toml` + `uv.lock`；Playwright 钉 1.59，ffmpeg 用 `imageio-ffmpeg`。
- 新增 `app/render/`（models / timeline / cards / stage / capture / encode）、舞台与 5 类卡片模板、`specs/demo_episode.json`、`scripts/render_demo.py`。
- 3 镜头 / 12 秒 / 300 帧 demo 输出成功：1920×1080、25fps、H.264、AAC 48kHz；单进程约 160 秒。
- `uv run pytest` 4 条通过；静帧模式可快速调布局。
- 未接 API/DB/队列；当前是单进程 CLI，后续拆 render-worker 并做并行渲染。

### 2026-10-27 · Batch 6 完成

- R-23 戴眼镜、R-24 咖啡、R-25 摊手、R-26 数据展示、R-27 庆祝入库。
- manifest 升到 v8，总资产 30 张；只剩 R-28 被代码包围（角色抱头，漂浮代码后期合成）。

### 2026-10-27 · Batch 5 完成

- R-19 敲键盘、R-20 调试翻车、R-21 灵光一现、R-22 怀疑审视入库。
- manifest 升到 v7，总资产 25 张；最低 18 张早已达标。
- 剩余 AI 主题 R-23 戴眼镜、R-24 咖啡、R-25 悬浮终端、R-26 数据展示、R-27 庆祝、R-28 被代码包围。

### 2026-10-27 · Batch 4 完成

- R-10 放松坐姿、R-01v 平静开口（重生成后替换了原来的闭嘴版）、R-02v 疑惑开口、R-16v 说话闭口、R-18 白板讲解入库，共 5 张；总资产 21 张，最低 18 张已达标。
- R-01v 第一次生成仍是闭嘴微笑，和 R-16v 重复；用“R-01 姿势 + R-03 张嘴参考”重生成后通过，文件归入 `tmp/roxy_batch04/` 并替换旧图。
- R-10 是坐姿，资产包含椅子与轻微阴影，锚点按椅子底部对齐。

### 2026-10-27 · Batch 3 角色立绘完成

- 收到豆包生成的 R-08 害羞、R-12 震惊、R-13 微笑、R-14 沉思、R-15 气鼓鼓，共 5 张。
- 全部按 1080×1920 RGBA 去白底/水印入库；manifest 升到 v5，共 16 个角色资产。
- 首版最低 18 张，还差 R-10 坐姿 + 至少 1 个闭/开口变体；Batch 4 用 R-10 + R-01v/R-02v/R-16v + R-18 白板讲解补齐并开始 AI 主题。

### 2026-10-27 · Batch 2 角色立绘完成

- 收到豆包生成的 R-07 专注、R-09 认真、R-11 指向、R-16 开口、R-17 讲解指向，共 5 张。
- 发现并修复背景移除 bug：`ndimage.label` 的 0 号标签（所有非近白像素）被错误当成背景，脚底贴边的 R-11 整张角色被清空；修复为 `border_labels.discard(0)`，并重跑 Batch 2。
- manifest 升到 v4，共 11 个角色资产；checklist 已标 R-07/R-09/R-11/R-16/R-17。首版最低 18 张，还差 7 张。

### 2026-10-27 · Batch 1 角色立绘完成

- 收到豆包生成的 R-02 疑惑、R-03 惊讶、R-04 无奈、R-05 得意、R-06 思考，共 5 张。
- 用 `prepare_character_asset.py --keep-largest-component` 去白底/水印，归一化到 1080×1920 RGBA，入库到 `character_packs/roxy/`。
- manifest 升到 v3，共 6 个角色资产；checklist 已把 R-02～R-06 标为完成。首版最低 18 张，还差 12 张。

### 2026-10-27 · 角色立绘改为 5 张/批

- 暂停生成非角色图片；背景/舞台/演示物件等 M3 工作流实现后由 Seedream 按需求生成。
- 角色立绘按 5 张/批推进；分批计划写入 `character_packs/roxy/checklist.md`，Batch 1 = R-02～R-06。

### 2026-10-27 · AI 主题立绘扩展 + 背景/道具

- 需求新增 R-17～R-28：讲解指向、白板讲解、敲键盘、调试翻车、灵光一现、怀疑审视、戴眼镜、咖啡、悬浮终端、数据展示、庆祝、被代码包围。
- 核心 6 个立绘提示词写入 `character_packs/roxy/ai_pose_prompts.md`；R-01 已完成，其余按主题补齐。
- Seedream 生成纸纹 + 木地板背景（1920×1080）；终端/白板/AI 机器人/神经网络道具在 `tmp/seedream_assets/props/` 生成中。

### 2026-10-27 · 资产生产分工

- 用户确认：洛琪希等版权角色立绘由用户提供；背景、舞台层、演示物件由 Seedream 生成；含文字卡片仍用 HTML。
- 写入 ADR-006；Seedream 首版清单约 12–17 张（背景 3–4、物件 6–8、图标表 1、封面/片头片尾 2–4）。

### 2026-10-27 · 豆包立绘水印检查

- 豆包生成图右下角带“豆包 AI 生成”水印；直接入成片会让 alpha bbox 扩大、角色缩小偏移，并在每个镜头出现。
- 给 `prepare_character_asset.py` 增加 `--keep-largest-component`：只保留角色主体，水印作为孤立小组件被排除。
- 处理结果：`tmp/roxy_doubao_01_1080x1920.png`，角色完整、水印已排除；是否正式入库待确认豆包条款。
- 用户选定豆包版为正式资产：`character_packs/roxy/roxy_calm_standing_01.png`；ChatGPT 版移到 `alternates/`，manifest 升到 v2。

### 2026-10-26 · 角色素材测试

- Seedream 5.0 Pro 原创角色生成成功：1088×1920 → 裁到 1080×1920，纯白底 RGB，产物 `tmp/original_girl_01_1080x1920.png`。
- 洛琪希特定形象被版权过滤：带名称、参考图或高度相似描述都返回 `OutputImageSensitiveContentDetected.PolicyViolation`；Roxy pack 改为自绘/外包，AI 生成只用于原创角色/背景/装饰。
- ChatGPT 在线生图产出首个洛琪希正面立绘；用 `prepare_character_asset.py` 去白底、裁到 1080×1920，存入 `character_packs/roxy/`（本地，gitignored）。

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
- 代码：还没有 `app/`、`compose.yaml`、前端；M1 从零开始。

---

## 2. 下一步做什么

### 2.1 立即

1. **确认 initial commit 已推到 GitHub**：`git status -sb` 应显示 `main...origin/main`；没有就 `git push -u origin main`。
2. **确认运行环境**：本机 Docker Desktop/WSL2 是否可用；VM 是否已挂 ≥200GB 数据盘；8080/8443/9100/9101 是否空闲。
3. **确认 TTS 凭据**（不阻塞 M1）：火山语音 AppID + Access Token；如果换 MiniMax/阿里云，准备好对应凭据。

### 2.2 M1：渲染链路打通

目标：手写一份脚本/镜头表 → 用占位角色包 → 输出 720P/12.5fps 粗剪 → 再跑 1080P/25fps。

建议顺序：

1. `compose.infra.yml`：Postgres、RabbitMQ、Redis、MinIO（MinIO 可选，先本地存储也可）。
2. `pyproject.toml` + `uv`；FastAPI skeleton；Alembic 初始迁移（`series` / `episode` / `script_line` / `shot` / `node_run`）。
3. `render-worker`：Playwright/Chromium + Jinja2 舞台模板 + ffmpeg 逐帧编码。
4. `character_packs/placeholder/`：先放 1 套占位立绘/背景，保证渲染链路能跑。
5. 手写 3–5 个镜头的 `shot.json`，跑通“卡片 → 镜头片段 → concat → 成片”。
6. golden frame 测试：同一输入重复渲染，像素差异在阈值内。

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
└─ scripts/
   └─ check_llm.py
```

M1 计划新增的目录见架构方案附录 A：`app/`（api/workflow/agents/domains/providers）、`templates/`、`prompts/`、`assets/`、`character_packs/`、`migrations/`、`tests/`、`web/`。

---

## 4. 环境与约定

### 4.1 模型与接口

| 用途 | 配置 | 状态 |
|---|---|---|
| 文本/代码主模型 | `DEEPSEEK_MODEL=deepseek-flash` | ✅ 可用 |
| 文本备选/A-B | `ARK_MODEL_STRONG=doubao-seed-2-1-pro-260915` | ✅ 可用 |
| 图像素材 | `ARK_IMAGE_MODEL=doubao-seedream-5-0-pro-260628` | ✅ 可用（需人工筛选） |
| 视觉质检 | `ARK_MODEL_VISION` | ❌ 无可用模型；先 DOM 规则 |
| TTS | `VOLC_TTS_APP_ID` / `VOLC_TTS_ACCESS_TOKEN` | ⏳ 待提供 |

- DeepSeek Base URL：`https://api.deepseek.com`
- 火山方舟 Base URL：`https://ark.cn-beijing.volces.com/api/v3`
- 校验脚本：`python scripts/check_llm.py --live`（DeepSeek 必检，Ark 可选）；`--require-ark` 把 Ark 当必检。
- 图像生成测试产物在 `tmp/seedream_probe.png`（gitignore）。

### 4.2 Git 与提交

- Remote：`origin` → `https://github.com/Tsuki11111/roxy-pipeline.git`
- 分支：`main`
- 提交信息：Conventional Commits，描述中文；例：
  - `docs: 补充 M1 渲染链路设计`
  - `feat(render): 增加镜头级 ffmpeg 编码`
- **不要提交**：`.env`、`docs/assets/roxy_reference.webp`、`tmp/`、`data/`、私有 `character_packs/*`。

### 4.3 Docker 与端口

- 部署目标：Ubuntu 24.04 VM，Docker 29 / Compose 2.40。
- 本项目资源命名以 `roxy-` 开头；Postgres 库 `roxy`；Redis key 前缀 `roxy:`；MinIO bucket `roxy-*`。
- 端口：Nginx 8080/8443；MinIO 9100/9101；Postgres/Redis/RabbitMQ 仅在 Docker 网络。
- 现有 VM 已占用 8088/8001/8002/8003/9000/9002，避开。
- 根分区约 18GB 不够；数据盘挂 `/data`，`PGDATA`、`MINIO_DATA`、备份都指过去。
- MinIO 预签名 URL 要区分 `MINIO_INTERNAL_ENDPOINT`（容器内 `http://minio:9000`）与 `MINIO_PUBLIC_ENDPOINT`（浏览器可访问的外部地址）。

### 4.4 渲染约定

- 输出规格：1920×1080、25fps、H.264/AAC 48kHz。
- 所有动画由 `renderAt(tMs)` 计算，禁用 CSS animation / `Date.now()` / `Math.random()`；随机用固定 seed。
- 镜头片段编码参数必须完全一致，最终 `-c copy` 拼接。
- 含文字卡片用 HTML；图像生成只做角色/背景/装饰。
- 角色/背景素材生成后固定资产化，不每期重生成。

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
- 角色/背景 AI 生成后必须人工筛选、去背景、统一尺寸、入库；不要每期重生成。
- AI 生成的洛琪希衍生图仍受 C-01～C-06 约束；生成服务条款也要看。
- 字体/BGM 只用 OFL 或已授权素材。

### 5.5 环境

- 本机 Python 可用；Docker Desktop/WSL2 尚未验证。
- VM 根分区 18GB 不能放 MinIO 数据；先挂数据盘。
- 2 期并行需要约 8–16 vCPU / 32GB；资源不足先单期串行。

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

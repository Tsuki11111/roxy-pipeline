# 项目约定（Roxy Pipeline）

## 刚进到这个目录，先做这两件事

1. 读 **[README.md](README.md)** —— 项目是什么、当前阶段、技术栈、文档入口。
2. 读 **[HANDOFF.md](HANDOFF.md)** —— 现在做到哪、下一步做什么、踩过哪些坑。

**顺序不要颠倒**：README 给全局，HANDOFF 给当前落点。

需要需求细节时读 **[docs/AI科普视频Agent系统需求分析文档.md](docs/AI科普视频Agent系统需求分析文档.md)**；
需要选型理由时读 **[docs/AI科普视频Agent系统架构选型方案.md](docs/AI科普视频Agent系统架构选型方案.md)** 与
**[docs/decisions-architecture.md](docs/decisions-architecture.md)**。
**动代码之前**，先读架构方案里对应的模块、状态机、渲染流水线、接口章节，别重复造已有的设计。

---

## 项目定位

AI 科普视频自动生成 Agent 系统：选题 → 脚本 → 分镜 → 逐句 TTS/对齐 → HTML 卡片/逐帧渲染 → ffmpeg 拼接 → 质检。

- **个人自用项目**；洛琪希为《无职转生》角色，仅限非商业同人使用，遵守需求文档第 11 章。
- **当前阶段**：架构设计完成；M1 渲染链路原型已跑通（手写镜头 JSON → MP4），API/DB/队列未接。
- **GitHub**：<https://github.com/Tsuki11111/roxy-pipeline>（Public）。
- **仓库不包含**：`.env`、洛琪希参考图/立绘、`tmp/`、私有 character pack。

---

## 协作偏好

- **全程中文回复。**
- **改了代码或设计，主动同步文档，不要等被提醒。** 三份文档分工不同，按这个顺序改：
  1. **需求 / 架构 / 决策** —— 设计变了才改；需求看范围，架构看做法，ADR 记取舍。
  2. **[HANDOFF.md](HANDOFF.md)** —— 记当前状态、下一步、踩过的坑，是**状态层的权威源**。
  3. **[README.md](README.md)** —— 精简报告，内容一律以 HANDOFF 为准。
- **收到用户补充的新约束，立刻写进文档**，不要只留在对话里。
- **提交信息用 Conventional Commits，描述用中文**：`feat` / `fix` / `docs` / `refactor` / `test` / `chore` 等。
- **不擅自换技术栈**。见 README 技术栈表；有异议先讨论，再改文档。
- **先跑通再优化**；但状态机幂等、缓存键、渲染确定性这些地基不能省。
- **任何 Key / Token 只进本地 `.env`**；不要写进文档、代码、提交信息或聊天回复。
- **公开仓库**：不提交未授权的角色图、BGM、字体；默认用 placeholder 素材。
- **不删除 / 覆盖用户已有文件**；改动前先读。

---

## 硬约束

### 1. 技术栈已定

Python 3.12 + FastAPI + Pydantic v2 + SQLAlchemy 2.0 + PostgreSQL + RabbitMQ/Celery + Redis + MinIO +
Playwright/Chromium + ffmpeg + LangGraph（仅 AI 子图）；前端 React + Vite + TypeScript + Ant Design。
详见架构方案第 3 节。

### 2. LangGraph 边界

- LangGraph 只做 `script_graph` / `storyboard_graph` / `qc_repair_graph`。
- 媒体流水线（TTS、渲染、拼接）仍由 PostgreSQL 状态机 + Celery 负责。
- `episode.status` 是业务事实来源；LangGraph checkpoint 不是。
- 图节点不直接跑 Chromium/ffmpeg/TTS。

### 3. 模型路由

- 文本/代码主模型：DeepSeek `deepseek-flash`（当前 Key 只开放这个模型）。
- 豆包 Pro：仅备选/A-B，不阻塞主流程。
- 图像素材：火山方舟 Seedream 5.0 Pro，生成候选后**人工筛选、固定资产化**；仅限原创角色/背景/装饰，洛琪希会被版权过滤，不能 AI 复刻。
- 视觉质检：DOM/几何规则优先；视觉模型可选，不作为关键路径。
- **含文字的信息卡片必须用 HTML 渲染**，不得用图像生成模型。

### 4. 密钥与素材

- `.env` 已在 `.gitignore`；仓库只提交 `.env.example`。
- **资产分工**：洛琪希等版权角色立绘由用户用 ChatGPT/豆包/自绘提供；背景、舞台层、演示物件由 Seedream 生成；含文字信息卡片仍用 HTML。
- **当前阶段（2026-10-27 起）只生成人物立绘**；背景/舞台/演示物件暂停，等系统工作流实现后由 Seedream 按需求生成。
- `docs/assets/roxy_reference.webp` 已 gitignore，不随公开仓库分发。
- `character_packs/*` 默认忽略，只允许 `character_packs/placeholder/`。
- AI 生成图带可见水印（如“豆包 AI 生成”）时不得直接入成片；先确认服务条款，允许再用脚本排除/遮罩。
- `tmp/`、`data/` 忽略；生成的样片/帧不要提交。

### 5. 运行环境

- 开发机：Windows 11 + Git Bash；Python 可用；Docker Desktop/WSL2 待确认。
- 部署目标：Ubuntu 24.04 VM，Docker 29 / Compose 2.40。
- 数据盘 ≥200GB（推荐 500GB），挂 `/data`；根分区约 18GB，不够放 MinIO 和中间产物。
- 端口：8080/8443，MinIO 9100/9101；避开 8088/8001/8002/8003/9000/9002。

---

## 文档权威

| 文档 | 作用 |
|---|---|
| [docs/AI科普视频Agent系统需求分析文档.md](docs/AI科普视频Agent系统需求分析文档.md) | 需求范围、验收标准、版权约束 |
| [docs/AI科普视频Agent系统架构选型方案.md](docs/AI科普视频Agent系统架构选型方案.md) | 技术选型、模块/服务拆分、渲染与接口设计 |
| [docs/decisions-architecture.md](docs/decisions-architecture.md) | ADR：为什么这样选、代价是什么 |
| [HANDOFF.md](HANDOFF.md) | 当前状态、下一步、坑 |
| [README.md](README.md) | 精简报告 |

**冲突时**：范围看需求，设计看架构，状态看 HANDOFF。

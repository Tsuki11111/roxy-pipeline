# Roxy Pipeline

[![GitHub](https://img.shields.io/badge/GitHub-roxy--pipeline-181717?logo=github)](https://github.com/Tsuki11111/roxy-pipeline)
[![Status](https://img.shields.io/badge/status-architecture-blue)]()
[![Python](https://img.shields.io/badge/Python-3.12-3776AB?logo=python&logoColor=white)]()
[![FastAPI](https://img.shields.io/badge/FastAPI-framework-009688?logo=fastapi&logoColor=white)]()
[![PostgreSQL](https://img.shields.io/badge/PostgreSQL-17-4169E1?logo=postgresql&logoColor=white)]()
[![RabbitMQ](https://img.shields.io/badge/RabbitMQ-4-FF6600?logo=rabbitmq&logoColor=white)]()
[![Redis](https://img.shields.io/badge/Redis-7-DC382D?logo=redis&logoColor=white)]()
[![MinIO](https://img.shields.io/badge/MinIO-S3-C72E49?logo=minio&logoColor=white)]()
[![LangGraph](https://img.shields.io/badge/LangGraph-AI%20subgraphs-1C3C3C)]()
[![React](https://img.shields.io/badge/React-19-61DAFB?logo=react&logoColor=black)]()

**AI 科普视频自动生成 Agent 系统**：从选题、脚本、分镜，到逐句 TTS、卡片/逐帧渲染、ffmpeg 拼接和质检的全自动流水线。

**定位**：个人自用项目；洛琪希为《无职转生》角色，仅限非商业同人使用，遵守[需求文档第 11 章](docs/AI科普视频Agent系统需求分析文档.md)。
**当前阶段**：M1 渲染原型 + M1.1 API/DB + M1.2 队列/渲染 worker + M2 脚本 Agent 已跑通（FastAPI + SQLAlchemy + Alembic + Celery + LangGraph + DeepSeek）；分镜/配音待接。

---

## 技术栈

| 层 | 选型 |
|---|---|
| 语言 | Python 3.12 |
| Web | FastAPI + Pydantic v2 + SQLAlchemy 2.0 + Alembic |
| 数据库 | PostgreSQL 17 —— 状态、脚本、镜头、节点、成本、审计 |
| 任务队列 | RabbitMQ 4 + Celery 5 —— 长任务、重试、DLQ |
| 缓存/锁 | Redis 7 —— 缓存、分布式锁、限流、SSE 广播 |
| 对象存储 | MinIO —— 角色/背景/音频/片段/成片 |
| AI 子图 | LangGraph + PostgreSQL checkpointer —— 只做脚本/分镜/QC |
| 渲染 | Playwright + Chromium + Jinja2 + ffmpeg |
| 文本模型 | DeepSeek `deepseek-flash`（主）；火山方舟豆包 Pro（备选/A-B） |
| 图像生成 | 火山方舟 Seedream 5.0 Pro（背景/舞台/演示物件；角色立绘由用户提供） |
| 前端 | React + Vite + TypeScript + Ant Design |
| 部署 | Docker Compose + Nginx |
| 可观测 | structlog + Prometheus/Grafana + Sentry（后续） |

> 详细选型理由见 [架构选型方案](docs/AI科普视频Agent系统架构选型方案.md) 与 [ADR](docs/decisions-architecture.md)。

## 架构

```text
浏览器 ──HTTPS/SSE──> Nginx ──> FastAPI API
                                  │
              ┌───────────────────┼───────────────────┐
              ▼                   ▼                   ▼
         PostgreSQL          RabbitMQ + Redis         MinIO
      状态/元数据/审计       任务/缓存/锁/广播      资产/产物/成片
                                  │
        ┌─────────────┬───────────┼─────────────┬─────────────┐
        ▼             ▼           ▼             ▼             ▼
   workflow       agent        media         asset         render
   状态机      LangGraph      TTS/对齐      Seedream     Playwright
   重试/补偿   脚本/分镜/QC   音频装配      素材候选      + ffmpeg
```

流水线：**选题 → 脚本 → 分镜 → TTS → 对齐 → 卡片 → 镜头 → 拼接 → 质检 → 发布包**。

**四条边界：**

1. `episode.status` 是业务事实来源；LangGraph checkpoint 只是图运行状态。
2. 媒体任务（TTS、Chromium、ffmpeg）不进 LangGraph；由状态机 + Celery 调度。
3. 含文字的信息卡片必须用 HTML 渲染；Seedream 只做背景/舞台/演示物件。
4. 镜头是缓存和并行的最小单位；局部改一句只重跑受影响的镜头和拼接。

## 当前进度

| 阶段 | 状态 |
|---|---|
| 需求分析 v1.2 | ✅ 2026-10-26 |
| 架构选型 v1.3 + ADR-001～005 | ✅ 2026-10-26 |
| 仓库初始化 + 文档规范化 | ✅ 2026-10-26 |
| M1 渲染链路 + M1.1 API/DB | 🚧 渲染原型与 API/DB 骨架已跑通 |
| M1.2 队列/状态机/render worker | ✅ outbox + Celery `render.shot` 并行 + `render.concat`；真实 RabbitMQ 验证 |
| M2 脚本 Agent（LangGraph） | ✅ `script_graph` + DeepSeek `deepseek-flash` + 脚本校验/编辑/确认 |
| M3 分镜 Agent + 节奏规则 + AI 素材 | ⏳ |
| M4 质检与全流程自动化 | ⏳ |
| M5 局部修改、续跑、运维 | ⏳ |

## 环境隔离

- 本地：`ROXY_ENV=local`、`COMPOSE_PROJECT_NAME=roxy-local`，配置模板 `.env.example`（localhost + 映射端口）。
- VM：`ROXY_ENV=vm`、`COMPOSE_PROJECT_NAME=roxy-vm`，配置模板 `.env.vm.example`（容器服务名 `postgres/rabbitmq/redis/minio`）。
- 容器名、网络、数据卷按环境前缀隔离；后端所有服务地址只从 `Settings` / 环境变量读取，业务代码不写死地址。

## 快速开始

### M1 本地渲染（已可运行）

```bash
git clone https://github.com/Tsuki11111/roxy-pipeline.git
cd roxy-pipeline
UV_DEFAULT_INDEX=https://pypi.tuna.tsinghua.edu.cn/simple uv sync
uv run playwright install chromium
uv run pytest -q
uv run python scripts/render_demo.py
```

输出：`tmp/render_demo/demo_episode.mp4`（3 镜头、12 秒、1920×1080、25fps、H.264/AAC）。
只出静帧调布局：

```bash
uv run python scripts/render_demo.py --stills-only --still-ms 2000 --still-out tmp/render_demo/still_2s.png
```

> 当前 demo 引用本地 `character_packs/roxy/` 与 `tmp/seedream_assets/`，这些素材不进公开仓库；公开复现需要后续补 placeholder pack。

### M1.1 API / 基础设施

本地无 Docker 时默认 SQLite：

```bash
uv run alembic upgrade head
uv run uvicorn app.api.main:app --reload --port 8000
# http://localhost:8000/docs
```

使用 compose 基础设施（默认 Postgres / RabbitMQ / Redis；MinIO 走 storage profile）：

```bash
docker compose -f compose.infra.yml up -d
# 把 .env 的 DATABASE_URL 改为 postgresql+asyncpg://roxy:roxy-dev@localhost:5433/roxy
uv run alembic upgrade head
```

> MinIO 用 `docker compose -f compose.infra.yml --profile storage up -d`。RabbitMQ 4.4 通过 `infra/rabbitmq.conf` 允许 Celery pidbox 的临时非独占回复队列。

### M1.2 队列渲染（需要 RabbitMQ / Redis）

```bash
docker compose -f compose.infra.yml up -d
# .env 本机原生进程用 localhost：
# DATABASE_URL=postgresql+asyncpg://roxy:roxy-dev@localhost:5433/roxy
# RABBITMQ_URL=amqp://roxy:roxy-dev@localhost:5673//
# REDIS_URL=redis://localhost:6380/0
uv run alembic upgrade head
uv run uvicorn app.api.main:app --reload --port 8000
```

另开两个终端启动 worker 和 beat：

```bash
uv run celery -A app.workflow.celery_app worker -Q workflow,agent,render -l info -c 2
```

> Windows 本机调试要加 `--pool=solo`（Celery prefork 在 Windows 不可用）；并行渲染在 Linux VM 上用默认 prefork `-c 2`。

```bash
uv run celery -A app.workflow.celery_app beat -l info
```

触发一次完整链路（创建期 → 挂 render spec → outbox → RabbitMQ → render worker → 成片）：

```bash
uv run python scripts/queue_demo_render.py --base-url http://localhost:8000
```

> 已在本机 Postgres + RabbitMQ + Redis 上实测：3 镜头 6.00 秒成片，outbox DISPATCHED、episode READY。

公开占位素材可直接复现：

```bash
uv run python scripts/render_demo.py --spec specs/demo_placeholder.json --out tmp/render_demo/placeholder.mp4
```

### M2 脚本生成

确认选题会转 `SCRIPTING` 并投递 `script.generate` 到 `agent` 队列：

```bash
curl -X POST http://localhost:8000/api/v1/episodes/<episode_id>/actions/confirm-topic
```

查看/校验脚本：

```bash
curl http://localhost:8000/api/v1/episodes/<episode_id>/script
```

校验通过后确认脚本进入分镜阶段：

```bash
curl -X POST http://localhost:8000/api/v1/episodes/<episode_id>/actions/confirm-script
```

脚本生成使用 `prompts/script/` 下的 Prompt 和 DeepSeek `deepseek-flash`；校验规则是单句 ≤25 字、洛琪希 ≤15 字、全文字数 ±10%、章节顺序与覆盖。

### 模型校验

```bash
cp .env.example .env
# 在 .env 填入 DeepSeek / 火山方舟 / TTS 凭据
uv run python scripts/check_llm.py --live
```

Celery/RabbitMQ worker 与 Web 前端还在 M1.2 之后，尚未接入。

## 模型配置

| 用途 | 变量 | 当前状态 |
|---|---|---|
| 文本/代码主模型 | `DEEPSEEK_MODEL=deepseek-flash` | ✅ 可用 |
| 文本备选/A-B | `ARK_MODEL_STRONG=doubao-seed-2-1-pro-260915` | ✅ 可用 |
| 图像素材 | `ARK_IMAGE_MODEL=doubao-seedream-5-0-pro-260628` | ✅ 可用（背景/舞台/演示物件） |
| 视觉质检 | `ARK_MODEL_VISION` | ❌ 暂无；先 DOM 规则 |
| TTS | `VOLC_TTS_APP_ID` / `VOLC_TTS_ACCESS_TOKEN` | ⏳ 待配置 |

- DeepSeek Base URL：`https://api.deepseek.com`
- 火山方舟 Base URL：`https://ark.cn-beijing.volces.com/api/v3`
- 校验脚本：[scripts/check_llm.py](scripts/check_llm.py)；Key 只在本地 `.env`，不会提交。

## 文档

| 文件 | 作用 |
|---|---|
| [HANDOFF.md](HANDOFF.md) | **状态层权威源** —— 当前进度、下一步、踩过的坑 |
| [CLAUDE.md](CLAUDE.md) | 给 AI 助手的项目约定与协作偏好 |
| [docs/AI科普视频Agent系统需求分析文档.md](docs/AI科普视频Agent系统需求分析文档.md) | 需求范围、验收标准、版权约束 |
| [docs/AI科普视频Agent系统架构选型方案.md](docs/AI科普视频Agent系统架构选型方案.md) | 技术选型、模块/服务拆分、渲染流水线、接口 |
| [docs/decisions-architecture.md](docs/decisions-architecture.md) | ADR：为什么这样选、代价是什么 |
| [.env.example](.env.example) | 环境变量模板；真实值填本地 `.env` |

> 本 README 是 [HANDOFF.md](HANDOFF.md) 的**精简报告**。两者内容允许重复；
> 当前状态如有出入，一律以 HANDOFF 为准。

## 说明

- 仓库**不包含**受版权保护的角色参考图、立绘、BGM 或未授权字体；洛琪希资产包由使用者本地提供并遵守非商业同人约束。
- 洛琪希等版权角色立绘由用户提供；Seedream 只做背景/舞台/演示物件，不能复刻洛琪希。
- Seedream 实测会对洛琪希名称、参考图或高度相似特征触发版权过滤；不要尝试绕过。
- 公开仓库只保留文字规格和后续的原创占位素材（占位素材尚未创建）。
- 许可证待定；在选定前保留所有权利。

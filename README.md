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
**当前阶段**：架构设计完成，代码尚未开始。仓库只包含文档、环境模板和模型校验脚本。

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
| M1 渲染链路（手写脚本 → 成片） | ⏳ 下一步 |
| M2 脚本 Agent（LangGraph） | ⏳ |
| M3 分镜 Agent + 节奏规则 + AI 素材 | ⏳ |
| M4 质检与全流程自动化 | ⏳ |
| M5 局部修改、续跑、运维 | ⏳ |

## 快速开始

**代码尚未实现**；当前只能克隆文档和运行模型校验。M1 完成后会补 `docker compose up` 一键启动。

```bash
git clone https://github.com/Tsuki11111/roxy-pipeline.git
cd roxy-pipeline
cp .env.example .env
# 在 .env 填入 DeepSeek / 火山方舟 / TTS 凭据
python scripts/check_llm.py --live
```

M1 目标启动方式（待实现）：

```bash
docker compose up -d
# 打开 http://localhost:8080
```

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

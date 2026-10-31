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

**AI 科普视频自动生成 Agent 系统**：从文章导入、AI 拆解润色、分镜，到逐句 TTS、卡片/逐帧渲染、ffmpeg 拼接和质检的全自动流水线。

**定位**：个人自用项目；洛琪希为《无职转生》角色，仅限非商业同人使用，遵守[需求文档第 11 章](docs/AI科普视频Agent系统需求分析文档.md)。
**当前阶段**：M1 渲染原型 + M1.1 API/DB + M1.2 队列/渲染 worker + 文章导入/文稿优化 Agent + M3 分镜 Agent + 资产持久化/复用 + Asset Agent + M4.1 逐句配音 + M4.2 句级对齐（字级可选） + M4.3 规则/DeepSeek 多模态质检 + M5.1 局部修改/续跑/发布包 + Web 控制台 + 分镜时间线编辑器 + Remotion 逐镜头代码生成 Agent（唯一渲染器）已跑通；按主题自动生成脚本的功能已移除，下一步成本报表与监控。

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
| 渲染 | Remotion（每镜头 LLM 生成 TSX，Docker 沙箱，唯一生产渲染器）+ ffmpeg |
| 文本模型 | DeepSeek `deepseek-flash`（主）；火山方舟豆包 Pro（备选/A-B） |
| TTS | 本地 IndexTTS2 zero-shot（Python 3.11 + torch 2.8 cu128，常驻服务） |
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
   状态机      LangGraph      TTS/对齐      Seedream    Remotion
   重试/补偿   脚本/分镜/QC   音频装配      素材候选      + ffmpeg
```

流水线：**文章导入 → AI 脚本/润色 → 分镜 → TTS → 对齐 → 卡片 → 镜头 → 拼接 → 质检 → 发布包**。

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
| 文章导入/文稿优化 Agent | ✅ DeepSeek 理解长文、拆章节问题、生成台词、润色；不再按主题自动生成脚本 |
| M3 分镜 Agent + 节奏规则 | ✅ `storyboard_graph` + 确定性节奏修复；半身反应镜头/章首滑入已接入，Seedream 素材按需生成 |
| M3.1 资产持久化/复用 | ✅ `asset` 表 + `data/assets` + `reuse_key`；生成前查重，生成后入库 |
| Asset Agent | ✅ 文本→无文字演示素材；优先 `reuse_key` 复用，缺失才调 Seedream |
| M4 源 TTS（IndexTTS2） | ✅ 本地 zero-shot 克隆 + 常驻服务；长文本 RTF 1.75 |
| M4.1 逐句配音 + 音轨 | ✅ `line_audio` + media 任务 + 句级对齐 + 真实音轨成片 |
| M4.2 对齐 | ✅ 默认句级，字幕整句显示；字级 wav2vec2 强制对齐可选 |
| M4.3 质检与报告 | ✅ 规则前置 + DeepSeek 抽帧质检；review 表与 QC API |
| M5.1 局部修改/续跑/发布包 | ✅ 单句修订、镜头缓存、通用续跑、stale reconciler、本地发布包、时间戳输出目录 + MinIO |
| Web 控制台 | ✅ 总览、视频期流程动作、脚本/分镜/音频/QC/发布包、资产生成与审批、分镜时间线编辑器 |
| M6 Remotion 代码生成 Agent | ✅ 每镜头 DeepSeek 生成自由 TSX + Docker 沙箱校验/渲染 + 镜头级缓存；Playwright 仅测试/历史 |
| M5.2 成本与监控 | ⏳ token/TTS 成本报表、告警与运维面板 |

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
uv run python scripts/demo/render_demo.py
```

输出：`tmp/render_demo/demo_episode.mp4`（3 镜头、12 秒、1920×1080、25fps、H.264/AAC）。
只出静帧调布局：

```bash
uv run python scripts/demo/render_demo.py --stills-only --still-ms 2000 --still-out tmp/render_demo/still_2s.png
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

另开终端启动 worker（渲染）和 beat；配音另起一个媒体 worker，TTS 并发固定为 1：

```bash
uv run celery -A app.workflow.celery_app worker -Q workflow,agent,render -l info -c 2
```

```bash
uv run celery -A app.workflow.celery_app worker -Q media -l info -c 1
```

> Windows 本机调试要加 `--pool=solo`（Celery prefork 在 Windows 不可用）；并行渲染在 Linux VM 上用默认 prefork `-c 2`。media worker 常驻 IndexTTS2 模型；默认句级对齐，开启 `ALIGN_LEVEL=char` 时才执行字级对齐，TTS 与字级对齐都必须单并发。

> 16GB 本机默认 `TTS_UNLOAD_AFTER_VOICE=true`：配音结束停掉常驻 TTS，对齐前再兜底 `/shutdown`；每镜头渲染、对齐、QC、拼接结束都会回收内存，TTS 下次配音自动重启。

> 每个镜头独立按自己的起点初始化渲染器；角色从最近侧屏幕外 280ms 冲入，旧角色 80ms 模糊让位，只预加载本镜头素材。卡片与字幕换镜时直接切换，不再从透明淡入。

```bash
uv run celery -A app.workflow.celery_app beat -l info
```

触发一次完整链路（创建期 → 挂 render spec → outbox → RabbitMQ → render worker → 成片）：

```bash
uv run python scripts/demo/queue_demo_render.py --base-url http://localhost:8000
```

> 已在本机 Postgres + RabbitMQ + Redis 上实测：3 镜头 6.00 秒成片，outbox DISPATCHED、episode READY。

公开占位素材可直接复现：

```bash
uv run python scripts/demo/render_demo.py --spec specs/demo_placeholder.json --out tmp/render_demo/placeholder.mp4
```

### 文稿导入与润色

不再按主题自动生成脚本；视频期通过「导入文稿」创建，或对已有空期调用导入接口：

```bash
curl -X POST http://localhost:8000/api/v1/episodes/<episode_id>/actions/import-script \
  -H "Content-Type: application/json" \
  -d '{"article":"完整文章正文...","optimize":true}'
```

查看/校验脚本：

```bash
curl http://localhost:8000/api/v1/episodes/<episode_id>/script
```

校验通过后可以先润色文稿：保持章节/句数不变，把整段口播改得更口语、增加生活例子，让洛琪希语气更丰富：

```bash
curl -X POST http://localhost:8000/api/v1/episodes/<episode_id>/actions/optimize-script \
  -H "Content-Type: application/json" \
  -d '{"apply":true}'
```

润色后必须重新通过同一套校验；不通过不会写回。确认脚本进入分镜阶段：

```bash
curl -X POST http://localhost:8000/api/v1/episodes/<episode_id>/actions/confirm-script
```

脚本由 `prompts/script/article.md` 和 DeepSeek `deepseek-flash` 生成，润色用 `prompts/script/optimize.md`；校验规则是单句 ≤50 字、全文字数 ±10%、章节顺序与覆盖。所有台词统一由洛琪希单人口播，不设旁白。

- 支持最多 30000 字；前端视频期页提供「导入文稿」按钮，可直接粘贴或上传 `.txt`/`.md`。
- 导入后保持 series 的章节标签顺序，生成问题式小标题和逐句台词。
- 自动跑脚本校验和可选润色；导入后进入 `SCRIPT_REVIEW`。校验不通过会标记 WARNING，`confirm-script` 仍会拦截，先修稿再确认。
- 视频期列表和详情页都有「取消」，运行中状态也可 `POST /api/v1/episodes/{id}/actions/cancel`；「删除」只清数据库记录和关联行，不动 `output/` 和 MinIO 成片，运行中的期必须先取消再删。

### M3 分镜生成

确认脚本后，生成分镜：

```bash
curl -X POST http://localhost:8000/api/v1/episodes/<episode_id>/actions/generate-storyboard
```

查看分镜与节奏报告：

```bash
curl http://localhost:8000/api/v1/episodes/<episode_id>/storyboard
```

校验通过后确认分镜（进入 VOICING），再把 shot 表转成渲染 spec：

```bash
curl -X POST http://localhost:8000/api/v1/episodes/<episode_id>/actions/confirm-storyboard
```

```bash
curl -X POST http://localhost:8000/api/v1/episodes/<episode_id>/actions/build-render-spec
```

节奏规则是纯函数：连续 3 个同卡片、角色连续 5 个、章节末非 icon/pure_text、时长越界都会被确定性修复器拦住；`PATCH /api/v1/shots/{id}` 可手工改单个镜头。

### 资产入库与复用

把已有图片索引到数据库；`tmp/seedream_assets` 的背景/物件会复制到 `data/assets`，角色包在原目录索引：

```bash
uv run python scripts/tools/ingest_assets.py
```

查询可复用资产：

```bash
curl "http://localhost:8000/api/v1/assets?type=background&status=APPROVED"
```

生成新图时先给 `reuse_key`；命中 APPROVED 资产就不会调用 Seedream：

```bash
uv run python scripts/tools/generate_seedream_image.py --prompt "..." --out tmp/new_bg.png --asset-type background --reuse-key bg:paper:dark
```

新图默认以 `CANDIDATE` 入库，人工筛选后调用 `POST /api/v1/assets/{id}/approve` 才会被复用。所有新入库/索引的图片会同时镜像到 MinIO 的 `MINIO_BUCKET_ASSETS`，对象路径为 `assets/<type>/<checksum前16位>.<ext>`，记录在 `asset.meta["minio"]`。

### 文本生成演示素材 Agent

把一段科普文本交给 Asset Agent，它会规划无文字的 background/prop/icon/cover，先按 `reuse_key` 查已有资产，命中就复用，缺失才调用 Seedream 生成候选：

```bash
curl -X POST http://localhost:8000/api/v1/assets/generate \
  -H "Content-Type: application/json" \
  -d '{"text":"解释太阳光穿过三棱镜后为什么会出现七色光带","count":1}'
```

- 不生成角色立绘、动漫人物或带文字的信息卡片。
- 新图默认 `CANDIDATE`；`auto_approve=true` 且 DeepSeek 视觉检查通过时才直接 `APPROVED`。
- `IMAGE_PROVIDER=mock` 可本地跑通流程，不调用 Seedream。
- 按整期文稿生成时用 `POST /episodes/{id}/actions/generate-assets`：Agent 读取 `script_line` 的章节和台词，生成结果记录 `episode_id`，不是脱离文稿的自由生成。

### Web 控制台

```bash
cd web
npm install
npm run dev
```

- 默认 `http://127.0.0.1:5173`，Vite 把 `/api` 和 `/health` 代理到 `http://127.0.0.1:8000`。
- 页面：总览、视频期列表/详情、资产库。
- 详情页可直接导入/润色文稿、生成与确认分镜、配音、对齐、QC、渲染、发布包和发布，运行中显示节点进度并支持取消。
- 详情页「剪辑」tab 是分镜时间线编辑器：成片预览 + 镜头时间线 + 视觉属性面板；可改卡片类型/文案、角色立绘/位置、背景、动作和入场方向，保存后只重渲染受影响镜头。
- 资产库支持按文稿生成素材、审批/拒绝、DeepSeek 图片检查。
- 生产构建：`npm run build`，产物在 `web/dist/`。

### 分镜编辑器（视觉属性）

详情页「剪辑」tab：

- 上方是上一次成片预览；点时间线镜头会跳转到对应时间点。
- 时间线按镜头时长排布，显示镜头号、卡片类型和时长。
- 属性面板可改卡片类型/文案、角色立绘/位置、背景、动作、入场方向；镜头时长由配音决定，只读。
- **贴图层**：可上传 PNG/JPG/WebP，或输入描述让 DeepSeek 写 Seedream 提示词后在线生成候选；可调位置/宽度/底部距离/不透明度，白底素材选「白底融合」（multiply）。
- 「保存镜头」只写 `shot` 与缓存键；「保存并重渲染」会重建 `render_spec` 并投递渲染，未变化的镜头复用片段缓存。
- 预览基于上一次成片，重渲染完成后自动刷新视频。
- 相关 API：`GET /api/v1/episodes/{id}/video`、`POST /api/v1/episodes/{id}/actions/rerender`、`PATCH /api/v1/shots/{id}`（`card_text` / `overlay_*`）、`POST /api/v1/assets/upload`、`POST /api/v1/assets/image-prompt`、`POST /api/v1/assets/seedream`、`GET /api/v1/assets/file`。
- Seedream 生成的素材默认 `CANDIDATE`，可直接应用到镜头，后续在资产库审批；不可生成洛琪希等已有版权角色。

### Remotion 渲染（默认）

镜头画面只由 Remotion 渲染；`REMOTION_ONLY=true`，Playwright 仅保留测试/历史。

- 编辑器「Remotion 渲染」卡片点「生成 Remotion 代码」，或 `POST /api/v1/episodes/{id}/actions/generate-remotion`。
- 每个镜头单独调用一次 DeepSeek，生成自由 TSX；Python 负责 `Root.tsx`、时长、素材映射和 Composition 注册。
- 代码在 Docker 沙箱里 `tsc` + `remotion compositions` 校验，失败自动带编译错误重试一次。
- 全部镜头 READY 后 `remotion_meta.enabled=true`，后续 `POST /actions/rerender` 自动走 Remotion；新期在配音/对齐完成后会**自动排队 Remotion codegen 再渲染**（`REMOTION_AUTO_CODEGEN=true`），失败或未全部 READY 时标记失败、不渲染（Playwright 已禁用）。
- 生成过程中可在编辑器点「取消生成」，或调用 `POST /api/v1/episodes/{id}/actions/cancel-remotion`；已就绪的旧代码会保留。
- 渲染缓存键包含 renderer、Remotion 版本、镜像 digest 和该镜头 code hash，只失效受影响的镜头。

构建沙箱镜像（仓库根目录）：

```bash
docker build -f infra/remotion/Dockerfile -t roxy-remotion:4.0.539 .
```

- Docker 必须可用；镜像 tag 与 `REMOTION_IMAGE` 一致（默认 `roxy-remotion:4.0.539`）。
- 沙箱无网络、只读根文件系统、非 root、限制 CPU/内存/PID；生成代码只写 `tmp/remotion/<episode_id>/`，不进仓库。
- 生成代码受 Skill 约束：单镜头 ≤9000 字符、浅底深字、有角色必须出现；画面文字用 `PaperCard` Claude 暖纸卡（6 种样式、4 种纸色），约 1/3 镜头纯演示不放卡；切换配方在 slide/zoom/flip/drop/reveal/push 中轮换，位移 ≥300px、缩放变化 ≥0.3、旋转 ≥5° 或 rotateY ≥45°。
- 背景与字幕也使用 Claude 纸墨语言：暖纸舞台 + 底部浅阴影，字幕为暖纸底、墨字、陶土短线。
- 有角色的镜头必须有动效：从屏幕外冲入、呼吸轻摆、至少一次手势/让位；静态 `<Character>` 会被生成检查拦下。
- 视觉风格必须服务内容：同一期统一色调、材质、线条和图形语言；禁止与主题无关的赛博霓虹/故障/机器人装饰。
- 字幕由 Python 生成 Root 时统一叠加 `SubtitleTrack`，按句级时间轴显示；生成代码不画字幕。
- 改动 `app/agents/remotion/templates/` 后需要重新构建镜像，沙箱才会使用新组件。
- Remotion 许可：个人/非商业项目免费；商用需另行获得 Remotion 授权。

### 成片输出与 MinIO

每次渲染完成，成片会复制到时间戳目录：

```text
output/20261029-185432_8c7ade6b/
├─ episode.mp4
└─ metadata.json
```

- `OUTPUT_ROOT=./output`（VM 为 `/data/output`）。
- `MINIO_UPLOAD_ENABLED=true` 时同时上传到 `MINIO_BUCKET_OUTPUT`，对象路径为 `episodes/<输出目录名>/episode.mp4`。
- 本地 MinIO 未启动时默认只记录 `minio_error`，不阻塞成片；VM 设置 `MINIO_REQUIRED=true` 后上传失败会判定渲染失败。
- `episode.output_path` 指向 output 目录，`episode.output_meta` 记录本地路径和 MinIO URI。

### 模型校验

```bash
cp .env.example .env
# 在 .env 填入 DeepSeek / 火山方舟凭据
uv run python scripts/tools/check_llm.py --live
```

Celery/RabbitMQ worker 已在快速开始中给出启动命令；Web 控制台见上一节。

## 模型配置

| 用途 | 变量 | 当前状态 |
|---|---|---|
| 文本/代码主模型 | `DEEPSEEK_MODEL=deepseek-flash` | ✅ 可用 |
| 文本备选/A-B | `ARK_MODEL_STRONG=doubao-seed-2-1-pro-260915` | ✅ 可用 |
| 图像素材 | `ARK_IMAGE_MODEL=doubao-seedream-5-0-pro-260628` | ✅ 可用（背景/舞台/演示物件） |
| 视觉质检 | `DEEPSEEK_MODEL=deepseek-flash`（多模态：图片/视频抽帧） | ✅ 可用 |
| TTS | `TTS_PROVIDER=indextts2` + `data/assets/voice/indextts2/` | ✅ 本地 IndexTTS2 zero-shot |
| 对齐 | `ALIGN_LEVEL=sentence`（默认）/ `char` + `ALIGN_MODEL_DIR` | ✅ 默认句级；字级可选 |

- DeepSeek Base URL：`https://api.deepseek.com`
- 火山方舟 Base URL：`https://ark.cn-beijing.volces.com/api/v3`
- 校验脚本：[scripts/tools/check_llm.py](scripts/tools/check_llm.py)；Key 只在本地 `.env`，不会提交。

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

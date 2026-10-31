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

**M1 渲染原型 + M1.1 API/DB + M1.2 队列/渲染 worker + 文章导入/文稿优化 Agent + M3 分镜 Agent + 资产复用/持久化 + M4.1 逐句配音 + M4.2 句级对齐（字级可选） + M4.3 质检 + M5.1 局部修改/续跑/发布包 + Web 控制台 + 分镜时间线编辑器 + Remotion 逐镜头代码生成 Agent（唯一生产渲染器）+ 真实音轨成片已跑通（2026-10-30）；按主题自动生成脚本已移除。**

- 需求文档 v1.2、架构方案 v1.10、ADR-001～010 已写完。
- GitHub 仓库已创建：<https://github.com/Tsuki11111/roxy-pipeline>（Public）。
- 本地 initial commit 与文档规范化 commit 已推送到 `origin/main`（2026-10-26）。
- `.env`、洛琪希参考图、`tmp/` 已由 `.gitignore` 排除；仓库只提交 `.env.example`。
- 模型验证：
  - DeepSeek `deepseek-flash`：**PASS**。
  - 火山方舟 `doubao-seed-2-1-pro-260915` / `lite`：**PASS**；`turbo` 仍 `ModelNotOpen`。
  - 火山方舟 Seedream 5.0 Pro：**PASS**（关闭安全体验模式后，1024×1024 测试成功）。
  - 视觉质检：统一用 `deepseek-flash` 多模态；图片直接读图，视频按镜头抽帧 + ffmpeg 指标；不接豆包 Vision。
  - 火山 TTS：不使用（改为本地 IndexTTS2），云 TTS 凭据不再是 M4 前置条件。
- 角色包：正式资产选用豆包版 `character_packs/roxy/roxy_calm_standing_01.png`（1080×1920 RGBA，水印已排除，本地，gitignored）；ChatGPT 版留在 `alternates/`。Seedream 不能生成洛琪希。
- Batch 1 已完成：R-02 疑惑、R-03 惊讶、R-04 无奈、R-05 得意、R-06 思考，共 6 张入库；首版最低 18 张，还差 12 张。
- Batch 2 已完成：R-07 专注、R-09 认真、R-11 指向、R-16 开口、R-17 讲解指向，共 11 张入库；首版最低 18 张，还差 7 张。
- Batch 3 已完成：R-08 害羞、R-12 震惊、R-13 微笑、R-14 沉思、R-15 气鼓鼓，共 16 张入库；首版最低 18 张，还差 2 张（R-10 坐姿 + 至少 1 个闭/开口变体）。
- Batch 4 已完成：R-10 坐姿、R-01v 平静开口（重生成替换闭嘴版）、R-02v 疑惑开口、R-16v 说话闭口、R-18 白板讲解，共 21 张；最低 18 张已达标。
- Batch 5 已完成：R-19 敲键盘、R-20 调试翻车、R-21 灵光一现、R-22 怀疑审视，共 25 张；剩余 AI 主题 R-23～R-28 共 6 张。
- R-19 已完成重做：坐姿木桌版 `roxy_typing_sitting_01.png` 入正式资产；旧站立版移到 `alternates/`。
- Batch 7 已完成：R-28 被代码包围、R-29 跳跃欢呼、R-30 奔跑、R-31 后仰失衡、R-32 伸手抓取入库，共 35 张；R-29 保留 220px 脚下空档。
- Batch 8 已完成：R-33 抱 GPU、R-34 放大镜、R-35 推白板（场景资产 1536×1799 紧裁切）、R-36 大喇叭、R-37 提示牌入库，共 40 张。
- Batch 9 已完成：R-38 拉网线（场景资产 1124×1819，左边缘/网线底部贴画布边，用户接受）、R-39 抱 AI 机器人、R-40 举灯泡、R-41 修服务器、R-42 端托盘入库，共 45 张。
- Batch 10 全部 10 张已入库：B-01～B-05 + B-06 灵光、B-07 怀疑、B-08 崩溃、B-09 害羞、B-10 认真，共 55 个正式资产；1080×1350。B-09 为构图模板：人物/辫子/发带完整在画布内，腰部截断线不贴底边，底部留白。
- 新约束（2026-10-28）：角色不能全程静止；换位/让位/配合道具时，角色与物件作为整体做 120–300ms 的自然快速平移（参考 BV1BgH36DE7y）。已写入需求 F-47 与架构 10.11，待渲染阶段实现。
- 新约束（2026-10-28）：本地 Docker 与 VM 资源必须隔离；后端服务地址全部从环境变量/`Settings` 读取，不写死 `localhost`、VM IP 或容器名。已加 `ROXY_ENV`/`COMPOSE_PROJECT_NAME` 环境隔离、`.env.vm.example` 模板。
- 新约束（2026-10-29）：所有视觉模型调用统一用 `deepseek-flash` 多模态；生成图片资产直接读图检查，完整视频用抽帧 + ffmpeg 指标检查；不接入豆包 Vision 等第二视觉模型。
- 新约束（2026-10-29）：音色克隆只能用用户本人或明确授权的声音；禁止动画原声/声优本人音频克隆。当前方案为本地 IndexTTS2 zero-shot，参考音与模型放 `data/assets/voice/`，不提交公开仓库。
- Batch 6 已完成：R-23 戴眼镜、R-24 咖啡、R-25 摊手、R-26 数据展示、R-27 庆祝，共 30 张；只剩 R-28 被代码包围。
- M1 渲染链路原型已跑通：手写 3 镜头 JSON → 舞台 HTML → Playwright 逐帧 → ffmpeg；12 秒/300 帧/1920×1080/25fps/H.264/AAC，单进程约 160 秒。
- 角色换姿势已改为双层交叉淡入 + 横移（180ms），字幕和卡片同步短淡入；参考片实测换姿势约 0.2 秒，不是硬切。
- M1.1 API/DB 骨架已完成：`compose.infra.yml`、FastAPI 应用、SQLAlchemy 模型、Alembic 初始迁移；`/health` 正常，7 条测试通过。
- M1.2 队列/状态机/渲染 worker 骨架已完成：`outbox_event` + dispatcher、`app/workflow/`（Celery 路由、状态机、render_service、render_tasks）、`render.shot` 按镜头并行、`render.concat` 回写 episode；eager 模式单镜头 0.5 秒端到端输出 MP4。
- M1.2 API：`PUT /episodes/{id}/render-spec`、`POST /episodes/{id}/actions/render`，以及 confirm-script/cancel/publish 状态闸口；`Episode.render_spec` 是 M1.2 的临时手工 spec，等 M3 生成分镜后替换。
- M1.2 渲染增强：`CharacterSpec` 增加 `anchor_x/anchor_y/scale`；新增公开 `character_packs/placeholder/` 与 `specs/demo_placeholder.json`；golden frame 回归测试；当前 42 条测试通过（含 M2/M3/资产层）。
- 本机 Docker 已启动；Postgres 17 + RabbitMQ 4.4 + Redis 7 实机联调通过：API → outbox → Celery → 3 镜头 6.00 秒占位成片 READY。
- RabbitMQ 4.4 默认禁止 Celery 的临时非独占回复队列，`infra/rabbitmq.conf` 已开启 `deprecated_features.permit.transient_nonexcl_queues`；Celery 升级后复查。
- 脚本来源已改为文章导入 Agent：DeepSeek 理解长文，按 series 章节标签生成问题式小标题、章节目标和逐句口播，产物写入 `script_line` + `episode.script_meta`；`POST /episodes/{id}/actions/import-script` 支持最多 30000 字，导入后进入 SCRIPT_REVIEW。所有台词统一 `speaker=roxy`，洛琪希单人口播。
- 文稿润色 Agent：`POST /episodes/{id}/actions/optimize-script` 在 SCRIPT_REVIEW 阶段做口语化润色，保持章节/句数/说话人不变，校验通过才写回。
- 脚本 API：`GET /episodes/{id}/script`、`PATCH /script-lines/{id}`、`POST /episodes/{id}/script/validate`、confirm-script（校验通过才进 STORYBOARDING）。
- 按主题自动生成脚本（`script_graph`、`script.generate`、confirm-topic、retry/regenerate-script）已于 2026-10-29 移除；历史实现见 §6。
- M3 分镜 Agent 已跑通：`storyboard_graph` 按章节让 DeepSeek 选镜头，代码做 schema 归一化 + 确定性节奏修复（连续 3 同卡片、角色连续 5、章节末 icon/pure_text、时长 1.5–6s）。
- M3 API：generate/retry/regenerate-storyboard、`GET /episodes/{id}/storyboard`、storyboard/validate、confirm-storyboard（进 VOICING）、`PATCH /shots/{id}`、build-render-spec。
- M3 实测：29 句脚本生成 29 镜头、4 种卡片、角色占比 75.9%、节奏校验 valid；confirm 进 VOICING，build-render-spec 生成 29 镜头 spec，静帧已出图。
- LLM JSON 增加 `json-repair` 兜底；分镜单次输出上限提高到 `max(2000, 行数×220)`，避免截断。
- M3 已补：Seedream 生成 Agent 已实现（批量仍按需触发）、半身反应镜头/章首滑入已接入分镜与渲染；剩余 P1 多模态分镜评审、物件/卡片同组位移。
- 资产复用已落地：`asset` 表 + `data/assets` 持久化仓库；已有 3 张背景 + 7 个物件复制入库、56 个角色在原目录索引；`build-render-spec` 自动解析入库的纸纹/木地板。
- `generate_seedream_image.py` 生成前查 `reuse_key`，命中 APPROVED 直接复用；生成后默认以 CANDIDATE 入库，`/assets/{id}/approve` 后才可复用。`scripts/tools/ingest_assets.py` 可批量索引已有图片。
- M4 音色已定：本地 **IndexTTS2** zero-shot 克隆，用户试听长文本后确认“效果非常好”。模型 `IndexTeam/IndexTTS-2` 在 `data/assets/voice/indextts2/`，参考音固定为 `data/assets/voice/indextts2/reference.wav`；RVC v3 / MeloTTS / Piper 已停用并清理，旧模型与工具链约 5GB 已删除。
- M4.1 逐句配音已跑通：`line_audio` 表按 `(script_line, text_hash, voice_key)` 缓存；`voice.episode` 在 media 队列逐句合成，音频按内容寻址存 `data/audio/lines/`，自动回写镜头时长并装配 `audio.wav`（-14 LUFS），句级对齐写入 `episode.audio_meta`；默认自动进入 RENDERING，成片封装真实 AAC 音轨。实测 3 句 / 10.25 秒成片通过。
- M4.2 对齐已跑通：默认句级（`ALIGN_LEVEL=sentence`），`voice.episode` 产出每句 start/end 并写 `audio_meta`，字幕整句显示，不加载对齐模型。字级为可选：`align.episode` 用中文 wav2vec2（`jonatasgrosman/wav2vec2-large-xlsr-53-chinese-zh-cn`）对每句做 CTC 强制对齐，字级时间写入 `audio_meta.lines[].chars` 和 `alignment.json`；模型在 `data/assets/voice/align/wav2vec2-chinese/`（1.2GB），显存不足自动回退 CPU。
- M4.3 质检已跑通：`render.concat` 完成后默认进入 QC；规则检查流参数/时长/响度/对齐/字幕/资产，再按镜头抽首帧+中间帧送 `deepseek-flash` 多模态；结果写 `review` 表与 `episode.qc_meta`。视觉问题默认 warning，`QC_VISION_BLOCKING=true` 才作为 error；图片资产可单独 `POST /assets/{id}/check`。
- M5.1 已跑通：`POST /episodes/{id}/actions/revise-line` 改单句后重置到 VOICING，只重合成变化句、重对齐并重渲染；镜头片段带 hash 缓存，未变化镜头直接复用；`POST /actions/resume` 按当前状态续跑；`workflow.reconcile_nodes` 清理 stale RUNNING 节点；`POST /actions/package` / `POST /actions/publish` 生成本地发布包（视频、封面、SRT、脚本、metadata、音频）。
- 最终视频输出：渲染完成后复制到 `output/YYYYMMDD-HHMMSS_<episode_id前8位>/episode.mp4`，同目录写 `metadata.json`；`episode.output_path` 指向该路径，`episode.output_meta` 记录本地路径与 MinIO URI。MinIO 上传由 `MINIO_UPLOAD_ENABLED` 控制，VM 可设 `MINIO_REQUIRED=true` 强制成功。
- M6 Remotion 代码生成 Agent 已跑通（2026-10-30）：`app/agents/remotion/` 每镜头调用一次 DeepSeek 生成自由 TSX，Python 生成 `Root.tsx`/Composition（ID 用 `Shot-0001`，组件名 `Shot_0001`）；代码在 Docker 沙箱 `tsc --noEmit` + `remotion compositions` 校验，失败带编译错误重试一次；全部镜头 READY 才 `remotion_meta.enabled=true`，`POST /actions/rerender` 自动切 Remotion，失败直接报错，不再回退 Playwright。
- Remotion 沙箱镜像 `roxy-remotion:4.0.539` 由 `infra/remotion/Dockerfile` 构建；运行参数 `--network none --read-only --user 10001 --cpus 2 -m 3g --pids-limit 256`，`/tmp` 与 `/app/node_modules/.cache` 挂 tmpfs。
- **新期自动 codegen（2026-10-31 补）**：配音/对齐完成后 `start_auto_render` 先排队 `remotion.generate`（`REMOTION_AUTO_CODEGEN=true`），codegen 成功后自动 `start_render`；失败/部分 READY 时标记失败，不回退 Playwright。这样新导入的期不需要手动点「生成 Remotion 代码」。
- Remotion 实测：11 镜头整期真实 DeepSeek 生成 + Docker 渲染 + ffmpeg `-c copy` 拼接 + QC 全通过（最终 `health=OK`，0 warning）。首版因生成代码“浅底浅字”被 QC 报 4 条对比度 warning；补 Skill 配色约束并重生成后消失。最终改为 Claude 暖纸 `PaperCard` + 纯演示镜头混排。生成代码在 `tmp/remotion/<episode_id>/`，不进仓库。
- Remotion 生成质量约束：单个镜头代码 ≤7000 字符/180 行；浅色纸纹背景必须用深色字，白字只能放在 alpha ≥0.75 的深色实底上；有 `character` 时必须画 Roxy。早期不写这些约束时会出现“浅底浅字”与整镜头无角色。
- Remotion 缓存键：`shot_render_hash` 包含 renderer、Remotion 版本、镜像 digest、该镜头 code hash；代码或镜像变化只失效受影响镜头。
- Remotion 字幕（2026-10-30 补）：Python 生成 Root 时给每个 Composition 包一层 `SubtitleTrack`，按 `build_timeline` 的句级 chunks（转成镜头内相对时间）显示底部字幕；生成代码不画字幕。`renderer_version=m6.1-subtitles`，字幕层变化会让镜头缓存失效。
- Remotion 前端：编辑器「Remotion 渲染」卡片支持整期/单镜头生成、状态表、代码预览、「用 Remotion 重渲染」；API 为 `POST /actions/generate-remotion`、`GET /episodes/{id}/remotion`、`GET /episodes/{id}/remotion/shots/{shot_id}`。
- DeepSeek 输出上限：Remotion 单镜头代码用 `max_tokens=16384`（6000/8192 都会截断长镜头）；provider 会检测 `finish_reason=length` 并按失败重试，不再把截断 JSON 当成功。
- 当前阶段仍以角色立绘为主；背景/舞台/演示物件可按需通过 Asset Agent 生成，不再固定暂停。
- AI 主题扩展：需求新增 R-17～R-28（讲解指向/白板/敲键盘/调试翻车/灵光一现/怀疑审视等），核心 6 个提示词在 `character_packs/roxy/ai_pose_prompts.md`（本地）。背景已出纸纹 + 木地板；道具在生成中。
- 代码：`app/agents`、`app/voice`、`app/qc`、`app/render`、`app/workflow`、`web/` 均已落地；SSE 与登录权限未接。

---

## 2. 下一步做什么

### 2.1 立即

1. **Remotion 整期验收**：用 11 镜头真实成片抽查字幕/标注对比度与角色出现率；单镜头不满意可在编辑器里只重新生成该镜头，再「用 Remotion 重渲染」。VM 部署前先预构建 `roxy-remotion:4.0.539` 镜像。
2. **进入 M5.2 成本与监控**：M5.1 已闭环局部修改/续跑/发布包；下一步补 token/TTS 成本报表、告警和运维面板。
3. **M6 二阶段（可选）**：Remotion 代码在线编辑/候选对比、失败自动修复、按镜头类型路由模型、成本统计。
4. **M3 P1 待补**：多模态分镜评审、物件/卡片同组位移。
5. **VM 部署**：数据盘 ≥200GB，按 §4.4 起 `roxy-vm` 栈。

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
- `specs/demo_episode.json`：3 镜头、12 秒；`scripts/demo/render_demo.py` 输出 `tmp/render_demo/demo_episode.mp4`。
- `uv run pytest` 7 条通过；demo 视频 1920×1080 / 25fps / H.264 / AAC 48kHz。
- `compose.infra.yml`：Postgres / RabbitMQ / Redis / MinIO + minio-init，端口避开现有栈（5433/5673/15673/6380/9100/9101）。
- FastAPI：`app/api`、`app/models`、`app/schemas`、`app/core`；`/health`、`/api/v1/series`、`/api/v1/episodes`。
- Alembic 初始迁移：`series` / `episode` / `script_line` / `shot` / `node_run`；本地默认 SQLite，Postgres 通过 `DATABASE_URL` 切换。

**还没做：**

- Ubuntu VM 上的 worker/beat 部署与并行压测（本机 `--pool=solo` 已验证真实队列）。
- outbox reconciler/heartbeat 扫描、失败任务自动恢复、DLQ 告警。
- 镜头级缓存与幂等复用未做；重复投递会重渲染并覆盖。
- `render_spec` 仍是手工 JSON；等 M2/M3 由脚本/分镜生成。
- 2 期并行与每期渲染信号量（Redis）；SSE 进度；Web UI。
- agents/media worker、TTS/对齐/质检。

**M1.2 已完成（2026-10-28）：**

- Celery 队列路由 + `outbox_event` + dispatcher（beat 每 5 秒补投）。
- 状态机与人工闸口 API：confirm-script / cancel / publish（confirm-topic 已于 2026-10-29 移除）。
- `render.episode` 拆分为 `render.shot` 按镜头并行，`render.concat` 拼接并回写 episode；eager 模式单镜头端到端输出 0.5 秒 MP4。
- `anchor_x/anchor_y/scale`；公开 placeholder pack + `specs/demo_placeholder.json`；golden frame 回归测试。
- 当前 42 条测试通过（含 M2/M3/资产层）。

### 2.3 M1 之后再动

- **脚本**：文章导入 + 文稿润色 Agent 已完成；按主题 `script_graph` 已移除。模型自检、成本日志归入 M5.2。
- **M3**：`storyboard_graph` + 节奏规则；Seedream 素材 Agent + 人工入库。**分镜与节奏、半身反应/章首滑入已完成**；Seedream 批量生成、物件/卡片同组位移待补。
- **M4**：TTS/对齐/质检；视觉质检先用 DOM 规则。
- **M5**：局部重渲染、断点续跑、成本报表。

### 2.4 待决事项

| 编号 | 问题 | 现状/建议 |
|---|---|---|
| Q-05 | 2 期并行是否 M1 硬指标 | 先按单期串行；资源足够再开 2 期 |
| Q-06 | `TOPIC_CONFIRMED` 语义 | 按主题生成已移除；该状态仅为历史枚举，新期从 DRAFT 直接导入文稿 |
| Q-07 | 字幕与镜头是否严格 1:1 | 数据模型支持 1:N；MVP 先 1:1 |
| Q-08 | 是否自动上传平台 | 非目标；先做本地发布包 |
| Q-11 | Seedream 1080×1920 / 参考图 | 已确认 1024×1024 可用；立绘尺寸与参考图输入待测 |
| Q-12 | `deepseek-flash` JSON 能力 | 用 Pydantic + JSON 解析兜底；实测后记录 |

---

## 3. 项目结构

当前仓库（全部模块）：

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
│  ├─ roxy/                        # 本地洛琪希 pack，gitignore
│  │  ├─ manifest.json
│  │  ├─ checklist.md
│  │  ├─ ai_pose_prompts.md
│  │  ├─ bust_prompts.md
│  │  ├─ roxy_calm_standing_01.png # 正式（豆包版，水印已排除）
│  │  └─ alternates/
│  │     └─ roxy_calm_standing_01_chatgpt.png
│  └─ placeholder/                 # 公开占位包，可提交
│     ├─ manifest.json
│     ├─ character.png
│     ├─ background.png
│     └─ floor.png
├─ app/
│  ├─ api/                         # FastAPI app + routes
│  ├─ agents/                      # 所有智能体
│  │  ├─ script/                   # 文章导入 + 文稿润色 Agent
│  │  │  ├─ importer.py            # 长文导入：章节/问题/台词结构化
│  │  │  ├─ optimizer.py           # 文稿口语化润色
│  │  │  ├─ validation.py
│  │  │  ├─ utils.py               # 脚本读取/校验/保存
│  │  │  └─ prompts.py
│  │  ├─ storyboard/               # M3 分镜 Agent
│  │  │  ├─ graph.py
│  │  │  ├─ grammar.py
│  │  │  ├─ rhythm.py
│  │  │  ├─ models.py
│  │  │  ├─ service.py
│  │  │  ├─ tasks.py               # storyboard.generate
│  │  │  ├─ prompts.py
│  │  │  ├─ loaders.py
│  │  │  ├─ utils.py               # 分镜校验/保存
│  │  │  ├─ spec_builder.py        # shot → EpisodeSpec
│  │  │  └─ render_spec.py         # 从 DB/资产构建渲染 spec
│  │  ├─ asset/                    # 文本→无文字演示素材，reuse_key 复用
│  │  │  ├─ models.py
│  │  │  ├─ prompts.py
│  │  │  └─ service.py
│  │  └─ remotion/                 # M6 每镜头 Remotion 代码生成
│  │     ├─ models.py              # ShotCodeOutput / Remotion*Meta
│  │     ├─ service.py             # 生成、校验、持久化、Root 生成
│  │     ├─ tasks.py               # remotion.generate
│  │     ├─ docker.py              # 沙箱校验/渲染
│  │     ├─ prompts.py
│  │     ├─ skills/remotion_shot/SKILL.md
│  │     └─ templates/             # 固定工程骨架 + 共享组件
│  ├─ voice/                       # M4 配音与对齐
│  │  ├─ service.py                # voice.episode 启动
│  │  ├─ tasks.py
│  │  ├─ align_service.py
│  │  ├─ align_tasks.py
│  │  └─ audio.py                  # 音轨装配/响度
│  ├─ qc/                          # M4.3 质检
│  │  ├─ rules.py
│  │  ├─ frames.py
│  │  ├─ vision.py                 # DeepSeek 多模态
│  │  ├─ service.py
│  │  └─ tasks.py
│  ├─ publish/                     # M5 发布包
│  ├─ storage/                     # 最终输出目录 + MinIO 上传
│  ├─ render/                      # 渲染、镜头缓存与拼接
│  │  ├─ models.py / timeline.py / cards.py / stage.py / capture.py / encode.py
│  │  ├─ remotion.py               # Docker 渲染 + ffmpeg 归一化
│  │  ├─ service.py                # start_render
│  │  └─ tasks.py                  # render.episode/shot/concat
│  ├─ assets/                      # 资产持久化/复用
│  ├─ providers/                   # llm / tts 适配层
│  ├─ workflow/                    # Celery、outbox、状态机、cancel、resume/revision
│  ├─ core/config.py
│  ├─ db/                          # Base + async session
│  ├─ models/core.py
│  └─ schemas/core.py
├─ migrations/                     # Alembic（含 c3d4e5f6a7b8 M6 Remotion）
├─ alembic.ini
├─ compose.infra.yml               # Postgres/RabbitMQ/Redis/MinIO
├─ infra/remotion/Dockerfile       # Remotion 沙箱镜像
├─ prompts/
│  ├─ script/                      # system/article/optimize
│  ├─ storyboard/                  # system/generate
│  └─ remotion/                    # system + generate_shot
├─ templates/
│  ├─ stage/                       # stage.html/css/renderer.js
│  └─ cards/                       # 5 类卡片 HTML
├─ specs/
│  ├─ demo_episode.json            # 3 镜头 12 秒 demo（本地素材）
│  └─ demo_placeholder.json        # 3 镜头 6 秒公开 demo（placeholder 素材）
├─ web/                            # React + Vite + Ant Design 控制台
│  ├─ src/pages/                   # 总览 / 视频期 / 详情 / 资产库
│  ├─ src/api.ts                   # API client
│  └─ vite.config.ts               # /api、/health 代理到 8000
├─ tests/
│  ├─ conftest.py
│  ├─ test_timeline.py
│  ├─ test_api.py
│  ├─ test_state_machine.py
│  ├─ test_render_flow.py
│  ├─ test_outbox.py
│  ├─ test_stage_anchor.py
│  ├─ test_render_golden.py
│  ├─ test_script_validation.py
│  ├─ test_script_importer.py
│  ├─ test_script_optimizer.py
│  ├─ test_script_api.py
│  ├─ test_storyboard_rhythm.py
│  ├─ test_storyboard_graph.py
│  ├─ test_storyboard_spec.py
│  ├─ test_storyboard_api.py
│  ├─ test_llm_json.py
│  ├─ test_remotion_agent.py
│  └─ golden/placeholder_still.png
├─ data/assets/                    # 持久化资产，gitignore
├─ pyproject.toml
├─ uv.lock
└─ scripts/
   ├─ check_llm.py
   ├─ prepare_character_asset.py
   ├─ generate_seedream_image.py
   ├─ ingest_assets.py             # 已有图片批量入库
   ├─ make_placeholder_pack.py
   ├─ queue_demo_render.py         # API → outbox → Celery → 成片
   └─ render_demo.py               # 手写镜头 → MP4
```

M1 计划新增的目录见架构方案附录 A：`app/`（api/workflow/agents/domains/providers）、`templates/`、`prompts/`、`assets/`、`character_packs/`、`migrations/`、`tests/`、`web/`。

---

## 4. 环境与约定

### 4.1 模型与接口

| 用途 | 配置 | 状态 |
|---|---|---|
| 文本/代码主模型 | `DEEPSEEK_MODEL=deepseek-flash` | ✅ 可用 |
| 文章导入/润色 | `DEEPSEEK_MODEL=deepseek-flash` + `prompts/script/` | ✅ 真实调用已验证 |
| 文本备选/A-B | `ARK_MODEL_STRONG=doubao-seed-2-1-pro-260915` | ✅ 可用 |
| 图像素材 | `ARK_IMAGE_MODEL=doubao-seedream-5-0-pro-260628` | ✅ 可用（原创角色/背景；洛琪希会被版权过滤） |
| 视觉质检 | `DEEPSEEK_MODEL=deepseek-flash` 多模态 | ✅ 图片直传/视频抽帧 |
| TTS | `TTS_PROVIDER=indextts2` + `data/assets/voice/indextts2/` | ✅ 本地可用（IndexTTS2 zero-shot） |

- DeepSeek Base URL：`https://api.deepseek.com`
- 火山方舟 Base URL：`https://ark.cn-beijing.volces.com/api/v3`
- IndexTTS2：独立 Python 3.11 环境 `data/tools/indextts-venv`（torch 2.8 cu128）；`app/providers/tts.py` 自动拉起 `scripts/runtime/indextts_server.py`（`127.0.0.1:8765`，模型常驻）；8GB 显存用 fp16 + Wav2Vec2-BERT 放 CPU；长文本实测 RTF 1.75。
- 对齐：默认 `ALIGN_LEVEL=sentence`，字幕整句显示，不运行 wav2vec2；字级模式设 `ALIGN_LEVEL=char`，同一 Python 3.11 环境运行 `scripts/runtime/align_words.py`；模型 `data/assets/voice/align/wav2vec2-chinese/`；默认 `ALIGN_DEVICE=cuda`，与常驻 TTS 抢显存时脚本会自动回退 CPU。
- 校验脚本：`python scripts/tools/check_llm.py --live`（DeepSeek 必检，Ark 可选）；`--require-ark` 把 Ark 当必检。
- 图像生成测试产物在 `tmp/seedream_probe.png`（gitignore）。

### 4.2 本地渲染环境（M1）

- 依赖安装（PyPI 直连容易卡，国内镜像更快）：
  `UV_DEFAULT_INDEX=https://pypi.tuna.tsinghua.edu.cn/simple uv sync`
- Playwright 钉在 **1.59.0**，复用本机 `chromium-1217`；升级 Playwright 前先确认对应 Chromium 已安装，否则 `uv run playwright install chromium`。
- ffmpeg 用 `imageio-ffmpeg` 自带二进制（`imageio-ffmpeg==0.6.0`，含 libx264/AAC），本机不需要系统 ffmpeg。
- 测试：`uv run pytest -q`
- 渲染成片：`uv run python scripts/demo/render_demo.py`
- 只出静帧：`uv run python scripts/demo/render_demo.py --stills-only --still-ms 2000 --still-out tmp/render_demo/still_2s.png`
- 当前单进程速度约 **0.53 秒/帧**；10 分钟片约 2.3 小时，后续必须并行 render worker。

### 4.2.1 API / 基础设施（M1.1）

- 本地无 Docker 时默认 SQLite，先迁移再启动：
  `uv run alembic upgrade head`
  `uv run uvicorn app.api.main:app --reload --port 8000`
  打开 `http://localhost:8000/docs`。
- 使用 compose 基础设施：
  `docker compose -f compose.infra.yml up -d`
  然后把 `.env` 的 `DATABASE_URL` 改为 `postgresql+asyncpg://roxy:roxy-dev@localhost:5433/roxy`，再跑迁移。
- 端口避开现有栈：Postgres 5433、RabbitMQ 5673/15673、Redis 6380、MinIO 9100/9101。
- 本机 Docker 已启动并验证三件套；compose 默认只起 Postgres/RabbitMQ/Redis，MinIO 用 `--profile storage` 另行启动。RabbitMQ 4.4 挂载 `infra/rabbitmq.conf`，允许 Celery pidbox 的临时非独占回复队列。

### 4.2.2 队列与 render worker（M1.2）

- 本机原生进程要在 `.env` 用 localhost：`DATABASE_URL=postgresql+asyncpg://roxy:roxy-dev@localhost:5433/roxy`、`RABBITMQ_URL=amqp://roxy:roxy-dev@localhost:5673//`、`REDIS_URL=redis://localhost:6380/0`；只做单机演示也可继续 SQLite。
- 迁移后分别启动：
  `uv run uvicorn app.api.main:app --reload --port 8000`
  `uv run celery -A app.workflow.celery_app worker -Q workflow,agent,render -l info -c 2`
  `uv run celery -A app.workflow.celery_app worker -Q media -l info -c 1`
  `uv run celery -A app.workflow.celery_app beat -l info`
- `-c` 是同时渲染的 Chromium 数量：2 vCPU/2GB 先 `-c 1`，4 核以上再 `-c 2`。
- media worker 常驻 IndexTTS2（GPU），并发必须为 1；Windows 调试同样加 `--pool=solo`。
- Windows 本机 Celery 默认 prefork 不可用：调试加 `--pool=solo`（单并发）；并行渲染在 Ubuntu VM 上用默认 prefork `-c N`。
- 队列：`workflow`（状态推进/outbox 补投）、`agent`（`storyboard.generate` / `qc.episode`）、`media`（`voice.episode` / `align.episode`）、`render`（`render.episode` / `render.shot` / `render.concat`）。
- 触发真实队列渲染：`uv run python scripts/demo/queue_demo_render.py --base-url http://localhost:8000`。
- beat 每 5 秒执行 `workflow.dispatch_outbox`，把 PENDING 事件投到 RabbitMQ；失败按指数退避，5 次后置 FAILED。
- `CELERY_TASK_ALWAYS_EAGER=true` 只用于任务级测试；在 async dispatcher 里同步执行 task 会和事件循环冲突。
- 本机实测（2026-10-28）：`queue_demo_render.py` 3 镜头 6.00 秒成片，outbox DISPATCHED、episode READY、node_run SUCCESS；worker 用 `--pool=solo`。
- MinIO 不是 M1.2 必需；`docker compose -f compose.infra.yml --profile storage up -d` 单独启动（`minio/mc` 镜像拉取失败时先跳过）。

### 4.2.3 文章导入与文稿润色（取代 M2 主题生成）

- 唯一的脚本来源是文章导入：`POST /api/v1/episodes/{id}/actions/import-script`，body 为 `{article, optimize, instructions}`；最多 30000 字（`SCRIPT_ARTICLE_MAX_CHARS`）。
- 导入同步调用 DeepSeek（不投队列），按 series 章节标签生成问题式小标题、章节目标和逐句台词；写 `script_line`，`episode.script_meta` 记录 summary/outline/article_chars/validation。
- 所有导入台词统一写 `speaker=roxy`，由洛琪希单人口播；校验不再限制洛琪希 15 字或台词占比，单句统一 ≤50 字。
- 导入后进入 SCRIPT_REVIEW；校验不通过会保留稿件并标 WARNING，`confirm-script` 仍返回 409。
- 润色：`POST /api/v1/episodes/{id}/actions/optimize-script`（`{apply, instructions}`），保持章节/句数/说话人不变，校验通过才写回，`script_meta.optimization` 记录修改句数。
- 查看脚本：`GET /api/v1/episodes/{id}/script`；编辑单句：`PATCH /api/v1/script-lines/{line_id}`；重新校验：`POST /api/v1/episodes/{id}/script/validate`。
- `POST /api/v1/episodes/{id}/actions/confirm-script` 通过后进 STORYBOARDING。
- Prompt 在 `prompts/script/article.md` 与 `prompts/script/optimize.md`。
- 取消：`POST /api/v1/episodes/{id}/actions/cancel` 把状态转 CANCELLED；media/render/QC 任务在检查点抛 `TaskCancelled` 停止重试。
- 删除：`DELETE /api/v1/episodes/{id}`，运行中状态返回 409，只清 DB 关联行，不动 `output/` 与 MinIO 成片。

### 4.2.4 分镜 Agent（M3）

- 确认脚本后 episode 进入 STORYBOARDING，再调 `POST /api/v1/episodes/{id}/actions/generate-storyboard`；任务投到 `agent` 队列。
- 查看/校验分镜：`GET /api/v1/episodes/{id}/storyboard`、`POST /api/v1/episodes/{id}/storyboard/validate`。
- 编辑单镜头：`PATCH /api/v1/shots/{shot_id}`，支持 card_type / character_image / character_position / duration_ms / bg / transition / motion；修改后会自动重算节奏。
- `POST /api/v1/episodes/{id}/actions/confirm-storyboard` 校验通过后进入 VOICING。
- `POST /api/v1/episodes/{id}/actions/build-render-spec` 把 shot 表转成 `EpisodeSpec` 存回 `episode.render_spec`，之后可直接调 `actions/render` 渲染。
- 节奏规则是纯函数（`app/agents/storyboard/rhythm.py`）；LLM 只负责语义选镜，违规由确定性修复器兜底，最多修 4 轮。
- 分镜生成使用 `prompts/storyboard/`；`shot.cache_key` 由台词文本、卡片类型、payload、角色图和模板版本计算。

### 4.2.5 资产持久化与复用（M3.1）

- 已有图片入库：`uv run python scripts/tools/ingest_assets.py`；会把 `tmp/seedream_assets` 的背景/物件复制到 `data/assets`，角色包在原目录索引，写入 `asset` 表。
- `asset.reuse_key` 是复用的唯一键：背景 `bg:paper:light` / `bg:floor:wood` / `bg:wood:table`，角色 `character:<pack>:<id>`，物件 `prop:<name>`。
- `build-render-spec` 会优先解析 `APPROVED` 的背景/地面资产；找不到才退回 placeholder。
- 生成前先查复用键：`generate_seedream_image.py --reuse-key bg:paper:dark --asset-type background`；命中 APPROVED 时不会调用 Seedream。
- 新生成图默认 `CANDIDATE` 入库，人工筛选后 `POST /api/v1/assets/{id}/approve` 才可复用；拒绝用 `/reject`。
- 查询资产：`GET /api/v1/assets?type=background&status=APPROVED` 或 `?reuse_key=...`。
- 本机 `ASSET_ROOT=./data/assets`；VM 用 `/data/assets`（数据盘），备份时一起备份 `data/assets` 和 `character_packs/`。

### 4.3 Git 与提交

- Remote：`origin` → `https://github.com/Tsuki11111/roxy-pipeline.git`
- 分支：`main`
- 提交信息：Conventional Commits，描述中文；例：
  - `docs: 补充 M1 渲染链路设计`
  - `feat(render): 增加镜头级 ffmpeg 编码`
- **不要提交**：`.env`、`docs/assets/roxy_reference.webp`、`tmp/`、`data/`、私有 `character_packs/*`。

### 4.4 Docker 与端口

- 部署目标：Ubuntu 24.04 VM，Docker 29 / Compose 2.40。
- **环境隔离**：本地 `ROXY_ENV=local`、`COMPOSE_PROJECT_NAME=roxy-local`，容器 `roxy-local-*`、网络 `roxy-local-net`；VM 用 `ROXY_ENV=vm`、`COMPOSE_PROJECT_NAME=roxy-vm`，容器 `roxy-vm-*`、网络 `roxy-vm-net`。数据卷随 compose project 名自动隔离。
- **配置来源**：本地 `.env` 用 `.env.example`；VM 用 `.env.vm.example`（服务名 `postgres/rabbitmq/redis/minio`）。两份模板不要互相复制。
- **后端解耦**：数据库、RabbitMQ、Redis、MinIO、API 地址全部经 `app/core/config.py` 的 `Settings` 读取；业务模块不得出现 `localhost`、VM IP 或容器名。
- Postgres 库 `roxy`；Redis key 前缀 `roxy:`；MinIO bucket `roxy-*`。
- 端口：Nginx 8080/8443；MinIO 9100/9101；本地映射 Postgres 5433、RabbitMQ 5673/15673、Redis 6380，均可在 `.env` 覆盖。
- 现有 VM 已占用 8088/8001/8002/8003/9000/9002，避开。
- 根分区约 18GB 不够；数据盘挂 `/data`，`PGDATA`、`MINIO_DATA`、备份都指过去。
- MinIO 预签名 URL 要区分 `MINIO_INTERNAL_ENDPOINT`（容器内 `http://minio:9000`）与 `MINIO_PUBLIC_ENDPOINT`（浏览器可访问的外部地址）。

### 4.5 渲染约定

- 输出规格：1920×1080、25fps、H.264/AAC 48kHz。
- 所有动画由 `renderAt(tMs)` 计算，禁用 CSS animation / `Date.now()` / `Math.random()`；随机用固定 seed。
- 角色切换按镜头自己的 `start_ms` 初始化；`character_from` 提供上一镜角色，新角色从最近侧屏幕外 280ms 冲入，旧角色 80ms 模糊让位；换镜时卡片与字幕直接切换，不做透明淡入。
- 镜头片段编码参数必须完全一致，最终 `-c copy` 拼接。
- 含文字卡片用 HTML；Seedream 只做背景/舞台/演示物件（无文字空壳）。
- 背景/演示物件生成后固定资产化，不每期重生成。
- Remotion 为唯一生产渲染器；Playwright 仅测试/历史。Remotion 输出经 ffmpeg 统一为 1920×1080/25fps/H.264/yuv420p/CRF18，保证 `-c copy` 拼接。
- Remotion 代码只存在于 `tmp/remotion/<episode_id>/`；`remotion_shot` 表记录 code_hash/status/input_hash。
- 生成代码约束：单镜头 ≤7000 字符；浅底必须深字，白字必须有深色实底；有 `character` 必须出现 Roxy；不能用随机/时间/CSS 动画。
- 布局约束：Remotion 不做关键词标签；画面文字用 `PaperCard` Claude 暖纸卡（variant：note/quote/index/letter/sticky/specimen；tone：cream/sand/peach/sage；transition：slide/zoom/flip/drop/reveal/push）。Python 按镜头序号排期：约 1/3 镜头 `card_style=null` 做纯演示，其余给卡并指定样式/动效；切换位移 ≥300px、缩放变化 ≥0.3、旋转 ≥5° 或 rotateY ≥45°。
- 角色动效：有 `character` 的镜头必须有入场（offsetX ±400–600、opacity 0→1、scale 0.94→1、rotate ±2°）、呼吸轻摆和至少一次手势/让位；生成检查会拒绝只有 `src/side/height` 的静态 `<Character>`。
- 背景与字幕：`Stage` 统一渲染 Claude 暖纸背景（纸纹 + 底部浅阴影 + 手绘星），不再使用旧纸纹/木地板资产；`SubtitleTrack` 改为暖纸底 + 墨字 + 陶土短线。
- 改动 `app/agents/remotion/templates/` 后必须重建镜像 `roxy-remotion:4.0.539`，否则沙箱仍用旧组件。
- Remotion 字幕由 Root 里的 `SubtitleTrack` 统一叠加（bottom 40，样式同旧 Playwright）；生成代码不画字幕，y 940–1080 的底部区留给字幕。
- 画面长段文本由生成代码的 `PaperCard` 组件渲染（Claude 暖纸/墨字/陶土），Python 只负责底部字幕 `SubtitleTrack`。文本长度和分段由模型决定，优先直接用 `narration`/`card.text` 的长段。
- Docker 不可用或镜像缺失时 Remotion 生成失败，期次标记失败；`REMOTION_ONLY=true` 下不回退 Playwright。

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
- ChatGPT 在线生图可用于本地洛琪希候选（用户自用、非商业）；产物只放 `character_packs/roxy/`（gitignored），不要提交公开仓库。处理脚本：`scripts/tools/prepare_character_asset.py`。
- 豆包生成图右下角有“豆包 AI 生成”水印；不要直接入成片。脚本可用 `--keep-largest-component` 排除孤立水印；使用前先确认豆包条款是否允许去除/隐藏水印。
- 原创角色/背景 AI 生成后必须人工筛选、去背景、统一尺寸、入库；不要每期重生成。
- AI 生成的洛琪希衍生图仍受 C-01～C-06 约束；生成服务条款也要看。
- 字体/BGM 只用 OFL 或已授权素材。

### 5.5 环境

- 本机 Python 可用；Docker Desktop/WSL2 尚未验证。
- **IndexTTS2 常驻内存**：本机实测常驻服务私有内存约 17GB，系统提交上限只剩 3–4GB；字级模式下再启动对齐子进程加载 1.2GB wav2vec2 会报 `DefaultCPUAllocator: not enough memory`。`align.episode` 会先 POST IndexTTS2 `/shutdown`（`ALIGN_STOP_TTS=true`）释放内存，再跑对齐；配音结束也会主动停服务（`TTS_UNLOAD_AFTER_VOICE=true`），下次配音自动重启。默认句级模式不加载对齐模型，但保留这些回收逻辑。16GB 本机不要关闭该行为。
- VM 根分区 18GB 不能放 MinIO 数据；先挂数据盘。
- 2 期并行需要约 8–16 vCPU / 32GB；资源不足先单期串行。

### 5.6 M1 渲染环境

- PyPI 直连会卡住：`uv sync` 用 `UV_DEFAULT_INDEX=https://pypi.tuna.tsinghua.edu.cn/simple`。
- Playwright 1.64 需要新 Chromium（1248），本机只有 1217；把 `playwright` 钉在 `==1.59.0`，避免重下浏览器。
- 本机没有系统 ffmpeg；用 `imageio-ffmpeg` 自带二进制，已确认有 libx264/AAC。
- 单进程渲染约 0.53 秒/帧：300 帧 12 秒片约 160 秒；10 分钟片约 2.3 小时，必须并行化。
- **不要假设逐镜头渲染从 t=0 开始**：必须用镜头 `start_ms` 初始化，否则会拿第 1 镜角色做过渡，出现空白帧、拉伸和错误平移。
- `specs/demo_episode.json` 引用本地 `character_packs/roxy/` 和 `tmp/seedream_assets/`；这些不进公开仓库，公开复现需要 placeholder pack。
- Windows 控制台输出中文可能乱码，不影响文件；需要时设 `PYTHONUTF8=1`。
- 本机 Docker Desktop 未启动：`compose.infra.yml` 只做了 `docker compose config` 校验，实际容器启动要在 VM 上验证。

### 5.7 Remotion 沙箱与生成

- Composition ID 不能含下划线，用 `Shot-0001`；组件导出名仍是 `Shot_0001`。
- `--read-only` 下 Remotion/Chromium 会写 `/app/node_modules/.cache`，必须挂 tmpfs，否则 `EROFS`。
- Windows Git Bash 下 Docker `--mount` 路径要做 `MSYS_NO_PATHCONV=1`，否则盘符被改写。
- DeepSeek 单镜头代码很长：`max_tokens=6000/8192` 都会截断长镜头（表现为空 content 或半截 JSON）；现用 16384，并检测 `finish_reason=length`。
- 生成代码不能用 `staticFile()` 二次包裹 `Stage` 的 `bg/floor`；模板用 `assetSrc()` 兼容“资产名或已解析 URL”。
- `Card` 同时接受流水线类型（`chat_bubble`/`pure_text`）和原型别名（`chat`/`pure`）；chat 气泡渲染 `body` 以支持 `lines`。
- 部分镜头生成成功时 `remotion_meta.enabled` 必须保持 `false`，否则 Root 缺 Composition 会渲染失败。
- 模型默认会写浅色字：必须在 Skill 里明确“浅底深字 / 白字必须有深色实底”，否则会出现 QC 报的文字不可读。
- 旧 `Card` 是绝对定位、`zIndex=4` 的 820px 白块，模型把图表画到同一区域会被整块盖住。现已禁止 Remotion 使用 `TerminalCard`/`Card`/`Label`/`Caption`/`Board`，画面文字统一改用 `PaperCard`；Skill/Prompt 都写明“任何动画元素不得与文字卡重叠”。

---

## 6. 历史记录

### 2026-10-31 · Remotion-only

- 用户要求新期只用 Remotion；新增 `REMOTION_ONLY=true`（默认），Playwright 仅保留测试/历史，不参与新期渲染。
- `start_render` / `rerender_episode` 在 renderer 不是 remotion 时直接拒绝；`render_shot_task` 渲染失败不再切 Playwright。
- 自动 codegen 失败或未全部 READY 时期次标记 FAILED，不再静默回退旧样式。
- `Character` 支持 `side="center"`，避免模型生成 `center` 时编译失败；生成服务仍会校验角色动效。
- 后端 90 条测试通过，前端构建通过。

### 2026-10-31 · 新期默认自动 Remotion + 单句 50 字

- 问题：新导入的期默认走 Playwright（`render_spec.py` 的 renderer 初始值是 playwright），而 `remotion.generate` 只有手动 API 会触发；voice/align 完成后直接 `start_render`，所以 PaperCard/暖纸背景/角色动效对新期全部不生效。
- 修复：新增 `start_auto_render`，voice/align 的 `voice_auto_render` 分支改为先排队 `remotion.generate`（`auto_render=true`），codegen 任务成功后自动 `start_render`；失败或未全部 READY 时不回退 Playwright。新增 `REMOTION_AUTO_CODEGEN=true`。
- codegen 完成后会重建并写回 `episode.render_spec`，确保自动渲染使用 Remotion spec。
- 脚本单句上限从 25 字改为 50 字（校验、Prompt、文档、测试同步）。
- 实测：新建 11 镜头测试期，`start_auto_render` 后状态 RENDERING、`remotion.codegen` 排队并自动生成/渲染，不再需要手动点按钮。
- 后端 89 条测试通过。

### 2026-10-31 · 恢复角色动效

- 问题：Claude 纸卡重生成后，多数有角色的镜头只剩 `<Character src side height />`，人物完全静止。
- `Character` 增加 `scale`/`rotate` props（transform-origin 底部中心）。
- Skill/Prompt 增加角色硬规则：入场 offsetX ±400–600、opacity 0→1、scale 0.94→1、rotate ±2°，停留呼吸轻摆，卡片/关键图形出现时做手势/让位。
- 生成服务新增检查：有 `character` 却没画 Character、或 Character 只有静态数值属性时，带反馈重试。
- 实测：7 个有角色镜头全部有 ±520px 冲入 + `Math.sin` 呼吸 + gesture/lean；QC `PASS`，后端 88 条测试通过。

### 2026-10-31 · Claude 纸卡与暖纸舞台

- 用户确认 Claude 暖纸风格，要求除动画外全部替换：卡片、背景、字幕都改成暖纸/墨字/陶土，删掉终端风。
- 新增 `PaperCard`：6 种 variant（note/quote/index/letter/sticky/specimen）× 4 种 tone（cream/sand/peach/sage）；暖纸、墨字、宋体、陶土/鼠尾草少量强调、手绘星/下划线。
- `Stage` 改为 Claude 暖纸背景（纸纹 + 底部浅阴影 + 手绘星），不再使用纸纹/木地板资产；`SubtitleTrack` 改为暖纸底 + 墨字 + 陶土短线。
- 删除 `TerminalCard`/`Card`/`Label`/`Caption`/`Board` 模板；生成服务检测到旧组件或 `card_style` 不符会带反馈重试。
- Python 卡片排期保持不变：`CARD_PATTERN=[True,True,False,True,False]` 约 1/3 镜头纯演示；variant/tone/transition 轮换。
- 实测：7 个纸卡镜头 + 4 个纯演示，覆盖 6 种 variant、4 种 tone；QC `PASS`，后端 87 条测试通过。

### 2026-10-30 · 二次元终端卡与多样切换

- 用户要求：不是每个动画都要卡片；卡片风格和切换动画要多样；改成二次元终端/代码块画风。
- 新增 `TerminalCard`：6 种 variant（terminal/editor/hud/console/snippet/chat）× 4 种 tone（navy/purple/mint/rose），支持 `translateX/Y`、`scale`、`rotate`、`rotateY`、`reveal`、`cursor`。
- Python 按镜头序号排期 `card_style`：`CARD_PATTERN=[True,True,False,True,False]` 约 1/3 镜头 `null` 做纯演示；其余轮换 variant/tone/transition。生成服务校验 `card_style=null` 时不得用 TerminalCard，指定 variant/tone 不符则带反馈重试。
- 切换配方 6 种：slide/zoom/flip/drop/reveal/push；Skill 要求位移 ≥300px、缩放变化 ≥0.3、旋转 ≥5° 或 rotateY ≥45°。
- 禁用 `Card`/`Label`/`Caption`/`Board`；文本仍为长段，优先 `narration`/`card.text`，不得扩写原文。
- 实测：11 镜头中 4 个纯演示、7 个卡片；覆盖 6 种 variant、4 种 tone；QC `PASS`，后端 87 条测试通过。

### 2026-10-30 · 长段板书卡与分段动效

- 用户要求去掉关键词标签，改为长段文本卡的切换动画 + 演示组合；板书卡要二次元软萌风格，卡片切换动效幅度要大。
- 新增 `Board` 组件：木框黑板、粉笔字、贴纸/涂鸦、柔和 accent；支持 `text/lines/title`、位置/尺寸、`translateX/Y`、`scale`、`rotate`、`opacity`。
- Skill/Prompt 改为：每镜头至少「Board 长段文本 + 演示段」两个 `<Sequence>` 场景；文本优先用 `narration`/`card.text` 的长段；切换位移 ≥240px、缩放 0.72–0.82→1、旋转 ±4°–8°、spring 允许过冲；卡内文字逐行 stagger。
- 生成服务禁用 `Card`/`Label`/`Caption`，检测到即带反馈重试；移除“禁止整句”检查（长段文本现在是主形态）。
- 实测：11 镜头全部 Board + Sequence，单镜 2 段、文本 20–40 字；QC `PASS`，84 条测试通过。

### 2026-10-30 · 标签位置/框型与内容风格

- 新增 `Label` 组件：任意 `left/top` 定位，`variant` 支持 `pill`/`tag`/`callout`/`note`/`badge`/`stamp`，可 `rotate`。
- Skill/Prompt 改为：关键词跟着对象走（箭头端点、节点旁、图内空白、角色手势附近），位置和框型随构图轮换；关键词不再用 `Caption`，生成服务检测到 `Caption` 会带反馈重试。
- 风格约束：Remotion Skill/Prompt 与 Asset Agent 都要求先判断主题再选色调、材质、线条、图形语言；同一期统一，禁止与内容无关的赛博霓虹/故障/机器人装饰。
- 实测：11 镜头使用 Label，单镜 3–4 个标签、多种位置与框型；QC `PASS`，后端 84 条测试通过。

### 2026-10-30 · 修复 Remotion 卡片遮挡动画

- 问题：旧 `Card` 是固定 820px 宽、绝对定位、`zIndex=4` 的白块；生成代码把光谱/问号/图表画在卡片同一区域时被整块盖住（第 3 镜光谱、第 1 镜问号）。
- 修复：Remotion 镜头**禁用旧 `Card`**；新增 `Caption` 底部小条；`Card` 增加 `top`/`width` props（仅兼容旧代码）；Skill/Prompt 写明“任何动画元素不得与文字面板重叠”。
- 生成服务增加确定性检查：代码出现 `import Card`/`<Card` 或 `Caption` 时带错误反馈重试一次；代码里出现 ≥10 字的整句 `narration` 时同样重试，强制画面只放关键词标签。
- 标签布局：新增 `Label` 组件（6 种框型 + 任意 `left/top` + `rotate`）；Skill 要求标签跟着对象走、位置和框型轮换，不要默认右下角；`Caption` 只保留给旧代码/极少数底部注释。
- 风格约束：Skill/Prompt/Asset Agent 都要求先判断主题再选色调、材质、线条和图形语言；同一期保持统一，禁止与内容无关的赛博霓虹/故障/机器人装饰。
- 字幕：此前 Remotion 成片只有卡片/面板文字，没有底部字幕；现由 Python 生成 `Root.tsx` 时给每个 Composition 包一层 `SubtitleTrack`，用 `build_timeline` 的句级 chunks（转为镜头内相对时间）渲染，样式沿用旧 Playwright 字幕条。`renderer_version` 升到 `m6.1-subtitles` 以失效旧缓存。
- 画面文字：完整句子只交给字幕；生成代码只放关键词/短标签（实测 11 镜头标签均为 1–4 字，如 `蓝光`、`波长短`、`大气层`、`混合光`）。
- 渲染链路修复：重渲染后 QC 已跑过会抛 `QcConflict`，之前被当成失败并把 health 置 FAILED；现在按幂等成功处理，保留 `health=OK`。
- 实测：11 镜头全部无 `Card`，画面文字均为 1–4 字关键词标签（如 `蓝光`、`波长短`、`大气层`、`混合光`），完整句子只在底部字幕；重新渲染后 QC `PASS`（health=OK）；后端 83 条测试通过。

### 2026-10-30 · M6 Remotion 代码生成 Agent（默认渲染器）

- 用户决定：Remotion 取代 Playwright 成为默认渲染器；每镜头一个 Composition；LLM 生成自由 TSX；运行时 Skill 放 `app/agents/remotion/skills/`；Docker 沙箱；每镜头单独生成。记录为 ADR-011。
- 新增 `app/agents/remotion/`（models/service/tasks/docker/prompts/templates/skill）、`prompts/remotion/`、`infra/remotion/Dockerfile`、`app/render/remotion.py`、迁移 `c3d4e5f6a7b8`（`episode.remotion_meta` + `remotion_shot`）。
- 生成流程：素材复制为 `public/assets/<checksum>` → 每镜头一次 DeepSeek（并发 3）→ 写 `src/shots/shot_XXXX.tsx` → Python 生成 Root → Docker `tsc + remotion compositions` 校验 → 失败带错误重试一次 → 全 READY 才启用。
- 渲染流程：`build_episode_render_spec` 读 meta → `renderer=remotion`；`render_shot_task` 调 Docker 渲染，失败即镜头失败（不回退 Playwright）；ffmpeg 归一化后继续 `-c copy` 拼接。
- API/前端：`POST /actions/generate-remotion`、`GET /episodes/{id}/remotion`、`GET /episodes/{id}/remotion/shots/{shot_id}`；编辑器新增「Remotion 渲染」卡片（生成、状态、代码预览、单镜头重生成、重渲染）。
- 实测：`roxy-remotion:4.0.539` 镜像构建成功；11 镜头整期真实生成/渲染/QC 通过（health OK）；单镜头 Docker 渲染约 18–21 秒；后端 81 条测试通过，前端构建通过。
- 生成期间遇到的问题与修复：max_tokens 截断（6000→8192→16384 + `finish_reason=length` 检测）、Composition ID 下划线、`EROFS` cache、`staticFile` 二次包裹、`Card` kind 别名、partial meta 误启用、浅底浅字。
- 注意：旧的原型评估结论（“暂不整体替换”）已被本条取代。

### 2026-10-30 · Remotion 渲染原型评估

- 在 `tmp/remotion_prototype/` 建了 3 个 1080p25 的“什么是 AI Agent”视觉原型：`ShotRush`（屏幕外冲入/让位 + 任务循环图 + 终端执行）、`ShotSpring`（spring 半身角色切换 + 工具 chips + 机器人）、`ShotCards`（目标终端 → 循环图 → 浏览器结果）；不再使用纯文字卡。复用本地 AI 主题立绘，未接主链路、未提交。
- 同机 5 秒/125 帧对比：Remotion 约 23 秒（含 bundle/启动），现有 Playwright 渲染器约 17 秒（简单镜头）；Remotion 没有速度收益，瓶颈仍是 Chromium 逐帧 + 编码。
- 观感：spring 缓动和组件化卡片更自然，但需要 Node 第二运行时、重写现有舞台/卡片/缓存，并处理 Remotion 许可与版本固定。
- 结论（已被 2026-10-30 M6 决策取代）：当时暂不整体替换；保持 Playwright + ffmpeg。用户后来要求按主题生成 Remotion 代码并替换默认渲染器，见上方 M6 记录。

### 2026-10-30 · 分镜时间线编辑器

- 前端详情页新增「剪辑」tab：成片播放器 + 按镜头时长排布的时间线 + 视觉属性面板。
- 可编辑卡片类型/文案、角色立绘与位置、背景、动作、入场方向；点击镜头会 seek 到对应成片时间点。镜头时长仍由配音决定，只读。
- 后端新增 `GET /episodes/{id}/video`（仅允许输出目录内文件，支持 Range）、`POST /actions/rerender`（READY/PUBLISHED/QC 重建 render_spec 并投递渲染）。
- `PATCH /shots/{id}` 增加 `card_text` 与 `overlay_*`；`shot.bg` 现在会进入逐镜头 render spec，背景键通过资产注册表解析。
- 新增独立贴图层：`OverlaySpec` + `#overlay`，支持上传/Seedream 图片、位置/宽度/底部/不透明度/`normal|multiply` 混合；`multiply` 用于白底素材融合。
- 新增 `POST /assets/upload`（base64 图片入库）、`POST /assets/image-prompt`（DeepSeek 写 Seedream 提示词）、`POST /assets/seedream`（生成候选并入库）、`GET /assets/file`（安全预览）。
- 编辑器预览基于上一次成片；保存并重渲染后自动刷新。实测 11 镜头从 RENDERING → QC → READY，视频版本自动更新。
- 前端 `npm run build` 通过，后端 78 条测试通过；真实 Seedream 生成 1 张候选成功（MinIO 离线时只记 warning）。

### 2026-10-30 · 角色改为屏幕外冲入

- 角色切换不再用遮罩擦除：新角色从最近侧屏幕外以 280ms ease-out-quad 滑入，入场距离约 0.65 屏，带最多 1.2px 速度模糊；旧角色 80ms 模糊让位。
- 镜头没有角色时，旧角色沿最近侧滑出屏幕；角色同图连续镜头仍直接保持。
- 逐镜头渲染按镜头 `start_ms` 初始化，卡片/字幕直接切换；`renderer_version=m5.5-rush-in`。
- 4 镜头和 11 镜头预览已验证；正式成片需重新渲染。

### 2026-10-30 · 分镜切换平滑度调整

- 逐帧检查成片确认 25fps 稳定、无重复帧；卡顿感来自换镜时角色整体变透明、卡片从 0 透明度淡入、字幕 70ms 淡入叠加造成的“闪一下/发虚”。
- 换镜时卡片内容直接切换并保持 opacity=1，字幕直接显示/隐藏，不再做每镜入场淡入或位移缩放。
- 角色退场从整体透明度淡出改为方向遮罩擦除；角色切换时长从 180ms 提到 220ms，柔边从 12% 提到 16%，减少阶跃感。
- `renderer_version` 升到 `m5.4-smooth-cut`，旧镜头缓存失效。

### 2026-10-30 · 默认改为句级对齐

- 新增 `ALIGN_LEVEL=sentence|char`，默认 `sentence`：配音本身产出每句起止时间，字幕整句显示，跳过 wav2vec2 字级对齐，省掉 1.2GB 模型加载与对齐耗时。
- `EpisodeSpec` 新增 `alignment_level`（旧 spec 默认 `char` 兼容）；`build_timeline` 在句级模式下每个镜头只生成一个整句字幕块，超过 34 字才回退按标点分块。
- `voice.episode` 仅在 `align_level=char` 且 `voice_auto_align=true` 时排队 `align.episode`；句级模式下直接进入渲染。
- 字级对齐仍保留：手动 `/actions/align` 或把 `ALIGN_LEVEL` 设为 `char` 即可恢复；`align.episode` 会把 `alignment_level` 切回 `char`。
- 测试 71 条通过；新增句级字幕块测试。

### 2026-10-30 · 角色加载与切换动画修复

- 问题：逐镜头渲染时 `initStage` 固定 `renderAt(0)`，每个镜头开头都会从第 1 镜头的角色做起始过渡；旧层复用了新角色的 `height/anchor`，导致空白帧、拉伸和异常平移；新图未 `decode()`，首帧偶尔缺图。
- 修复：`initStage(data, atMs, preloadAll)` 按镜头起点初始化；`build_stage_payload` 为每镜写 `character_from`（上一镜角色，含同角色连续镜头）；角色切换改为 220ms 双向遮罩擦除，旧/新层各自使用自己的锚点与高度，只保留最多 18px 轻微位移；首镜角色直接显示。换镜时卡片和字幕直接切换，角色退场也走遮罩擦除，不再整体变透明。
- 性能：逐镜头只预加载本镜头背景/地板/前后角色图，`decode()` 并等待两帧 rAF 后才置 `stageReady`。
- `renderer_version` 升到 `m5.3-char-transition`，旧镜头缓存自动失效。

### 2026-10-29 · 阶段级内存自动回收

- 新增 `app/workflow/memory.py` 的 `release_memory()`：`gc.collect()`，若进程已加载 torch 再 `empty_cache()` / `ipc_collect()`；不主动 import torch，避免把模型依赖带进 worker。
- 配音任务结束（成功、失败、取消）统一停掉 IndexTTS2（`TTS_UNLOAD_AFTER_VOICE=true`）并回收内存；下次配音由 provider 自动重启。
- `render.shot` 每镜头结束、`render.concat`、`align.episode`、`qc.episode` 结束都调用 `release_memory()`。
- IndexTTS2 每合成一句后执行 `gc.collect()` + `torch.cuda.empty_cache()`，降低长文稿的显存碎片。
- 当前正在渲染的 115 镜头任务仍由旧 worker 执行；新逻辑在下次重启 worker 后生效。

### 2026-10-29 · 对齐前释放 IndexTTS2 内存

- 115 句的期在 `align.episode` 失败：`DefaultCPUAllocator: not enough memory`，加载 wav2vec2 时连 8MB 都分配失败。
- 原因：IndexTTS2 常驻服务私有内存约 17GB，系统提交上限只剩 3.7GB；对齐子进程再加载 1.2GB 模型即撞上限。
- 修复：`scripts/runtime/indextts_server.py` 新增 `POST /shutdown`；`app/providers/tts.py` 新增 `request_tts_shutdown()`；`align.episode` 在启动对齐前调用它，等待健康检查失败后再拉起对齐子进程。
- 新增 `ALIGN_STOP_TTS=true`；TTS 服务在下次配音时由 provider 自动重启。释放后系统提交空闲从 3.7GB 回到 20.9GB。

### 2026-10-29 · 脚本改为洛琪希单人口播

- 文章导入与润色提示词不再区分旁白/洛琪希，所有台词统一由洛琪希第一人称讲解。
- 导入时强制 `speaker=roxy`；校验移除洛琪希 15 字上限与 10%–30% 占比，单句统一 ≤50 字。
- 保留 `narrator` 枚举兼容旧数据；Web 脚本表与音频表移除“说话人”列。

### 2026-10-29 · 取消/删除 + 移除按主题生成

- 取消：`POST /episodes/{id}/actions/cancel` 转 CANCELLED；`app/workflow/cancel.py` 提供 `TaskCancelled` 与 `ensure_not_cancelled()`，voice/align/qc/render 任务在关键步骤检查；取消后任务不重试。
- 删除：新增 `DELETE /api/v1/episodes/{id}`；运行中状态（SCRIPTING/STORYBOARDING/VOICING/ALIGNING/RENDERING/QC）返回 409，其他状态清理 Review/LineAudio/OutboxEvent/NodeRun/Shot/ScriptLine 后删除期；不动 `output/` 与 MinIO 成片。
- 前端视频期列表与详情页增加取消/删除；运行中显示节点进度、阶段百分比和耗时，3 秒轮询并自动刷新。
- 移除按主题生成脚本：删除 `app/agents/script/graph.py`、`service.py`、`tasks.py`、`tests/test_script_graph.py` 与 outline/sections/lines/repair prompts；移除 confirm-topic、retry-script、regenerate-script 路由和 `script.generate` Celery 路由。
- 脚本唯一来源改为文章导入 + 可选润色；CLAUDE/README/架构文档同步。
- 后端 67 条测试通过；前端 `npm run build` 通过。

### 2026-10-29 · 文章导入与文稿润色 Agent

- 新增 `POST /episodes/{id}/actions/import-script`：导入最多 30000 字长文，DeepSeek 先理解文章，再按 series 章节标签生成问题式小标题、章节目标和逐句口播；可自动调用润色 Agent。
- 导入后进入 `SCRIPT_REVIEW`；校验不通过会标记 WARNING，`confirm-script` 仍会拦截，避免直接进入分镜。
- `script_meta` 记录 summary、outline、article_chars、validation 和可选润色结果；对话/长文超时或解析失败会回退原状态。
- 新增 `app/agents/script/importer.py` 与 `prompts/script/article.md`；前端视频期页增加「导入文稿」弹窗，支持粘贴和 `.txt`/`.md` 上传。
- 新增 `app/agents/script/optimizer.py`：在 SCRIPT_REVIEW 阶段读取现有台词，调用 DeepSeek 做口语化润色；保持章节、句数、说话人不变，鼓励生活例子、具体动作和洛琪希语气变化。
- 新增 `POST /episodes/{id}/actions/optimize-script`，支持 `apply` 和补充 `instructions`；润色结果必须通过原有脚本校验才会写回，`script_meta.optimization` 记录修改句数和模型。
- 前端脚本页增加“润色文稿”按钮；真实全流程稿副本实测修改 13 句、校验通过。
- 当时 `optimize.md` 不参与 `script.generate` 的 prompt_hash；`script.generate` 已于同日移除，缓存键逻辑不再适用。

### 2026-10-29 · Web 控制台

- 新增 `web/`：React 18 + Vite + TypeScript + Ant Design，Vite 代理 `/api` 与 `/health` 到本地 8000。
- 页面：总览统计、视频期列表/创建、期详情（概览、脚本、分镜、配音对齐、QC、发布包）、资产库（按文稿/文本生成、审批、检查）。
- 期详情可直接触发确认选题、脚本/分镜确认、配音、对齐、QC、渲染、发布包和发布；脚本/镜头支持编辑。
- 用本地 API + 全流程演示库实际打开并截图验证；`npm run build` 通过。
- 当前未接 SSE/登录权限；API 地址通过 Vite 代理或 `VITE_API_BASE` 配置。

### 2026-10-29 · 全流程真实验收

- 用独立 SQLite 库跑通完整链路：DeepSeek 脚本 Agent → 分镜 Agent → IndexTTS2 逐句配音 → 中文 wav2vec2 字级对齐 → 18 镜头渲染 → QC → 发布包。
- 真实结果：18 句 / 18 镜头，成片 50.68 秒、1920×1080/25fps、48kHz AAC；QC PASS，发布状态 PUBLISHED。
- 输出：`output/20261029-192127_916fd598/episode.mp4`，MinIO `s3://roxy-output/episodes/20261029-192127_916fd598/episode.mp4`；发布包在 `tmp/full_run_packages/916fd598-b985-4b9e-983a-2d054b127abf/`。
- 首轮 QC 发现卡片固定右上、角色站右侧时压住脸部/文字；已改为卡片自动放到角色对侧并翻转聊天气泡尾巴，重渲染后 QC 0 error / 0 warning。
- 渲染缓存新增 `renderer_version` 参与 shot hash，模板/布局变化不会误复用旧片段。

### 2026-10-29 · 视觉补全与最终输出/MinIO

- 半身反应镜头：`load_character_assets` 不再排除 `pose=bust`；分镜提示词允许在强调/吐槽句选 bust；`spec_builder` 通过 `_bust_` 识别，设 `anchor_y=0`、高度 1000px。
- 角色滑入：`CharacterSpec.move` 增加 `slide_in_left/right`、`shift_left/right`；Storyboard 在每章第一个有角色的镜头交替分配滑入；`renderer.js` 按 240ms ease-out 计算位移，`move` 参与镜头缓存 hash。
- 已生成半身静帧验证：0.05s 与 0.4s 角色位置不同，半身图完整落在舞台内。
- 最终输出：`app/storage/output.py` 把成片复制到 `output/YYYYMMDD-HHMMSS_<id8>/episode.mp4` 并写 `metadata.json`；`episode.output_path`/`output_meta` 记录本地路径和 MinIO URI。
- 图片资产：`ingest_asset` 入库时同步镜像到 `roxy-assets/assets/<type>/<checksum>.<ext>`，对象信息写 `asset.meta["minio"]`；已有 APPROVED 资产在下次 ingest 时补传。已用 `scripts/tools/ingest_assets.py` 补传 66 个资产。
- MinIO：新增 `minio` 依赖；默认上传到 `roxy-output/episodes/<目录名>/episode.mp4`；本地 MinIO 不在线只记 warning，VM `MINIO_REQUIRED=true` 失败即渲染失败。本机用 `[::1]:9100` 实测上传成功。
- 测试：62 条通过，含输出目录与 MinIO 元数据测试。

### 2026-10-29 · Asset Agent（文本生成演示素材）

- 新增 `app/agents/asset/`：DeepSeek 把文本规划成 background/prop/icon/cover 无文字素材请求；禁止角色立绘、动漫人物、文字/水印卡片。
- 复用策略：把已有 APPROVED/CANDIDATE 资产的 name/type/reuse_key/prompt 作为上下文，模型优先返回已有 reuse_key；命中后不调用 Seedream，直接复用。
- 生成：`app/providers/imagegen.py` 封装 Seedream；新图默认 CANDIDATE，写入 `data/assets`；可选 DeepSeek 图片检查，`auto_approve=true` 且检查通过才直接 APPROVED。
- API：`POST /api/v1/assets/generate`，支持 `text/asset_type/count/auto_approve/check/force`；`IMAGE_PROVIDER=mock` 可离线跑通流程。
- 实测：真实 DeepSeek 规划出 `prop:prism-white-light-dispersion`，mock 图片入库；第二次同文本命中现有候选，不重复生成。
- 按文稿入口：`POST /episodes/{id}/actions/generate-assets` 读取该期 `script_line` 的标题/主题/章节/台词作为 Agent 输入，生成资产 meta 记录 `episode_id`；不再脱离文稿自由生成。
- 暂不引入 RAG：当前资产量小，先用“现有资产上下文 + reuse_key 精确命中”；资产规模或复用命中率需要时再加轻量检索。
- 测试：新增 3 条资产 Agent 测试，全套 60 条通过。

### 2026-10-29 · 目录规范化

- 所有智能体统一收进 `app/agents/`：`agents/script/`、`agents/storyboard/`（LangGraph）与 `agents/asset/`（工具型）；包内文件改为 `graph.py` / `validation.py` / `service.py` / `utils.py`。
- `app/media` → `app/voice`，统一放 TTS、字级对齐和音轨装配。
- 渲染服务和任务从 `app/workflow` 移到 `app/render/service.py` / `tasks.py`；workflow 只保留 Celery、outbox、状态机、resume/revision。
- `api/script_utils.py` / `api/storyboard_utils.py` 下沉为 `script/utils.py` / `storyboard/utils.py`；`storyboard/spec_service.py` 改名 `render_spec.py`。
- `scripts/` 拆为 `runtime/`（IndexTTS2、对齐）、`tools/`（资产/LLM 工具）、`demo/`（演示渲染与队列脚本）。
- 同步更新所有导入、Celery 任务注册、配置默认路径和文档；57 条测试通过，Celery 任务全部注册。

### 2026-10-29 · M5.1 局部修改、续跑与发布包

- 单句修订：`POST /episodes/{id}/actions/revise-line` 接收 `line_id/text`，仅允许 READY/QC 状态；更新行版本后回到 VOICING，自动重跑配音（不变句命中 `line_audio` 缓存）、对齐和渲染。
- 镜头缓存：每镜头写 `shots/shot_XXXX.json`（含 shot/render hash）；`render_shot_task` 命中相同 hash 直接复用 MP4，只有变化镜头重新渲染，拼接仍用全量片段 `-c copy`。
- 通用续跑：`POST /episodes/{id}/actions/resume` 按 VOICING/ALIGNING/QC/RENDERING 分派对应 start 服务；QC 的 SUCCESS+FAILED 也允许 retry。
- 运维：新增 `workflow.reconcile_nodes` beat 任务，扫描 heartbeat 超时（默认 1800s）的 RUNNING 节点并标记 FAILED，供 resume/retry 接管。
- 发布包：`POST /actions/package` 生成 `tmp/packages/{episode_id}/`，包含 `episode.mp4`、`cover.jpg`、`subtitles.srt`、`script.txt`、`metadata.json`、可选 `audio.wav` 和 `package.json`；`POST /actions/publish` 先建包再转 PUBLISHED；`GET /package` 返回清单。
- 最终视频输出：渲染完成复制到 `output/YYYYMMDD-HHMMSS_<id8>/episode.mp4` + `metadata.json`；默认尝试上传 MinIO `episodes/<目录名>/episode.mp4`，本地失败只记 warning，VM `MINIO_REQUIRED=true` 时失败即渲染失败。
- 元数据包含非商业声明和版权提示；发布包只落本地，不自动上传平台。
- 测试 57 条全部通过，覆盖修订、续跑、reconciler 和发布包。

### 2026-10-29 · M4.3 质检与 DeepSeek 多模态

- 新增 `review` 表与 `episode.qc_meta`（迁移 `a1b2c3d4e5f6`）；`review.level` = PASS/WARNING/ERROR/MANUAL。
- 新增 `app/qc/`：`rules.py` 做流参数、时长、响度、对齐、字幕长度、角色资产检查；`frames.py` 按镜头抽首帧+中间帧；`vision.py` 统一调用 `deepseek-flash` 多模态；`tasks.py` 的 `qc.episode` 负责汇总写库。
- `render.concat` 成功后默认进入 QC（`QC_AUTO_RUN=true`）；无 error 时自动 QC→READY，warning 时 READY+WARNING，error 时停留 QC+FAILED。
- API：`POST /episodes/{id}/actions/qc`、`POST /actions/retry-qc`、`GET /episodes/{id}/qc`、`POST /reviews/{id}/resolve`、`POST /assets/{id}/check`。
- 视觉问题默认 advisory（warning）；`QC_VISION_BLOCKING=true` 才把模型 severity=error 作为阻断错误。图片资产检查直接传原图，视频按镜头抽帧、缩放到长边 ≤1280。
- 实测首轮 3 句视频 QC：模型把“字幕分块只显示半句”误判为文字裁切，2 error/2 warning；在提示词中明确“分块字幕/换行卡片不算溢出”后重跑 0 error/0 warning，QC→READY。占位立绘资产检查返回 pass。
- 测试 52 条全部通过；迁移升级/回滚验证通过。
- 已知限制：无自动修复，只有报告与人工 resolve；视频检查依赖抽帧覆盖，模型可能漏检细微问题；视觉调用会计入 token 成本。

### 2026-10-29 · M4.2 字级强制对齐

- 选用 WhisperX 同款中文 wav2vec2 模型 `jonatasgrosman/wav2vec2-large-xlsr-53-chinese-zh-cn`，从 ModelScope 下载到 `data/assets/voice/align/wav2vec2-chinese/`（约 1.2GB，只保留 PyTorch 权重）。
- 新增 `scripts/runtime/align_words.py`：已知台词 + 逐句音频 → CTC 强制对齐（`torchaudio.functional.forced_align`），输出原文字符级起止时间；数字/符号先用 IndexTTS2 的 `TextNormalizer` 归一，再用 `difflib` 映射回原文。
- 字级时间先按模型帧取点，再把每个字的结束时间延到下一个字开始、最后一个字延到句尾，避免字幕单帧闪烁。
- 新增 `align.episode` media 任务与 `start_align` 服务：校验句级对齐/逐句音频，调用独立 Python 进程，失败可重试；模型加载或推理显存不足时自动回退 CPU。
- 新增 API：`POST /episodes/{id}/actions/align`、`POST /episodes/{id}/actions/retry-align`；`GET /episodes/{id}/audio` 返回字级 `chars`。
- 字幕：`ShotSpec.char_timings` 保存镜头内字级时间，`build_timeline` 用字级起止生成字幕块；标点归并到前一块，避免单独闪一个标点。
- 自动链路：`voice.episode` 完成后默认入 `align.episode`，对齐完成后再入 `render.episode`；`VOICE_AUTO_ALIGN` / `VOICE_AUTO_RENDER` 可分别关闭。
- 实测 3 句：对齐字符数 21/18/16；首句字幕第一块 40–1223ms、第二块 1223–3587ms，截图确认 0.5s 与 1.6s 显示不同字幕块；成片重新渲染成功。
- 已知限制：字幕是“块级显隐”，不是逐字卡拉 OK 高亮；标点时间为零宽；模型每次对齐任务加载约 20–30 秒。

### 2026-10-29 · M4.1 逐句配音与真实音轨成片

- 新增 `line_audio` 表（迁移 `f7b8c9d0e1f2`）与 `episode.audio_path/audio_meta`：按 `(script_line_id, text_hash, voice_key)` 缓存逐句音频；文本、参考音或模型变化才重合成。
- 新增 `app/voice/`：`service.py` 负责启动校验与 NodeRun 幂等，`tasks.py` 的 `voice.episode` 在 `media` 队列逐句调用 IndexTTS2，`audio.py` 用 ffmpeg concat + 句间静音 + 单遍 loudnorm（-14 LUFS）装配 `audio.wav`。
- 逐句音频内容寻址存 `data/audio/lines/<voice_key>/<text_hash>.wav`；整期音轨与 `alignment.json` 存 `data/audio/episodes/<episode_id>/`。
- 镜头时长回写为 `max(1500, 音频时长 + 180ms)`，上限 15s；`alignment.json` 记录每句 start/end 与 shot_end，粒度 sentence。
- 新增 API：`POST /episodes/{id}/actions/voice`、`POST /episodes/{id}/actions/retry-voice`、`GET /episodes/{id}/audio`；`voice.episode` 路由到 `media` 队列。
- `render.concat` 支持 `audio_path`：`start_render` 自动带上 `episode.audio_path`，封装真实 AAC 音轨；无音频时仍走原来的静音轨，兼容 M1.2。
- `voice_auto_render=true` 时任务自动完成 `VOICING → ALIGNING → RENDERING` 并投递渲染；设 false 则停在 ALIGNING，手动调 `/actions/render`。
- 测试 45 条通过；真实 3 句实测：IndexTTS2 生成 3.59s/3.20s/2.91s，音轨 10.25s，成片 1920×1080/25fps + 48kHz 立体声 AAC，时长 10.24s。
- 已知限制（M4.1 当时）：字幕按句内字数比例分配，后续已由 M4.2 字级对齐补齐；TTS 后镜头时长可能超过 M3 的 1.5–6s 节奏区间，M4.1 不再重跑节奏校验；全片单音色洛琪希，不做旁白双音色。

### 2026-10-29 · M4 源 TTS 改用 IndexTTS2

- 用户确认长文本吐字差来自 MeloTTS 源 TTS，决定改用本地 **IndexTTS2** zero-shot 克隆，不做付费云 TTS。
- 模型 `IndexTeam/IndexTTS-2`（gpt 3.25GB + s2mel 1.12GB + qwen emo 1.2GB）与辅助模型（w2v-BERT、BigVGAN、CAMPPlus、semantic codec）已下到 `data/assets/voice/indextts2/`，约 8.3GB。
- 参考音固定为 20 句干净录音中的「人们端午节吃粽子…」，4.94 秒，复制到 `data/assets/voice/indextts2/reference.wav`；原始 20 句保留。
- 8GB 显存策略：fp16 + `use_qwen_emo=False` + Wav2Vec2-BERT 放 CPU 做一次性音色编码；实测可跑。
- 实测 224 字长文本生成 44.74 秒，RTF 1.75；用户试听确认“效果非常好，就以这样为准”。
- 新增 `scripts/runtime/indextts_server.py` 常驻 HTTP 服务（`127.0.0.1:8765`，模型加载一次、单句合成）；`app/providers/tts.py` 改为 `IndexTTS2Provider`，首次合成自动拉起服务，进程退出时关闭；配置项迁到 `tts_indextts_*`。
- 清理：删除 RVC v3 模型/index、MeloTTS 源码与 venv、Piper venv 与模型、MeloTTS 模型/BERT、IndexTTS2 重复 `conformer_shaw.pt` 与重复 semantic codec，共约 5.1GB；未动外部 RVC 仓库（4GB）。
- 测试：42 条全部通过；provider 端到端合成 3.45 秒测试音频成功。
- 待办：`line` 音频表 + 逐句合成任务 + 时长写回 + 音轨装配；再决定强制对齐方案。

### 2026-10-29 · 新干净音频重训 v3

- 用户确认昨天音频杂音过大，提供 20 句干净录音（44.1k mono，总 76.7 秒，21 个切片）。
- 已删除旧 v1 模型、index、v2 日志、旧音频副本和测试 wav；保留 MeloTTS/Piper 基础设施。
- v3 训练：RVC v2 40k、batch 4、200 epochs、pretrained G/D；index IVF76；模型/index 在 `data/assets/voice/rvc/roxy_v3/`。
- MeloTTS 已裁剪语言模块并改为本地 BERT，可离线合成；跨音色测试句已发用户试听，等待吐字清晰度反馈。
- 数据集仅 76.7 秒，远低于 RVC 建议的 10 分钟；若清晰度仍不足，优先补录音到 5–10 分钟，而不是继续调参。

### 2026-10-28 · M4 音色调试暂停

- v1 RVC 模型已训练（40k / 100 epochs / 139 clips），用户试听确认音色相似；但跨音色输出有金属音、吐字不清。
- 已用 pymss speech 模型分离训练音频：vocals RMS -27.9dB，other -35.0dB，确认混有非人声成分。
- v2 已基于分离后的 vocals 完成预处理（95 段）、F0 pm、HuBERT 特征、filelist/config；正式训练在启动前暂停，尚未产出 v2 模型。
- MeloTTS 已本地跑通（独立 venv、ModelScope 模型、本地 BERT），但首次加载慢，尚未接进 M4。
- 下次继续：训练 v2 → index → 用同一句 MeloTTS 对比 v1/v2；再调 pitch/protect/index rate，必要时换 RMVPE 或 GPT-SoVITS。
- 关键路径：`data/assets/voice/raw/roxy_local_v1/`（原音频/分离 stems）、`data/assets/voice/raw/roxy_local_v1_vocals/`、`data/assets/voice/rvc/roxy_local_v1/`（v1 模型）、`data/tools/MeloTTS/`、`data/tools/melo-venv/`。

### 2026-10-28 · M4.1 本地 RVC 音色模型

- 用户提供 13:49 竖屏视频（静态配图 + 音轨），提取为 44.1k mono 人声；峰值 -0.83dB、整体 -25.9 LUFS，立体声相关性 0.995（无明显立体声 BGM）。
- RVC 独立 venv（复用系统 torch 2.6 cu118 / 4060 8GB）；HuBERT 从 ModelScope 下载，v2 40k 底模从 HF CDN 下载；F0 用 pm（RMVPE 镜像太慢，暂未用）。
- 预处理 141 段、有效训练 139 段；batch 4、100 epochs，约 16 秒/epoch；index IVF663。
- 模型与 index 复制到 `data/assets/voice/rvc/roxy_local_v1/`，`voice_profile.json` 记录 checksum/训练参数；3.7 秒测试音频推理成功（40k，时长 3.70→3.68s）。
- 待办：用户试听确认音色；接入 MeloTTS/Piper 基础 TTS；把 RVC 推理封装成后端 provider；必要时补 RMVPE 下载。

### 2026-10-28 · M3.1 资产持久化与复用

- 新增 `asset` 表（迁移 `e5f6a7b8c9d0`）：type/name/reuse_key/path/checksum/尺寸/来源/prompt/model/seed/status。
- 新增 `data/assets` 内容寻址仓库；已有背景/物件复制入库，角色包在原目录索引。
- 入库结果：3 张背景、7 个物件、56 个角色；`data/assets` 约 16MB。
- `build-render-spec` 自动使用入库的纸纹/木地板；静帧确认正常。
- `generate_seedream_image.py` 生成前查 `reuse_key`，命中 APPROVED 直接复用；生成后默认 CANDIDATE 入库，需 `/assets/{id}/approve`。
- 新增 `scripts/tools/ingest_assets.py`、`/api/v1/assets` 查询与 approve/reject；测试 42 条通过。

### 2026-10-28 · M3 分镜 Agent

- 新增 `app/agents/storyboard/`：视觉语法、节奏规则/确定性修复器、LangGraph `storyboard_graph`、shot 持久化、shot → `EpisodeSpec` 构建器。
- 分镜生成按章节调用 DeepSeek，代码归一化 schema；节奏违规由纯函数修复，不依赖 LLM 重排。
- 新增 `episode.storyboard_meta` 迁移 `d4e5f6a7b8c9`；新增分镜查看/校验/确认/重生成、`PATCH /shots`、`build-render-spec` API。
- 实测真实脚本生成 29 镜头、4 种卡片、角色占比 75.9%、节奏 valid；confirm 进 VOICING；render_spec 29 镜头，静帧正常。
- JSON 解析增加 `json-repair` 兜底；分镜输出上限提高，测试 39 条通过。
- 待补：Seedream 背景/物件、半身反应镜头与角色位移、P1 多模态分镜评审。

### 2026-10-28 · M2 脚本 Agent

- 新增 LangGraph `script_graph`：outline → sections → lines（按章生成）→ validate → repair（≤2 次）。
- 新增 DeepSeek `deepseek-flash` provider：JSON mode、429/5xx 退避、JSON 解析失败重试；只允许 `deepseek-flash`。
- Prompt 文件化到 `prompts/script/`（system/outline/sections/lines/repair），hash 进入 `NodeRun.input_hash`。
- 新增 `script_meta` 迁移 `b7e2c9a14d10`；确认选题转 SCRIPTING 并投 `script.generate` 到 `agent` 队列。
- 新增脚本 API：查看/编辑/校验/确认、retry/regenerate；`confirm-script` 校验不通过返回 409。
- 实测：真实 DeepSeek 生成 30 句 / 347 字 / 校验通过；假 LLM 任务入库 24 句、SCRIPT_REVIEW、node SUCCESS；测试 27 条通过。
- 待补：Postgres checkpointer、模型自检、`model_call_log` 成本表、章级重生成。

### 2026-10-28 · M1.2 队列与渲染 worker 骨架

- 新增 `outbox_event` 表与 `episode.render_spec`，迁移 `9c1f4e7a2b30`。
- 新增 `app/workflow/`：Celery app、outbox dispatcher（beat 5s）、状态机、render_service、render_tasks。
- API：`PUT /episodes/{id}/render-spec`、`POST /episodes/{id}/actions/render`，以及 confirm-topic/confirm-script/cancel/publish。
- 渲染拆成 `render.episode → render.shot（按镜头并行）→ render.concat`；eager 模式单镜头 0.5 秒端到端输出 MP4 验证通过。
- `CharacterSpec` 增加 `anchor_x/anchor_y/scale`；新增 `character_packs/placeholder/`、`specs/demo_placeholder.json`、golden frame 回归测试。
- 测试从 7 条增至 16 条；本机 Docker 启动后完成 Postgres/RabbitMQ/Redis 实机联调，3 镜头 6.00 秒成片 READY；RabbitMQ 4.4 兼容配置在 `infra/rabbitmq.conf`。

### 2026-10-28 · 半身表情提示词调整

- 首张 B-01 试生：人物占满画幅、身体和辫子贴边、底边截断突兀，动作/表情偏低。
- 提示词改为：脸部 30–35%、人物居中左右留白 ≥8%、包含上臂与手势、每张写明确动作；B-02～B-05 分别加托腮、举手、抱臂、摊手。
- 需求文档 5.2.1 规格同步；B-01～B-05 重生成后入库。

### 2026-10-28 · Batch 10 前 5 张入库 + 角色位移要求

- B-01～B-05 五张半身图处理为 1080×1350 RGBA；manifest 升到 v15，共 50 个正式资产。
- 豆包水印压在右下角辫子/蝴蝶结上，连通域法无效；统一裁掉源图底部 160px（画布底边即裁切边），水印清除。
- 给 `prepare_character_asset.py` 增加 `--crop-bottom` 与实验性的 `--remove-corner-watermark`（前者正式使用）。
- B-09 害羞入库（manifest v16），用户指定它为构图模板：人物、辫子、发带完整在画布内，腰部截断线在画布内部，底部留白，水印落在空白区。
- 按 B-09 收紧通用前缀（人物总高 85%、脸部宽 25–30%、四周留白、腰部不贴底），B-06/B-07/B-08/B-10 重生成后全部入库；manifest v17，共 55 个；Batch 10 完成。
- 用户新要求：角色不能全程站立不动，必要时配合物件做自然快速平移；写入需求 F-47、架构 10.11，待 M1.2 渲染实现。

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
- 豆包容易把桌子和电脑画出边界，提示词已加“画面边界最高优先级”：窄桌（约肩宽 2.3 倍）、上/下/左/右留白 60/100/60/120px、桌子右端距右边缘 ≥100px、禁用特写/广角、笔记本不能悬浮。
- 旧 `roxy_typing_standing_01.png` 已移到 `alternates/`，不再作为正式 R-19。
- 新版已生成并处理为 1080×1920 RGBA，边界检查通过（桌子右侧/桌腿/笔记本完整）；未提交。

### 2026-10-27 · M1.1 API/DB 骨架完成

- 新增 `compose.infra.yml`：Postgres 17 / RabbitMQ 4 / Redis 7 / MinIO + minio-init；端口避开现有栈。
- 新增 FastAPI 应用：`/health`、`/api/v1/series`、`/api/v1/episodes`，OpenAPI 正常。
- 新增 SQLAlchemy 模型与 Alembic 初始迁移：`series` / `episode` / `script_line` / `shot` / `node_run`。
- 本地默认 SQLite，`uv run alembic upgrade head` 建表；`uv run pytest` 7 条通过；uvicorn smoke test 通过。
- Docker Desktop 本机未启动，compose 只做了 `config` 校验；实际容器启动待 VM。
- 未提交。

### 2026-10-27 · 角色换姿势过渡优化

- 用户反馈 demo 人物切换太突兀；下载参考视频（BV1BgH36DE7y，360p）抽帧分析，换姿势约 0.2 秒完成，带轻微滑动/淡入，不是硬切。
- 舞台改为双层角色图层：新姿势 180ms 内从右侧 36px 滑入并淡入，旧姿势左移 30px 并淡出；字幕和卡片的淡入同步缩短。
- 重新渲染 demo 验证；未提交。

### 2026-10-27 · Batch 9 完成

- R-38 拉网线、R-39 抱 AI 机器人、R-40 举灯泡、R-41 修服务器、R-42 端托盘全部入库。
- manifest 升到 v14，共 45 个正式资产；R-38 为 1124×1819 紧裁场景资产，服务器左边缘/网线底部贴画布边，用户明确接受。
- R-41 为 1228×1887 紧裁场景资产；R-40 的光线被组件过滤掉，只保留灯泡。
- 未提交。

### 2026-10-27 · Batch 8 完成

- R-33 抱 GPU、R-34 放大镜检查日志、R-35 推白板、R-36 大喇叭、R-37 举空白提示牌入库；manifest 升到 v12，共 40 个正式资产。
- R-35 重生成后白板完整；因为横向场景在 1080×1920 画布上会留大片透明区，改用 `prepare_character_asset.py --tight` 输出 1536×1799 的紧裁场景资产，stage 需要自定义缩放/锚点。
- 物件互动资产的道具都保持空白，文字/图表后续由 HTML 合成；未提交。

### 2026-10-27 · Batch 7 动态动作完成

- R-28 被代码包围、R-29 跳跃欢呼、R-30 奔跑、R-31 后仰失衡、R-32 伸手抓取入库。
- manifest 升到 v10，共 35 个正式资产；R-29 用 `--bottom-padding 220` 保留腾空高度。
- 动态姿势在舞台里不能统一按“脚底贴地”处理，M1.1 需要给每个 asset 增加垂直偏移/锚点；R-30 这类跑动姿势还要注意朝向。
- 未提交。

### 2026-10-27 · Batch 8 物件互动扩展

- 用户要求人物多与物件互动；新增 R-33 抱 GPU/服务器、R-34 放大镜检查日志、R-35 推移动白板、R-36 拿大喇叭、R-37 举空白提示牌。
- 提示词写入 `character_packs/roxy/ai_pose_prompts.md`；道具保持简洁、无文字/品牌/图标，文字后期 HTML 合成。
- 与 Batch 7 动态动作分开生成，每批 5 张；未提交。

### 2026-10-27 · M1 渲染链路原型跑通

- 新建 `pyproject.toml` + `uv.lock`；Playwright 钉 1.59，ffmpeg 用 `imageio-ffmpeg`。
- 新增 `app/render/`（models / timeline / cards / stage / capture / encode）、舞台与 5 类卡片模板、`specs/demo_episode.json`、`scripts/demo/render_demo.py`。
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

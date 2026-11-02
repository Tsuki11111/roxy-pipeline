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

- **2026-11-01 运行时简化（当前有效）**：已移除 PostgreSQL、RabbitMQ、MinIO 和 VM 部署；默认 SQLite `data/db/roxy.db` + 单 Redis（Celery broker）+ 本地文件系统，FastAPI 托管 `web/dist`，TTS 为可选组件。Playwright 依赖、渲染器、模板、相关测试和 demo 也已移除，Remotion 是唯一渲染器。下文 2026-11-01 之前的历史条目里出现的 Postgres/RabbitMQ/MinIO/VM/Playwright 只作记录，不再是当前运行方式。
- 本地运行时已验证：`uv run pytest -q` 93 passed；Redis-only compose + API + 2 worker + beat；`/health` 正常，SQLite 6 期数据可见。
- **2026-11-01 脚本/分镜/连续性改造（当前有效）**：新建期不再填时长，脚本生成后由 AI 估算 `estimated_duration_s`；润色增加完整性校验（数字/英文 token、总字数下限）。分镜允许 1–4 句合并成一个镜头（`shot_line`），单镜 3–20 秒；新增 `continuity_group`/`scene`，同组共享背景与实体，Remotion 同组串行生成并要求 `data-entity`。旧期通过迁移回填单句 `shot_line`，行为不变。

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
- M3 分镜 Agent 已跑通：`storyboard_graph` 按章节让 DeepSeek 分组镜头，代码做 schema 归一化 + 确定性节奏修复（连续 3 同卡片、角色连续 5、章节末 icon/pure_text、单镜 3–20s、多句镜头必须有 scene/continuity_group）。
- M3 API：generate/retry/regenerate-storyboard、`GET /episodes/{id}/storyboard`、storyboard/validate、confirm-storyboard（进 VOICING）、`PATCH /shots/{id}`、build-render-spec。
- M3 实测：29 句脚本生成 29 镜头、4 种卡片、角色占比 75.9%、节奏校验 valid；confirm 进 VOICING，build-render-spec 生成 29 镜头 spec，静帧已出图。
- LLM JSON 增加 `json-repair` 兜底；分镜单次输出上限提高到 `max(2000, 行数×220)`，避免截断。
- M3 已补：Seedream 生成 Agent 已实现（批量仍按需触发）、半身反应镜头/章首滑入已接入分镜与渲染；剩余 P1 多模态分镜评审、物件/卡片同组位移。
- 资产复用已落地：`asset` 表 + `data/assets` 持久化仓库；已有 3 张背景 + 7 个物件复制入库、56 个角色在原目录索引；`build-render-spec` 自动解析入库的纸纹/木地板。
- `generate_seedream_image.py` 生成前查 `reuse_key`，命中 APPROVED 直接复用；生成后默认以 CANDIDATE 入库，`/assets/{id}/approve` 后才可复用。`scripts/tools/ingest_assets.py` 可批量索引已有图片。
- M4 音色已定：本地 **IndexTTS2** zero-shot 克隆，用户试听长文本后确认“效果非常好”。模型 `IndexTeam/IndexTTS-2` 在 `data/assets/voice/indextts2/`，参考音固定为 `data/assets/voice/indextts2/reference.wav`；RVC v3 / MeloTTS / Piper 已停用并清理，旧模型与工具链约 5GB 已删除。
- M4.1 逐句配音已跑通：`line_audio` 表按 `(script_line, text_hash, voice_key)` 缓存；`voice.episode` 在 media 队列逐句合成，音频按内容寻址存 `data/audio/lines/`，自动回写镜头时长并装配 `audio.wav`（-14 LUFS），句级对齐写入 `episode.audio_meta`；默认自动进入 RENDERING，成片封装真实 AAC 音轨。实测 3 句 / 10.25 秒成片通过。
- M4.2 对齐已跑通：默认句级（`ALIGN_LEVEL=sentence`），`voice.episode` 产出每句 start/end 并写 `audio_meta`，字幕整句显示，不加载对齐模型。字级为可选：`align.episode` 用中文 wav2vec2（`jonatasgrosman/wav2vec2-large-xlsr-53-chinese-zh-cn`）对每句做 CTC 强制对齐，字级时间写入 `audio_meta.lines[].chars` 和 `alignment.json`；模型在 `data/assets/voice/align/wav2vec2-chinese/`（1.2GB），显存不足自动回退 CPU。
- M4.3 质检已跑通：`render.concat` 完成后默认进入 QC；规则检查流参数/时长/响度/对齐/字幕/资产，再按镜头抽首帧+中间帧送 `deepseek-flash` 多模态；结果写 `review` 表与 `episode.qc_meta`。一般视觉问题默认 warning，`QC_VISION_BLOCKING=true` 才作为 error；但 `text_occlusion`/`card_overlap`（角色遮挡卡片或图示文字）固定为 ERROR。QC Tab 显示证据帧和「去修复」，可直接跳到剪辑 Tab 对应镜头；编辑器支持角色高度/缩放/底部距离。图片资产可单独 `POST /assets/{id}/check`。
- M5.1 已跑通：`POST /episodes/{id}/actions/revise-line` 改单句后重置到 VOICING，只重合成变化句、重对齐并重渲染；镜头片段带 hash 缓存，未变化镜头直接复用；`POST /actions/resume` 按当前状态续跑；`workflow.reconcile_nodes` 清理 stale RUNNING 节点；`POST /actions/package` / `POST /actions/publish` 生成本地发布包（视频、封面、SRT、脚本、metadata、音频）。
- 最终视频输出：渲染完成后复制到 `output/YYYYMMDD-HHMMSS_<episode_id前8位>/episode.mp4`，同目录写 `metadata.json`；`episode.output_path` 指向该路径，`episode.output_meta` 记录本地路径与 MinIO URI。MinIO 上传由 `MINIO_UPLOAD_ENABLED` 控制，VM 可设 `MINIO_REQUIRED=true` 强制成功。
- 自动清理（2026-11-02）：`workflow.cleanup` beat 任务默认每天清理 `tmp/remotion`（30 天）、`tmp/renders`（7 天）、`tmp/qc`（3 天）；成片只保留最新 `OUTPUT_KEEP_VERSIONS=2` 个版本；QC 完成后只保留 review 引用的证据帧。`output/` 当前版本、`data/assets`、`data/tools` 不自动删除。
- M6 Remotion 代码生成 Agent 已跑通（2026-10-30）：`app/agents/remotion/` 每镜头调用一次 DeepSeek 生成自由 TSX，Python 生成 `Root.tsx`/Composition（ID 用 `Shot-0001`，组件名 `Shot_0001`）；代码在 Docker 沙箱 `tsc --noEmit` + `remotion compositions` 校验，失败带编译错误重试一次；全部镜头 READY 才 `remotion_meta.enabled=true`，`POST /actions/rerender` 自动切 Remotion，失败直接报错，不再回退 Playwright。
- 镜头级 Agent 修改已跑通（2026-11-02）：编辑器「镜头属性」顶部新增修改说明框，QC「去修复」自动带入问题/建议/证据并选中镜头；`POST /episodes/{id}/remotion/shots/{shot_id}/revise` 将当前 TSX + 说明交给 Agent，仅重生成该镜头，校验通过后自动 rerender。实测修掉 shot 12 的 `card_overlap`，重渲染后 QC 0 error / 0 warning。
- Remotion 沙箱镜像 `roxy-remotion:4.0.539` 由 `infra/remotion/Dockerfile` 构建；运行参数 `--network none --read-only --init --user 10001 --cpus 2 -m 3g --memory-swap 3g --pids-limit 256`，`/tmp` 与 `/app/node_modules/.cache` 是限容 tmpfs；容器带 `roxy.pipeline=remotion` label，超时会主动 `docker rm -f`。构建用 `scripts/dev/build_remotion.ps1`，构建后清理本项目悬空镜像并清理 7 天前的 Build Cache（支持时再限制到 2GB）。
- **新期自动 codegen（2026-10-31 补）**：配音/对齐完成后 `start_auto_render` 先排队 `remotion.generate`（`REMOTION_AUTO_CODEGEN=true`），codegen 成功后自动 `start_render`；失败/部分 READY 时标记失败，不回退 Playwright。这样新导入的期不需要手动点「生成 Remotion 代码」。
- Remotion 实测：11 镜头整期真实 DeepSeek 生成 + Docker 渲染 + ffmpeg `-c copy` 拼接 + QC 全通过（最终 `health=OK`，0 warning）。首版因生成代码“浅底浅字”被 QC 报 4 条对比度 warning；补 Skill 配色约束并重生成后消失。最终改为 Claude 暖纸 `PaperCard` + 纯演示镜头混排。生成代码在 `tmp/remotion/<episode_id>/`，不进仓库。
- Remotion 生成质量约束：单个镜头代码 ≤7000 字符/180 行；浅色纸纹背景必须用深色字，白字只能放在 alpha ≥0.75 的深色实底上；有 `character` 时必须画 Roxy。早期不写这些约束时会出现“浅底浅字”与整镜头无角色。
- Remotion 缓存键：`shot_render_hash` 包含 renderer、Remotion 版本、镜像 digest、该镜头 code hash；代码或镜像变化只失效受影响镜头。
- Remotion 字幕（2026-10-30 补，2026-11-02 改样式）：Python 生成 Root 时给每个 Composition 包一层 `SubtitleTrack`，按 `build_timeline` 的句级 chunks（转成镜头内相对时间）显示底部字幕；生成代码不画字幕。当前为深色半透明底 + 白字，`renderer_version=m6.5-black-subtitle`，字幕层变化会让镜头缓存失效。
- Remotion 前端：编辑器「Remotion 渲染」卡片支持整期/单镜头生成、状态表、代码预览、「用 Remotion 重渲染」；API 为 `POST /actions/generate-remotion`、`GET /episodes/{id}/remotion`、`GET /episodes/{id}/remotion/shots/{shot_id}`。
- DeepSeek 输出上限：Remotion 单镜头代码用 `max_tokens=16384`（6000/8192 都会截断长镜头）；provider 会检测 `finish_reason=length` 并按失败重试，不再把截断 JSON 当成功。
- 当前阶段仍以角色立绘为主；背景/舞台/演示物件可按需通过 Asset Agent 生成，不再固定暂停。
- AI 主题扩展：需求新增 R-17～R-28（讲解指向/白板/敲键盘/调试翻车/灵光一现/怀疑审视等），核心 6 个提示词在 `character_packs/roxy/ai_pose_prompts.md`（本地）。背景已出纸纹 + 木地板；道具在生成中。
- 代码：`app/agents`、`app/voice`、`app/qc`、`app/render`、`app/workflow`、`web/` 均已落地；SSE 与登录权限未接。

---

## 2. 下一步做什么

### 2.1 立即

1. **Remotion 整期验收**：用 11 镜头真实成片抽查字幕/标注对比度与角色出现率；单镜头不满意可在编辑器里只重新生成该镜头，再「用 Remotion 重渲染」。
2. **进入 M5.2 成本与监控**：M5.1 已闭环局部修改/续跑/发布包；下一步补 token/TTS 成本报表、告警和运维面板。
3. **M6 二阶段（可选）**：Remotion 代码在线编辑/候选对比、失败自动修复、按镜头类型路由模型、成本统计。
4. **M3 P1 待补**：多模态分镜评审、物件/卡片同组位移。

### 2.2 待决事项

| 编号 | 问题 | 现状/建议 |
|---|---|---|
| Q-05 | 2 期并行是否硬指标 | 本地单机先按单期串行；资源足够再开 2 期 |
| Q-06 | `TOPIC_CONFIRMED` 语义 | 按主题生成已移除；该状态仅为历史枚举，新期从 DRAFT 直接导入文稿 |
| Q-07 | 字幕与镜头是否严格 1:1 | 数据模型支持 1:N；MVP 先 1:1 |
| Q-08 | 是否自动上传平台 | 非目标；先做本地发布包 |
| Q-11 | Seedream 立绘尺寸/参考图 | 已确认 1024×1024 可用；立绘尺寸与参考图输入待测 |
| Q-12 | `deepseek-flash` JSON 能力 | 用 Pydantic + JSON 解析兜底；实测后记录 |

---

## 3. 项目结构

当前仓库（全部模块）：

```text
roxy_pipline/
├─ CLAUDE.md / HANDOFF.md / README.md
├─ .env.example / .gitignore / pyproject.toml / uv.lock / alembic.ini
├─ start-dev.bat                     # 一键启动
├─ stop-dev.bat                      # 停止并关闭服务窗口
├─ compose.local.yml                 # 单 Redis（Celery broker）
├─ docs/
│  ├─ AI科普视频Agent系统需求分析文档.md
│  ├─ AI科普视频Agent系统架构选型方案.md
│  ├─ decisions-architecture.md
│  ├─ history/completed-milestones.md
│  └─ assets/roxy_reference.webp     # 本地保留，gitignore
├─ app/
│  ├─ api/
│  │  ├─ main.py                     # FastAPI + web/dist 托管
│  │  └─ routes/
│  │     ├─ episodes/                # crud/script/storyboard/media/render/lifecycle
│  │     └─ assets/shots/series/script_lines/reviews/health.py
│  ├─ agents/                        # script / storyboard / asset / remotion
│  ├─ voice/                         # TTS、对齐、音轨
│  ├─ qc/                            # 规则 + DeepSeek 多模态
│  ├─ render/                        # Remotion 渲染、编码、时间线
│  ├─ assets/                        # 资产领域 + reuse_key
│  ├─ storage/                       # paths/assets/output 本地文件
│  ├─ providers/                     # llm / imagegen / tts
│  ├─ workflow/                      # Celery、outbox、状态机、cancel、resume/revision
│  ├─ publish/                       # 发布包
│  └─ core/ db/ models/ schemas/
├─ migrations/                       # Alembic
├─ infra/remotion/
│  ├─ Dockerfile
│  └─ template/                      # Node/Remotion 工程骨架
├─ prompts/                          # script / storyboard / remotion / asset
├─ web/                              # React + Vite + Ant Design
├─ tests/                            # 扁平 pytest 用例
├─ scripts/
│  ├─ dev/start_all.ps1              # 一键启动
│  ├─ dev/stop_all.ps1               # 按 PID 停止并关闭窗口
│  ├─ runtime/                       # indextts_server.py / align_words.py
│  └─ tools/                         # check_llm / seedream / ingest_assets 等
├─ character_packs/                  # roxy 本地 pack、placeholder 公开包
├─ data/                             # gitignore：db/assets/voice/tools/backup
├─ output/                           # gitignore：成片
└─ tmp/                              # gitignore：可清理中间产物
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
- 渲染依赖：Remotion 镜像 `roxy-remotion:4.0.539`（Docker）+ ffmpeg；Playwright 已移除。
- ffmpeg 用 `imageio-ffmpeg` 自带二进制（`imageio-ffmpeg==0.6.0`，含 libx264/AAC），本机不需要系统 ffmpeg。
- 测试：`uv run pytest -q`
- 渲染由 Celery/Remotion 执行；旧的 `render_demo.py` 和静帧脚本已删除。
- 当前单进程速度约 **0.53 秒/帧**；10 分钟片约 2.3 小时，后续必须并行 render worker。

### 4.2.1 API（M1.1）

- 本地默认 SQLite，先迁移再启动：
  `uv run alembic upgrade head`
  `uv run uvicorn app.api.main:app --reload --port 8000`
  打开 `http://127.0.0.1:8000/docs`；`web/dist` 存在时 `/` 直接打开前端。
- 数据文件：`data/db/roxy.db`。不再提供 Postgres/MinIO 配置。
- 端口：API 8000、Redis 6380；Remotion 只在 Docker 内部运行。

### 4.2.2 队列与 render worker（M1.2）

- `.env` 本地默认：`DATABASE_URL=sqlite+aiosqlite:///./data/db/roxy.db`、`REDIS_URL=redis://localhost:6380/0`、`CELERY_BROKER_URL=redis://localhost:6380/0`。
- 启动 Redis 和迁移：
  `docker compose -f compose.local.yml up -d`
  `uv run alembic upgrade head`
- 分别启动：
  `uv run uvicorn app.api.main:app --reload --port 8000`
  `uv run celery -A app.workflow.celery_app worker -Q workflow,agent,render -l info -c 1`
  `uv run celery -A app.workflow.celery_app worker -Q media -l info -c 1`
  `uv run celery -A app.workflow.celery_app beat -l info -s data/celerybeat-schedule`
- `-c` 是同时渲染的 Chromium 数量；单机 SQLite 建议固定 `-c 1`，避免并发写。
- media worker 常驻 IndexTTS2（GPU），并发必须为 1；Windows 调试同样加 `--pool=solo`。
- Windows 本机 Celery 默认 prefork 不可用：调试加 `--pool=solo`（单并发）。
- Windows 一键启动（本地极简模式）：双击仓库根目录 `start-dev.bat`（内部 `scripts/dev/start_all.ps1`），只启动 Docker、单个 Redis 容器、API、两个 worker 和 beat；前端由 FastAPI 托管 `web/dist`，默认 SQLite + 本地文件系统，不启动 Postgres/RabbitMQ/MinIO。`-Dev` 参数会额外启动 Vite。
- 停止服务：双击 `stop-dev.bat` 或运行 `scripts/dev/stop_all.ps1`，按 `data/run/*.pid` 关闭整棵进程树，并 `docker compose -f compose.local.yml down` 停止 Redis（数据卷保留）；启动脚本每次会先清理上次残留的空窗口，避免服务窗口越积越多。只想保留 Redis 时加 `-KeepRedis`。
- Celery broker 固定为 Redis：`CELERY_BROKER_URL=redis://localhost:6380/0`，不再回退 RabbitMQ。
- 队列：`workflow`（状态推进/outbox 补投）、`agent`（`storyboard.generate` / `qc.episode`）、`media`（`voice.episode` / `align.episode`）、`render`（`render.episode` / `render.shot` / `render.concat`）。
- 触发真实队列渲染：通过前端视频期详情页或对应 API 动作发起；旧的队列 demo 脚本已删除。
- beat 每 5 秒执行 `workflow.dispatch_outbox`，把 PENDING 事件投到 Redis；失败按指数退避，5 次后置 FAILED。
- `CELERY_TASK_ALWAYS_EAGER=true` 只用于任务级测试；在 async dispatcher 里同步执行 task 会和事件循环冲突。

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

- 运行目标：Windows 单机；Docker 仅用于 Redis 和 Remotion 沙箱，不再有 VM 部署。
- **本地栈**：`compose.local.yml`（project `roxy-local-min`）只起 `roxy-local-min-redis`，数据卷 `roxy-min-redis-data`，AOF 持久化。
- **配置来源**：本地 `.env` 用 `.env.example`；`.env.vm.example` 已删除。
- **后端解耦**：数据库、Redis、API 地址全部经 `app/core/config.py` 的 `Settings` 读取；业务模块不得出现 `localhost` 或容器名。
- 端口：API 8000、Vite 5173、Redis 6380；Remotion 容器只在 Docker 内部运行。
- 数据目录：`data/db`、`data/assets`、`output/`、`tmp/`；升级/重装前手动备份。
- 根分区约 18GB 不够；数据盘挂 `/data`，`PGDATA`、`MINIO_DATA`、备份都指过去。
- MinIO 预签名 URL 要区分 `MINIO_INTERNAL_ENDPOINT`（容器内 `http://minio:9000`）与 `MINIO_PUBLIC_ENDPOINT`（浏览器可访问的外部地址）。

### 4.5 渲染约定

- 输出规格：1920×1080、25fps、H.264/AAC 48kHz。
- 所有动画由 `renderAt(tMs)` 计算，禁用 CSS animation / `Date.now()` / `Math.random()`；随机用固定 seed。
- 角色切换按镜头自己的 `start_ms` 初始化；`character_from` 提供上一镜角色，新角色从最近侧屏幕外 280ms 冲入，旧角色 80ms 模糊让位；换镜时卡片与字幕直接切换，不做透明淡入。
- 镜头片段编码参数必须完全一致，最终 `-c copy` 拼接。
- 含文字卡片用 HTML；Seedream 只做背景/舞台/演示物件（无文字空壳）。
- 背景/演示物件生成后固定资产化，不每期重生成。
- Remotion 为唯一渲染器；Playwright 已移除。Remotion 输出经 ffmpeg 统一为 1920×1080/25fps/H.264/yuv420p/CRF18，保证 `-c copy` 拼接。
- Remotion 代码只存在于 `tmp/remotion/<episode_id>/`；`remotion_shot` 表记录 code_hash/status/input_hash。
- 生成代码约束：单镜头 ≤7000 字符；浅底必须深字，白字必须有深色实底；有 `character` 必须出现 Roxy；不能用随机/时间/CSS 动画。
- 布局约束：Remotion 不做关键词标签；画面文字用 `PaperCard` Claude 暖纸卡（variant：note/quote/index/letter/sticky/specimen；tone：cream/sand/peach/sage；transition：slide/zoom/flip/drop/reveal/push）。Python 按镜头序号排期：约 1/3 镜头 `card_style=null` 做纯演示，其余给卡并指定样式/动效；切换位移 ≥300px、缩放变化 ≥0.3、旋转 ≥5° 或 rotateY ≥45°。
- 镜头分组：`shot_line` 关联 1–4 句连续台词，单镜 3–20 秒；详细讲解保持一个镜头，用 `<Sequence>` 演分子动画；章节台词 ≥4 句时至少一个多句镜头。
- 视觉连续性：`continuity_group` + `scene`（setting/entities）同组共享；Remotion 同组按 seq 串行生成，后一镜 payload 带 `previous.code`，实体节点必须带 `data-entity="<id>"`，缺失重试一次后失败。
- 镜头级 Agent 修改：编辑器「镜头属性」顶部有「让 Agent 修改这个镜头」输入框；QC Tab 的「去修复」会把问题、建议和证据帧带进修改说明并选中对应镜头。提交 `POST /episodes/{id}/remotion/shots/{shot_id}/revise`（`instruction`）后，后端把当前 TSX + 修改说明交给 Remotion Agent 只重生成该镜头，校验通过后自动重渲染；其他镜头复用缓存。
- 角色层级：`Stage` 使用 `isolation:isolate` 建立层叠上下文，`Character` 固定 `zIndex:-1`，所有 SVG/PaperCard/文字在其上方；渲染前会把 `infra/remotion/template/src/components` 同步到现有 workdir，`renderer_version=m6.5-black-subtitle` 使旧片段缓存失效。
- 角色动效：有 `character` 的镜头必须有入场（offsetX ±400–600、opacity 0→1、scale 0.94→1、rotate ±2°）、呼吸轻摆和至少一次手势/让位；生成检查会拒绝只有 `src/side/height` 的静态 `<Character>`。
- 背景与字幕：`Stage` 统一渲染 Claude 暖纸背景（纸纹 + 底部浅阴影 + 手绘星），不再使用旧纸纹/木地板资产；`SubtitleTrack` 为深色半透明底 + 白字圆角字幕条。
- 改动 `infra/remotion/template/` 后必须重建镜像 `roxy-remotion:4.0.539`，否则沙箱仍用旧组件。根目录 `.dockerignore` 只保留 `infra/remotion/template` 作为构建上下文，Dockerfile 的 apt 源使用阿里云镜像；否则会把 `data/output/tmp` 共十几 GB 送进 Docker，且 `deb.debian.org` 在国内容易卡死。
- Remotion 字幕由 Root 里的 `SubtitleTrack` 统一叠加（bottom 40，深色半透明底 + 白字字幕条）；生成代码不画字幕，y 940–1080 的底部区留给字幕。
- 画面长段文本由生成代码的 `PaperCard` 组件渲染（Claude 暖纸/墨字/陶土），Python 只负责底部字幕 `SubtitleTrack`。文本长度和分段由模型决定，优先直接用 `narration`/`card.text` 的长段。
- Docker 不可用或镜像缺失时 Remotion 生成失败，期次标记失败；`REMOTION_ONLY=true` 下不回退其他渲染器。

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

已完成里程碑的详细记录已归档到 [docs/history/completed-milestones.md](docs/history/completed-milestones.md)；本文只保留当前状态、下一步和仍然有效的坑。

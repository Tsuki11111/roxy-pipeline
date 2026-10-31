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

AI 科普视频自动生成 Agent 系统：文章导入 → AI 结构化脚本/润色 → 分镜 → 逐句 TTS/对齐 → HTML 卡片/逐帧渲染 → ffmpeg 拼接 → 质检。

- **个人自用项目**；洛琪希为《无职转生》角色，仅限非商业同人使用，遵守需求文档第 11 章。
- **当前阶段**：M1 渲染原型 + M1.1 API/DB + M1.2 队列/渲染 worker + 文章导入/文稿优化 Agent + M3 分镜 Agent + 资产持久化/复用 + Asset Agent + M4.1 逐句配音 + M4.2 句级对齐（字级可选） + M4.3 规则/DeepSeek 多模态质检 + M5.1 局部修改/续跑/发布包 + Web 控制台 + 分镜时间线编辑器 + Remotion 逐镜头代码生成 Agent（唯一生产渲染器）已跑通；按主题自动生成脚本的功能已移除，下一步成本报表与监控。
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
- **小改动不自动 commit/push**：小范围文档、提示词、清单调整留在工作区并口头说明；只有大功能、结构调整、里程碑或用户明确要求时才提交推送。
- **不擅自换技术栈**。见 README 技术栈表；有异议先讨论，再改文档。
- **先跑通再优化**；但状态机幂等、缓存键、渲染确定性这些地基不能省。
- **任何 Key / Token 只进本地 `.env`**；不要写进文档、代码、提交信息或聊天回复。
- **公开仓库**：不提交未授权的角色图、BGM、字体；默认用 placeholder 素材。
- **不删除 / 覆盖用户已有文件**；改动前先读。

---

## 硬约束

### 1. 技术栈已定

Python 3.12 + FastAPI + Pydantic v2 + SQLAlchemy 2.0 + PostgreSQL + RabbitMQ/Celery + Redis + MinIO +
Remotion（Node 22，Docker 沙箱，唯一生产渲染器）+ Playwright/Chromium（仅测试/历史）+ ffmpeg + LangGraph（仅 AI 子图）；
前端 React + Vite + TypeScript + Ant Design。详见架构方案第 3 节。

### 2. LangGraph 边界

- LangGraph 只做 `storyboard_graph` / `qc_repair_graph`；脚本来自文章导入与文稿优化，不再有按主题生成脚本的图。
- 媒体流水线（TTS、渲染、拼接）仍由 PostgreSQL 状态机 + Celery 负责。
- `episode.status` 是业务事实来源；LangGraph checkpoint 不是。
- 图节点不直接跑 Chromium/ffmpeg/TTS。

### 3. 模型路由

- 文本/代码主模型：DeepSeek `deepseek-flash`（当前 Key 只开放这个模型）。
- 豆包 Pro：仅备选/A-B，不阻塞主流程。
- 图像素材：火山方舟 Seedream 5.0 Pro，生成候选后**人工筛选、固定资产化**；仅限原创角色/背景/装饰，洛琪希会被版权过滤，不能 AI 复刻。文本→素材规划由 `app/agents/asset/` 的 Asset Agent 用 DeepSeek + `reuse_key` 复用，缺失才生成。
- 视觉质检：统一用 **DeepSeek `deepseek-flash` 多模态**；图片资产直接传图检查，完整视频按镜头/时间点抽帧 + ffmpeg 流指标一起送模型。不接入豆包 Vision 等第二视觉模型；确定性 DOM/几何规则仍作为前置检查。
- Remotion 代码生成：`app/agents/remotion/` 用 DeepSeek `deepseek-flash`，每镜头一次调用，Prompt 在 `prompts/remotion/`，Skill 在 `app/agents/remotion/skills/remotion_shot/SKILL.md`。
- **TTS：本地 IndexTTS2 zero-shot 声音克隆**（Python 3.11 独立环境 + 常驻 HTTP 服务），不使用付费云 TTS；参考音固定为 `data/assets/voice/indextts2/reference.wav`。
- **含文字的信息卡片必须用代码渲染（HTML 或 React/Remotion），不得用图像生成模型**。
- **脚本与配音统一为洛琪希单人口播**，不设旁白；`speaker` 字段仅为兼容旧数据保留，新导入统一写 `roxy`。脚本单句 ≤50 字，校验是硬闸口。

### 3.1 Remotion 渲染边界

- **Remotion 是唯一生产渲染器**；`REMOTION_ONLY=true` 时 Playwright 只保留给测试/历史，不参与新期渲染。
- **新期自动 codegen**：配音/对齐完成后 `start_auto_render` 先排队 `remotion.generate`（`REMOTION_AUTO_CODEGEN=true`），成功后自动进入渲染；codegen 失败或未全部 READY 时标记失败，不回退 Playwright。不要只在编辑器手动点生成。
- **每镜头一个 Composition**：LLM 只生成 `src/shots/shot_<seq>.tsx`；Root、Composition ID、时长、尺寸、素材映射由 Python 生成，LLM 不得改。
- 生成代码只能在 **Docker 沙箱**执行（`--network none --read-only --user 10001 --cpus 2 -m 3g --pids-limit 256`），禁止在宿主机直接 `npm run`。
- 生成代码只写 `tmp/remotion/<episode_id>/`，不进主仓库；固定依赖宇宙（react/remotion/@remotion/*/模板组件），不得新增 npm 依赖、外链或 Node 内置模块。
- 全部镜头代码 READY 才启用 Remotion；单镜头失败即失败，不切换 Playwright。缓存键必须包含 renderer、Remotion 版本、镜像 digest 和该镜头 code hash。
- Remotion 输出必须经 ffmpeg 归一化为 1920×1080/25fps/H.264/yuv420p，帧数与时间线一致，保证 `-c copy` 拼接。
- 生成质量约束：单镜头代码 ≤7000 字符/180 行；浅底深字、白字必须有深色实底；有 `character` 必须出现 Roxy；禁止随机/时间/CSS 动画。
- 布局约束：Remotion 不做关键词标签；画面文字用 `PaperCard` Claude 暖纸卡（variant：note/quote/index/letter/sticky/specimen；tone：cream/sand/peach/sage；transition：slide/zoom/flip/drop/reveal/push）。Python 按镜头排期：约 1/3 镜头 `card_style=null` 做纯演示，其余给卡并指定样式/动效；切换位移 ≥300px、缩放变化 ≥0.3、旋转 ≥5° 或 rotateY ≥45°。
- 角色动效：有 `character` 的镜头必须有入场（offsetX ±400–600、opacity 0→1、scale 0.94→1、rotate ±2°）、呼吸轻摆和至少一次手势/让位；禁止只有 `src/side/height` 的静态 `<Character>`，生成服务会检查并重试。
- 背景与字幕：`Stage` 统一渲染 Claude 暖纸背景（纸纹 + 底部浅阴影 + 手绘星），不要再用旧纸纹/木地板资产；`SubtitleTrack` 为暖纸底 + 墨字 + 陶土短线。
- 风格约束：视觉风格必须服务内容；先判断主题再选色调/材质/线条/图形语言，同一期保持统一；禁止与内容无关的赛博霓虹、故障扫描线、机器人装饰。
- 字幕：由 Python 生成 Root 时统一叠加 `SubtitleTrack`（句级 chunks、镜头内相对时间），生成代码不画字幕；字幕层变化要提升 `renderer_version` 失效镜头缓存。
- 画面长段文本由生成代码的 `PaperCard` 组件渲染（Claude 暖纸/墨字/陶土），Python 只叠加底部字幕；文本长度和分段由模型决定，优先直接用 `narration`/`card.text` 的长段。`TerminalCard`/`Card`/`Label`/`Caption`/`Board` 禁止用于新镜头。
- 改动 `app/agents/remotion/templates/` 后必须重建镜像，否则沙箱仍用旧组件。
- 许可：个人/非商业免费；商用需 Remotion 授权，本项目保持个人非商业。镜像 `roxy-remotion:4.0.539` 由 `infra/remotion/Dockerfile` 构建。

### 4. 密钥与素材

- `.env` 已在 `.gitignore`；仓库只提交 `.env.example`。
- **资产分工**：洛琪希等版权角色立绘由用户用 ChatGPT/豆包/自绘提供；背景、舞台层、演示物件由 Seedream 生成；含文字信息卡片用 HTML/React 渲染。
- **素材生成**：角色立绘由用户提供；背景/舞台/演示物件可通过 `scripts/tools/generate_seedream_image.py` 或 Asset Agent 按文稿生成候选，人工 approve 后复用。
- `docs/assets/roxy_reference.webp` 已 gitignore，不随公开仓库分发。
- `character_packs/*` 默认忽略，只允许 `character_packs/placeholder/`。
- **图片资产必须可复用、持久化**：所有图像先查 `asset` 表的 `reuse_key`；已入库且 `APPROVED` 的资产直接复用，不重复生成。新生成的背景/物件必须复制到 `data/assets`（VM 为 `/data/assets`）并记录 checksum、prompt、model、seed；同时镜像到 MinIO `minio_bucket_assets`，对象路径 `assets/<type>/<checksum>.<ext>`，写入 `asset.meta["minio"]`。角色包在原目录索引。禁止每期重新生成。
- **音色克隆数据合规**：IndexTTS2 / 声音克隆只能用用户本人声音或用户持有明确书面授权的声音；禁止用动画原声、声优本人音频克隆或生成新台词。参考音与音色模型放 `data/assets/voice/`（gitignore），不提交公开仓库；`series.voice_profile` 固定 provider、模型、参考音等参数。
- AI 生成图带可见水印（如“豆包 AI 生成”）时不得直接入成片；先确认服务条款，允许再用脚本排除/遮罩。
- `tmp/`、`data/` 忽略；生成的样片/帧不要提交。

### 5. 运行环境

- 开发机：Windows 11 + Git Bash；Python 可用；Docker Desktop 已可用。本地 compose 默认只起 Postgres/RabbitMQ/Redis，MinIO 用 `storage` profile。
- **Remotion 沙箱**：需要 Docker；镜像 `docker build -f infra/remotion/Dockerfile -t roxy-remotion:4.0.539 .`，tag 与 `REMOTION_IMAGE` 一致。生成代码在 `tmp/remotion/`；镜像 digest + 版本进入镜头缓存键。Windows Git Bash 挂载路径需 `MSYS_NO_PATHCONV=1`。
- **IndexTTS2 独立环境**：主项目 Python 3.12；IndexTTS2 固定在 `data/tools/indextts-venv`（Python 3.11 + torch 2.8 cu128），由 `scripts/runtime/indextts_server.py` 常驻 `127.0.0.1:8765`；模型在 `data/assets/voice/indextts2/`（gitignore）。8GB 显存下用 fp16，并把 Wav2Vec2-BERT 放 CPU 做一次性音色编码。
- **对齐**：默认句级对齐（`ALIGN_LEVEL=sentence`），配音本身产出每句起止时间，字幕整句显示，不加载对齐模型。字级对齐为可选（`ALIGN_LEVEL=char`）：同一 Python 3.11 环境运行 `scripts/runtime/align_words.py`，中文模型在 `data/assets/voice/align/wav2vec2-chinese/`；`align.episode` 与 `voice.episode` 都在 media 队列，TTS 并发固定 1。
- **内存自动回收**：配音结束停掉 IndexTTS2（`TTS_UNLOAD_AFTER_VOICE=true`），对齐前再兜底 `/shutdown`（`ALIGN_STOP_TTS=true`）；每个镜头渲染后、对齐/QC/拼接结束都调用 `release_memory()`。TTS 下次配音自动重启。16GB 本机不要关闭这些行为。
- **最终视频输出**：渲染完成后写到 `output/YYYYMMDD-HHMMSS_<episode_id8>/episode.mp4`，同目录写 `metadata.json`；`episode.output_path` 指向该文件。`MINIO_UPLOAD_ENABLED=true` 时上传 `MINIO_BUCKET_OUTPUT`；VM 用 `MINIO_REQUIRED=true` 强制成功。
- 部署目标：Ubuntu 24.04 VM，Docker 29 / Compose 2.40。
- **本地与 VM 资源隔离**：本地用 `ROXY_ENV=local` / `COMPOSE_PROJECT_NAME=roxy-local`，VM 用 `ROXY_ENV=vm` / `COMPOSE_PROJECT_NAME=roxy-vm`；容器名、网络、数据卷按环境分开，不能共用同一套资源。
- **后端禁止写死服务地址**：数据库、RabbitMQ、Redis、MinIO、API 地址全部从环境变量 / `Settings` 读取；业务模块不出现 `localhost`、VM IP 或容器名。地址只出现在 `.env` / `.env.vm` 和 compose 的环境变量里。
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

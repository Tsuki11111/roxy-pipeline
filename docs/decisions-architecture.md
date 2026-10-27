# 架构决策记录

| 项目 | 内容 |
|---|---|
| 状态 | 已确认 |
| 日期 | 2026-10-26 |
| 关联文档 | [需求分析文档](AI科普视频Agent系统需求分析文档.md)、[架构选型方案](AI科普视频Agent系统架构选型方案.md) |

---

## ADR-001：采用方案 A（Python 模块化单体 + 进程级拆分 + Celery）

### 背景

系统需要完成从选题到成片的全自动流水线：脚本生成、分镜、逐句 TTS、强制对齐、HTML 卡片渲染、逐帧渲染、ffmpeg 拼接、质检与局部重跑。需求要求断点续跑、镜头级缓存、2 期并行和渲染横向扩展。

### 决策

采用 Python 3.12 + FastAPI + PostgreSQL + RabbitMQ + Redis + MinIO + Celery；一套代码库按进程拆分为 `api`、`workflow`、`agent`、`media`、`render`、`scheduler`；前端用 React + Vite + Ant Design；渲染用 Playwright/Chromium + ffmpeg。

### 理由

1. LLM、TTS、强制对齐、视觉质检和 ffmpeg 的主生态都在 Python，单一语言避免了 Java/Python 双语言契约和两套 CI。
2. 进程级拆分已经能满足“渲染单独扩容”，不需要为 MVP 支付微服务成本。
3. 现有 Ubuntu VM 可以直接用 Docker Compose 起步；渲染 worker 后续可接入同一队列横向扩展。
4. 状态机、断点续跑和局部重跑用“PostgreSQL 状态 + 幂等节点 + 内容寻址缓存”实现，逻辑透明、可测试。

### 代价与风险

- 单机 CPU/磁盘是主要瓶颈；需要独立数据盘和资源上限。
- Celery + 自研状态机要求严格的幂等设计，否则会重复执行或卡死。
- 没有高可用；单机故障会导致整条流水线停止。

### 重新评估触发条件

- 渲染 worker 超过 2 台机器，或工作流节点超过 40 个：考虑拆 render-service 或引入 Temporal。
- 团队规模扩大到需要独立部署/独立权限：按触发条件拆分服务。
- 渲染吞吐仍不足：评估 Remotion。

---

## ADR-002：LangGraph 只用于 AI 决策子图，不做媒体流水线总编排

### 背景

脚本生成、分镜生成和质检回炉都有状态、条件分支、循环和局部人工选择，适合用图表达；但 TTS、200 个镜头的 Chromium 渲染和 ffmpeg 拼接是长任务，需要分布式队列、心跳、重试和横向扩展。

### 决策

- LangGraph 负责 `script_graph`、`storyboard_graph`、`qc_repair_graph` 三个短生命周期子图。
- 媒体流水线仍由 PostgreSQL 状态机 + Celery/RabbitMQ 负责。
- LangGraph checkpoint 存 PostgreSQL 独立 schema `agent_checkpoints`（通过连接串 `search_path` 或独立数据库隔离），`thread_id = episode_id:stage:run_id`。
- 主人工闸口（选题确认、脚本确认）由 episode 状态机 + API 管理；图内 `interrupt` 只用于局部选择。
- 图节点不直接执行 Chromium/ffmpeg/TTS；需要媒体任务时写业务表并投递 Celery。
- `graph_version` 进入节点缓存键；升级图定义后不复用旧 checkpoint；阶段成功后 30 天清理 checkpoint。

### 理由

1. LangGraph 的条件边、循环、checkpoint 和 interrupt 正好覆盖 AI 子图，不需要自己写图调度。
2. LangGraph OSS 是进程内执行；把它当唯一编排器，200 个渲染任务仍要外挂 worker 池，等于多了一层而没有减少系统数量。
3. 保持 episode 状态机为唯一业务事实来源，图运行失败不会污染业务状态；渲染故障也不会拖住图。
4. 避免长期挂起的图线程和 checkpoint 膨胀，降低图版本升级的兼容成本。

### 代价与风险

- 两套编排概念（episode 状态机 + LangGraph），需要文档和代码都明确边界。
- checkpoint 可能包含 Prompt/模型输出，需要与业务数据同级保护。
- LangGraph 版本升级可能带来 checkpoint 不兼容；通过短生命周期和 `graph_version` 控制。

### 重新评估触发条件

- 媒体任务也需要在图里统一表达，且愿意接受 LangGraph Platform/Server + 自建 worker 池的运维成本。
- 工作流复杂到需要跨阶段持久化、定时器和分布式扇出：优先评估 Temporal，而不是把 LangGraph 扩成总编排器。

---

## ADR-003：部署与外部服务约束

### 已确认

- 部署：现有 Ubuntu VM 先跑。
- 模型：国内 LLM/TTS 为主。
- TTS：云 TTS 优先。

### 落地约束

1. 现有 VM 根分区约 18GB，必须挂 ≥200GB 数据盘（推荐 500GB）；Postgres、MinIO、备份都放 `/data`。
2. 该 VM 已占用 8088/8001/8002/8003/9000/9002；本项目使用 8080/8443 和 MinIO 9100/9101。
3. 2 期并行需要约 8–16 vCPU / 32GB；如果与 ItsMyGo/rag_helper 共用且资源不足，先单期串行或另开渲染机。
4. 云 TTS 的字级时间戳、并发配额和计费必须在选型阶段实测；不满足时用 WhisperX/ctc-forced-aligner 兜底。
5. Web 默认只暴露局域网；公网访问必须加 TLS、强认证、限流和审计。

### 待决事项

- 云 TTS 最终厂商与音色（Q-01）。
- 现有 VM 的实际 CPU/内存规格与数据盘挂载方案（Q-02、Q-03）。
- 2 期并行是否为 MVP 硬指标（Q-05）。
- `TOPIC_CONFIRMED` 状态语义（Q-06）。
- 字幕与镜头是否严格 1:1（Q-07）。

---

## ADR-004：LLM 供应商与模型约束

### 已确认

- DeepSeek 官方 API Key，可用模型仅 `deepseek-flash`。
- 火山引擎 API Key。

### 决策

- `deepseek-flash` 作为文本/代码主模型，承担脚本大纲、分段、逐句、分镜和自检。
- 火山方舟豆包 Pro 只做备选和 A/B 对照，不阻塞主流程；视觉模型可选，不作为关键路径。
- 视觉质检优先 DOM/几何规则；豆包 Vision / Qwen-VL / GLM-4V 只在配置后做语义抽查。
- 火山方舟 Seedream 用于图像素材候选（见 ADR-005），与文本 LLM 分开。

### 理由

1. 用户实际体验 `deepseek-flash` 在文本/代码上强，不应按“flash”这个名字判断为轻量模型。
2. 豆包 Pro 未开通不应阻塞脚本/分镜主流程；保留备选用于 A/B 或故障切换。
3. 视觉质检的硬问题（文字溢出、角色裁切）用 DOM/几何规则更可靠，视觉模型能力不足也不影响主流程。
4. 图像生成是另一类模型（Seedream），不能拿文本 LLM 代替，也不能用来生成含文字的信息卡片。

### 需要手动配置

- DeepSeek Key 填入 `.env`，`DEEPSEEK_MODEL=deepseek-flash`。
- 豆包 Pro / 视觉模型按需开通；不配置也能跑文本主流程。
- 图像素材生成需要在方舟控制台开通 Seedream（候选 `doubao-seedream-5-0-pro-260628`），填入 `ARK_IMAGE_MODEL`。
- 确认火山引擎 Key 是否覆盖豆包语音 TTS；TTS 通常需要 AppID + Access Token，不是方舟 Key。

### 验证记录（2026-10-26）

- DeepSeek `/models` 返回 `deepseek-flash` 与 `deepseek-v4-pro`；按实际体验选 `deepseek-flash` 作为文本主模型。
- 火山方舟 Key 可访问 `/models`；`doubao-seed-2-1-pro-260915` 返回 `ModelNotOpen`，但豆包 Pro 已降为备选，不阻塞主流程。
- `/models` 列表包含 Seedream 图像生成模型（如 `doubao-seedream-5-0-pro-260628`），但需在控制台开通后才能调用。
- 批量探测结果：`doubao-seed-2-1-pro-260915`、`doubao-seed-2-1-turbo-260628`、`doubao-seed-2-1-lite-260915`、`doubao-seedream-5-0-pro-260628`、`doubao-seedream-5-0-flash-260915` 均为 `ModelNotOpen`（存在，可开通）；旧版 Doubao 文本/视觉模型与 Seedream 4.5 返回 `InvalidEndpointOrModel.NotFound`（当前账号无权限）。
- 更换 `ark-...` 格式的 API Key 后复测，鉴权通过，但上述模型仍为 `ModelNotOpen`；确认根因是模型未在方舟控制台开通，不是 Key 错误。
- 2026-10-26 再次复测：`doubao-seed-2-1-pro-260915` 与 `doubao-seed-2-1-lite-260915` 已 PASS；`doubao-seed-2-1-turbo-260628` 仍为 `ModelNotOpen`。
- Seedream 5.0 Pro/Flash 已开通，但返回 `SetLimitExceeded`（HTTP 429）：账号处于“安全体验模式”，用量达到设定上限；需在开通管理页调整或关闭安全体验模式，或改为按量付费。
- 关闭安全体验模式后复测：Seedream 5.0 Pro 生成成功（1024x1024, RGB），图像生成链路可用；1080x1920 立绘尺寸和参考图输入待测。
- 其他试用的豆包模型返回 `InvalidEndpointOrModel.NotFound`；视觉模型能力待实测，不作为关键路径。

### 风险与重新评估

- `deepseek-flash` 在长脚本/复杂分镜上质量不达标：用豆包 Pro 或第二家模型做 A/B，按评测结果切换，不靠名字假设。
- 视觉模型能力不足：以 DOM 规则和人工抽检为主，视觉模型只做辅助。
- 图像生成一致性差：固定 canonical 图/参考图/seed，人工筛选后固定资产化（见 ADR-005）。

---

## ADR-005：AI 生成美术素材，文字卡片仍用 HTML

### 背景

角色立绘、背景和装饰素材的产出是主要人工成本之一；用户希望用 AI 完成素材生成。但信息卡片承载大量文字，图像生成模型对中文文字和版式的准确率不可靠。

### 决策

- 角色/背景/装饰素材用图像生成模型（首选火山方舟 Seedream）产出候选，人工筛选/修图后入库。
- 入库后作为固定资产，不在每期视频中重新生成；角色 pack 版本化。
- 含文字的信息卡片仍由 HTML 模板渲染（F-25），图像生成只做美术层。
- 生成记录 `prompt`、`model`、`seed`、`reference_assets`、provider request id；后处理包括背景移除、缩放、描边。
- 图像生成 provider 可配置；未配置时使用 placeholder 素材，不影响渲染链路。
- 生成结果必须人工审核后才能进入资产库和成片。

### 理由

1. AI 能显著降低角色/背景的一次性制作成本，但无法保证文字卡片的准确性和版式一致性。
2. 固定资产化能解决角色形象漂移问题；每期重生成会让脸、服装、比例不断变化。
3. 人工筛选是必要的质量闸口，生成候选不等于可直接使用。

### 代价与风险

- 图像生成模型对透明底、线稿、文字的处理不稳定，需要后处理和人工修图。
- 角色一致性依赖参考图/seed，换模型或换 pack 会漂移；必须版本化并重渲染相关镜头。
- AI 生成的洛琪希衍生图仍受 C-01～C-06 约束，且受图像服务条款约束。
- 2026-10-26 实测：Seedream 5.0 Pro 可生成原创角色（1088×1920），但洛琪希名称、参考图或高度相似描述会触发版权过滤（`OutputImageSensitiveContentDetected.PolicyViolation`）；Roxy pack 必须自绘/外包，AI 只做原创角色/背景/装饰。

### 重新评估触发条件

- Seedream 角色一致性或线稿质量不达标：改外包/自绘，或换图像模型；不要把未筛选素材直接进成片。
- 图像生成成本高于人工：只保留背景/装饰生成，角色立绘改为人工。

---

## ADR-006：角色立绘用户提供，背景/演示物件 Seedream 生成

### 背景

Seedream 因版权过滤不能生成洛琪希；用户愿意用 ChatGPT / 豆包 / 自绘提供角色立绘。背景、舞台层和演示物件数量多、可复用，适合交给 Seedream。

### 决策

- 角色立绘：用户负责，系统不调用 Seedream 生成版权角色；pack 放 `character_packs/roxy/`，本地保留，不提交公开仓库。
- 背景 / 舞台层 / 演示物件：Seedream 生成候选，人工筛选后入库。
- 含文字的信息卡片：仍用 HTML 渲染；Seedream 只提供无文字的空壳/纹理/装饰。
- 图标：优先 SVG；需要 AI 版时用 Seedream 生成图标表再切图。
- 首版 Seedream 清单约 12–17 张：背景 3–4、演示物件 6–8、图标表 1、封面/片头片尾 2–4。

### 理由

1. 角色立绘涉及版权，交给用户生成/提供可以避免平台版权过滤和合规争议。
2. Seedream 擅长背景、纹理、空壳物件；文字卡片交给 HTML 能保证中文和版式准确。
3. 背景和物件一次生成、长期复用，符合固定资产化原则。

### 代价与风险

- 角色 pack 进度依赖用户产出；M1 先用占位 pack 跑通渲染。
- Seedream 物件的透视、留白区域和线条风格可能与 HTML 模板不一致，需要人工筛选和模板适配。
- 豆包等来源的水印/条款问题：不能直接入成片，使用前确认条款。

### 重新评估触发条件

- Seedream 的物件质量或一致性不足：改用 CSS/SVG 或人工素材。
- 角色 pack 供应不足：先用占位 pack 和单张立绘完成 M1，不阻塞渲染链路。




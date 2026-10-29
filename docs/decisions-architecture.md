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

---

## ADR-007：源 TTS 用本地 IndexTTS2，放弃 RVC 变声链

### 背景

M4 需要中文吐字清晰、音量充足的配音。实测 MeloTTS + RVC v3 的方案在短句上音色相似，但长文本吐字明显变差；定位后确认瓶颈在 MeloTTS 源语音，而不是 RVC 变声。用户不使用付费云 TTS，要求本地方案。

### 决策

- 源 TTS 用 **IndexTTS2 zero-shot 声音克隆**，模型 `IndexTeam/IndexTTS-2`，参考音为用户提供的 20 句干净录音中的 4.94 秒片段。
- IndexTTS2 跑在独立 Python 3.11 + torch 2.8 cu128 环境，由 `scripts/runtime/indextts_server.py` 常驻 `127.0.0.1:8765`，模型只加载一次，逐句合成走 HTTP。
- 8GB 显存：fp16、关闭 QwenEmotion、Wav2Vec2-BERT 放 CPU 做一次性音色编码。
- 删除 RVC 变声层、MeloTTS/Piper 基础设施和训练模型；不再维护第二套音色转换链。

### 理由

1. 长文本实测 224 字 / 44.7 秒，RTF 1.75，用户试听确认清晰度和音量达标。
2. zero-shot 直接用参考音，省去 RVC 训练、F0、index 调参和金属音问题。
3. 本地常驻服务没有按量费用，也避免跨境网络依赖。

### 代价与风险

- 需要 NVIDIA GPU；无 GPU 的 VM 不能跑 TTS，媒体 worker 要与 GPU 机器绑定。
- 模型与辅助权重约 8.3GB，显存占用高，单卡并行度有限，media worker 的 TTS 并发需限制为 1。
- IndexTTS2 暂未暴露语速和情绪参数；需要变速时用 ffmpeg 后处理，情绪控制后续再接。
- 参考音决定音色与部分韵律，换参考音会影响全片一致性。

### 重新评估触发条件

- IndexTTS-2.5 或后续版本在同等显存下明显更好：升级模型版本。
- 参考音克隆稳定性不足：增加参考音或改用微调，而不是回到 RVC。
- 需要多 worker 并发生成：再评估 vLLM 服务化或第二张 GPU。

---

## ADR-008：字级对齐用中文 wav2vec2，不引入整套 WhisperX

### 背景

字幕需要字级时间戳（F-22/F-28），但 IndexTTS2 只给句级音频和时长。WhisperX 默认中文对齐模型是 `jonatasgrosman/wav2vec2-large-xlsr-53-chinese-zh-cn`，但安装 WhisperX 会带入 faster-whisper、pyannote 等一整套 ASR/说话人日志依赖；本项目已经知道每句的准确台词，不需要再跑 ASR。

### 决策

- 只使用 WhisperX 同款中文 wav2vec2 CTC 模型，做“已知文本 → 音频”的强制对齐。
- 在独立 Python 3.11 进程运行 `scripts/runtime/align_words.py`，用 `torchaudio.functional.forced_align` 求字符级路径；不安装 WhisperX 包。
- 数字/符号先用 IndexTTS2 的文本归一化器转成实际读法，再用 `difflib` 映射回原文字符，保证字幕文本不变。
- 字级时间写入 `episode.audio_meta.lines[].chars` 与 `alignment.json`；字幕块用字级起止时间显隐。

### 理由

1. 已知台词，强制对齐比 ASR + 对齐更直接、更可控，也不会因为识别错字导致时间偏移。
2. 复用 IndexTTS2 的 Python 环境和 torch，不新增第二套深度学习依赖。
3. 中文模型按字符对齐，正好匹配中文字幕；英文/数字按字符映射后再合并为字幕块。

### 代价与风险

- 模型约 1.2GB，每次对齐任务加载需要 20–30 秒；没有常驻服务。
- 数字、英文缩写依赖归一化映射；异常文本可能退化为句内均匀分布。
- 目前是“块级显隐”，不是逐字卡拉 OK 高亮；如需逐字高亮，渲染层要再消费 `chars`。
- 与常驻 IndexTTS2 同时占显存时可能 OOM，脚本会回退 CPU，速度明显变慢。

### 重新评估触发条件

- 字幕需要逐字高亮/卡拉 OK：扩展渲染模板消费 `chars`，而不是改对齐方案。
- 长文本对齐准确率不足：评估 MMS_FA 或微调中文对齐模型。
- 对齐耗时成为瓶颈：改为常驻对齐服务，或与 TTS 分卡运行。

---

## ADR-009：所有视觉质检统一用 `deepseek-flash` 多模态

### 背景

现有火山账号没有可用的视觉模型；用户明确要求视觉模型调用全部使用 `deepseek-flash`，包括生成图片资产检查和完整视频检查。实测 `deepseek-flash` 能读取单张图片，也能比较同一视频的两帧并输出结构化 JSON。

### 决策

- 视觉质检固定使用 `deepseek-flash` 多模态，不接入豆包 Vision / Qwen-VL / GLM-4V 等第二视觉模型。
- 图片资产：直接把 PNG/JPEG 传给 `deepseek-flash`，检查角色完整性、裁切、水印、文字伪影、背景与风格一致性。
- 完整视频：用 ffmpeg 按镜头抽首帧/中间帧（必要时补章节边界帧），把帧图 + 时长/帧率/分辨率/响度/字幕对齐作为文本上下文一起送模型，输出 `VideoVerdict`。
- DOM/几何、像素统计、ffmpeg 流检查仍作为确定性前置规则，不替代模型。

### 理由

1. 账号只有 `deepseek-flash`，统一模型可以避免再申请、部署或下载第二套视觉模型。
2. 实测能识别角色外观和字幕块变化，图片与多帧 JSON 质检都可用。
3. 模型同时承担文本脚本、分镜和视觉判定，provider/重试/成本日志可以复用同一套。

### 代价与风险

- 视频不是原生输入，必须抽帧；抽帧数量直接决定 token 成本和漏检率，需要在“每镜头首帧 + 中间帧”与章节边界帧之间做取舍。
- 高分辨率多帧会增加请求体积和延迟；发送前统一缩放到质检分辨率（建议长边 ≤1280），保留原始帧用于人工复核。
- 单次图片数量受 API 限制，长视频要分批检查，不能一次塞完整片。
- 模型可能对画面细节产生误判；低置信度必须转人工，不自动打回。

### 重新评估触发条件

- 抽帧质检漏检率过高：增加关键帧/章节帧或改用视频原生视觉模型。
- token 成本超过预算：降低帧分辨率或减少抽帧密度。
- `deepseek-flash` 视觉能力不足：再评估第二视觉模型，但需用户确认。

---

## ADR-010：资产复用先用 LLM 上下文 + `reuse_key`，暂不引入 RAG

### 背景

Asset Agent 需要根据文本复用已有演示素材。可选方案：把所有资产塞进 LLM 上下文让模型选；或建立向量库做语义检索（RAG）。当前 `asset` 表只有几十张图，已有 `reuse_key` 精确索引。

### 决策

- 现阶段不做 RAG/向量库。
- Asset Agent 把最近 80 个 APPROVED/CANDIDATE 资产的 `name/type/reuse_key/prompt` 作为上下文，由 DeepSeek 决定复用已有 `reuse_key` 还是新建。
- 复用命中后由数据库唯一索引保证不重复生成；语义不匹配才创建新 key。

### 理由

1. 资产量小，上下文足够覆盖；RAG 的召回和误复用成本反而更高。
2. `reuse_key` 是确定性的复用契约，比向量相似度更可控，也便于人工审核。
3. 不引入 embedding 模型、向量库和额外部署依赖。

### 代价与风险

- 资产超过上下文窗口或数量很大时，模型可能漏掉可复用项。
- 同义但不同 `reuse_key` 的资产可能重复生成，需要人工合并。
- 语义相似但视觉不合适的复用仍要靠资产检查和人工 approve。

### 重新评估触发条件

- APPROVED 资产超过约 100 个，或复用命中率明显下降：先加 SQLite FTS/Postgres 全文检索，再评估向量检索。
- 出现大量同义重复资产：引入规范化 key 或 embedding 去重。
- 需要跨系列检索大量素材：再评估独立向量库。




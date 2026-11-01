# 已完成里程碑归档

> 从 HANDOFF.md 拆出，按时间倒序；仅作历史参考，当前状态以 HANDOFF 为准。

### 2026-10-31 · 可取消 Remotion codegen

- 问题：点击「生成 Remotion 代码」后按钮禁用，没有取消入口。
- 新增 `POST /episodes/{id}/actions/cancel-remotion`：把 `remotion.codegen` 节点标为 `INTERRUPTED`、设置 `remotion_meta.cancel_requested=true`，恢复上一版 ready 状态；任务 watcher 每 3 秒检查一次，取消在途 LLM 调用并保留已生成的代码。
- 编辑器在 `remotion_meta.status=generating` 时显示「取消生成」。
- 后端 91 条测试通过，前端构建通过。

### 2026-10-31 · Remotion-only

- 用户要求新期只用 Remotion；新增 `REMOTION_ONLY=true`（默认），Playwright 仅保留测试/历史，不参与新期渲染。
- `start_render` / `rerender_episode` 在 renderer 不是 remotion 时直接拒绝；`render_shot_task` 渲染失败不再切 Playwright。
- 自动 codegen 失败或未全部 READY 时期次标记 FAILED，不再静默回退旧样式。
- `Character` 支持 `side="center"`，避免模型生成 `center` 时编译失败；生成服务仍会校验角色动效。
- 补充：`Character`/`PaperCard` 接受 `style` 透传；Remotion 归一化移除 `fps` 滤镜，改为 `-r 25`，保证每镜帧数与时间线一致（之前 130 镜少 130 帧、总时长少 5.2 秒）；QC 抽帧加 `-strict unofficial`，字幕块阈值 20→34，`renderer_version` 升到 `m6.2-frame-exact`。
- 后端 90 条测试通过，前端构建通过；130 镜头《Agent核心组成是什么》重跑后 QC `PASS`。

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

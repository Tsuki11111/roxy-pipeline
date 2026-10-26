# Roxy Pipeline

AI 科普视频自动生成 Agent 系统的架构与实现仓库。

当前状态：**架构设计阶段，代码尚未实现。**

## 目标

从选题到成片的全自动流水线：脚本生成、分镜、逐句 TTS、强制对齐、HTML 卡片渲染、逐帧渲染、ffmpeg 拼接、质检与局部重跑。

计划中的技术栈：Python 3.12 + FastAPI + PostgreSQL + RabbitMQ/Celery + MinIO + Playwright/Chromium + ffmpeg + LangGraph（AI 子图）。

## 文档

- [需求分析文档](docs/AI科普视频Agent系统需求分析文档.md)
- [架构选型方案](docs/AI科普视频Agent系统架构选型方案.md)
- [架构决策记录](docs/decisions-architecture.md)

## 计划里程碑

- M1：渲染链路打通（手写脚本 → 成片）
- M2：脚本 Agent（LangGraph）
- M3：分镜 Agent + 节奏规则 + AI 素材候选
- M4：质检与全流程自动化
- M5：局部修改、续跑、运维

## 说明

- 仓库不包含受版权保护的角色参考图或立绘；洛琪希资产包由使用者本地提供并遵守非商业同人约束。
- API Key 只放在本地 `.env`，已被 `.gitignore` 排除；仓库只提交 `.env.example`。
- 许可证待定（在选定前保留所有权利）。

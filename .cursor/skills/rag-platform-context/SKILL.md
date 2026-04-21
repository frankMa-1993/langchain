---
name: rag-platform-context
description: >-
  Loads RAG platform architecture, frozen stack, and run modes from
  rag-platform/README.md. Use when implementing or debugging rag-platform,
  changing API/worker/frontend/ingest/search, or when the user asks how the
  project is structured or how to run it.
---

# RAG Platform：架构与开发背景

## 何时应用

在涉及 `rag-platform/` 的**实现、排错、重构、依赖或运行方式**前，先对齐本文档与官方说明；不要把本技能当作唯一来源——**以仓库内 `rag-platform/README.md` 为准**（路径、脚本、环境变量以该文件与 `.env.example` 为准）。

工作区另有 `.cursor/rules/RAG.mdc`，内容与 README 高度一致；若规则已注入，仍建议在改代码前**打开或检索 README** 确认启动方式与前置条件。

## 必读

1. 阅读 [`rag-platform/README.md`](../../../rag-platform/README.md)（相对本文件：仓库根目录下的 `rag-platform/README.md`）。
2. 需要错误码契约时：[`rag-platform/app/core/errors.py`](../../../rag-platform/app/core/errors.py)。

## 项目是什么

- **定位**：基于 **LangChain + FastAPI** 的文档检索与问答；混合检索、SSE 流式、异步入库。
- **后端入口**：`rag-platform/app/main.py`（Uvicorn 挂载 `app.main:app`）。
- **前端**：`rag-platform/frontend/`（Node 20+，`npm run dev` 典型端口 5173）。
- **异步入库**：全栈模式下依赖 **ARQ Worker**（README 与脚本中的 `start-worker` / `arq app.workers.settings.WorkerSettings`）；上传文档通常需要 Worker 在跑。

## 两种运行心智模型（README 核心）

| 模式 | 特点 | 适用 |
|------|------|------|
| **稳定版 / 本地极简** | SQLite、`uploads/`、**BM25**、可不依赖外部 embedding；可选 `CHAT_*` 接入兼容 OpenAI 的聊天 API | 无 Docker、快速验证检索与对话 |
| **完整栈** | PostgreSQL、Redis、Qdrant；Docker 或云端连接串；Worker 处理入库 | 与「冻结栈」一致的生产形态能力 |

未配置 `CHAT_*` 时可能退化为「本地检索摘要」类行为，仍可检索与基础问答（见 README）。

## 冻结技术栈（决策表）

与 README「Stack decisions」一致，改架构前先确认是否破坏既定选型：

| 领域 | 选型 |
|------|------|
| 向量库 | Qdrant |
| 任务队列 | ARQ（Redis） |
| 元数据 / OLTP | PostgreSQL |
| 缓存 / 锁 / 限流 | Redis |
| 文件存储 | 本地 `uploads/`（生产可换 MinIO） |
| 鉴权 | 可选 `X-API-Key`（`API_KEY`） |
| 文档删除 | 硬删：PG、Qdrant、可选磁盘文件 |

## 执行任务时的检查清单

- [ ] 本次改动属于 API、Worker、检索、入库、前端还是部署？对应 README 哪一节？
- [ ] 用户环境是「仅 SQLite/BM25」还是「PG+Redis+Qdrant」？不要假设人人都有 Docker。
- [ ] 若动到上传/切片/索引：是否说明或测试 **Worker** 与队列依赖？
- [ ] API 响应是否仍符合 `errors.py` 的 `{ code, message, detail, request_id }` 约定？

## 与「写提交说明」技能的关系

若改动同时涉及 RAG 代码与 `.cursor/skills` / `.cursor/rules`，提交格式可参考项目内 [`commit-feature-rag-skills`](../commit-feature-rag-skills/SKILL.md)。

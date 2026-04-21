---
description: 
alwaysApply: true
---

# RAG Platform (LangChain + FastAPI)

Document retrieval and Q&A with hybrid search, SSE streaming, and async ingest.

## 当前推荐方案（稳定版）

默认推荐使用：

- 本地 `SQLite`
- 本地文件上传目录 `uploads/`
- 本地检索：`BM25` 关键词检索，**不依赖外部 embedding**
- 可选聊天模型：`DeepSeek` 等 OpenAI-compatible chat provider

这样即使没有 Docker、没有 OpenAI embedding、或者外部向量服务不可用，也能稳定完成：

- 新建知识库
- 上传文件并切片入库
- 检索文档
- 基础对话

### 推荐启动（Windows，无 Docker）

1. 复制环境变量：

```powershell
cd d:\workspace\NodeSpace\rag-platform
copy .env.example .env
```

2. 若要启用生成式聊天，填写 `.env`：

```env
CHAT_API_KEY=你的密钥
CHAT_BASE_URL=https://api.deepseek.com/v1
CHAT_MODEL=deepseek-chat
```

3. 安装并启动：

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
python -m uvicorn app.main:app --host 127.0.0.1 --port 8000
```

4. 打开：

- API Docs: `http://127.0.0.1:8000/docs`
- Frontend: `http://localhost:5173`

> 如果未配置 `CHAT_*`，系统会退回到“本地检索摘要模式”，仍可完成基础问答与文件检索。

## 最省事：把后端跑起来（Windows）

**推荐路径（本地一条线装依赖 + 一键脚本）：**

1. 安装 **Docker Desktop**（用系统包管理器一条命令即可，装好后一般需**重启**一次）：

```powershell
winget install -e --id Docker.DockerDesktop
```

2. 重启电脑 → 打开 **Docker Desktop**，等托盘图标显示已运行。

3. 复制环境变量并填写 `OPENAI_API_KEY`：

```powershell
cd d:\workspace\NodeSpace\rag-platform
copy .env.example .env
# 用编辑器打开 .env，改 OPENAI_API_KEY
```

4. **一键启动基础设施 + 安装依赖 + 启动 API**：

```powershell
Set-ExecutionPolicy -Scope CurrentUser RemoteSigned
.\scripts\start-backend.ps1
```

（若从未运行过本地脚本，先执行第一行一次即可。）

5. **再开一个终端**，启动入库 Worker（上传文档必须开着）：

```powershell
.\scripts\start-worker.ps1
```

6. 浏览器打开：**http://127.0.0.1:8000/docs**

> 若第 4 步提示「未检测到 Docker」，说明 Docker 未装好或未进 PATH，请先完成第 1～2 步并新开终端。

### 不想装 Docker：用云端数据库（零本地容器）

在 **Neon / Supabase** 建 PostgreSQL，在 **Upstash** 建 Redis，在 **Qdrant Cloud** 建免费集群，把连接串填进 `.env` 的 `DATABASE_URL`、`REDIS_URL`、`QDRANT_URL`（格式与 `.env.example` 一致）。然后**不要**执行 `docker compose`，直接：

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
python -m uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

另开终端执行 `.\scripts\start-worker.ps1`。  
（云端 Redis 若使用 `rediss://`，请确认 URL 与 ARQ 兼容。）

---

## Stack decisions (frozen)

| Item | Choice |
|---|-----|
| Vector DB | **Qdrant** |
| Task queue | **ARQ** (Redis) |
| Metadata / OLTP | **PostgreSQL** |
| Cache / locks / rate limit | **Redis** |
| File storage | Local `uploads/` (replace with MinIO in production) |
| Auth | Optional `X-API-Key` (set `API_KEY` env); omit for open demo |
| Document delete | **Hard delete**: PG rows, Qdrant points, optional file on disk |

## Prerequisites

- **Docker Desktop**（推荐）或云端 PG + Redis + Qdrant
- Python 3.11+（你当前若为 3.14，一般可用；若个别包装不上再换 3.11–3.12）
- Node.js 20+（仅前端）
- `OPENAI_API_KEY`（或兼容 OpenAI 的网关）

### If `docker` is not recognized

1. Install **Docker Desktop**: https://docs.docker.com/desktop/install/windows-install/  
2. Start Docker Desktop, **new terminal**, then `docker version`.

If you cannot use Docker, use **hosted** databases and set `.env` (`DATABASE_URL`, `REDIS_URL`, `QDRANT_URL`).

## Manual quick start (no script)

```powershell
cd rag-platform
copy .env.example .env
docker compose up -d
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
python -m uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
# other terminal:
arq app.workers.settings.WorkerSettings
```

Frontend:

```powershell
cd frontend
npm install
npm run dev
```

- API docs: http://localhost:8000/docs  
- OpenAPI JSON: http://localhost:8000/openapi.json  
- Metrics: http://localhost:8000/metrics  
- UI: http://localhost:5173  

## Error codes

See `app/core/errors.py` — responses use `{ "code", "message", "detail", "request_id" }`.

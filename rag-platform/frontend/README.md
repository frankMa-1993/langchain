# RAG 平台 · 前端

本目录是 RAG 知识库与对话平台的 Web 前端，与后端 `http://127.0.0.1:8000`（默认）通过 REST 与 SSE 流式接口协作。

## 技术栈

- **React 18** + **TypeScript**
- **Vite 6** 构建与开发服务器
- **Ant Design 5** 组件与布局
- **React Router 7** 单页路由

## 业务与页面

| 路由 | 页面 | 说明 |
|------|------|------|
| `/` | 知识库列表 | 分页展示知识库，支持新建；可跳转文档管理与对话 |
| `/kb/:kbId` | 文档管理 | 上传 PDF / Word / TXT / Markdown，查看解析与索引状态，支持重索引与删除 |
| `/chat` | 对话 | 选择知识库与会话，流式问答；可选「混合检索（语义 + BM25）」；URL 查询参数 `?kb=<id>` 可预选知识库 |

顶栏提供可选的 **X-API-Key**：保存后写入 `localStorage`，后续 `fetch` 会自动带上请求头，与后端鉴权策略一致。

## 目录结构

```
src/
  main.tsx          # 入口：StrictMode、Antd ConfigProvider、BrowserRouter
  App.tsx           # 顶栏布局、菜单、API Key、路由出口
  api.ts            # API 前缀、鉴权、JSON/上传封装、对话 SSE 流解析
  index.css         # 全局样式
  pages/
    KbListPage.tsx  # 知识库 CRUD 列表
    KbDocsPage.tsx  # 某知识库下的文档列表与上传
    ChatPage.tsx    # 会话列表、消息历史、流式发送与来源展示
vite.config.ts      # 开发代理：/api 等到后端
```

数据流概览：页面组件调用 `api.ts` 中的 `apiJson` / `apiUpload` / `streamChat`，统一走前缀 `/api/v1`；开发环境下由 Vite 将 `/api` 代理到后端，避免跨域。

## 本地开发

前置条件：后端已启动（默认 `8000` 端口），或自行修改 `vite.config.ts` 中的 `proxy.target`。

```bash
cd rag-platform/frontend
npm install
npm run dev
```

浏览器访问开发服务器默认地址（一般为 `http://localhost:5173`）。

## 构建与预览

```bash
npm run build    # tsc 检查 + Vite 生产构建，产物在 dist/
npm run preview  # 本地预览构建结果（仍可按需配置代理或同源部署）
```

生产部署时，需保证浏览器能访问到同源或可配置的 `/api/v1`（或由网关反代到后端），否则需调整 `api.ts` 中的 `API_BASE` 或构建时注入环境变量（当前为固定相对路径）。

## 与后端的约定要点

- JSON 接口：`/api/v1/...`，错误体解析为 `ApiError`（含 `message`、`status`、`request_id` 等）。
- 流式对话：`POST /api/v1/conversations/:id/chat/stream`，响应为 SSE 风格分块，`data: {JSON}` 行解析为 `sources` / `delta` / `done` / `error` 等事件。

更多接口细节见项目根目录或后端的 OpenAPI 文档。

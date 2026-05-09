/** 与后端约定的 REST 前缀；开发环境由 Vite 代理到后端 */
const API_BASE = "/api/v1";

export function getApiKey() {
  return localStorage.getItem("rag_api_key");
}

export function setApiKey(key) {
  if (key) localStorage.setItem("rag_api_key", key);
  else localStorage.removeItem("rag_api_key");
}

function headers(json = true) {
  const h = {};
  if (json) h["Content-Type"] = "application/json";
  const k = getApiKey();
  if (k) h["X-API-Key"] = k;
  return h;
}

export class ApiError extends Error {
  constructor(message, status, code, requestId, detail) {
    super(message);
    this.name = "ApiError";
    this.status = status;
    this.code = code;
    this.requestId = requestId;
    this.detail = detail;
  }
}

async function parseError(res) {
  let body = {};
  try {
    body = await res.json();
  } catch {
    /* ignore */
  }
  const message = body.message || res.statusText || "Request failed";
  return new ApiError(
    message,
    res.status,
    body.code,
    body.request_id || res.headers.get("X-Request-ID"),
    body.detail
  );
}

export async function apiJson(path, init) {
  const res = await fetch(`${API_BASE}${path}`, {
    ...init,
    headers: { ...headers(), ...init?.headers },
  });
  if (!res.ok) throw await parseError(res);
  if (res.status === 204) return undefined;
  return res.json();
}

export async function apiUpload(path, file) {
  const fd = new FormData();
  fd.append("file", file);
  const h = {};
  const k = getApiKey();
  if (k) h["X-API-Key"] = k;
  const res = await fetch(`${API_BASE}${path}`, { method: "POST", body: fd, headers: h });
  if (!res.ok) throw await parseError(res);
  return res.json();
}

/**
 * 对话流式接口：读取 SSE 风格响应，按 `data: {...}` 解析为事件回调。
 */
export async function streamChat(conversationId, content, hybrid, onEvent, signal) {
  const res = await fetch(`${API_BASE}/conversations/${conversationId}/chat/stream`, {
    method: "POST",
    headers: headers(),
    body: JSON.stringify({ content, hybrid }),
    signal,
  });
  if (!res.ok) throw await parseError(res);
  const reader = res.body?.getReader();
  if (!reader) throw new Error("No response body");
  const dec = new TextDecoder();
  let buf = "";
  while (true) {
    const { done, value } = await reader.read();
    if (done) break;
    buf += dec.decode(value, { stream: true });
    const parts = buf.split("\n\n");
    buf = parts.pop() || "";
    for (const block of parts) {
      const line = block.split("\n").find((l) => l.startsWith("data: "));
      if (!line) continue;
      const raw = line.slice(6).trim();
      if (!raw) continue;
      try {
        onEvent(JSON.parse(raw));
      } catch {
        /* skip malformed */
      }
    }
  }
}

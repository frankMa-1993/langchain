const API_BASE = "/api/v1";

export function getApiKey(): string | null {
  return localStorage.getItem("rag_api_key");
}

export function setApiKey(key: string | null) {
  if (key) localStorage.setItem("rag_api_key", key);
  else localStorage.removeItem("rag_api_key");
}

function headers(json = true): HeadersInit {
  const h: Record<string, string> = {};
  if (json) h["Content-Type"] = "application/json";
  const k = getApiKey();
  if (k) h["X-API-Key"] = k;
  return h;
}

export class ApiError extends Error {
  constructor(
    message: string,
    public status: number,
    public code?: string,
    public requestId?: string | null,
    public detail?: unknown
  ) {
    super(message);
    this.name = "ApiError";
  }
}

async function parseError(res: Response): Promise<ApiError> {
  let body: Record<string, unknown> = {};
  try {
    body = (await res.json()) as Record<string, unknown>;
  } catch {
    /* ignore */
  }
  const message = (body.message as string) || res.statusText || "Request failed";
  return new ApiError(
    message,
    res.status,
    body.code as string | undefined,
    (body.request_id as string) || res.headers.get("X-Request-ID"),
    body.detail
  );
}

export async function apiJson<T>(path: string, init?: RequestInit): Promise<T> {
  const res = await fetch(`${API_BASE}${path}`, {
    ...init,
    headers: { ...headers(), ...init?.headers },
  });
  if (!res.ok) throw await parseError(res);
  if (res.status === 204) return undefined as T;
  return res.json() as Promise<T>;
}

export async function apiUpload(
  path: string,
  file: File
): Promise<{ document_id: string; task_id: string }> {
  const fd = new FormData();
  fd.append("file", file);
  const h: Record<string, string> = {};
  const k = getApiKey();
  if (k) h["X-API-Key"] = k;
  const res = await fetch(`${API_BASE}${path}`, { method: "POST", body: fd, headers: h });
  if (!res.ok) throw await parseError(res);
  return res.json();
}

export type KB = { id: string; name: string; description: string | null; created_at: string };
export type Doc = {
  id: string;
  kb_id: string;
  filename: string;
  mime_type: string | null;
  status: string;
  error_message: string | null;
  char_count: number | null;
  created_at: string;
  updated_at: string;
};
export type Task = {
  id: string;
  document_id: string;
  status: string;
  error_message: string | null;
  created_at: string;
  updated_at: string;
};
export type Conversation = { id: string; kb_id: string; title: string | null; created_at: string };
export type Source = {
  chunk_id: string;
  document_id: string;
  filename: string;
  page: number | null;
  excerpt: string | null;
};

export type MessageOut = {
  id: string;
  conversation_id: string;
  role: string;
  content: string;
  sources: Source[] | null;
  created_at: string;
};
export type ChatEvent =
  | { type: "sources"; sources: Source[] }
  | { type: "delta"; delta: string }
  | { type: "done"; done: boolean }
  | { type: "error"; message: string };

export async function streamChat(
  conversationId: string,
  content: string,
  hybrid: boolean,
  onEvent: (e: ChatEvent) => void,
  signal?: AbortSignal
): Promise<void> {
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
        onEvent(JSON.parse(raw) as ChatEvent);
      } catch {
        /* skip malformed */
      }
    }
  }
}

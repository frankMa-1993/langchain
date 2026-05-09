# RAG 平台 — 前端专项面试题与参考答案

> **项目背景**：前端基于 React 18 + TypeScript + Vite + Ant Design 5，使用原生 `fetch` 实现 SSE 流式对话，纯 Hooks 状态管理（无 Redux），react-router-dom v7 路由。

---

## 面试说明

- **目标岗位**：前端工程师（React 方向）/ 全栈工程师
- **面试时长**：45–60 分钟
- **题目分级**：⭐ 初级 | ⭐⭐ 中级 | ⭐⭐⭐ 高级

---

## 一、React 生态与 Hooks 深度

### 题 1.1 ⭐⭐ ChatPage 中大量 useState 的维护困境

**问题**：
`ChatPage.tsx` 中同时维护了 `kbId`、`convId`、`msgs`、`streaming`、`hybrid`、`batchMode`、`selectedConvIds` 等 7 个以上的 `useState`。当功能继续扩展时，这种写法会遇到什么问题？你会如何重构？

**参考答案**：

**当前问题**：
1. **状态耦合难以追踪**：`convId` 变化需要联动清空 `msgs`，`kbId` 变化需要联动清空 `convId` 和 `msgs`，逻辑散落在多个 `useEffect` 中。
2. **批量更新陷阱**：`send()` 中 `setMsgs`、`setStreaming`、`setInput` 连续调用，React 18 会自动批处理，但在异步回调（如 SSE `onEvent`）中可能触发多次渲染。
3. **逻辑复用困难**：对话相关的 CRUD（创建/删除/加载会话）与批量删除逻辑混杂在同一个组件中。
4. **测试困难**：业务逻辑与 UI 渲染强耦合，无法单独测试状态流转。

**重构方案**：

**方案 A：useReducer + Context（推荐，适合当前规模）**

```typescript
// 将对话相关的状态收敛为一个状态机
type ChatAction =
  | { type: "SELECT_KB"; kbId: string }
  | { type: "SELECT_CONV"; convId: string }
  | { type: "APPEND_DELTA"; delta: string; sources?: Source[] }
  | { type: "FINISH_STREAM" }
  | { type: "NEW_CONV"; conv: Conversation }
  | { type: "DELETE_CONV"; id: string };

function chatReducer(state: ChatState, action: ChatAction): ChatState {
  switch (action.type) {
    case "SELECT_KB":
      return { ...state, kbId: action.kbId, convId: undefined, msgs: [] };
    case "APPEND_DELTA": {
      const msgs = [...state.msgs];
      const last = msgs[msgs.length - 1];
      if (last?.role === "assistant") {
        last.content += action.delta;
        last.sources = action.sources || last.sources;
      } else {
        msgs.push({ role: "assistant", content: action.delta, sources: action.sources });
      }
      return { ...state, msgs };
    }
    // ... 其他 case
  }
}
```

**方案 B：Zustand / Jotai（适合更复杂的跨组件共享）**
- 将 `kbId`、`convId`、`msgs` 提升为全局 Store，避免 props drilling。
- `ChatPage` 只负责渲染，`useChatStore()` 负责数据获取和状态流转。

**方案 C：自定义 Hooks 拆分（最小侵入）**

```typescript
// 不引入新库，将逻辑拆分为自定义 Hook
function useConversations(kbId: string | undefined) {
  const [convs, setConvs] = useState<Conversation[]>([]);
  const [batchMode, setBatchMode] = useState(false);
  // ... 加载、创建、删除、批量删除逻辑
  return { convs, batchMode, ... };
}

function useMessages(convId: string | undefined) {
  const [msgs, setMsgs] = useState<Msg[]>([]);
  const [streaming, setStreaming] = useState(false);
  // ... 发送、流式累积、停止逻辑
  return { msgs, streaming, send, stop };
}
```

**评分要点**：
- 能指出状态分散导致的联动 bug 风险 → 及格
- 能提出 useReducer 或自定义 Hooks 的具体拆分方案 → 良好
- 能分析 React 18 自动批处理的边界情况（异步回调中的多次 setState）→ 优秀

---

### 题 1.2 ⭐⭐⭐ useEffect 依赖数组的陷阱与性能优化

**问题**：
`KbDocsPage.tsx` 第 36–46 行有一个 `useEffect`：

```typescript
useEffect(() => {
  const t = setInterval(() => {
    if (docs.some((d) => d.status === "pending" || d.status === "processing")) void load();
  }, 3000);
  return () => clearInterval(t);
}, [docs, load]);
```

这段代码存在什么问题？如果 `load()` 内部有竞态条件（旧请求结果覆盖新请求），如何修复？

**参考答案**：

**问题 1：依赖数组导致定时器频繁重建**

- `load` 是用 `useCallback(..., [kbId])` 创建的，理论上引用稳定。
- 但 `docs` 是状态，每次 `load()` 执行后 `setDocs` 会更新 `docs`，导致 `useEffect` 重新执行，定时器被清除再重建。
- **后果**：定时器实际上每 3 秒就被重建一次，如果组件有其他状态更新，可能导致轮询间隔不稳定。

**修复**：将 `docs` 从依赖数组移除，改用 ref 获取最新状态：

```typescript
const docsRef = useRef(docs);
docsRef.current = docs;

useEffect(() => {
  const t = setInterval(() => {
    if (docsRef.current.some((d) => d.status === "pending" || d.status === "processing")) {
      void load();
    }
  }, 3000);
  return () => clearInterval(t);
}, [load]); // 移除 docs
```

**问题 2：竞态条件（Race Condition）**

场景：用户快速切换知识库，或定时器触发时上一次 `load()` 尚未返回。

```typescript
// 竞态示例：
// t=0: load() A 发出请求
// t=1: 用户切换 kbId → load() B 发出请求
// t=2: B 先返回 → setDocs(B结果)
// t=3: A 后返回 → setDocs(A结果) ❌ 覆盖了 B！
```

**修复：使用闭包版本号 / AbortController**

```typescript
const load = useCallback(async () => {
  if (!kbId) return;
  setLoading(true);
  try {
    const res = await apiJson<{ items: Doc[] }>(
      `/knowledge-bases/${kbId}/documents?page=1&page_size=100`
    );
    // 使用函数式更新，但更好的方式是检查 kbId 是否已变更
    setDocs((prev) => {
      // 如果当前 kbId 已不是请求时的 kbId，丢弃结果
      // 需要借助 ref 或其他机制
      return res.items;
    });
  } finally {
    setLoading(false);
  }
}, [kbId]);

// 更彻底的修复：使用一个递增的 requestId
const reqIdRef = useRef(0);
const load = useCallback(async () => {
  if (!kbId) return;
  const reqId = ++reqIdRef.current;
  setLoading(true);
  try {
    const res = await apiJson<...>(...);
    if (reqId === reqIdRef.current) {
      setDocs(res.items); // 只有最新请求的结果才被采纳
    }
  } finally {
    if (reqId === reqIdRef.current) setLoading(false);
  }
}, [kbId]);
```

**评分要点**：
- 能指出 `docs` 在依赖数组中导致定时器频繁重建 → 及格
- 能使用 ref 修复依赖问题，或提到竞态条件 → 良好
- 能给出 requestId 模式的完整竞态修复方案 → 优秀

---

### 题 1.3 ⭐⭐ 流式消息累积的性能问题

**问题**：
`ChatPage.tsx` 的 SSE 回调中，每收到一个 `delta` 就执行一次 `setMsgs`：

```typescript
setMsgs((m) => {
  const copy = [...m];
  const last = copy[copy.length - 1];
  if (last && last.role === "assistant") copy[copy.length - 1] = { ...last, content: acc, sources };
  else copy.push({ role: "assistant", content: acc, sources });
  return copy;
});
```

这段代码有什么问题？当流式回复很长（如 5000 字）时，性能瓶颈在哪里？

**参考答案**：

**问题 1：每次渲染都复制整个 messages 数组**

- `copy = [...m]` 是浅拷贝，对于 100 条消息的数组，每次 delta 都要复制 100 个引用。
- 更严重的是 `{ ...last, content: acc }`，这里 `content` 是长字符串，每次都在创建新的字符串对象。
- 当流式输出 5000 字，分 1000 个 delta 传输时：
  - 字符串总复制量 ≈ `1000 × (平均长度 2500)` ≈ **2.5MB 的字符串复制**
  - React 每次都要对比 100 条消息的前后的差异。

**问题 2：React 的渲染阻塞**

- 高频 `setState`（每秒 10–20 次）可能导致主线程阻塞，输入框卡顿。

**优化方案**：

**方案 A：节流 + 局部更新（最小改动）**

```typescript
// 使用 ref 累积，定时刷新到 state
const accRef = useRef("");
const sourcesRef = useRef<Source[] | undefined>(undefined);
const flushTimerRef = useRef<ReturnType<typeof setTimeout>>();

const flush = () => {
  setMsgs((m) => {
    const copy = [...m];
    const last = copy[copy.length - 1];
    if (last?.role === "assistant") {
      copy[copy.length - 1] = { ...last, content: accRef.current, sources: sourcesRef.current };
    } else {
      copy.push({ role: "assistant", content: accRef.current, sources: sourcesRef.current });
    }
    return copy;
  });
};

// 在 onEvent 中
if (ev.type === "delta") {
  accRef.current += ev.delta;
  // 节流：最多每 100ms 更新一次 UI
  if (!flushTimerRef.current) {
    flushTimerRef.current = setTimeout(() => {
      flush();
      flushTimerRef.current = undefined;
    }, 100);
  }
}
```

**方案 B：使用 useRef 完全脱离 React 状态（打字机效果）**

```typescript
// 只在最后一次性 setMsgs，中间用 DOM 操作更新
const contentRef = useRef<HTMLDivElement>(null);
const textRef = useRef("");

onEvent: (ev) => {
  if (ev.type === "delta") {
    textRef.current += ev.delta;
    if (contentRef.current) {
      contentRef.current.textContent = textRef.current; // 直接操作 DOM，不触发 React 渲染
    }
  }
}
```

**方案 C：使用虚拟列表（消息量极大时）**
- 当历史消息 > 1000 条时，使用 `react-window` 或 `@tanstack/react-virtual` 只渲染视口内的消息。

**评分要点**：
- 能指出数组浅拷贝和长字符串重复创建的问题 → 及格
- 能给出节流（throttle）或 requestAnimationFrame 的优化方案 → 良好
- 能提出 useRef + DOM 直接操作的极致性能方案，或虚拟列表 → 优秀

---

## 二、状态管理与组件设计

### 题 2.1 ⭐⭐ 为什么不使用 Redux / Zustand？

**问题**：
本项目完全使用 React 原生 Hooks 管理状态，没有引入任何全局状态管理库。请评价这个选择的合理性，并说明在什么规模下你会考虑引入 Redux / Zustand / Jotai。

**参考答案**：

**当前选择的合理性**：
1. **项目规模小**：只有 3 个页面，状态 mostly 集中在 `ChatPage` 内部，无深层 props drilling。
2. **状态类型简单**：多为 CRUD 列表 + 表单状态，无复杂的跨组件共享需求。
3. **减少依赖**：少一个库 = 少一份 bundle size（Zustand 1KB 虽小，Redux 工具链 ~20KB）和学习成本。
4. **服务端状态为主**：大部分状态来自 API（知识库列表、文档列表、消息列表），适合 React Query / SWR 而非 Redux。

**何时引入全局状态库**：

| 信号 | 说明 | 推荐方案 |
|------|------|----------|
| Props drilling > 3 层 | 子孙组件需要访问祖先状态 | Zustand / Jotai |
| 跨页面状态共享 | 如用户头像在顶栏和设置页同时编辑 | Zustand |
| 状态更新逻辑复杂 | 如 Undo/Redo、时间旅行调试 | Redux Toolkit |
| 派生状态多 | 多处使用 `useMemo` 计算过滤/排序 | Zustand + selector |
| 服务端状态复杂 | 缓存、重试、乐观更新、分页 | React Query |

**针对本项目的建议**：
- **暂不引入 Redux**：过重。
- **可考虑 Zustand**：当新增"用户系统"（登录态跨页面共享）或"多窗口对话"（同时打开多个 chat tab）时。
- **优先引入 React Query**：当前所有列表加载都是手动 `useEffect + fetch`，换成 React Query 可自动处理缓存、重试、去重、后台刷新。

**评分要点**：
- 能分析当前项目规模与状态复杂度 → 及格
- 能给出明确的引入阈值（如 drilling 层数、页面数）→ 良好
- 能区分服务端状态（React Query）和客户端状态（Zustand）的适用场景 → 优秀

---

### 题 2.2 ⭐⭐⭐ 组件拆分与职责边界

**问题**：
`ChatPage.tsx` 目前有 415 行，包含：知识库选择、会话列表管理（含批量删除）、消息展示、SSE 流式发送、混合检索开关。如果要求将其拆分为多个组件，你会如何划分？如何保证拆分后组件间的通信既简洁又类型安全？

**参考答案**：

**组件拆分方案**：

```
ChatPage/
├── ChatLayout.tsx          # 布局壳：左右分栏
├── KnowledgeBaseSelect.tsx # 知识库下拉选择
├── ConversationList.tsx    # 左侧会话列表 + 批量模式
├── ConversationItem.tsx    # 单条会话（复用）
├── MessageList.tsx         # 消息列表滚动区
├── MessageItem.tsx         # 单条消息（用户/助手）
├── SourcePanel.tsx         # 来源折叠面板
├── ChatInput.tsx           # 底部输入框 + 发送/停止
├── HybridToggle.tsx        # 混合检索开关
```

**通信设计**：

**方案 A：Props + Callback（适合当前规模）**

```typescript
// ChatPage 作为容器组件（Container），管理所有状态
// 子组件只接收 props 和 callback

interface ChatInputProps {
  disabled: boolean;
  loading: boolean;
  onSend: (text: string) => void;
  onStop: () => void;
}

interface MessageListProps {
  msgs: Msg[];
  streaming: boolean;
}
```

**方案 B：Composition 模式（更灵活）**

```tsx
<ChatLayout
  sidebar={<ConversationList {...convListProps} />}
  toolbar={<HybridToggle checked={hybrid} onChange={setHybrid} />}
  main={
    <>
      <MessageList msgs={msgs} />
      <ChatInput onSend={send} onStop={stop} />
    </>
  }
/>
```

**方案 C：Context + useReducer（避免 props drilling）**

```typescript
const ChatContext = createContext<{ state: ChatState; dispatch: Dispatch<ChatAction> } | null>(null);

// 深层组件直接消费
function MessageItem({ index }: { index: number }) {
  const { state } = useContext(ChatContext)!;
  const msg = state.msgs[index];
  // ...
}
```

**类型安全保证**：
1. 所有组件 Props 显式定义 TypeScript interface。
2. 使用 `React.FC<Props>` 或函数参数解构，开启 `strict` 模式。
3. Context 使用 `null` 初始值 + 自定义 Hook 抛错：

```typescript
function useChat() {
  const ctx = useContext(ChatContext);
  if (!ctx) throw new Error("useChat must be inside ChatProvider");
  return ctx;
}
```

**评分要点**：
- 能给出合理的组件拆分粒度 → 及格
- 能设计 Props 接口并说明容器/展示组件分离 → 良好
- 能结合 Context + useReducer 或 Composition 设计通信方案 → 优秀

---

## 三、网络与流式数据处理

### 题 3.1 ⭐⭐⭐ SSE 流式解析的健壮性

**问题**：
`api.ts` 中的 `streamChat` 手动解析 SSE 流：

```typescript
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
```

这段代码存在哪些边界 case 未处理？如何改进其健壮性？

**参考答案**：

**未处理的边界 case**：

| Case | 场景 | 当前行为 | 期望行为 |
|------|------|----------|----------|
| **SSE 注释行** | `data: {...}\n\n:heartbeat\n\n` | 可能解析错误 | 跳过以 `:` 开头的注释行 |
| **多行 data** | `data: 行1\ndata: 行2\n\n` | 只取一行 | 合并多行 data（标准 SSE） |
| **非 JSON data** | `data: [DONE]` | `JSON.parse` 抛错被吞 | 识别 `[DONE]` 等特殊标记 |
| **响应中断** | 网络断开 | 循环结束，无错误通知 | 应抛出 NetworkError |
| **HTTP 错误** | 500 Internal Server Error | `parseError` 处理 | 正确，但 SSE 的 500 可能返回 HTML |
| **reader.cancel** | 用户点击"停止" | `AbortError` 被 catch | 正确，但需确保 reader 释放 |

**改进后的实现**：

```typescript
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
  if (!res.body) throw new Error("No response body");

  const reader = res.body.getReader();
  const dec = new TextDecoder();
  let buf = "";

  try {
    while (true) {
      const { done, value } = await reader.read();
      if (done) break;
      buf += dec.decode(value, { stream: true });

      // 按 SSE 规范分割：两个换行符分隔事件
      const events = buf.split("\n\n");
      buf = events.pop() || "";

      for (const evt of events) {
        const lines = evt.split("\n");
        const dataLines: string[] = [];
        let eventName = "message";

        for (const line of lines) {
          if (line.startsWith("event: ")) {
            eventName = line.slice(7);
          } else if (line.startsWith("data: ")) {
            dataLines.push(line.slice(6));
          } else if (line.startsWith(":")) {
            // 跳过注释/heartbeat
            continue;
          } else if (line === "" || line === "\r") {
            continue;
          }
        }

        const raw = dataLines.join("\n");
        if (!raw) continue;

        // 处理特殊标记
        if (raw === "[DONE]") {
          onEvent({ type: "done", done: true });
          continue;
        }

        try {
          const payload = JSON.parse(raw);
          onEvent(payload as ChatEvent);
        } catch (err) {
          console.warn("Malformed SSE payload:", raw, err);
          // 可选择通知上层
          onEvent({ type: "error", message: `Parse error: ${raw.slice(0, 100)}` });
        }
      }
    }

    // 处理最后残留的 buffer（正常情况下应为空）
    if (buf.trim()) {
      console.warn("Trailing SSE buffer:", buf);
    }
  } finally {
    reader.releaseLock(); // 确保释放锁
  }
}
```

**进一步改进：封装为通用 Hook**

```typescript
function useSSE<T>(url: string, options?: RequestInit) {
  const [data, setData] = useState<T[]>([]);
  const [error, setError] = useState<Error | null>(null);
  const [connected, setConnected] = useState(false);
  const abortRef = useRef<AbortController | null>(null);

  const connect = useCallback((body: unknown) => {
    abortRef.current?.abort();
    abortRef.current = new AbortController();
    // ... 封装上述解析逻辑
  }, [url]);

  const disconnect = useCallback(() => {
    abortRef.current?.abort();
  }, []);

  return { data, error, connected, connect, disconnect };
}
```

**评分要点**：
- 能指出多行 data 和注释行未处理 → 及格
- 能给出完整的健壮性改进代码 → 良好
- 能封装为可复用的 `useSSE` Hook，并考虑 `releaseLock` 和 `finally` → 优秀

---

### 题 3.2 ⭐⭐ 请求取消与内存泄漏

**问题**：
`ChatPage.tsx` 中使用了 `AbortController` 来取消流式请求。请回答：
1. 如果用户在消息流式输出过程中快速切换会话（从 convA 切到 convB），当前代码是否会发生内存泄漏或竞态？
2. `KbDocsPage.tsx` 的 `useEffect` 轮询中，如果组件卸载时 `load()` 刚好返回并调用 `setDocs`，会发生什么？

**参考答案**：

**问题 1：快速切换会话的竞态**

当前代码：

```typescript
const send = async () => {
  // ...
  abortRef.current?.abort();
  abortRef.current = new AbortController();
  try {
    await streamChat(convId, text, hybrid, onEvent, abortRef.current.signal);
  } catch (e) {
    // ...
  } finally {
    setStreaming(false);
  }
};
```

**隐患**：
- 切换会话时，`convId` 变化触发 `useEffect` 加载新消息，但旧会话的 SSE 请求可能仍在 `finally` 中执行 `setStreaming(false)` 或 `setMsgs(...)`。
- 如果 `onEvent` 闭包中引用了旧的 `convId`，可能导致消息被错误地写入新会话。

**修复**：

```typescript
const send = async () => {
  // ...
  const currentConvId = convId; // 快照
  abortRef.current?.abort();
  abortRef.current = new AbortController();
  try {
    await streamChat(currentConvId!, text, hybrid, (ev) => {
      // 检查 convId 是否已变更
      if (convIdRef.current !== currentConvId) return;
      // ... 处理事件
    }, abortRef.current.signal);
  } finally {
    if (convIdRef.current === currentConvId) {
      setStreaming(false);
    }
  }
};
```

**问题 2：组件卸载后 setState**

React 18 严格模式下，组件卸载后调用 `setState` 会触发 warning（development mode）：

```
Warning: Can't perform a React state update on an unmounted component.
```

**修复**：使用 `useEffect` 的 cleanup + 标志位：

```typescript
const mountedRef = useRef(true);
useEffect(() => {
  mountedRef.current = true;
  return () => { mountedRef.current = false; };
}, []);

const load = useCallback(async () => {
  if (!kbId) return;
  setLoading(true);
  try {
    const res = await apiJson<{ items: Doc[] }>(...);
    if (mountedRef.current) setDocs(res.items);
  } finally {
    if (mountedRef.current) setLoading(false);
  }
}, [kbId]);
```

**更优雅的方式**：使用 `useIsMounted` Hook 或直接用 `AbortController` 取消未完成的请求。

**评分要点**：
- 能指出切换会话时的状态污染风险 → 及格
- 能给出 convId 快照或 ref 对比的修复 → 良好
- 能同时处理组件卸载后的 setState 警告和请求取消 → 优秀

---

## 四、TypeScript 工程化

### 题 4.1 ⭐⭐ 类型定义与 API 契约

**问题**：
`api.ts` 中手动定义了 `KB`、`Doc`、`Task` 等 TypeScript 类型。如果后端 API 发生变更（如新增字段、字段改名），前端如何及时发现？你会如何改进类型维护流程？

**参考答案**：

**当前问题**：
1. **类型与后端不同步**：手动维护类型，后端改了接口前端可能运行时才报错。
2. **无运行时校验**：`res.json()` 返回 `any`，即使后端多字段/少字段，TypeScript 编译也通不过（但实际运行可能 undefined）。

**改进方案**：

**方案 A：OpenAPI / Swagger 自动生成类型**

本项目后端使用 FastAPI，自带 `/openapi.json` 端点：

```bash
# 安装 openapi-typescript
npm install -D openapi-typescript

# 生成类型
npx openapi-typescript http://127.0.0.1:8000/openapi.json -o src/api-types.ts
```

生成的类型：

```typescript
// api-types.ts（自动生成）
export interface components {
  schemas: {
    KB: { id: string; name: string; description: string | null; ... };
    Doc: { ... };
  };
}
```

**CI 集成**：

```yaml
# .github/workflows/sync-types.yml
- name: Generate API Types
  run: |
    npx openapi-typescript http://backend/openapi.json -o src/api-types.ts
    git diff --exit-code src/api-types.ts || (echo "API types out of sync!" && exit 1)
```

**方案 B：Zod / Yup 运行时校验**

```typescript
import { z } from "zod";

const KBSchema = z.object({
  id: z.string(),
  name: z.string(),
  description: z.string().nullable(),
  created_at: z.string().datetime(),
});

export type KB = z.infer<typeof KBSchema>;

// API 返回时校验
const res = await apiJson<unknown>("/knowledge-bases");
const parsed = z.array(KBSchema).parse(res.items); // 运行时校验！
```

**方案 C：GraphQL / tRPC（架构层面）**
- 如果后端支持，直接用 tRPC 实现端到端类型安全，前端类型随后端自动推导。

**评分要点**：
- 能指出手动维护类型的同步风险 → 及格
- 能给出 OpenAPI 自动生成类型的方案 → 良好
- 能结合 Zod 运行时校验和 CI 门禁 → 优秀

---

### 题 4.2 ⭐⭐ 泛型工具与类型体操

**问题**：
`apiJson<T>` 使用了泛型：

```typescript
export async function apiJson<T>(path: string, init?: RequestInit): Promise<T> {
  const res = await fetch(...);
  return res.json() as Promise<T>;
}
```

这种方式的 `T` 完全是"盲猜"，没有任何约束。请设计一个更类型安全的 API 调用层，要求：
1. 每个 API endpoint 有对应的请求参数类型和响应类型。
2. 调用时如果参数类型不匹配，编译期报错。
3. 避免重复定义 endpoint 字符串。

**参考答案**：

**方案：Endpoint 映射表 + 条件类型**

```typescript
// api-endpoints.ts
interface EndpointMap {
  "/knowledge-bases": {
    GET: {
      params: { page?: number; page_size?: number };
      res: { items: KB[]; total: number };
    };
    POST: {
      body: { name: string; description?: string };
      res: KB;
    };
  };
  "/conversations/:id/chat/stream": {
    POST: {
      params: { id: string }; // URL 参数
      body: { content: string; hybrid: boolean };
      res: ReadableStream; // 流式
    };
  };
}

type Method = "GET" | "POST" | "DELETE" | "PATCH";

type ApiResponse<P extends keyof EndpointMap, M extends Method> =
  EndpointMap[P] extends Record<M, infer R> ? R : never;

// 类型安全的调用函数
async function apiCall<P extends keyof EndpointMap, M extends Method & keyof EndpointMap[P]>(
  path: P,
  method: M,
  ...args: ApiResponse<P, M> extends { body: infer B }
    ? [body: B]
    : ApiResponse<P, M> extends { params: infer P }
    ? [params: P]
    : []
): Promise<ApiResponse<P, M> extends { res: infer R } ? R : never> {
  // 实现...
}

// 使用
const list = await apiCall("/knowledge-bases", "GET", { page: 1 });
// list 自动推导为 { items: KB[]; total: number }

const created = await apiCall("/knowledge-bases", "POST", { name: "test" });
// 如果缺少 name，编译报错！
```

**更实用的简化版（基于对象映射）**：

```typescript
const api = {
  getKbs: (p: { page?: number }) =>
    apiJson<{ items: KB[]; total: number }>(`/knowledge-bases?page=${p.page ?? 1}`),
  createKb: (body: { name: string; description?: string }) =>
    apiJson<KB>("/knowledge-bases", { method: "POST", body: JSON.stringify(body) }),
} as const;

// 使用时直接 api.getKbs({ page: 1 })
```

**评分要点**：
- 能指出 `as Promise<T>` 的类型不安全 → 及格
- 能设计 endpoint 映射表或 api 对象封装 → 良好
- 能使用 TypeScript 条件类型实现编译期参数校验 → 优秀

---

## 五、工程构建与性能

### 题 5.1 ⭐⭐ Vite 构建优化与部署

**问题**：
当前 `vite.config.ts` 只有开发代理配置，没有任何生产构建优化。假设需要部署到生产环境，你会做哪些配置调整？如何优化首屏加载速度？

**参考答案**：

**生产配置调整**：

```typescript
import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";
import { visualizer } from "rollup-plugin-visualizer";

export default defineConfig(({ mode }) => ({
  plugins: [
    react(),
    mode === "analyze" && visualizer({ open: true }), // 分析包体积
  ],
  build: {
    target: "es2020", // 现代浏览器，减少 polyfill
    sourcemap: true,
    rollupOptions: {
      output: {
        manualChunks: {
          // Ant Design 单独拆包
          antd: ["antd"],
          // React 生态单独拆包（缓存友好）
          react: ["react", "react-dom", "react-router-dom"],
        },
      },
    },
    chunkSizeWarningLimit: 500,
  },
  server: {
    proxy: { /* 开发代理 */ },
  },
}));
```

**首屏优化**：

| 优化项 | 具体措施 | 预期收益 |
|--------|----------|----------|
| **路由懒加载** | `React.lazy(() => import('./pages/ChatPage'))` | 首屏 JS 减少 60%+ |
| **AntD 按需加载** | 已默认按需（Vite + esm），确认无全量引入 | 避免 500KB+ 冗余 |
| **Gzip/Brotli** | Nginx/CDN 开启压缩 | 传输体积减少 70% |
| **CDN 静态资源** | 构建产物上传到 OSS/S3 + CDN | 全球加速 |
| **预加载关键路由** | `<link rel="preload">` 首屏 JS/CSS | FCP 降低 200ms |

**当前代码问题**：
- `index.html` 没有 `<meta name="description">`，SEO 不友好。
- 无 PWA / Service Worker，弱网环境无法离线访问。
- 无生产环境 API Base URL 配置，部署后需要手动改代理或配 Nginx。

**评分要点**：
- 能给出 manualChunks 拆包或路由懒加载方案 → 及格
- 能分析首屏优化的多维度（构建/网络/渲染）→ 良好
- 能指出当前配置缺失（PWA/API Base/SEO）→ 优秀

---

### 题 5.2 ⭐⭐⭐ 前端可观测性与错误监控

**问题**：
当前前端没有任何错误监控和性能上报。如果生产环境用户反馈"对话页面卡死"或"消息不显示"，你如何在前端侧建立可观测性体系来定位问题？

**参考答案**：

**1. 错误监控**：

```typescript
// sentry.ts 或自研上报
window.addEventListener("error", (e) => {
  reportError({ type: "js-error", message: e.message, stack: e.error?.stack });
});

window.addEventListener("unhandledrejection", (e) => {
  reportError({ type: "promise-rejection", message: e.reason?.message });
});

// API 错误统一上报
class ApiError extends Error {
  // ...
  report() {
    reportError({
      type: "api-error",
      status: this.status,
      code: this.code,
      requestId: this.requestId,
      message: this.message,
    });
  }
}
```

**2. 性能监控（Web Vitals）**：

```typescript
import { onCLS, onFID, onFCP, onLCP, onTTFB } from "web-vitals";

onLCP((metric) => {
  reportMetric({ name: "LCP", value: metric.value, id: metric.id });
});

// 自定义业务指标
const reportChatLatency = (duration: number) => {
  reportMetric({ name: "chat_first_delta_latency", value: duration });
};
```

**3. 用户行为回放（Session Replay）**：
- 集成 Sentry Session Replay 或自研 RRWeb，复现"卡死"场景。
- 关键操作（发送消息、切换会话）打点，形成用户路径。

**4. SSE 专项监控**：

```typescript
// 在 streamChat 中埋点
const start = performance.now();
await streamChat(..., (ev) => {
  if (ev.type === "delta" && !firstDelta) {
    firstDelta = true;
    reportMetric({ name: "sse_first_byte", value: performance.now() - start });
  }
  if (ev.type === "done") {
    reportMetric({ name: "sse_total_duration", value: performance.now() - start });
  }
  if (ev.type === "error") {
    reportError({ type: "sse-error", message: ev.message });
  }
});
```

**5. 日志分级与采样**：
- **Error 级**：全量上报（但需限流，防止错误风暴）。
- **Warn 级**：采样 10%。
- **Info 级**：采样 1%，仅用于关键路径验证。

**评分要点**：
- 能设计全局 error/rejection 监听 → 及格
- 能结合 Web Vitals 和业务自定义指标 → 良好
- 能针对 SSE 流式设计专项监控（首字节延迟、流中断率）→ 优秀

---

## 六、用户体验与交互设计

### 题 6.1 ⭐⭐ 消息渲染与 XSS 防护

**问题**：
`ChatPage.tsx` 中消息内容直接渲染：

```tsx
<div style={{ whiteSpace: "pre-wrap", marginTop: 4 }}>{m.content}</div>
```

如果 LLM 返回的内容包含 HTML（如 `<script>alert(1)</script>`）或 Markdown 格式，当前处理是否安全？如何改进？

**参考答案**：

**安全风险**：
- **XSS**：虽然 React 的 `{}` 会自动转义 HTML 标签，`<script>` 不会执行，但如果未来改用 `dangerouslySetInnerHTML` 来渲染 Markdown，就会中招。
- **Markdown 未渲染**：LLM 经常返回 Markdown 格式（如 `**粗体**`、`[链接](url)`），当前显示为纯文本，可读性差。
- **代码块无高亮**：技术文档问答中代码块是高频内容，无高亮体验差。

**改进方案**：

**方案 A：安全渲染 Markdown**

```tsx
import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";
import { Prism as SyntaxHighlighter } from "react-syntax-highlighter";

<MessageItem>
  <ReactMarkdown
    remarkPlugins={[remarkGfm]}
    components={{
      code({ node, inline, className, children, ...props }) {
        const match = /language-(\w+)/.exec(className || "");
        return !inline && match ? (
          <SyntaxHighlighter language={match[1]} {...props}>
            {String(children).replace(/\n$/, "")}
          </SyntaxHighlighter>
        ) : (
          <code className={className} {...props}>{children}</code>
        );
      },
      a: ({ href, children }) => (
        <a href={href} target="_blank" rel="noopener noreferrer">{children}</a>
      ),
    }}
  >
    {m.content}
  </ReactMarkdown>
</MessageItem>
```

**方案 B：DOMPurify 净化（如果必须用 dangerouslySetInnerHTML）**

```tsx
import DOMPurify from "dompurify";

const safeHtml = DOMPurify.sanitize(rawHtml);
<div dangerouslySetInnerHTML={{ __html: safeHtml }} />
```

**方案 C：链接安全检测**
- Markdown 中的链接需要经过安全校验，禁止 `javascript:` 协议。
- 外部链接统一添加 `rel="noopener noreferrer"`。

**评分要点**：
- 能指出 React 默认转义的安全性，但 Markdown 渲染的潜在风险 → 及格
- 能给出 react-markdown + 自定义 code 组件的方案 → 良好
- 能同时考虑 DOMPurify、链接安全策略和代码高亮 → 优秀

---

### 题 6.2 ⭐⭐⭐ 长对话的无限滚动与历史加载

**问题**：
当前 `ChatPage` 一次性加载会话的全部历史消息（`page_size=200`）。如果用户有 10 万字的对话历史，会出现什么问题？如何设计无限滚动（Virtual Scrolling）+ 分页加载？

**参考答案**：

**问题分析**：
1. **DOM 节点爆炸**：200 条消息 × 复杂渲染 = 上千个 DOM 节点，滚动卡顿。
2. **内存占用**：所有消息内容常驻内存，长对话应用崩溃。
3. **首屏慢**：加载 200 条历史消息可能需要数秒。

**无限滚动 + 虚拟列表方案**：

**方案 A：反向无限滚动（聊天场景）**

```typescript
function MessageList({ convId }: { convId: string }) {
  const [msgs, setMsgs] = useState<Msg[]>([]);
  const [hasMore, setHasMore] = useState(true);
  const containerRef = useRef<HTMLDivElement>(null);
  const loadingRef = useRef(false);

  // 监听滚动到顶部，加载更早的消息
  const onScroll = useCallback(() => {
    const el = containerRef.current;
    if (!el || loadingRef.current || !hasMore) return;
    if (el.scrollTop < 100) {
      loadingRef.current = true;
      loadMore().finally(() => { loadingRef.current = false; });
    }
  }, [hasMore]);

  const loadMore = async () => {
    const oldestId = msgs[0]?.id;
    const res = await apiJson<{ items: MessageOut[] }>(
      `/conversations/${convId}/messages?before_id=${oldestId}&page_size=20`
    );
    setMsgs((prev) => [...res.items, ...prev]);
    setHasMore(res.items.length === 20);
  };

  return (
    <div ref={containerRef} onScroll={onScroll} style={{ overflow: "auto", height: "100%" }}>
      {hasMore && <div style={{ textAlign: "center" }}>加载中…</div>}
      {msgs.map((m) => <MessageItem key={m.id} msg={m} />)}
    </div>
  );
}
```

**方案 B：虚拟列表（只渲染视口内 + 缓冲）**

```tsx
import { useVirtualizer } from "@tanstack/react-virtual";

function VirtualMessageList({ msgs }: { msgs: Msg[] }) {
  const parentRef = useRef<HTMLDivElement>(null);
  const virtualizer = useVirtualizer({
    count: msgs.length,
    getScrollElement: () => parentRef.current,
    estimateSize: () => 80, // 预估每条消息高度
    overscan: 5, // 视口外多渲染 5 条
  });

  return (
    <div ref={parentRef} style={{ overflow: "auto", height: "100%" }}>
      <div style={{ height: virtualizer.getTotalSize() }}>
        {virtualizer.getVirtualItems().map((item) => (
          <div key={item.key} style={{ transform: `translateY(${item.start}px)` }}>
            <MessageItem msg={msgs[item.index]} />
          </div>
        ))}
      </div>
    </div>
  );
}
```

**方案 C：内容分页（按日期折叠）**
- 超过 7 天的历史消息默认折叠，点击展开。
- 减少一次性渲染量，同时保持时间线清晰。

**评分要点**：
- 能指出一次性加载大量消息的 DOM/内存问题 → 及格
- 能设计滚动监听 + 分页加载的加载更多机制 → 良好
- 能使用虚拟列表（react-window / tanstack-virtual）实现只渲染视口内内容 → 优秀

---

## 七、前端安全

### 题 7.1 ⭐⭐⭐ 前端安全全景

**问题**：
请从前端角度分析本项目的安全风险，包括但不限于：API Key 存储、XSS、CSRF、CSP，并给出修复方案。

**参考答案**：

**1. API Key 存储风险**

**当前实现**：`localStorage.setItem("rag_api_key", key)`

**风险**：
- XSS 攻击可读取 `localStorage` 中的 API Key。
- 浏览器扩展、恶意脚本可窃取 Key。

**修复**：
- **不再前端存储敏感 Key**：API Key 改为后端 session/cookie 鉴权，前端不接触 Key。
- **如果需要存储**：使用 `httpOnly; secure; sameSite=strict` Cookie，前端不可读取。
- **临时输入框**：像当前这样每次手动输入（不持久化）反而更安全，但体验差。

**2. XSS 风险**

- 当前 `m.content` 使用 React 默认转义，较为安全。
- 但如果未来支持 Markdown / HTML 渲染，需要 DOMPurify 净化（见题 6.1）。

**3. CSRF 风险**

- 当前使用 `fetch` 未携带任何 CSRF Token。
- 如果后端 cookie 鉴权，需要：
  - 后端设置 `SameSite=Lax/Strict`。
  - 或前端从 meta tag 读取 CSRF Token 并加入请求头。

**4. CSP（Content Security Policy）**

```html
<!-- index.html -->
<meta http-equiv="Content-Security-Policy" content="
  default-src 'self';
  script-src 'self';
  style-src 'self' 'unsafe-inline';
  connect-src 'self' https://api.your-domain.com;
  img-src 'self' data:;
">
```

**5. 其他安全风险**：

| 风险 | 说明 | 修复 |
|------|------|------|
| **点击劫持** | 页面被嵌入 iframe | `X-Frame-Options: DENY` |
| **敏感信息泄露** | 源码 map 暴露路径 | 生产环境不部署 `.map` |
| **开放重定向** | URL 参数跳转钓鱼 | 校验 `?redirect` 白名单 |
| **原型链污染** | `JSON.parse` 被利用 | 避免 `obj[key] = value` 无校验 |

**评分要点**：
- 能指出 localStorage 存储 API Key 的 XSS 风险 → 及格
- 能给出 httpOnly Cookie 或后端 session 的修复方案 → 良好
- 能全面覆盖 CSP、CSRF、点击劫持并给出配置代码 → 优秀

---

## 面试评分总表

| 考察维度 | 题号 | 初级目标 | 中级目标 | 高级目标 |
|----------|------|----------|----------|----------|
| React Hooks 深度 | 1.1–1.3 | 能指出 useState 分散问题 | 能修复竞态/节流 | 能设计 useReducer + ref 极致优化 |
| 状态管理 | 2.1–2.2 | 能评价 Redux 取舍 | 能拆分组件 | 能设计类型安全的通信方案 |
| 网络与流式 | 3.1–3.2 | 能指出 SSE 解析问题 | 能处理多行 data | 能封装 useSSE + 竞态修复 |
| TypeScript | 4.1–4.2 | 能指出类型不同步 | 能用 OpenAPI 生成 | 能用条件类型约束 endpoint |
| 工程构建 | 5.1–5.2 | 能列出构建优化项 | 能配 manualChunks | 能设计可观测性体系 |
| 用户体验 | 6.1–6.2 | 能指出 XSS 风险 | 能渲染 Markdown | 能设计虚拟列表 + 无限滚动 |
| 前端安全 | 7.1 | 能指出 API Key 风险 | 能用 httpOnly Cookie | 能设计 CSP + CSRF 全方案 |

**总体评级**：
- **通过（P）**：5 个维度以上达到中级目标。
- **良好（G）**：7 个维度均达到中级，且 3 个以上达到高级目标。
- **优秀（E）**：5 个以上维度达到高级目标，且能提出超越参考答案的见解。

---

> **使用建议**：
> 1. 初面前端（30 min）：从 ⭐⭐ 中选 4–5 题，重点考察 Hooks 和 TypeScript。
> 2. 终面前端（45 min）：从 ⭐⭐⭐ 中选 3–4 题，深入 SSE 健壮性、性能优化、安全方案。
> 3. 可结合实际代码追问：打开 `ChatPage.tsx` 让候选人现场 review 并指出 3 个以上可改进点。

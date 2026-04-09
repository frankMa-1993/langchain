import {
  Button,
  Card,
  Checkbox,
  Collapse,
  Empty,
  Input,
  List,
  Modal,
  Select,
  Space,
  Switch,
  Typography,
  message,
} from "antd";
import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { useSearchParams } from "react-router-dom";
import { ApiError, apiJson, streamChat, type Conversation, type KB, type MessageOut, type Source } from "../api";

/** 界面展示用的消息结构（含流式累积内容与引用来源） */
type Msg = { role: "user" | "assistant"; content: string; sources?: Source[] };

/** RAG 对话：选库、会话列表、历史消息、SSE 流式回复与混合检索开关 */
export default function ChatPage() {
  const [params] = useSearchParams();
  const kbFromUrl = params.get("kb");

  const [kbs, setKbs] = useState<KB[]>([]);
  const [kbId, setKbId] = useState<string | undefined>(kbFromUrl || undefined);
  const [convs, setConvs] = useState<Conversation[]>([]);
  const [convId, setConvId] = useState<string | undefined>();
  const [msgs, setMsgs] = useState<Msg[]>([]);
  const [input, setInput] = useState("");
  const [hybrid, setHybrid] = useState(true);
  const [streaming, setStreaming] = useState(false);
  const abortRef = useRef<AbortController | null>(null);

  // Batch delete states
  const [batchMode, setBatchMode] = useState(false);
  const [selectedConvIds, setSelectedConvIds] = useState<string[]>([]);

  const loadKbs = useCallback(async () => {
    try {
      const res = await apiJson<{ items: KB[] }>("/knowledge-bases?page=1&page_size=100");
      setKbs(res.items);
      setKbId((cur) => cur || res.items[0]?.id);
    } catch (e) {
      if (e instanceof ApiError) message.error(e.message);
    }
  }, []);

  const loadConvs = useCallback(async () => {
    if (!kbId) return;
    try {
      const res = await apiJson<{ items: Conversation[] }>(
        `/conversations?kb_id=${kbId}&page=1&page_size=50`
      );
      setConvs(res.items);
    } catch (e) {
      if (e instanceof ApiError) message.error(e.message);
    }
  }, [kbId]);

  const loadMsgs = useCallback(async (cid: string) => {
    try {
      const res = await apiJson<{ items: MessageOut[] }>(
        `/conversations/${cid}/messages?page=1&page_size=200`
      );
      const m: Msg[] = res.items.map((x) => ({
        role: x.role as "user" | "assistant",
        content: x.content,
        sources: x.sources || undefined,
      }));
      setMsgs(m);
    } catch (e) {
      if (e instanceof ApiError) message.error(e.message);
    }
  }, []);

  useEffect(() => {
    void loadKbs();
  }, [loadKbs]);

  useEffect(() => {
    void loadConvs();
  }, [loadConvs]);

  useEffect(() => {
    if (convId) void loadMsgs(convId);
    else setMsgs([]);
  }, [convId, loadMsgs]);

  useEffect(() => {
    if (kbFromUrl) setKbId(kbFromUrl);
  }, [kbFromUrl]);

  const newChat = async () => {
    if (!kbId) return;
    try {
      const c = await apiJson<Conversation>("/conversations", {
        method: "POST",
        body: JSON.stringify({ kb_id: kbId }),
      });
      setConvId(c.id);
      setMsgs([]);
      await loadConvs();
      message.success("新会话");
    } catch (e) {
      if (e instanceof ApiError) message.error(e.message);
    }
  };

  const removeConv = async (id: string) => {
    try {
      await apiJson(`/conversations/${id}`, { method: "DELETE" });
      message.success("会话已删除");
      if (convId === id) {
        setConvId(undefined);
        setMsgs([]);
      }
      await loadConvs();
    } catch (e) {
      if (e instanceof ApiError) message.error(e.message);
      else message.error("删除失败");
    }
  };

  const batchRemove = async () => {
    if (selectedConvIds.length === 0) return;
    Modal.confirm({
      title: "确认批量删除",
      content: `确定要删除选中的 ${selectedConvIds.length} 个会话吗？此操作无法恢复。`,
      okText: "删除",
      okButtonProps: { danger: true },
      cancelText: "取消",
      onOk: async () => {
        try {
          await apiJson("/conversations/batch-delete", {
            method: "POST",
            body: JSON.stringify({ ids: selectedConvIds }),
          });
          message.success(`已删除 ${selectedConvIds.length} 个会话`);
          if (convId && selectedConvIds.includes(convId)) {
            setConvId(undefined);
            setMsgs([]);
          }
          setSelectedConvIds([]);
          setBatchMode(false);
          await loadConvs();
        } catch (e) {
          if (e instanceof ApiError) message.error(e.message);
          else message.error("批量删除失败");
        }
      },
    });
  };

  const toggleConvSelection = (id: string) => {
    setSelectedConvIds((prev) =>
      prev.includes(id) ? prev.filter((x) => x !== id) : [...prev, id]
    );
  };

  const selectAllConvs = () => {
    setSelectedConvIds(convs.map((c) => c.id));
  };

  const clearSelection = () => {
    setSelectedConvIds([]);
  };

  const exitBatchMode = () => {
    setBatchMode(false);
    setSelectedConvIds([]);
  };

  const send = async () => {
    const text = input.trim();
    if (!text || !convId) {
      message.warning("请选择或创建会话");
      return;
    }
    setInput("");
    setMsgs((m) => [...m, { role: "user", content: text }]);
    setStreaming(true);
    abortRef.current?.abort();
    abortRef.current = new AbortController();
    let acc = "";
    let sources: Source[] | undefined;
    try {
      await streamChat(
        convId,
        text,
        hybrid,
        (ev) => {
          if (ev.type === "sources") sources = ev.sources;
          // 将增量文本拼到最后一条 assistant 消息上，实现打字机效果
          if (ev.type === "delta") {
            acc += ev.delta;
            setMsgs((m) => {
              const copy = [...m];
              const last = copy[copy.length - 1];
              if (last && last.role === "assistant") copy[copy.length - 1] = { ...last, content: acc, sources };
              else copy.push({ role: "assistant", content: acc, sources });
              return copy;
            });
          }
        },
        abortRef.current.signal
      );
      setMsgs((m) => {
        const copy = [...m];
        const last = copy[copy.length - 1];
        if (last && last.role === "assistant") copy[copy.length - 1] = { ...last, content: acc, sources };
        return copy;
      });
    } catch (e) {
      if (e instanceof ApiError) message.error(e.message);
      else if ((e as Error).name !== "AbortError") message.error("发送失败");
    } finally {
      setStreaming(false);
    }
  };

  const kbOptions = useMemo(() => kbs.map((k) => ({ label: k.name, value: k.id })), [kbs]);

  return (
    <div style={{ display: "flex", height: "100%", minHeight: 520 }}>
      <div style={{ width: 280, borderRight: "1px solid #f0f0f0", padding: 12, overflow: "auto", display: "flex", flexDirection: "column" }}>
        <Space direction="vertical" style={{ width: "100%" }} size="middle">
          <Typography.Text type="secondary">知识库</Typography.Text>
          <Select
            style={{ width: "100%" }}
            options={kbOptions}
            value={kbId}
            onChange={(v) => {
              setKbId(v);
              setConvId(undefined);
            }}
            placeholder="选择知识库"
          />
          <Button type="primary" block onClick={() => void newChat()} disabled={!kbId || batchMode}>
            新会话
          </Button>
          {!batchMode ? (
            <Button block onClick={() => setBatchMode(true)} disabled={!kbId || convs.length === 0}>
              批量管理
            </Button>
          ) : null}
          <Typography.Text type="secondary">历史会话</Typography.Text>
          <List
            size="small"
            dataSource={convs}
            locale={{ emptyText: "暂无" }}
            style={{ flex: 1, overflow: "auto" }}
            renderItem={(c) => (
              <List.Item
                style={{
                  cursor: batchMode ? "default" : "pointer",
                  background: convId === c.id ? "#e6f4ff" : undefined,
                  paddingLeft: batchMode ? 8 : 12,
                }}
                onClick={() => {
                  if (!batchMode) setConvId(c.id);
                }}
              >
                <Space style={{ width: "100%" }}>
                  {batchMode && (
                    <Checkbox
                      checked={selectedConvIds.includes(c.id)}
                      onChange={() => toggleConvSelection(c.id)}
                      onClick={(e) => e.stopPropagation()}
                    />
                  )}
                  <Typography.Text ellipsis title={c.title || c.id} style={{ flex: 1 }}>
                    {c.title || c.id.slice(0, 8)}
                  </Typography.Text>
                  {!batchMode && (
                    <Button
                      size="small"
                      danger
                      type="text"
                      onClick={(e) => {
                        e.stopPropagation();
                        Modal.confirm({
                          title: "确认删除",
                          content: `确定要删除会话 "${c.title || c.id.slice(0, 8)}" 吗？`,
                          okText: "删除",
                          okButtonProps: { danger: true },
                          cancelText: "取消",
                          onOk: () => removeConv(c.id),
                        });
                      }}
                    >
                      删除
                    </Button>
                  )}
                </Space>
              </List.Item>
            )}
          />
        </Space>
        {batchMode && (
          <div style={{ marginTop: 12, paddingTop: 12, borderTop: "1px solid #f0f0f0" }}>
            <Space direction="vertical" style={{ width: "100%" }}>
              <Space>
                <Checkbox
                  indeterminate={selectedConvIds.length > 0 && selectedConvIds.length < convs.length}
                  checked={selectedConvIds.length === convs.length && convs.length > 0}
                  onChange={(e) => (e.target.checked ? selectAllConvs() : clearSelection())}
                >
                  全选 ({selectedConvIds.length}/{convs.length})
                </Checkbox>
              </Space>
              <Space style={{ width: "100%", justifyContent: "space-between" }}>
                <Button size="small" onClick={exitBatchMode}>
                  取消
                </Button>
                <Button
                  size="small"
                  danger
                  type="primary"
                  disabled={selectedConvIds.length === 0}
                  onClick={() => batchRemove()}
                >
                  删除选中
                </Button>
              </Space>
            </Space>
          </div>
        )}
      </div>
      <div style={{ flex: 1, display: "flex", flexDirection: "column", padding: 16 }}>
        <Card size="small" style={{ marginBottom: 12 }}>
          <Space wrap>
            <span>混合检索（语义+BM25）</span>
            <Switch checked={hybrid} onChange={setHybrid} />
          </Space>
        </Card>
        <div style={{ flex: 1, overflow: "auto", marginBottom: 12 }}>
          {!convId ? (
            <Empty description="创建或选择一个会话" />
          ) : (
            msgs.map((m, i) => (
              <div key={i} style={{ marginBottom: 16 }}>
                <Typography.Text strong>{m.role === "user" ? "你" : "助手"}</Typography.Text>
                <div style={{ whiteSpace: "pre-wrap", marginTop: 4 }}>{m.content}</div>
                {m.role === "assistant" && m.sources && m.sources.length > 0 && (
                  <Collapse
                    size="small"
                    style={{ marginTop: 8 }}
                    items={[
                      {
                        key: "src",
                        label: `来源 (${m.sources.length})`,
                        children: (
                          <ul style={{ paddingLeft: 16, margin: 0 }}>
                            {m.sources.map((s) => (
                              <li key={s.chunk_id}>
                                <Typography.Text type="secondary">
                                  {s.filename}
                                  {s.page != null ? ` · p.${s.page}` : ""}
                                </Typography.Text>
                                <div>{s.excerpt}</div>
                              </li>
                            ))}
                          </ul>
                        ),
                      },
                    ]}
                  />
                )}
              </div>
            ))
          )}
        </div>
        <Space.Compact style={{ width: "100%" }}>
          <Input.TextArea
            rows={2}
            value={input}
            onChange={(e) => setInput(e.target.value)}
            placeholder="输入问题…"
            disabled={streaming || !convId}
            onPressEnter={(e) => {
              if (!e.shiftKey) {
                e.preventDefault();
                void send();
              }
            }}
          />
          <Button type="primary" loading={streaming} onClick={() => void send()} disabled={!convId}>
            发送
          </Button>
          {streaming && (
            <Button
              danger
              onClick={() => {
                abortRef.current?.abort();
              }}
            >
              停止
            </Button>
          )}
        </Space.Compact>
      </div>
    </div>
  );
}

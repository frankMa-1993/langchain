import {
  Button,
  Card,
  Space,
  Table,
  Typography,
  Upload,
  message,
  Popconfirm,
  Tag,
} from "antd";
import { useEffect, useState, useCallback } from "react";
import { Link, useParams } from "react-router-dom";
import { ApiError, apiJson, apiUpload, type Doc, type Task } from "../api";

/** 指定知识库下的文档：上传、列表轮询处理中状态、删除与重索引 */
export default function KbDocsPage() {
  const { kbId } = useParams();
  const [docs, setDocs] = useState<Doc[]>([]);
  const [loading, setLoading] = useState(false);

  const load = useCallback(async () => {
    if (!kbId) return;
    setLoading(true);
    try {
      const res = await apiJson<{ items: Doc[] }>(`/knowledge-bases/${kbId}/documents?page=1&page_size=100`);
      setDocs(res.items);
    } catch (e) {
      if (e instanceof ApiError) message.error(e.message);
      else message.error("加载失败");
    } finally {
      setLoading(false);
    }
  }, [kbId]);

  useEffect(() => {
    void load();
  }, [load]);

  // 存在处理中文档时定时刷新列表，直到状态变为终态
  useEffect(() => {
    const t = setInterval(() => {
      if (docs.some((d) => d.status === "pending" || d.status === "processing")) void load();
    }, 3000);
    return () => clearInterval(t);
  }, [docs, load]);

  const pollTask = async (taskId: string) => {
    try {
      const t = await apiJson<Task>(`/tasks/${taskId}`);
      if (t.status === "failed") message.error(t.error_message || "入库失败");
    } catch {
      /* ignore */
    }
  };

  const uploadProps = {
    showUploadList: false,
    beforeUpload: async (file: File) => {
      if (!kbId) return false;
      try {
        const res = await apiUpload(`/knowledge-bases/${kbId}/documents`, file);
        message.success("已上传，处理中…");
        void pollTask(res.task_id);
        await load();
      } catch (e) {
        if (e instanceof ApiError) message.error(e.message);
        else message.error("上传失败");
      }
      return false;
    },
  };

  const remove = async (id: string) => {
    try {
      await apiJson(`/documents/${id}`, { method: "DELETE" });
      message.success("已删除");
      await load();
    } catch (e) {
      if (e instanceof ApiError) message.error(e.message);
    }
  };

  const reindex = async (id: string) => {
    try {
      await apiJson(`/documents/${id}/reindex`, { method: "POST" });
      message.success("已加入重索引队列");
      await load();
    } catch (e) {
      if (e instanceof ApiError) message.error(e.message);
    }
  };

  return (
    <div style={{ padding: 24, maxWidth: 1100, margin: "0 auto" }}>
      <Space style={{ marginBottom: 16 }}>
        <Link to="/">← 返回</Link>
        <Typography.Title level={3} style={{ margin: 0 }}>
          文档管理
        </Typography.Title>
        {kbId && (
          <Link to={`/chat?kb=${kbId}`}>
            <Button type="link">去对话</Button>
          </Link>
        )}
      </Space>
      <Card>
        <Space style={{ marginBottom: 16 }}>
          <Upload {...uploadProps}>
            <Button type="primary">上传 PDF / Word / TXT / Markdown</Button>
          </Upload>
        </Space>
        <Table
          rowKey="id"
          loading={loading}
          dataSource={docs}
          columns={[
            { title: "文件名", dataIndex: "filename" },
            {
              title: "状态",
              dataIndex: "status",
              render: (s: string) => {
                const color = s === "ready" ? "green" : s === "failed" ? "red" : "blue";
                return <Tag color={color}>{s}</Tag>;
              },
            },
            { title: "字符数", dataIndex: "char_count" },
            {
              title: "错误",
              dataIndex: "error_message",
              ellipsis: true,
              render: (t: string | null) => t || "—",
            },
            {
              title: "操作",
              key: "a",
              render: (_, r) => (
                <Space>
                  <Button size="small" onClick={() => void reindex(r.id)}>
                    重索引
                  </Button>
                  <Popconfirm title="确定删除？" onConfirm={() => void remove(r.id)}>
                    <Button size="small" danger>
                      删除
                    </Button>
                  </Popconfirm>
                </Space>
              ),
            },
          ]}
        />
      </Card>
    </div>
  );
}

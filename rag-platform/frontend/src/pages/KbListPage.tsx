import { Button, Card, Form, Input, Modal, Space, Table, Typography, message } from "antd";
import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { ApiError, apiJson, type KB } from "../api";

export default function KbListPage() {
  const [rows, setRows] = useState<KB[]>([]);
  const [total, setTotal] = useState(0);
  const [loading, setLoading] = useState(false);
  const [open, setOpen] = useState(false);
  const [form] = Form.useForm();

  const load = async () => {
    setLoading(true);
    try {
      const res = await apiJson<{ items: KB[]; total: number }>("/knowledge-bases?page=1&page_size=50");
      setRows(res.items);
      setTotal(res.total);
    } catch (e) {
      if (e instanceof ApiError) message.error(`${e.message}${e.requestId ? ` (${e.requestId})` : ""}`);
      else message.error("加载失败");
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    void load();
  }, []);

  const create = async () => {
    const v = await form.validateFields();
    try {
      await apiJson("/knowledge-bases", { method: "POST", body: JSON.stringify(v) });
      message.success("已创建");
      setOpen(false);
      form.resetFields();
      await load();
    } catch (e) {
      if (e instanceof ApiError) message.error(e.message);
      else message.error("创建失败");
    }
  };

  return (
    <div style={{ padding: 24, maxWidth: 1100, margin: "0 auto" }}>
      <Space style={{ marginBottom: 16, width: "100%", justifyContent: "space-between" }}>
        <Typography.Title level={3} style={{ margin: 0 }}>
          知识库
        </Typography.Title>
        <Button type="primary" onClick={() => setOpen(true)}>
          新建知识库
        </Button>
      </Space>
      <Card>
        <Table
          rowKey="id"
          loading={loading}
          dataSource={rows}
          pagination={{ total, pageSize: 50, showSizeChanger: false }}
          columns={[
            { title: "名称", dataIndex: "name" },
            { title: "描述", dataIndex: "description", ellipsis: true },
            {
              title: "操作",
              key: "a",
              render: (_, r) => (
                <Space>
                  <Link to={`/kb/${r.id}`}>文档</Link>
                  <Link to={`/chat?kb=${r.id}`}>对话</Link>
                </Space>
              ),
            },
          ]}
        />
      </Card>
      <Modal title="新建知识库" open={open} onOk={create} onCancel={() => setOpen(false)} destroyOnClose>
        <Form form={form} layout="vertical">
          <Form.Item name="name" label="名称" rules={[{ required: true }]}>
            <Input />
          </Form.Item>
          <Form.Item name="description" label="描述">
            <Input.TextArea rows={3} />
          </Form.Item>
        </Form>
      </Modal>
    </div>
  );
}

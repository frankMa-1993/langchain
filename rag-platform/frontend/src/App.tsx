import { Layout, Menu, Typography, Input, Space, Button } from "antd";
import { Link, Navigate, Route, Routes, useLocation } from "react-router-dom";
import { useState } from "react";
import KbListPage from "./pages/KbListPage";
import KbDocsPage from "./pages/KbDocsPage";
import ChatPage from "./pages/ChatPage";
import { getApiKey, setApiKey } from "./api";

const { Header, Content } = Layout;

/** 顶栏主导航：根据路径高亮「知识库」或「对话」 */
function AppMenu() {
  const loc = useLocation();
  const selected = loc.pathname.startsWith("/chat") ? ["chat"] : ["home"];
  return (
    <Menu
      theme="dark"
      mode="horizontal"
      selectedKeys={selected}
      items={[
        { key: "home", label: <Link to="/">知识库</Link> },
        { key: "chat", label: <Link to="/chat">对话</Link> },
      ]}
      style={{ flex: 1, minWidth: 0 }}
    />
  );
}

/** 应用壳：布局、API Key、页面路由 */
export default function App() {
  const [keyInput, setKeyInput] = useState(getApiKey() || "");

  return (
    <Layout style={{ minHeight: "100%" }}>
      <Header style={{ display: "flex", alignItems: "center", gap: 16, paddingInline: 16 }}>
        <Typography.Text style={{ color: "#fff", fontWeight: 600, whiteSpace: "nowrap" }}>
          RAG 平台
        </Typography.Text>
        <AppMenu />
        <Space.Compact style={{ maxWidth: 280 }}>
          <Input.Password
            placeholder="X-API-Key（可选）"
            value={keyInput}
            onChange={(e) => setKeyInput(e.target.value)}
            visibilityToggle
          />
          <Button
            type="primary"
            onClick={() => {
              setApiKey(keyInput.trim() || null);
              setKeyInput(getApiKey() || "");
            }}
          >
            保存
          </Button>
        </Space.Compact>
      </Header>
      <Content style={{ background: "#f5f5f5" }}>
        <Routes>
          <Route path="/" element={<KbListPage />} />
          <Route path="/kb/:kbId" element={<KbDocsPage />} />
          <Route
            path="/chat"
            element={
              <div style={{ background: "#fff", minHeight: "calc(100vh - 64px)" }}>
                <ChatPage />
              </div>
            }
          />
          <Route path="*" element={<Navigate to="/" replace />} />
        </Routes>
      </Content>
    </Layout>
  );
}

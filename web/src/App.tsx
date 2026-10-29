import { useMemo, useState } from "react";
import { Layout, Menu, Typography } from "antd";
import {
  AppstoreOutlined,
  DashboardOutlined,
  PictureOutlined,
} from "@ant-design/icons";
import { Link, Route, Routes, useLocation, useNavigate } from "react-router-dom";
import DashboardPage from "./pages/DashboardPage";
import EpisodesPage from "./pages/EpisodesPage";
import EpisodeDetailPage from "./pages/EpisodeDetailPage";
import AssetsPage from "./pages/AssetsPage";

const { Header, Sider, Content } = Layout;

export default function App() {
  const location = useLocation();
  const navigate = useNavigate();
  const [collapsed, setCollapsed] = useState(false);

  const selected = useMemo(() => {
    if (location.pathname.startsWith("/assets")) return "assets";
    if (location.pathname.startsWith("/episodes")) return "episodes";
    return "dashboard";
  }, [location.pathname]);

  return (
    <Layout className="app-shell">
      <Sider
        collapsible
        collapsed={collapsed}
        onCollapse={setCollapsed}
        width={220}
        className="app-sider"
      >
        <Link to="/" className="brand">
          <span className="brand-mark">R</span>
          {!collapsed && (
            <span className="brand-text">
              Roxy
              <small>Pipeline</small>
            </span>
          )}
        </Link>
        <Menu
          mode="inline"
          selectedKeys={[selected]}
          onClick={(item) => {
            if (item.key === "dashboard") navigate("/");
            if (item.key === "episodes") navigate("/episodes");
            if (item.key === "assets") navigate("/assets");
          }}
          items={[
            { key: "dashboard", icon: <DashboardOutlined />, label: "总览" },
            { key: "episodes", icon: <AppstoreOutlined />, label: "视频期" },
            { key: "assets", icon: <PictureOutlined />, label: "资产库" },
          ]}
          className="app-menu"
        />
      </Sider>
      <Layout>
        <Header className="app-header">
          <Typography.Text className="header-kicker">
            AI 科普视频流水线
          </Typography.Text>
          <Typography.Title level={4} className="header-title">
            脚本 · 分镜 · 配音 · 渲染 · 质检
          </Typography.Title>
        </Header>
        <Content className="app-content">
          <Routes>
            <Route path="/" element={<DashboardPage />} />
            <Route path="/episodes" element={<EpisodesPage />} />
            <Route path="/episodes/:id" element={<EpisodeDetailPage />} />
            <Route path="/assets" element={<AssetsPage />} />
          </Routes>
        </Content>
      </Layout>
    </Layout>
  );
}

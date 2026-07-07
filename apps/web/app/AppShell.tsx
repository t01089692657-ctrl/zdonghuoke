"use client";

/** 应用外壳：左侧导航 + 顶栏。所有页面渲染在内容区。 */
import {
  DashboardOutlined,
  InboxOutlined,
  SafetyCertificateOutlined,
  SendOutlined,
  TeamOutlined,
} from "@ant-design/icons";
import { Layout, Menu, Typography } from "antd";
import { usePathname, useRouter } from "next/navigation";
import { useMemo, useState, type ReactNode } from "react";
import { API_BASE_URL } from "@/lib/api";

const { Header, Sider, Content } = Layout;

const NAV_ITEMS = [
  { key: "/", icon: <DashboardOutlined />, label: "仪表盘" },
  { key: "/leads", icon: <TeamOutlined />, label: "找客户 / 线索" },
  { key: "/campaigns", icon: <SendOutlined />, label: "营销活动" },
  { key: "/inbox", icon: <InboxOutlined />, label: "统一收件箱" },
  { key: "/review", icon: <SafetyCertificateOutlined />, label: "人审队列" },
];

export default function AppShell({ children }: { children: ReactNode }) {
  const router = useRouter();
  const pathname = usePathname() || "/";
  const [collapsed, setCollapsed] = useState(false);

  // 选中项：取匹配前缀最长的导航（保证 /leads/[id] 也高亮「找客户」）
  const selectedKey = useMemo(() => {
    const matches = NAV_ITEMS.map((it) => it.key)
      .filter((key) => (key === "/" ? pathname === "/" : pathname.startsWith(key)))
      .sort((a, b) => b.length - a.length);
    return matches[0] ?? "/";
  }, [pathname]);

  return (
    <Layout style={{ minHeight: "100vh" }}>
      <Sider
        collapsible
        collapsed={collapsed}
        onCollapse={setCollapsed}
        theme="dark"
        width={220}
      >
        <div className="zdhk-logo">
          <span className="dot" />
          {!collapsed && <span>ZDHK 客户工作台</span>}
        </div>
        <Menu
          theme="dark"
          mode="inline"
          selectedKeys={[selectedKey]}
          items={NAV_ITEMS}
          onClick={({ key }) => router.push(key)}
        />
      </Sider>
      <Layout>
        <Header
          style={{
            background: "#fff",
            padding: "0 24px",
            display: "flex",
            alignItems: "center",
            justifyContent: "space-between",
            borderBottom: "1px solid #f0f0f0",
          }}
        >
          <Typography.Text strong style={{ fontSize: 16 }}>
            自动获客系统 · 客户工作台
          </Typography.Text>
          <Typography.Text type="secondary" className="zdhk-mono">
            API: {API_BASE_URL}
          </Typography.Text>
        </Header>
        <Content className="zdhk-content">{children}</Content>
      </Layout>
    </Layout>
  );
}

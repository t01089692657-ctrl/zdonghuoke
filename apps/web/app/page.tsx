"use client";

/** 仪表盘：健康状态 + 概览卡片（线索数、可发送联系人、活动数等）+ 线索阶段分布。 */
import {
  ApiOutlined,
  ContactsOutlined,
  MailOutlined,
  SendOutlined,
  TeamOutlined,
} from "@ant-design/icons";
import { useQuery } from "@tanstack/react-query";
import {
  Card,
  Col,
  Progress,
  Row,
  Space,
  Spin,
  Statistic,
  Tag,
  Typography,
} from "antd";
import DegradedNotice from "@/components/DegradedNotice";
import PageHeader from "@/components/PageHeader";
import { api, type AnalyticsSummary } from "@/lib/api";
import { labelOf, leadStageColors, leadStageLabels } from "@/lib/labels";

function HealthCard() {
  const { data, isLoading, error } = useQuery({
    queryKey: ["health"],
    queryFn: api.health,
  });

  return (
    <Card title="后端健康状态" size="small">
      {isLoading && <Spin />}
      {error && <DegradedNotice error={error} endpoint="/health" />}
      {data && (
        <Space direction="vertical" size={4}>
          <Space>
            <Tag color={data.status === "ok" ? "green" : "red"}>
              {data.status === "ok" ? "正常" : data.status}
            </Tag>
            <Typography.Text type="secondary">v{data.version}</Typography.Text>
          </Space>
          <Typography.Text type="secondary">
            环境：{data.env} · 适配器模式：{data.adapter_mode}
          </Typography.Text>
        </Space>
      )}
    </Card>
  );
}

function StageDistribution({ summary }: { summary?: AnalyticsSummary }) {
  const stages = summary?.stages ?? [];
  const max = Math.max(1, ...stages.map((s) => s.count));
  return (
    <Card title="线索阶段分布" size="small">
      {stages.length === 0 ? (
        <Typography.Text type="secondary">暂无数据</Typography.Text>
      ) : (
        <Space direction="vertical" style={{ width: "100%" }} size={8}>
          {stages.map((s) => (
            <div key={s.stage}>
              <Space style={{ justifyContent: "space-between", width: "100%" }}>
                <Tag color={leadStageColors[s.stage]}>
                  {labelOf(leadStageLabels, s.stage)}
                </Tag>
                <Typography.Text type="secondary">
                  {s.count} · {(s.ratio * 100).toFixed(0)}%
                </Typography.Text>
              </Space>
              <Progress
                percent={Math.round((s.count / max) * 100)}
                showInfo={false}
                size="small"
              />
            </div>
          ))}
        </Space>
      )}
    </Card>
  );
}

export default function DashboardPage() {
  // 概览接口（模块 I，可降级）
  const summary = useQuery<AnalyticsSummary>({
    queryKey: ["analytics-summary"],
    queryFn: api.analyticsSummary,
  });

  // 兜底：概览接口不可用时，线索总数直接取 /api/leads 分页 total
  const leads = useQuery({
    queryKey: ["leads", 1, 1],
    queryFn: () => api.listLeads(1, 1),
    enabled: summary.isError,
  });

  // 活动数（模块 E，可降级）
  const campaigns = useQuery({
    queryKey: ["campaigns-count"],
    queryFn: () => api.listCampaigns(1, 1),
  });

  const s = summary.data;
  const leadsTotal = s?.total_companies ?? leads.data?.total;
  const contactsTotal = s?.total_contacts;
  const sendable = s?.sendable_contacts;
  const campaignsTotal = campaigns.isSuccess ? campaigns.data.total : undefined;

  const fmt = (v: number | undefined) => (v === undefined ? "—" : v);

  return (
    <div>
      <PageHeader
        title="仪表盘"
        description="全局概览：线索规模、可触达联系人、活动与阶段分布。以回复率为核心 KPI。"
      />

      {summary.isError && (
        <DegradedNotice
          error={summary.error}
          endpoint="/api/analytics/summary"
          style={{ marginBottom: 16 }}
        />
      )}

      <Row gutter={[16, 16]}>
        <Col xs={24} sm={12} lg={6}>
          <Card>
            <Statistic
              title="线索总数"
              value={fmt(leadsTotal)}
              prefix={<TeamOutlined />}
            />
          </Card>
        </Col>
        <Col xs={24} sm={12} lg={6}>
          <Card>
            <Statistic
              title="联系人总数"
              value={fmt(contactsTotal)}
              prefix={<ContactsOutlined />}
            />
          </Card>
        </Col>
        <Col xs={24} sm={12} lg={6}>
          <Card>
            <Statistic
              title="可发送联系人"
              value={fmt(sendable)}
              prefix={<MailOutlined />}
              valueStyle={{ color: "#3f8600" }}
            />
          </Card>
        </Col>
        <Col xs={24} sm={12} lg={6}>
          <Card>
            <Statistic
              title="营销活动"
              value={fmt(campaignsTotal)}
              prefix={<SendOutlined />}
            />
          </Card>
        </Col>
      </Row>

      <Row gutter={[16, 16]} style={{ marginTop: 16 }}>
        <Col xs={24} lg={8}>
          <StageDistribution summary={s} />
        </Col>
        <Col xs={24} lg={8}>
          <HealthCard />
        </Col>
        <Col xs={24} lg={8}>
          <Card title="快速上手" size="small">
            <Space direction="vertical">
              <Typography.Text>
                <ApiOutlined /> 到「找客户」页输入关键词与目标国，一键跑通
                搜索 → 富化 → 验证 → 合规 → 评分 → 落库 流水线。
              </Typography.Text>
              <Typography.Text type="secondary">
                本地 ADAPTER_MODE=local 下全程零外部调用、零费用，结果确定性可复现。
              </Typography.Text>
            </Space>
          </Card>
        </Col>
      </Row>
    </div>
  );
}

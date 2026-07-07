"use client";

/** 线索详情：公司信息 + 联系人表 + 评分理由 + 来源留痕。 */
import { ArrowLeftOutlined } from "@ant-design/icons";
import { useQuery } from "@tanstack/react-query";
import {
  Button,
  Card,
  Col,
  Descriptions,
  Empty,
  List,
  Progress,
  Row,
  Space,
  Spin,
  Table,
  Tag,
  Typography,
} from "antd";
import type { ColumnsType } from "antd/es/table";
import Link from "next/link";
import { useParams } from "next/navigation";
import DegradedNotice from "@/components/DegradedNotice";
import PageHeader from "@/components/PageHeader";
import { api, type Contact, type ProvenanceEntry } from "@/lib/api";
import {
  contactName,
  emailStatusColors,
  emailStatusLabels,
  emailTypeLabels,
  labelOf,
} from "@/lib/labels";

function contactColumns(): ColumnsType<Contact> {
  return [
    {
      title: "姓名",
      key: "name",
      render: (_: unknown, row) => (
        <Space>
          {contactName(row.first_name, row.last_name)}
          {row.is_primary && <Tag color="blue">主联系人</Tag>}
        </Space>
      ),
    },
    {
      title: "职位",
      dataIndex: "title",
      key: "title",
      render: (v?: string) => v || "—",
    },
    {
      title: "邮箱",
      dataIndex: "email",
      key: "email",
      render: (v?: string) =>
        v ? <span className="zdhk-mono">{v}</span> : "—",
    },
    {
      title: "验证状态",
      dataIndex: "email_status",
      key: "email_status",
      width: 120,
      render: (s: Contact["email_status"]) => (
        <Tag color={emailStatusColors[s]}>
          {labelOf(emailStatusLabels, s)}
        </Tag>
      ),
    },
    {
      title: "企业/个人",
      dataIndex: "email_type",
      key: "email_type",
      width: 100,
      render: (t: Contact["email_type"]) => labelOf(emailTypeLabels, t),
    },
    {
      title: "来源",
      dataIndex: "enrichment_provider",
      key: "enrichment_provider",
      render: (v?: string) => v || "—",
    },
  ];
}

function ProvenanceList({ items }: { items: ProvenanceEntry[] }) {
  if (!items || items.length === 0) {
    return <Empty description="无留痕记录" image={Empty.PRESENTED_IMAGE_SIMPLE} />;
  }
  return (
    <List
      size="small"
      dataSource={items}
      renderItem={(p, i) => (
        <List.Item key={i}>
          <Space wrap>
            {p.source && <Tag>{p.source}</Tag>}
            {p.ref && <span className="zdhk-mono">{String(p.ref)}</span>}
            {p.at && (
              <Typography.Text type="secondary">{String(p.at)}</Typography.Text>
            )}
          </Space>
        </List.Item>
      )}
    />
  );
}

export default function LeadDetailPage() {
  const params = useParams<{ id: string }>();
  const id = params?.id;

  const { data, isLoading, error } = useQuery({
    queryKey: ["lead", id],
    queryFn: () => api.getLead(id as string),
    enabled: Boolean(id),
  });

  return (
    <div>
      <PageHeader
        title="线索详情"
        description="公司概况、联系人、评分理由与来源留痕（合规可追溯）。"
        extra={
          <Link href="/leads">
            <Button icon={<ArrowLeftOutlined />}>返回列表</Button>
          </Link>
        }
      />

      {isLoading && (
        <div style={{ textAlign: "center", padding: 48 }}>
          <Spin />
        </div>
      )}

      {error && <DegradedNotice error={error} endpoint={`/api/leads/${id}`} />}

      {data && (
        <Row gutter={[16, 16]}>
          <Col xs={24} lg={16}>
            <Card title="公司信息" style={{ marginBottom: 16 }}>
              <Descriptions column={{ xs: 1, sm: 2 }} bordered size="small">
                <Descriptions.Item label="名称">{data.name}</Descriptions.Item>
                <Descriptions.Item label="国家">
                  {data.country || "—"}
                </Descriptions.Item>
                <Descriptions.Item label="行业">
                  {data.industry || "—"}
                </Descriptions.Item>
                <Descriptions.Item label="域名">
                  {data.domain || "—"}
                </Descriptions.Item>
                <Descriptions.Item label="官网" span={2}>
                  {data.website ? (
                    <a href={data.website} target="_blank" rel="noreferrer">
                      {data.website}
                    </a>
                  ) : (
                    "—"
                  )}
                </Descriptions.Item>
                <Descriptions.Item label="首要来源">
                  {data.source_type}
                </Descriptions.Item>
                <Descriptions.Item label="阶段">{data.stage}</Descriptions.Item>
                <Descriptions.Item label="简介" span={2}>
                  {data.description || "—"}
                </Descriptions.Item>
              </Descriptions>
            </Card>

            <Card title={`联系人（${data.contacts.length}）`}>
              <Table<Contact>
                rowKey="id"
                size="small"
                columns={contactColumns()}
                dataSource={data.contacts}
                pagination={false}
                scroll={{ x: 720 }}
              />
            </Card>
          </Col>

          <Col xs={24} lg={8}>
            <Card title="AI 匹配度评分" style={{ marginBottom: 16 }}>
              <Progress
                type="dashboard"
                percent={Math.round(data.score)}
                format={(p) => `${p}`}
              />
              <div style={{ marginTop: 12 }}>
                <Typography.Text strong>评分理由</Typography.Text>
                {data.score_reasons.length > 0 ? (
                  <ul style={{ paddingLeft: 18, marginTop: 8 }}>
                    {data.score_reasons.map((r, i) => (
                      <li key={i}>{r}</li>
                    ))}
                  </ul>
                ) : (
                  <Typography.Paragraph type="secondary">
                    暂无评分理由
                  </Typography.Paragraph>
                )}
              </div>
            </Card>

            <Card title="来源留痕">
              <ProvenanceList items={data.provenance} />
            </Card>
          </Col>
        </Row>
      )}
    </div>
  );
}

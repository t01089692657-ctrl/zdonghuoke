"use client";

/** 找客户：发现表单 + 结果表；下方为线索列表（分页）。 */
import { SearchOutlined } from "@ant-design/icons";
import { useMutation, useQuery } from "@tanstack/react-query";
import {
  App,
  Button,
  Card,
  Col,
  Form,
  Input,
  InputNumber,
  Popover,
  Row,
  Select,
  Space,
  Statistic,
  Switch,
  Table,
  Tag,
  Typography,
} from "antd";
import type { ColumnsType } from "antd/es/table";
import Link from "next/link";
import { useState } from "react";
import DegradedNotice from "@/components/DegradedNotice";
import PageHeader from "@/components/PageHeader";
import {
  api,
  type Company,
  type DiscoverRequest,
  type DiscoverResult,
} from "@/lib/api";
import { labelOf, leadStageColors, leadStageLabels } from "@/lib/labels";

interface DiscoverFormValues {
  keywords: string[];
  countries: string[];
  hs_code?: string;
  industry?: string;
  limit: number;
  enrich: boolean;
}

// 常见目标市场（可自由输入，mode=tags）
const COMMON_COUNTRIES = [
  "US",
  "DE",
  "GB",
  "FR",
  "IT",
  "ES",
  "NL",
  "CA",
  "AU",
  "JP",
  "KR",
  "IN",
  "BR",
  "MX",
  "AE",
];

function ScoreTag({ score }: { score: number }) {
  const color = score >= 70 ? "green" : score >= 40 ? "gold" : "default";
  return <Tag color={color}>{Math.round(score)}</Tag>;
}

function ReasonsCell({ reasons }: { reasons: string[] }) {
  if (!reasons || reasons.length === 0) return <Typography.Text type="secondary">—</Typography.Text>;
  const head = reasons.slice(0, 2).join("；");
  return (
    <Popover
      title="评分理由"
      content={
        <ul style={{ margin: 0, paddingLeft: 18, maxWidth: 320 }}>
          {reasons.map((r, i) => (
            <li key={i}>{r}</li>
          ))}
        </ul>
      }
    >
      <Typography.Text style={{ cursor: "pointer" }}>
        {head}
        {reasons.length > 2 ? " …" : ""}
      </Typography.Text>
    </Popover>
  );
}

function companyColumns(): ColumnsType<Company> {
  return [
    {
      title: "公司名称",
      dataIndex: "name",
      key: "name",
      render: (name: string, row) => (
        <Link href={`/leads/${row.id}`}>{name}</Link>
      ),
    },
    {
      title: "国家",
      dataIndex: "country",
      key: "country",
      width: 90,
      render: (v?: string) => v || "—",
    },
    {
      title: "行业",
      dataIndex: "industry",
      key: "industry",
      render: (v?: string) => v || "—",
    },
    {
      title: "阶段",
      dataIndex: "stage",
      key: "stage",
      width: 90,
      render: (stage: Company["stage"]) => (
        <Tag color={leadStageColors[stage]}>
          {labelOf(leadStageLabels, stage)}
        </Tag>
      ),
    },
    {
      title: "评分",
      dataIndex: "score",
      key: "score",
      width: 80,
      sorter: (a, b) => a.score - b.score,
      render: (score: number) => <ScoreTag score={score} />,
    },
    {
      title: "评分理由",
      dataIndex: "score_reasons",
      key: "score_reasons",
      render: (reasons: string[]) => <ReasonsCell reasons={reasons} />,
    },
    {
      title: "联系人",
      key: "contacts",
      width: 80,
      align: "center",
      render: (_: unknown, row) => row.contacts?.length ?? 0,
    },
  ];
}

function DiscoverPanel({
  onResult,
}: {
  onResult: (r: DiscoverResult) => void;
}) {
  const { message } = App.useApp();
  const [form] = Form.useForm<DiscoverFormValues>();

  const mutation = useMutation({
    mutationFn: (body: DiscoverRequest) => api.discoverLeads(body),
    onSuccess: (data) => {
      onResult(data);
      message.success(
        `发现 ${data.discovered} 家，新增 ${data.new_companies} 家，可发送联系人 ${data.sendable_contacts} 个`,
      );
    },
    onError: (err: Error) => message.error(err.message),
  });

  const onFinish = (values: DiscoverFormValues) => {
    if (
      (!values.keywords || values.keywords.length === 0) &&
      !values.hs_code
    ) {
      message.warning("请至少填写「关键词」或「HS 编码」之一");
      return;
    }
    mutation.mutate({
      keywords: values.keywords ?? [],
      countries: values.countries ?? [],
      hs_code: values.hs_code || undefined,
      industry: values.industry || undefined,
      limit: values.limit ?? 20,
      enrich: values.enrich,
    });
  };

  return (
    <Card title="一键找客户" style={{ marginBottom: 16 }}>
      <Form<DiscoverFormValues>
        form={form}
        layout="vertical"
        onFinish={onFinish}
        initialValues={{
          keywords: [],
          countries: [],
          limit: 20,
          enrich: true,
        }}
      >
        <Row gutter={16}>
          <Col xs={24} md={12} lg={8}>
            <Form.Item
              label="关键词"
              name="keywords"
              tooltip="产品词 / 公司名，回车分隔，可多个"
            >
              <Select
                mode="tags"
                placeholder="如 solar wall light"
                tokenSeparators={[",", "，"]}
                open={false}
                suffixIcon={null}
              />
            </Form.Item>
          </Col>
          <Col xs={24} md={12} lg={8}>
            <Form.Item label="目标国" name="countries" tooltip="ISO 国家码，可多选/自定义">
              <Select
                mode="tags"
                placeholder="如 US、DE"
                options={COMMON_COUNTRIES.map((c) => ({ label: c, value: c }))}
                tokenSeparators={[",", "，"]}
              />
            </Form.Item>
          </Col>
          <Col xs={24} md={12} lg={8}>
            <Form.Item label="HS 编码" name="hs_code">
              <Input placeholder="如 940540" allowClear />
            </Form.Item>
          </Col>
          <Col xs={24} md={12} lg={8}>
            <Form.Item label="行业" name="industry">
              <Input placeholder="如 lighting" allowClear />
            </Form.Item>
          </Col>
          <Col xs={12} md={6} lg={4}>
            <Form.Item label="数量上限" name="limit">
              <InputNumber min={1} max={200} style={{ width: "100%" }} />
            </Form.Item>
          </Col>
          <Col xs={12} md={6} lg={4}>
            <Form.Item
              label="富化联系人"
              name="enrich"
              valuePropName="checked"
              tooltip="是否顺带挖联系人邮箱并验证"
            >
              <Switch checkedChildren="开" unCheckedChildren="关" />
            </Form.Item>
          </Col>
        </Row>
        <Button
          type="primary"
          htmlType="submit"
          icon={<SearchOutlined />}
          loading={mutation.isPending}
        >
          开始找客户
        </Button>
      </Form>
    </Card>
  );
}

function ResultPanel({ result }: { result: DiscoverResult }) {
  return (
    <Card title="发现结果" style={{ marginBottom: 16 }}>
      <Row gutter={16} style={{ marginBottom: 16 }}>
        <Col xs={12} sm={8} md={4}>
          <Statistic title="发现" value={result.discovered} />
        </Col>
        <Col xs={12} sm={8} md={4}>
          <Statistic title="新增公司" value={result.new_companies} />
        </Col>
        <Col xs={12} sm={8} md={4}>
          <Statistic title="合并去重" value={result.merged_duplicates} />
        </Col>
        <Col xs={12} sm={8} md={4}>
          <Statistic title="联系人" value={result.contacts_found} />
        </Col>
        <Col xs={12} sm={8} md={4}>
          <Statistic
            title="可发送联系人"
            value={result.sendable_contacts}
            valueStyle={{ color: "#3f8600" }}
          />
        </Col>
      </Row>
      <Table<Company>
        rowKey="id"
        size="middle"
        columns={companyColumns()}
        dataSource={result.companies}
        pagination={false}
        scroll={{ x: 800 }}
      />
    </Card>
  );
}

function LeadsListPanel() {
  const [page, setPage] = useState(1);
  const [size, setSize] = useState(10);

  const { data, isLoading, error } = useQuery({
    queryKey: ["leads", page, size],
    queryFn: () => api.listLeads(page, size),
  });

  return (
    <Card title="线索列表">
      {error ? (
        <DegradedNotice error={error} endpoint="/api/leads" />
      ) : (
        <Table<Company>
          rowKey="id"
          size="middle"
          loading={isLoading}
          columns={companyColumns()}
          dataSource={data?.items ?? []}
          scroll={{ x: 800 }}
          pagination={{
            current: page,
            pageSize: size,
            total: data?.total ?? 0,
            showSizeChanger: true,
            showTotal: (t) => `共 ${t} 条`,
            onChange: (p, s) => {
              setPage(p);
              setSize(s);
            },
          }}
        />
      )}
    </Card>
  );
}

export default function LeadsPage() {
  const [result, setResult] = useState<DiscoverResult | null>(null);

  return (
    <div>
      <PageHeader
        title="找客户 / 线索"
        description="输入产品关键词与目标市场，一键跑通「搜索 → 去重 → 富化 → 验证 → 合规 → 评分 → 落库」。"
      />
      <DiscoverPanel onResult={setResult} />
      {result && <ResultPanel result={result} />}
      <LeadsListPanel />
    </div>
  );
}

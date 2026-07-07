"use client";

/** 营销活动：列表 + 新建表单。后端未挂载/宕机时优雅降级。 */
import { PlusOutlined } from "@ant-design/icons";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import {
  App,
  Button,
  Card,
  Form,
  Input,
  Modal,
  Select,
  Table,
  Tag,
  Typography,
} from "antd";
import type { ColumnsType } from "antd/es/table";
import { useState } from "react";
import DegradedNotice from "@/components/DegradedNotice";
import PageHeader from "@/components/PageHeader";
import { api, type Campaign, type CampaignCreate } from "@/lib/api";
import {
  campaignStatusColors,
  campaignStatusLabels,
  labelOf,
} from "@/lib/labels";

// 新建表单收集的字段（会组装进 icp_config 传给后端）
interface CampaignFormValues {
  name: string;
  product?: string;
  target_market?: string;
  language?: string;
}

const columns: ColumnsType<Campaign> = [
  { title: "活动名称", dataIndex: "name", key: "name" },
  {
    title: "状态",
    dataIndex: "status",
    key: "status",
    width: 100,
    render: (s: Campaign["status"]) => (
      <Tag color={campaignStatusColors[s]}>
        {labelOf(campaignStatusLabels, s)}
      </Tag>
    ),
  },
  {
    title: "产品",
    key: "product",
    render: (_: unknown, row) =>
      (row.icp_config?.product as string) || "—",
  },
  {
    title: "目标市场",
    key: "target_market",
    render: (_: unknown, row) =>
      (row.icp_config?.target_market as string) || "—",
  },
  {
    title: "序列步数",
    key: "sequence_steps",
    width: 100,
    align: "center",
    render: (_: unknown, row) => row.sequence_def?.length ?? 0,
  },
  {
    title: "目标数",
    key: "targets",
    width: 90,
    align: "center",
    render: (_: unknown, row) => row.targets?.length ?? 0,
  },
];

function CreateCampaignModal({
  open,
  onClose,
}: {
  open: boolean;
  onClose: () => void;
}) {
  const { message } = App.useApp();
  const [form] = Form.useForm<CampaignFormValues>();
  const qc = useQueryClient();

  const mutation = useMutation({
    mutationFn: (body: CampaignCreate) => api.createCampaign(body),
    onSuccess: () => {
      message.success("活动已创建（默认套用 3-7-7 四步序列）");
      qc.invalidateQueries({ queryKey: ["campaigns"] });
      form.resetFields();
      onClose();
    },
    onError: (err: Error) => message.warning(`创建暂不可用：${err.message}`),
  });

  const onFinish = (v: CampaignFormValues) => {
    mutation.mutate({
      name: v.name,
      // 产品/市场/语言存入 ICP 配置，供写信 agent 引用
      icp_config: {
        product: v.product,
        target_market: v.target_market,
        language: v.language,
      },
    });
  };

  return (
    <Modal
      title="新建营销活动"
      open={open}
      onCancel={onClose}
      okText="创建"
      cancelText="取消"
      confirmLoading={mutation.isPending}
      onOk={() => form.submit()}
    >
      <Form<CampaignFormValues>
        form={form}
        layout="vertical"
        onFinish={onFinish}
        initialValues={{ language: "en" }}
      >
        <Form.Item
          label="活动名称"
          name="name"
          rules={[{ required: true, message: "请输入活动名称" }]}
        >
          <Input placeholder="如 2026 Q1 太阳能墙灯 · 北美" />
        </Form.Item>
        <Form.Item label="产品" name="product">
          <Input placeholder="如 solar wall light" />
        </Form.Item>
        <Form.Item label="目标市场" name="target_market">
          <Input placeholder="如 US, DE" />
        </Form.Item>
        <Form.Item label="邮件语言" name="language">
          <Select
            options={[
              { label: "英语", value: "en" },
              { label: "德语", value: "de" },
              { label: "法语", value: "fr" },
              { label: "西班牙语", value: "es" },
            ]}
          />
        </Form.Item>
        <Typography.Text type="secondary">
          序列默认套用 3-7-7 四步（首封 + 3 封跟进），可稍后编辑。
        </Typography.Text>
      </Form>
    </Modal>
  );
}

export default function CampaignsPage() {
  const [open, setOpen] = useState(false);

  const { data, isLoading, error } = useQuery({
    queryKey: ["campaigns"],
    queryFn: () => api.listCampaigns(),
  });

  return (
    <div>
      <PageHeader
        title="营销活动"
        description="创建活动并编排邮件序列，从线索加目标批量触达。回复率是核心 KPI。"
        extra={
          <Button
            type="primary"
            icon={<PlusOutlined />}
            onClick={() => setOpen(true)}
          >
            新建活动
          </Button>
        }
      />

      {error ? (
        <>
          <DegradedNotice
            error={error}
            endpoint="/api/campaigns"
            style={{ marginBottom: 16 }}
          />
          <Card>
            <Table<Campaign>
              rowKey="id"
              columns={columns}
              dataSource={[]}
              locale={{ emptyText: "活动模块暂不可用" }}
            />
          </Card>
        </>
      ) : (
        <Card>
          <Table<Campaign>
            rowKey="id"
            loading={isLoading}
            columns={columns}
            dataSource={data?.items ?? []}
            pagination={{ pageSize: 10, showTotal: (t) => `共 ${t} 条` }}
          />
        </Card>
      )}

      <CreateCampaignModal open={open} onClose={() => setOpen(false)} />
    </div>
  );
}

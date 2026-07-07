"use client";

/** 人审队列（HITL）：展示 AI 待审草稿，含个性化证据与垃圾词评分，支持通过/驳回。 */
import { CheckOutlined, CloseOutlined } from "@ant-design/icons";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import {
  App,
  Button,
  Card,
  Col,
  Empty,
  Input,
  Modal,
  Row,
  Space,
  Spin,
  Tag,
  Typography,
} from "antd";
import { useState } from "react";
import DegradedNotice from "@/components/DegradedNotice";
import PageHeader from "@/components/PageHeader";
import { api, type AgentDraft } from "@/lib/api";

// 骨架阶段：无鉴权，用固定审核人标识。接入登录后替换为当前用户。
const REVIEWER = "workbench";

function EvidenceList({ evidence }: { evidence: string[] }) {
  if (!evidence || evidence.length === 0) {
    return (
      <Typography.Text type="secondary">
        无个性化证据（需警惕编造）
      </Typography.Text>
    );
  }
  return (
    <Space size={[4, 8]} wrap>
      {evidence.map((e, i) => (
        <Tag key={i} color="geekblue">
          {e}
        </Tag>
      ))}
    </Space>
  );
}

function SpamScoreTag({ score }: { score: number }) {
  const color = score <= 1 ? "green" : score <= 3 ? "gold" : "red";
  return <Tag color={color}>垃圾词评分 {score}</Tag>;
}

function DraftCard({
  draft,
  onReject,
}: {
  draft: AgentDraft;
  onReject: (draft: AgentDraft) => void;
}) {
  const { message } = App.useApp();
  const qc = useQueryClient();

  const approve = useMutation({
    mutationFn: () => api.approveDraft(draft.id, REVIEWER),
    onSuccess: () => {
      message.success("已通过");
      qc.invalidateQueries({ queryKey: ["drafts"] });
    },
    onError: (err: Error) => message.warning(`操作暂不可用：${err.message}`),
  });

  return (
    <Card
      style={{ marginBottom: 16 }}
      title={
        <Space>
          <span>{draft.subject}</span>
          {draft.language && <Tag>{draft.language}</Tag>}
          <SpamScoreTag score={draft.spam_score} />
        </Space>
      }
      extra={
        draft.lead_id ? (
          <Typography.Text className="zdhk-mono" type="secondary">
            lead: {draft.lead_id.slice(0, 8)}
          </Typography.Text>
        ) : null
      }
      actions={[
        <Button
          key="approve"
          type="link"
          icon={<CheckOutlined />}
          loading={approve.isPending}
          onClick={() => approve.mutate()}
        >
          通过
        </Button>,
        <Button
          key="reject"
          type="link"
          danger
          icon={<CloseOutlined />}
          onClick={() => onReject(draft)}
        >
          驳回
        </Button>,
      ]}
    >
      <div className="zdhk-email-body">{draft.body}</div>
      <div style={{ marginTop: 12 }}>
        <Typography.Text strong>个性化证据：</Typography.Text>{" "}
        <EvidenceList evidence={draft.evidence} />
      </div>
    </Card>
  );
}

function RejectModal({
  draft,
  onClose,
}: {
  draft: AgentDraft | null;
  onClose: () => void;
}) {
  const { message } = App.useApp();
  const qc = useQueryClient();
  const [reason, setReason] = useState("");

  const reject = useMutation({
    mutationFn: () => api.rejectDraft(draft!.id, REVIEWER, reason.trim()),
    onSuccess: () => {
      message.success("已驳回");
      qc.invalidateQueries({ queryKey: ["drafts"] });
      setReason("");
      onClose();
    },
    onError: (err: Error) => message.warning(`操作暂不可用：${err.message}`),
  });

  return (
    <Modal
      title="驳回草稿"
      open={Boolean(draft)}
      okText="确认驳回"
      cancelText="取消"
      okButtonProps={{ danger: true, disabled: reason.trim().length === 0 }}
      confirmLoading={reject.isPending}
      onOk={() => reject.mutate()}
      onCancel={() => {
        setReason("");
        onClose();
      }}
    >
      <Typography.Paragraph type="secondary">
        请填写驳回理由（会记入草稿，供写信 agent 改进）。
      </Typography.Paragraph>
      <Input.TextArea
        rows={3}
        value={reason}
        onChange={(e) => setReason(e.target.value)}
        placeholder="如：措辞过硬 / 引用了未验证信号 / 主题行含垃圾词"
      />
    </Modal>
  );
}

export default function ReviewPage() {
  const [rejecting, setRejecting] = useState<AgentDraft | null>(null);

  const { data, isLoading, error } = useQuery({
    queryKey: ["drafts"],
    queryFn: api.listDrafts,
  });

  const drafts = data ?? [];

  return (
    <div>
      <PageHeader
        title="人审队列（HITL）"
        description="逐条审阅 AI 草稿：核对个性化证据（引用了哪些真实信号），10 秒判断通过或驳回。批准率达标后可对该活动放开自动发送。"
      />

      {isLoading && (
        <div style={{ textAlign: "center", padding: 48 }}>
          <Spin />
        </div>
      )}

      {error && (
        <>
          <DegradedNotice
            error={error}
            endpoint="/api/agent/drafts"
            style={{ marginBottom: 16 }}
          />
          <Card>
            <Empty description="人审模块暂不可用，无待审草稿" />
          </Card>
        </>
      )}

      {!isLoading && !error && (
        <Row>
          <Col xs={24} lg={16}>
            {drafts.length === 0 ? (
              <Card>
                <Empty description="暂无待审草稿" />
              </Card>
            ) : (
              drafts.map((d) => (
                <DraftCard key={d.id} draft={d} onReject={setRejecting} />
              ))
            )}
          </Col>
        </Row>
      )}

      <RejectModal draft={rejecting} onClose={() => setRejecting(null)} />
    </div>
  );
}

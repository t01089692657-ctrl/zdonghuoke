"use client";

/** 统一收件箱：占位骨架。未来接 /api/sending 收件与会话聚合。 */
import { InboxOutlined } from "@ant-design/icons";
import { Alert, Card, Col, Empty, List, Row, Tag, Typography } from "antd";
import PageHeader from "@/components/PageHeader";

// 占位会话列表（真实数据未来来自 /api/sending 的收件聚合）
const PLACEHOLDER_THREADS = [
  { id: "t1", from: "buyer@example-import.com", subject: "Re: solar wall lights inquiry", intent: "感兴趣" },
  { id: "t2", from: "purchasing@acme-trading.de", subject: "Out of office until Monday", intent: "自动回复" },
  { id: "t3", from: "info@nordic-lighting.se", subject: "Please remove me", intent: "退订" },
];

export default function InboxPage() {
  return (
    <div>
      <PageHeader
        title="统一收件箱"
        description="跨发信邮箱聚合收件，会话视图并绑定线索卡片。回复自动分诊、低置信度转人工。"
      />

      <Alert
        type="info"
        showIcon
        style={{ marginBottom: 16 }}
        message="收件箱功能开发中"
        description="待发送模块（/api/sending）上线后，这里将展示真实会话。以下为占位示意。"
      />

      <Row gutter={16}>
        <Col xs={24} md={9} lg={7}>
          <Card title="会话" size="small" bodyStyle={{ padding: 0 }}>
            <List
              dataSource={PLACEHOLDER_THREADS}
              renderItem={(t) => (
                <List.Item style={{ padding: "12px 16px", cursor: "not-allowed" }}>
                  <List.Item.Meta
                    title={
                      <Typography.Text ellipsis style={{ maxWidth: 200 }}>
                        {t.subject}
                      </Typography.Text>
                    }
                    description={
                      <span>
                        <span className="zdhk-mono">{t.from}</span>{" "}
                        <Tag>{t.intent}</Tag>
                      </span>
                    }
                  />
                </List.Item>
              )}
            />
          </Card>
        </Col>
        <Col xs={24} md={15} lg={17}>
          <Card size="small" style={{ minHeight: 360 }}>
            <div style={{ padding: 48 }}>
              <Empty
                image={<InboxOutlined style={{ fontSize: 48, color: "#bfbfbf" }} />}
                description="选择左侧会话查看往来邮件（占位）"
              />
            </div>
          </Card>
        </Col>
      </Row>
    </div>
  );
}

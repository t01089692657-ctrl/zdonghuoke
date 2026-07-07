"use client";

import { Typography } from "antd";
import type { ReactNode } from "react";

/** 页面标题 + 描述 + 右侧操作区。 */
export default function PageHeader({
  title,
  description,
  extra,
}: {
  title: string;
  description?: string;
  extra?: ReactNode;
}) {
  return (
    <div
      style={{
        display: "flex",
        alignItems: "flex-start",
        justifyContent: "space-between",
        marginBottom: 20,
        gap: 16,
      }}
    >
      <div>
        <Typography.Title level={3} className="zdhk-page-title">
          {title}
        </Typography.Title>
        {description && <p className="zdhk-page-desc">{description}</p>}
      </div>
      {extra && <div>{extra}</div>}
    </div>
  );
}

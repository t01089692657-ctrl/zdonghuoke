"use client";

import { Alert } from "antd";
import { ApiError } from "@/lib/api";

/**
 * 优雅降级提示条。用于并行开发中的接口：
 * - 接口未实现（404/405/501）→ 温和提示「后端开发中」。
 * - 后端不可达（网络错误）→ 提示检查后端是否启动。
 * - 其它错误 → 显示错误信息。
 */
export default function DegradedNotice({
  error,
  endpoint,
  style,
}: {
  error: unknown;
  endpoint?: string;
  style?: React.CSSProperties;
}) {
  const apiError = error instanceof ApiError ? error : null;

  if (apiError?.isNotImplemented) {
    return (
      <Alert
        type="info"
        showIcon
        style={style}
        message="该模块后端接口开发中"
        description={
          <>
            接口 {endpoint ? <code>{endpoint}</code> : "尚未实现"}
            （HTTP {apiError.status}），当前展示占位内容。等后端上线后本页将自动接入真实数据。
          </>
        }
      />
    );
  }

  if (apiError?.isNetworkError) {
    return (
      <Alert
        type="warning"
        showIcon
        style={style}
        message="无法连接后端"
        description={
          <>
            {apiError.message}
            <br />
            请确认后端已启动（默认 http://localhost:8000），或检查 NEXT_PUBLIC_API_BASE_URL。
          </>
        }
      />
    );
  }

  const message =
    apiError?.message ?? (error instanceof Error ? error.message : "未知错误");
  return (
    <Alert
      type="error"
      showIcon
      style={style}
      message="请求出错"
      description={message}
    />
  );
}

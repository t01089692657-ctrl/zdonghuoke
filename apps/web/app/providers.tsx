"use client";

/**
 * 全局 Provider：TanStack Query + antd ConfigProvider（中文 locale + 主题）+ antd App。
 * antd 的 message/notification 通过 <App> 上下文获取，避免脱离主题的静态调用告警。
 */
import { App as AntApp, ConfigProvider } from "antd";
import zhCN from "antd/locale/zh_CN";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { useState, type ReactNode } from "react";

export default function Providers({ children }: { children: ReactNode }) {
  const [queryClient] = useState(
    () =>
      new QueryClient({
        defaultOptions: {
          queries: {
            // retry 关掉，让 404（未实现接口）立即触发降级，不做无谓重试
            retry: false,
            refetchOnWindowFocus: false,
            staleTime: 30_000,
          },
        },
      }),
  );

  return (
    <QueryClientProvider client={queryClient}>
      <ConfigProvider
        locale={zhCN}
        theme={{
          token: {
            colorPrimary: "#2f54eb",
            borderRadius: 6,
          },
        }}
      >
        <AntApp>{children}</AntApp>
      </ConfigProvider>
    </QueryClientProvider>
  );
}

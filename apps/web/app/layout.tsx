import type { Metadata } from "next";
import { AntdRegistry } from "@ant-design/nextjs-registry";
import type { ReactNode } from "react";
import AppShell from "./AppShell";
import Providers from "./providers";
import "./globals.css";

export const metadata: Metadata = {
  title: "ZDHK 客户工作台",
  description: "面向外贸企业的 AI 自动获客系统 —— 客户工作台",
};

export default function RootLayout({ children }: { children: ReactNode }) {
  return (
    <html lang="zh-CN">
      <body>
        <AntdRegistry>
          <Providers>
            <AppShell>{children}</AppShell>
          </Providers>
        </AntdRegistry>
      </body>
    </html>
  );
}

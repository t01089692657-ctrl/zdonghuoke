# apps/web — 客户工作台（前端）

ZDHK 自动获客系统的客户工作台。**Next.js 14（App Router）+ TypeScript + Ant Design v5 + TanStack Query**。

## 技术栈

| 关注点 | 选型 |
|---|---|
| 框架 | Next.js 14 App Router |
| 语言 | TypeScript（strict） |
| UI | Ant Design v5（中文 locale）+ @ant-design/icons |
| SSR 样式 | @ant-design/nextjs-registry |
| 数据请求 | TanStack Query v5 + 自研类型化 fetch 客户端（`lib/api.ts`） |

## 本地运行

前置：Node ≥ 18.18（推荐 20/22）、pnpm。后端需在 `http://localhost:8000` 运行（见 `services/api`）。

```bash
cd apps/web
pnpm install
pnpm dev            # http://localhost:3000
```

生产构建与启动：

```bash
pnpm build
pnpm start          # 默认 3000 端口
```

其它脚本：`pnpm lint`（eslint）、`pnpm typecheck`（tsc --noEmit）。

## 环境变量

| 变量 | 默认值 | 说明 |
|---|---|---|
| `NEXT_PUBLIC_API_BASE_URL` | `http://localhost:8000` | 后端 API 基地址（不带尾斜杠）。 |

本地可复制 `.env.example` 为 `.env.local` 覆盖。

## 页面

| 路由 | 模块 | 说明 |
|---|---|---|
| `/` | 仪表盘（I） | 健康状态 + 概览卡片（线索数、可发送联系人、活动数、正向回复）。 |
| `/leads` | 找客户（B/C） | 发现表单 → `POST /api/leads/discover`；结果表 + 线索列表（`GET /api/leads` 分页）。 |
| `/leads/[id]` | 线索详情（C） | 公司信息 + 联系人表 + 评分理由 + 来源留痕（`GET /api/leads/{id}`）。 |
| `/campaigns` | 营销活动（E/I） | 列表 + 新建表单（`/api/campaigns`，未实现时降级）。 |
| `/inbox` | 统一收件箱（E9） | 占位骨架，未来接 `/api/sending` 收件聚合。 |
| `/review` | 人审队列（G4） | 展示 AI 草稿 + 个性化证据，通过/驳回（`/api/agent/drafts`，未实现时降级）。 |

## API 客户端与优雅降级

`lib/api.ts` 是唯一的类型化 API 客户端：

- 读 `NEXT_PUBLIC_API_BASE_URL`，封装 `http.get/http.post` 及各业务方法（`api.*`）。
- 定义与后端 `schema` 对应的 TS 类型：`Company`、`Contact`、`DiscoverRequest`、`DiscoverResult`、`Page<T>`、`EmailCheckResult` 等。
- 统一解析后端错误体 `{"error":{"code","message"}}`，抛 `ApiError`（带 `status`/`code`）。
- 对并行开发中的接口（`/api/analytics`、`/api/campaigns`、`/api/agent`、`/api/sending`），
  当返回 404/405/501 时 `ApiError.isNotImplemented` 为真，页面用 `components/DegradedNotice`
  显示占位/提示而不崩溃。

## 目录结构

```
apps/web/
  app/
    layout.tsx          # AntdRegistry + Providers + AppShell
    providers.tsx       # QueryClient + ConfigProvider(zhCN) + antd App
    AppShell.tsx        # 侧边导航 + 顶栏
    globals.css
    page.tsx            # / 仪表盘
    leads/page.tsx      # /leads 找客户
    leads/[id]/page.tsx # 线索详情
    campaigns/page.tsx
    inbox/page.tsx
    review/page.tsx
  components/           # PageHeader、DegradedNotice
  lib/
    api.ts              # 类型化 API 客户端 + 类型定义
    labels.ts           # 枚举→中文标签
  Dockerfile            # 多阶段：install + build + next start（暴露 3000）
```

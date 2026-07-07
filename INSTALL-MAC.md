# Mac 安装与运行指南

在你的 Mac（含 Mac mini）上解压本压缩包后，按下面任一路径启动。

---

## 方式 A：一键脚本（推荐，免 Docker）

前置：装两个包管理器（各一行命令，装过可跳过）：

```bash
# 1) uv —— Python 包管理器
curl -LsSf https://astral.sh/uv/install.sh | sh
# 2) Node + pnpm —— 前端
brew install node
npm install -g pnpm
```

然后在解压出来的项目根目录运行：

```bash
bash mac-quickstart.sh
```

脚本会自动：装依赖 → 灌 18 家演示公司数据 → 同时起后端和前端。看到下面两行即成功：

- 后端 API 文档：http://localhost:8000/docs
- 前端界面：http://localhost:3000

打开 http://localhost:3000 就能看到和预览截图一样的工作台。按 `Ctrl+C` 停止。

---

## 方式 B：Docker 一键（装了 Docker Desktop 的话最省事）

```bash
cp .env.example .env
docker compose up --build
```

同样是后端 8000、前端 3000。它会额外起一个 Postgres 容器（更接近生产）。

---

## 方式 C：手动分步（想分别控制时）

```bash
# 后端
cd services/api
uv sync --extra dev
DATABASE_URL="sqlite+aiosqlite:///./local.db" ADAPTER_MODE=local uv run python -m app.scripts.seed   # 灌演示数据
DATABASE_URL="sqlite+aiosqlite:///./local.db" ADAPTER_MODE=local uv run uvicorn app.main:app --port 8000

# 前端（另开一个终端）
cd apps/web
pnpm install
NEXT_PUBLIC_API_BASE_URL=http://localhost:8000 pnpm dev
```

---

## 常见问题

- **端口被占用**：先关掉占用 3000/8000 的程序，或改端口（后端 `--port`，前端 `pnpm dev -- -p 3002` 并相应改 `NEXT_PUBLIC_API_BASE_URL`）。
- **这是什么模式？** 默认 `ADAPTER_MODE=local`：所有外部依赖（大模型/海关数据/邮件发送）用内置的确定性「假适配器」，**零外部调用、零费用**，用于验证产品与流程。数据是演示用的，不会真的给任何人发邮件。
- **怎么接真实数据/真发邮件？** 编辑 `.env` 设 `ADAPTER_MODE=cloud` 并填入真实密钥（大模型、海关/搜索/地图、SES 等），业务代码一行不改。真实适配器的实现位置和对接方式见 `infra/README.md` 与 `docs/05-架构与开发规范.md` 第 3 节。
- **跑测试**：`cd services/api && uv run pytest`（62 项）。
- **想读代码从哪看起**：`README.md` → `docs/05-架构与开发规范.md`（代码库宪法）→ `services/api/app/modules/leads/`（标准模块样板）。

---

## 目录结构速览

```
zdonghuoke/
├── mac-quickstart.sh        ← Mac 一键启动
├── MAC安装指南.md            ← 本文件
├── README.md                ← 项目总览与快速开始
├── docs/                    ← 调研/PRD/技术方案/岗位分工/架构规范(01-05)
├── docker-compose.yml       ← Docker 一键（方式 B）
├── apps/web/                ← Next.js 前端工作台
├── services/api/            ← 后端（模块化单体 + 端口与适配器）
└── infra/                   ← 部署指南（本地→单机→双平面云）
```

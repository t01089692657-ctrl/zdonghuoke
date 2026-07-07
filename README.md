# 自动获客系统（项目代号：ZDHK）

> 面向中国外贸出口企业的 **AI 自动获客 SaaS**。
> 对标产品：[麦穗获客 / 麦穗智能体（51wheatsearch.com）](https://www.51wheatsearch.com/)，并参考探迹、小满 OKKI、Apollo.io、Instantly.ai、Clay.com 等国内外同类产品。

## 一句话定位

**"你的 7×24 小时 AI 外贸业务员"** —— 输入产品和目标市场，系统自动完成：
市场分析 → 全球找买家 → 挖决策人联系方式 → AI 写个性化开发信 → 自动序列触达与跟进 → 回复分诊 → 高意向线索沉淀进 CRM，人只在关键节点审批和接管谈判。

## 快速开始（Mac mini）

```bash
cp .env.example .env      # 默认 ADAPTER_MODE=local，零外部依赖/零费用即可跑
make up                   # docker compose 启动：Postgres + API + Web
# 打开 http://localhost:8000/docs  （API 文档）  与  http://localhost:3000（前端）
```

不用 Docker（纯本地 SQLite）：

```bash
make install              # 装后端(uv)+前端(pnpm)依赖
cd services/api && DATABASE_URL="sqlite+aiosqlite:///./local.db" uv run uvicorn app.main:app --reload
make dev-web              # 另开终端起前端
```

试跑找客户流水线（本地 fake，全程无外部调用、无费用）：

```bash
make seed
# 或直接调 API：
curl -X POST localhost:8000/api/leads/discover -H 'Content-Type: application/json' \
  -d '{"keywords":["solar wall light"],"countries":["US","DE"],"limit":20,"enrich":true}'
```

**上云**：把 `.env` 的 `ADAPTER_MODE` 改成 `cloud` 并填真实密钥（大模型/海关/SES…），
业务代码一行不改。原理见 [docs/05](docs/05-架构与开发规范.md) 第 3 节。

## 文档导航

| 文档 | 内容 | 主要读者 |
|---|---|---|
| [docs/01-调研与对标分析.md](docs/01-调研与对标分析.md) | 麦穗智能体功能全拆解、18 个竞品功能矩阵、赛道趋势、市场规模、差异化机会 | 全员 |
| [docs/02-产品需求文档PRD.md](docs/02-产品需求文档PRD.md) | 产品定位、目标用户、完整功能需求清单（P0/P1/P2）、非功能需求、定价、成功指标、MVP 范围 | 产品经理、全员 |
| [docs/03-技术架构与实现方案.md](docs/03-技术架构与实现方案.md) | 总体架构（境内控制面+海外执行面）、技术选型、数据源方案、发送基建、AI 智能体流水线、合规工程、成本模型 | 工程师 |
| [docs/04-岗位分工与执行计划.md](docs/04-岗位分工与执行计划.md) | 团队配置、产品经理与各工程师岗位的职责/任务/交付物、里程碑排期（M0–M4）、验收标准、风险清单 | 全员 |
| [docs/05-架构与开发规范.md](docs/05-架构与开发规范.md) | **代码库宪法**：分层与依赖规则、模块解剖、端口与适配器、测试规范（改代码前必读） | 工程师 |

## 实现状态

已交付一个**可运行、有测试、模块边界清晰**的完整骨架（`ADAPTER_MODE=local` 在 Mac mini 上零依赖即可跑通全流程）：

| 层/模块 | 状态 | 说明 |
|---|---|---|
| 工程地基（core/domain/ports/adapters/DI） | ✅ | 模块化单体 + 端口与适配器，本地/云一套代码 |
| leads 线索发现 | ✅ | 多源检索→跨源去重→可解释评分→落库 |
| enrichment 富化 | ✅ | 瀑布式补全（命中即停）+ 邮箱验证 |
| compliance 合规 | ✅ | 全局抑制列表 + 企业/个人邮箱守卫 + 审计（发送前硬校验） |
| sending 发送与送达率 | ✅ | 域名/邮箱池、预热状态机、频控、序列引擎、探针、退信投诉闭环、送达红线 |
| agent AI 智能体 | ✅ | 模型路由 + 研究/写信/回复三 agent + 人审 HITL |
| campaigns / crm / analytics | ✅ | 活动与序列、线索阶段与跟进、漏斗与看板 |
| orchestration 编排 | ✅ | 把上述模块串成完整闭环（备信→人审→发送→回复分诊） |
| web 前端工作台 | ✅ | Next.js + AntD：仪表盘/找客户/详情/活动/收件箱/人审队列 |
| 测试 | ✅ | 62 项后端测试全绿（含端到端集成测试），ruff 干净 |

完整闭环已用真实 HTTP 接口端到端验证：找客户 → 建活动 → AI 备信 → 人审 → 入队发送 →
tick 推进 → 入站退订分诊 → 全局抑制。三条红线（人审闸门、送达率熔断、退订即抑制）实测生效。

## 核心结论速览

1. **做什么**：复刻麦穗"五步法"闭环（分析市场 → 采集客户 → 开发跟进 → AI 写信 → 社媒/归档），但以三点差异化：
   - **多源瀑布流数据 + AI 实时背调**（对标 Clay 模式，打掉"单一数据源之争"）；
   - **送达率基础设施产品化**（域名池、预热、频控、信誉监控——国内同类普遍缺失，是护城河）；
   - **人机协作的 AI SDR**（AI 干活、人审关键节点，配可解释性，符合 2026 年行业验证的最佳实践）。
2. **MVP 范围（P0）**：搜索/海关/地图三个找客户入口 + 邮箱瀑布富化与验证 + AI 写信 + 邮件序列自动跟进 + 探针 + 统一收件箱 + 回复意图分类 + 轻 CRM + 数据看板。约 12 周可上线内测。
3. **合规是设计约束不是事后补丁**：只做企业/职务邮箱冷触达、一键退订+全局抑制列表、数据来源可追溯、WhatsApp 仅 opt-in、不突破反爬红线；生成式 AI 走"登记"轻路径（只接入已备案大模型）；数据架构按"境外采集→境内处理→再出境"豁免条款做分域。
4. **商业模型**：主流价格带 1–3 万元/年（麦穗 29,800/年），每客户月变动成本约 ¥350–800，毛利率 65–85%；另设自助低价档切入 78 万外贸主体的长尾市场。

## 仓库结构

```
zdonghuoke/
├── docs/                    # 产品与技术文档（01-05）
├── docker-compose.yml       # Mac mini 一键全栈
├── Makefile                 # make up / test / seed / lint …
├── apps/
│   └── web/                 # 客户工作台（Next.js + TypeScript）
├── services/
│   └── api/                 # 后端（模块化单体 + 端口与适配器）
│       └── app/
│           ├── core/        # 配置/DB/日志/错误/DI 容器
│           ├── domain/      # 纯业务规则+枚举+契约（无 IO，可单测）
│           ├── ports/       # 外部依赖抽象接口
│           ├── adapters/    # 接口实现：fake(本地) / real(云端)
│           └── modules/     # 业务模块：leads/enrichment/compliance/
│                            #          sending/agent/campaigns/crm/analytics
└── infra/                   # IaC 与部署（境内控制面 + 海外执行面，后续）
```

架构采用**模块化单体 + 端口与适配器（Hexagonal）**：本地一套代码用 fake 适配器零依赖跑，
上云换 `ADAPTER_MODE=cloud` 即用真实供应商，业务与领域代码零改动。改起来不会牵一发动全身，
细节见 [docs/05 架构与开发规范](docs/05-架构与开发规范.md)。

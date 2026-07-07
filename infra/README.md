# 部署指南（infra）

从 Mac mini 到云服务器的三级演进路径。核心：**同一套代码，靠 `ADAPTER_MODE` 与
`DATABASE_URL` 切换环境**，不重写业务。

---

## 阶段一：Mac mini 本地运行（现在）

最省事，零外部依赖、零费用：

```bash
cp .env.example .env      # ADAPTER_MODE=local
make up                   # docker compose：Postgres + API(:8000) + Web(:3000)
```

或不装 Docker（纯本地）：

```bash
make install
cd services/api && DATABASE_URL="sqlite+aiosqlite:///./local.db" uv run uvicorn app.main:app --reload
make dev-web
```

Mac mini 作为常驻小服务器很合适：`make up` 后设为开机自启（用 `launchd` 或 `docker compose up -d`），
即可 7×24 给自己或小团队用。此阶段所有外部适配器是 fake，用于打磨产品与流程，不产生真实触达。

---

## 阶段二：单台云服务器（首个真实客户）

一台 2C4G 云主机即可起步：

```bash
# 服务器上
git clone <repo> && cd zdonghuoke
cp .env.example .env      # 填真实密钥，设 ADAPTER_MODE=cloud
docker compose -f docker-compose.yml -f docker-compose.prod.yml up -d
```

要点：
- 数据库换成云托管 Postgres（改 `.env` 的 `DATABASE_URL` 即可，代码不动）；
- 反向代理（Caddy/Nginx）挂 HTTPS；
- 先只接入「真实大模型 + 1 个数据源 + 邮箱验证」，发送仍可用小批量 SES 灰度；
- 此时即可服务真实外贸客户，验证送达率与回复率。

---

## 阶段三：双平面云架构（规模化，见 docs/03 §1）

按合规与送达要求拆「境内控制面 + 海外执行面」：

```
境内（阿里云/腾讯云）        海外（AWS/阿里云海外区）
─────────────────────      ─────────────────────────
Web 工作台 / 主 API          采集集群（Playwright+代理池）
CRM / 账务 / 人审            Enrichment 瀑布 / 邮箱验证
国产大模型(DeepSeek/Qwen)    发送引擎(SES 域名池) / 预热网络
                            探针落地页 / IMAP 收件 / SNS 回调
        └──── 只传输符合出境豁免条件的数据 ────┘
```

落地方式：
- 执行面的适配器（`adapters/real/` 的数据源/SES/富化）部署在海外节点；控制面跑 API/前端/CRM；
- 两平面通过内网专线/加密通道通信，跨境只传「境外采集→境内加工→再出境」豁免范围内的数据
  （详见 docs/04 缺口五与 docs/03 §5）；
- 长时序列建议引入 Temporal（sending 模块的 Scheduler 抽象已为此预留，换实现不动业务）；
- Postgres 换 JSONB/pgvector、上 Alembic 迁移、加 OpenSearch 做线索检索。

---

## 数据库迁移（生产）

本地/MVP 用 `Base.metadata.create_all`（`app.core.database.init_db`）。
上生产前引入 Alembic：

```bash
cd services/api
uv add alembic
uv run alembic init alembic
# 配置 alembic env 指向 app.core.database.Base.metadata 与 DATABASE_URL
uv run alembic revision --autogenerate -m "init"
uv run alembic upgrade head
```

## 备份红线

`suppression_entries`（全局抑制列表）与发信域名信誉数据是全系统最不可丢的数据 ——
每日快照。丢了会导致对已退订用户重复发信（合规事故）与送达率崩坏。

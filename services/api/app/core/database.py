"""数据库会话与 ORM 基类（SQLAlchemy 2.0 异步）。

设计要点：
- 用 async engine，Postgres(asyncpg) 与 SQLite(aiosqlite) 同一套代码。
- 所有 ORM 模型继承 Base，统一 id/created_at/updated_at。
- 为了跨库可移植，模型层避免 Postgres 专有类型（用通用 JSON、String）。
  未来上 Postgres 后可换 JSONB / pgvector，只需改列类型，不动业务。
"""
from __future__ import annotations

import uuid
from collections.abc import AsyncGenerator
from datetime import UTC, datetime

from sqlalchemy import DateTime, String, func
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column

from app.core.config import get_settings

settings = get_settings()

# SQLite 需要 check_same_thread=False 之外无特殊参数；asyncpg 走连接池。
engine = create_async_engine(
    settings.database_url,
    echo=False,
    future=True,
    pool_pre_ping=not settings.database_url.startswith("sqlite"),
)

SessionLocal = async_sessionmaker(engine, expire_on_commit=False, class_=AsyncSession)


def new_uuid() -> str:
    return str(uuid.uuid4())


def utcnow() -> datetime:
    return datetime.now(UTC)


class Base(DeclarativeBase):
    """所有 ORM 模型的基类，带统一主键与时间戳。"""

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_uuid)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), default=utcnow
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), default=utcnow, onupdate=utcnow
    )


async def get_session() -> AsyncGenerator[AsyncSession, None]:
    """FastAPI 依赖：每请求一个会话，自动提交/回滚/关闭。"""
    async with SessionLocal() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise


async def init_db() -> None:
    """本地/MVP 用 create_all 建表；生产改用 Alembic 迁移（见 infra/）。

    导入所有模块的 models 以便 Base.metadata 收集到全部表。
    """
    from app import models_registry  # noqa: F401  汇总所有 ORM 模型

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

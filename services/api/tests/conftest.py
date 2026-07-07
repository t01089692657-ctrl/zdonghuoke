"""测试夹具：每个测试一个独立的内存 SQLite 库，快且互不干扰。"""
from __future__ import annotations

import pytest
import pytest_asyncio
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app import models_registry  # noqa: F401  收集所有模型
from app.core.database import Base


@pytest_asyncio.fixture
async def session() -> AsyncSession:
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    maker = async_sessionmaker(engine, expire_on_commit=False, class_=AsyncSession)
    async with maker() as s:
        yield s
    await engine.dispose()


@pytest.fixture
def sample_query():
    from app.domain.contracts import LeadSearchQuery

    return LeadSearchQuery(
        keywords=["solar light"], countries=["US", "DE"], industry="Wholesale", limit=10
    )

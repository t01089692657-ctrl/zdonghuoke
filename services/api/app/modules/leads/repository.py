"""线索持久化。把 SQL 细节关在这里，service 只调方法，便于将来换存储。"""
from __future__ import annotations

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.leads.models import Company, Contact


class LeadRepository:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def find_by_fingerprint(self, fingerprint: str) -> Company | None:
        result = await self.session.execute(
            select(Company).where(Company.dedup_fingerprint == fingerprint)
        )
        return result.scalar_one_or_none()

    async def get(self, company_id: str) -> Company | None:
        result = await self.session.execute(select(Company).where(Company.id == company_id))
        return result.scalar_one_or_none()

    async def add(self, company: Company, *, flush: bool = True) -> Company:
        """加入会话。flush=False 时保持 pending，便于先构建完整对象图（含 contacts）
        再一次性 flush —— 避免对已持久化对象的关系集合触发异步惰性加载。"""
        self.session.add(company)
        if flush:
            await self.session.flush()
        return company

    async def flush(self) -> None:
        await self.session.flush()

    async def list(self, *, offset: int, limit: int) -> tuple[list[Company], int]:
        total = int(
            (await self.session.execute(select(func.count()).select_from(Company))).scalar_one()
        )
        result = await self.session.execute(
            select(Company).order_by(Company.score.desc(), Company.created_at.desc())
            .offset(offset).limit(limit)
        )
        return list(result.scalars().all()), total

    async def add_contact(self, contact: Contact) -> Contact:
        self.session.add(contact)
        await self.session.flush()
        return contact

    async def find_contact_by_email(self, email: str) -> Contact | None:
        """按邮箱找联系人（入站回复归因：来信邮箱 → 联系人 → 公司）。"""
        result = await self.session.execute(
            select(Contact).where(Contact.email == email.strip().lower()).limit(1)
        )
        return result.scalar_one_or_none()

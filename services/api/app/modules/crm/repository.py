"""crm 持久化。SQL 关在这里；对 leads.Company 的读写也统一走此层。"""
from __future__ import annotations

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.crm.models import Activity
from app.modules.leads.models import Company


class CrmRepository:
    def __init__(self, session: AsyncSession):
        self.session = session

    # ---- Company（阶段直接落在 leads.Company.stage）------------------------
    async def get_company(self, company_id: str) -> Company | None:
        result = await self.session.execute(select(Company).where(Company.id == company_id))
        return result.scalar_one_or_none()

    async def companies_by_stage(self, stage: str) -> list[Company]:
        result = await self.session.execute(
            select(Company)
            .where(Company.stage == stage)
            .order_by(Company.score.desc(), Company.created_at.desc())
        )
        return list(result.scalars().all())

    async def find_companies_by_domain(self, domain: str) -> list[Company]:
        result = await self.session.execute(
            select(Company).where(func.lower(Company.domain) == domain.lower())
        )
        return list(result.scalars().all())

    # ---- Activity ----------------------------------------------------------
    async def add_activity(self, activity: Activity) -> Activity:
        self.session.add(activity)
        await self.session.flush()
        return activity

    async def list_activities(self, company_id: str) -> list[Activity]:
        """按发生时间倒序返回时间线。"""
        result = await self.session.execute(
            select(Activity)
            .where(Activity.company_id == company_id)
            .order_by(Activity.at.desc(), Activity.created_at.desc())
        )
        return list(result.scalars().all())

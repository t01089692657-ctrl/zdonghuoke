"""campaigns 持久化。所有 SQL 关在这里，service 只调方法。"""
from __future__ import annotations

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.campaigns.models import Campaign, CampaignTarget
from app.modules.leads.models import Company


class CampaignRepository:
    def __init__(self, session: AsyncSession):
        self.session = session

    # ---- Campaign ----------------------------------------------------------
    async def add(self, campaign: Campaign) -> Campaign:
        self.session.add(campaign)
        await self.session.flush()
        return campaign

    async def get(self, campaign_id: str) -> Campaign | None:
        result = await self.session.execute(select(Campaign).where(Campaign.id == campaign_id))
        return result.scalar_one_or_none()

    async def list(self, *, offset: int, limit: int) -> tuple[list[Campaign], int]:
        total = int(
            (await self.session.execute(select(func.count()).select_from(Campaign))).scalar_one()
        )
        result = await self.session.execute(
            select(Campaign).order_by(Campaign.created_at.desc()).offset(offset).limit(limit)
        )
        return list(result.scalars().all()), total

    # ---- CampaignTarget ----------------------------------------------------
    async def add_target(self, target: CampaignTarget, *, flush: bool = True) -> CampaignTarget:
        self.session.add(target)
        if flush:
            await self.session.flush()
        return target

    async def flush(self) -> None:
        await self.session.flush()

    async def list_targets(self, campaign_id: str) -> list[CampaignTarget]:
        result = await self.session.execute(
            select(CampaignTarget)
            .where(CampaignTarget.campaign_id == campaign_id)
            .order_by(CampaignTarget.created_at.asc())
        )
        return list(result.scalars().all())

    async def list_targets_by_state(self, campaign_id: str, state: str) -> list[CampaignTarget]:
        result = await self.session.execute(
            select(CampaignTarget)
            .where(CampaignTarget.campaign_id == campaign_id, CampaignTarget.state == state)
            .order_by(CampaignTarget.created_at.asc())
        )
        return list(result.scalars().all())

    async def existing_contact_ids(self, campaign_id: str) -> set[str]:
        """该活动已入队的 contact_id 集合，用于加目标时去重。"""
        result = await self.session.execute(
            select(CampaignTarget.contact_id).where(
                CampaignTarget.campaign_id == campaign_id,
                CampaignTarget.contact_id.isnot(None),
            )
        )
        return {row[0] for row in result.all() if row[0] is not None}

    # ---- 从 leads 取公司（含联系人，selectin 预加载）------------------------
    async def load_companies(self, company_ids: list[str] | None) -> list[Company]:
        """按公司 id 列表取 Company；company_ids 为空则取全部（可作简单筛选入口）。"""
        stmt = select(Company)
        if company_ids:
            stmt = stmt.where(Company.id.in_(company_ids))
        stmt = stmt.order_by(Company.score.desc(), Company.created_at.desc())
        result = await self.session.execute(stmt)
        return list(result.scalars().all())

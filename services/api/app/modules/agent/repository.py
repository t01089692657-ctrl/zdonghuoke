"""agent 持久化。把 SQL 关在这里：素材卡缓存的读写、人审草稿队列的增改查。"""
from __future__ import annotations

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.domain.enums import ApprovalStatus
from app.modules.agent.models import DraftApproval, ResearchCache


class AgentRepository:
    def __init__(self, session: AsyncSession):
        self.session = session

    # ---- 研究素材卡缓存 ----------------------------------------------------
    async def get_cached_brief(self, domain: str) -> ResearchCache | None:
        result = await self.session.execute(
            select(ResearchCache).where(ResearchCache.company_domain == domain)
        )
        return result.scalar_one_or_none()

    async def save_brief(self, domain: str, brief: dict) -> ResearchCache:
        entry = ResearchCache(company_domain=domain, brief=brief)
        self.session.add(entry)
        await self.session.flush()
        return entry

    # ---- 人审草稿队列（HITL）----------------------------------------------
    async def add_draft(self, draft: DraftApproval) -> DraftApproval:
        self.session.add(draft)
        await self.session.flush()  # flush 以拿到 id
        return draft

    async def get_draft(self, draft_id: str) -> DraftApproval | None:
        result = await self.session.execute(
            select(DraftApproval).where(DraftApproval.id == draft_id)
        )
        return result.scalar_one_or_none()

    async def list_pending(self) -> list[DraftApproval]:
        result = await self.session.execute(
            select(DraftApproval)
            .where(DraftApproval.status == ApprovalStatus.pending)
            .order_by(DraftApproval.created_at.asc())
        )
        return list(result.scalars().all())

    async def count_by_status(self, status: ApprovalStatus) -> int:
        result = await self.session.execute(
            select(func.count()).select_from(DraftApproval).where(DraftApproval.status == status)
        )
        return int(result.scalar_one())

    async def list_by_campaign(
        self, campaign_id: str, status: ApprovalStatus | None = None
    ) -> list[DraftApproval]:
        """按活动查草稿（可按状态过滤）。orchestration 用它取「已批准」的草稿去入队发送。"""
        stmt = select(DraftApproval).where(DraftApproval.campaign_id == campaign_id)
        if status is not None:
            stmt = stmt.where(DraftApproval.status == status)
        result = await self.session.execute(stmt.order_by(DraftApproval.created_at.asc()))
        return list(result.scalars().all())

    async def find_draft(self, campaign_id: str, lead_id: str) -> DraftApproval | None:
        """查同一活动同一线索是否已有草稿（任意状态），保证重复 prepare 幂等。"""
        result = await self.session.execute(
            select(DraftApproval)
            .where(DraftApproval.campaign_id == campaign_id)
            .where(DraftApproval.lead_id == lead_id)
            .limit(1)
        )
        return result.scalar_one_or_none()

    async def flush(self) -> None:
        await self.session.flush()

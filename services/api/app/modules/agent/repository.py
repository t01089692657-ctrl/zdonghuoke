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

    async def flush(self) -> None:
        await self.session.flush()

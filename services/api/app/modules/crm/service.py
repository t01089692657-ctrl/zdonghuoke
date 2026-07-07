"""crm 服务：线索阶段、跟进记录、管道视图、防撞单。

阶段直接读写 leads.Company.stage（LeadStage），本模块不复制阶段状态，避免双写不一致。
每次阶段跃迁都会自动落一条 stage_change Activity，形成可追溯的时间线。
"""
from __future__ import annotations

from app.core.errors import NotFoundError, ValidationError
from app.domain.enums import LeadStage
from app.domain.rules import email_domain
from app.modules.crm.models import Activity
from app.modules.crm.repository import CrmRepository
from app.modules.leads.models import Company


class CrmService:
    def __init__(self, repo: CrmRepository):
        self.repo = repo

    # ---- 跟进记录 ----------------------------------------------------------
    async def log_activity(
        self,
        company_id: str,
        *,
        type: str,
        content: str | None = None,
        actor: str = "system",
        contact_id: str | None = None,
    ) -> Activity:
        """记一条交互。公司不存在则报错，避免脏时间线。"""
        await self._get_company_or_404(company_id)
        if not type or not type.strip():
            raise ValidationError("活动类型不能为空")
        activity = Activity(
            company_id=company_id,
            contact_id=contact_id,
            type=type.strip(),
            content=content,
            actor=actor,
        )
        return await self.repo.add_activity(activity)

    async def timeline(self, company_id: str) -> list[Activity]:
        """公司的交互时间线（倒序）。"""
        await self._get_company_or_404(company_id)
        return await self.repo.list_activities(company_id)

    # ---- 阶段管理 ----------------------------------------------------------
    async def change_stage(
        self, company_id: str, new_stage: LeadStage, *, actor: str = "system"
    ) -> Company:
        """更新 Company.stage 并记一条 stage_change activity（记录 旧→新）。"""
        company = await self._get_company_or_404(company_id)
        old_stage = company.stage
        old_value = old_stage.value if isinstance(old_stage, LeadStage) else str(old_stage)
        if old_value == new_stage.value:
            # 阶段未变：幂等，不重复记录
            return company
        company.stage = new_stage
        await self.repo.add_activity(
            Activity(
                company_id=company_id,
                type="stage_change",
                content=f"{old_value} -> {new_stage.value}",
                actor=actor,
            )
        )
        return company

    async def list_pipeline(self) -> list[dict]:
        """按 LeadStage 分组的管道视图：每个阶段的公司数量与公司列表（漏斗顺序）。"""
        pipeline: list[dict] = []
        for stage in LeadStage:
            companies = await self.repo.companies_by_stage(stage.value)
            pipeline.append({"stage": stage, "count": len(companies), "companies": companies})
        return pipeline

    # ---- 防撞单 ------------------------------------------------------------
    async def collision_check(
        self, *, email: str | None = None, domain: str | None = None
    ) -> dict:
        """按邮箱域名/公司域名查是否已有同公司，防止团队内重复开发（撞单）。"""
        target_domain = domain.strip().lower() if domain else None
        if not target_domain and email:
            target_domain = email_domain(email)
        if not target_domain:
            raise ValidationError("需提供 email 或 domain")
        if target_domain.startswith("www."):
            target_domain = target_domain[4:]
        matched = await self.repo.find_companies_by_domain(target_domain)
        return {"domain": target_domain, "collision": len(matched) > 0, "matched": matched}

    # ---- 内部 --------------------------------------------------------------
    async def _get_company_or_404(self, company_id: str) -> Company:
        company = await self.repo.get_company(company_id)
        if company is None:
            raise NotFoundError("公司不存在")
        return company

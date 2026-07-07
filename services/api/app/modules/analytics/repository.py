"""analytics 持久化（只读聚合）。SQL 关在这里，service 只做汇总编排。

数据以 leads 的 Company/Contact 为主。送达/邮件漏斗指标待 sending 模块就绪后接入
（见 service.py 的扩展点注释），此处不 import sending，避免与并行开发耦合。
"""
from __future__ import annotations

from sqlalchemy import Float, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.domain.enums import EmailStatus, EmailType
from app.modules.leads.models import Company, Contact

_SENDABLE_STATUSES = (EmailStatus.valid.value, EmailStatus.unknown.value)


class AnalyticsRepository:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def stage_counts(self) -> dict[str, int]:
        """按线索阶段分组统计公司数量。"""
        result = await self.session.execute(
            select(Company.stage, func.count()).group_by(Company.stage)
        )
        return {str(stage): int(count) for stage, count in result.all()}

    async def company_count(self) -> int:
        result = await self.session.execute(select(func.count()).select_from(Company))
        return int(result.scalar_one())

    async def contact_count(self) -> int:
        result = await self.session.execute(select(func.count()).select_from(Contact))
        return int(result.scalar_one())

    async def sendable_contact_count(self) -> int:
        """可发送联系人：企业邮箱 + 状态 valid/unknown + 邮箱非空。"""
        result = await self.session.execute(
            select(func.count())
            .select_from(Contact)
            .where(
                Contact.email.isnot(None),
                Contact.email_type == EmailType.corporate.value,
                Contact.email_status.in_(_SENDABLE_STATUSES),
            )
        )
        return int(result.scalar_one())

    async def source_breakdown(self) -> list[tuple[str, int, float]]:
        """按数据源类型统计线索数与平均分。"""
        result = await self.session.execute(
            select(
                Company.source_type,
                func.count(),
                func.coalesce(func.avg(Company.score), 0.0).cast(Float),
            ).group_by(Company.source_type)
        )
        return [(str(src), int(cnt), float(avg)) for src, cnt, avg in result.all()]

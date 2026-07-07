"""analytics 服务：效果看板的只读聚合。

当前以 leads 数据为主，提供线索漏斗、数据源质量、总览三张视图（对标 PRD 模块 I）。
邮件层指标（发送/送达/回复漏斗、送达健康度）留清晰扩展点，待 sending 就绪后接入。
"""
from __future__ import annotations

from app.domain.enums import LeadStage
from app.modules.analytics.repository import AnalyticsRepository


class AnalyticsService:
    def __init__(self, repo: AnalyticsRepository):
        self.repo = repo

    async def funnel(self) -> list[dict]:
        """按 LeadStage 统计线索漏斗数量（固定漏斗顺序，含数量为 0 的阶段）。

        扩展点：I1 的完整 Campaign 漏斗还需 发送/送达/打开/点击/回复/正向回复/询盘
        各层数据 —— 待 sending 的统计就绪后，在此叠加邮件层漏斗（回复率为核心 KPI）。
        """
        counts = await self.repo.stage_counts()
        return [
            {"stage": stage, "count": counts.get(stage.value, 0)} for stage in LeadStage
        ]

    async def lead_source_breakdown(self) -> list[dict]:
        """按 Company.source_type 统计线索数与平均分（对标 I4 数据源质量报表）。

        扩展点：完整版还应含各源的验证通过率与回复率（反哺采购决策），
        分别依赖 enrichment 与 sending 的统计，接入后在此合并。
        """
        rows = await self.repo.source_breakdown()
        return [
            {"source_type": src, "count": cnt, "avg_score": round(avg, 2)}
            for src, cnt, avg in rows
        ]

    async def summary(self) -> dict:
        """总览：总公司数、总联系人数、可发送联系人数、各阶段占比。"""
        total_companies = await self.repo.company_count()
        total_contacts = await self.repo.contact_count()
        sendable_contacts = await self.repo.sendable_contact_count()
        counts = await self.repo.stage_counts()
        stages = [
            {
                "stage": stage,
                "count": counts.get(stage.value, 0),
                "ratio": (
                    round(counts.get(stage.value, 0) / total_companies, 4)
                    if total_companies
                    else 0.0
                ),
            }
            for stage in LeadStage
        ]
        return {
            "total_companies": total_companies,
            "total_contacts": total_contacts,
            "sendable_contacts": sendable_contacts,
            "stages": stages,
        }

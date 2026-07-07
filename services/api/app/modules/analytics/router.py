"""analytics 模块 HTTP 路由（薄层）：收参 → 调 service → 返 schema。"""
from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_session
from app.modules.analytics.repository import AnalyticsRepository
from app.modules.analytics.schemas import (
    FunnelOut,
    FunnelStageOut,
    SourceBreakdownOut,
    SourcesOut,
    StageRatioOut,
    SummaryOut,
)
from app.modules.analytics.service import AnalyticsService

router = APIRouter(prefix="/analytics", tags=["analytics"])


def build_analytics_service(session: AsyncSession) -> AnalyticsService:
    return AnalyticsService(repo=AnalyticsRepository(session))


@router.get("/funnel", response_model=FunnelOut)
async def get_funnel(session: AsyncSession = Depends(get_session)):
    """线索漏斗：按 LeadStage 统计数量。"""
    svc = build_analytics_service(session)
    rows = await svc.funnel()
    stages = [FunnelStageOut(stage=r["stage"], count=r["count"]) for r in rows]
    return FunnelOut(stages=stages, total=sum(s.count for s in stages))


@router.get("/sources", response_model=SourcesOut)
async def get_sources(session: AsyncSession = Depends(get_session)):
    """数据源质量：按 source_type 统计线索数与平均分。"""
    svc = build_analytics_service(session)
    rows = await svc.lead_source_breakdown()
    return SourcesOut(sources=[SourceBreakdownOut(**r) for r in rows])


@router.get("/summary", response_model=SummaryOut)
async def get_summary(session: AsyncSession = Depends(get_session)):
    """总览：总公司数、总联系人数、可发送联系人数、各阶段占比。"""
    svc = build_analytics_service(session)
    data = await svc.summary()
    return SummaryOut(
        total_companies=data["total_companies"],
        total_contacts=data["total_contacts"],
        sendable_contacts=data["sendable_contacts"],
        stages=[StageRatioOut(**s) for s in data["stages"]],
    )

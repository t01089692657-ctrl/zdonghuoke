"""crm 模块 HTTP 路由（薄层）：收参 → 调 service → 返 schema。"""
from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_session
from app.modules.crm.repository import CrmRepository
from app.modules.crm.schemas import (
    ActivityIn,
    ActivityOut,
    CollisionCheckOut,
    CompanyBrief,
    CompanyStageOut,
    PipelineOut,
    PipelineStageOut,
    StageChangeIn,
)
from app.modules.crm.service import CrmService

router = APIRouter(prefix="/crm", tags=["crm"])


def build_crm_service(session: AsyncSession) -> CrmService:
    return CrmService(repo=CrmRepository(session))


@router.get("/pipeline", response_model=PipelineOut)
async def get_pipeline(session: AsyncSession = Depends(get_session)):
    """按阶段分组的漏斗管道视图。"""
    svc = build_crm_service(session)
    pipeline = await svc.list_pipeline()
    stages = [
        PipelineStageOut(
            stage=row["stage"],
            count=row["count"],
            companies=[CompanyBrief.model_validate(c) for c in row["companies"]],
        )
        for row in pipeline
    ]
    return PipelineOut(stages=stages, total=sum(s.count for s in stages))


@router.post("/companies/{company_id}/stage", response_model=CompanyStageOut)
async def change_stage(
    company_id: str, body: StageChangeIn, session: AsyncSession = Depends(get_session)
):
    """更新公司阶段并自动记录一条 stage_change 交互。"""
    svc = build_crm_service(session)
    company = await svc.change_stage(company_id, body.stage, actor=body.actor)
    return CompanyStageOut.model_validate(company)


@router.post("/companies/{company_id}/activities", response_model=ActivityOut, status_code=201)
async def add_activity(
    company_id: str, body: ActivityIn, session: AsyncSession = Depends(get_session)
):
    """记一条跟进/交互。"""
    svc = build_crm_service(session)
    activity = await svc.log_activity(
        company_id,
        type=body.type,
        content=body.content,
        actor=body.actor,
        contact_id=body.contact_id,
    )
    return ActivityOut.model_validate(activity)


@router.get("/companies/{company_id}/timeline", response_model=list[ActivityOut])
async def get_timeline(company_id: str, session: AsyncSession = Depends(get_session)):
    """公司交互时间线（倒序）。"""
    svc = build_crm_service(session)
    activities = await svc.timeline(company_id)
    return [ActivityOut.model_validate(a) for a in activities]


@router.get("/collision-check", response_model=CollisionCheckOut)
async def collision_check(
    email: str | None = None,
    domain: str | None = None,
    session: AsyncSession = Depends(get_session),
):
    """撞单检查：按邮箱域名/公司域名查是否已有同公司。"""
    svc = build_crm_service(session)
    result = await svc.collision_check(email=email, domain=domain)
    return CollisionCheckOut(
        domain=result["domain"],
        collision=result["collision"],
        matched=[CompanyBrief.model_validate(c) for c in result["matched"]],
    )

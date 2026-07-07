from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_session
from app.modules.agent.router import build_agent_service
from app.modules.campaigns.router import build_campaign_service
from app.modules.crm.router import build_crm_service
from app.modules.leads.repository import LeadRepository
from app.modules.orchestration.schemas import (
    InboundRequest,
    InboundResult,
    LaunchResult,
    PrepareRequest,
    PrepareResult,
    TickResult,
)
from app.modules.orchestration.service import OrchestrationService
from app.modules.sending.router import build_sending_service

router = APIRouter(prefix="/orchestration", tags=["orchestration"])


def build_orchestration_service(session: AsyncSession) -> OrchestrationService:
    """组合各模块 service（复用各自的 build_*，保证装配方式全局一致）。"""
    return OrchestrationService(
        campaigns=build_campaign_service(session),
        agent=build_agent_service(session),
        sending=build_sending_service(session),
        crm=build_crm_service(session),
        leads=LeadRepository(session),
    )


@router.post("/campaigns/{campaign_id}/prepare", response_model=PrepareResult)
async def prepare(
    campaign_id: str, body: PrepareRequest, session: AsyncSession = Depends(get_session)
):
    """为活动目标逐个 AI 研究+写信，生成待人审草稿（HITL 第一步）。"""
    svc = build_orchestration_service(session)
    result = await svc.prepare_campaign(campaign_id, body.product_info)
    return PrepareResult(**result)


@router.post("/campaigns/{campaign_id}/launch", response_model=LaunchResult)
async def launch(campaign_id: str, session: AsyncSession = Depends(get_session)):
    """把已批准草稿 + 活动后续步骤入队发送序列（只发人审通过的内容）。"""
    svc = build_orchestration_service(session)
    result = await svc.launch_approved(campaign_id)
    return LaunchResult(**result)


@router.post("/campaigns/{campaign_id}/quick-launch", response_model=LaunchResult)
async def quick_launch(campaign_id: str, session: AsyncSession = Depends(get_session)):
    """模板直发模式：活动模板序列直接入队（模板需已被人工确认）。"""
    svc = build_orchestration_service(session)
    result = await svc.quick_launch(campaign_id)
    return LaunchResult(**result)


@router.post("/inbound", response_model=InboundResult)
async def inbound(body: InboundRequest, session: AsyncSession = Depends(get_session)):
    """入站回复分诊：AI 分类 → 停序列/抑制/CRM 跃迁。

    生产由收件轮询触发，此端点亦可手动/webhook 调用。
    """
    svc = build_orchestration_service(session)
    result = await svc.handle_inbound(body.from_email, body.text)
    return InboundResult(**result)


@router.post("/tick", response_model=TickResult)
async def tick(session: AsyncSession = Depends(get_session)):
    """系统心跳：预热推进 + 序列步进。生产环境由 cron/定时器每分钟调用。"""
    svc = build_orchestration_service(session)
    result = await svc.tick()
    return TickResult(**result)

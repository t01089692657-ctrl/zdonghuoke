"""agent 模块 HTTP 路由（薄层）。装配 service（走 DI 容器）、收参、调 service、返 schema。

对外面：研究 / 写信（研究→写信两段式）/ 回复分类 / 人审队列（HITL）。
"""
from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.core import deps
from app.core.database import get_session
from app.domain.contracts import GeneratedEmail, ReplyClassification, ResearchBrief
from app.modules.agent.model_router import ModelRouter
from app.modules.agent.repository import AgentRepository
from app.modules.agent.schemas import (
    ApprovalRateOut,
    ApproveRequest,
    ClassifyRequest,
    DraftOut,
    RejectRequest,
    ResearchRequest,
    SubmitDraftRequest,
    WriteRequest,
)
from app.modules.agent.service import AgentService

router = APIRouter(prefix="/agent", tags=["agent"])


def build_agent_service(session: AsyncSession) -> AgentService:
    """在一个地方装配 AgentService 及其依赖（LLM 走 DI 容器，可 local/cloud 切换）。"""
    return AgentService(
        router=ModelRouter(deps.get_llm()),
        repo=AgentRepository(session),
    )


# ---- 三 agent --------------------------------------------------------------
@router.post("/research", response_model=ResearchBrief)
async def research(body: ResearchRequest, session: AsyncSession = Depends(get_session)):
    """背调：产出研究素材卡（可缓存）。"""
    svc = build_agent_service(session)
    return await svc.research(body.domain, body.website_text)


@router.post("/write", response_model=GeneratedEmail)
async def write(body: WriteRequest, session: AsyncSession = Depends(get_session)):
    """写开发信：内部先 research 再 write，体现「研究→写信」两段式。"""
    svc = build_agent_service(session)
    brief = await svc.research(body.domain)
    return await svc.write_email(brief, body.product_info, body.contact)


@router.post("/classify-reply", response_model=ReplyClassification)
async def classify_reply(body: ClassifyRequest, session: AsyncSession = Depends(get_session)):
    """回复分类：规则前置命中即零成本返回，否则走 LLM。"""
    svc = build_agent_service(session)
    return await svc.classify_reply(body.text)


# ---- 人审工作台（HITL）----------------------------------------------------
@router.post("/drafts", response_model=DraftOut)
async def submit_draft(body: SubmitDraftRequest, session: AsyncSession = Depends(get_session)):
    """提交一封开发信草稿进人审队列。"""
    svc = build_agent_service(session)
    draft = await svc.submit_draft(body.campaign_id, body.lead_id, body.email)
    return DraftOut.model_validate(draft)


@router.get("/drafts", response_model=list[DraftOut])
async def list_pending(session: AsyncSession = Depends(get_session)):
    """待审草稿列表。"""
    svc = build_agent_service(session)
    drafts = await svc.list_pending()
    return [DraftOut.model_validate(d) for d in drafts]


@router.post("/drafts/{draft_id}/approve", response_model=DraftOut)
async def approve(
    draft_id: str, body: ApproveRequest, session: AsyncSession = Depends(get_session)
):
    svc = build_agent_service(session)
    draft = await svc.approve(draft_id, body.reviewer)
    return DraftOut.model_validate(draft)


@router.post("/drafts/{draft_id}/reject", response_model=DraftOut)
async def reject(
    draft_id: str, body: RejectRequest, session: AsyncSession = Depends(get_session)
):
    svc = build_agent_service(session)
    draft = await svc.reject(draft_id, body.reviewer, body.reason)
    return DraftOut.model_validate(draft)


@router.get("/approval-rate", response_model=ApprovalRateOut)
async def approval_rate(session: AsyncSession = Depends(get_session)):
    """人审看板：待审/通过/拒绝计数与通过率。"""
    svc = build_agent_service(session)
    return ApprovalRateOut(**await svc.approval_stats())

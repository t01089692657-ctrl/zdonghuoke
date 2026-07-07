"""campaigns 模块 HTTP 路由（薄层）：收参 → 调 service → 返 schema。"""
from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_session
from app.core.errors import NotFoundError
from app.core.pagination import Page, PageParams
from app.modules.campaigns.repository import CampaignRepository
from app.modules.campaigns.schemas import (
    AddTargetsRequest,
    AddTargetsResult,
    CampaignCreate,
    CampaignOut,
    CampaignTargetOut,
)
from app.modules.campaigns.service import CampaignService

router = APIRouter(prefix="/campaigns", tags=["campaigns"])


def build_campaign_service(session: AsyncSession) -> CampaignService:
    return CampaignService(repo=CampaignRepository(session))


@router.post("", response_model=CampaignOut, status_code=201)
async def create_campaign(body: CampaignCreate, session: AsyncSession = Depends(get_session)):
    """建活动。未给序列则套用默认 3-7-7 四步序列。"""
    svc = build_campaign_service(session)
    sequence = (
        [s.model_dump() for s in body.sequence_def] if body.sequence_def is not None else None
    )
    campaign = await svc.create_campaign(
        name=body.name,
        icp_config=body.icp_config,
        sequence_def=sequence,
        created_by=body.created_by,
    )
    return CampaignOut.model_validate(campaign)


@router.get("", response_model=Page[CampaignOut])
async def list_campaigns(
    params: PageParams = Depends(), session: AsyncSession = Depends(get_session)
):
    svc = build_campaign_service(session)
    items, total = await svc.list_campaigns(offset=params.offset, limit=params.limit)
    return Page.of([CampaignOut.model_validate(c) for c in items], total, params)


@router.get("/{campaign_id}", response_model=CampaignOut)
async def get_campaign(campaign_id: str, session: AsyncSession = Depends(get_session)):
    svc = build_campaign_service(session)
    campaign = await svc.get_campaign(campaign_id)
    if campaign is None:
        raise NotFoundError("活动不存在")
    return CampaignOut.model_validate(campaign)


@router.post("/{campaign_id}/activate", response_model=CampaignOut)
async def activate_campaign(campaign_id: str, session: AsyncSession = Depends(get_session)):
    """draft → active。激活后其 pending targets 可被 sending 模块 enroll。"""
    svc = build_campaign_service(session)
    campaign = await svc.activate(campaign_id)
    return CampaignOut.model_validate(campaign)


@router.post("/{campaign_id}/targets", response_model=AddTargetsResult)
async def add_targets(
    campaign_id: str, body: AddTargetsRequest, session: AsyncSession = Depends(get_session)
):
    """从线索加目标：取可发送联系人加入 targets（company_ids 为空表示全部公司）。"""
    svc = build_campaign_service(session)
    result = await svc.add_targets_from_leads(campaign_id, company_ids=body.company_ids or None)
    return AddTargetsResult(
        added=result["added"],
        skipped=result["skipped"],
        targets=[CampaignTargetOut.model_validate(t) for t in result["targets"]],
    )

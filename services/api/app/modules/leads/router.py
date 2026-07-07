from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.core import deps
from app.core.database import get_session
from app.core.errors import NotFoundError
from app.core.pagination import Page, PageParams
from app.domain.contracts import LeadSearchQuery
from app.modules.enrichment.service import EnrichmentService
from app.modules.leads.repository import LeadRepository
from app.modules.leads.schemas import CompanyOut, DiscoverRequest, DiscoverResult
from app.modules.leads.service import LeadService

router = APIRouter(prefix="/leads", tags=["leads"])


def build_lead_service(session: AsyncSession) -> LeadService:
    """在一个地方装配 LeadService 及其全部依赖（走 DI 容器）。"""
    enrichment = EnrichmentService(
        providers=deps.get_enrichment_providers(),
        verifier=deps.get_email_verifier(),
    )
    return LeadService(
        repo=LeadRepository(session),
        data_sources=deps.get_data_sources(),
        enrichment=enrichment,
        clock=deps.get_clock(),
    )


@router.post("/discover", response_model=DiscoverResult)
async def discover(body: DiscoverRequest, session: AsyncSession = Depends(get_session)):
    """一键找客户：搜索→去重→富化→验证→合规标注→评分→落库。"""
    svc = build_lead_service(session)
    query = LeadSearchQuery(
        keywords=body.keywords,
        hs_code=body.hs_code,
        countries=body.countries,
        industry=body.industry,
        limit=body.limit,
    )
    result = await svc.discover(query, enrich=body.enrich)
    return DiscoverResult(
        discovered=result["discovered"],
        new_companies=result["new_companies"],
        merged_duplicates=result["merged_duplicates"],
        contacts_found=result["contacts_found"],
        sendable_contacts=result["sendable_contacts"],
        companies=[CompanyOut.model_validate(c) for c in result["companies"]],
    )


@router.get("", response_model=Page[CompanyOut])
async def list_companies(
    params: PageParams = Depends(), session: AsyncSession = Depends(get_session)
):
    svc = build_lead_service(session)
    items, total = await svc.list_companies(offset=params.offset, limit=params.limit)
    return Page.of([CompanyOut.model_validate(c) for c in items], total, params)


@router.get("/{company_id}", response_model=CompanyOut)
async def get_company(company_id: str, session: AsyncSession = Depends(get_session)):
    svc = build_lead_service(session)
    company = await svc.get_company(company_id)
    if company is None:
        raise NotFoundError("公司不存在")
    return CompanyOut.model_validate(company)

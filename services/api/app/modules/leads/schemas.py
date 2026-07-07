from __future__ import annotations

from pydantic import BaseModel

from app.domain.enums import EmailStatus, EmailType, LeadStage


class ContactOut(BaseModel):
    id: str
    first_name: str | None = None
    last_name: str | None = None
    title: str | None = None
    email: str | None = None
    email_status: EmailStatus
    email_type: EmailType
    linkedin_url: str | None = None
    phone: str | None = None
    enrichment_provider: str | None = None
    is_primary: bool

    class Config:
        from_attributes = True


class CompanyOut(BaseModel):
    id: str
    name: str
    domain: str | None = None
    website: str | None = None
    country: str | None = None
    industry: str | None = None
    description: str | None = None
    source_type: str
    stage: LeadStage
    score: float
    score_reasons: list[str] = []
    provenance: list = []
    contacts: list[ContactOut] = []

    class Config:
        from_attributes = True


class DiscoverRequest(BaseModel):
    """一键找客户：驱动 搜索→富化→验证→合规→评分→落库 流水线。"""

    keywords: list[str] = []
    hs_code: str | None = None
    countries: list[str] = []
    industry: str | None = None
    limit: int = 20
    enrich: bool = True  # 是否顺带富化联系人+验证邮箱


class DiscoverResult(BaseModel):
    discovered: int
    new_companies: int
    merged_duplicates: int
    contacts_found: int
    sendable_contacts: int
    companies: list[CompanyOut] = []

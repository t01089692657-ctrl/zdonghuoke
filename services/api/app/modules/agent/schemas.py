"""agent 模块 API 出入参（pydantic）。领域契约（ResearchBrief/GeneratedEmail/
ReplyClassification）直接复用 domain.contracts，仅在此定义 HTTP 专属的请求/响应包装。
"""
from __future__ import annotations

from pydantic import BaseModel, Field

from app.domain.contracts import GeneratedEmail
from app.domain.enums import ApprovalStatus


class ResearchRequest(BaseModel):
    domain: str
    website_text: str | None = None


class WriteRequest(BaseModel):
    """写开发信：内部先 research(domain) 再 write，体现「研究→写信」两段式。"""

    domain: str
    product_info: dict = Field(default_factory=dict)
    contact: dict = Field(default_factory=dict)


class ClassifyRequest(BaseModel):
    text: str


class SubmitDraftRequest(BaseModel):
    campaign_id: str | None = None
    lead_id: str | None = None
    email: GeneratedEmail


class ApproveRequest(BaseModel):
    reviewer: str


class RejectRequest(BaseModel):
    reviewer: str
    reason: str


class DraftOut(BaseModel):
    id: str
    campaign_id: str | None = None
    lead_id: str | None = None
    subject: str
    body: str
    language: str
    evidence: list = []
    spam_score: int
    status: ApprovalStatus
    reviewed_by: str | None = None
    reject_reason: str | None = None

    class Config:
        from_attributes = True


class ApprovalRateOut(BaseModel):
    approved: int
    rejected: int
    pending: int
    approval_rate: float

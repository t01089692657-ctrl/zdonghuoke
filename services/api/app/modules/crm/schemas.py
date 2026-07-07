from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel

from app.domain.enums import LeadStage


class ActivityIn(BaseModel):
    type: str
    content: str | None = None
    actor: str = "system"
    contact_id: str | None = None


class ActivityOut(BaseModel):
    id: str
    company_id: str
    contact_id: str | None = None
    type: str
    content: str | None = None
    actor: str
    at: datetime

    class Config:
        from_attributes = True


class StageChangeIn(BaseModel):
    stage: LeadStage
    actor: str = "system"


class CompanyBrief(BaseModel):
    """管道/撞单视图用的公司精简卡片。"""

    id: str
    name: str
    domain: str | None = None
    country: str | None = None
    stage: LeadStage
    score: float

    class Config:
        from_attributes = True


class CompanyStageOut(BaseModel):
    id: str
    stage: LeadStage

    class Config:
        from_attributes = True


class PipelineStageOut(BaseModel):
    stage: LeadStage
    count: int
    companies: list[CompanyBrief] = []


class PipelineOut(BaseModel):
    stages: list[PipelineStageOut] = []
    total: int


class CollisionCheckOut(BaseModel):
    domain: str
    collision: bool
    matched: list[CompanyBrief] = []

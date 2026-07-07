from __future__ import annotations

from pydantic import BaseModel

from app.domain.enums import LeadStage


class FunnelStageOut(BaseModel):
    stage: LeadStage
    count: int


class FunnelOut(BaseModel):
    stages: list[FunnelStageOut] = []
    total: int


class SourceBreakdownOut(BaseModel):
    source_type: str
    count: int
    avg_score: float


class SourcesOut(BaseModel):
    sources: list[SourceBreakdownOut] = []


class StageRatioOut(BaseModel):
    stage: LeadStage
    count: int
    ratio: float


class SummaryOut(BaseModel):
    total_companies: int
    total_contacts: int
    sendable_contacts: int
    stages: list[StageRatioOut] = []

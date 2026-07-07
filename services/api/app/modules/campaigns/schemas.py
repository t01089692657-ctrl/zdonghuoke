from __future__ import annotations

from pydantic import BaseModel, Field

from app.domain.enums import CampaignStatus


class SequenceStep(BaseModel):
    """序列中的一步。wait_days 为相对上一步的等待天数。"""

    step: int
    wait_days: int
    subject: str = ""
    body: str = ""


class CampaignCreate(BaseModel):
    name: str
    icp_config: dict = Field(default_factory=dict)
    # 不传则由 service 套用默认 3-7-7 四步序列
    sequence_def: list[SequenceStep] | None = None
    created_by: str | None = None


class CampaignTargetOut(BaseModel):
    id: str
    company_id: str
    contact_id: str | None = None
    to_email: str | None = None
    state: str

    class Config:
        from_attributes = True


class CampaignOut(BaseModel):
    id: str
    name: str
    icp_config: dict = {}
    sequence_def: list[dict] = []
    status: CampaignStatus
    created_by: str | None = None
    targets: list[CampaignTargetOut] = []

    class Config:
        from_attributes = True


class AddTargetsRequest(BaseModel):
    """从线索加目标：给定公司 id 列表（空表示全部公司）。"""

    company_ids: list[str] = Field(default_factory=list)


class AddTargetsResult(BaseModel):
    added: int
    skipped: int
    targets: list[CampaignTargetOut] = []

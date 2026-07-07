"""发送模块 API 出入参（pydantic）。"""
from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, Field

from app.domain.enums import SequenceState, WarmupStage


# ---- 域名 ------------------------------------------------------------------
class DomainIn(BaseModel):
    domain: str
    spf_ok: bool = False
    dkim_ok: bool = False
    dmarc_ok: bool = False
    reputation: float = 0.0
    active: bool = True


class DomainOut(BaseModel):
    id: str
    domain: str
    spf_ok: bool
    dkim_ok: bool
    dmarc_ok: bool
    reputation: float
    active: bool
    dns_ok: bool
    sendable: bool

    class Config:
        from_attributes = True


# ---- 邮箱 ------------------------------------------------------------------
class MailboxIn(BaseModel):
    sender_domain_id: str
    email: str
    warmup_stage: WarmupStage = WarmupStage.w1
    active: bool = True


class MailboxOut(BaseModel):
    id: str
    sender_domain_id: str
    email: str
    warmup_stage: WarmupStage
    sent_today: int
    last_reset_date: str | None = None
    active: bool

    class Config:
        from_attributes = True


class WarmupTickResult(BaseModel):
    advanced: int  # 推进阶段的邮箱数
    reset: int     # 跨日重置计数的邮箱数


# ---- 单封发送 --------------------------------------------------------------
class MessageIn(BaseModel):
    to_email: str
    subject: str
    body: str
    campaign_id: str | None = None
    lead_id: str | None = None


class MessageOut(BaseModel):
    id: str
    to_email: str
    status: str
    message_id: str | None = None
    accepted: bool
    bounced: bool
    spam_score: int
    spam_warnings: list[str] = []


# ---- 序列 ------------------------------------------------------------------
class StepIn(BaseModel):
    wait_days: int = 0
    subject: str
    body: str


class EnrollIn(BaseModel):
    lead_id: str | None = None
    campaign_id: str | None = None
    to_email: str
    steps: list[StepIn] = Field(default_factory=list)


class EnrollOut(BaseModel):
    id: str
    lead_id: str | None = None
    campaign_id: str | None = None
    to_email: str
    state: SequenceState
    step_index: int
    next_action_at: datetime | None = None

    class Config:
        from_attributes = True


class TickResult(BaseModel):
    processed: int
    sent: int
    skipped: int
    completed: int


# ---- 送达健康度 ------------------------------------------------------------
class HealthOut(BaseModel):
    total: int
    bounced: int
    complained: int
    bounce_rate: float
    complaint_rate: float
    action: str  # ok | warn | halt

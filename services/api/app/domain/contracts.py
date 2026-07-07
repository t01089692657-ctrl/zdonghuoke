"""模块与端口之间传递的数据契约（pydantic DTO，非 ORM）。

这些是系统内部各有界上下文对话用的「通用语言」。放在领域层，所有模块与
适配器都依赖它们、而不是互相依赖对方的 ORM 模型 —— 从而解耦、可独立演进。
"""
from __future__ import annotations

from pydantic import BaseModel, Field

from app.domain.enums import DataSourceType, EmailStatus, EmailType, ReplyIntent


# ---- 线索发现 --------------------------------------------------------------
class LeadSearchQuery(BaseModel):
    """找客户请求。数据源适配器据此返回候选公司。"""

    keywords: list[str] = Field(default_factory=list)
    hs_code: str | None = None
    countries: list[str] = Field(default_factory=list)
    industry: str | None = None
    limit: int = 50


class CompanyCandidate(BaseModel):
    """数据源返回的候选公司（尚未落库、未富化）。"""

    name: str
    domain: str | None = None
    website: str | None = None
    country: str | None = None
    industry: str | None = None
    description: str | None = None
    source_type: DataSourceType
    source_ref: str | None = None  # 供应商侧的原始 ID/URL，用于来源留痕
    raw: dict = Field(default_factory=dict)


# ---- 联系人富化与验证 ------------------------------------------------------
class EmailCandidate(BaseModel):
    """enrichment 返回的候选邮箱。"""

    email: str
    first_name: str | None = None
    last_name: str | None = None
    title: str | None = None
    confidence: float = 0.0
    provider: str = "unknown"


class VerificationResult(BaseModel):
    """邮箱验证结果。"""

    email: str
    status: EmailStatus
    email_type: EmailType
    reason: str | None = None


# ---- AI 写信 ---------------------------------------------------------------
class ResearchBrief(BaseModel):
    """Research Agent 产出的「素材卡」，供写信 agent 引用（可缓存）。"""

    company_domain: str
    what_they_do: str = ""
    who_they_sell_to: str = ""
    signals: list[str] = Field(default_factory=list)  # 可引用的真实信号
    approach_hint: str = ""


class GeneratedEmail(BaseModel):
    """写信 Agent 产出。personalization_evidence 是可解释性关键：
    列出正文引用了哪些真实字段，供人审 10 秒判断、并防止编造。"""

    subject: str
    body: str
    language: str = "en"
    personalization_evidence: list[str] = Field(default_factory=list)


class ReplyClassification(BaseModel):
    """Reply Agent 对来信的分类。"""

    intent: ReplyIntent
    confidence: float
    extracted: dict = Field(default_factory=dict)  # 如 OOO 返回日期、转介绍新联系人


# ---- 发送 ------------------------------------------------------------------
class OutboundEmail(BaseModel):
    """交给发送适配器的一封邮件。"""

    to_email: str
    from_email: str
    subject: str
    body_html: str
    body_text: str | None = None
    headers: dict[str, str] = Field(default_factory=dict)


class SendResult(BaseModel):
    message_id: str | None = None
    accepted: bool = False
    error: str | None = None

"""全系统共享的枚举。放在领域层，模块与适配器都引用同一份，避免字符串魔法值。"""
from __future__ import annotations

from enum import StrEnum


class EmailStatus(StrEnum):
    """邮箱验证状态。"""

    valid = "valid"
    catch_all = "catch_all"  # 域名全收，无法逐一确认 → 降权
    invalid = "invalid"
    unknown = "unknown"


class EmailType(StrEnum):
    """企业邮箱 vs 个人邮箱。合规关键：默认只向企业邮箱冷触达。"""

    corporate = "corporate"
    personal = "personal"
    unknown = "unknown"


class DataSourceType(StrEnum):
    """线索数据源类型（对标麦穗十大采购商源头）。"""

    search_engine = "search_engine"
    customs = "customs"
    maps = "maps"
    directory = "directory"
    tradeshow = "tradeshow"
    b2b_inquiry = "b2b_inquiry"
    social = "social"
    brand = "brand"


class LeadStage(StrEnum):
    """线索在漏斗中的阶段。"""

    new = "new"
    contacted = "contacted"
    replied = "replied"
    interested = "interested"
    quote = "quote"
    won = "won"
    lost = "lost"


class Channel(StrEnum):
    email = "email"
    whatsapp = "whatsapp"
    linkedin = "linkedin"


class MessageDirection(StrEnum):
    outbound = "outbound"
    inbound = "inbound"


class ReplyIntent(StrEnum):
    """回复意图分类（对标 AI SDR 标准类别）。"""

    interested = "interested"
    meeting = "meeting"
    objection = "objection"
    not_interested = "not_interested"
    referral = "referral"
    out_of_office = "out_of_office"
    unsubscribe = "unsubscribe"
    wrong_person = "wrong_person"
    bounce = "bounce"
    unknown = "unknown"


class WarmupStage(StrEnum):
    """发信邮箱预热阶段，决定每日发送上限。"""

    w1 = "w1"
    w2 = "w2"
    w3 = "w3"
    active = "active"


class SuppressionReason(StrEnum):
    """进入全局抑制列表的原因。任一原因 → 永不再发。"""

    unsubscribe = "unsubscribe"
    complaint = "complaint"
    hard_bounce = "hard_bounce"
    invalid = "invalid"
    manual = "manual"


class CampaignStatus(StrEnum):
    draft = "draft"
    active = "active"
    paused = "paused"
    completed = "completed"


class SequenceState(StrEnum):
    """单条线索在序列中的状态机。"""

    pending = "pending"
    active = "active"
    replied = "replied"
    bounced = "bounced"
    unsubscribed = "unsubscribed"
    completed = "completed"
    stopped = "stopped"


class ApprovalStatus(StrEnum):
    """人审工作台（HITL）审批状态。"""

    pending = "pending"
    approved = "approved"
    rejected = "rejected"
    auto_approved = "auto_approved"

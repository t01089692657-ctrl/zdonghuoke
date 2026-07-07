"""sending 模块 ORM 模型：发信域名池、邮箱池、外发邮件、序列状态机。

被 app.models_registry 收集用于建表。为跨库可移植（SQLite 本地 / Postgres 云端），
只用通用列类型（String/Integer/Float/Boolean/JSON/DateTime）。
模块之间不建 FK：campaign_id / lead_id 只存对方的字符串 id（解耦，见架构规范 §1）。
"""
from __future__ import annotations

from datetime import datetime

from sqlalchemy import JSON, Boolean, DateTime, Float, ForeignKey, Index, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base
from app.domain.enums import SequenceState, WarmupStage


class SenderDomain(Base):
    """一个发信域名。SPF/DKIM/DMARC「三件套」未全通过则该域不可发送（送达红线）。"""

    __tablename__ = "sender_domains"
    __table_args__ = (Index("ix_sender_domains_domain", "domain"),)

    domain: Mapped[str] = mapped_column(String(255), nullable=False)
    spf_ok: Mapped[bool] = mapped_column(Boolean, default=False)
    dkim_ok: Mapped[bool] = mapped_column(Boolean, default=False)
    dmarc_ok: Mapped[bool] = mapped_column(Boolean, default=False)
    # 域名信誉分（0~100），供未来节流/挑域参考。
    reputation: Mapped[float] = mapped_column(Float, default=0.0)
    active: Mapped[bool] = mapped_column(Boolean, default=True)

    @property
    def dns_ok(self) -> bool:
        """三件套全通过才允许发送。任一未通过 → 该域不可用。"""
        return self.spf_ok and self.dkim_ok and self.dmarc_ok

    @property
    def sendable(self) -> bool:
        return self.active and self.dns_ok


class SenderMailbox(Base):
    """发信邮箱。归属某发信域名；warmup_stage 决定每日发送上限（频控）。"""

    __tablename__ = "sender_mailboxes"
    __table_args__ = (Index("ix_sender_mailboxes_email", "email"),)

    sender_domain_id: Mapped[str] = mapped_column(
        ForeignKey("sender_domains.id", ondelete="CASCADE"), nullable=False
    )
    email: Mapped[str] = mapped_column(String(320), nullable=False)
    warmup_stage: Mapped[WarmupStage] = mapped_column(String(20), default=WarmupStage.w1)
    warmup_started_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    sent_today: Mapped[int] = mapped_column(Integer, default=0)
    # 上次日计数重置的日期（ISO date，如 2026-07-07），跨日则清零 sent_today。
    last_reset_date: Mapped[str | None] = mapped_column(String(10), nullable=True)
    active: Mapped[bool] = mapped_column(Boolean, default=True)


class OutboundMessage(Base):
    """一封已尝试投递的外发邮件。承载探针（open/click）与退信/投诉闭环状态。"""

    __tablename__ = "outbound_messages"
    __table_args__ = (
        Index("ix_outbound_messages_message_id", "message_id"),
        Index("ix_outbound_messages_to_email", "to_email"),
    )

    # 跨模块只存字符串 id，不建 FK（解耦）。
    campaign_id: Mapped[str | None] = mapped_column(String(36), nullable=True)
    lead_id: Mapped[str | None] = mapped_column(String(36), nullable=True)

    to_email: Mapped[str] = mapped_column(String(320), nullable=False)
    from_mailbox_id: Mapped[str | None] = mapped_column(String(36), nullable=True)
    subject: Mapped[str] = mapped_column(String(500), nullable=False)
    body: Mapped[str] = mapped_column(Text, nullable=False)

    status: Mapped[str] = mapped_column(String(20), default="sent")
    message_id: Mapped[str | None] = mapped_column(String(120), nullable=True)

    sent_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    opened_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    clicked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    bounced: Mapped[bool] = mapped_column(Boolean, default=False)
    complained: Mapped[bool] = mapped_column(Boolean, default=False)


class SequenceEnrollment(Base):
    """「每条线索一台状态机」：一条线索在某活动序列中的进度与下一步触发时间。

    steps 为 [{wait_days, subject, body}] 的有序步骤表；state 驱动「回复即停」等规则。
    """

    __tablename__ = "sequence_enrollments"
    __table_args__ = (
        Index("ix_sequence_enrollments_next", "next_action_at"),
        Index("ix_sequence_enrollments_to_email", "to_email"),
    )

    lead_id: Mapped[str | None] = mapped_column(String(36), nullable=True)
    campaign_id: Mapped[str | None] = mapped_column(String(36), nullable=True)
    to_email: Mapped[str] = mapped_column(String(320), nullable=False)

    state: Mapped[SequenceState] = mapped_column(String(20), default=SequenceState.active)
    step_index: Mapped[int] = mapped_column(Integer, default=0)
    next_action_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    steps: Mapped[list] = mapped_column(JSON, default=list)

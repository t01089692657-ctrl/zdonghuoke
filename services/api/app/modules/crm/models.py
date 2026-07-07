"""crm 模块 ORM 模型。被 app.models_registry 收集用于建表。

线索的「阶段」直接复用 leads.Company.stage（LeadStage），本模块不另建阶段字段，
只负责记录围绕公司/联系人的交互与跟进（Activity 时间线）。
"""
from __future__ import annotations

from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Index, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base, utcnow


class Activity(Base):
    """一条围绕公司（可选到联系人）的交互记录。构成客户 360 的时间线。

    type：note（跟进备注）/ stage_change（阶段跃迁）/ email（邮件往来）等。
    at：业务意义上的发生时间（可与 created_at 不同，如补录历史交互）。
    """

    __tablename__ = "activities"
    __table_args__ = (
        Index("ix_activities_company", "company_id"),
        Index("ix_activities_at", "at"),
    )

    company_id: Mapped[str] = mapped_column(
        ForeignKey("companies.id", ondelete="CASCADE"), nullable=False
    )
    contact_id: Mapped[str | None] = mapped_column(
        ForeignKey("contacts.id", ondelete="SET NULL"), nullable=True
    )
    type: Mapped[str] = mapped_column(String(30), nullable=False)
    content: Mapped[str | None] = mapped_column(Text, nullable=True)
    actor: Mapped[str] = mapped_column(String(120), default="system")
    at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)

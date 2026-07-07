from __future__ import annotations

from sqlalchemy import Index, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base
from app.domain.enums import SuppressionReason


class SuppressionEntry(Base):
    """全局抑制列表。email 唯一。发送前按邮箱哈希/明文查此表。"""

    __tablename__ = "suppression_entries"
    __table_args__ = (
        UniqueConstraint("email", name="uq_suppression_email"),
        Index("ix_suppression_email", "email"),
    )

    email: Mapped[str] = mapped_column(String(320), nullable=False)
    reason: Mapped[SuppressionReason] = mapped_column(String(20), nullable=False)
    note: Mapped[str | None] = mapped_column(String(500), nullable=True)


class AuditLog(Base):
    """关键动作审计（谁在何时对什么做了什么）。合规可追溯的基础。"""

    __tablename__ = "audit_logs"

    actor: Mapped[str] = mapped_column(String(120), default="system")
    action: Mapped[str] = mapped_column(String(120), nullable=False)
    entity_type: Mapped[str] = mapped_column(String(60), nullable=False)
    entity_id: Mapped[str | None] = mapped_column(String(36), nullable=True)
    detail: Mapped[str | None] = mapped_column(String(1000), nullable=True)

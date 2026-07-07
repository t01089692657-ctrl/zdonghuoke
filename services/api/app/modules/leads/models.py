from __future__ import annotations

from sqlalchemy import JSON, Float, ForeignKey, Index, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base
from app.domain.enums import EmailStatus, EmailType, LeadStage


class Company(Base):
    """一家潜在采购商。dedup_fingerprint 用于跨数据源识别同一家公司。"""

    __tablename__ = "companies"
    __table_args__ = (Index("ix_companies_fingerprint", "dedup_fingerprint"),)

    name: Mapped[str] = mapped_column(String(300), nullable=False)
    domain: Mapped[str | None] = mapped_column(String(255), nullable=True)
    website: Mapped[str | None] = mapped_column(String(500), nullable=True)
    country: Mapped[str | None] = mapped_column(String(80), nullable=True)
    industry: Mapped[str | None] = mapped_column(String(120), nullable=True)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)

    dedup_fingerprint: Mapped[str] = mapped_column(String(400), nullable=False)
    source_type: Mapped[str] = mapped_column(String(30), nullable=False)
    # 来源留痕：[{source, ref, at}]，合规可追溯
    provenance: Mapped[list] = mapped_column(JSON, default=list)

    stage: Mapped[LeadStage] = mapped_column(String(20), default=LeadStage.new)
    score: Mapped[float] = mapped_column(Float, default=0.0)
    score_reasons: Mapped[list] = mapped_column(JSON, default=list)
    raw: Mapped[dict] = mapped_column(JSON, default=dict)

    contacts: Mapped[list[Contact]] = relationship(
        back_populates="company", cascade="all, delete-orphan", lazy="selectin"
    )


class Contact(Base):
    """公司里的一个联系人（决策人/KP）。"""

    __tablename__ = "contacts"
    __table_args__ = (Index("ix_contacts_email", "email"),)

    company_id: Mapped[str] = mapped_column(
        ForeignKey("companies.id", ondelete="CASCADE"), nullable=False
    )
    first_name: Mapped[str | None] = mapped_column(String(120), nullable=True)
    last_name: Mapped[str | None] = mapped_column(String(120), nullable=True)
    title: Mapped[str | None] = mapped_column(String(200), nullable=True)

    email: Mapped[str | None] = mapped_column(String(320), nullable=True)
    email_status: Mapped[EmailStatus] = mapped_column(String(20), default=EmailStatus.unknown)
    email_type: Mapped[EmailType] = mapped_column(String(20), default=EmailType.unknown)

    linkedin_url: Mapped[str | None] = mapped_column(String(500), nullable=True)
    phone: Mapped[str | None] = mapped_column(String(60), nullable=True)

    enrichment_provider: Mapped[str | None] = mapped_column(String(60), nullable=True)
    provenance: Mapped[list] = mapped_column(JSON, default=list)
    is_primary: Mapped[bool] = mapped_column(default=False)

    company: Mapped[Company] = relationship(back_populates="contacts")

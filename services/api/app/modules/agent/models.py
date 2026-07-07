"""agent 模块 ORM 模型：人审草稿队列（HITL）与研究素材卡缓存。

被 app.models_registry 收集用于建表。列类型只用通用类型（String/Text/Integer/JSON/
DateTime），保证 SQLite 本地与 Postgres 云端同一套代码可跑。
"""
from __future__ import annotations

from datetime import datetime

from sqlalchemy import JSON, DateTime, Index, Integer, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base, utcnow
from app.domain.enums import ApprovalStatus


class DraftApproval(Base):
    """人审工作台（HITL）里的一条待审草稿。

    发送/活动模块生成开发信后，把草稿提交到这里，人工 10 秒判断 approve/reject
    （evidence 列出正文引用了哪些真实字段，spam_score 提示送达风险）。
    """

    __tablename__ = "draft_approvals"
    __table_args__ = (Index("ix_draft_approvals_status", "status"),)

    campaign_id: Mapped[str | None] = mapped_column(String(36), nullable=True)
    lead_id: Mapped[str | None] = mapped_column(String(36), nullable=True)

    subject: Mapped[str] = mapped_column(String(500), nullable=False)
    body: Mapped[str] = mapped_column(Text, nullable=False)
    language: Mapped[str] = mapped_column(String(10), default="en")
    # 可解释性证据：正文引用了哪些已验证字段（防编造、供人审快速核对）
    evidence: Mapped[list] = mapped_column(JSON, default=list)
    spam_score: Mapped[int] = mapped_column(Integer, default=0)

    status: Mapped[ApprovalStatus] = mapped_column(String(20), default=ApprovalStatus.pending)
    reviewed_by: Mapped[str | None] = mapped_column(String(120), nullable=True)
    reject_reason: Mapped[str | None] = mapped_column(String(1000), nullable=True)


class ResearchCache(Base):
    """研究素材卡缓存。company_domain 唯一，命中即复用，避免重复背调（省 token）。"""

    __tablename__ = "research_cache"
    __table_args__ = (UniqueConstraint("company_domain", name="uq_research_domain"),)

    company_domain: Mapped[str] = mapped_column(String(255), nullable=False)
    brief: Mapped[dict] = mapped_column(JSON, default=dict)
    cached_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)

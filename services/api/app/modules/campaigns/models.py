"""campaigns 模块 ORM 模型。被 app.models_registry 收集用于建表。

Campaign 承载「活动 + 序列定义 + ICP 配置 + 状态机」；CampaignTarget 是活动下
挂载的一条待触达目标（指向 leads 的 Company/Contact）。真正的发信由 sending 模块
消费这些 target 完成，本模块只负责编排与备料。
"""
from __future__ import annotations

from sqlalchemy import JSON, ForeignKey, Index, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base
from app.domain.enums import CampaignStatus


class Campaign(Base):
    """一个开发活动。sequence_def 为 4 步序列定义，默认 3-7-7 节奏（Day0/3/10/17）。"""

    __tablename__ = "campaigns"

    name: Mapped[str] = mapped_column(String(200), nullable=False)
    # ICP 画像配置（关键词/国家/行业/职位偏好等），供筛选目标与写信引用
    icp_config: Mapped[dict] = mapped_column(JSON, default=dict)
    # 序列定义：[{step, wait_days, subject, body}]，wait_days 为相对上一步的等待天数
    sequence_def: Mapped[list] = mapped_column(JSON, default=list)
    status: Mapped[CampaignStatus] = mapped_column(String(20), default=CampaignStatus.draft)
    created_by: Mapped[str | None] = mapped_column(String(120), nullable=True)

    targets: Mapped[list[CampaignTarget]] = relationship(
        back_populates="campaign", cascade="all, delete-orphan", lazy="selectin"
    )


class CampaignTarget(Base):
    """活动下的一条目标联系人。state 是本模块的入队状态（pending/enrolled/replied…）；
    序列内部的细粒度状态机（SequenceState）由 sending 模块维护，两者互不越界。"""

    __tablename__ = "campaign_targets"
    __table_args__ = (
        Index("ix_campaign_targets_campaign", "campaign_id"),
        Index("ix_campaign_targets_state", "state"),
    )

    campaign_id: Mapped[str] = mapped_column(
        ForeignKey("campaigns.id", ondelete="CASCADE"), nullable=False
    )
    # 指向 leads 的 Company/Contact（外键引用，跨模块只读取不反向依赖）
    company_id: Mapped[str] = mapped_column(
        ForeignKey("companies.id", ondelete="CASCADE"), nullable=False
    )
    contact_id: Mapped[str | None] = mapped_column(
        ForeignKey("contacts.id", ondelete="SET NULL"), nullable=True
    )
    to_email: Mapped[str | None] = mapped_column(String(320), nullable=True)
    # 入队状态：pending（待入序列）/ enrolled（已交给 sending）/ replied（有回复即停）等
    state: Mapped[str] = mapped_column(String(20), default="pending")

    campaign: Mapped[Campaign] = relationship(back_populates="targets")

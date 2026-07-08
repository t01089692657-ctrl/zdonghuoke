"""发送模块持久化。所有 SQL 关在这里（架构规范 §2：service 不写裸 SQL）。"""
from __future__ import annotations

from collections.abc import Sequence
from datetime import datetime

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.domain.enums import SequenceState
from app.modules.sending.models import (
    OutboundMessage,
    SenderDomain,
    SenderMailbox,
    SequenceEnrollment,
)


class SendingRepository:
    def __init__(self, session: AsyncSession):
        self.session = session

    # ---- 通用 --------------------------------------------------------------
    async def add(self, obj, *, flush: bool = True):
        self.session.add(obj)
        if flush:
            await self.session.flush()
        return obj

    async def flush(self) -> None:
        await self.session.flush()

    # ---- 域名 / 邮箱 -------------------------------------------------------
    async def get_domain(self, domain_id: str) -> SenderDomain | None:
        result = await self.session.execute(
            select(SenderDomain).where(SenderDomain.id == domain_id)
        )
        return result.scalar_one_or_none()

    async def get_mailbox(self, mailbox_id: str) -> SenderMailbox | None:
        result = await self.session.execute(
            select(SenderMailbox).where(SenderMailbox.id == mailbox_id)
        )
        return result.scalar_one_or_none()

    async def list_mailboxes(self) -> list[SenderMailbox]:
        result = await self.session.execute(select(SenderMailbox))
        return list(result.scalars().all())

    async def list_active_mailboxes(self) -> list[SenderMailbox]:
        result = await self.session.execute(
            select(SenderMailbox)
            .where(SenderMailbox.active.is_(True))
            .order_by(SenderMailbox.created_at)
        )
        return list(result.scalars().all())

    async def domains_by_id(self) -> dict[str, SenderDomain]:
        result = await self.session.execute(select(SenderDomain))
        return {d.id: d for d in result.scalars().all()}

    # ---- 外发邮件 ----------------------------------------------------------
    async def get_message_by_external_id(self, message_id: str) -> OutboundMessage | None:
        """按发送适配器返回的 message_id 查（供 open/click 探针回填）。

        用 first() 而非 scalar_one_or_none()：即便历史数据里存在重复 message_id，
        探针回填也不该因此 500（MultipleResultsFound）。取最近一条即可。
        """
        result = await self.session.execute(
            select(OutboundMessage)
            .where(OutboundMessage.message_id == message_id)
            .order_by(OutboundMessage.created_at.desc())
            .limit(1)
        )
        return result.scalars().first()

    async def message_stats(self) -> tuple[int, int, int]:
        """返回 (总发送数, 退信数, 投诉数)，供送达健康度计算。"""
        total = int(
            (
                await self.session.execute(select(func.count()).select_from(OutboundMessage))
            ).scalar_one()
        )
        bounced = int(
            (
                await self.session.execute(
                    select(func.count())
                    .select_from(OutboundMessage)
                    .where(OutboundMessage.bounced.is_(True))
                )
            ).scalar_one()
        )
        complained = int(
            (
                await self.session.execute(
                    select(func.count())
                    .select_from(OutboundMessage)
                    .where(OutboundMessage.complained.is_(True))
                )
            ).scalar_one()
        )
        return total, bounced, complained

    # ---- 序列状态机 --------------------------------------------------------
    async def due_enrollments(
        self, now: datetime, states: Sequence[SequenceState]
    ) -> list[SequenceEnrollment]:
        """到期（next_action_at<=now）且状态可推进的 enrollment。"""
        result = await self.session.execute(
            select(SequenceEnrollment)
            .where(
                SequenceEnrollment.state.in_(list(states)),
                SequenceEnrollment.next_action_at.is_not(None),
                SequenceEnrollment.next_action_at <= now,
            )
            .order_by(SequenceEnrollment.next_action_at)
        )
        return list(result.scalars().all())

    async def enrollments_by_email(
        self, to_email: str, states: Sequence[SequenceState]
    ) -> list[SequenceEnrollment]:
        result = await self.session.execute(
            select(SequenceEnrollment).where(
                SequenceEnrollment.to_email == to_email.strip().lower(),
                SequenceEnrollment.state.in_(list(states)),
            )
        )
        return list(result.scalars().all())

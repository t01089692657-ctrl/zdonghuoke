"""合规服务：抑制列表、邮箱守卫、审计。发送模块在真正投递前必须经过这里。"""
from __future__ import annotations

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.errors import ComplianceError
from app.domain.enums import EmailType, SuppressionReason
from app.domain.rules import classify_email_type
from app.modules.compliance.models import AuditLog, SuppressionEntry


class ComplianceService:
    def __init__(self, session: AsyncSession):
        self.session = session

    # ---- 抑制列表 ----------------------------------------------------------
    async def is_suppressed(self, email: str) -> bool:
        email = email.strip().lower()
        result = await self.session.execute(
            select(SuppressionEntry.id).where(SuppressionEntry.email == email)
        )
        return result.first() is not None

    async def add_suppression(
        self, email: str, reason: SuppressionReason, note: str | None = None
    ) -> None:
        """幂等加入抑制列表。已存在则忽略。"""
        email = email.strip().lower()
        if await self.is_suppressed(email):
            return
        self.session.add(SuppressionEntry(email=email, reason=reason, note=note))
        await self.audit("system", "suppress", "email", None, f"{email}:{reason.value}")

    async def suppression_count(self) -> int:
        result = await self.session.execute(select(func.count()).select_from(SuppressionEntry))
        return int(result.scalar_one())

    # ---- 邮箱守卫（发送前硬校验）------------------------------------------
    async def assert_sendable(self, email: str) -> None:
        """不满足任一条件即抛 ComplianceError（403），发送被拒。

        规则：
        - 必须是企业邮箱（个人邮箱默认禁止冷触达）；
        - 不能在全局抑制列表中。
        """
        if classify_email_type(email) is EmailType.personal:
            raise ComplianceError(f"拒绝发送：{email} 是个人邮箱，合规上默认不做冷触达")
        if await self.is_suppressed(email):
            raise ComplianceError(f"拒绝发送：{email} 在全局抑制列表中")

    async def is_sendable(self, email: str) -> bool:
        try:
            await self.assert_sendable(email)
            return True
        except ComplianceError:
            return False

    # ---- 审计 --------------------------------------------------------------
    async def audit(
        self,
        actor: str,
        action: str,
        entity_type: str,
        entity_id: str | None,
        detail: str | None = None,
    ) -> None:
        self.session.add(
            AuditLog(
                actor=actor,
                action=action,
                entity_type=entity_type,
                entity_id=entity_id,
                detail=detail,
            )
        )

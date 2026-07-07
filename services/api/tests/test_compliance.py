"""合规模块测试：抑制列表幂等、邮箱守卫拦截（个人邮箱/已抑制）。"""
from __future__ import annotations

import pytest

from app.core.errors import ComplianceError
from app.domain.enums import SuppressionReason
from app.modules.compliance.service import ComplianceService


async def test_suppression_is_idempotent(session):
    svc = ComplianceService(session)
    await svc.add_suppression("a@corp.com", SuppressionReason.unsubscribe)
    await svc.add_suppression("a@corp.com", SuppressionReason.complaint)  # 重复
    await session.flush()
    assert await svc.suppression_count() == 1
    assert await svc.is_suppressed("A@corp.com")  # 大小写不敏感


async def test_personal_email_rejected(session):
    svc = ComplianceService(session)
    with pytest.raises(ComplianceError):
        await svc.assert_sendable("someone@gmail.com")


async def test_suppressed_email_rejected(session):
    svc = ComplianceService(session)
    await svc.add_suppression("buyer@corp.com", SuppressionReason.unsubscribe)
    await session.flush()
    with pytest.raises(ComplianceError):
        await svc.assert_sendable("buyer@corp.com")


async def test_clean_corporate_email_sendable(session):
    svc = ComplianceService(session)
    assert await svc.is_sendable("buyer@acme-trading.com")

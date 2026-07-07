"""发送与送达率模块测试（全程 fake 适配器 + 可控时钟，确定性）。

覆盖关键红线：预热推进/频控、合规守卫、硬退信闭环、序列「回复即停」。
"""
from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest
from sqlalchemy import func, select

from app.adapters.fake.sender import FakeEmailSender
from app.core.errors import ComplianceError
from app.domain.enums import SequenceState, SuppressionReason, WarmupStage
from app.domain.rules import daily_cap_for_stage
from app.modules.compliance.service import ComplianceService
from app.modules.sending.models import OutboundMessage
from app.modules.sending.repository import SendingRepository
from app.modules.sending.service import SendingService


class FakeClock:
    """可控时钟：返回固定时间，测试里可手动推进（预热/序列依赖时间）。"""

    def __init__(self, now: datetime):
        self._now = now

    def now(self) -> datetime:
        return self._now

    def advance(self, *, days: int = 0) -> None:
        self._now = self._now + timedelta(days=days)


def _build_service(session, clock: FakeClock) -> SendingService:
    return SendingService(
        repo=SendingRepository(session),
        sender=FakeEmailSender(),
        clock=clock,
        compliance=ComplianceService(session),
    )


async def _make_sendable_mailbox(svc: SendingService, stage: WarmupStage = WarmupStage.active):
    """建一个「DNS 三件套全通过」的域 + 一个可发信邮箱。"""
    domain = await svc.register_domain(
        "sender-a.com", spf_ok=True, dkim_ok=True, dmarc_ok=True, reputation=80.0
    )
    return await svc.register_mailbox(domain.id, "hi@sender-a.com", warmup_stage=stage)


async def _count_to(session, email: str) -> int:
    result = await session.execute(
        select(func.count()).select_from(OutboundMessage).where(OutboundMessage.to_email == email)
    )
    return int(result.scalar_one())


# ---- 预热推进 --------------------------------------------------------------
async def test_warmup_advances_stage_and_raises_cap(session):
    clock = FakeClock(datetime(2026, 7, 1, tzinfo=UTC))
    svc = _build_service(session, clock)
    mb = await _make_sendable_mailbox(svc, stage=WarmupStage.w1)

    # 当前阶段已满 8 天（>7）→ 应升级
    mb.warmup_started_at = clock.now() - timedelta(days=8)
    await session.flush()

    result = await svc.warmup_tick()

    assert result["advanced"] == 1
    assert mb.warmup_stage is WarmupStage.w2
    # 日上限随阶段提高：w1=10 → w2=20
    assert daily_cap_for_stage(WarmupStage.w2) > daily_cap_for_stage(WarmupStage.w1)


async def test_warmup_tick_resets_daily_counter_across_day(session):
    clock = FakeClock(datetime(2026, 7, 7, tzinfo=UTC))
    svc = _build_service(session, clock)
    mb = await _make_sendable_mailbox(svc, stage=WarmupStage.active)

    mb.sent_today = 5
    mb.last_reset_date = "2026-07-06"  # 昨天
    await session.flush()

    result = await svc.warmup_tick()

    assert result["reset"] == 1
    assert mb.sent_today == 0
    assert mb.last_reset_date == "2026-07-07"


# ---- 频控 ------------------------------------------------------------------
async def test_rate_limit_blocks_when_cap_reached(session):
    clock = FakeClock(datetime(2026, 7, 7, tzinfo=UTC))
    svc = _build_service(session, clock)
    mb = await _make_sendable_mailbox(svc, stage=WarmupStage.w1)  # cap=10

    mb.sent_today = daily_cap_for_stage(WarmupStage.w1)  # 已达上限
    await session.flush()
    assert await svc.pick_available_mailbox() is None

    mb.sent_today = daily_cap_for_stage(WarmupStage.w1) - 1  # 还剩 1 封额度
    await session.flush()
    assert await svc.pick_available_mailbox() is mb


async def test_pick_skips_dns_unqualified_domain(session):
    clock = FakeClock(datetime(2026, 7, 7, tzinfo=UTC))
    svc = _build_service(session, clock)
    # DKIM 未通过 → 三件套不全 → 该域不可发送
    domain = await svc.register_domain(
        "bad-dns.com", spf_ok=True, dkim_ok=False, dmarc_ok=True
    )
    await svc.register_mailbox(domain.id, "hi@bad-dns.com", warmup_stage=WarmupStage.active)
    await session.flush()
    assert await svc.pick_available_mailbox() is None


# ---- 合规守卫 --------------------------------------------------------------
async def test_send_one_rejects_personal_email(session):
    clock = FakeClock(datetime(2026, 7, 7, tzinfo=UTC))
    svc = _build_service(session, clock)
    await _make_sendable_mailbox(svc)
    await session.flush()
    with pytest.raises(ComplianceError):
        await svc.send_one("someone@gmail.com", "Hi", "hello")


async def test_send_one_rejects_suppressed_email(session):
    clock = FakeClock(datetime(2026, 7, 7, tzinfo=UTC))
    svc = _build_service(session, clock)
    await _make_sendable_mailbox(svc)
    await svc.compliance.add_suppression("buyer@acme-trading.com", SuppressionReason.manual)
    await session.flush()
    with pytest.raises(ComplianceError):
        await svc.send_one("buyer@acme-trading.com", "Hi", "hello")


# ---- 硬退信闭环 ------------------------------------------------------------
async def test_hard_bounce_auto_suppresses(session):
    clock = FakeClock(datetime(2026, 7, 7, tzinfo=UTC))
    svc = _build_service(session, clock)
    await _make_sendable_mailbox(svc)
    await session.flush()

    # fake sender 对该地址确定性返回 hard_bounce
    bouncing = "buyer5@acme-trading.com"
    outcome = await svc.send_one(bouncing, "Hi", "hello")

    assert outcome.bounced is True
    assert outcome.message.bounced is True
    assert outcome.message.status == "bounced"
    # 自动进抑制列表，之后再发会被合规拦截
    assert await svc.compliance.is_suppressed(bouncing)
    with pytest.raises(ComplianceError):
        await svc.send_one(bouncing, "Hi again", "hello")


async def test_send_one_returns_spam_assessment(session):
    clock = FakeClock(datetime(2026, 7, 7, tzinfo=UTC))
    svc = _build_service(session, clock)
    await _make_sendable_mailbox(svc)
    await session.flush()

    outcome = await svc.send_one(
        "buyer0@acme-trading.com",
        "FREE cash guarantee!!!",  # 命中多个垃圾词 → 高分
        "act now click here for your winner discount",
    )
    assert outcome.accepted is True
    assert outcome.spam_score > 0
    assert outcome.spam_warnings


# ---- 序列「回复即停」------------------------------------------------------
async def test_sequence_ticks_and_schedules_next(session):
    clock = FakeClock(datetime(2026, 7, 7, tzinfo=UTC))
    svc = _build_service(session, clock)
    await _make_sendable_mailbox(svc)
    await session.flush()

    steps = [
        {"wait_days": 0, "subject": "step1", "body": "hello"},
        {"wait_days": 3, "subject": "step2", "body": "follow up"},
    ]
    enr = await svc.enroll("lead-1", "camp-1", "buyer0@acme-trading.com", steps)

    report = await svc.tick_sequences()
    assert report.sent == 1
    assert enr.step_index == 1
    assert enr.state is SequenceState.active
    # 下一步排到 +3 天
    assert enr.next_action_at == clock.now() + timedelta(days=3)
    assert await _count_to(session, "buyer0@acme-trading.com") == 1


async def test_sequence_stops_on_reply(session):
    clock = FakeClock(datetime(2026, 7, 7, tzinfo=UTC))
    svc = _build_service(session, clock)
    await _make_sendable_mailbox(svc)
    await session.flush()

    steps = [
        {"wait_days": 0, "subject": "step1", "body": "hello"},
        {"wait_days": 3, "subject": "step2", "body": "follow up"},
    ]
    email = "buyer0@acme-trading.com"
    enr = await svc.enroll("lead-1", "camp-1", email, steps)

    await svc.tick_sequences()  # 发出第 1 步
    assert await _count_to(session, email) == 1

    # 收到回复 → 停止后续
    stopped = await svc.record_reply(email)
    assert stopped == 1
    assert enr.state is SequenceState.replied

    # 即便把下一步设为「立即到期」，再 tick 也不会再发（回复即停）
    enr.next_action_at = clock.now()
    await session.flush()
    report = await svc.tick_sequences()
    assert report.sent == 0
    assert await _count_to(session, email) == 1

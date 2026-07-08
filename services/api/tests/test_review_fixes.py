"""对抗性审查发现的问题——修复后的回归测试。

每个测试对应一条被验证为真的 bug，锁死修复、防止回归。
"""
from __future__ import annotations

from datetime import UTC, datetime

from app.core.errors import ComplianceError
from app.domain.contracts import (
    CompanyCandidate,
    OutboundEmail,
    ReplyClassification,
    SendResult,
)
from app.domain.enums import DataSourceType, ReplyIntent, SequenceState, WarmupStage
from app.domain.rules import classify_email_type, is_free_email_domain
from app.modules.compliance.service import ComplianceService
from app.modules.sending.repository import SendingRepository
from app.modules.sending.service import SendingService


class FakeClock:
    def __init__(self, now: datetime):
        self._now = now

    def now(self) -> datetime:
        return self._now


class SoftFailSender:
    """总是"软失败"（未被接受、非硬退信）的发送方，模拟 SMTP 4xx/超时。"""

    async def send(self, email: OutboundEmail) -> SendResult:
        self.last = email
        return SendResult(accepted=False, error="temporary_failure")


class OkSender:
    async def send(self, email: OutboundEmail) -> SendResult:
        self.last = email
        return SendResult(accepted=True, message_id="ok-1")


def _svc(session, sender, clock):
    return SendingService(
        repo=SendingRepository(session),
        sender=sender,
        clock=clock,
        compliance=ComplianceService(session),
    )


async def _sendable_mailbox(svc):
    d = await svc.register_domain("s.com", spf_ok=True, dkim_ok=True, dmarc_ok=True, reputation=80)
    return await svc.register_mailbox(d.id, "hi@s.com", warmup_stage=WarmupStage.active)


# ---- 1. 瞬态失败不该把线索永久停用（critical）--------------------------------
async def test_quota_full_defers_not_stops(session):
    """无可用邮箱(额度满)→ 顺延重试，enrollment 保持 active，绝不置 stopped。"""
    clock = FakeClock(datetime(2026, 1, 1, tzinfo=UTC))
    svc = _svc(session, OkSender(), clock)
    # 不注册任何发信邮箱 → pick_available_mailbox 返回 None → send_one 抛 ValidationError
    step = {"step": 1, "wait_days": 0, "subject": "hi", "body": "b"}
    await svc.enroll("L1", "C1", "buyer@corp.com", [step])
    report = await svc.tick_sequences()
    assert report.deferred == 1 and report.sent == 0
    enr = (await svc.repo.enrollments_by_email("buyer@corp.com", (SequenceState.active,)))
    assert len(enr) == 1 and enr[0].state == SequenceState.active  # 仍 active，未被丢弃
    assert enr[0].step_index == 0  # step 未推进


async def test_soft_fail_does_not_advance_step(session):
    """软失败 → 不推进 step、不停用，顺延重试（不白占额度跳过该封）。"""
    clock = FakeClock(datetime(2026, 1, 1, tzinfo=UTC))
    svc = _svc(session, SoftFailSender(), clock)
    await _sendable_mailbox(svc)
    step = {"step": 1, "wait_days": 0, "subject": "hi", "body": "b"}
    await svc.enroll("L1", "C1", "buyer@corp.com", [step])
    report = await svc.tick_sequences()
    assert report.sent == 0 and report.deferred == 1
    enr = (await svc.repo.enrollments_by_email("buyer@corp.com", (SequenceState.active,)))
    assert enr[0].step_index == 0  # 软失败不推进，下轮会重试


async def test_success_advances_and_injects_unsubscribe(session):
    """成功发送 → 推进 step；且每封都带 List-Unsubscribe 头（合规红线）。"""
    clock = FakeClock(datetime(2026, 1, 1, tzinfo=UTC))
    sender = OkSender()
    svc = _svc(session, sender, clock)
    await _sendable_mailbox(svc)
    await svc.enroll("L1", "C1", "buyer@corp.com", [
        {"step": 1, "wait_days": 0, "subject": "hi", "body": "b"},
        {"step": 2, "wait_days": 3, "subject": "hi2", "body": "b2"},
    ])
    report = await svc.tick_sequences()
    assert report.sent == 1
    assert "List-Unsubscribe" in sender.last.headers
    assert "List-Unsubscribe-Post" in sender.last.headers


# ---- 2. 合规守卫仍拦个人邮箱（回归）------------------------------------------
async def test_personal_email_still_blocked(session):
    clock = FakeClock(datetime(2026, 1, 1, tzinfo=UTC))
    svc = _svc(session, OkSender(), clock)
    await _sendable_mailbox(svc)
    import pytest
    with pytest.raises(ComplianceError):
        await svc.send_one("someone@gmail.com", "hi", "b")


def test_free_email_subdomain_and_regional():
    """子域(mail.qq.com)与区域性免费邮箱被识别为个人邮箱；企业域不误伤。"""
    assert is_free_email_domain("mail.qq.com")          # 子域
    assert is_free_email_domain("web.de")               # 区域性
    assert classify_email_type("x@notgmail.com").value == "corporate"  # 不误伤含子串的企业域
    assert classify_email_type("x@gmail.com").value == "personal"


# ---- 3. 退订端点签名校验 + 抑制（合规）--------------------------------------
async def test_unsubscribe_suppresses(session):
    clock = FakeClock(datetime(2026, 1, 1, tzinfo=UTC))
    svc = _svc(session, OkSender(), clock)
    n = await svc.record_unsubscribe("buyer@corp.com")
    assert await svc.compliance.is_suppressed("buyer@corp.com")
    assert n == 0  # 无进行中序列时停 0 条，但已抑制


async def test_bounce_suppresses(session):
    """入站退信 record_bounce → 进抑制列表（后续活动不再发）。"""
    clock = FakeClock(datetime(2026, 1, 1, tzinfo=UTC))
    svc = _svc(session, OkSender(), clock)
    await svc.record_bounce("dead@corp.com")
    assert await svc.compliance.is_suppressed("dead@corp.com")


# ---- 4. 签名工具：防开放重定向/伪造退订 -------------------------------------
def test_signature_roundtrip_and_tamper():
    from app.core.security import sign, verify
    msg = "unsub:buyer@corp.com"
    assert verify(msg, sign(msg))
    assert not verify(msg, "deadbeef")          # 错签名拒绝
    assert not verify(msg, "")                    # 空签名拒绝
    assert not verify("unsub:other@corp.com", sign(msg))  # 换 email 拒绝


# ---- 5. 跨源去重合并信号（不丢海关信号）------------------------------------
def test_dedup_merge_preserves_signals():
    from app.modules.leads.service import LeadService
    search = CompanyCandidate(name="Acme", domain="acme.com",
                              source_type=DataSourceType.search_engine,
                              raw={"serper": {"position": 1}})
    customs = CompanyCandidate(name="Acme", domain="acme.com", country="US",
                               source_type=DataSourceType.customs,
                               raw={"customs": {"shipments": 42}})
    merged = LeadService._merge_candidates(search, customs)
    assert merged.raw.get("customs", {}).get("shipments") == 42  # 海关信号保留
    assert merged.raw.get("serper")                               # 原信号也在
    assert merged.country == "US"                                 # 缺失字段被补


# ---- 6. 低置信度回复不触发不可逆动作 ----------------------------------------
async def test_low_confidence_reply_needs_review():
    """低置信度分类 → needs_human_review，不改 CRM/不停序列（用 orchestration 的路由纯逻辑）。"""
    from app.modules.orchestration.service import OrchestrationService

    orch = OrchestrationService.__new__(OrchestrationService)  # 只测纯路由，不需依赖
    actions = await orch._route_actions(
        "x@corp.com", ReplyClassification(intent=ReplyIntent.interested, confidence=0.3)
    )
    assert actions == ["needs_human_review"]

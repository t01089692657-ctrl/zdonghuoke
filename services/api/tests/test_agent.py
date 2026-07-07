"""agent 模块测试（全程 fake LLM，ADAPTER_MODE 默认 local，确定性、零外部调用）。

覆盖：研究素材卡结构、字段约束式写信、回复分类的规则前置与 LLM 兜底、人审 HITL 通过率。
"""
from __future__ import annotations

from app.adapters.fake.llm import FakeLLM
from app.domain.contracts import GeneratedEmail, ResearchBrief
from app.domain.enums import ApprovalStatus, ReplyIntent
from app.modules.agent.model_router import ModelRouter
from app.modules.agent.repository import AgentRepository
from app.modules.agent.service import AgentService


def _build_service(session) -> AgentService:
    return AgentService(router=ModelRouter(FakeLLM()), repo=AgentRepository(session))


async def test_research_returns_complete_brief(session):
    svc = _build_service(session)
    brief = await svc.research("acme-imports.com")

    assert isinstance(brief, ResearchBrief)
    assert brief.company_domain == "acme-imports.com"
    assert brief.what_they_do  # 非空
    assert brief.who_they_sell_to
    assert brief.signals  # 至少一条可引用信号
    assert brief.approach_hint


async def test_research_uses_cache_second_time(session):
    svc = _build_service(session)
    first = await svc.research("acme-imports.com")
    second = await svc.research("acme-imports.com")
    # 命中缓存 → 内容一致，且没有重复落库（唯一约束不冲突即证明走了缓存）
    assert second.model_dump() == first.model_dump()
    cached = await svc.repo.get_cached_brief("acme-imports.com")
    assert cached is not None


async def test_write_email_has_subject_body_and_evidence(session):
    svc = _build_service(session)
    brief = await svc.research("acme-imports.com")
    email = await svc.write_email(
        brief,
        product_info={"name": "LED panel", "moq": 500},
        contact={"first_name": "Sam", "title": "Buyer"},
    )

    assert isinstance(email, GeneratedEmail)
    assert email.subject.strip()
    assert email.body.strip()
    assert email.language == "en"
    assert email.personalization_evidence  # 个性化证据非空（可解释、防编造）


async def test_classify_reply_rule_shortcut_unsubscribe(session):
    svc = _build_service(session)
    result = await svc.classify_reply("Please unsubscribe me from all future emails.")
    # 规则前置：命中 unsubscribe，高置信度、零 LLM 成本
    assert result.intent is ReplyIntent.unsubscribe
    assert result.confidence >= 0.9


async def test_classify_reply_falls_back_to_llm(session):
    svc = _build_service(session)
    result = await svc.classify_reply("Thanks for reaching out, tell me more about pricing.")
    # 普通文本走 LLM → 返回合法的 ReplyIntent 枚举值
    assert isinstance(result.intent, ReplyIntent)
    assert 0.0 <= result.confidence <= 1.0


async def test_hitl_approval_rate_is_half(session):
    svc = _build_service(session)
    email_a = GeneratedEmail(
        subject="Reliable supply", body="Hello, quick note.", personalization_evidence=["signal"]
    )
    email_b = GeneratedEmail(
        subject="Quick intro", body="Hi there, another note.", personalization_evidence=["signal"]
    )
    draft_a = await svc.submit_draft("camp-1", "lead-1", email_a)
    draft_b = await svc.submit_draft("camp-1", "lead-2", email_b)

    # 提交后两条都在待审队列
    pending = await svc.list_pending()
    assert len(pending) == 2

    await svc.approve(draft_a.id, reviewer="alice")
    await svc.reject(draft_b.id, reviewer="alice", reason="太生硬")

    assert await svc.approval_rate() == 0.5
    stats = await svc.approval_stats()
    assert stats["approved"] == 1
    assert stats["rejected"] == 1
    assert stats["pending"] == 0

    # 状态确实落到审批枚举上
    reloaded = await svc.repo.get_draft(draft_a.id)
    assert reloaded is not None
    assert reloaded.status == ApprovalStatus.approved

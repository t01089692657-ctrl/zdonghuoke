"""端到端集成测试：完整获客闭环（全程 fake 适配器，确定性、零外部调用）。

覆盖链路：找客户 → 建活动加目标 → AI 备信(HITL 草稿) → 人审批准 →
launch 入队 → tick 发送 → 入站回复分诊（退订→抑制；意向→CRM 跃迁）。
这是「系统作为一个整体是否成立」的守门测试。
"""
from __future__ import annotations

from app.adapters.fake.data_sources import FakeCustomsSource, FakeSearchSource
from app.adapters.fake.enrichment import FakeHunterEnrichment, FakeSnovEnrichment
from app.adapters.fake.llm import FakeLLM
from app.adapters.fake.sender import FakeEmailSender
from app.adapters.fake.verifier import FakeEmailVerifier
from app.adapters.system_clock import SystemClock
from app.domain.contracts import LeadSearchQuery, ReplyClassification
from app.domain.enums import ReplyIntent
from app.modules.agent.model_router import ModelRouter
from app.modules.agent.repository import AgentRepository
from app.modules.agent.service import AgentService
from app.modules.campaigns.repository import CampaignRepository
from app.modules.campaigns.service import CampaignService
from app.modules.compliance.service import ComplianceService
from app.modules.crm.repository import CrmRepository
from app.modules.crm.service import CrmService
from app.modules.enrichment.service import EnrichmentService
from app.modules.leads.repository import LeadRepository
from app.modules.leads.service import LeadService
from app.modules.orchestration.service import OrchestrationService, render_template
from app.modules.sending.repository import SendingRepository
from app.modules.sending.service import SendingService


def _build(session) -> tuple[OrchestrationService, LeadService, ComplianceService]:
    clock = SystemClock()
    compliance = ComplianceService(session)
    leads_repo = LeadRepository(session)
    lead_svc = LeadService(
        repo=leads_repo,
        data_sources=(FakeSearchSource(), FakeCustomsSource()),
        enrichment=EnrichmentService(
            providers=(FakeHunterEnrichment(), FakeSnovEnrichment()),
            verifier=FakeEmailVerifier(),
        ),
        clock=clock,
    )
    orch = OrchestrationService(
        campaigns=CampaignService(CampaignRepository(session)),
        agent=AgentService(ModelRouter(FakeLLM()), AgentRepository(session)),
        sending=SendingService(
            repo=SendingRepository(session),
            sender=FakeEmailSender(),
            clock=clock,
            compliance=compliance,
        ),
        crm=CrmService(CrmRepository(session)),
        leads=leads_repo,
    )
    return orch, lead_svc, compliance


async def _seed_campaign_with_targets(session, orch, lead_svc) -> str:
    """造线索 → 建活动 → 加目标 → 激活，返回 campaign_id。"""
    await lead_svc.discover(
        LeadSearchQuery(keywords=["solar light"], countries=["US"], limit=10), enrich=True
    )
    await session.flush()
    campaign = await orch.campaigns.create_campaign(name="集成测试活动", icp_config={})
    await orch.campaigns.add_targets_from_leads(campaign.id)
    await orch.campaigns.activate(campaign.id)
    await session.flush()
    return campaign.id


async def test_full_loop_prepare_approve_launch_tick(session):
    orch, lead_svc, _ = _build(session)
    campaign_id = await _seed_campaign_with_targets(session, orch, lead_svc)

    # 1) AI 备信：每个目标一封草稿；重复 prepare 幂等
    r1 = await orch.prepare_campaign(campaign_id, {"product": "solar wall light", "moq": "500"})
    assert r1["drafted"] > 0
    r2 = await orch.prepare_campaign(campaign_id, {"product": "solar wall light"})
    assert r2["drafted"] == 0 and r2["skipped"] >= r1["drafted"]

    # 2) 未批准前 launch：全部等待人审，不发一封
    r = await orch.launch_approved(campaign_id)
    assert r["enrolled"] == 0 and r["waiting_approval"] > 0

    # 3) 人审批准全部草稿 → launch 入队
    for draft in await orch.agent.list_pending():
        await orch.agent.approve(draft.id, reviewer="pm")
    r = await orch.launch_approved(campaign_id)
    assert r["enrolled"] > 0

    # 4) 注册达标发信域+邮箱后 tick：真正走发送（fake sender）
    d = await orch.sending.register_domain("mail.zdhk.io", spf_ok=True, dkim_ok=True, dmarc_ok=True)
    await orch.sending.register_mailbox(d.id, "outreach@mail.zdhk.io")
    await session.flush()
    result = await orch.tick()
    assert result["sequences"]["sent"] >= 1  # 至少发出一封（受预热日限约束）


async def test_inbound_unsubscribe_suppresses_and_stops(session):
    orch, lead_svc, compliance = _build(session)
    campaign_id = await _seed_campaign_with_targets(session, orch, lead_svc)
    await orch.quick_launch(campaign_id)  # 模板直发模式入队
    await session.flush()

    # 找一个已入队的邮箱，模拟其回信要求退订（规则前置分类，确定性）
    targets = await orch.campaigns.list_targets(campaign_id)
    enrolled = [t for t in targets if t.state == "enrolled" and t.to_email]
    assert enrolled, "quick_launch 后应有已入队目标"
    victim = enrolled[0].to_email

    result = await orch.handle_inbound(victim, "Please unsubscribe me from this list.")
    assert result["intent"] == "unsubscribe"
    assert await compliance.is_suppressed(victim)  # 已进全局抑制列表
    # 后续任何发送尝试都会被合规守卫拒绝
    assert not await compliance.is_sendable(victim)


async def test_inbound_interested_moves_crm_stage(session):
    orch, lead_svc, _ = _build(session)
    campaign_id = await _seed_campaign_with_targets(session, orch, lead_svc)
    await orch.quick_launch(campaign_id)
    await session.flush()

    targets = await orch.campaigns.list_targets(campaign_id)
    enrolled = [t for t in targets if t.state == "enrolled" and t.to_email]
    target = enrolled[0]

    # 直接驱动动作路由（绕过 LLM 分类的不确定性，专测编排逻辑）
    actions = await orch._route_actions(
        target.to_email,
        ReplyClassification(intent=ReplyIntent.interested, confidence=0.95),
    )
    assert any(a.startswith("sequence_stopped") for a in actions)
    assert "crm_stage->interested" in actions
    company = await orch.leads.get(target.company_id)
    assert str(company.stage) == "interested"


def test_render_template_placeholders():
    out = render_template("Hi {{first_name}}, about {{company}}", company="Acme", first_name="Li")
    assert out == "Hi Li, about Acme"
    fallback = render_template("Hi {{first_name}} at {{company}}")
    assert "{{" not in fallback  # 缺失变量必须有兜底，不能发出残缺模板

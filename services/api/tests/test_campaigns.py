"""campaigns 模块测试：建活动（默认 4 步序列）、激活、从线索加目标。"""
from __future__ import annotations

from itertools import accumulate

import pytest

from app.core.errors import ValidationError
from app.domain.enums import CampaignStatus, EmailStatus, EmailType
from app.modules.campaigns.repository import CampaignRepository
from app.modules.campaigns.service import CampaignService, default_sequence
from app.modules.leads.models import Company, Contact


def _svc(session) -> CampaignService:
    return CampaignService(repo=CampaignRepository(session))


async def _seed_leads(session) -> list[Company]:
    """造两家公司及若干联系人：其中 2 个可发送、2 个不可发送。"""
    acme = Company(
        name="Acme Trading",
        domain="acme.com",
        country="US",
        dedup_fingerprint="d:acme.com",
        source_type="search_engine",
        score=80.0,
    )
    acme.contacts = [
        Contact(  # 可发送：企业邮箱 + valid
            email="ceo@acme.com",
            email_type=EmailType.corporate,
            email_status=EmailStatus.valid,
        ),
        Contact(  # 不可发送：个人邮箱
            email="ceo@gmail.com",
            email_type=EmailType.personal,
            email_status=EmailStatus.valid,
        ),
        Contact(  # 不可发送：企业邮箱但 invalid
            email="bounce@acme.com",
            email_type=EmailType.corporate,
            email_status=EmailStatus.invalid,
        ),
    ]
    globex = Company(
        name="Globex",
        domain="globex.com",
        country="DE",
        dedup_fingerprint="d:globex.com",
        source_type="customs",
        score=60.0,
    )
    globex.contacts = [
        Contact(  # 可发送：企业邮箱 + unknown（未验证但允许尝试）
            email="buyer@globex.com",
            email_type=EmailType.corporate,
            email_status=EmailStatus.unknown,
        ),
    ]
    session.add_all([acme, globex])
    await session.flush()
    return [acme, globex]


def test_default_sequence_is_four_step_3_7_7():
    seq = default_sequence()
    assert len(seq) == 4
    assert [s["step"] for s in seq] == [1, 2, 3, 4]
    assert [s["wait_days"] for s in seq] == [0, 3, 7, 7]
    # 累计触达日为 Day 0/3/10/17
    assert list(accumulate(s["wait_days"] for s in seq)) == [0, 3, 10, 17]
    assert all(s["subject"] and s["body"] for s in seq)


async def test_create_campaign_uses_default_sequence(session):
    svc = _svc(session)
    campaign = await svc.create_campaign(name="Q3 Solar Outreach", created_by="alice")
    assert campaign.status is CampaignStatus.draft
    assert len(campaign.sequence_def) == 4
    assert [s["wait_days"] for s in campaign.sequence_def] == [0, 3, 7, 7]
    assert campaign.created_by == "alice"


async def test_activate_draft_to_active(session):
    svc = _svc(session)
    campaign = await svc.create_campaign(name="Activate Me")
    activated = await svc.activate(campaign.id)
    assert activated.status is CampaignStatus.active
    # 已激活的活动不能再次激活
    with pytest.raises(ValidationError):
        await svc.activate(campaign.id)


async def test_add_targets_from_leads_picks_sendable(session):
    await _seed_leads(session)
    svc = _svc(session)
    campaign = await svc.create_campaign(name="Targeting")

    result = await svc.add_targets_from_leads(campaign.id)
    await session.flush()

    # 4 个联系人里只有 2 个可发送（企业邮箱 + valid/unknown）
    assert result["added"] == 2
    assert result["skipped"] == 2
    emails = {t.to_email for t in result["targets"]}
    assert emails == {"ceo@acme.com", "buyer@globex.com"}
    assert all(t.state == "pending" for t in result["targets"])


async def test_add_targets_is_idempotent(session):
    await _seed_leads(session)
    svc = _svc(session)
    campaign = await svc.create_campaign(name="Dedup")

    first = await svc.add_targets_from_leads(campaign.id)
    await session.flush()
    second = await svc.add_targets_from_leads(campaign.id)
    await session.flush()

    assert first["added"] == 2
    assert second["added"] == 0  # 已入队的 contact 不重复加

    # 可被 sending 消费的 pending 目标为 2 条
    enrollable = await svc.enrollable_targets(campaign.id)
    assert len(enrollable) == 2


async def test_add_targets_by_company_ids_filter(session):
    companies = await _seed_leads(session)
    acme = companies[0]
    svc = _svc(session)
    campaign = await svc.create_campaign(name="Only Acme")

    result = await svc.add_targets_from_leads(campaign.id, company_ids=[acme.id])
    await session.flush()

    assert result["added"] == 1  # 仅 Acme 的 1 个可发送联系人
    assert result["targets"][0].to_email == "ceo@acme.com"

"""crm 模块测试：阶段跃迁写入并生成 activity、管道分组、撞单命中。"""
from __future__ import annotations

import pytest

from app.core.errors import NotFoundError
from app.domain.enums import LeadStage
from app.modules.crm.repository import CrmRepository
from app.modules.crm.service import CrmService
from app.modules.leads.models import Company


def _svc(session) -> CrmService:
    return CrmService(repo=CrmRepository(session))


async def _mk_company(session, name, domain, stage=LeadStage.new, score=0.0) -> Company:
    company = Company(
        name=name,
        domain=domain,
        country="US",
        dedup_fingerprint=f"d:{domain}",
        source_type="search_engine",
        stage=stage,
        score=score,
    )
    company.contacts = []
    session.add(company)
    await session.flush()
    return company


async def test_change_stage_writes_and_logs_activity(session):
    company = await _mk_company(session, "Acme", "acme.com")
    svc = _svc(session)

    updated = await svc.change_stage(company.id, LeadStage.contacted, actor="alice")
    assert updated.stage is LeadStage.contacted

    timeline = await svc.timeline(company.id)
    assert len(timeline) == 1
    act = timeline[0]
    assert act.type == "stage_change"
    assert act.content == "new -> contacted"
    assert act.actor == "alice"


async def test_change_stage_is_idempotent_when_same(session):
    company = await _mk_company(session, "Acme", "acme.com", stage=LeadStage.replied)
    svc = _svc(session)
    # 变更到相同阶段：不重复记录
    await svc.change_stage(company.id, LeadStage.replied)
    timeline = await svc.timeline(company.id)
    assert timeline == []


async def test_change_stage_missing_company(session):
    svc = _svc(session)
    with pytest.raises(NotFoundError):
        await svc.change_stage("no-such-id", LeadStage.contacted)


async def test_log_activity_appears_in_timeline(session):
    company = await _mk_company(session, "Globex", "globex.com")
    svc = _svc(session)
    await svc.log_activity(company.id, type="note", content="打过电话，让我下周再联系", actor="bob")
    timeline = await svc.timeline(company.id)
    assert len(timeline) == 1
    assert timeline[0].type == "note"
    assert timeline[0].actor == "bob"


async def test_list_pipeline_groups_by_stage(session):
    await _mk_company(session, "A", "a.com", stage=LeadStage.new)
    await _mk_company(session, "B", "b.com", stage=LeadStage.new)
    await _mk_company(session, "C", "c.com", stage=LeadStage.contacted)
    await _mk_company(session, "D", "d.com", stage=LeadStage.interested)
    svc = _svc(session)

    pipeline = await svc.list_pipeline()
    counts = {row["stage"]: row["count"] for row in pipeline}
    assert counts[LeadStage.new] == 2
    assert counts[LeadStage.contacted] == 1
    assert counts[LeadStage.interested] == 1
    assert counts[LeadStage.won] == 0
    # 全部 7 个阶段都在（含数量为 0 的），且总数正确
    assert len(pipeline) == len(list(LeadStage))
    assert sum(row["count"] for row in pipeline) == 4
    # new 分组里能取到公司列表
    new_row = next(r for r in pipeline if r["stage"] is LeadStage.new)
    assert {c.name for c in new_row["companies"]} == {"A", "B"}


async def test_collision_check_hits_by_email(session):
    await _mk_company(session, "Acme", "acme.com")
    svc = _svc(session)

    hit = await svc.collision_check(email="newbuyer@acme.com")
    assert hit["collision"] is True
    assert hit["domain"] == "acme.com"
    assert {c.name for c in hit["matched"]} == {"Acme"}


async def test_collision_check_miss(session):
    await _mk_company(session, "Acme", "acme.com")
    svc = _svc(session)
    miss = await svc.collision_check(domain="unknown-co.com")
    assert miss["collision"] is False
    assert miss["matched"] == []

"""analytics 模块测试：造数据后 funnel/sources/summary 数字正确。"""
from __future__ import annotations

from app.domain.enums import EmailStatus, EmailType, LeadStage
from app.modules.analytics.repository import AnalyticsRepository
from app.modules.analytics.service import AnalyticsService
from app.modules.leads.models import Company, Contact


def _svc(session) -> AnalyticsService:
    return AnalyticsService(repo=AnalyticsRepository(session))


async def _seed(session) -> None:
    """3 家公司（不同阶段/来源/评分），带可发送与不可发送联系人。"""
    a = Company(
        name="A",
        domain="a.com",
        dedup_fingerprint="d:a.com",
        source_type="search_engine",
        stage=LeadStage.new,
        score=90.0,
    )
    a.contacts = [
        Contact(email="k@a.com", email_type=EmailType.corporate, email_status=EmailStatus.valid),
        Contact(  # 个人邮箱：不可发送
            email="k@gmail.com", email_type=EmailType.personal, email_status=EmailStatus.valid
        ),
    ]
    b = Company(
        name="B",
        domain="b.com",
        dedup_fingerprint="d:b.com",
        source_type="search_engine",
        stage=LeadStage.contacted,
        score=70.0,
    )
    b.contacts = [
        Contact(
            email="k@b.com", email_type=EmailType.corporate, email_status=EmailStatus.unknown
        ),
    ]
    c = Company(
        name="C",
        domain="c.com",
        dedup_fingerprint="d:c.com",
        source_type="customs",
        stage=LeadStage.new,
        score=50.0,
    )
    c.contacts = [
        Contact(  # 企业邮箱但 invalid：不可发送
            email="x@c.com", email_type=EmailType.corporate, email_status=EmailStatus.invalid
        ),
    ]
    session.add_all([a, b, c])
    await session.flush()


async def test_funnel_counts_by_stage(session):
    await _seed(session)
    svc = _svc(session)
    rows = await svc.funnel()

    counts = {row["stage"]: row["count"] for row in rows}
    assert counts[LeadStage.new] == 2
    assert counts[LeadStage.contacted] == 1
    assert counts[LeadStage.won] == 0
    assert len(rows) == len(list(LeadStage))  # 含空阶段


async def test_summary_numbers(session):
    await _seed(session)
    svc = _svc(session)
    data = await svc.summary()

    assert data["total_companies"] == 3
    assert data["total_contacts"] == 4
    # 可发送：k@a.com(valid) + k@b.com(unknown) = 2；个人邮箱与 invalid 均排除
    assert data["sendable_contacts"] == 2

    ratios = {s["stage"]: s["ratio"] for s in data["stages"]}
    assert ratios[LeadStage.new] == round(2 / 3, 4)
    assert ratios[LeadStage.contacted] == round(1 / 3, 4)
    assert sum(s["count"] for s in data["stages"]) == 3


async def test_source_breakdown(session):
    await _seed(session)
    svc = _svc(session)
    rows = await svc.lead_source_breakdown()
    by_source = {r["source_type"]: r for r in rows}

    assert by_source["search_engine"]["count"] == 2
    assert by_source["search_engine"]["avg_score"] == 80.0  # (90 + 70) / 2
    assert by_source["customs"]["count"] == 1
    assert by_source["customs"]["avg_score"] == 50.0


async def test_summary_empty_db(session):
    """空库不报错，占比为 0。"""
    svc = _svc(session)
    data = await svc.summary()
    assert data["total_companies"] == 0
    assert data["sendable_contacts"] == 0
    assert all(s["ratio"] == 0.0 for s in data["stages"])

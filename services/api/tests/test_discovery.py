"""端到端找客户流水线测试（全程用 fake 适配器）。

验证架构的核心闭环：多源检索→去重→富化→验证→评分→落库 全部跑通且确定性。
"""
from __future__ import annotations

from app.adapters.fake.data_sources import FakeCustomsSource, FakeSearchSource
from app.adapters.fake.enrichment import FakeHunterEnrichment, FakeSnovEnrichment
from app.adapters.fake.verifier import FakeEmailVerifier
from app.adapters.system_clock import SystemClock
from app.modules.enrichment.service import EnrichmentService
from app.modules.leads.repository import LeadRepository
from app.modules.leads.service import LeadService


def _build_service(session) -> LeadService:
    enrichment = EnrichmentService(
        providers=(FakeHunterEnrichment(), FakeSnovEnrichment()),
        verifier=FakeEmailVerifier(),
    )
    return LeadService(
        repo=LeadRepository(session),
        data_sources=(FakeSearchSource(), FakeCustomsSource()),
        enrichment=enrichment,
        clock=SystemClock(),
    )


async def test_discovery_pipeline_persists_and_scores(session, sample_query):
    svc = _build_service(session)
    result = await svc.discover(sample_query, enrich=True)
    await session.flush()

    assert result["discovered"] > 0
    assert result["new_companies"] > 0
    # 两个源检索同样的关键词 → 有可去重的重复
    assert result["merged_duplicates"] > 0
    for company in result["companies"]:
        assert 0 <= company.score <= 100
        assert company.score_reasons  # 评分必须可解释
        assert company.provenance  # 来源必须留痕


async def test_discovery_is_idempotent_by_fingerprint(session, sample_query):
    """同样的查询跑两次，不应重复建公司（去重生效）。"""
    svc = _build_service(session)
    first = await svc.discover(sample_query, enrich=False)
    await session.flush()
    second = await svc.discover(sample_query, enrich=False)
    await session.flush()

    assert second["new_companies"] == 0
    items, total = await svc.list_companies(offset=0, limit=100)
    assert total == first["new_companies"]


async def test_enrichment_waterfall_finds_contacts(session, sample_query):
    svc = _build_service(session)
    result = await svc.discover(sample_query, enrich=True)
    await session.flush()
    # fake 富化对部分域名命中，应至少找到一些联系人
    assert result["contacts_found"] >= 1

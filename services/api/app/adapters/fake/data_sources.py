"""fake 数据源：根据查询确定性地生成看起来合理的候选公司。

覆盖三个 P0 源（搜索/海关/地图），演示与测试用。真实适配器在 adapters/real。
"""
from __future__ import annotations

from app.adapters.fake._util import pick, stable_int
from app.domain.contracts import CompanyCandidate, LeadSearchQuery
from app.domain.enums import DataSourceType

_COUNTRIES = ["US", "DE", "GB", "FR", "NL", "AE", "SG", "BR", "AU", "CA", "IT", "ES"]
_INDUSTRIES = ["Wholesale", "Retail", "Manufacturing", "Distribution", "Import"]
_SUFFIX = ["Trading", "Global", "Imports", "Supply", "Group", "Industries", "Solutions"]
_TLD = ["com", "net", "de", "co.uk", "nl", "com.br", "com.au"]


def _make_company(seed: str, source: DataSourceType, i: int) -> CompanyCandidate:
    kw = seed.split()[0].title() if seed.strip() else "Acme"
    suffix = pick(_SUFFIX, seed, str(i))
    name = f"{kw} {suffix}"
    slug = f"{kw}{suffix}".lower()
    tld = pick(_TLD, seed, str(i), "tld")
    domain = f"{slug}.{tld}"
    country = pick(_COUNTRIES, seed, str(i), "c")
    industry = pick(_INDUSTRIES, seed, str(i), "ind")
    return CompanyCandidate(
        name=name,
        domain=domain,
        website=f"https://{domain}",
        country=country,
        industry=industry,
        description=f"{industry} of {seed or 'goods'} serving {country} market.",
        source_type=source,
        source_ref=f"fake-{source.value}-{stable_int(seed, str(i))}",
        raw={"seed": seed, "index": i},
    )


class _BaseFakeSource:
    _source: DataSourceType

    @property
    def source_type(self) -> DataSourceType:
        return self._source

    async def search(self, query: LeadSearchQuery) -> list[CompanyCandidate]:
        seed = " ".join(query.keywords) or (query.hs_code or query.industry or "goods")
        n = min(query.limit, 25)
        return [_make_company(seed, self._source, i) for i in range(n)]


class FakeSearchSource(_BaseFakeSource):
    _source = DataSourceType.search_engine


class FakeCustomsSource(_BaseFakeSource):
    """海关源：额外在 raw 里塞进采购信号（对标麦穗海关四维报表）。"""

    _source = DataSourceType.customs

    async def search(self, query: LeadSearchQuery) -> list[CompanyCandidate]:
        companies = await super().search(query)
        for c in companies:
            shipments = 5 + stable_int(c.name, "ship") % 95
            c.raw["customs"] = {
                "shipments_12m": shipments,
                "hs_code": query.hs_code or "unknown",
                "last_supplier_country": "CN",
            }
        return companies


class FakeMapsSource(_BaseFakeSource):
    _source = DataSourceType.maps

    async def search(self, query: LeadSearchQuery) -> list[CompanyCandidate]:
        companies = await super().search(query)
        for c in companies:
            c.raw["maps"] = {
                "rating": round(3.5 + (stable_int(c.name, "r") % 15) / 10, 1),
                "phone": f"+1-555-{stable_int(c.name, 'p') % 9000 + 1000}",
            }
        return companies

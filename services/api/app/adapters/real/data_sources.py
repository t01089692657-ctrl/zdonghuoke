"""真实数据源适配器。

已实现：Serper（Google 搜索 API，最易接入的真实找客户源）。
待接入（需商业数据合同，按 DataSourcePort 补充后在 build_real_data_sources 登记）：
  海关数据(ImportGenius/腾道)、Google Maps(Outscraper/Apify)。见 docs/06 接入指南。

设计：key 缺失时在「调用时」抛清晰错误，而非导入时，方便逐个数据源灰度接入。
"""
from __future__ import annotations

from urllib.parse import urlparse

import httpx
from tenacity import retry, stop_after_attempt, wait_exponential

from app.core.config import get_settings
from app.core.errors import ExternalServiceError
from app.core.logging import get_logger
from app.domain.contracts import CompanyCandidate, LeadSearchQuery
from app.domain.enums import DataSourceType
from app.ports.data_source import DataSourcePort

log = get_logger("real-datasource")


def _domain_of(url: str) -> str | None:
    try:
        host = urlparse(url).netloc.lower()
        return host[4:] if host.startswith("www.") else host or None
    except Exception:
        return None


class SerperSearchSource:
    """用 Serper.dev（Google 搜索 API）按关键词找公司。

    每条自然搜索结果 → 一个候选公司（取域名、标题、摘要）。真实、即时、覆盖广，
    适合作为第一个可用的找客户源。计费按查询次数，见 https://serper.dev 。
    """

    @property
    def source_type(self) -> DataSourceType:
        return DataSourceType.search_engine

    @retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, min=1, max=8))
    async def search(self, query: LeadSearchQuery) -> list[CompanyCandidate]:
        settings = get_settings()
        if not settings.serp_api_key:
            raise ExternalServiceError("SERP_API_KEY 未配置（Serper.dev）")

        q_terms = list(query.keywords)
        if query.industry:
            q_terms.append(query.industry)
        # 用「关键词 + importer/distributor/wholesaler」提升买家命中
        q = " ".join(q_terms) + " (importer OR distributor OR wholesaler)"
        gl = (query.countries[0].lower() if query.countries else "us")

        try:
            async with httpx.AsyncClient(timeout=30) as client:
                resp = await client.post(
                    "https://google.serper.dev/search",
                    headers={"X-API-KEY": settings.serp_api_key},
                    json={"q": q, "num": min(query.limit, 20), "gl": gl},
                )
                resp.raise_for_status()
                data = resp.json()
        except httpx.HTTPError as e:
            raise ExternalServiceError(f"Serper 搜索失败: {e}") from e

        out: list[CompanyCandidate] = []
        seen: set[str] = set()
        for item in data.get("organic", []):
            link = item.get("link", "")
            domain = _domain_of(link)
            if not domain or domain in seen:
                continue
            seen.add(domain)
            out.append(
                CompanyCandidate(
                    name=item.get("title", domain).split(" - ")[0].split(" | ")[0].strip(),
                    domain=domain,
                    website=f"https://{domain}",
                    country=query.countries[0] if query.countries else None,
                    industry=query.industry,
                    description=item.get("snippet"),
                    source_type=self.source_type,
                    source_ref=link,
                    raw={"serper": {"position": item.get("position")}},
                )
            )
        log.info("serper.search", q=q, results=len(out))
        return out


def build_real_data_sources() -> tuple[DataSourcePort, ...]:
    """登记启用的真实数据源。先上 Serper；海关/地图接入后追加到此元组。"""
    return (SerperSearchSource(),)

"""Apollo.io 适配器 —— 最全面的单一 B2B 数据源（2.7 亿+ 联系人）。

一家搞定「找公司 + 挖决策人邮箱」，是"最全面好用"的旗舰选择：
  · ApolloOrganizationSource —— 组织搜索，按行业/地区/关键词找目标公司（找客户源）
  · ApolloEnrichment        —— 按公司域名找决策人及其邮箱（富化）

接入：注册 https://apollo.io → Settings → Integrations → API → 生成 master API key，
填 APOLLO_API_KEY。请求头 X-Api-Key。文档 https://docs.apollo.io 。

注意（如实说明）：
- Apollo 的接口字段会迭代，且揭示邮箱(reveal_personal_emails)会消耗 credit；
  首次接入请对照其最新文档校验字段。本实现按 2025–2026 文档编写，缺 key 时调用处报错。
- 免费档有 credit 限制；付费档邮箱覆盖率与准确率是同类最高之一。
"""
from __future__ import annotations

from urllib.parse import urlparse

import httpx
from tenacity import retry, stop_after_attempt, wait_exponential

from app.core.config import get_settings
from app.core.errors import ExternalServiceError
from app.core.logging import get_logger
from app.domain.contracts import CompanyCandidate, EmailCandidate, LeadSearchQuery
from app.domain.enums import DataSourceType

log = get_logger("apollo")

_BASE = "https://api.apollo.io/api/v1"
# 决策人职级（找采购/负责人）
_SENIORITIES = ["owner", "founder", "c_suite", "partner", "vp", "head", "director", "manager"]


def _headers() -> dict:
    key = get_settings().apollo_api_key
    if not key:
        raise ExternalServiceError("APOLLO_API_KEY 未配置")
    return {"X-Api-Key": key, "Content-Type": "application/json", "Cache-Control": "no-cache"}


def _domain_of(url: str | None) -> str | None:
    if not url:
        return None
    try:
        host = urlparse(url if "//" in url else f"https://{url}").netloc.lower()
        return host[4:] if host.startswith("www.") else host or None
    except Exception:
        return None


def _is_real_email(email: str | None) -> bool:
    """Apollo 未解锁的邮箱会返回 email_not_unlocked@domain.com 之类占位，需过滤。"""
    return bool(email) and "not_unlocked" not in email and "@" in email


class ApolloOrganizationSource:
    """Apollo 组织搜索：按关键词/行业/地区找目标公司。"""

    @property
    def source_type(self) -> DataSourceType:
        return DataSourceType.search_engine

    @retry(stop=stop_after_attempt(3), wait=wait_exponential(min=1, max=8), reraise=True)
    async def search(self, query: LeadSearchQuery) -> list[CompanyCandidate]:
        payload: dict = {
            "page": 1,
            "per_page": min(query.limit, 25),
            "q_organization_keyword_tags": list(query.keywords),
        }
        if query.countries:
            payload["organization_locations"] = query.countries
        try:
            async with httpx.AsyncClient(timeout=30) as client:
                resp = await client.post(
                    f"{_BASE}/mixed_companies/search", headers=_headers(), json=payload
                )
                resp.raise_for_status()
                data = resp.json()
        except httpx.HTTPError as e:
            raise ExternalServiceError(f"Apollo 组织搜索失败: {e}") from e

        out: list[CompanyCandidate] = []
        for org in data.get("organizations", []) or data.get("accounts", []):
            domain = org.get("primary_domain") or _domain_of(org.get("website_url"))
            if not domain:
                continue
            out.append(
                CompanyCandidate(
                    name=org.get("name", domain),
                    domain=domain,
                    website=org.get("website_url") or f"https://{domain}",
                    country=(org.get("country")
                             or (query.countries[0] if query.countries else None)),
                    industry=org.get("industry") or query.industry,
                    description=(org.get("short_description") or None),
                    source_type=self.source_type,
                    source_ref=org.get("id"),
                    raw={"apollo_org_id": org.get("id")},
                )
            )
        log.info("apollo.org_search", results=len(out))
        return out


class ApolloEnrichment:
    """Apollo 人物搜索：按公司域名找决策人及其邮箱。"""

    @property
    def name(self) -> str:
        return "apollo"

    @retry(stop=stop_after_attempt(3), wait=wait_exponential(min=1, max=8), reraise=True)
    async def find_emails(
        self, domain: str, *, first_name: str | None = None, last_name: str | None = None
    ) -> list[EmailCandidate]:
        payload = {
            "page": 1,
            "per_page": 10,
            "q_organization_domains_list": [domain],
            "person_seniorities": _SENIORITIES,
            "reveal_personal_emails": True,
        }
        try:
            async with httpx.AsyncClient(timeout=30) as client:
                resp = await client.post(
                    f"{_BASE}/mixed_people/search", headers=_headers(), json=payload
                )
                resp.raise_for_status()
                data = resp.json()
        except httpx.HTTPError as e:
            raise ExternalServiceError(f"Apollo 人物搜索失败: {e}") from e

        out: list[EmailCandidate] = []
        for p in data.get("people", []):
            email = p.get("email")
            if not _is_real_email(email):
                continue
            out.append(
                EmailCandidate(
                    email=email.lower(),
                    first_name=p.get("first_name"),
                    last_name=p.get("last_name"),
                    title=p.get("title"),
                    confidence=0.9,  # Apollo 已做验证，给较高置信度
                    provider=self.name,
                )
            )
        log.info("apollo.people_search", domain=domain, found=len(out))
        return out

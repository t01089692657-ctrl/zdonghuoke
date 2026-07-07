"""真实富化适配器。已实现 Hunter.io（域名→邮箱）。可再加 Snov 组成瀑布。

key 缺失时在调用处抛错，业务层瀑布逻辑会自动跳到下一家（见 EnrichmentService）。
"""
from __future__ import annotations

import re

import httpx
from tenacity import retry, stop_after_attempt, wait_exponential

from app.core.config import get_settings
from app.core.errors import ExternalServiceError
from app.core.logging import get_logger
from app.domain.contracts import EmailCandidate
from app.ports.data_source import EnrichmentPort

log = get_logger("real-enrich")

_EMAIL_RE = re.compile(r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}")
# 抓官网时优先看这些页面
_CONTACT_PATHS = ("", "/contact", "/contact-us", "/about", "/about-us", "/impressum")


class HunterEnrichment:
    """Hunter.io 域名搜索：给定公司域名，返回该域名下的公开邮箱与职位。

    文档 https://hunter.io/api-documentation 。按 credit 计费。
    """

    @property
    def name(self) -> str:
        return "hunter"

    @retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, min=1, max=8))
    async def find_emails(
        self, domain: str, *, first_name: str | None = None, last_name: str | None = None
    ) -> list[EmailCandidate]:
        settings = get_settings()
        if not settings.hunter_api_key:
            raise ExternalServiceError("HUNTER_API_KEY 未配置")

        params = {"domain": domain, "api_key": settings.hunter_api_key, "limit": "10"}
        try:
            async with httpx.AsyncClient(timeout=30) as client:
                resp = await client.get("https://api.hunter.io/v2/domain-search", params=params)
                resp.raise_for_status()
                data = resp.json()
        except httpx.HTTPError as e:
            raise ExternalServiceError(f"Hunter 调用失败: {e}") from e

        out: list[EmailCandidate] = []
        for e in data.get("data", {}).get("emails", []):
            out.append(
                EmailCandidate(
                    email=e.get("value", ""),
                    first_name=e.get("first_name"),
                    last_name=e.get("last_name"),
                    title=e.get("position"),
                    confidence=(e.get("confidence") or 0) / 100.0,
                    provider=self.name,
                )
            )
        # 优先决策人/采购相关职位排前
        out.sort(key=lambda c: (0 if c.title and any(
            k in c.title.lower() for k in ("purchas", "procure", "buyer", "ceo", "founder", "owner")
        ) else 1, -c.confidence))
        return [c for c in out if c.email]


class WebsiteEmailScraper:
    """免费富化：抓公司官网 contact/about 页里公开的邮箱。零 API 费用。

    覆盖率不如 Hunter，但对"官网留了 info@/sales@"的中小企业很有效，可作免费首选或兜底。
    只抓公开页面、遵守常识频控；命中的邮箱丢给验证环节筛。
    """

    @property
    def name(self) -> str:
        return "website"

    async def find_emails(
        self, domain: str, *, first_name: str | None = None, last_name: str | None = None
    ) -> list[EmailCandidate]:
        found: dict[str, EmailCandidate] = {}
        async with httpx.AsyncClient(
            timeout=15, follow_redirects=True, headers={"User-Agent": "ZDHK-LeadBot/1.0"}
        ) as client:
            for path in _CONTACT_PATHS:
                url = f"https://{domain}{path}"
                try:
                    resp = await client.get(url)
                    if resp.status_code != 200:
                        continue
                    for m in _EMAIL_RE.findall(resp.text):
                        addr = m.lower()
                        # 跳过明显的图片/资源误匹配与非本域噪声
                        if addr.endswith((".png", ".jpg", ".gif", ".webp", ".svg")):
                            continue
                        if addr not in found:
                            found[addr] = EmailCandidate(
                                email=addr,
                                confidence=0.6 if domain in addr else 0.4,
                                provider=self.name,
                            )
                except httpx.HTTPError:
                    continue
        # 本域邮箱优先
        result = sorted(
            found.values(), key=lambda c: (0 if domain in c.email else 1, -c.confidence)
        )
        log.info("website.scrape", domain=domain, found=len(result))
        return result[:10]


def build_real_enrichment() -> tuple[EnrichmentPort, ...]:
    """按 ENRICH_PROVIDER 选富化（瀑布顺序=命中即停）：

    apollo(最全) / hunter(付费) / website(免费抓官网) / hunter+website /
    apollo+hunter+website(全瀑布)
    """
    provider = get_settings().enrich_provider.lower()
    if provider == "website":
        return (WebsiteEmailScraper(),)
    if provider == "hunter+website":
        return (HunterEnrichment(), WebsiteEmailScraper())
    if provider in ("apollo", "apollo+hunter+website"):
        from app.adapters.real.apollo import ApolloEnrichment

        if provider == "apollo":
            return (ApolloEnrichment(),)
        # 全瀑布：最全的 Apollo 优先 → Hunter 补 → 免费抓官网兜底
        return (ApolloEnrichment(), HunterEnrichment(), WebsiteEmailScraper())
    return (HunterEnrichment(),)

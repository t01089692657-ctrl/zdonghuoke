"""真实富化适配器。已实现 Hunter.io（域名→邮箱）。可再加 Snov 组成瀑布。

key 缺失时在调用处抛错，业务层瀑布逻辑会自动跳到下一家（见 EnrichmentService）。
"""
from __future__ import annotations

import httpx
from tenacity import retry, stop_after_attempt, wait_exponential

from app.core.config import get_settings
from app.core.errors import ExternalServiceError
from app.domain.contracts import EmailCandidate
from app.ports.data_source import EnrichmentPort


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


def build_real_enrichment() -> tuple[EnrichmentPort, ...]:
    """瀑布顺序（命中即停）。先 Hunter；接入 Snov 后追加到元组尾部作为兜底。"""
    return (HunterEnrichment(),)

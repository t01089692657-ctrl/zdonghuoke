"""富化服务：对一个域名跑瀑布富化，再验证邮箱，返回带验证状态的联系人。

只依赖端口（EnrichmentPort / EmailVerifierPort），不关心背后是 fake 还是 Hunter/Snov。
"""
from __future__ import annotations

from dataclasses import dataclass

from app.core.logging import get_logger
from app.domain.contracts import EmailCandidate, VerificationResult
from app.ports.data_source import EmailVerifierPort, EnrichmentPort

log = get_logger("enrichment")


@dataclass
class EnrichedContact:
    candidate: EmailCandidate
    verification: VerificationResult


class EnrichmentService:
    def __init__(
        self,
        providers: tuple[EnrichmentPort, ...],
        verifier: EmailVerifierPort,
    ):
        self.providers = providers
        self.verifier = verifier

    async def enrich_domain(
        self, domain: str, *, first_name: str | None = None, last_name: str | None = None
    ) -> list[EnrichedContact]:
        """瀑布富化 + 验证。命中即停。"""
        candidates = await self._waterfall(domain, first_name, last_name)
        enriched: list[EnrichedContact] = []
        for cand in candidates:
            verification = await self.verifier.verify(cand.email)
            enriched.append(EnrichedContact(candidate=cand, verification=verification))
        return enriched

    async def _waterfall(
        self, domain: str, first_name: str | None, last_name: str | None
    ) -> list[EmailCandidate]:
        for provider in self.providers:
            try:
                found = await provider.find_emails(
                    domain, first_name=first_name, last_name=last_name
                )
            except Exception as e:  # 单个供应商失败不应中断瀑布
                log.warning("enrichment.provider_failed", provider=provider.name, error=str(e))
                continue
            if found:
                log.info("enrichment.hit", provider=provider.name, domain=domain, n=len(found))
                return found
        return []

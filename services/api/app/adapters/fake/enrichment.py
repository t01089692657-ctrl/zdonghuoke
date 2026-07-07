"""fake enrichment：根据域名确定性地造出候选联系人邮箱。

模拟真实 enrichment 供应商的「命中率不 100%」特性：部分域名返回空，
以便瀑布富化逻辑（依次调多家直到命中）能被真实地测试到。
"""
from __future__ import annotations

from app.adapters.fake._util import pick, stable_int
from app.domain.contracts import EmailCandidate
from app.domain.rules import generate_email_patterns

_FIRST = ["john", "maria", "ahmed", "li", "hans", "sofia", "david", "yuki", "pierre"]
_LAST = ["smith", "garcia", "khan", "wang", "muller", "rossi", "dubois", "tanaka"]
_TITLE = ["Purchasing Manager", "Procurement Lead", "CEO", "Import Manager", "Buyer"]


class FakeHunterEnrichment:
    """模拟 Hunter：域名模式识别较强，约 70% 域名能命中一个联系人。"""

    @property
    def name(self) -> str:
        return "fake-hunter"

    async def find_emails(
        self, domain: str, *, first_name: str | None = None, last_name: str | None = None
    ) -> list[EmailCandidate]:
        if stable_int(domain, "hunter-hit") % 10 < 3:  # 30% 未命中，交给下一家
            return []
        first = first_name or pick(_FIRST, domain, "f")
        last = last_name or pick(_LAST, domain, "l")
        patterns = generate_email_patterns(first, last, domain)
        if not patterns:
            return []
        return [
            EmailCandidate(
                email=patterns[0],
                first_name=first.title(),
                last_name=last.title(),
                title=pick(_TITLE, domain, "t"),
                confidence=0.85,
                provider=self.name,
            )
        ]


class FakeSnovEnrichment:
    """模拟 Snov：命中率不同，作为瀑布的第二家。"""

    @property
    def name(self) -> str:
        return "fake-snov"

    async def find_emails(
        self, domain: str, *, first_name: str | None = None, last_name: str | None = None
    ) -> list[EmailCandidate]:
        if stable_int(domain, "snov-hit") % 10 < 5:
            return []
        first = first_name or pick(_FIRST, domain, "sf")
        last = last_name or pick(_LAST, domain, "sl")
        patterns = generate_email_patterns(first, last, domain)
        if not patterns:
            return []
        return [
            EmailCandidate(
                email=patterns[1] if len(patterns) > 1 else patterns[0],
                first_name=first.title(),
                last_name=last.title(),
                title=pick(_TITLE, domain, "st"),
                confidence=0.7,
                provider=self.name,
            )
        ]

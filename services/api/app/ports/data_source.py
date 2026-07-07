"""数据源、富化、邮箱验证三个端口。

DataSourcePort 是可插拔的「源适配器框架」：每加一个数据源（搜索/海关/地图/名录…）
就实现一个，业务层对它们一视同仁。这样麦穗的「十大源头」我们能逐个增量接入。
"""
from __future__ import annotations

from typing import Protocol

from app.domain.contracts import (
    CompanyCandidate,
    EmailCandidate,
    LeadSearchQuery,
    VerificationResult,
)
from app.domain.enums import DataSourceType


class DataSourcePort(Protocol):
    """一个线索数据源。"""

    @property
    def source_type(self) -> DataSourceType: ...

    async def search(self, query: LeadSearchQuery) -> list[CompanyCandidate]: ...


class EnrichmentPort(Protocol):
    """联系方式富化。输入公司域名+可选人名，返回候选邮箱。"""

    @property
    def name(self) -> str: ...

    async def find_emails(
        self, domain: str, *, first_name: str | None = None, last_name: str | None = None
    ) -> list[EmailCandidate]: ...


class EmailVerifierPort(Protocol):
    """邮箱验证。"""

    async def verify(self, email: str) -> VerificationResult: ...

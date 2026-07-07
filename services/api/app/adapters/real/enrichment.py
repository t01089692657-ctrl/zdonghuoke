"""真实富化适配器（占位）。数据工程师按 EnrichmentPort 实现 Hunter/Snov。"""
from __future__ import annotations

from app.core.errors import ExternalServiceError
from app.ports.data_source import EnrichmentPort


def build_real_enrichment() -> tuple[EnrichmentPort, ...]:
    raise ExternalServiceError(
        "真实富化适配器尚未实现。请在 adapters/real/enrichment.py 按 EnrichmentPort 实现"
        "（Hunter/Snov API），或设置 ADAPTER_MODE=local。"
    )

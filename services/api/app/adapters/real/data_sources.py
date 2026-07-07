"""真实数据源适配器（占位）。数据工程师按 DataSourcePort 实现搜索/海关/地图。

实现前，cloud 模式下调用会抛清晰错误，指引改回 local 或完成实现。
参考 docs/03 数据层选型：SERP API / ImportGenius·腾道 / Outscraper·Apify。
"""
from __future__ import annotations

from app.core.errors import ExternalServiceError
from app.ports.data_source import DataSourcePort


def build_real_data_sources() -> tuple[DataSourcePort, ...]:
    raise ExternalServiceError(
        "真实数据源适配器尚未实现。请在 adapters/real/data_sources.py 按 DataSourcePort "
        "实现后于此登记，或设置 ADAPTER_MODE=local 使用本地演示数据。"
    )

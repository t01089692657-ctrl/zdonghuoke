"""依赖注入容器 —— 全系统唯一装配外部适配器的地方。

根据 ADAPTER_MODE 返回 fake 或 real 适配器。业务模块通过这里的 provider 拿依赖，
永远不 import 具体适配器类。所以：
  - 换供应商 = 改这里一行 + 新增一个 adapter，业务代码零改动；
  - 测试 = 注入自定义 fake，无需真实 IO。

用 @lru_cache 让无状态适配器单例化。
"""
from __future__ import annotations

from functools import lru_cache

from app.core.config import get_settings
from app.ports.clock import ClockPort
from app.ports.data_source import DataSourcePort, EmailVerifierPort, EnrichmentPort
from app.ports.email_sender import EmailSenderPort
from app.ports.llm import LLMPort


@lru_cache
def get_clock() -> ClockPort:
    from app.adapters.system_clock import SystemClock

    return SystemClock()


@lru_cache
def get_llm() -> LLMPort:
    if get_settings().is_local_adapters:
        from app.adapters.fake.llm import FakeLLM

        return FakeLLM()
    from app.adapters.real.llm_openai import OpenAICompatibleLLM

    return OpenAICompatibleLLM()


@lru_cache
def get_data_sources() -> tuple[DataSourcePort, ...]:
    """返回启用的数据源集合（可插拔的源适配器框架）。"""
    if get_settings().is_local_adapters:
        from app.adapters.fake.data_sources import (
            FakeCustomsSource,
            FakeMapsSource,
            FakeSearchSource,
        )

        return (FakeSearchSource(), FakeCustomsSource(), FakeMapsSource())
    # cloud：真实源适配器由数据工程师在 adapters/real 补齐后在此登记
    from app.adapters.real.data_sources import build_real_data_sources

    return build_real_data_sources()


@lru_cache
def get_enrichment_providers() -> tuple[EnrichmentPort, ...]:
    """瀑布富化的供应商顺序：命中即停。顺序即优先级。"""
    if get_settings().is_local_adapters:
        from app.adapters.fake.enrichment import FakeHunterEnrichment, FakeSnovEnrichment

        return (FakeHunterEnrichment(), FakeSnovEnrichment())
    from app.adapters.real.enrichment import build_real_enrichment

    return build_real_enrichment()


@lru_cache
def get_email_verifier() -> EmailVerifierPort:
    if get_settings().is_local_adapters:
        from app.adapters.fake.verifier import FakeEmailVerifier

        return FakeEmailVerifier()
    from app.adapters.real.verifier import RealEmailVerifier

    return RealEmailVerifier()


@lru_cache
def get_email_sender() -> EmailSenderPort:
    if get_settings().is_local_adapters:
        from app.adapters.fake.sender import FakeEmailSender

        return FakeEmailSender()
    from app.adapters.real.ses_sender import SesEmailSender

    return SesEmailSender()

"""端口（Ports）：外部依赖的抽象接口。

业务模块只依赖这些接口，不依赖具体实现。实现放在 app.adapters：
- adapters/fake/*  本地确定性实现（Mac mini，零外部依赖）
- adapters/real/*  云端真实实现（SES、海关 API、大模型…）
由 app.core.deps 根据 ADAPTER_MODE 装配。换供应商 = 换 adapter，业务零改动。
"""
from app.ports.clock import ClockPort
from app.ports.data_source import DataSourcePort, EmailVerifierPort, EnrichmentPort
from app.ports.email_sender import EmailSenderPort
from app.ports.llm import LLMPort

__all__ = [
    "DataSourcePort",
    "EnrichmentPort",
    "EmailVerifierPort",
    "EmailSenderPort",
    "LLMPort",
    "ClockPort",
]

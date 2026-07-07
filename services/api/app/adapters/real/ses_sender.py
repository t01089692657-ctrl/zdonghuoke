"""真实邮件发送适配器（占位）。送达率工程师按 EmailSenderPort 实现 Amazon SES。

实现要点见 docs/03：多域多邮箱、配置集(configuration set)绑定 bounce/complaint SNS、
发送前查全局抑制列表（由 sending 模块在调用本适配器前完成）。
"""
from __future__ import annotations

from app.core.errors import ExternalServiceError
from app.domain.contracts import OutboundEmail, SendResult


class SesEmailSender:
    async def send(self, email: OutboundEmail) -> SendResult:
        raise ExternalServiceError(
            "真实 SES 发送适配器尚未实现。请实现 adapters/real/ses_sender.py "
            "或设 ADAPTER_MODE=local。"
        )

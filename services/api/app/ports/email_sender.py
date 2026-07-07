"""邮件发送端口。本地用 fake（写日志不真发），云端用 SES。"""
from __future__ import annotations

from typing import Protocol

from app.domain.contracts import OutboundEmail, SendResult


class EmailSenderPort(Protocol):
    async def send(self, email: OutboundEmail) -> SendResult: ...

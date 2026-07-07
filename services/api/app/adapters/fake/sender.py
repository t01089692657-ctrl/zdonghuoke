"""fake 邮件发送：不真发，只记日志并返回结果；确定性地模拟极少量硬退信。

这样序列引擎/退信闭环在本地也能被完整驱动测试，而不会真的骚扰任何人。
"""
from __future__ import annotations

from app.adapters.fake._util import stable_int
from app.core.logging import get_logger
from app.domain.contracts import OutboundEmail, SendResult

log = get_logger("fake-sender")


class FakeEmailSender:
    async def send(self, email: OutboundEmail) -> SendResult:
        # 约 3% 确定性「硬退信」，用于驱动退信处理逻辑
        if stable_int(email.to_email, "bounce") % 100 < 3:
            log.info("fake_send.bounced", to=email.to_email)
            return SendResult(accepted=False, error="hard_bounce")
        mid = f"fake-{stable_int(email.to_email, email.subject)}"
        log.info("fake_send.accepted", to=email.to_email, subject=email.subject, message_id=mid)
        return SendResult(message_id=mid, accepted=True)

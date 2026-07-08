"""fake 邮件发送：不真发，只记日志并返回结果；确定性地模拟极少量硬退信。

这样序列引擎/退信闭环在本地也能被完整驱动测试，而不会真的骚扰任何人。
"""
from __future__ import annotations

import itertools

from app.adapters.fake._util import stable_int
from app.core.logging import get_logger
from app.domain.contracts import OutboundEmail, SendResult

log = get_logger("fake-sender")

# 单调计数器：保证每封 message_id 唯一（真实发送方的 message_id 也是每封唯一的）。
# 否则同一收件人被同一序列步重发时会撞 id，探针回填的 scalar_one_or_none 会抛 MultipleResultsFound。
_counter = itertools.count(1)


class FakeEmailSender:
    async def send(self, email: OutboundEmail) -> SendResult:
        # 约 3% 确定性「硬退信」，用于驱动退信处理逻辑
        if stable_int(email.to_email, "bounce") % 100 < 3:
            log.info("fake_send.bounced", to=email.to_email)
            return SendResult(accepted=False, error="hard_bounce")
        mid = f"fake-{stable_int(email.to_email, email.subject)}-{next(_counter)}"
        log.info("fake_send.accepted", to=email.to_email, subject=email.subject, message_id=mid)
        return SendResult(message_id=mid, accepted=True)

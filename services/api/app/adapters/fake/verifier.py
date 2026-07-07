"""fake 邮箱验证：确定性地判定 valid / catch_all / invalid，并标注企业/个人。

个人邮箱的判定走领域规则（真实逻辑），验证状态用哈希模拟，保证可测。
"""
from __future__ import annotations

from app.adapters.fake._util import stable_int
from app.domain.contracts import VerificationResult
from app.domain.enums import EmailStatus
from app.domain.rules import classify_email_type, email_domain, is_valid_email_syntax


class FakeEmailVerifier:
    async def verify(self, email: str) -> VerificationResult:
        email_type = classify_email_type(email)
        if not is_valid_email_syntax(email):
            return VerificationResult(
                email=email, status=EmailStatus.invalid, email_type=email_type, reason="语法非法"
            )
        domain = email_domain(email) or ""
        bucket = stable_int(email, "verify") % 100
        if bucket < 70:
            status, reason = EmailStatus.valid, None
        elif bucket < 85:
            status, reason = EmailStatus.catch_all, f"{domain} 疑似全收域名"
        elif bucket < 95:
            status, reason = EmailStatus.invalid, "邮箱不存在"
        else:
            status, reason = EmailStatus.unknown, "无法确认"
        return VerificationResult(email=email, status=status, email_type=email_type, reason=reason)

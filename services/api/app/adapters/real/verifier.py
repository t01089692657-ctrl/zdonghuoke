"""真实邮箱验证适配器：ZeroBounce（多信号验证 + catch-all 识别）。

文档 https://www.zerobounce.net/docs/ 。企业/个人邮箱判定复用领域规则（本地纯函数）。
"""
from __future__ import annotations

import httpx
from tenacity import retry, stop_after_attempt, wait_exponential

from app.core.config import get_settings
from app.core.errors import ExternalServiceError
from app.domain.contracts import VerificationResult
from app.domain.enums import EmailStatus
from app.domain.rules import classify_email_type

# ZeroBounce status → 我们的 EmailStatus
_STATUS_MAP = {
    "valid": EmailStatus.valid,
    "catch-all": EmailStatus.catch_all,
    "invalid": EmailStatus.invalid,
    "spamtrap": EmailStatus.invalid,
    "abuse": EmailStatus.invalid,
    "do_not_mail": EmailStatus.invalid,
    "unknown": EmailStatus.unknown,
}


class RealEmailVerifier:
    @retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, min=1, max=8))
    async def verify(self, email: str) -> VerificationResult:
        settings = get_settings()
        if not settings.email_verify_api_key:
            raise ExternalServiceError("EMAIL_VERIFY_API_KEY 未配置（ZeroBounce）")

        params = {"api_key": settings.email_verify_api_key, "email": email}
        try:
            async with httpx.AsyncClient(timeout=30) as client:
                resp = await client.get("https://api.zerobounce.net/v2/validate", params=params)
                resp.raise_for_status()
                data = resp.json()
        except httpx.HTTPError as e:
            raise ExternalServiceError(f"ZeroBounce 调用失败: {e}") from e

        status = _STATUS_MAP.get(data.get("status", "unknown"), EmailStatus.unknown)
        return VerificationResult(
            email=email,
            status=status,
            email_type=classify_email_type(email),
            reason=data.get("sub_status") or None,
        )

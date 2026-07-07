"""真实邮箱验证适配器（占位）。按 EmailVerifierPort 实现 ZeroBounce/NeverBounce。"""
from __future__ import annotations

from app.core.errors import ExternalServiceError
from app.domain.contracts import VerificationResult


class RealEmailVerifier:
    async def verify(self, email: str) -> VerificationResult:
        raise ExternalServiceError(
            "真实邮箱验证适配器尚未实现（ZeroBounce/NeverBounce）。请实现或设 ADAPTER_MODE=local。"
        )

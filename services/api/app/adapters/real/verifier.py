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


def build_email_verifier():
    """按 VERIFY_PROVIDER 选：zerobounce(付费高准) 或 local(免费 语法+MX+一次性域名)。"""
    from app.core.config import get_settings

    if get_settings().verify_provider.lower() == "local":
        return LocalMxVerifier()
    return RealEmailVerifier()


class LocalMxVerifier:
    """免费本地验证：语法 + 域名 MX 记录 + 一次性邮箱域名黑名单。零 API 费用。

    比专业 API 弱（无法逐地址确认存在性、catch-all 靠猜），但能零成本挡掉
    语法错误、无邮件服务的域名、一次性邮箱。SMTP 逐地址探测在住宅 IP 上多被封，
    默认不做（想做可另配）。量大后再切 zerobounce。
    """

    _DISPOSABLE = {
        "mailinator.com", "guerrillamail.com", "10minutemail.com", "tempmail.com",
        "yopmail.com", "trashmail.com", "getnada.com", "sharklasers.com",
    }
    _SYNTAX = __import__("re").compile(r"^[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}$")

    async def verify(self, email: str) -> VerificationResult:
        import asyncio

        email = email.strip().lower()
        etype = classify_email_type(email)
        if not self._SYNTAX.match(email):
            return VerificationResult(email=email, status=EmailStatus.invalid,
                                      email_type=etype, reason="syntax")
        domain = email.rsplit("@", 1)[-1]
        if domain in self._DISPOSABLE:
            return VerificationResult(email=email, status=EmailStatus.invalid,
                                      email_type=etype, reason="disposable")
        has_mx = await asyncio.to_thread(self._has_mx, domain)
        if not has_mx:
            return VerificationResult(email=email, status=EmailStatus.invalid,
                                      email_type=etype, reason="no_mx")
        # 有 MX 但无法逐地址确认 → unknown（保守，交由后续低权重发送/人工判断）
        return VerificationResult(email=email, status=EmailStatus.unknown,
                                  email_type=etype, reason="mx_ok_unconfirmed")

    @staticmethod
    def _has_mx(domain: str) -> bool:
        try:
            import dns.resolver  # dnspython
            answers = dns.resolver.resolve(domain, "MX", lifetime=5)
            return len(answers) > 0
        except Exception:
            # 无 dnspython 或查询失败：退化为「A 记录存在即可能收信」的粗判
            try:
                import socket
                socket.gethostbyname(domain)
                return True
            except Exception:
                return False


class RealEmailVerifier:
    @retry(stop=stop_after_attempt(3), wait=wait_exponential(min=1, max=8), reraise=True)
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

        # ZeroBounce 错误响应(如 Invalid API Key)没有 status 字段——必须显式报错，
        # 否则会被静默当成 unknown，等于"验证被无声关闭、坏邮箱照发"。
        if not isinstance(data, dict) or "status" not in data or data.get("error"):
            raise ExternalServiceError(f"ZeroBounce 返回异常: {data.get('error') or data}")
        status = _STATUS_MAP.get(data.get("status", "unknown"), EmailStatus.unknown)
        return VerificationResult(
            email=email,
            status=status,
            email_type=classify_email_type(email),
            reason=data.get("sub_status") or None,
        )

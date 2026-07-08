"""轻量签名工具：用 secret_key 做 HMAC，防开放重定向与退订链接被伪造。

用途：
- 点击追踪重定向：只允许跳转到我们签发过的 URL（杜绝 open redirect 钓鱼）；
- 一键退订链接：带签名 token，防止他人伪造 email 退订别人/被滥用。
"""
from __future__ import annotations

import hashlib
import hmac

from app.core.config import get_settings


def _sign(message: str) -> str:
    key = get_settings().secret_key.encode()
    return hmac.new(key, message.encode(), hashlib.sha256).hexdigest()[:32]


def sign(message: str) -> str:
    """返回 message 的短签名（十六进制，32 字符）。"""
    return _sign(message)


def verify(message: str, signature: str) -> bool:
    """恒定时间校验签名，防时序攻击。"""
    if not signature:
        return False
    return hmac.compare_digest(_sign(message), signature)

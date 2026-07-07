"""通用 SMTP 发送适配器。可对接任意 SMTP：Brevo/Mailtrap 等免费档，或你自己的邮件服务器。

⚠️ 仅建议用于「测试/小量」。真正规模化冷邮件请用 SES（专业发信 IP + 信誉管理），
   免费 SMTP 档普遍禁止/限制冷邮件，且住宅 IP/共享池到达率差。见 docs/06 §2 红线。

发送前的合规守卫（个人邮箱/抑制列表）已在 sending 模块完成，这里只负责投递。
"""
from __future__ import annotations

from email.message import EmailMessage

from app.core.config import get_settings
from app.core.errors import ExternalServiceError
from app.core.logging import get_logger
from app.domain.contracts import OutboundEmail, SendResult

log = get_logger("smtp-sender")


class SmtpEmailSender:
    async def send(self, email: OutboundEmail) -> SendResult:
        settings = get_settings()
        if not settings.smtp_host:
            raise ExternalServiceError("SMTP_HOST 未配置")

        msg = EmailMessage()
        msg["From"] = email.from_email
        msg["To"] = email.to_email
        msg["Subject"] = email.subject
        for k, v in (email.headers or {}).items():
            msg[k] = v
        msg.set_content(email.body_text or "")
        msg.add_alternative(email.body_html, subtype="html")

        try:
            import asyncio

            result = await asyncio.to_thread(self._send_sync, settings, msg)
            return result
        except Exception as e:  # noqa: BLE001 —— 发送失败不抛，返回失败结果供发送层记账
            log.warning("smtp.send_failed", to=email.to_email, error=str(e))
            return SendResult(accepted=False, error=str(e))

    @staticmethod
    def _send_sync(settings, msg: EmailMessage) -> SendResult:
        import smtplib

        if settings.smtp_use_tls:
            server = smtplib.SMTP(settings.smtp_host, settings.smtp_port, timeout=30)
            server.starttls()
        else:
            server = smtplib.SMTP(settings.smtp_host, settings.smtp_port, timeout=30)
        try:
            if settings.smtp_user:
                server.login(settings.smtp_user, settings.smtp_password)
            server.send_message(msg)
        finally:
            server.quit()
        return SendResult(accepted=True)

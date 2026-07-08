"""真实邮件发送适配器：Amazon SES（boto3）。

发送前的合规守卫（个人邮箱/抑制列表）由 sending 模块在调用本适配器前完成 ——
本适配器只负责「把已放行的邮件投递出去」，职责单一。

boto3 为可选依赖（仅 cloud 需要）：`uv sync --extra cloud`。
SES 配置集(configuration set)用于把 bounce/complaint 事件经 SNS 回流（见 docs/06）。
"""
from __future__ import annotations

from app.core.config import get_settings
from app.core.errors import ExternalServiceError
from app.core.logging import get_logger
from app.domain.contracts import OutboundEmail, SendResult

log = get_logger("ses-sender")


class SesEmailSender:
    def __init__(self) -> None:
        self._client = None

    def _get_client(self):
        if self._client is not None:
            return self._client
        settings = get_settings()
        try:
            import boto3  # 延迟导入：local 模式无需安装 boto3
        except ImportError as e:
            raise ExternalServiceError(
                "boto3 未安装。运行 `uv sync --extra cloud` 后再用 SES。"
            ) from e
        if not (settings.aws_access_key_id and settings.aws_secret_access_key):
            raise ExternalServiceError("AWS 凭证未配置（AWS_ACCESS_KEY_ID/SECRET）")
        self._client = boto3.client(
            "ses",
            region_name=settings.aws_region,
            aws_access_key_id=settings.aws_access_key_id,
            aws_secret_access_key=settings.aws_secret_access_key,
        )
        return self._client

    async def send(self, email: OutboundEmail) -> SendResult:
        import asyncio

        try:
            # 整个「建客户端 + raw MIME 发送」都放到线程池：boto3 建客户端会读磁盘配置，
            # 若在事件循环线程内执行会阻塞。确保自定义头（List-Unsubscribe）随信发出。
            resp = await asyncio.to_thread(self._send_raw, email)
        except Exception as e:  # botocore ClientError 等
            log.warning("ses.send_failed", to=email.to_email, error=str(e))
            return SendResult(accepted=False, error=str(e))
        return SendResult(message_id=resp.get("MessageId"), accepted=True)

    def _send_raw(self, email: OutboundEmail) -> dict:
        from email.message import EmailMessage

        client = self._get_client()
        settings = get_settings()
        msg = EmailMessage()
        msg["From"] = email.from_email
        msg["To"] = email.to_email
        msg["Subject"] = email.subject
        for k, v in (email.headers or {}).items():
            msg[k] = v
        msg.set_content(email.body_text or "")
        msg.add_alternative(email.body_html, subtype="html")

        kwargs = {
            "Source": email.from_email,
            "Destinations": [email.to_email],
            "RawMessage": {"Data": msg.as_bytes()},
        }
        if settings.ses_configuration_set:
            kwargs["ConfigurationSetName"] = settings.ses_configuration_set
        return client.send_raw_email(**kwargs)

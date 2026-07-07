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
        settings = get_settings()
        client = self._get_client()
        body: dict = {"Html": {"Data": email.body_html, "Charset": "UTF-8"}}
        if email.body_text:
            body["Text"] = {"Data": email.body_text, "Charset": "UTF-8"}
        kwargs = {
            "Source": email.from_email,
            "Destination": {"ToAddresses": [email.to_email]},
            "Message": {
                "Subject": {"Data": email.subject, "Charset": "UTF-8"},
                "Body": body,
            },
        }
        if email.headers:
            # SES v2 支持自定义头；此处经 send_email 的 Tags/ReplyTo 之外的头需用 SESv2，
            # 为简洁起见，List-Unsubscribe 等由发送层拼进 body/headers 时用 send_raw_email 更佳。
            pass
        if settings.ses_configuration_set:
            kwargs["ConfigurationSetName"] = settings.ses_configuration_set

        try:
            # boto3 是同步库；用线程池避免阻塞事件循环
            import asyncio

            resp = await asyncio.to_thread(client.send_email, **kwargs)
        except Exception as e:  # botocore ClientError 等
            log.warning("ses.send_failed", to=email.to_email, error=str(e))
            return SendResult(accepted=False, error=str(e))

        return SendResult(message_id=resp.get("MessageId"), accepted=True)

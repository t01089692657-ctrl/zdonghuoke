"""sending 模块 HTTP 路由（薄层）：收参 → 调 service → 返 schema。

装配 service 的方式照 leads/router.py 的 build_*_service 模式（走 DI 容器 + session）。
合规拦截由 service 抛 ComplianceError，API 层统一转 403（见 core/errors）。
"""
from __future__ import annotations

import base64

from fastapi import APIRouter, Depends
from fastapi.responses import RedirectResponse, Response
from sqlalchemy.ext.asyncio import AsyncSession

from app.core import deps
from app.core.database import get_session
from app.core.errors import NotFoundError
from app.modules.compliance.service import ComplianceService
from app.modules.sending.repository import SendingRepository
from app.modules.sending.scheduler import PollingScheduler
from app.modules.sending.schemas import (
    DomainIn,
    DomainOut,
    EnrollIn,
    EnrollOut,
    HealthOut,
    MailboxIn,
    MailboxOut,
    MessageIn,
    MessageOut,
    TickResult,
    WarmupTickResult,
)
from app.modules.sending.service import SendingService

router = APIRouter(prefix="/sending", tags=["sending"])

# 1x1 透明 GIF（open 探针像素）。解码一次，供每次请求复用。
_PIXEL_GIF = base64.b64decode(
    "R0lGODlhAQABAIAAAAAAAP///yH5BAEAAAAALAAAAAABAAEAAAIBRAA7"
)


def build_sending_service(session: AsyncSession) -> SendingService:
    """在一个地方装配 SendingService 及其全部依赖（走 DI 容器）。"""
    clock = deps.get_clock()
    return SendingService(
        repo=SendingRepository(session),
        sender=deps.get_email_sender(),
        clock=clock,
        compliance=ComplianceService(session),
        scheduler=PollingScheduler(clock),
    )


# ---- 域名 / 邮箱 ----------------------------------------------------------
@router.post("/domains", response_model=DomainOut, status_code=201)
async def register_domain(body: DomainIn, session: AsyncSession = Depends(get_session)):
    svc = build_sending_service(session)
    domain = await svc.register_domain(
        body.domain,
        spf_ok=body.spf_ok,
        dkim_ok=body.dkim_ok,
        dmarc_ok=body.dmarc_ok,
        reputation=body.reputation,
        active=body.active,
    )
    return DomainOut.model_validate(domain)


@router.post("/mailboxes", response_model=MailboxOut, status_code=201)
async def register_mailbox(body: MailboxIn, session: AsyncSession = Depends(get_session)):
    svc = build_sending_service(session)
    if await svc.repo.get_domain(body.sender_domain_id) is None:
        raise NotFoundError("发信域名不存在")
    mailbox = await svc.register_mailbox(
        body.sender_domain_id, body.email, warmup_stage=body.warmup_stage, active=body.active
    )
    return MailboxOut.model_validate(mailbox)


@router.post("/warmup/tick", response_model=WarmupTickResult)
async def warmup_tick(session: AsyncSession = Depends(get_session)):
    svc = build_sending_service(session)
    return WarmupTickResult(**await svc.warmup_tick())


# ---- 单封发送（演示合规守卫：个人邮箱 → 403）-----------------------------
@router.post("/messages", response_model=MessageOut)
async def send_message(body: MessageIn, session: AsyncSession = Depends(get_session)):
    svc = build_sending_service(session)
    outcome = await svc.send_one(
        body.to_email,
        body.subject,
        body.body,
        campaign_id=body.campaign_id,
        lead_id=body.lead_id,
    )
    return MessageOut(
        id=outcome.message.id,
        to_email=outcome.message.to_email,
        status=outcome.message.status,
        message_id=outcome.message.message_id,
        accepted=outcome.accepted,
        bounced=outcome.bounced,
        spam_score=outcome.spam_score,
        spam_warnings=outcome.spam_warnings,
    )


# ---- 序列 ------------------------------------------------------------------
@router.post("/enrollments", response_model=EnrollOut, status_code=201)
async def enroll(body: EnrollIn, session: AsyncSession = Depends(get_session)):
    svc = build_sending_service(session)
    enrollment = await svc.enroll(
        body.lead_id,
        body.campaign_id,
        body.to_email,
        [s.model_dump() for s in body.steps],
    )
    return EnrollOut.model_validate(enrollment)


@router.post("/sequences/tick", response_model=TickResult)
async def tick_sequences(session: AsyncSession = Depends(get_session)):
    svc = build_sending_service(session)
    report = await svc.tick_sequences()
    return TickResult(
        processed=report.processed,
        sent=report.sent,
        skipped=report.skipped,
        completed=report.completed,
    )


# ---- 送达健康度 ------------------------------------------------------------
@router.get("/health", response_model=HealthOut)
async def health(session: AsyncSession = Depends(get_session)):
    svc = build_sending_service(session)
    return HealthOut(**await svc.deliverability_stats())


# ---- 探针（open / click）--------------------------------------------------
@router.get("/track/open/{message_id}")
async def track_open(message_id: str, session: AsyncSession = Depends(get_session)):
    """返回 1x1 透明 gif；顺带记录一次打开（找不到消息也照常返回像素）。"""
    svc = build_sending_service(session)
    await svc.record_open(message_id)
    return Response(content=_PIXEL_GIF, media_type="image/gif")


@router.get("/track/click/{message_id}")
async def track_click(
    message_id: str, url: str, sig: str = "", session: AsyncSession = Depends(get_session)
):
    """记录一次点击后 302 跳到目标 url。

    防开放重定向：url 必须带我们签发的 sig（HMAC）才放行，否则 400。
    追踪链接由发送端用 build_click_url() 生成并签名，杜绝本域被当钓鱼跳板。
    """
    from app.core.errors import ValidationError
    from app.core.security import verify

    if not verify(f"{message_id}:{url}", sig):
        raise ValidationError("非法的追踪链接（签名校验失败）")
    svc = build_sending_service(session)
    await svc.record_click(message_id)
    return RedirectResponse(url=url, status_code=302)


@router.api_route("/unsubscribe", methods=["GET", "POST"])
async def unsubscribe(email: str, sig: str = "", session: AsyncSession = Depends(get_session)):
    """一键退订（RFC 8058）：校验签名 → 加入全局抑制列表 → 停止其所有序列。

    List-Unsubscribe 头里的链接指向这里；GET 供用户点击，POST 供邮箱商 One-Click。
    """
    from app.core.errors import ValidationError
    from app.core.security import verify

    if not verify(f"unsub:{email.strip().lower()}", sig):
        raise ValidationError("非法的退订链接（签名校验失败）")
    svc = build_sending_service(session)
    n = await svc.record_unsubscribe(email)
    return {"unsubscribed": email.strip().lower(), "sequences_stopped": n}

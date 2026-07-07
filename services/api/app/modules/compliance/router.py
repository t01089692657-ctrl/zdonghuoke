from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_session
from app.domain.enums import EmailType
from app.domain.rules import classify_email_type
from app.modules.compliance.schemas import EmailCheckResult, SuppressionIn
from app.modules.compliance.service import ComplianceService

router = APIRouter(prefix="/compliance", tags=["compliance"])


@router.post("/suppressions", status_code=201)
async def add_suppression(body: SuppressionIn, session: AsyncSession = Depends(get_session)):
    svc = ComplianceService(session)
    await svc.add_suppression(body.email, body.reason, body.note)
    return {"ok": True}


@router.get("/suppressions/count")
async def suppression_count(session: AsyncSession = Depends(get_session)):
    svc = ComplianceService(session)
    return {"count": await svc.suppression_count()}


@router.get("/check", response_model=EmailCheckResult)
async def check_email(email: str, session: AsyncSession = Depends(get_session)):
    svc = ComplianceService(session)
    etype = classify_email_type(email)
    suppressed = await svc.is_suppressed(email)
    sendable = await svc.is_sendable(email)
    reason = None
    if etype is EmailType.personal:
        reason = "个人邮箱，默认不做冷触达"
    elif suppressed:
        reason = "在全局抑制列表中"
    return EmailCheckResult(
        email=email, email_type=etype, suppressed=suppressed, sendable=sendable, reason=reason
    )

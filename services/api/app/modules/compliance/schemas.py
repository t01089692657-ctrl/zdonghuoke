from __future__ import annotations

from pydantic import BaseModel

from app.domain.enums import EmailType, SuppressionReason


class SuppressionIn(BaseModel):
    email: str
    reason: SuppressionReason = SuppressionReason.manual
    note: str | None = None


class EmailCheckResult(BaseModel):
    email: str
    email_type: EmailType
    suppressed: bool
    sendable: bool
    reason: str | None = None

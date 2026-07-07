"""统一错误类型与 HTTP 异常处理。

业务层抛领域异常（DomainError 子类），API 层统一转成规范的 JSON 错误响应。
好处：模块之间用异常表达失败，不需要到处返回 (ok, err) 元组，也便于测试。
"""
from __future__ import annotations

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse


class DomainError(Exception):
    """所有业务异常的基类。"""

    status_code: int = 400
    code: str = "domain_error"

    def __init__(self, message: str, *, code: str | None = None):
        super().__init__(message)
        self.message = message
        if code:
            self.code = code


class NotFoundError(DomainError):
    status_code = 404
    code = "not_found"


class ValidationError(DomainError):
    status_code = 422
    code = "validation_error"


class ComplianceError(DomainError):
    """合规红线拦截（如向个人邮箱发信、命中抑制列表）。不可绕过。"""

    status_code = 403
    code = "compliance_blocked"


class ConflictError(DomainError):
    status_code = 409
    code = "conflict"


class ExternalServiceError(DomainError):
    status_code = 502
    code = "external_service_error"


def register_error_handlers(app: FastAPI) -> None:
    @app.exception_handler(DomainError)
    async def _handle_domain_error(_: Request, exc: DomainError) -> JSONResponse:
        return JSONResponse(
            status_code=exc.status_code,
            content={"error": {"code": exc.code, "message": exc.message}},
        )

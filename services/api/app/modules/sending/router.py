"""sending 模块 HTTP 路由（骨架）。由对应工程师填充实现。"""
from __future__ import annotations

from fastapi import APIRouter

router = APIRouter(prefix="/sending", tags=["sending"])


@router.get("/_status")
async def status() -> dict:
    return {"module": "sending", "status": "scaffold"}

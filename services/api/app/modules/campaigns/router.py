"""campaigns 模块 HTTP 路由（骨架）。由对应工程师填充实现。"""
from __future__ import annotations

from fastapi import APIRouter

router = APIRouter(prefix="/campaigns", tags=["campaigns"])


@router.get("/_status")
async def status() -> dict:
    return {"module": "campaigns", "status": "scaffold"}

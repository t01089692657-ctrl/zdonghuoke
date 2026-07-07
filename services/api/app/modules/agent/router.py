"""agent 模块 HTTP 路由（骨架）。由对应工程师填充实现。"""
from __future__ import annotations

from fastapi import APIRouter

router = APIRouter(prefix="/agent", tags=["agent"])


@router.get("/_status")
async def status() -> dict:
    return {"module": "agent", "status": "scaffold"}

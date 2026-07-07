"""路由装配（薄层）。把各模块的 router 挂到 /api 下。

模块间不互相 import 路由，全部在这里集中挂载 —— 一眼看清系统对外的 HTTP 面。
"""
from __future__ import annotations

from fastapi import APIRouter

from app.modules.agent.router import router as agent_router
from app.modules.analytics.router import router as analytics_router
from app.modules.campaigns.router import router as campaigns_router
from app.modules.compliance.router import router as compliance_router
from app.modules.crm.router import router as crm_router
from app.modules.leads.router import router as leads_router
from app.modules.orchestration.router import router as orchestration_router
from app.modules.sending.router import router as sending_router

api_router = APIRouter(prefix="/api")

api_router.include_router(leads_router)
api_router.include_router(compliance_router)
api_router.include_router(sending_router)
api_router.include_router(agent_router)
api_router.include_router(campaigns_router)
api_router.include_router(crm_router)
api_router.include_router(analytics_router)
api_router.include_router(orchestration_router)

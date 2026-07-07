"""FastAPI 应用入口。装配日志、CORS、错误处理、路由，并在启动时建表。"""
from __future__ import annotations

from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.routes import api_router
from app.core.config import get_settings
from app.core.database import init_db
from app.core.errors import register_error_handlers
from app.core.logging import configure_logging, get_logger

settings = get_settings()


@asynccontextmanager
async def lifespan(app: FastAPI):
    configure_logging()
    log = get_logger()
    log.info("startup", env=settings.app_env.value, adapter_mode=settings.adapter_mode.value)
    await init_db()  # 本地/MVP：create_all；生产：Alembic
    yield
    log.info("shutdown")


app = FastAPI(
    title="ZDHK 自动获客系统 API",
    version="0.1.0",
    description="面向外贸企业的 AI 自动获客后端。模块化单体 + 端口与适配器。",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origin_list,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

register_error_handlers(app)
app.include_router(api_router)


@app.get("/health", tags=["system"])
async def health() -> dict:
    """健康检查。docker-compose 与云端探活都打这个。"""
    return {
        "status": "ok",
        "env": settings.app_env.value,
        "adapter_mode": settings.adapter_mode.value,
        "version": app.version,
    }


@app.get("/", tags=["system"])
async def root() -> dict:
    return {"service": "zdhk-api", "docs": "/docs", "health": "/health"}

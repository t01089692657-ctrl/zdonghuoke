from __future__ import annotations

from pydantic import BaseModel, Field


class PrepareRequest(BaseModel):
    """AI 备信请求：product_info 会被写信 agent 作为「可引用的已验证字段」使用。"""

    product_info: dict = Field(default_factory=dict)


class PrepareResult(BaseModel):
    targets: int
    drafted: int
    skipped: int


class LaunchResult(BaseModel):
    enrolled: int
    waiting_approval: int = 0


class InboundRequest(BaseModel):
    from_email: str
    text: str


class InboundResult(BaseModel):
    intent: str
    confidence: float
    extracted: dict = Field(default_factory=dict)
    actions: list[str] = Field(default_factory=list)


class TickResult(BaseModel):
    warmup: dict
    sequences: dict

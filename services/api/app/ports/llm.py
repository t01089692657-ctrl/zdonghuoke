"""大模型端口。OpenAI 兼容协议的最小抽象，可指向 DeepSeek / Qwen / 本地 fake。"""
from __future__ import annotations

from typing import Protocol

from pydantic import BaseModel


class LLMMessage(BaseModel):
    role: str  # system | user | assistant
    content: str


class LLMResponse(BaseModel):
    content: str
    model: str
    prompt_tokens: int = 0
    completion_tokens: int = 0


class LLMPort(Protocol):
    async def complete(
        self,
        messages: list[LLMMessage],
        *,
        model: str | None = None,
        temperature: float = 0.4,
        max_tokens: int = 1024,
        json_mode: bool = False,
    ) -> LLMResponse: ...

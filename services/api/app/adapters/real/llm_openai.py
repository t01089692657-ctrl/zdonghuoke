"""真实大模型适配器：OpenAI 兼容 HTTP 协议。

BASE_URL 指向 DeepSeek / Qwen(DashScope 兼容) / 任意 OpenAI 兼容网关即可。
只接入已备案国产模型 → 走生成式 AI「登记」轻合规路径（见 docs/03）。
"""
from __future__ import annotations

import httpx
from tenacity import retry, stop_after_attempt, wait_exponential

from app.core.config import get_settings
from app.core.errors import ExternalServiceError
from app.ports.llm import LLMMessage, LLMResponse


class OpenAICompatibleLLM:
    def __init__(self) -> None:
        s = get_settings()
        self._base_url = s.llm_base_url.rstrip("/")
        self._api_key = s.llm_api_key
        self._default_model = s.llm_model_writer

    @retry(stop=stop_after_attempt(3), wait=wait_exponential(min=1, max=8), reraise=True)
    async def complete(
        self,
        messages: list[LLMMessage],
        *,
        model: str | None = None,
        temperature: float = 0.4,
        max_tokens: int = 1024,
        json_mode: bool = False,
    ) -> LLMResponse:
        if not self._api_key:
            raise ExternalServiceError("LLM_API_KEY 未配置")
        body: dict = {
            "model": model or self._default_model,
            "messages": [m.model_dump() for m in messages],
            "temperature": temperature,
            "max_tokens": max_tokens,
        }
        if json_mode:
            body["response_format"] = {"type": "json_object"}
        try:
            async with httpx.AsyncClient(timeout=60) as client:
                resp = await client.post(
                    f"{self._base_url}/chat/completions",
                    headers={"Authorization": f"Bearer {self._api_key}"},
                    json=body,
                )
                resp.raise_for_status()
                data = resp.json()
        except httpx.HTTPError as e:
            raise ExternalServiceError(f"LLM 调用失败: {e}") from e

        # 网关可能返回 200 + error body，或 content=null；健壮解析，不让 KeyError 冒泡成 500
        try:
            choice = data["choices"][0]["message"]["content"]
        except (KeyError, IndexError, TypeError) as e:
            err = data.get("error") if isinstance(data, dict) else None
            raise ExternalServiceError(f"LLM 返回异常: {err or data}") from e
        if choice is None:
            raise ExternalServiceError("LLM 返回空内容(content=null)")
        usage = data.get("usage", {}) or {}
        return LLMResponse(
            content=choice,
            model=body["model"],
            prompt_tokens=usage.get("prompt_tokens", 0),
            completion_tokens=usage.get("completion_tokens", 0),
        )

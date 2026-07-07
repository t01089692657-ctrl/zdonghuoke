"""模型路由：按任务类型挑模型，并提供健壮的 JSON 补全辅助。

封装 deps.get_llm() 拿到的 LLMPort：业务层只依赖端口，换模型/供应商零改动。
  - 写信 / 背调（research/writing）→ settings.llm_model_writer
  - 回复分类（classify）          → settings.llm_model_classifier
JSON 解析刻意做到健壮：json.loads 失败要回退，绝不把异常抛成 500。
"""
from __future__ import annotations

import json

from app.core.config import get_settings
from app.core.logging import get_logger
from app.ports.llm import LLMMessage, LLMPort

log = get_logger("agent.model_router")


class ModelRouter:
    """把「任务 → 模型名」的映射与「LLM → dict」的健壮解析收在一处。"""

    def __init__(self, llm: LLMPort):
        self.llm = llm
        self.settings = get_settings()

    def route(self, task_type: str) -> str:
        """按任务类型返回模型名。分类走 classifier，其余（写信/背调）走 writer。"""
        if task_type == "classify":
            return self.settings.llm_model_classifier
        return self.settings.llm_model_writer

    async def complete_json(
        self,
        messages: list[LLMMessage],
        model: str,
        *,
        temperature: float = 0.4,
        max_tokens: int = 1024,
    ) -> dict:
        """以 json_mode 调 LLM，把返回内容解析成 dict；任何解析失败都回退空 dict。"""
        resp = await self.llm.complete(
            messages,
            model=model,
            temperature=temperature,
            max_tokens=max_tokens,
            json_mode=True,
        )
        return self._parse(resp.content)

    @staticmethod
    def _parse(content: str) -> dict:
        """健壮解析：先直连 json.loads；失败再截取首尾花括号重试；仍失败回退空 dict。"""
        try:
            data = json.loads(content)
            return data if isinstance(data, dict) else {}
        except (json.JSONDecodeError, TypeError):
            pass
        # 回退：模型可能用 ```json 包裹或夹带解释文字，截取第一个 { 到最后一个 }
        start = content.find("{")
        end = content.rfind("}")
        if start != -1 and end > start:
            try:
                data = json.loads(content[start : end + 1])
                return data if isinstance(data, dict) else {}
            except json.JSONDecodeError:
                pass
        log.warning("agent.json_parse_failed", preview=content[:120])
        return {}

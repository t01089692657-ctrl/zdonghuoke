"""fake 大模型：确定性响应，无外部调用、无费用。

约定（AI 模块的 prompt 需遵守，以便本地/CI 拿到结构正确的 JSON）：
当 json_mode=True 时，根据 prompt 中的任务关键词返回对应结构的 JSON：
  - 含 "classify"/"intent"/"分类"      → 回复分类结果
  - 含 "research"/"brief"/"素材卡"      → 研究素材卡
  - 含 "subject"/"cold email"/"开发信"  → 生成的邮件
真实适配器（adapters/real/llm.py）走 OpenAI 兼容 HTTP，不受此约定限制。
"""
from __future__ import annotations

import json

from app.adapters.fake._util import pick, stable_int
from app.domain.enums import ReplyIntent
from app.ports.llm import LLMMessage, LLMResponse

_INTENTS = [
    ReplyIntent.interested, ReplyIntent.meeting, ReplyIntent.objection,
    ReplyIntent.not_interested, ReplyIntent.out_of_office, ReplyIntent.unsubscribe,
]


class FakeLLM:
    async def complete(
        self,
        messages: list[LLMMessage],
        *,
        model: str | None = None,
        temperature: float = 0.4,
        max_tokens: int = 1024,
        json_mode: bool = False,
    ) -> LLMResponse:
        text = "\n".join(m.content for m in messages)
        low = text.lower()
        seed = str(stable_int(text))

        if json_mode:
            payload = self._json_for(low, text, seed)
            content = json.dumps(payload, ensure_ascii=False)
        else:
            content = self._plain(low, seed)

        return LLMResponse(
            content=content,
            model=model or "fake-llm",
            prompt_tokens=len(text) // 4,
            completion_tokens=len(content) // 4,
        )

    def _json_for(self, low: str, text: str, seed: str) -> dict:
        if any(k in low for k in ("classify", "intent", "分类", "reply")):
            intent = pick(_INTENTS, seed)  # type: ignore[arg-type]
            extracted: dict = {}
            if intent is ReplyIntent.out_of_office:
                extracted = {"return_date": "2026-08-01"}
            if intent is ReplyIntent.referral:
                extracted = {"referred_contact": "buyer@example.com"}
            return {
                "intent": intent.value,
                "confidence": 0.6 + (stable_int(seed, "c") % 40) / 100,
                "extracted": extracted,
            }
        if any(k in low for k in ("research", "brief", "素材卡", "company profile")):
            return {
                "what_they_do": "Imports and distributes consumer goods regionally.",
                "who_they_sell_to": "Regional retailers and wholesalers.",
                "signals": ["recently expanded product line", "active importer per customs data"],
                "approach_hint": "Lead with reliability and MOQ flexibility.",
            }
        # 默认当作生成邮件
        return {
            "subject": "Reliable supply for your product line",
            "body": (
                "Hi there,\n\nI noticed your company imports in this category. "
                "We help importers like you secure consistent quality with flexible MOQ. "
                "Would it make sense to share a quick catalog?\n\nBest regards,\nSales Team"
            ),
            "personalization_evidence": ["active importer per customs data"],
        }

    def _plain(self, low: str, seed: str) -> str:
        return "OK"

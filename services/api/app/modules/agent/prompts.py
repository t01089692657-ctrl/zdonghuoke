"""三套 agent 的 prompt 构造函数（system + user）。

刻意在文案里保留任务关键词（research/素材卡、cold email/开发信、classify/intent/分类），
以便本地 ADAPTER_MODE=local 下 fake LLM 依关键词返回结构正确的 JSON —— 见
adapters/fake/llm.py 的约定。真实模型不受此约束，关键词只是自然的英文指令。
"""
from __future__ import annotations

import json

from app.domain.contracts import ResearchBrief
from app.ports.llm import LLMMessage

# 分类允许的意图取值（与 domain.enums.ReplyIntent 对齐，供 few-shot 约束模型输出）
_ALLOWED_INTENTS = (
    "interested, meeting, objection, not_interested, referral, "
    "out_of_office, unsubscribe, wrong_person, bounce, unknown"
)


def build_research_prompt(domain: str, website_text: str | None = None) -> list[LLMMessage]:
    """研究 agent：产出「素材卡」(ResearchBrief) 结构的 JSON。"""
    system = LLMMessage(
        role="system",
        content=(
            "You are a B2B research agent. Produce a concise research brief (研究素材卡) "
            "about one company to help a sales rep personalize outreach. Only state facts "
            "you can ground in the given inputs; never invent numbers, names or claims. "
            "Respond as JSON with keys: what_they_do (string), who_they_sell_to (string), "
            "signals (array of short factual strings that can be cited), approach_hint (string)."
        ),
    )
    parts = [f"Company domain: {domain}"]
    if website_text:
        parts.append(f"Website text excerpt:\n{website_text[:2000]}")
    parts.append("Build the research brief (素材卡) now and output it as JSON.")
    return [system, LLMMessage(role="user", content="\n\n".join(parts))]


def build_writing_prompt(
    brief: ResearchBrief, product_info: dict, contact: dict
) -> list[LLMMessage]:
    """写信 agent：字段约束式 prompt —— 只允许引用给定的已验证字段，禁止编造。"""
    # 已验证、可引用的字段全集。写信 agent 只能从这里取材，任何其它「事实」都算编造。
    verified_fields = {
        "company_domain": brief.company_domain,
        "what_they_do": brief.what_they_do,
        "who_they_sell_to": brief.who_they_sell_to,
        "signals": brief.signals,
        "approach_hint": brief.approach_hint,
        "contact": contact,
        "product": product_info,
    }
    system = LLMMessage(
        role="system",
        content=(
            "You are an expert cold email (开发信) copywriter for B2B outbound sales. "
            "Write one short, personalized cold email. STRICT RULE: you may ONLY reference "
            "facts present in the provided verified fields (已验证字段). Do NOT fabricate any "
            "company facts, names, numbers, or claims. Keep it under 120 words, natural tone, "
            "no spammy phrases, one clear soft call to action. Respond as JSON with keys: "
            "subject (string), body (string), personalization_evidence "
            "(array listing the exact verified fields you actually cited)."
        ),
    )
    user = LLMMessage(
        role="user",
        content=(
            "只允许引用以下已验证字段，禁止编造未列出的任何信息：\n"
            + json.dumps(verified_fields, ensure_ascii=False, indent=2)
            + "\n\nWrite the cold email (开发信) now. Output subject, body and "
            "personalization_evidence as JSON."
        ),
    )
    return [system, user]


def build_classify_prompt(reply_text: str) -> list[LLMMessage]:
    """回复 agent：few-shot 分类 prompt —— 输出 intent/confidence/extracted。"""
    system = LLMMessage(
        role="system",
        content=(
            "You are a reply classification agent for B2B cold email. Classify the buyer's "
            f"reply into exactly one intent. Allowed intent values: {_ALLOWED_INTENTS}. "
            "Respond as JSON with keys: intent (one allowed value), confidence (0..1), "
            "extracted (object with any useful fields, e.g. return_date for out_of_office, "
            "referred_contact for referral). Follow the few-shot examples."
        ),
    )
    examples = (
        "Examples (分类样例):\n"
        "Reply: 'Please remove me from your list.' -> "
        '{"intent":"unsubscribe","confidence":0.98,"extracted":{}}\n'
        "Reply: 'I am out of office until Aug 1.' -> "
        '{"intent":"out_of_office","confidence":0.95,"extracted":{"return_date":"Aug 1"}}\n'
        "Reply: 'Sounds interesting, can we schedule a call next week?' -> "
        '{"intent":"meeting","confidence":0.9,"extracted":{}}\n'
    )
    user = LLMMessage(
        role="user",
        content=(
            f"{examples}\nClassify this reply and output the intent JSON (分类):\n\n{reply_text}"
        ),
    )
    return [system, user]

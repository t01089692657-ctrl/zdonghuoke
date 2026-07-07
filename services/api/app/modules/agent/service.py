"""AI 智能体服务：编排研究/写信/回复三 agent + 人审（HITL）。

编排原则同 leads：service 只做编排（调 ModelRouter + repository + domain 规则），
不写裸 SQL、不碰具体适配器。写信走「研究→写信」两段式，可解释性靠 evidence 落地。
"""
from __future__ import annotations

from app.core.errors import NotFoundError
from app.core.logging import get_logger
from app.domain.contracts import GeneratedEmail, ReplyClassification, ResearchBrief
from app.domain.enums import ApprovalStatus, ReplyIntent
from app.domain.rules import assess_spam_risk
from app.modules.agent.model_router import ModelRouter
from app.modules.agent.models import DraftApproval
from app.modules.agent.prompts import (
    build_classify_prompt,
    build_research_prompt,
    build_writing_prompt,
)
from app.modules.agent.repository import AgentRepository

log = get_logger("agent")

# ---- 回复分类的规则前置 ----------------------------------------------------
# 确定性类别用关键词秒判、零成本、零 token；命中即返回，不再打扰 LLM。
# 顺序即优先级：退订 > 退信 > 找错人 > 自动回复（OOO）。
_UNSUBSCRIBE_KWS = (
    "unsubscribe", "remove me", "opt out", "opt-out", "take me off",
    "stop emailing", "stop sending", "退订", "取消订阅", "不要再发", "别再发",
)
_BOUNCE_KWS = (
    "mailer-daemon", "delivery failed", "undeliverable", "delivery status notification",
    "address not found", "recipient rejected", "退信", "无法送达",
)
_WRONG_PERSON_KWS = (
    "wrong person", "no longer with", "not the right person", "i have left the company",
    "找错人", "已离职",
)
_OOO_KWS = (
    "out of office", "out-of-office", "ooo", "on vacation", "on annual leave",
    "automatic reply", "auto-reply", "autoreply", "away until",
    "自动回复", "休假", "年假", "外出",
)


def rule_classify(text: str) -> ReplyClassification | None:
    """关键词规则前置分类。命中确定性类别返回高置信度结果，否则返回 None（交给 LLM）。"""
    low = text.lower()
    if any(k in low for k in _UNSUBSCRIBE_KWS):
        return ReplyClassification(intent=ReplyIntent.unsubscribe, confidence=0.98)
    if any(k in low for k in _BOUNCE_KWS):
        return ReplyClassification(intent=ReplyIntent.bounce, confidence=0.95)
    if any(k in low for k in _WRONG_PERSON_KWS):
        return ReplyClassification(intent=ReplyIntent.wrong_person, confidence=0.9)
    if any(k in low for k in _OOO_KWS):
        return ReplyClassification(
            intent=ReplyIntent.out_of_office, confidence=0.9, extracted={"auto_reply": True}
        )
    return None


class AgentService:
    def __init__(self, router: ModelRouter, repo: AgentRepository):
        self.router = router
        self.repo = repo

    # ---- 研究 agent --------------------------------------------------------
    async def research(self, domain: str, website_text: str | None = None) -> ResearchBrief:
        """产出研究素材卡。先查缓存命中即复用，否则走 LLM 并回写缓存。"""
        cached = await self.repo.get_cached_brief(domain)
        if cached is not None:
            return ResearchBrief(company_domain=domain, **cached.brief)

        model = self.router.route("research")
        data = await self.router.complete_json(build_research_prompt(domain, website_text), model)
        brief = ResearchBrief(
            company_domain=domain,
            what_they_do=str(data.get("what_they_do", "")),
            who_they_sell_to=str(data.get("who_they_sell_to", "")),
            signals=_as_str_list(data.get("signals")),
            approach_hint=str(data.get("approach_hint", "")),
        )
        await self.repo.save_brief(domain, brief.model_dump(exclude={"company_domain"}))
        return brief

    # ---- 写信 agent --------------------------------------------------------
    async def write_email(
        self, brief: ResearchBrief, product_info: dict, contact: dict
    ) -> GeneratedEmail:
        """字段约束式写信。解析后校验个性化证据、评估垃圾风险，语言默认 en。"""
        model = self.router.route("writing")
        data = await self.router.complete_json(
            build_writing_prompt(brief, product_info, contact), model, temperature=0.6
        )
        subject = str(data.get("subject", "")).strip()
        body = str(data.get("body", "")).strip()
        evidence = _as_str_list(data.get("personalization_evidence"))
        language = (str(data.get("language")).strip() or "en") if data.get("language") else "en"

        # 个性化证据为空 → 无可引用的真实字段，标注需人工兜底（不放行编造内容）。
        if not evidence:
            log.warning("agent.write.no_evidence", domain=brief.company_domain)

        # 附带送达风险：用纯函数评估，风险高时告警，供人审与发送层参考。
        assessment = assess_spam_risk(subject, body)
        if assessment.risky:
            log.warning(
                "agent.write.spam_risk",
                domain=brief.company_domain,
                score=assessment.score,
                warnings=assessment.warnings,
            )

        return GeneratedEmail(
            subject=subject,
            body=body,
            language=language,
            personalization_evidence=evidence,
        )

    # ---- 回复 agent --------------------------------------------------------
    async def classify_reply(self, text: str) -> ReplyClassification:
        """规则前置命中即零成本返回；否则走 LLM few-shot，低置信度标注 needs_review。"""
        ruled = rule_classify(text)
        if ruled is not None:
            return ruled

        model = self.router.route("classify")
        data = await self.router.complete_json(build_classify_prompt(text), model, temperature=0.0)
        intent = _parse_intent(data.get("intent"))
        confidence = _coerce_confidence(data.get("confidence"))
        raw_extracted = data.get("extracted")
        extracted = dict(raw_extracted) if isinstance(raw_extracted, dict) else {}
        if confidence < 0.6:
            extracted["needs_review"] = True
        return ReplyClassification(intent=intent, confidence=confidence, extracted=extracted)

    # ---- 人审工作台（HITL）------------------------------------------------
    async def submit_draft(
        self, campaign_id: str | None, lead_id: str | None, email: GeneratedEmail
    ) -> DraftApproval:
        """把一封生成的开发信提交进人审队列，落库前顺带算好垃圾风险分。"""
        assessment = assess_spam_risk(email.subject, email.body)
        draft = DraftApproval(
            campaign_id=campaign_id,
            lead_id=lead_id,
            subject=email.subject,
            body=email.body,
            language=email.language,
            evidence=list(email.personalization_evidence),
            spam_score=assessment.score,
            status=ApprovalStatus.pending,
        )
        return await self.repo.add_draft(draft)

    async def list_pending(self) -> list[DraftApproval]:
        return await self.repo.list_pending()

    async def approve(self, draft_id: str, reviewer: str) -> DraftApproval:
        draft = await self._require_draft(draft_id)
        draft.status = ApprovalStatus.approved
        draft.reviewed_by = reviewer
        draft.reject_reason = None
        await self.repo.flush()
        return draft

    async def reject(self, draft_id: str, reviewer: str, reason: str) -> DraftApproval:
        draft = await self._require_draft(draft_id)
        draft.status = ApprovalStatus.rejected
        draft.reviewed_by = reviewer
        draft.reject_reason = reason
        await self.repo.flush()
        return draft

    async def approval_rate(self) -> float:
        """通过率 = approved / (approved + rejected)。无已审样本时返回 0.0。"""
        stats = await self.approval_stats()
        return stats["approval_rate"]

    async def approval_stats(self) -> dict:
        """人审看板计数：待审/通过/拒绝 及通过率。"""
        approved = await self.repo.count_by_status(ApprovalStatus.approved)
        rejected = await self.repo.count_by_status(ApprovalStatus.rejected)
        pending = await self.repo.count_by_status(ApprovalStatus.pending)
        decided = approved + rejected
        return {
            "approved": approved,
            "rejected": rejected,
            "pending": pending,
            "approval_rate": approved / decided if decided else 0.0,
        }

    async def _require_draft(self, draft_id: str) -> DraftApproval:
        draft = await self.repo.get_draft(draft_id)
        if draft is None:
            raise NotFoundError("草稿不存在")
        return draft


# ---- 解析辅助（健壮容错，绝不因脏数据抛异常）------------------------------
def _as_str_list(value: object) -> list[str]:
    """把 LLM 返回的任意值规整成非空字符串列表。"""
    if isinstance(value, list):
        return [str(v).strip() for v in value if v is not None and str(v).strip()]
    if isinstance(value, str) and value.strip():
        return [value.strip()]
    return []


def _parse_intent(value: object) -> ReplyIntent:
    """把模型返回的 intent 字符串映射到枚举；非法值回退 unknown。"""
    if isinstance(value, str):
        try:
            return ReplyIntent(value.strip().lower())
        except ValueError:
            pass
    return ReplyIntent.unknown


def _coerce_confidence(value: object) -> float:
    """把置信度收敛到 [0, 1]；无法解析回退 0.0。"""
    try:
        c = float(value)  # type: ignore[arg-type]
    except (TypeError, ValueError):
        return 0.0
    return max(0.0, min(1.0, c))

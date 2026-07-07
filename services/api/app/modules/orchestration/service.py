"""编排服务：跨模块业务流的唯一组合点。

三条主链路：
1. prepare → 人审 → launch：AI 为每个目标写个性化首封信（草稿），人批准后
   才会与后续跟进步骤一起进入发送序列（HITL 冷启动铁律：首封信必须人审）。
2. quick_launch：跳过逐封 AI 个性化，直接用活动模板序列入队
   （适用于已被人审验证过的模板，模板本身即是被批准的内容）。
3. handle_inbound：入站回复 → AI 分诊 → 停序列/抑制/CRM 阶段跃迁。
"""
from __future__ import annotations

from app.core.errors import NotFoundError, ValidationError
from app.core.logging import get_logger
from app.domain.contracts import ReplyClassification
from app.domain.enums import LeadStage, ReplyIntent
from app.modules.agent.service import AgentService
from app.modules.campaigns.service import CampaignService
from app.modules.crm.service import CrmService
from app.modules.leads.repository import LeadRepository
from app.modules.sending.service import SendingService

log = get_logger("orchestration")


def render_template(text: str, *, company: str = "", first_name: str = "") -> str:
    """极简占位符渲染：{{company}} / {{first_name}}。缺失时给中性兜底，避免发出残缺变量。"""
    return text.replace("{{company}}", company or "your company").replace(
        "{{first_name}}", first_name or "there"
    )


class OrchestrationService:
    def __init__(
        self,
        campaigns: CampaignService,
        agent: AgentService,
        sending: SendingService,
        crm: CrmService,
        leads: LeadRepository,
    ):
        self.campaigns = campaigns
        self.agent = agent
        self.sending = sending
        self.crm = crm
        self.leads = leads

    # ---- 链路 1：AI 备信（prepare）→ 人审 → 入队（launch）--------------------
    async def prepare_campaign(self, campaign_id: str, product_info: dict) -> dict:
        """为活动的每个待入队目标生成个性化首封信草稿，进人审队列。

        幂等：同活动同公司已有草稿则跳过。研究结果按域名缓存，重复目标不重复背调。
        """
        campaign = await self.campaigns.get_campaign(campaign_id)
        if campaign is None:
            raise NotFoundError("活动不存在")

        targets = await self.campaigns.enrollable_targets(campaign_id)
        drafted = 0
        skipped = 0
        for target in targets:
            if await self.agent.has_draft(campaign_id, target.company_id):
                skipped += 1
                continue
            company = await self.leads.get(target.company_id)
            if company is None or not company.domain:
                skipped += 1
                continue
            contact = {
                "email": target.to_email,
                "company": company.name,
                "country": company.country,
                "industry": company.industry,
            }
            brief = await self.agent.research(company.domain)
            email = await self.agent.write_email(brief, product_info, contact)
            await self.agent.submit_draft(campaign_id, target.company_id, email)
            drafted += 1

        log.info("orchestration.prepare", campaign=campaign_id, drafted=drafted, skipped=skipped)
        return {"targets": len(targets), "drafted": drafted, "skipped": skipped}

    async def launch_approved(self, campaign_id: str) -> dict:
        """把「已批准」草稿作为第 1 步 + 活动序列的后续步骤，入队发送序列。

        只有人审通过的内容才会被发送（HITL 闸门）。target.state 置为 enrolled。
        """
        campaign = await self.campaigns.get_campaign(campaign_id)
        if campaign is None:
            raise NotFoundError("活动不存在")
        if str(campaign.status) != "active":
            raise ValidationError("活动未激活：请先 activate 再 launch")

        approved = {d.lead_id: d for d in await self.agent.approved_drafts(campaign_id)}
        targets = await self.campaigns.enrollable_targets(campaign_id)

        enrolled = 0
        waiting_approval = 0
        for target in targets:
            draft = approved.get(target.company_id)
            if draft is None or not target.to_email:
                waiting_approval += 1
                continue
            followups = await self._followup_steps(campaign, target)
            steps = [
                {"step": 1, "wait_days": 0, "subject": draft.subject, "body": draft.body},
                *followups,
            ]
            await self.sending.enroll(target.company_id, campaign_id, target.to_email, steps)
            target.state = "enrolled"
            enrolled += 1

        log.info(
            "orchestration.launch",
            campaign=campaign_id,
            enrolled=enrolled,
            waiting=waiting_approval,
        )
        return {"enrolled": enrolled, "waiting_approval": waiting_approval}

    # ---- 链路 2：模板直发（quick_launch）------------------------------------
    async def quick_launch(self, campaign_id: str) -> dict:
        """用活动模板序列直接入队全部待入队目标（模板需已经过人工确认）。

        与 launch_approved 的区别：不做逐封 AI 个性化，只渲染 {{company}}/{{first_name}}。
        """
        campaign = await self.campaigns.get_campaign(campaign_id)
        if campaign is None:
            raise NotFoundError("活动不存在")
        if str(campaign.status) != "active":
            raise ValidationError("活动未激活：请先 activate 再 launch")

        targets = await self.campaigns.enrollable_targets(campaign_id)
        enrolled = 0
        for target in targets:
            if not target.to_email:
                continue
            steps = await self._rendered_sequence(campaign, target)
            await self.sending.enroll(target.company_id, campaign_id, target.to_email, steps)
            target.state = "enrolled"
            enrolled += 1
        return {"enrolled": enrolled}

    # ---- 链路 3：入站回复分诊（inbound）-------------------------------------
    async def handle_inbound(self, from_email: str, text: str) -> dict:
        """入站回复 → AI 分诊 → 路由动作。

        动作矩阵（对应 PRD G3）：
        - unsubscribe   → 停序列 + 全局抑制（永不再发）
        - interested/meeting → 回复即停 + CRM 阶段跃迁(replied→interested) + 记活动
        - objection/not_interested/wrong_person → 回复即停 + 记活动
        - out_of_office → 不停序列（顺延由序列节奏自然覆盖），仅记录
        - bounce        → 停序列（退信闭环主要走发送层，这里兜底）
        """
        classification = await self.agent.classify_reply(text)
        actions = await self._route_actions(from_email, classification)
        return {
            "intent": classification.intent.value,
            "confidence": classification.confidence,
            "extracted": classification.extracted,
            "actions": actions,
        }

    async def _route_actions(
        self, from_email: str, classification: ReplyClassification
    ) -> list[str]:
        actions: list[str] = []
        intent = classification.intent
        email = from_email.strip().lower()

        if intent is ReplyIntent.unsubscribe:
            stopped = await self.sending.record_unsubscribe(email)
            actions.append(f"suppressed+stopped({stopped})")
        elif intent in (ReplyIntent.interested, ReplyIntent.meeting):
            stopped = await self.sending.record_reply(email)
            actions.append(f"sequence_stopped({stopped})")
            company_id = await self._company_by_email(email)
            if company_id:
                await self.crm.change_stage(company_id, LeadStage.interested, actor="ai-inbound")
                await self.crm.log_activity(
                    company_id, type="email", content=f"收到意向回复: {intent.value}", actor="ai"
                )
                actions.append("crm_stage->interested")
        elif intent in (
            ReplyIntent.objection,
            ReplyIntent.not_interested,
            ReplyIntent.wrong_person,
            ReplyIntent.referral,
        ):
            stopped = await self.sending.record_reply(email)
            actions.append(f"sequence_stopped({stopped})")
            company_id = await self._company_by_email(email)
            if company_id:
                await self.crm.log_activity(
                    company_id, type="email", content=f"收到回复: {intent.value}", actor="ai"
                )
                actions.append("crm_activity_logged")
        elif intent is ReplyIntent.bounce:
            stopped = await self.sending.record_reply(email)
            actions.append(f"sequence_stopped({stopped})")
        else:
            # out_of_office / unknown：不动序列，低置信度已由 agent 标注 needs_review
            actions.append("no_sequence_action")
        return actions

    # ---- 定时推进 -----------------------------------------------------------
    async def tick(self) -> dict:
        """一次系统心跳：预热推进 + 序列步进。生产由定时任务每分钟调用。"""
        warmup = await self.sending.warmup_tick()
        report = await self.sending.tick_sequences()
        return {"warmup": warmup, "sequences": report.__dict__}

    # ---- 内部工具 -----------------------------------------------------------
    async def _company_by_email(self, email: str) -> str | None:
        contact = await self.leads.find_contact_by_email(email)
        return contact.company_id if contact else None

    async def _rendered_sequence(self, campaign, target) -> list[dict]:
        company = await self.leads.get(target.company_id)
        name = company.name if company else ""
        first = ""
        if company:
            for c in company.contacts:
                if c.id == target.contact_id and c.first_name:
                    first = c.first_name
                    break
        return [
            {
                "step": s.get("step", i + 1),
                "wait_days": s.get("wait_days", 0),
                "subject": render_template(s.get("subject", ""), company=name, first_name=first),
                "body": render_template(s.get("body", ""), company=name, first_name=first),
            }
            for i, s in enumerate(campaign.sequence_def or [])
        ]

    async def _followup_steps(self, campaign, target) -> list[dict]:
        rendered = await self._rendered_sequence(campaign, target)
        return rendered[1:]  # 第 1 步由已批准草稿替代

"""发送服务：域名/邮箱池、预热、频控、序列引擎、探针、退信/投诉闭环。

这是本项目最深的护城河：把「能不能发、该发给谁、发多少、发完之后怎么闭环」全部编排在此。
所有外部依赖（发送、时间）走端口注入；合规判断强制复用 ComplianceService（绝不绕过）。
纯业务判断下沉到 domain.rules（预热推进、频控上限、垃圾风险、送达红线），service 只做编排。
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta

from app.core.errors import ComplianceError, ValidationError
from app.core.logging import get_logger
from app.domain.contracts import OutboundEmail
from app.domain.enums import SequenceState, SuppressionReason, WarmupStage
from app.domain.rules import (
    assess_spam_risk,
    daily_cap_for_stage,
    deliverability_action,
    next_warmup_stage,
)
from app.modules.compliance.service import ComplianceService
from app.modules.sending.models import (
    OutboundMessage,
    SenderDomain,
    SenderMailbox,
    SequenceEnrollment,
)
from app.modules.sending.repository import SendingRepository
from app.modules.sending.scheduler import PollingScheduler, Scheduler
from app.ports.clock import ClockPort
from app.ports.email_sender import EmailSenderPort

log = get_logger("sending")

# 序列引擎会主动推进的状态（其余状态如 replied/unsubscribed/completed 即「已停」）。
_ACTIVE_STATES = (SequenceState.active, SequenceState.pending)


@dataclass
class SendOutcome:
    """send_one 的结果：既回传落库的邮件，也回传发送前的垃圾风险评分。"""

    message: OutboundMessage
    accepted: bool
    bounced: bool
    spam_score: int
    spam_warnings: list[str] = field(default_factory=list)


@dataclass
class TickReport:
    """一轮序列推进的统计。"""

    processed: int = 0
    sent: int = 0
    skipped: int = 0  # 被合规拦截/硬退信而永久停止
    completed: int = 0
    deferred: int = 0  # 瞬态失败（额度满/软退信/网络）→ 顺延重试，不推进不停用


def _as_aware(dt: datetime | None) -> datetime | None:
    """SQLite 读回的 datetime 可能是 naive；统一按 UTC 处理，避免相减报错。"""
    if dt is None:
        return None
    return dt if dt.tzinfo is not None else dt.replace(tzinfo=UTC)


class SendingService:
    def __init__(
        self,
        repo: SendingRepository,
        sender: EmailSenderPort,
        clock: ClockPort,
        compliance: ComplianceService,
        scheduler: Scheduler | None = None,
    ):
        self.repo = repo
        self.sender = sender
        self.clock = clock
        self.compliance = compliance
        # 默认轮询调度；未来可注入 Temporal 适配器而业务不变。
        self.scheduler = scheduler or PollingScheduler(clock)

    # ---- 域名 / 邮箱注册 ---------------------------------------------------
    async def register_domain(
        self,
        domain: str,
        *,
        spf_ok: bool = False,
        dkim_ok: bool = False,
        dmarc_ok: bool = False,
        reputation: float = 0.0,
        active: bool = True,
    ) -> SenderDomain:
        d = SenderDomain(
            domain=domain.strip().lower(),
            spf_ok=spf_ok,
            dkim_ok=dkim_ok,
            dmarc_ok=dmarc_ok,
            reputation=reputation,
            active=active,
        )
        await self.repo.add(d)
        return d

    async def register_mailbox(
        self,
        sender_domain_id: str,
        email: str,
        *,
        warmup_stage: WarmupStage = WarmupStage.w1,
        active: bool = True,
    ) -> SenderMailbox:
        now = self.clock.now()
        mb = SenderMailbox(
            sender_domain_id=sender_domain_id,
            email=email.strip().lower(),
            warmup_stage=warmup_stage,
            warmup_started_at=now,
            sent_today=0,
            last_reset_date=now.date().isoformat(),
            active=active,
        )
        await self.repo.add(mb)
        return mb

    # ---- 预热与每日频控重置 ------------------------------------------------
    async def warmup_tick(self) -> dict:
        """周期性调用：满 7 天推进预热阶段；跨日重置 sent_today。

        阶段推进用 domain.rules.next_warmup_stage（纯函数），每日上限随阶段自动提高。
        """
        now = self.clock.now()
        today = now.date().isoformat()
        advanced = 0
        reset = 0
        for mb in await self.repo.list_mailboxes():
            # 跨日 → 清零当日计数
            if mb.last_reset_date != today:
                mb.sent_today = 0
                mb.last_reset_date = today
                reset += 1
            # 预热推进：当前阶段满 7 天升一级
            started = _as_aware(mb.warmup_started_at) or now
            days_in_stage = (now - started).days
            new_stage = next_warmup_stage(mb.warmup_stage, days_in_stage)
            if new_stage != mb.warmup_stage:
                mb.warmup_stage = new_stage
                mb.warmup_started_at = now  # 新阶段重新计时
                advanced += 1
        await self.repo.flush()
        return {"advanced": advanced, "reset": reset}

    # ---- 挑选可用发信邮箱（频控核心）--------------------------------------
    async def pick_available_mailbox(self) -> SenderMailbox | None:
        """选一个「还有当日额度」的邮箱。

        跳过：① 停用邮箱；② 所在域 DNS 三件套未达标或域停用；③ 当日已达 cap 的邮箱。
        没有可用邮箱则返回 None（调用方据此暂停发送，绝不硬发爆量毁信誉）。
        """
        domains = await self.repo.domains_by_id()
        for mb in await self.repo.list_active_mailboxes():
            domain = domains.get(mb.sender_domain_id)
            if domain is None or not domain.sendable:
                continue  # DNS 未达标的域不可发送
            cap = daily_cap_for_stage(mb.warmup_stage)
            if mb.sent_today < cap:
                return mb
        return None

    # ---- 发送一封（合规守卫 → 风险评分 → 投递 → 记录 → 退信闭环）----------
    async def send_one(
        self,
        to_email: str,
        subject: str,
        body: str,
        *,
        campaign_id: str | None = None,
        lead_id: str | None = None,
    ) -> SendOutcome:
        # 1) 合规硬守卫：个人邮箱/已抑制 → 抛 ComplianceError(403)。绝不 try/except 吞掉。
        await self.compliance.assert_sendable(to_email)

        # 2) 发送前给垃圾风险评分（不阻断，但随结果返回以便预警）
        spam = assess_spam_risk(subject, body)

        # 3) 频控：挑一个还有额度的邮箱；没有则拒绝发送（暂停优于爆量）
        mailbox = await self.pick_available_mailbox()
        if mailbox is None:
            raise ValidationError("无可用发信邮箱：额度已满或没有 DNS 达标的发信域")

        # 4) 投递（走端口，本地 fake 不真发）。强制注入一键退订头（合规红线，RFC 8058）。
        unsub_headers = self._unsubscribe_headers(to_email)
        result = await self.sender.send(
            OutboundEmail(
                to_email=to_email,
                from_email=mailbox.email,
                subject=subject,
                body_html=body,
                body_text=body,
                headers=unsub_headers,
            )
        )
        now = self.clock.now()
        is_bounce = (not result.accepted) and result.error == "hard_bounce"
        status = "sent" if result.accepted else ("bounced" if is_bounce else "failed")

        message = OutboundMessage(
            campaign_id=campaign_id,
            lead_id=lead_id,
            to_email=to_email.strip().lower(),
            from_mailbox_id=mailbox.id,
            subject=subject,
            body=body,
            status=status,
            message_id=result.message_id,
            sent_at=now if result.accepted else None,
            bounced=is_bounce,
        )
        await self.repo.add(message)
        # 5) 计入当日发送量（频控）
        mailbox.sent_today += 1

        # 6) 硬退信闭环：进全局抑制列表，永不再发
        if is_bounce:
            await self.compliance.add_suppression(
                to_email, SuppressionReason.hard_bounce, note="发送硬退信自动抑制"
            )
            log.info("send.hard_bounce", to=to_email)

        await self.repo.flush()
        return SendOutcome(
            message=message,
            accepted=result.accepted,
            bounced=is_bounce,
            spam_score=spam.score,
            spam_warnings=spam.warnings,
        )

    def _unsubscribe_headers(self, to_email: str) -> dict[str, str]:
        """生成 List-Unsubscribe 头（带签名的退订链接），满足批量发件人合规要求。"""
        from app.core.config import get_settings
        from app.core.security import sign

        settings = get_settings()
        addr = to_email.strip().lower()
        sig = sign(f"unsub:{addr}")
        base = settings.public_base_url.rstrip("/")
        url = f"{base}/api/sending/unsubscribe?email={addr}&sig={sig}"
        return {
            "List-Unsubscribe": f"<{url}>",
            "List-Unsubscribe-Post": "List-Unsubscribe=One-Click",
        }

    # ---- 序列：报名与推进 -------------------------------------------------
    async def enroll(
        self,
        lead_id: str | None,
        campaign_id: str | None,
        to_email: str,
        steps: list[dict],
    ) -> SequenceEnrollment:
        """把一条线索报名进序列。next_action_at=now → 第一步立即可发。"""
        enrollment = SequenceEnrollment(
            lead_id=lead_id,
            campaign_id=campaign_id,
            to_email=to_email.strip().lower(),
            state=SequenceState.active,
            step_index=0,
            next_action_at=self.clock.now(),
            steps=steps,
        )
        await self.repo.add(enrollment)
        return enrollment

    # 瞬态失败顺延重试的间隔（额度满/软退信/网络抖动）。
    _RETRY_AFTER = timedelta(hours=1)

    async def tick_sequences(self) -> TickReport:
        """推进所有到期序列：发下一步、排下一步、走到底则完成。

        关键：区分「永久失败」与「瞬态失败」，二者处理截然不同——
        - 永久失败（合规拦截 ComplianceError / 硬退信）：置 stopped，不再重试；
        - 瞬态失败（无可用邮箱=当日额度满 / 软退信 / 网络）：**不推进 step、不停用**，
          仅把 next_action_at 顺延，下一轮重试。绝不能把这类当永久失败丢弃线索；
        - **只有真正发送成功（accepted）才推进 step_index**，避免失败的一步被跳过且白占额度。
        """
        report = TickReport()
        due = await self.scheduler.due_enrollments(self.repo, _ACTIVE_STATES)
        now = self.clock.now()
        for enr in due:
            steps = list(enr.steps or [])
            if enr.step_index >= len(steps):
                enr.state = SequenceState.completed
                report.completed += 1
                continue
            report.processed += 1
            step = steps[enr.step_index]
            try:
                outcome = await self.send_one(
                    enr.to_email,
                    step.get("subject", ""),
                    step.get("body", ""),
                    campaign_id=enr.campaign_id,
                    lead_id=enr.lead_id,
                )
            except ComplianceError as exc:
                # 永久：个人邮箱/已抑制 → 停止，重试无意义
                enr.state = SequenceState.stopped
                report.skipped += 1
                log.info("sequence.step_stopped", to=enr.to_email, reason=str(exc))
                continue
            except Exception as exc:  # noqa: BLE001 - 无可用邮箱/网络等瞬态：顺延重试
                enr.next_action_at = now + self._RETRY_AFTER
                report.deferred += 1
                log.info("sequence.step_deferred", to=enr.to_email, reason=str(exc))
                continue

            if outcome.bounced:
                # 硬退信：send_one 已抑制该地址 → 停止序列
                enr.state = SequenceState.stopped
                report.skipped += 1
                continue
            if not outcome.accepted:
                # 软失败（SMTP 4xx/超时）：不推进 step，顺延重试
                enr.next_action_at = now + self._RETRY_AFTER
                report.deferred += 1
                log.info("sequence.step_soft_fail", to=enr.to_email)
                continue

            # 只有发送成功才推进
            report.sent += 1
            enr.step_index += 1
            if enr.step_index < len(steps):
                wait_days = int(steps[enr.step_index].get("wait_days", 0))
                enr.next_action_at = now + timedelta(days=wait_days)
            else:
                enr.state = SequenceState.completed
                report.completed += 1
        await self.repo.flush()
        return report

    # ---- 探针与反馈闭环 ---------------------------------------------------
    async def record_open(self, message_id: str) -> bool:
        msg = await self.repo.get_message_by_external_id(message_id)
        if msg is None:
            return False
        if msg.opened_at is None:
            msg.opened_at = self.clock.now()
        await self.repo.flush()
        return True

    async def record_click(self, message_id: str) -> bool:
        msg = await self.repo.get_message_by_external_id(message_id)
        if msg is None:
            return False
        now = self.clock.now()
        msg.clicked_at = now
        if msg.opened_at is None:  # 点击必然已打开
            msg.opened_at = now
        await self.repo.flush()
        return True

    async def record_reply(self, to_email: str) -> int:
        """「回复即停」：该地址所有进行中的 enrollment 置为 replied，停止后续。"""
        return await self._stop_enrollments(to_email, SequenceState.replied)

    async def record_unsubscribe(self, to_email: str) -> int:
        """退订：停止序列并加入抑制列表（永不再发）。"""
        await self.compliance.add_suppression(
            to_email, SuppressionReason.unsubscribe, note="收件人退订"
        )
        return await self._stop_enrollments(to_email, SequenceState.unsubscribed)

    async def record_bounce(self, to_email: str) -> int:
        """入站退信：加入抑制列表（永不再发）并停止该地址所有进行中序列。"""
        await self.compliance.add_suppression(
            to_email, SuppressionReason.hard_bounce, note="入站退信自动抑制"
        )
        return await self._stop_enrollments(to_email, SequenceState.stopped)

    async def record_complaint(self, to_email: str, message_id: str | None = None) -> int:
        """投诉：加入抑制列表、停止序列，并标记对应外发邮件 complained。"""
        await self.compliance.add_suppression(
            to_email, SuppressionReason.complaint, note="收件人投诉（垃圾邮件申诉）"
        )
        if message_id is not None:
            msg = await self.repo.get_message_by_external_id(message_id)
            if msg is not None:
                msg.complained = True
        return await self._stop_enrollments(to_email, SequenceState.unsubscribed)

    async def _stop_enrollments(self, to_email: str, state: SequenceState) -> int:
        enrollments = await self.repo.enrollments_by_email(to_email, _ACTIVE_STATES)
        for enr in enrollments:
            enr.state = state
        await self.repo.flush()
        return len(enrollments)

    # ---- 送达健康度 -------------------------------------------------------
    async def deliverability_stats(self) -> dict:
        """算退信率/投诉率，用 domain.rules.deliverability_action 给出 ok/warn/halt。"""
        total, bounced, complained = await self.repo.message_stats()
        bounce_rate = (bounced / total) if total else 0.0
        complaint_rate = (complained / total) if total else 0.0
        action = deliverability_action(bounce_rate, complaint_rate)
        return {
            "total": total,
            "bounced": bounced,
            "complained": complained,
            "bounce_rate": round(bounce_rate, 4),
            "complaint_rate": round(complaint_rate, 4),
            "action": action,
        }

"""序列调度器抽象与实现。

「找出到期该发下一步的 enrollment」这个动作被抽象成 Scheduler 端口：
- 现在用 PollingScheduler（拿 ClockPort 的当前时间，查库中 next_action_at<=now 的记录），
  由外部定时任务（cron / 后台 loop）周期性调用 SendingService.tick_sequences()。
- 未来若接入 Temporal / Celery 等工作流引擎，只需新增一个 TemporalScheduler 实现同一 Protocol
  （每条 enrollment 一个 durable timer，到点回调），**业务编排（service）一字不改**。

这与架构规范「换实现=加适配器+改装配一行，业务零改动」一致。
"""
from __future__ import annotations

from collections.abc import Sequence
from typing import Protocol

from app.domain.enums import SequenceState
from app.modules.sending.models import SequenceEnrollment
from app.modules.sending.repository import SendingRepository
from app.ports.clock import ClockPort


class Scheduler(Protocol):
    """序列调度端口：给定可推进的状态集合，返回此刻应被处理的 enrollment。"""

    async def due_enrollments(
        self, repo: SendingRepository, states: Sequence[SequenceState]
    ) -> list[SequenceEnrollment]: ...


class PollingScheduler:
    """轮询式调度：以「现在」为界，从库里捞出所有到期的 enrollment。

    确定性、无外部依赖，本地/CI 直接可跑；时间来自 ClockPort，故完全可测。
    """

    def __init__(self, clock: ClockPort):
        self.clock = clock

    async def due_enrollments(
        self, repo: SendingRepository, states: Sequence[SequenceState]
    ) -> list[SequenceEnrollment]:
        return await repo.due_enrollments(self.clock.now(), states)

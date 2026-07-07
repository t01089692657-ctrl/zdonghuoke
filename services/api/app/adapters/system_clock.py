"""真实系统时钟。两种模式都用它；测试里可替换为固定时钟。"""
from __future__ import annotations

from datetime import UTC, datetime


class SystemClock:
    def now(self) -> datetime:
        return datetime.now(UTC)

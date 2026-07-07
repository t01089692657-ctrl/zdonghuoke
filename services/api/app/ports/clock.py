"""时间端口。把「现在几点」抽象出来，让依赖时间的逻辑（预热、频控、序列）可测。"""
from __future__ import annotations

from datetime import datetime
from typing import Protocol


class ClockPort(Protocol):
    def now(self) -> datetime: ...

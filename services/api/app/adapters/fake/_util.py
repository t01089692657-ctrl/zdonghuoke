"""fake 适配器共用的确定性工具：用哈希把输入映射成稳定的伪随机结果。"""
from __future__ import annotations

import hashlib


def stable_int(*parts: str) -> int:
    """由输入生成稳定的非负整数（跨进程一致，不用 random 以保证可测）。"""
    h = hashlib.sha256("|".join(parts).encode("utf-8")).hexdigest()
    return int(h[:12], 16)


def pick(seq: list, *parts: str):
    return seq[stable_int(*parts) % len(seq)]

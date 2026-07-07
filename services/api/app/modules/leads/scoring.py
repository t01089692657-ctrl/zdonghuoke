"""线索匹配度评分（纯函数，可解释）。

刻意用透明的加权规则而非黑盒：每一分都能给出理由（score_reasons），
符合产品「可解释」原则。将来可由 AI 评分增强，但保留可解释输出契约。
"""
from __future__ import annotations

from app.domain.contracts import CompanyCandidate, LeadSearchQuery


def score_candidate(
    candidate: CompanyCandidate,
    query: LeadSearchQuery,
    *,
    has_verified_email: bool = False,
    has_corporate_email: bool = False,
) -> tuple[float, list[str]]:
    """返回 (0~100 分, 理由列表)。"""
    score = 40.0  # 基线：进入结果集即有一定价值
    reasons: list[str] = ["命中数据源检索"]

    if query.countries and candidate.country in query.countries:
        score += 12
        reasons.append(f"目标国匹配({candidate.country})")

    if (
        query.industry
        and candidate.industry
        and query.industry.lower() in candidate.industry.lower()
    ):
        score += 8
        reasons.append("行业匹配")

    customs = candidate.raw.get("customs") if candidate.raw else None
    if customs and customs.get("shipments_12m"):
        shipments = int(customs["shipments_12m"])
        bonus = min(shipments / 5, 20)
        score += bonus
        reasons.append(f"海关活跃采购({shipments}票/年)")

    if has_corporate_email:
        score += 10
        reasons.append("已获企业邮箱")
    if has_verified_email:
        score += 10
        reasons.append("邮箱验证通过")

    return round(min(score, 100.0), 1), reasons

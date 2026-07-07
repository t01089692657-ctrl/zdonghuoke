"""纯业务规则函数。无 IO、无副作用、可确定性单测。

集中放置「合规与送达」相关的关键判断：这些规则一旦出错影响面极大
（发错人、进垃圾箱、被封域名），所以刻意提到纯函数层、配足单测。
"""
from __future__ import annotations

import re
import unicodedata

from app.domain.enums import EmailType, WarmupStage

# 免费/个人邮箱域名黑名单。EmailType=personal 的邮箱默认禁止冷触达（合规红线）。
# 生产环境应扩充为可维护的完整清单（数百个），这里覆盖主流。
FREE_EMAIL_DOMAINS: frozenset[str] = frozenset(
    {
        "gmail.com", "googlemail.com", "yahoo.com", "yahoo.co.jp", "ymail.com",
        "hotmail.com", "outlook.com", "live.com", "msn.com", "aol.com",
        "icloud.com", "me.com", "mac.com", "protonmail.com", "proton.me",
        "gmx.com", "gmx.de", "mail.com", "zoho.com", "yandex.com", "yandex.ru",
        "163.com", "126.com", "qq.com", "foxmail.com", "sina.com", "sohu.com",
        "139.com", "189.cn", "aliyun.com", "naver.com", "hanmail.net", "daum.net",
    }
)

# 冷邮件常见垃圾触发词（进垃圾箱风险）。命中越多、送达风险越高。
SPAM_TRIGGER_WORDS: frozenset[str] = frozenset(
    {
        "free", "guarantee", "guaranteed", "act now", "limited time", "click here",
        "buy now", "order now", "cash", "cheap", "discount", "no obligation",
        "risk free", "winner", "congratulations", "urgent", "100%", "$$$",
        "amazing", "best price", "double your", "earn money", "extra income",
    }
)

_EMAIL_RE = re.compile(r"^[^@\s]+@([^@\s]+\.[^@\s]+)$")
_NON_ALNUM = re.compile(r"[^a-z0-9]+")


def email_domain(email: str) -> str | None:
    """提取并规范化邮箱域名（小写）。非法邮箱返回 None。"""
    m = _EMAIL_RE.match(email.strip().lower())
    return m.group(1) if m else None


def is_free_email_domain(domain: str) -> bool:
    return domain.strip().lower() in FREE_EMAIL_DOMAINS


def classify_email_type(email: str) -> EmailType:
    """判断企业邮箱 vs 个人邮箱。发送层据此执行合规拦截。"""
    domain = email_domain(email)
    if domain is None:
        return EmailType.unknown
    return EmailType.personal if is_free_email_domain(domain) else EmailType.corporate


def is_valid_email_syntax(email: str) -> bool:
    return email_domain(email) is not None


def _slug(text: str) -> str:
    """去重指纹用：转 ASCII、小写、去掉非字母数字。"""
    norm = unicodedata.normalize("NFKD", text).encode("ascii", "ignore").decode("ascii")
    return _NON_ALNUM.sub("", norm.lower())


def dedup_fingerprint(name: str, domain: str | None = None, country: str | None = None) -> str:
    """跨数据源识别「同一家公司」的指纹。

    优先用域名（最可靠）；无域名时退化为 规范化公司名 + 国家。
    """
    if domain:
        d = domain.strip().lower()
        d = d[4:] if d.startswith("www.") else d
        return f"d:{d}"
    parts = [_slug(name)]
    if country:
        parts.append(_slug(country))
    return "n:" + "|".join(p for p in parts if p)


def generate_email_patterns(first: str, last: str, domain: str) -> list[str]:
    """邮箱猜测兜底：已知姓名+域名，生成常见模式候选（按命中概率排序）。

    这些候选必须再经验证环节筛选，绝不能盲发（高退信会毁域名信誉）。
    """
    f = _slug(first)
    ln = _slug(last)
    d = domain.strip().lower()
    d = d[4:] if d.startswith("www.") else d
    if not f or not d:
        return []
    fi = f[0]
    raw = [
        f"{f}.{ln}@{d}" if ln else "",
        f"{f}@{d}",
        f"{fi}{ln}@{d}" if ln else "",
        f"{f}{ln}@{d}" if ln else "",
        f"{f}_{ln}@{d}" if ln else "",
        f"{fi}.{ln}@{d}" if ln else "",
        f"{ln}.{f}@{d}" if ln else "",
        f"{ln}{fi}@{d}" if ln else "",
    ]
    seen: list[str] = []
    for c in raw:
        if c and c not in seen:
            seen.append(c)
    return seen


class SpamAssessment:
    """垃圾风险评估结果。score 越高越危险（0~100），发送前给出警告。"""

    def __init__(self, score: int, triggers: list[str], warnings: list[str]):
        self.score = score
        self.triggers = triggers
        self.warnings = warnings

    @property
    def risky(self) -> bool:
        return self.score >= 50


def assess_spam_risk(subject: str, body: str) -> SpamAssessment:
    """启发式垃圾风险评分：触发词、大写比例、链接数、长度。"""
    text = f"{subject}\n{body}"
    low = text.lower()
    triggers = sorted({w for w in SPAM_TRIGGER_WORDS if w in low})
    warnings: list[str] = []
    score = min(len(triggers) * 12, 60)

    letters = [c for c in subject if c.isalpha()]
    if letters:
        caps_ratio = sum(1 for c in letters if c.isupper()) / len(letters)
        if caps_ratio > 0.5 and len(letters) > 6:
            score += 15
            warnings.append("主题行大写字母过多")

    link_count = len(re.findall(r"https?://", text))
    if link_count > 3:
        score += 15
        warnings.append(f"链接过多({link_count})")

    if subject.count("!") >= 2:
        score += 10
        warnings.append("感叹号过多")

    if triggers:
        warnings.append(f"命中垃圾词: {', '.join(triggers)}")

    return SpamAssessment(score=min(score, 100), triggers=triggers, warnings=warnings)


# ---- 预热与频控 ------------------------------------------------------------
# 每个预热阶段的每日发送上限（对标行业保守节奏：新域慢启动）。
WARMUP_DAILY_CAP: dict[WarmupStage, int] = {
    WarmupStage.w1: 10,
    WarmupStage.w2: 20,
    WarmupStage.w3: 40,
    WarmupStage.active: 50,
}


def daily_cap_for_stage(stage: WarmupStage) -> int:
    return WARMUP_DAILY_CAP[stage]


def next_warmup_stage(stage: WarmupStage, days_in_stage: int) -> WarmupStage:
    """预热推进：每个阶段满 7 天进入下一阶段，直到 active。"""
    if days_in_stage < 7:
        return stage
    order = [WarmupStage.w1, WarmupStage.w2, WarmupStage.w3, WarmupStage.active]
    idx = order.index(stage)
    return order[min(idx + 1, len(order) - 1)]


def mailboxes_needed(daily_target: int, per_mailbox_cap: int = 40) -> int:
    """产品化容量公式：日发 X 封需要几个发信邮箱。"""
    if daily_target <= 0:
        return 0
    return -(-daily_target // per_mailbox_cap)  # ceil 除法


def domains_needed(daily_target: int, per_domain_cap: int = 120) -> int:
    if daily_target <= 0:
        return 0
    return -(-daily_target // per_domain_cap)


# ---- 送达健康红线 ----------------------------------------------------------
BOUNCE_RATE_LIMIT = 0.02       # 退信率 >2% 危险
COMPLAINT_RATE_WARN = 0.001    # 投诉率 >0.1% 预警
COMPLAINT_RATE_HALT = 0.003    # 投诉率 >0.3% 熔断暂停


def deliverability_action(bounce_rate: float, complaint_rate: float) -> str:
    """根据退信/投诉率给出动作：ok | warn | halt。"""
    if complaint_rate >= COMPLAINT_RATE_HALT or bounce_rate >= BOUNCE_RATE_LIMIT * 2:
        return "halt"
    if complaint_rate >= COMPLAINT_RATE_WARN or bounce_rate >= BOUNCE_RATE_LIMIT:
        return "warn"
    return "ok"

"""领域纯规则单测。这些规则错了影响面最大（发错人/进垃圾箱），必须扎实覆盖。"""
from __future__ import annotations

from app.domain.enums import EmailType, WarmupStage
from app.domain.rules import (
    assess_spam_risk,
    classify_email_type,
    daily_cap_for_stage,
    dedup_fingerprint,
    deliverability_action,
    domains_needed,
    generate_email_patterns,
    is_free_email_domain,
    mailboxes_needed,
    next_warmup_stage,
)


class TestEmailClassification:
    def test_corporate_email(self):
        assert classify_email_type("john@acme-trading.com") is EmailType.corporate

    def test_personal_email_blocked(self):
        assert classify_email_type("john@gmail.com") is EmailType.personal
        assert classify_email_type("li@163.com") is EmailType.personal
        assert classify_email_type("k@qq.com") is EmailType.personal

    def test_invalid_email_unknown(self):
        assert classify_email_type("not-an-email") is EmailType.unknown

    def test_free_domain_list(self):
        assert is_free_email_domain("gmail.com")
        assert not is_free_email_domain("acme.com")


class TestDedup:
    def test_same_domain_same_fingerprint(self):
        a = dedup_fingerprint("Acme Trading", "acme.com", "US")
        b = dedup_fingerprint("ACME Trading Co", "www.acme.com", "US")
        assert a == b  # 域名一致即同一家（忽略 www 与名称差异）

    def test_no_domain_falls_back_to_name_country(self):
        a = dedup_fingerprint("Acme Trading", None, "US")
        b = dedup_fingerprint("acme  trading", None, "us")
        assert a == b

    def test_different_companies_differ(self):
        assert dedup_fingerprint("Acme", "acme.com") != dedup_fingerprint("Globex", "globex.com")


class TestEmailPatterns:
    def test_generates_ordered_candidates(self):
        pats = generate_email_patterns("John", "Smith", "acme.com")
        assert "john.smith@acme.com" in pats
        assert pats[0] == "john.smith@acme.com"
        assert all("@acme.com" in p for p in pats)

    def test_strips_www(self):
        pats = generate_email_patterns("John", "Smith", "www.acme.com")
        assert all("www." not in p for p in pats)

    def test_empty_when_no_first_or_domain(self):
        assert generate_email_patterns("", "Smith", "acme.com") == []


class TestSpamRisk:
    def test_clean_email_low_score(self):
        a = assess_spam_risk("Quick question about your imports", "Hi, would a catalog help?")
        assert not a.risky

    def test_spammy_email_flagged(self):
        a = assess_spam_risk("FREE!! ACT NOW GUARANTEED", "Click here to WIN cash 100% risk free!!")
        assert a.risky
        assert a.triggers


class TestWarmupAndThrottle:
    def test_daily_caps_increase(self):
        assert daily_cap_for_stage(WarmupStage.w1) < daily_cap_for_stage(WarmupStage.active)

    def test_stage_advances_after_7_days(self):
        assert next_warmup_stage(WarmupStage.w1, 6) is WarmupStage.w1
        assert next_warmup_stage(WarmupStage.w1, 7) is WarmupStage.w2
        assert next_warmup_stage(WarmupStage.active, 30) is WarmupStage.active

    def test_capacity_formulas(self):
        assert mailboxes_needed(0) == 0
        assert mailboxes_needed(360, per_mailbox_cap=40) == 9
        assert mailboxes_needed(41, per_mailbox_cap=40) == 2
        assert domains_needed(360, per_domain_cap=120) == 3


class TestDeliverabilityGuard:
    def test_ok(self):
        assert deliverability_action(0.005, 0.0005) == "ok"

    def test_warn(self):
        assert deliverability_action(0.025, 0.0005) == "warn"

    def test_halt(self):
        assert deliverability_action(0.01, 0.004) == "halt"

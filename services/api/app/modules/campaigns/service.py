"""campaigns 服务：活动与序列的编排者。

职责边界：本模块负责「建活动 → 定序列 → 从线索备好目标 → 激活」，把 CampaignTarget
备好并暴露「可被 sending 消费」的查询。真正的定时发信、频控、探针由 sending 模块的
enroll/tick 完成 —— 两者通过 CampaignTarget 这张表解耦，互不 import 对方的编排逻辑。
"""
from __future__ import annotations

from app.core.errors import NotFoundError, ValidationError
from app.domain.enums import CampaignStatus, EmailStatus, EmailType
from app.modules.campaigns.models import Campaign, CampaignTarget
from app.modules.campaigns.repository import CampaignRepository
from app.modules.leads.models import Contact

# 可发送邮箱状态：valid（已验证）/ unknown（未验证但语法/MX 通过，允许尝试）。
# invalid / catch_all 不进冷触达序列。（用枚举成员，StrEnum 与其字符串值等价，
# 因此无论字段是枚举还是从库里读回的字符串都能正确匹配。）
_SENDABLE_STATUSES = frozenset({EmailStatus.valid, EmailStatus.unknown})


def default_sequence() -> list[dict]:
    """默认 4 步开发信序列，3-7-7 节奏（Day0/3/10/17）。

    wait_days 为「相对上一步」的等待天数：0→3→7→7，累计触达日为第 0/3/10/17 天。
    subject/body 为占位模板，写信 agent 集成时会做字段约束式个性化替换。
    """
    return [
        {
            "step": 1,
            "wait_days": 0,
            "subject": "Quick question about {{company}}",
            "body": (
                "Hi {{first_name}}, I came across {{company}} and think we may be able to "
                "help with {{value_prop}}. Worth a quick chat?"
            ),
        },
        {
            "step": 2,
            "wait_days": 3,
            "subject": "Re: Quick question about {{company}}",
            "body": (
                "Hi {{first_name}}, just floating this back to the top of your inbox — "
                "happy to share a short example relevant to {{company}}."
            ),
        },
        {
            "step": 3,
            "wait_days": 7,
            "subject": "A relevant example for {{company}}",
            "body": (
                "Hi {{first_name}}, sharing a quick case that mirrors {{company}}'s situation. "
                "Would it make sense to connect this week?"
            ),
        },
        {
            "step": 4,
            "wait_days": 7,
            "subject": "Should I close the loop?",
            "body": (
                "Hi {{first_name}}, I don't want to keep cluttering your inbox — if now isn't "
                "the right time just let me know and I'll follow up down the road."
            ),
        },
    ]


class CampaignService:
    def __init__(self, repo: CampaignRepository):
        self.repo = repo

    # ---- 活动 CRUD ---------------------------------------------------------
    async def create_campaign(
        self,
        *,
        name: str,
        icp_config: dict | None = None,
        sequence_def: list[dict] | None = None,
        created_by: str | None = None,
    ) -> Campaign:
        """建活动。未显式给序列则套用默认 3-7-7 四步序列。"""
        if not name or not name.strip():
            raise ValidationError("活动名称不能为空")
        campaign = Campaign(
            name=name.strip(),
            icp_config=icp_config or {},
            sequence_def=sequence_def if sequence_def else default_sequence(),
            status=CampaignStatus.draft,
            created_by=created_by,
        )
        campaign.targets = []  # transient 阶段先初始化集合，避免后续惰性加载
        return await self.repo.add(campaign)

    async def list_campaigns(self, *, offset: int, limit: int) -> tuple[list[Campaign], int]:
        return await self.repo.list(offset=offset, limit=limit)

    async def get_campaign(self, campaign_id: str) -> Campaign | None:
        return await self.repo.get(campaign_id)

    async def _get_or_404(self, campaign_id: str) -> Campaign:
        campaign = await self.repo.get(campaign_id)
        if campaign is None:
            raise NotFoundError("活动不存在")
        return campaign

    async def activate(self, campaign_id: str) -> Campaign:
        """draft → active。只有草稿可激活；无序列或无目标则拒绝，避免激活空活动。"""
        campaign = await self._get_or_404(campaign_id)
        # 用 == 而非 is：从库里读回的 status 是普通字符串（列为 String，非 Enum 类型），
        # StrEnum 与其字符串值相等，两种形态都能正确判断。
        if campaign.status != CampaignStatus.draft:
            raise ValidationError(f"仅 draft 活动可激活，当前状态 {campaign.status}")
        if not campaign.sequence_def:
            raise ValidationError("活动缺少序列定义，无法激活")
        campaign.status = CampaignStatus.active
        await self.repo.flush()
        return campaign

    # ---- 从线索加目标 ------------------------------------------------------
    async def add_targets_from_leads(
        self,
        campaign_id: str,
        *,
        company_ids: list[str] | None = None,
    ) -> dict:
        """从 leads.Company/Contact 取「可发送联系人」加入 targets。

        company_ids 为空表示取全部公司（简单筛选入口，将来可扩展为按 ICP/评分筛选）。
        可发送 = 企业邮箱 + 邮箱状态为 valid/unknown + 邮箱非空。已入队的 contact 跳过（去重）。
        """
        campaign = await self._get_or_404(campaign_id)
        companies = await self.repo.load_companies(company_ids)
        already = await self.repo.existing_contact_ids(campaign_id)

        added = 0
        skipped = 0
        new_targets: list[CampaignTarget] = []
        for company in companies:
            for contact in company.contacts:
                if not self._is_sendable(contact):
                    skipped += 1
                    continue
                if contact.id in already:
                    skipped += 1
                    continue
                target = CampaignTarget(
                    campaign_id=campaign.id,
                    company_id=company.id,
                    contact_id=contact.id,
                    to_email=contact.email,
                    state="pending",
                )
                await self.repo.add_target(target, flush=False)
                new_targets.append(target)
                already.add(contact.id)
                added += 1

        await self.repo.flush()
        return {"added": added, "skipped": skipped, "targets": new_targets}

    @staticmethod
    def _is_sendable(contact: Contact) -> bool:
        """判断联系人是否可进入冷触达序列（合规 + 送达前置门槛）。

        用 == / in（值相等）而非 is（同一对象）：字段可能是枚举成员，也可能是从库里
        读回的普通字符串；StrEnum 与其字符串值等价，两种形态都能命中。
        """
        if not contact.email:
            return False
        if contact.email_type != EmailType.corporate:
            return False
        return contact.email_status in _SENDABLE_STATUSES

    # ---- 供 sending 模块消费的查询 -----------------------------------------
    async def enrollable_targets(self, campaign_id: str) -> list[CampaignTarget]:
        """返回活动中「待入序列」的目标（state=pending）。

        集成衔接点（TODO / 主程序）：活动激活后，由主程序/集成层读取此查询，把这些
        pending target enroll 到 sending 模块的序列引擎（sending 会把 state 推进为
        enrolled，并在其内部维护 SequenceState 状态机）。本模块不 import sending，
        避免与并行开发的 sending 产生耦合与导入错误。
        """
        campaign = await self._get_or_404(campaign_id)
        return await self.repo.list_targets_by_state(campaign.id, "pending")

    async def list_targets(self, campaign_id: str) -> list[CampaignTarget]:
        await self._get_or_404(campaign_id)
        return await self.repo.list_targets(campaign_id)

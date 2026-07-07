"""灌入演示数据：跑一遍找客户流水线（本地 fake 模式）。

用法：  make seed   或   uv run python -m app.scripts.seed
"""
from __future__ import annotations

import asyncio

from app.core.database import SessionLocal, init_db
from app.domain.contracts import LeadSearchQuery
from app.modules.leads.router import build_lead_service


async def main() -> None:
    await init_db()
    async with SessionLocal() as session:
        svc = build_lead_service(session)
        query = LeadSearchQuery(
            keywords=["solar wall light"],
            hs_code="940540",
            countries=["US", "DE", "AE"],
            industry="Wholesale",
            limit=20,
        )
        result = await svc.discover(query, enrich=True)
        await session.commit()
        print("演示数据已生成：")
        print(f"  检索到候选: {result['discovered']}")
        print(f"  新建公司:   {result['new_companies']}")
        print(f"  合并重复:   {result['merged_duplicates']}")
        print(f"  找到联系人: {result['contacts_found']}")
        print(f"  可发送联系人: {result['sendable_contacts']}")


if __name__ == "__main__":
    asyncio.run(main())

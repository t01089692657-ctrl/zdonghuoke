"""线索服务：找客户流水线的编排者。

discover() 串起整条 P0 链路（全部经端口，本地用 fake、云端用真实，零改动）：
  数据源检索 → 跨源去重合并 → (可选)瀑布富化 → 邮箱验证 → 企业/个人邮箱标注
  → 匹配度评分 → 落库。
这就是「麦穗五步法」的第 2、3 步在我们架构下的具体实现，且每一步可独立替换。
"""
from __future__ import annotations

from app.core.logging import get_logger
from app.domain.contracts import CompanyCandidate, LeadSearchQuery
from app.domain.enums import EmailType
from app.domain.rules import dedup_fingerprint
from app.modules.enrichment.service import EnrichmentService
from app.modules.leads.models import Company, Contact
from app.modules.leads.repository import LeadRepository
from app.modules.leads.scoring import score_candidate
from app.ports.clock import ClockPort
from app.ports.data_source import DataSourcePort

log = get_logger("leads")


class LeadService:
    def __init__(
        self,
        repo: LeadRepository,
        data_sources: tuple[DataSourcePort, ...],
        enrichment: EnrichmentService,
        clock: ClockPort,
    ):
        self.repo = repo
        self.data_sources = data_sources
        self.enrichment = enrichment
        self.clock = clock

    async def discover(self, req_query: LeadSearchQuery, *, enrich: bool) -> dict:
        """执行找客户流水线，返回统计与落库后的公司列表。"""
        # 1) 多源检索
        all_candidates: list[CompanyCandidate] = []
        for source in self.data_sources:
            try:
                found = await source.search(req_query)
            except Exception as e:
                log.warning("discover.source_failed", source=source.source_type.value, error=str(e))
                continue
            all_candidates.extend(found)

        # 2) 跨源去重（内存内先合并，再与库中已有对齐）
        # 关键：命中重复时【合并字段】而非丢弃后到者——否则海关采购信号(评分最大项)
        # 可能被先到的搜索源结果覆盖清零。
        merged: dict[str, CompanyCandidate] = {}
        duplicates = 0
        for c in all_candidates:
            fp = dedup_fingerprint(c.name, c.domain, c.country)
            if fp in merged:
                merged[fp] = self._merge_candidates(merged[fp], c)
                duplicates += 1
            else:
                merged[fp] = c

        new_count = 0
        contacts_found = 0
        sendable = 0
        companies: list[Company] = []

        for fp, cand in merged.items():
            existing = await self.repo.find_by_fingerprint(fp)
            if existing is not None:
                # 已有公司：补充来源留痕，不重复建
                existing.provenance = list(existing.provenance) + [self._prov(cand)]
                companies.append(existing)
                duplicates += 1
                continue

            # 构建为 transient 对象，先把 contacts 都 append 好，最后统一 flush。
            company = Company(
                name=cand.name,
                domain=cand.domain,
                website=cand.website,
                country=cand.country,
                industry=cand.industry,
                description=cand.description,
                dedup_fingerprint=fp,
                source_type=cand.source_type.value,
                provenance=[self._prov(cand)],
                raw=cand.raw,
            )
            new_count += 1

            has_corp = False
            has_verified = False
            contacts: list[Contact] = []

            # 3) 富化 + 验证（可选）。单个公司富化/验证失败不能拖垮整批 discover：
            #    与数据源检索的容错对称——捕获后跳过该公司的联系人，其余照常。
            enriched = []
            if enrich and cand.domain:
                try:
                    enriched = await self.enrichment.enrich_domain(cand.domain)
                except Exception as e:  # noqa: BLE001
                    log.warning("discover.enrich_failed", domain=cand.domain, error=str(e))
                    enriched = []
            if enriched:
                for ec in enriched:
                    contacts_found += 1
                    is_corp = ec.verification.email_type is EmailType.corporate
                    is_sendable = is_corp and ec.verification.status.value in ("valid", "unknown")
                    first_corp = is_corp and not has_corp
                    if is_corp:
                        has_corp = True
                    if ec.verification.status.value == "valid":
                        has_verified = True
                    if is_sendable:
                        sendable += 1
                    contacts.append(
                        Contact(
                            first_name=ec.candidate.first_name,
                            last_name=ec.candidate.last_name,
                            title=ec.candidate.title,
                            email=ec.candidate.email,
                            email_status=ec.verification.status,
                            email_type=ec.verification.email_type,
                            enrichment_provider=ec.candidate.provider,
                            provenance=[{"provider": ec.candidate.provider}],
                            is_primary=first_corp,
                        )
                    )
            # 一次性赋值整个集合（即便为空）：在 transient 阶段初始化内存集合，
            # 之后 flush/序列化都不会再触发异步惰性加载。cascade 负责落库。
            company.contacts = contacts

            # 4) 评分
            score, reasons = score_candidate(
                cand, req_query, has_verified_email=has_verified, has_corporate_email=has_corp
            )
            company.score = score
            company.score_reasons = reasons

            # 对象图构建完成，此时才加入会话（保持到最后统一 flush）
            await self.repo.add(company, flush=False)
            companies.append(company)

        await self.repo.flush()  # 一次性落库，避免逐条 flush 触发关系惰性加载

        return {
            "discovered": len(all_candidates),
            "new_companies": new_count,
            "merged_duplicates": duplicates,
            "contacts_found": contacts_found,
            "sendable_contacts": sendable,
            "companies": companies,
        }

    @staticmethod
    def _merge_candidates(base: CompanyCandidate, extra: CompanyCandidate) -> CompanyCandidate:
        """同一家公司跨源合并：base 缺失的字段用 extra 补，raw 信号并集（不丢海关等信号）。"""
        merged_raw = {**(extra.raw or {}), **(base.raw or {})}
        return base.model_copy(
            update={
                "name": base.name or extra.name,
                "domain": base.domain or extra.domain,
                "website": base.website or extra.website,
                "country": base.country or extra.country,
                "industry": base.industry or extra.industry,
                "description": base.description or extra.description,
                "raw": merged_raw,
            }
        )

    def _prov(self, cand: CompanyCandidate) -> dict:
        return {
            "source": cand.source_type.value,
            "ref": cand.source_ref,
            "at": self.clock.now().isoformat(),
        }

    async def list_companies(self, *, offset: int, limit: int) -> tuple[list[Company], int]:
        return await self.repo.list(offset=offset, limit=limit)

    async def get_company(self, company_id: str) -> Company | None:
        return await self.repo.get(company_id)

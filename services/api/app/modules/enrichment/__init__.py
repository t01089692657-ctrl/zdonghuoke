"""富化模块：瀑布式补全联系人邮箱 + 验证。

瀑布(waterfall)：按供应商顺序依次查询，命中即停 —— 平衡命中率与单价成本。
供应商顺序由 deps.get_enrichment_providers() 决定（顺序即优先级）。
"""

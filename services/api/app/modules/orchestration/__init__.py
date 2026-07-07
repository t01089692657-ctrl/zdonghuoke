"""编排模块（集成层）：把各业务模块串成完整获客闭环。

对标麦穗「五步法」的自动化流水线，在我们架构下的落点：
  campaign 目标(campaigns) → AI 研究+写信(agent) → 人审(agent HITL)
  → 批准后入发送序列(sending) → 序列推进/预热(sending) → 入站回复分诊(agent)
  → 停序列/抑制/CRM 阶段跃迁(sending+compliance+crm)

设计原则：本模块只「编排」，不含业务规则 —— 全部通过各模块的 service 组合，
是唯一允许同时依赖多个业务模块 service 的地方。业务模块之间依旧互不依赖。
"""

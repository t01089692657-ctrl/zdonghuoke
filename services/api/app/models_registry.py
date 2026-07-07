"""汇总所有模块的 ORM 模型，供 Base.metadata.create_all 建表时收集。

新增模块时在此登记其 models 模块的 import。（生产用 Alembic 迁移替代 create_all。）
"""
# ruff: noqa: F401
from app.modules.agent import models as _agent_models
from app.modules.analytics import models as _analytics_models
from app.modules.campaigns import models as _campaigns_models
from app.modules.compliance import models as _compliance_models
from app.modules.crm import models as _crm_models
from app.modules.leads import models as _leads_models
from app.modules.sending import models as _sending_models

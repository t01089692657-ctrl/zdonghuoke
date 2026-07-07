"""analytics 模块 ORM 模型。

本模块以只读聚合为主，指标直接从 leads（及未来 sending）的数据实时计算，
不落自己的持久化模型，故此处保持为空（models_registry 仍会 import 但无表可建）。
"""
from __future__ import annotations

# 看板为只读聚合层，暂无 ORM 模型。若将来需要物化视图/快照缓存再在此定义。

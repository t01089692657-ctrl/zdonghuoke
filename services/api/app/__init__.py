"""ZDHK 自动获客系统后端。

架构：模块化单体 + 端口与适配器（Hexagonal）。
- app.domain   纯业务规则（无 IO，可单测）
- app.ports    外部依赖的抽象接口
- app.adapters 接口的实现（fake 本地 / real 云端）
- app.modules  业务模块（每个是一个有界上下文）
- app.core     配置、数据库、日志、依赖注入等横切基础设施
- app.api      HTTP 路由装配（薄层）
"""

__version__ = "0.1.0"

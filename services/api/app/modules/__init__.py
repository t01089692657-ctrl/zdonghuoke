"""业务模块（有界上下文）。每个模块自成一体：models(ORM) / schemas(API) /
repository(持久化) / service(业务编排) / router(HTTP)。模块间通过领域契约与端口交互，
不直接依赖彼此的 ORM 模型，以保持低耦合、可独立演进与替换。
"""

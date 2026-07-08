"""集中式配置。所有配置来自环境变量（12-Factor），本地开发从 .env 读取。

`ADAPTER_MODE` 是核心开关：local 用 fake 适配器，cloud 用真实适配器。
业务代码永远不读环境变量 —— 只读这里的 settings，便于测试与替换。
"""
from __future__ import annotations

from enum import StrEnum
from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class AppEnv(StrEnum):
    local = "local"
    staging = "staging"
    production = "production"


class AdapterMode(StrEnum):
    local = "local"  # fake 适配器，零外部依赖
    cloud = "cloud"  # 真实适配器


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env", env_file_encoding="utf-8", extra="ignore", case_sensitive=False
    )

    # 运行环境
    app_env: AppEnv = AppEnv.local
    adapter_mode: AdapterMode = AdapterMode.local
    log_level: str = "INFO"
    log_json: bool = False

    # 数据库：默认 SQLite（零 Docker 也能跑），docker-compose 会注入 Postgres URL
    database_url: str = "sqlite+aiosqlite:///./local.db"
    redis_url: str = "redis://localhost:6379/0"

    # API
    api_host: str = "0.0.0.0"
    api_port: int = 8000
    api_cors_origins: str = "http://localhost:3000"

    # 大模型（OpenAI 兼容；cloud 模式生效）
    llm_base_url: str = "https://api.deepseek.com/v1"
    llm_api_key: str = ""
    llm_model_writer: str = "deepseek-chat"
    llm_model_classifier: str = "deepseek-chat"

    # ---- 供应商选择（cloud 模式下选「付费 API」还是「免费/自建」变体）----------
    # search:  apollo（最全2.7亿库，推荐） | serper（付费Google） | searxng（自建免费）
    # enrich:  apollo（最全，推荐） | hunter（付费） | website（免费抓官网） | hunter+website
    # verify:  zerobounce（付费高准，推荐） | local（免费，语法+MX+一次性域名检测）
    # sender:  ses（Amazon SES，推荐） | smtp（任意SMTP，含Brevo/Mailtrap免费档，仅测试用）
    search_provider: str = "serper"
    enrich_provider: str = "hunter"
    verify_provider: str = "zerobounce"
    sender_provider: str = "ses"

    # 数据源 / enrichment / 验证（cloud 模式生效）
    serp_api_key: str = ""
    customs_api_key: str = ""
    maps_api_key: str = ""
    hunter_api_key: str = ""
    snov_api_key: str = ""
    apollo_api_key: str = ""       # Apollo.io（找客户+挖邮箱一体，最全面）
    email_verify_api_key: str = ""
    searxng_url: str = "http://localhost:8888"  # 自建 SearXNG 地址（免费搜索源）

    # 邮件发送（Amazon SES；cloud 模式生效）
    aws_region: str = "us-east-1"
    aws_access_key_id: str = ""
    aws_secret_access_key: str = ""
    ses_configuration_set: str = "zdhk-outbound"

    # 通用 SMTP 发送（sender_provider=smtp 时生效；可填 Brevo/Mailtrap 等免费档）
    smtp_host: str = ""
    smtp_port: int = 587
    smtp_user: str = ""
    smtp_password: str = ""
    smtp_use_tls: bool = True

    # 安全
    secret_key: str = "dev-only-change-me-in-production"
    access_token_expire_minutes: int = 1440
    # 对外可访问的基础 URL（退订/追踪链接用；Mac mini 经 Cloudflare Tunnel 时填公网域名）
    public_base_url: str = "http://localhost:8000"

    @property
    def cors_origin_list(self) -> list[str]:
        return [o.strip() for o in self.api_cors_origins.split(",") if o.strip()]

    @property
    def is_local_adapters(self) -> bool:
        return self.adapter_mode is AdapterMode.local


@lru_cache
def get_settings() -> Settings:
    """单例。整个进程只解析一次配置。"""
    return Settings()

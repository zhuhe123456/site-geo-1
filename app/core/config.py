from __future__ import annotations

import os
from dataclasses import dataclass

from dotenv import load_dotenv


# 从 .env 文件加载环境变量
load_dotenv()


def _get_float(name: str, default: float) -> float:
    """从环境变量读取浮点数，无效时返回默认值"""
    value = os.getenv(name)
    if value is None:
        return default
    try:
        return float(value)
    except ValueError:
        return default


def _get_int(name: str, default: int) -> int:
    """从环境变量读取整数，无效时返回默认值"""
    value = os.getenv(name)
    if value is None:
        return default
    try:
        return int(value)
    except ValueError:
        return default


def _get_bool(name: str, default: bool) -> bool:
    """从环境变量读取布尔值，无效时返回默认值。"""
    value = os.getenv(name)
    if value is None:
        return default
    return value.lower() in {"1", "true", "yes", "y", "on"}


@dataclass(frozen=True)
class Settings:
    """全局配置类（不可变），所有配置项从环境变量读取，提供合理默认值"""

    # 应用基础信息
    app_name: str = os.getenv("APP_NAME", "geo-audit-service")
    environment: str = os.getenv("APP_ENV", "development")
    debug: bool = os.getenv("APP_DEBUG", "false").lower() == "true"
    host: str = os.getenv("HOST", "0.0.0.0")
    port: int = _get_int("PORT", 8023)
    log_level: str = os.getenv("LOG_LEVEL", "INFO").upper()

    # HTTP 请求参数
    request_timeout_seconds: float = _get_float("REQUEST_TIMEOUT_SECONDS", 15.0)
    request_retries: int = _get_int("REQUEST_RETRIES", 3)

    # 站点地图抓取限制
    max_sitemap_urls: int = _get_int("MAX_SITEMAP_URLS", 50)
    max_sitemap_indexes: int = _get_int("MAX_SITEMAP_INDEXES", 10)

    # 审计结果缓存配置
    cache_ttl_days: int = _get_int("CACHE_TTL_DAYS", 7)
    cache_dir: str = os.getenv("CACHE_DIR", ".cache/audits")
    demo_access_token: str = os.getenv("DEMO_ACCESS_TOKEN", "").strip()
    demo_token_db_path: str = os.getenv("DEMO_TOKEN_DB_PATH", ".data/demo_tokens.sqlite3")
    token_admin_key: str = os.getenv("TOKEN_ADMIN_KEY", "").strip()
    api_token_required: bool = _get_bool("API_TOKEN_REQUIRED", True)
    token_log_retention_days: int = _get_int("TOKEN_LOG_RETENTION_DAYS", 90)

    # 站点资产库（MySQL）配置
    mysql_enabled: bool = _get_bool("MYSQL_ENABLED", False)
    mysql_host: str = os.getenv("MYSQL_HOST", "")
    mysql_port: int = _get_int("MYSQL_PORT", 3306)
    mysql_database: str = os.getenv("MYSQL_DATABASE", "")
    mysql_user: str = os.getenv("MYSQL_USER", "")
    mysql_password: str = os.getenv("MYSQL_PASSWORD", "")
    mysql_connect_timeout_seconds: int = _get_int("MYSQL_CONNECT_TIMEOUT_SECONDS", 5)
    mysql_read_timeout_seconds: int = _get_int("MYSQL_READ_TIMEOUT_SECONDS", 15)
    mysql_write_timeout_seconds: int = _get_int("MYSQL_WRITE_TIMEOUT_SECONDS", 15)
    mysql_store_raw_html: bool = _get_bool("MYSQL_STORE_RAW_HTML", False)
    mysql_store_parsed_content: bool = _get_bool("MYSQL_STORE_PARSED_CONTENT", True)
    discovery_fetch_concurrency: int = _get_int("DISCOVERY_FETCH_CONCURRENCY", 8)
    mysql_retry_attempts: int = _get_int("MYSQL_RETRY_ATTEMPTS", 3)
    mysql_retry_backoff_ms: int = _get_int("MYSQL_RETRY_BACKOFF_MS", 300)
    mysql_pool_size: int = _get_int("MYSQL_POOL_SIZE", 5)
    mysql_pool_max_overflow: int = _get_int("MYSQL_POOL_MAX_OVERFLOW", 10)
    mysql_pool_timeout_seconds: float = _get_float("MYSQL_POOL_TIMEOUT_SECONDS", 10.0)
    mysql_pool_recycle_seconds: int = _get_int("MYSQL_POOL_RECYCLE_SECONDS", 1800)
    mysql_pool_pre_ping: bool = _get_bool("MYSQL_POOL_PRE_PING", True)
    mysql_recovery_probe_interval_seconds: float = _get_float("MYSQL_RECOVERY_PROBE_INTERVAL_SECONDS", 1.0)

    # 爬虫 UA 标识
    default_user_agent: str = os.getenv(
        "DEFAULT_USER_AGENT",
        (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/131.0.0.0 Safari/537.36"
        ),
    )

    # 是否允许使用 Playwright 进行浏览器渲染
    allow_playwright: bool = os.getenv("ALLOW_PLAYWRIGHT", "false").lower() == "true"
    google_render_timeout_seconds: float = _get_float("GOOGLE_RENDER_TIMEOUT_SECONDS", 25.0)
    google_render_network_idle_seconds: float = _get_float("GOOGLE_RENDER_NETWORK_IDLE_SECONDS", 5.0)
    allow_benchmark_proxy_ips: bool = _get_bool("ALLOW_BENCHMARK_PROXY_IPS", False)

    # LLM 调用配置（OpenRouter）
    llm_request_timeout_seconds: float = _get_float("LLM_REQUEST_TIMEOUT_SECONDS", 30.0)
    default_openrouter_model: str = os.getenv("DEFAULT_OPENROUTER_MODEL", "openai/gpt-4.1")
    openrouter_api_key: str | None = os.getenv("OPENROUTER_API_KEY")
    openrouter_base_url: str = os.getenv("OPENROUTER_BASE_URL", "https://openrouter.ai/api/v1")
    openrouter_site_url: str = os.getenv("OPENROUTER_SITE_URL", "http://127.0.0.1:8023")
    openrouter_app_name: str = os.getenv("OPENROUTER_APP_NAME", "geo-audit-service")

    # Semrush 外链数据集成配置
    semrush_api_key: str | None = os.getenv("SEMRUSH_API_KEY")
    semrush_base_url: str = os.getenv("SEMRUSH_BASE_URL", "https://api.semrush.com/")
    semrush_target_type: str = os.getenv("SEMRUSH_TARGET_TYPE", "root_domain")
    semrush_enabled: bool = os.getenv("SEMRUSH_ENABLED", "true").lower() == "true"


# 全局单例配置对象
settings = Settings()

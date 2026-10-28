from __future__ import annotations

from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
        case_sensitive=False,
    )

    app_env: str = "dev"
    app_name: str = "Roxy Pipeline"

    # local dev defaults to SQLite so the API can run without Docker
    database_url: str = "sqlite+aiosqlite:///./tmp/roxy.db"

    # Service endpoints are environment-driven. The defaults below are
    # local-only fallbacks; business code must always read them from Settings.
    rabbitmq_url: str = "amqp://roxy:change-me@localhost:5673//"
    redis_url: str = "redis://localhost:6380/0"

    minio_internal_endpoint: str = "http://localhost:9100"
    minio_public_endpoint: str = "http://localhost:9100"
    minio_root_user: str = "roxy"
    minio_root_password: str = "change-me"
    minio_bucket_assets: str = "roxy-assets"
    minio_bucket_artifacts: str = "roxy-artifacts"
    minio_bucket_output: str = "roxy-output"

    app_secret_key: str = "dev-only-change-me"
    jwt_secret: str = "dev-only-change-me"

    # LLM (M2 script agent). The key itself only lives in the local .env.
    llm_provider: str = "deepseek"
    deepseek_api_key: str = ""
    deepseek_base_url: str = "https://api.deepseek.com"
    deepseek_model: str = "deepseek-flash"
    llm_timeout_s: float = 120.0

    script_target_chars_per_minute: int = 327
    script_max_repairs: int = 2
    script_roxy_ratio_min: float = 0.10
    script_roxy_ratio_max: float = 0.30
    script_min_lines_for_ratio: int = 20

    storyboard_max_repairs: int = 2

    celery_task_always_eager: bool = False
    outbox_poll_interval_s: float = 5.0
    render_dir: str = "./tmp/renders"
    asset_storage: str = "local"
    asset_root: str = "./data/assets"


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    return Settings()

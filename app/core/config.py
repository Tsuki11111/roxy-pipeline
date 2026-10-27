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


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    return Settings()

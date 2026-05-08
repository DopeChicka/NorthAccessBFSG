from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    app_name: str = "NorthAccessBFSG API"
    environment: str = "development"
    database_url: str = (
        "postgresql+psycopg2://northaccess:northaccess@localhost:5432/northaccessbfsg"
    )
    celery_broker_url: str = "redis://localhost:6379/0"
    celery_result_backend: str = "redis://localhost:6379/1"
    browser_name: str = "chromium"
    browser_headless: bool = True
    browser_navigation_timeout_ms: int = 30_000
    browser_action_timeout_ms: int = 10_000
    browser_viewport_width: int = 1440
    browser_viewport_height: int = 900
    browser_retries: int = 1
    browser_wait_until: str = "networkidle"
    evidence_storage_backend: str = "local"
    evidence_local_root: str = "/app/evidence-data"
    evidence_s3_bucket: str = ""
    evidence_s3_prefix: str = "northaccessbfsg/evidence"
    evidence_s3_endpoint_url: str = ""
    evidence_s3_region: str = "eu-central-1"

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )


@lru_cache
def get_settings() -> Settings:
    return Settings()


settings = get_settings()

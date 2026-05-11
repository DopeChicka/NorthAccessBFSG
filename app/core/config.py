from functools import lru_cache

from pydantic import field_validator
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
    google_places_api_key: str | None = None
    google_places_enabled: bool = False
    google_places_timeout_seconds: int = 10
    google_places_max_results_per_query: int = 5
    website_probe_live_enabled: bool = False
    website_probe_timeout_seconds: int = 10
    website_probe_user_agent: str = "NorthAccessBFSGBot/0.1"
    website_probe_max_body_bytes: int = 200_000
    public_quick_check_timeout_seconds: int = 10
    public_quick_check_user_agent: str = "NorthAccessBFSGQuickCheck/0.1"
    public_quick_check_max_body_bytes: int = 200_000
    quick_check_rate_limit_per_minute: int = 10
    frontend_origins: list[str] = [
        "http://localhost:3000",
        "http://127.0.0.1:3000",
    ]
    bfsg_microenterprise_employee_threshold: int = 10
    bfsg_microenterprise_revenue_threshold_eur: int = 2_000_000
    bfsg_microenterprise_balance_threshold_eur: int = 2_000_000

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    @field_validator("frontend_origins", mode="before")
    @classmethod
    def parse_frontend_origins(cls, value: object) -> object:
        if isinstance(value, str):
            return [item.strip() for item in value.split(",") if item.strip()]
        return value


@lru_cache
def get_settings() -> Settings:
    return Settings()


settings = get_settings()

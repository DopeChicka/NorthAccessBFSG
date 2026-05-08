from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    app_name: str = "NorthAccessBFSG API"
    environment: str = "development"
    database_url: str = (
        "postgresql+psycopg2://northaccess:northaccess@localhost:5432/northaccessbfsg"
    )

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )


@lru_cache
def get_settings() -> Settings:
    return Settings()


settings = get_settings()

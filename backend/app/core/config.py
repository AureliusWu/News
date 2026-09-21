from urllib.parse import quote

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    app_env: str = "development"
    app_name: str = "Global News"
    app_version: str = "0.2.0"
    app_base_path: str = ""
    postgres_db: str = "global_news"
    postgres_user: str = "global_news"
    postgres_password: str = ""
    postgres_host: str = "postgres"
    postgres_port: int = 5432
    database_url: str | None = None
    database_url_docker: str = ""
    database_url_local: str = ""
    database_mode: str = "local"
    cors_allowed_origins: str = "http://localhost:8080,http://127.0.0.1:8080,http://localhost:5173,http://127.0.0.1:5173"
    miniflux_url: str = "http://miniflux:8080"
    miniflux_admin_username: str = "admin"
    miniflux_admin_password: str = ""
    rsshub_url: str = "http://rsshub:1200"
    source_registry_path: str = "config/sources.yaml"
    news_sync_interval_seconds: int = Field(60, ge=30)
    news_initial_lookback_days: int = Field(5, ge=1, le=30)
    news_initial_full_refresh: bool = False
    news_page_size: int = Field(100, ge=1, le=1000)
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    @property
    def db_dsn(self) -> str:
        if self.database_url:
            return self.database_url
        configured = self.database_url_docker if self.database_mode == "docker" else self.database_url_local
        if configured:
            return configured
        host = self.postgres_host if self.database_mode == "docker" else "127.0.0.1"
        return f"postgresql+asyncpg://{quote(self.postgres_user, safe='')}:{quote(self.postgres_password, safe='')}@{host}:{self.postgres_port}/{self.postgres_db}"

    @property
    def cors_allowed_origins_list(self) -> list[str]:
        return [s.strip() for s in self.cors_allowed_origins.split(",") if s.strip() and s.strip() != "*"]


settings = Settings()
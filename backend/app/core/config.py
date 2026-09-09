from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    app_env: str = "development"
    app_name: str = "Global News"
    app_version: str = "0.1.2"

    postgres_db: str = "global_news"
    postgres_user: str = "global_news"
    postgres_password: str = "change_me"
    postgres_host: str = "postgres"
    postgres_port: int = 5432

    database_url: str | None = None
    database_url_docker: str = "postgresql+asyncpg://global_news:change_me@postgres:5432/global_news"
    database_url_local: str = "postgresql+asyncpg://global_news:change_me@127.0.0.1:5432/global_news"
    database_mode: str = "local"
    cors_allowed_origins: str = (
        "http://localhost:4173,http://127.0.0.1:4173,"
        "http://localhost:8080,http://127.0.0.1:8080,"
        "http://localhost:3000,http://127.0.0.1:3000"
    )

    backend_host: str = "0.0.0.0"
    backend_port: int = 8000

    vite_api_base_url: str = "http://localhost:8000"

    model_config = SettingsConfigDict(
        env_prefix="",
        env_file=".env",
        env_file_encoding="utf-8",
    )

    @property
    def db_dsn(self) -> str:
        if self.database_url:
            return self.database_url
        if self.database_mode == "docker":
            return self.database_url_docker

        if self.database_url_local:
            return self.database_url_local

        return (
            f"postgresql+asyncpg://{self.postgres_user}:{self.postgres_password}"
            f"@{self.postgres_host}:{self.postgres_port}/{self.postgres_db}"
        )

    @property
    def cors_allowed_origins_list(self) -> list[str]:
        origins = [origin.strip() for origin in self.cors_allowed_origins.split(",") if origin.strip()]
        if not origins and self.app_env.lower() == "production":
            return []

        return origins


settings = Settings()

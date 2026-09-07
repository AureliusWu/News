from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    app_env: str = "development"
    app_name: str = "Global News"
    app_version: str = "0.1.1"

    postgres_db: str = "global_news"
    postgres_user: str = "global_news"
    postgres_password: str = "change_me"
    postgres_host: str = "postgres"
    postgres_port: int = 5432

    database_url: str | None = None

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

        return (
            f"postgresql+asyncpg://{self.postgres_user}:{self.postgres_password}"
            f"@{self.postgres_host}:{self.postgres_port}/{self.postgres_db}"
        )


settings = Settings()

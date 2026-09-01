from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    APP_ENV: str = "dev"
    SECRET_KEY: str = "dev-secret-change-me"
    BASE_URL: str = "http://localhost:8000"

    DATABASE_URL: str = "sqlite:///./jessica.db"

    SUPABASE_URL: str = ""
    SUPABASE_ANON_KEY: str = ""
    SUPABASE_SERVICE_KEY: str = ""
    SUPABASE_JWT_SECRET: str = ""

    STORAGE_BACKEND: str = "local"  # "local" | "supabase"
    STORAGE_BUCKET: str = "documents"
    LOCAL_STORAGE_DIR: str = "./local_storage"

    ANTHROPIC_API_KEY: str = ""
    CLAUDE_MODEL_REVIEW: str = "claude-sonnet-5"
    CLAUDE_MODEL_ASK: str = "claude-sonnet-5"

    DOCUMENT_RETENTION_DAYS: int = 30
    ANON_RETENTION_HOURS: int = 24

    SENTRY_DSN: str = ""

    MAX_UPLOAD_MB: int = 25

    @property
    def is_sqlite(self) -> bool:
        return self.DATABASE_URL.startswith("sqlite")


@lru_cache
def get_settings() -> Settings:
    return Settings()


settings = get_settings()

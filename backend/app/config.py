import os
from pathlib import Path
from pydantic_settings import BaseSettings, SettingsConfigDict

_BASE_DIR = Path(__file__).resolve().parent.parent  # Points to backend/
_ROOT_DIR = _BASE_DIR.parent  # Points to repository root


class Settings(BaseSettings):
    # Database Connection Strings
    LOCAL_DATABASE_URL: str = ""
    SUPABASE_DATABASE_URL: str = ""
    DATABASE_URL: str = "sqlite:///./expense_tracker.db"

    # Authentication & Security
    JWT_SECRET: str = "change-me-to-a-secure-random-secret-key-at-least-32-chars"
    JWT_ACCESS_MINUTES: int = 15
    JWT_REFRESH_DAYS: int = 7
    FRONTEND_ORIGIN: str = "http://localhost:5173"
    CRON_SECRET: str = "change-me-to-a-secure-random-cron-secret-token"
    RATE_LIMIT_DEFAULT: str = "100/minute"
    RATE_LIMIT_AUTH: str = "5/minute"
    ENVIRONMENT: str = "development"

    model_config = SettingsConfigDict(
        env_file=(
            _BASE_DIR / ".env",
            _ROOT_DIR / ".env",
            ".env",
        ),
        env_file_encoding="utf-8",
        extra="ignore",
    )


settings = Settings()

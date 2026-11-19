import os
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    DATABASE_URL: str = "sqlite:///./expense_tracker.db"
    JWT_SECRET: str = "change-me-to-a-secure-random-secret-key-at-least-32-chars"
    JWT_ACCESS_MINUTES: int = 15
    JWT_REFRESH_DAYS: int = 7
    FRONTEND_ORIGIN: str = "http://localhost:5173"
    CRON_SECRET: str = "change-me-to-a-secure-random-cron-secret-token"
    RATE_LIMIT_DEFAULT: str = "100/minute"
    RATE_LIMIT_AUTH: str = "5/minute"
    ENVIRONMENT: str = "development"

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )


settings = Settings()

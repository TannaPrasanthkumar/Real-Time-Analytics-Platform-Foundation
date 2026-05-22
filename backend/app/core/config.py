import json
from typing import Any, List, Union
from pydantic import AnyHttpUrl, Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=True,
        extra="ignore"
    )

    # Core System Configurations
    ENVIRONMENT: str = Field(default="development")
    PROJECT_NAME: str = Field(default="Real-Time Analytics Platform")
    PORT: int = Field(default=8000)
    LOG_LEVEL: str = Field(default="INFO")

    # PostgreSQL Database Configurations
    DATABASE_URL: str

    # Connection pool configuration
    DATABASE_POOL_SIZE: int = Field(default=20)
    DATABASE_MAX_OVERFLOW: int = Field(default=10)

    # Redis Configurations
    REDIS_URL: str

    # Security & JWT Configurations
    JWT_SECRET_KEY: str
    JWT_ALGORITHM: str = Field(default="HS256")
    ACCESS_TOKEN_EXPIRE_MINUTES: int = Field(default=15)
    REFRESH_TOKEN_EXPIRE_DAYS: int = Field(default=7)

    # CORS Configuration
    CORS_ORIGINS: List[str] = Field(default=["http://localhost:3000"])

    @field_validator("CORS_ORIGINS", mode="before")
    @classmethod
    def assemble_cors_origins(cls, v: Union[str, List[str]]) -> List[str]:
        if isinstance(v, str) and not v.startswith("["):
            return [i.strip() for i in v.split(",")]
        elif isinstance(v, str) and v.startswith("["):
            try:
                parsed = json.loads(v)
                if isinstance(parsed, list):
                    return [str(item) for item in parsed]
            except Exception:
                pass
        elif isinstance(v, list):
            return [str(item) for item in v]
        raise ValueError(f"Invalid CORS origins value: {v}")

    # Background Tasks / Celery Configurations
    CELERY_BROKER_URL: str
    CELERY_RESULT_BACKEND: str

    # API Rate Limiting Config
    RATE_LIMIT_PER_MINUTE: int = Field(default=100)


settings = Settings()

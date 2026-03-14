"""
Application settings and configuration (Multi-Tenant).

Loads configuration from environment variables with sensible defaults.
Extended from single-tenant with Supabase, JWT, and multi-tenant support.
"""

import os
from typing import List, Optional
from pydantic_settings import BaseSettings
from pydantic import Field


class Settings(BaseSettings):
    """Application settings loaded from environment variables."""

    # Environment
    ENVIRONMENT: str = Field(default="development", alias="ENVIRONMENT")
    LOG_LEVEL: str = Field(default="INFO", alias="LOG_LEVEL")

    # CORS
    CORS_ORIGINS: str = Field(
        default="*",
        alias="CORS_ORIGINS",
        description="Comma-separated list of allowed origins",
    )

    # Uvicorn workers
    WORKERS: int = Field(default=2, alias="WORKERS")

    # ==========================================
    # Supabase (config tables: tenants, agents, panels, etc.)
    # ==========================================
    SUPABASE_URL: str = Field(default="", alias="SUPABASE_URL")
    SUPABASE_KEY: str = Field(default="", alias="SUPABASE_KEY")
    SUPABASE_DB_URL: str = Field(
        default="",
        alias="SUPABASE_DB_URL",
        description="Direct PostgreSQL connection string for Supabase RDG (asyncpg)",
    )

    # ==========================================
    # PostgreSQL (dedicated: LangGraph checkpoints, memory)
    # ==========================================
    POSTGRES_HOST: str = Field(default="localhost", alias="POSTGRES_HOST")
    POSTGRES_PORT: int = Field(default=5432, alias="POSTGRES_PORT")
    POSTGRES_DB: str = Field(default="postgres", alias="POSTGRES_DB")
    POSTGRES_USER: str = Field(default="postgres", alias="POSTGRES_USER")
    POSTGRES_PASSWORD: str = Field(default="", alias="POSTGRES_PASSWORD")

    # Connection pool
    DB_POOL_SIZE: int = Field(default=10, alias="DB_POOL_SIZE")
    DB_MAX_OVERFLOW: int = Field(default=20, alias="DB_MAX_OVERFLOW")
    DB_POOL_TIMEOUT: int = Field(default=30, alias="DB_POOL_TIMEOUT")
    DB_POOL_RECYCLE: int = Field(default=3600, alias="DB_POOL_RECYCLE")

    # ==========================================
    # JWT Authentication
    # ==========================================
    JWT_SECRET: str = Field(default="change-me-in-production", alias="JWT_SECRET")
    JWT_ALGORITHM: str = Field(default="HS256", alias="JWT_ALGORITHM")
    JWT_EXPIRE_MINUTES: int = Field(default=30, alias="JWT_EXPIRE_MINUTES")
    JWT_REFRESH_EXPIRE_DAYS: int = Field(default=7, alias="JWT_REFRESH_EXPIRE_DAYS")

    # ==========================================
    # xAI Grok API (default LLM)
    # ==========================================
    GROK_API_KEY: str = Field(default="", alias="GROK_API_KEY")
    GROK_MODEL: str = Field(default="grok-4-1-fast-non-reasoning", alias="GROK_MODEL")
    GROK_BASE_URL: str = Field(default="https://api.x.ai/v1", alias="GROK_BASE_URL")
    GROK_TEMPERATURE: float = Field(default=0.1, alias="GROK_TEMPERATURE")
    GROK_TOP_P: float = Field(default=0.3, alias="GROK_TOP_P")

    # ==========================================
    # Helena CRM API (default, can be overridden per tenant)
    # ==========================================
    HELENA_API_TOKEN: str = Field(default="", alias="HELENA_API_TOKEN")
    HELENA_BASE_URL: str = Field(default="https://api.helena.run", alias="HELENA_BASE_URL")
    HELENA_BOT_NUMBER: str = Field(default="", alias="HELENA_BOT_NUMBER")

    # ==========================================
    # Timezone
    # ==========================================
    TIMEZONE: str = Field(default="America/Sao_Paulo", alias="TZ")

    @property
    def cors_origins_list(self) -> List[str]:
        """Parse CORS_ORIGINS into a list."""
        return [origin.strip() for origin in self.CORS_ORIGINS.split(",")]

    @property
    def postgres_uri(self) -> str:
        """Build PostgreSQL connection URI."""
        return (
            f"postgresql://{self.POSTGRES_USER}:{self.POSTGRES_PASSWORD}"
            f"@{self.POSTGRES_HOST}:{self.POSTGRES_PORT}/{self.POSTGRES_DB}"
        )

    @property
    def postgres_async_uri(self) -> str:
        """Build async PostgreSQL connection URI (asyncpg)."""
        return (
            f"postgresql+asyncpg://{self.POSTGRES_USER}:{self.POSTGRES_PASSWORD}"
            f"@{self.POSTGRES_HOST}:{self.POSTGRES_PORT}/{self.POSTGRES_DB}"
        )

    @property
    def is_production(self) -> bool:
        """Check if running in production."""
        return self.ENVIRONMENT == "production"

    @property
    def is_development(self) -> bool:
        """Check if running in development."""
        return self.ENVIRONMENT == "development"

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"
        extra = "ignore"


# Singleton
settings = Settings()

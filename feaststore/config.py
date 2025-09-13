"""Runtime configuration, loaded from environment variables (12-factor style).

All settings are prefixed with ``FEASTSTORE_`` in the environment, e.g.
``FEASTSTORE_ONLINE_REDIS_URL=redis://cache:6379/0``.
"""

from __future__ import annotations

from functools import lru_cache

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_prefix="FEASTSTORE_",
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # Offline store (Postgres): historical features + point-in-time joins.
    offline_dsn: str = Field(
        default="postgresql+psycopg://feaststore:feaststore@localhost:5432/feaststore",
        description="SQLAlchemy DSN for the Postgres offline + registry store.",
    )

    # Online store (Redis): low-latency serving.
    online_redis_url: str = Field(default="redis://localhost:6379/0")
    online_key_prefix: str = Field(default="fs")

    # Serving
    project: str = Field(default="default", description="Namespace for keys and registry rows.")
    max_online_batch: int = Field(default=1000, ge=1, le=10_000)

    # Ops
    log_level: str = Field(default="INFO")
    enable_metrics: bool = Field(default=True)

    @property
    def redis_namespace(self) -> str:
        return f"{self.online_key_prefix}:{self.project}"


@lru_cache
def get_settings() -> Settings:
    """Cached accessor so we parse the environment exactly once per process."""
    return Settings()

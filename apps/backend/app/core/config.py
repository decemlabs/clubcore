"""Application settings via pydantic-settings (D-15)."""

from functools import lru_cache
from typing import Literal

from pydantic import PostgresDsn, RedisDsn, SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Read configuration from environment + .env file. No prefix; raw env var names."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    database_url: PostgresDsn
    redis_url: RedisDsn
    environment: Literal["dev", "staging", "prod"] = "dev"
    debug: bool = False
    secret_key: SecretStr


@lru_cache
def get_settings() -> Settings:
    """Return a cached Settings instance. Cache survives the process lifetime."""
    return Settings()

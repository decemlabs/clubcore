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

    # Phase 4 additions (D-05, D-25): JWT TTLs + cookie Secure flag, env-driven
    access_token_ttl_seconds: int = 900           # 15 min — access JWT lifetime
    refresh_token_ttl_seconds: int = 2_592_000    # 30 days — refresh token lifetime
    jwt_clock_leeway_seconds: int = 30            # PyJWT decode leeway for cross-container drift
    cookie_secure: bool = False  # prod startup must ASSERT True (Phase 5 adds assertion)


@lru_cache
def get_settings() -> Settings:
    """Return a cached Settings instance. Cache survives the process lifetime."""
    return Settings()

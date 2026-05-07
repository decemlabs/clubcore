"""Application settings via pydantic-settings (D-15)."""

from datetime import time
from functools import lru_cache
from typing import Literal

from pydantic import PostgresDsn, RedisDsn, SecretStr, model_validator
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

    # Phase 5 addition (D-13, AUTH-06): refresh-rotation reuse-window in seconds.
    # Two parallel /auth/refresh calls within this window return the same new pair
    # (idempotent same-pair return) — the lower bound on cache TTL at auth:rotate:{hash}.
    refresh_reuse_window_seconds: int = 5

    # Phase 7 additions (D-10, D-03): Telegram OTP channel.
    # Placeholder defaults so fresh-clone dev boot of `web` + admin-web does NOT
    # require setting bot credentials first. The bot worker process must check
    # for this sentinel and refuse to start (see app/workers/telegram_bot.py).
    # Real deployments override via .env / docker-compose env.
    telegram_bot_token: SecretStr = SecretStr("placeholder-telegram-bot-token-not-real")
    telegram_bot_username: str = "placeholder_bot"  # without leading `@`
    otp_deep_link_ttl_seconds: int = 600  # 10 min — AUTH-TG-01
    otp_code_ttl_seconds: int = 300       # 5 min  — AUTH-TG-02
    otp_max_attempts: int = 5             # AUTH-TG-02

    # Phase 19 additions (VIS-05): gym hours window in Europe/Moscow.
    # Pydantic v2 parses "07:00" env strings → time(7, 0) natively.
    gym_hours_start: time = time(7, 0)
    gym_hours_end: time = time(23, 0)

    @model_validator(mode="after")
    def _gym_hours_range_invariant(self) -> "Settings":
        # D-11: no midnight-spanning gym hours in v1.2.
        if self.gym_hours_end <= self.gym_hours_start:
            raise ValueError(
                "gym_hours_end must be strictly greater than gym_hours_start "
                "(midnight-spanning ranges deferred to v1.3+)."
            )
        return self


@lru_cache
def get_settings() -> Settings:
    """Return a cached Settings instance. Cache survives the process lifetime."""
    return Settings()

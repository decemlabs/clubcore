"""Application settings via pydantic-settings (D-15)."""

from datetime import time
from functools import lru_cache
from typing import Literal, Self

from pydantic import BaseModel, EmailStr, PostgresDsn, RedisDsn, SecretStr, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class EmailProviderSettings(BaseModel):
    """Email transport settings (D-42-28).

    Defaults are sandbox-safe so fresh-clone dev boot does NOT require setting
    email credentials first (mirrors v1.1 Telegram-block discipline in this
    same file). The @model_validator below fails fast at construction when
    provider != 'sandbox' and sandbox_mode=False but credentials/domain/
    webhook secret are missing.
    """

    provider: Literal["yandex_postbox", "sandbox"] = "sandbox"
    aws_access_key_id: SecretStr | None = None
    aws_secret_access_key: SecretStr | None = None
    endpoint_url: str = "https://postbox.cloud.yandex.net"
    from_address: str = "noreply@mail.clubcore.ru"
    from_domain: str = ""
    webhook_secret: SecretStr = SecretStr("")
    sandbox_mode: bool = False

    @model_validator(mode="after")
    def _validate_production_required(self) -> Self:
        if self.provider != "sandbox" and not self.sandbox_mode:
            if not self.from_domain:
                raise ValueError(
                    "EmailProviderSettings.from_domain required for non-sandbox provider"
                )
            if not self.webhook_secret.get_secret_value():
                raise ValueError(
                    "EmailProviderSettings.webhook_secret required for non-sandbox provider"
                )
            if not self.aws_access_key_id or not self.aws_secret_access_key:
                raise ValueError(
                    "EmailProviderSettings AWS credentials required for non-sandbox provider"
                )
        return self


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
    access_token_ttl_seconds: int = 900  # 15 min — access JWT lifetime
    refresh_token_ttl_seconds: int = 2_592_000  # 30 days — refresh token lifetime
    qr_token_ttl_seconds: int = 60  # ≈60s — D-70-07 QR self-check-in token lifetime
    jwt_clock_leeway_seconds: int = 30  # PyJWT decode leeway for cross-container drift
    cookie_secure: bool = False  # prod startup must ASSERT True (Phase 5 adds assertion)

    # Phase 5 addition (D-13, AUTH-06): refresh-rotation reuse-window in seconds.
    # Two parallel /auth/refresh calls within this window return the same new pair
    # (idempotent same-pair return) — the lower bound on cache TTL at auth:rotate:{hash}.
    refresh_reuse_window_seconds: int = 5

    # Phase 7 additions (D-10, D-03): Telegram OTP channel.
    # Placeholder defaults so fresh-clone dev boot of `web` + admin-app does NOT
    # require setting bot credentials first. The bot worker process must check
    # for this sentinel and refuse to start (see app/workers/telegram_bot.py).
    # Real deployments override via .env / docker-compose env.
    telegram_bot_token: SecretStr = SecretStr("placeholder-telegram-bot-token-not-real")
    telegram_bot_username: str = "placeholder_bot"  # without leading `@`
    otp_deep_link_ttl_seconds: int = 600  # 10 min — AUTH-TG-01
    otp_code_ttl_seconds: int = 300  # 5 min  — AUTH-TG-02
    otp_max_attempts: int = 5  # AUTH-TG-02

    # Phase 71 WR-06: explicit second guard for the dev-pinned client OTP.
    # The "111111" pin (and raw-code logging) is a local-UAT convenience that is
    # a hard auth bypass if ENVIRONMENT is ever misset to "dev" in a deployed env.
    # It now requires BOTH environment == "dev" AND this opt-in flag (default
    # False). A model_validator below fails fast if it is ever True outside dev.
    dev_otp_pin_enabled: bool = False

    # Phase 52 additions (D-52-09, NOT-04): Owner operator-alert recipients.
    # Consumed by the dispatch_payment_notification task for the payment_canceled
    # and fiscal_failed notification kinds — routes operator-actionable content
    # (payment_id, failure reasons) to the owner only, NEVER to client channels.
    # When unset (None), the dispatch task logs ERROR only and never raises or
    # blocks the financial commit (best-effort, D-52-09 / D-52-07).
    # Env-var documentation lives in the Phase 53 deployment runbook (VER-01).
    owner_alert_telegram_chat_id: int | None = None
    owner_alert_email: str | None = None

    # Phase 93 BRDG-01 — staff Telegram chat for client message forwarding.
    # When absent (None), the Telegram bridge (forward_to_staff ARQ task +
    # staff_reply_handler) is disabled with a structured log line.
    # Mirrors the owner_alert_telegram_chat_id sentinel pattern (D-52-09).
    # Env var: STAFF_TELEGRAM_CHAT_ID (int). Set to the staff DM chat_id or
    # group chat_id. Leave unset in dev to keep bridge disabled.
    staff_telegram_chat_id: int | None = None

    # Phase 42 addition (D-42-28): Email transport settings nested block.
    # Defaults are sandbox-safe so fresh-clone dev boot does NOT require setting
    # email credentials first (mirrors Telegram block discipline above).
    email: EmailProviderSettings = EmailProviderSettings()

    # Phase 19 additions (VIS-05): gym hours window in Europe/Moscow.
    # Pydantic v2 parses "07:00" env strings → time(7, 0) natively.
    gym_hours_start: time = time(7, 0)
    gym_hours_end: time = time(23, 0)

    # Phase 59 addition (D-59-04 / REC-02): rolling materialization horizon for
    # the generate_recurring_slots ARQ cron. Controls how far ahead the cron
    # materialises concrete trainer_availability_slots rows from recurring templates.
    # Default 56 days (~8 weeks). Override via env var RECURRING_SLOT_HORIZON_DAYS.
    # Read via get_settings().recurring_slot_horizon_days inside the cron service helper.
    recurring_slot_horizon_days: int = 56

    # Phase 43 addition (D-43-14): frontend base URL for owner-managed
    # invitation links (?include_invite_link=true escape hatch + email body).
    # Default points at the admin-app dev server (staff frontend, port 5173);
    # production overrides via .env.
    # The URL is NEVER stored in audit payloads — only the link_copied bool
    # flag is captured (D-43-14 / Pitfall 4 anti-oracle).
    frontend_base_url: str = "http://localhost:5173"

    # Phase 96 addition (REFER-01): client-pwa base URL for server-authoritative
    # deep-link shareUrl construction. The referral deep-link path /i/<code> is
    # consumed by the PWA (port 5174), not the admin-web (port 5173). Override
    # via PWA_BASE_URL env var in production. Never stored in audit payloads.
    pwa_base_url: str = "http://localhost:5174"

    # Phase 90 RT-02 — CSWSH guard allowlist for the WebSocket endpoint.
    # verify_ws_origin (app/core/dependencies.py) compares the WS upgrade
    # Origin header against this list. Defaults cover the admin-app dev server
    # (5173, staff frontend) and the client PWA dev port (5174 — vite.config
    # pins 5174 to avoid the admin-app 5173 clash) + testserver. Production
    # overrides via WS_ALLOWED_ORIGINS env var (comma-separated or JSON list).
    # Empty list means same-origin only (no cross-origin WS accepted).
    ws_allowed_origins: list[str] = [
        "http://localhost:5173",
        "http://localhost:5174",
        "http://localhost:3000",
        "http://testserver",
    ]

    # Phase 62 D-62-03 — env-driven email FROM override.
    # CLUBCORE_EMAIL_FROM overrides EmailProviderSettings.from_address default.
    # Typed as EmailStr (REVIEW-62.1 WR-02): pydantic rejects malformed addresses
    # (missing '@', empty/whitespace) at construction, restoring the fail-fast
    # posture the deleted multi-env fallback chain implicitly provided (WR-01).
    clubcore_email_from: EmailStr | None = None  # canonical env: CLUBCORE_EMAIL_FROM

    @model_validator(mode="after")
    def _gym_hours_range_invariant(self) -> Self:
        # D-11: no midnight-spanning gym hours in v1.2.
        if self.gym_hours_end <= self.gym_hours_start:
            raise ValueError(
                "gym_hours_end must be strictly greater than gym_hours_start "
                "(midnight-spanning ranges deferred to v1.3+)."
            )
        return self

    @model_validator(mode="after")
    def _dev_otp_pin_guard(self) -> Self:
        # Phase 71 WR-06: the dev-pinned client OTP must never be enabled outside
        # a dev environment. Fail fast at construction so a misset ENVIRONMENT
        # plus a leftover DEV_OTP_PIN_ENABLED=true can never silently turn into a
        # production auth bypass.
        if self.dev_otp_pin_enabled and self.environment != "dev":
            raise ValueError(
                "dev_otp_pin_enabled must be False unless environment == 'dev' "
                f"(got environment={self.environment!r}) — refusing to start."
            )
        return self

    @model_validator(mode="after")
    def _resolve_email_from(self) -> Self:
        # Phase 62 D-62-03 — canonical env override of EmailProviderSettings.from_address.
        resolved: str | None = self.clubcore_email_from
        if resolved is not None:
            # EmailProviderSettings is a pydantic BaseModel (not frozen by default
            # in this codebase, but use object.__setattr__ for forward-compat with
            # a future ConfigDict(frozen=True) tightening per 62-PATTERNS §G-4).
            object.__setattr__(self.email, "from_address", resolved)
        return self


@lru_cache
def get_settings() -> Settings:
    """Return a cached Settings instance. Cache survives the process lifetime."""
    return Settings()

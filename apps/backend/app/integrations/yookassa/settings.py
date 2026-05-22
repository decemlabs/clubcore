"""ЮKassa integration settings — Phase 47 INFRA-36 (D-47-07/08/09).

Standalone ``BaseSettings`` — deliberate deviation from ``EmailProviderSettings``
locality (which is nested under ``app.core.config.Settings``) per D-47-08,
isolating ЮKassa credential ownership next to the integration code. Composition
root instantiates ``YooKassaSettings`` once and passes the instance to the
``YooKassaClientProvider`` slot (wired empty in Phase 47; concrete in Phase 48).

Per D-47-07: ``sandbox: bool`` toggles the API base URL inside ``YooKassaClient``
and bypasses the IP allowlist in ``verify_yookassa_ip``. Per-environment ``.env``
files swap the credential values; no per-environment Settings subclasses.

Per D-47-09: ``.env.example`` documents every field with placeholder-only values.
``secret_key`` is typed as ``SecretStr`` so structlog ``redact_secrets`` formatter
(already configured for ``EmailProviderSettings.smtp_password`` lineage) suppresses
the value in logs (T-47-02-01 mitigation).

No ``@model_validator`` here: the sandbox-vs-credential-required guard lives in
Phase 48's ``webhook_verifier.py`` and ``client.py``. Phase 47 ships the bare
type only.
"""

from __future__ import annotations

from functools import lru_cache

from pydantic import HttpUrl, SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict


class YooKassaSettings(BaseSettings):
    """ЮKassa credential + endpoint settings (Phase 47 INFRA-36, D-47-07..09).

    Standalone ``BaseSettings`` so credential ownership is encapsulated next
    to the integration code and adapter unit tests can construct it directly.
    ``env_prefix='YOOKASSA_'`` means env vars are consumed verbatim
    (e.g., ``YOOKASSA_SHOP_ID``, ``YOOKASSA_SECRET_KEY``).
    """

    model_config = SettingsConfigDict(
        env_prefix="YOOKASSA_",
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    shop_id: int
    secret_key: SecretStr
    return_url: HttpUrl
    tax_system_code: int
    default_vat_code: int
    sandbox: bool = False


@lru_cache(maxsize=1)
def get_yookassa_settings() -> YooKassaSettings:
    """Process-scoped YooKassaSettings factory (Phase 49 BLOCKER #5 / D-49-14).

    pydantic-settings reads ``.env`` on instantiation; ``@lru_cache`` ensures
    the FastAPI ``Depends(get_yookassa_settings)`` callsite (Plan 49-04 router)
    receives the same instance on every request. Mirrors the module-level
    ``_settings: Final[YooKassaSettings] = YooKassaSettings()`` pattern used
    by ``app/integrations/yookassa/webhook_verifier.py:60``.

    NOT a substitute for the composition-root instantiation in
    ``app.main.create_app`` (lifespan-managed for shared http client). Use
    this factory ONLY where a stateless ``Depends(...)`` target is needed.
    """
    return YooKassaSettings()

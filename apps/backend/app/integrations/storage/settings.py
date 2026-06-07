"""S3-compatible object storage settings (Phase 92 ATT-01, T-92-02).

Standalone ``BaseSettings`` — mirrors the YooKassaSettings discipline (D-47-08):
credential ownership is encapsulated next to the integration code; the
composition root instantiates ``StorageSettings`` once and passes the instance
to the storage adapter.

``env_prefix='S3_'`` means env vars are consumed verbatim
(e.g. ``S3_ENDPOINT_URL``, ``S3_BUCKET``, ``S3_ACCESS_KEY_ID``).

``secret_access_key`` is typed as ``SecretStr`` so structlog ``redact_secrets``
formatter suppresses the value in logs (T-92-02 mitigation).

Dev-safe defaults allow a fresh clone to boot against the docker S3 service
(chrislusf/seaweedfs) that docker-compose exposes on http://localhost:8333.
The local S3 service uses dev-default credentials declared in docker-compose.yml.
Override all four S3_* vars in a real .env for staging/prod.

Layer invariant: this module lives at ``integrations`` layer — MUST NOT import
from ``app.modules.*``.
"""

from __future__ import annotations

from functools import lru_cache

from pydantic import SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict


class StorageSettings(BaseSettings):
    """S3-compatible object storage credential + endpoint settings (Phase 92 ATT-01).

    ``env_prefix='S3_'`` — env vars: S3_ENDPOINT_URL, S3_BUCKET,
    S3_ACCESS_KEY_ID, S3_SECRET_ACCESS_KEY, S3_REGION.

    Dev defaults point at the local docker S3 service (SeaweedFS)
    with the dev-default credentials from docker-compose.yml.
    Override all vars in .env for staging/prod.
    """

    model_config = SettingsConfigDict(
        env_prefix="S3_",
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    endpoint_url: str = "http://localhost:8333"
    bucket: str = "clubcore-local"
    access_key_id: SecretStr = SecretStr("dev-access-key")
    secret_access_key: SecretStr = SecretStr("dev-secret-key")
    region: str = "ru-central1"


@lru_cache(maxsize=1)
def get_storage_settings() -> StorageSettings:
    """Process-scoped StorageSettings factory.

    ``@lru_cache`` ensures the same instance is returned for every
    ``Depends(get_storage_settings)`` call, mirroring the
    ``get_yookassa_settings`` pattern (D-47-08).
    """
    return StorageSettings()

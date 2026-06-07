"""S3-compatible object storage integration package (Phase 92 ATT-01..03).

Public surface for downstream plans:

    from app.integrations.storage import Storage, StorageSettings, guess_allowed_mime
    from app.integrations.storage.factory import build_storage
    from app.integrations.storage import get_storage  # FastAPI dependency

``Storage``       — async protocol; Plan 02 upload service + Plan 03 serve proxy depend on it.
``StorageSettings`` — env-driven BaseSettings (env_prefix='S3_'); factory builds the adapter.
``guess_allowed_mime`` — magic-byte allowlist guard; Plan 02 upload validator calls it.
``ALLOWED_MIMES`` — frozenset of allowed MIME types; exposed for schema documentation.
``MAGIC_BYTE_READ_LEN`` — how many bytes callers must read before calling the guard.
``get_storage``   — FastAPI dependency; resolves the process-scoped adapter from app.state.

Layer invariant: this package MUST NOT import from ``app.modules.*``.
"""

from __future__ import annotations

from fastapi import Request

from app.integrations.storage.mime import (
    ALLOWED_MIMES,
    MAGIC_BYTE_READ_LEN,
    guess_allowed_mime,
)
from app.integrations.storage.settings import StorageSettings, get_storage_settings
from app.integrations.storage.types import Storage


def get_storage(request: Request) -> Storage:
    """Resolve the S3 storage adapter from app.state (Phase 92 ATT-01).

    Per-request dependency — reads the single process-scoped ``S3Storage``
    instance populated by ``combined_lifespan`` at startup.  No construction
    per request (mirrors ``get_redis`` reading ``app.state.redis`` lazily).

    Usage in router handlers:
        storage: Annotated[Storage, Depends(get_storage)]
    """
    adapter: Storage = request.app.state.storage
    return adapter


__all__ = [
    "ALLOWED_MIMES",
    "MAGIC_BYTE_READ_LEN",
    "Storage",
    "StorageSettings",
    "get_storage",
    "get_storage_settings",
    "guess_allowed_mime",
]

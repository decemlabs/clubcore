"""S3-compatible object storage integration package (Phase 92 ATT-01..03).

Public surface for downstream plans:

    from app.integrations.storage import Storage, StorageSettings, guess_allowed_mime
    from app.integrations.storage.factory import build_storage

``Storage``       — async protocol; Plan 02 upload service + Plan 03 serve proxy depend on it.
``StorageSettings`` — env-driven BaseSettings (env_prefix='S3_'); factory builds the adapter.
``guess_allowed_mime`` — magic-byte allowlist guard; Plan 02 upload validator calls it.
``ALLOWED_MIMES`` — frozenset of allowed MIME types; exposed for schema documentation.
``MAGIC_BYTE_READ_LEN`` — how many bytes callers must read before calling the guard.

Layer invariant: this package MUST NOT import from ``app.modules.*``.
"""

from __future__ import annotations

from app.integrations.storage.mime import (
    ALLOWED_MIMES,
    MAGIC_BYTE_READ_LEN,
    guess_allowed_mime,
)
from app.integrations.storage.settings import StorageSettings, get_storage_settings
from app.integrations.storage.types import Storage

__all__ = [
    "ALLOWED_MIMES",
    "MAGIC_BYTE_READ_LEN",
    "Storage",
    "StorageSettings",
    "get_storage_settings",
    "guess_allowed_mime",
]

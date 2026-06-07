"""Storage adapter factory (Phase 92 ATT-01).

Single entrypoint ``build_storage`` returns a configured ``S3Storage`` adapter.
Called once at composition root (app lifespan in Plan 02).

Construction is sync — no boot probe is performed here.  Bucket bootstrap
is deferred to lifespan (``await storage.ensure_bucket()`` in Plan 02) so
the factory remains a simple, side-effect-free constructor.

Layer invariant: this module lives at ``integrations`` layer — MUST NOT import
from ``app.modules.*``.
"""

from __future__ import annotations

import aioboto3

from app.integrations.storage.s3 import S3Storage
from app.integrations.storage.settings import StorageSettings


def build_storage(settings: StorageSettings) -> S3Storage:
    """Construct a fresh ``S3Storage`` adapter from ``settings``.

    Builds an ``aioboto3.Session`` from the credential pair in ``settings``
    (access_key_id / secret_access_key via ``get_secret_value()``), then
    constructs and returns the adapter.  No I/O occurs.

    Returns a FRESH adapter per call — no module-level caching.  The
    composition root (app lifespan) is responsible for holding the single
    process-scoped instance.
    """
    session = aioboto3.Session(
        aws_access_key_id=settings.access_key_id.get_secret_value(),
        aws_secret_access_key=settings.secret_access_key.get_secret_value(),
    )
    return S3Storage(
        session=session,
        endpoint_url=settings.endpoint_url,
        bucket=settings.bucket,
        region=settings.region,
    )

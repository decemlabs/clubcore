"""Storage protocol — typed contract for Plans 02/03 (Phase 92 ATT-01).

``Storage`` is a ``typing.Protocol`` that every storage adapter must satisfy.
``S3Storage`` (s3.py) is the only concrete implementation in v2.5; the
protocol allows test doubles without an aioboto3 session.

Three methods:
- ``put(key, data, content_type) -> None``: upload validated bytes.
- ``open_stream(key) -> AsyncIterator[bytes]``: streamed body for the serve proxy.
- ``ensure_bucket() -> None``: idempotent bucket bootstrap for local dev.

No aioboto3 / botocore types cross the public boundary — bytes/str/
AsyncIterator only.

Layer invariant: this module lives at ``integrations`` layer — MUST NOT import
from ``app.modules.*``.
"""

from __future__ import annotations

from collections.abc import AsyncIterator
from typing import Protocol, runtime_checkable


@runtime_checkable
class Storage(Protocol):
    """Async object-storage adapter protocol (Phase 92 ATT-01).

    All three methods are async.  Implementations must be usable as
    drop-in replacements in the upload service (Plan 02) and the serve
    proxy (Plan 03).

    No provider-specific types (boto3 / aioboto3 / botocore) may appear
    in any method signature — bytes, str, and AsyncIterator are the only
    allowed types at the public boundary.
    """

    async def put(self, key: str, data: bytes, content_type: str) -> None:
        """Upload ``data`` under ``key`` with the given ``content_type``.

        The key is a server-generated UUID-based path (P8 — no user-supplied
        filename crosses the boundary).
        """
        ...

    def open_stream(self, key: str) -> AsyncIterator[bytes]:
        """Return an async iterator that yields chunks of the stored object.

        The implementation MUST keep the underlying S3 client context open
        for the full lifetime of the iterator (the serve proxy in Plan 03
        consumes this iterator while streaming the HTTP response).
        """
        ...

    async def ensure_bucket(self) -> None:
        """Idempotently create the configured bucket if it does not exist.

        Called at app startup (Plan 02 lifespan).  Must swallow
        ``BucketAlreadyOwnedByYou`` for idempotency.  No-ops when the
        bucket already exists.
        """
        ...

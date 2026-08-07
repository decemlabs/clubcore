"""S3-compatible object storage adapter (Phase 92 ATT-01, T-92-02).

``S3Storage`` implements the ``Storage`` protocol using aioboto3.  Session
construction mirrors the ``EmailClient`` discipline (D-42-01/D-42-02):
- The ``aioboto3.Session`` is a factory — a fresh ``s3`` client is opened per
  operation via ``async with self._session.client("s3", ...)``.
- No aioboto3 / botocore types cross the public method boundary — only
  ``bytes``, ``str``, and ``AsyncIterator[bytes]`` appear in signatures.

``open_stream`` is an async generator that keeps the s3 client context open
for the full lifetime of the iterator, so the serve proxy (Plan 03) can stream
the response body chunk-by-chunk without pre-loading the whole file into memory.

``ensure_bucket`` is idempotent: it calls ``head_bucket`` first; on a 404 /
``NoSuchBucket`` / ``ClientError`` 404 it creates the bucket.  On
``BucketAlreadyOwnedByYou`` it succeeds silently.

Layer invariant: this module lives at ``integrations`` layer — MUST NOT import
from ``app.modules.*``.
"""

from __future__ import annotations

from collections.abc import AsyncIterator
from typing import Any

import structlog
from botocore.exceptions import ClientError

_log = structlog.get_logger("integrations.storage.s3")

# Chunk size for streaming body reads (8 KiB)
_STREAM_CHUNK_SIZE: int = 8 * 1024


class S3Storage:
    """aioboto3-backed S3-compatible storage adapter (Phase 92 ATT-01).

    Holds an ``aioboto3.Session`` factory + endpoint / bucket / region.
    A fresh ``s3`` client is opened per operation (aioboto3 sessions are
    factories; clients are async-context-managed).

    Constructed by ``build_storage(settings)`` — do not instantiate directly
    in application code outside the factory / composition root.
    """

    def __init__(
        self,
        *,
        session: Any,
        endpoint_url: str,
        bucket: str,
        region: str,
    ) -> None:
        self._session = session
        self._endpoint_url = endpoint_url
        self._bucket = bucket
        self._region = region

    async def put(self, key: str, data: bytes, content_type: str) -> None:
        """Upload ``data`` under ``key`` with the given ``content_type``.

        Opens a fresh ``s3`` client per call (aioboto3 factory discipline).
        ``content_type`` is the validated MIME type from the magic-byte guard
        (mime.py); it is set as ``ContentType`` on the S3 object.
        """
        async with self._session.client(
            "s3",
            endpoint_url=self._endpoint_url,
            region_name=self._region,
        ) as client:
            await client.put_object(
                Bucket=self._bucket,
                Key=key,
                Body=data,
                ContentType=content_type,
            )
        _log.debug("s3_put_ok", key=key, bucket=self._bucket, content_type=content_type)

    async def open_stream(self, key: str) -> AsyncIterator[bytes]:
        """Async generator that yields chunks of the stored object.

        The s3 client context is kept open for the full lifetime of the
        iterator (critical for streaming large files).  The serve proxy in
        Plan 03 consumes this generator inside a ``StreamingResponse``.
        """
        async with self._session.client(
            "s3",
            endpoint_url=self._endpoint_url,
            region_name=self._region,
        ) as client:
            response = await client.get_object(Bucket=self._bucket, Key=key)
            body = response["Body"]
            async for chunk in body.iter_chunks(_STREAM_CHUNK_SIZE):
                yield chunk

    async def ensure_bucket(self) -> None:
        """Idempotently create the configured bucket if it does not exist.

        Called at app startup (Plan 02 lifespan).  Uses ``head_bucket``
        to probe existence; on 404 / ``NoSuchBucket`` creates the bucket.
        Swallows ``BucketAlreadyOwnedByYou`` for race-condition safety.
        """
        async with self._session.client(
            "s3",
            endpoint_url=self._endpoint_url,
            region_name=self._region,
        ) as client:
            try:
                await client.head_bucket(Bucket=self._bucket)
                _log.debug("s3_bucket_exists", bucket=self._bucket)
            except ClientError as exc:
                resp = exc.response if isinstance(exc.response, dict) else {}
                error_code = resp.get("Error", {}).get("Code", "")
                if error_code in ("404", "NoSuchBucket"):
                    try:
                        await client.create_bucket(Bucket=self._bucket)
                        _log.info("s3_bucket_created", bucket=self._bucket)
                    except ClientError as create_exc:
                        create_resp = (
                            create_exc.response if isinstance(create_exc.response, dict) else {}
                        )
                        create_code = create_resp.get("Error", {}).get("Code", "")
                        if create_code == "BucketAlreadyOwnedByYou":
                            _log.debug(
                                "s3_bucket_already_owned",
                                bucket=self._bucket,
                            )
                        else:
                            raise
                else:
                    raise

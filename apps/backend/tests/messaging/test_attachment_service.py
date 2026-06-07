"""Service-layer tests for create_attachment (Phase 92 Plan 02, Task 2 TDD).

Tests use a stub Storage (in-memory) so no real S3 is needed.
Real bytes are used for magic-byte validation to exercise the filetype path.

Coverage:
  - SVG bytes with claimed_content_type='image/png' → UnsupportedMediaTypeError,
    no put() called (T-92-05 LOCKED INVARIANT)
  - 6MB payload → PayloadTooLargeError, no put() called (T-92-06)
  - Valid JPEG bytes → row persisted with client_id ownership, UUID object key,
    validated mime; previewUrl is the relative serve path; attachment_uploaded
    audit emitted
  - AttachmentUploadResponse fields: id UUID, preview_url starts with
    /api/v1/client/messages/attachments/
  - insert_attachment writes a row with correct fields (unit test)
"""

from __future__ import annotations

import asyncio
from collections.abc import AsyncIterator
from unittest.mock import AsyncMock, MagicMock, call, patch
from uuid import UUID, uuid4

import pytest

# ---------------------------------------------------------------------------
# Minimal JPEG and SVG magic bytes for real magic-byte detection tests
# ---------------------------------------------------------------------------

# JPEG magic: 0xFF 0xD8 0xFF
JPEG_MAGIC = b"\xff\xd8\xff\xe0" + b"\x00" * 257

# SVG: starts with XML declaration / "<svg" — will NOT match JPEG/PNG/WebP
SVG_BYTES = b"<svg xmlns='http://www.w3.org/2000/svg'><rect/></svg>" + b"\x00" * 209

# 6 MB of zeros (exceeds 5MB cap)
SIX_MB = b"\x00" * (6 * 1024 * 1024)

# ---------------------------------------------------------------------------
# Stub Storage implementation
# ---------------------------------------------------------------------------


class StubStorage:
    """In-memory Storage stub for unit tests.

    Records put() calls for assertion; open_stream + ensure_bucket are no-ops.
    """

    def __init__(self) -> None:
        self.put_calls: list[dict[str, object]] = []

    async def put(self, key: str, data: bytes, content_type: str) -> None:
        self.put_calls.append({"key": key, "data": data, "content_type": content_type})

    async def open_stream(self, key: str) -> AsyncIterator[bytes]:
        async def _empty() -> AsyncIterator[bytes]:
            return
            yield b""  # type: ignore[misc]  # makes this an async generator

        return _empty()

    async def ensure_bucket(self) -> None:
        pass


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def stub_storage() -> StubStorage:
    return StubStorage()


# ---------------------------------------------------------------------------
# Tests for create_attachment — validation rejections (no DB needed)
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_svg_with_fake_content_type_raises_unsupported_media_type(
    stub_storage: StubStorage,
) -> None:
    """SVG bytes with claimed_content_type='image/png' → UnsupportedMediaTypeError.

    The Content-Type header is NEVER trusted (T-92-05 LOCKED INVARIANT).
    put() must NOT be called.
    """
    from app.core.exceptions import UnsupportedMediaTypeError
    from app.modules.messaging import service

    mock_session = MagicMock()

    with pytest.raises(UnsupportedMediaTypeError):
        await service.create_attachment(
            mock_session,
            stub_storage,
            client_id=uuid4(),
            raw_bytes=SVG_BYTES,
            claimed_content_type="image/png",  # spoofed Content-Type
        )

    # put() must NEVER be called on invalid content
    assert len(stub_storage.put_calls) == 0, (
        "put() was called after UnsupportedMediaTypeError — magic-byte guard bypassed"
    )


@pytest.mark.asyncio
async def test_oversized_payload_raises_payload_too_large(
    stub_storage: StubStorage,
) -> None:
    """6MB payload → PayloadTooLargeError, no put() called (T-92-06)."""
    from app.core.exceptions import PayloadTooLargeError
    from app.modules.messaging import service

    mock_session = MagicMock()

    with pytest.raises(PayloadTooLargeError):
        await service.create_attachment(
            mock_session,
            stub_storage,
            client_id=uuid4(),
            raw_bytes=SIX_MB,
            claimed_content_type="image/jpeg",
        )

    assert len(stub_storage.put_calls) == 0, (
        "put() was called on oversized payload — size cap guard bypassed"
    )


# ---------------------------------------------------------------------------
# Tests for create_attachment — happy path (requires DB stub)
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_valid_jpeg_upload_returns_response_and_calls_put(
    stub_storage: StubStorage,
) -> None:
    """Valid JPEG bytes → AttachmentUploadResponse with UUID id + relative previewUrl.

    Stubs the repository and audit layers so no real DB is needed.
    Asserts:
      - storage.put() called once with key matching 'attachments/<uuid>'
      - content_type passed to put() is the VALIDATED mime (image/jpeg), not claimed_content_type
      - returned response.id is a UUID
      - returned response.preview_url starts with /api/v1/client/messages/attachments/
    """
    from app.modules.messaging import service

    client_id = uuid4()
    thread_id = uuid4()
    attachment_id = uuid4()
    mock_session = MagicMock()

    with (
        patch(
            "app.modules.messaging.service.repository.get_or_create_thread",
            new=AsyncMock(return_value=thread_id),
        ),
        patch(
            "app.modules.messaging.service.repository.insert_attachment",
            new=AsyncMock(return_value=attachment_id),
        ),
        patch(
            "app.modules.messaging.service.audit.emit",
            new=AsyncMock(),
        ) as mock_audit,
    ):
        result = await service.create_attachment(
            mock_session,
            stub_storage,
            client_id=client_id,
            raw_bytes=JPEG_MAGIC,
            claimed_content_type="image/jpeg",
        )

    # Storage put() was called exactly once
    assert len(stub_storage.put_calls) == 1
    put_call = stub_storage.put_calls[0]
    assert str(put_call["key"]).startswith("attachments/")
    assert put_call["content_type"] == "image/jpeg"
    assert put_call["data"] == JPEG_MAGIC

    # Object key is a UUID-based path (no client filename)
    key_str = str(put_call["key"])
    key_uuid_part = key_str.removeprefix("attachments/")
    UUID(key_uuid_part)  # raises ValueError if not a valid UUID

    # Response fields
    assert result.attachment_id == attachment_id
    assert result.preview_url == f"/api/v1/client/messages/attachments/{attachment_id}"

    # Audit was emitted exactly once
    mock_audit.assert_called_once()
    _, audit_kwargs = mock_audit.call_args
    assert audit_kwargs["actor_user_id"] is None
    assert audit_kwargs["resource_type"] == "message"
    assert audit_kwargs["client_id"] == str(client_id)


@pytest.mark.asyncio
async def test_valid_jpeg_upload_calls_insert_attachment_with_correct_args(
    stub_storage: StubStorage,
) -> None:
    """insert_attachment is called with correct thread_id, client_id, mime_type, size_bytes."""
    from app.modules.messaging import service

    client_id = uuid4()
    thread_id = uuid4()
    attachment_id = uuid4()
    mock_session = MagicMock()

    with (
        patch(
            "app.modules.messaging.service.repository.get_or_create_thread",
            new=AsyncMock(return_value=thread_id),
        ),
        patch(
            "app.modules.messaging.service.repository.insert_attachment",
            new=AsyncMock(return_value=attachment_id),
        ) as mock_insert,
        patch(
            "app.modules.messaging.service.audit.emit",
            new=AsyncMock(),
        ),
    ):
        await service.create_attachment(
            mock_session,
            stub_storage,
            client_id=client_id,
            raw_bytes=JPEG_MAGIC,
            claimed_content_type="image/jpeg",
        )

    mock_insert.assert_called_once()
    _, insert_kwargs = mock_insert.call_args
    assert insert_kwargs["thread_id"] == thread_id
    assert insert_kwargs["client_id"] == client_id
    assert insert_kwargs["mime_type"] == "image/jpeg"
    assert insert_kwargs["size_bytes"] == len(JPEG_MAGIC)
    # object_key is server-generated (UUID-based)
    assert str(insert_kwargs["object_key"]).startswith("attachments/")


# ---------------------------------------------------------------------------
# AttachmentUploadResponse schema: camelCase wire format
# ---------------------------------------------------------------------------


def test_attachment_upload_response_camelcase_wire() -> None:
    """AttachmentUploadResponse serialises attachment_id→attachmentId, preview_url→previewUrl."""
    from app.modules.messaging.schemas import AttachmentUploadResponse

    rid = uuid4()
    resp = AttachmentUploadResponse(
        attachment_id=rid,
        preview_url=f"/api/v1/client/messages/attachments/{rid}",
    )
    data = resp.model_dump(by_alias=True)
    assert "attachmentId" in data, f"Expected 'attachmentId' key, got: {list(data.keys())}"
    assert "previewUrl" in data, f"Expected 'previewUrl' key, got: {list(data.keys())}"
    assert data["attachmentId"] == rid
    assert data["previewUrl"] == f"/api/v1/client/messages/attachments/{rid}"

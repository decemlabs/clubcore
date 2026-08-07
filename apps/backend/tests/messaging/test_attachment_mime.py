"""MIME guard unit tests (Phase 92 ATT-02, T-92-01).

Tests use REAL magic bytes — no mocking.  The Content-Type header is never
consulted; all decisions are made on the byte stream alone.

TDD RED: written before app/integrations/storage/mime.py exists.
"""

from __future__ import annotations

# ---------------------------------------------------------------------------
# Real magic-byte constants for tests (no mock, no filetype import here)
# ---------------------------------------------------------------------------

# JPEG magic bytes (SOI marker)
JPEG_MAGIC = b"\xff\xd8\xff\xe0" + b"\x00" * 257

# PNG magic bytes (8-byte signature)
PNG_MAGIC = b"\x89PNG\r\n\x1a\n" + b"\x00" * 253

# WebP: RIFF....WEBPVP8  (16-byte header; filetype checks for 'WEBPVP8' prefix)
WEBP_MAGIC = b"RIFF\x00\x00\x00\x00WEBPVP8 " + b"\x00" * 245

# GIF89a magic bytes
GIF_MAGIC = b"GIF89a" + b"\x00" * 255

# SVG text (well-formed; should be rejected despite being a valid image format)
SVG_BYTES = b'<svg xmlns="http://www.w3.org/2000/svg"><rect/></svg>' + b"\x00" * 209

# HTML bytes (should be rejected)
HTML_BYTES = b"<!DOCTYPE html><html><head></head><body></body></html>" + b"\x00" * 208

# Empty input
EMPTY_BYTES = b""


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


def test_jpeg_accepted() -> None:
    from app.integrations.storage.mime import guess_allowed_mime

    result = guess_allowed_mime(JPEG_MAGIC)
    assert result == "image/jpeg"


def test_png_accepted() -> None:
    from app.integrations.storage.mime import guess_allowed_mime

    result = guess_allowed_mime(PNG_MAGIC)
    assert result == "image/png"


def test_webp_accepted() -> None:
    from app.integrations.storage.mime import guess_allowed_mime

    result = guess_allowed_mime(WEBP_MAGIC)
    assert result == "image/webp"


def test_gif_rejected() -> None:
    """GIF is a valid image format but NOT on the allowlist."""
    from app.integrations.storage.mime import guess_allowed_mime

    result = guess_allowed_mime(GIF_MAGIC)
    assert result is None


def test_svg_rejected() -> None:
    """SVG must be rejected even though it is a valid image format (T-92-01 LOCKED INVARIANT)."""
    from app.integrations.storage.mime import guess_allowed_mime

    result = guess_allowed_mime(SVG_BYTES)
    assert result is None


def test_html_rejected() -> None:
    """text/html must be rejected (T-92-01)."""
    from app.integrations.storage.mime import guess_allowed_mime

    result = guess_allowed_mime(HTML_BYTES)
    assert result is None


def test_empty_input_returns_none() -> None:
    """Empty bytes return None (not an exception)."""
    from app.integrations.storage.mime import guess_allowed_mime

    result = guess_allowed_mime(EMPTY_BYTES)
    assert result is None


def test_allowed_mimes_constant() -> None:
    """ALLOWED_MIMES must be exactly the three allowed types."""
    from app.integrations.storage.mime import ALLOWED_MIMES

    assert frozenset({"image/jpeg", "image/png", "image/webp"}) == ALLOWED_MIMES


def test_magic_byte_read_len_constant() -> None:
    """MAGIC_BYTE_READ_LEN must be 261 (filetype only needs first 261 bytes)."""
    from app.integrations.storage.mime import MAGIC_BYTE_READ_LEN

    assert MAGIC_BYTE_READ_LEN == 261

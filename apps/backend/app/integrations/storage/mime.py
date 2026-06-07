"""Magic-byte MIME allowlist guard (Phase 92 ATT-02, T-92-01).

LOCKED INVARIANT (P7): The ``Content-Type`` request header is NEVER consulted
here.  The only ground truth is the file's magic bytes.

``guess_allowed_mime`` reads the first ``MAGIC_BYTE_READ_LEN`` bytes from the
caller-supplied ``head`` buffer, passes them to ``filetype.guess``, and returns
the MIME type only if it is on the ``ALLOWED_MIMES`` allowlist.

Allowlist: {image/jpeg, image/png, image/webp}.

Explicitly rejected (even though they are valid image formats):
- image/svg+xml — SVG is XML/text and executes scripts in browsers.
- image/gif     — not on the allowlist; no animated image support in v2.5.
- text/*        — all text types, including text/html.
- everything else not in the allowlist.

Layer invariant: this module lives at ``integrations`` layer — MUST NOT import
from ``app.modules.*``.
"""

from __future__ import annotations

import filetype

# Only the first 261 bytes are needed; filetype uses at most 261 bytes for all
# detection algorithms.  Callers SHOULD pass at most MAGIC_BYTE_READ_LEN bytes.
MAGIC_BYTE_READ_LEN: int = 261

# Closed allowlist — three safe raster image formats only.
ALLOWED_MIMES: frozenset[str] = frozenset({"image/jpeg", "image/png", "image/webp"})


def guess_allowed_mime(head: bytes) -> str | None:
    """Return the detected MIME type if it is on the allowlist, else None.

    Args:
        head: Raw bytes from the start of the file (at most MAGIC_BYTE_READ_LEN
              bytes are needed; extra bytes are silently ignored).  An empty
              buffer always returns None.

    Returns:
        One of 'image/jpeg', 'image/png', 'image/webp', or None.

    The ``Content-Type`` request header is NEVER consulted (P7 LOCKED INVARIANT).
    SVG bytes, HTML bytes, GIF bytes, and all other non-allowlisted content
    return None.
    """
    if not head:
        return None

    # filetype.guess accepts bytes; it peeks at the leading bytes only.
    kind = filetype.guess(head[:MAGIC_BYTE_READ_LEN])
    if kind is None:
        return None

    mime: str = kind.mime
    if mime not in ALLOWED_MIMES:
        return None
    return mime

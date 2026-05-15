"""Audit hash helper (Phase 32 D-32-21..D-32-23).

Pure SHA-256 canonical-JSON over a payment row. Used by payments.service to
populate the `payment_row_hash` field of PaymentRecordedPayload and
RefundIssuedPayload (forensic chain-of-custody — D-30-04 / PAY-10 / REF-07).

Determinism: UUIDs serialized via str(); datetimes UTC-normalized via
astimezone(UTC).isoformat() — host TZ produces identical hashes for the same
instant. json.dumps with sort_keys=True, separators=(",", ":"),
ensure_ascii=False, default=str produces a byte-stable canonical form.

Architectural boundary: app.core.audit_hash MUST NOT import from
app.modules.* (importlinter `core-not-depend-on-modules` contract).
Only stdlib imports allowed in this module.
"""

from __future__ import annotations

import hashlib
import json
from collections.abc import Mapping
from datetime import UTC, datetime
from typing import Any
from uuid import UUID


def payment_row_hash(row: Mapping[str, Any]) -> str:
    """Return ``"sha256:<64-hex>"`` over the canonical-JSON of `row`.

    Canonicalization rules (D-32-21..D-32-23):
      * UUID values → ``str(value)``.
      * datetime values → ``value.astimezone(UTC).isoformat()`` so the host
        timezone does not influence the hash for the same instant.
      * All other values pass through ``json.dumps(..., default=str)``.
      * ``sort_keys=True, separators=(",", ":"), ensure_ascii=False``
        guarantees byte-stability across insertion order and locale.

    Output pattern: ``^sha256:[0-9a-f]{64}$`` (matches the audit-payload
    Pydantic constraint on ``payment_row_hash``).
    """
    canonical: dict[str, Any] = {}
    for key, value in row.items():
        if isinstance(value, UUID):
            canonical[key] = str(value)
        elif isinstance(value, datetime):
            # D-32-22 — UTC-normalize so host TZ does not affect the hash.
            canonical[key] = value.astimezone(UTC).isoformat()
        else:
            canonical[key] = value
    blob = json.dumps(
        canonical,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
        default=str,
    )
    digest = hashlib.sha256(blob.encode("utf-8")).hexdigest()
    return f"sha256:{digest}"


__all__ = ("payment_row_hash",)

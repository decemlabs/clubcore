"""Unit tests for app.core.audit_hash.payment_row_hash (Phase 32 D-32-21..D-32-23).

Covers determinism, UTC-normalization (host TZ independence), column-flip
sensitivity, output regex format, UUID normalization, None handling, and
sort-order independence.
"""

from __future__ import annotations

import re
from datetime import UTC, datetime, timezone
from uuid import UUID
from zoneinfo import ZoneInfo

import pytest

from app.core.audit_hash import payment_row_hash

_SAMPLE_ID = UUID("11111111-1111-4111-8111-111111111111")
_SAMPLE_USER_ID = UUID("22222222-2222-4222-8222-222222222222")
_SAMPLE_SUBJECT_ID = UUID("33333333-3333-4333-8333-333333333333")

_SAMPLE_ROW: dict[str, object] = {
    "id": _SAMPLE_ID,
    "subject_kind": "membership",
    "subject_id": _SAMPLE_SUBJECT_ID,
    "amount_kopecks": 250000,
    "method": "cash",
    "received_at": datetime(2026, 5, 15, 12, 30, 0, tzinfo=UTC),
    "received_by_user_id": _SAMPLE_USER_ID,
    "refund_of": None,
}


def test_determinism() -> None:
    """Same input dict twice → same hash."""
    h1 = payment_row_hash(_SAMPLE_ROW)
    h2 = payment_row_hash(_SAMPLE_ROW)
    assert h1 == h2


def test_tz_independence() -> None:
    """Same instant expressed in UTC vs Europe/Moscow → same hash (D-32-22)."""
    moscow_tz = ZoneInfo("Europe/Moscow")
    same_instant = datetime(2026, 5, 15, 12, 30, 0, tzinfo=UTC)
    row_utc = dict(_SAMPLE_ROW)
    row_utc["received_at"] = same_instant
    row_moscow = dict(_SAMPLE_ROW)
    # Convert the same UTC instant into Moscow zone — astimezone keeps the
    # absolute instant, payment_row_hash UTC-normalizes both back.
    row_moscow["received_at"] = same_instant.astimezone(moscow_tz)
    assert payment_row_hash(row_utc) == payment_row_hash(row_moscow)


def test_tz_independence_against_fixed_offset() -> None:
    """A datetime with a fixed-offset TZ produces the same hash as the UTC equivalent."""
    fixed_offset = timezone(offset=__import__("datetime").timedelta(hours=5))
    base_utc = datetime(2026, 5, 15, 12, 30, 0, tzinfo=UTC)
    row_utc = dict(_SAMPLE_ROW)
    row_utc["received_at"] = base_utc
    row_offset = dict(_SAMPLE_ROW)
    row_offset["received_at"] = base_utc.astimezone(fixed_offset)
    assert payment_row_hash(row_utc) == payment_row_hash(row_offset)


@pytest.mark.parametrize(
    "field, new_value",
    [
        ("id", UUID("99999999-9999-4999-8999-999999999999")),
        ("subject_kind", "pt_package"),
        ("subject_id", UUID("99999999-9999-4999-8999-999999999998")),
        ("amount_kopecks", 250001),
        ("method", "card"),
        ("received_at", datetime(2026, 5, 15, 12, 30, 1, tzinfo=UTC)),
        ("received_by_user_id", UUID("99999999-9999-4999-8999-999999999997")),
        ("refund_of", UUID("99999999-9999-4999-8999-999999999996")),
    ],
)
def test_column_flip_changes_hash(field: str, new_value: object) -> None:
    """Any single-field flip MUST change the hash (forensic distinguishability)."""
    baseline = payment_row_hash(_SAMPLE_ROW)
    mutated = dict(_SAMPLE_ROW)
    mutated[field] = new_value
    assert payment_row_hash(mutated) != baseline, f"hash unchanged when {field} flipped"


def test_format_matches_regex() -> None:
    """Hash output matches ``^sha256:[0-9a-f]{64}$`` (Pydantic constraint mirror)."""
    h = payment_row_hash(_SAMPLE_ROW)
    assert re.match(r"^sha256:[0-9a-f]{64}$", h) is not None


def test_uuid_normalization() -> None:
    """UUID and str(UUID) variants of the same id hash identically."""
    row_uuid = dict(_SAMPLE_ROW)
    row_str = dict(_SAMPLE_ROW)
    row_str["id"] = str(_SAMPLE_ID)
    assert payment_row_hash(row_uuid) == payment_row_hash(row_str)


def test_none_field_is_deterministic() -> None:
    """refund_of=None hashes deterministically (sentinel for sale-side rows)."""
    h1 = payment_row_hash(_SAMPLE_ROW)
    h2 = payment_row_hash(dict(_SAMPLE_ROW))
    assert h1 == h2


def test_sort_independence() -> None:
    """Different insertion order over the same key-set → same hash."""
    keys = list(_SAMPLE_ROW.keys())
    reverse_order: dict[str, object] = {key: _SAMPLE_ROW[key] for key in reversed(keys)}
    assert payment_row_hash(_SAMPLE_ROW) == payment_row_hash(reverse_order)

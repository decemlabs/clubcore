"""Unit tests for app.integrations.telegram.copy.pick_variant (Phase 27 NTF-COPY-01).

``pick_variant(client_id)`` MUST be deterministic per UUID (stable across
processes and time — D-27-10 anti-oracle property) and produce ~50/50 split
over uniformly random UUIDv4 inputs.

Force-A and Force-B UUIDs:
- ``UUID(bytes=b"\\x00" * 16)`` — first byte = 0 → ``(0 & 1) == 0`` → "A".
- ``UUID(bytes=b"\\x01" + b"\\x00" * 15)`` — first byte = 1 → ``(1 & 1) == 1`` → "B".
"""

from __future__ import annotations

from collections import Counter
from uuid import UUID, uuid4

from app.integrations.telegram.copy import pick_variant

_FORCE_A = UUID(bytes=b"\x00" * 16)
_FORCE_B = UUID(bytes=b"\x01" + b"\x00" * 15)


def test_pick_variant_is_deterministic_per_uuid() -> None:
    cid = UUID("12345678-1234-5678-1234-567812345678")
    results = {pick_variant(cid) for _ in range(5)}
    assert len(results) == 1


def test_pick_variant_force_a() -> None:
    assert pick_variant(_FORCE_A) == "A"


def test_pick_variant_force_b() -> None:
    assert pick_variant(_FORCE_B) == "B"


def test_pick_variant_split_is_balanced_over_random_uuids() -> None:
    counts: Counter[str] = Counter()
    for _ in range(1000):
        counts[pick_variant(uuid4())] += 1
    assert 400 <= counts["A"] <= 600, f"A count out of band: {counts}"
    assert 400 <= counts["B"] <= 600, f"B count out of band: {counts}"
    assert counts["A"] + counts["B"] == 1000

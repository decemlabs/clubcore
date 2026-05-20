"""Unit tests for ``select_expiring_variant`` — Phase 45 D-45-16.

Verifies the hoisted Phase 27 D-27-10 anti-oracle chooser still has the
exact same algorithmic shape (``client_id.bytes[0] & 1`` parity) when
called from the memberships/notifications module instead of inline in
the Telegram render code. Determinism + 50/50 distribution are the two
load-bearing properties.
"""

from __future__ import annotations

from uuid import UUID, uuid4

from app.modules.memberships.notifications import select_expiring_variant


def _uuid_with_first_byte(first: int) -> UUID:
    """Build a UUID with a deterministic first byte and zeros elsewhere."""
    return UUID(bytes=bytes([first]) + b"\x00" * 15)


def test_determinism_same_uuid_yields_same_variant() -> None:
    cid = uuid4()
    variants = {select_expiring_variant(cid) for _ in range(10)}
    assert len(variants) == 1


def test_even_first_byte_is_variant_a() -> None:
    for byte in (0x00, 0x02, 0x04, 0x06, 0x08, 0xFE):
        assert select_expiring_variant(_uuid_with_first_byte(byte)) == "A"


def test_odd_first_byte_is_variant_b() -> None:
    for byte in (0x01, 0x03, 0x05, 0x07, 0x09, 0xFF):
        assert select_expiring_variant(_uuid_with_first_byte(byte)) == "B"


def test_distribution_is_roughly_balanced() -> None:
    a_count = 0
    b_count = 0
    for _ in range(1000):
        variant = select_expiring_variant(uuid4())
        if variant == "A":
            a_count += 1
        else:
            b_count += 1
    assert 400 <= a_count <= 600, f"A count {a_count} outside [400, 600]"
    assert 400 <= b_count <= 600, f"B count {b_count} outside [400, 600]"
    assert a_count + b_count == 1000

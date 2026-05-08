"""Unit tests for _hash_telegram_user_id (Phase 20 D-20-10)."""

from __future__ import annotations

from app.integrations.telegram.handlers import _hash_telegram_user_id


def test_hash_is_stable() -> None:
    assert _hash_telegram_user_id(12345) == _hash_telegram_user_id(12345)


def test_different_inputs_produce_different_hashes() -> None:
    assert _hash_telegram_user_id(12345) != _hash_telegram_user_id(12346)


def test_hash_is_full_sha256_hex() -> None:
    h = _hash_telegram_user_id(12345)
    assert len(h) == 64
    assert all(c in "0123456789abcdef" for c in h)

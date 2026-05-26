"""Kopecks ↔ ЮKassa wire-format money converters.

Phase 47 INFRA-39 (Plan 47-05). The underscore-prefix on this module signals
*integration-internal* use — callers outside ``app.integrations.yookassa`` MUST
NOT import these helpers. For Russian-locale display formatting, use
``app.core.formatters.format_money`` (e.g., "1 200 ₽"); this module is the
wire-format counterpart (e.g., "199.00") consumed by ``YooKassaClient`` body
construction and webhook parsing in Phases 48-50.

Conversion discipline:
    - All arithmetic flows through ``decimal.Decimal``. No ``float`` anywhere.
    - Rounding mode is pinned to ``ROUND_HALF_EVEN`` (banker's rounding).
    - Sub-cent precision (>2 decimal places) on input is rejected — ЮKassa
      never sends such values; rejection catches malformed/tampered payloads
      early (T-47-05-02).
    - Negative values are rejected on both legs (T-47-05-03). ЮKassa wire
      amounts are always positive; refund sign lives at the ledger row level.

Off-by-100 / float-drift is BLOCKER pitfall #6 in ``research/PITFALLS.md``;
this module + its tests are the canonical pin.
"""

from __future__ import annotations

from decimal import ROUND_HALF_EVEN, Decimal, InvalidOperation

_CENT_QUANTUM = Decimal("0.01")
_INT_QUANTUM = Decimal("1")
_HUNDRED = Decimal(100)


def kopecks_to_yookassa(kopecks: int) -> str:
    """Convert internal kopecks integer to ЮKassa wire-format ruble string.

    Examples:
        kopecks_to_yookassa(0) == "0.00"
        kopecks_to_yookassa(1) == "0.01"
        kopecks_to_yookassa(19_900) == "199.00"
        kopecks_to_yookassa(9_999_999) == "99999.99"

    Raises:
        ValueError: if ``kopecks`` is negative.
    """
    if kopecks < 0:
        raise ValueError(f"kopecks must be non-negative, got {kopecks!r}")
    rubles = (Decimal(kopecks) / _HUNDRED).quantize(_CENT_QUANTUM, rounding=ROUND_HALF_EVEN)
    return f"{rubles:.2f}"


def yookassa_to_kopecks(amount: str) -> int:
    """Parse ЮKassa wire-format ruble string back to kopecks integer.

    Examples:
        yookassa_to_kopecks("199.00") == 19_900
        yookassa_to_kopecks("199") == 19_900
        yookassa_to_kopecks("00100.50") == 10_050

    Raises:
        ValueError: on non-numeric input, negative values, or amounts with
            more than 2 decimal places (sub-cent precision smuggling guard).
    """
    try:
        value = Decimal(amount)
    except InvalidOperation as exc:
        raise ValueError(f"invalid amount string: {amount!r}") from exc
    if value.is_nan() or value.is_infinite():
        raise ValueError(f"invalid amount string: {amount!r}")
    if value < 0:
        raise ValueError(f"amount must be non-negative, got {amount!r}")
    exponent = value.as_tuple().exponent
    if isinstance(exponent, int) and exponent < -2:
        raise ValueError("amount has more than 2 decimal places")
    return int((value * _HUNDRED).quantize(_INT_QUANTUM, rounding=ROUND_HALF_EVEN))

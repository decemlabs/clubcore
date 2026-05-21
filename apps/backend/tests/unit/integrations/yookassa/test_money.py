"""Unit tests for ``app.integrations.yookassa._money`` — kopecks ↔ ЮKassa wire-format.

Plan 47-05 (INFRA-39, Phase 47 Bedrock). Pins the Decimal-based conversion
discipline BEFORE Phase 48 ADAPTER-02 wires it into ``YooKassaClient`` body
construction and webhook parsing.

This file covers the ≥10 named edge cases enumerated in
``.planning/phases/47-bedrock/47-CONTEXT.md`` ``<specifics>``:

1. 0 kopecks → "0.00"
2. 1 kopeck → "0.01"
3. 99 kopecks → "0.99"
4. 100 kopecks → "1.00"
5. 9_999_999 kopecks → "99999.99"
6. Negative kopecks → ValueError
7. Round-trip 19_900 ↔ "199.00"
8. Missing decimal: "199" parses as 19_900
9. Leading zeros: "00100.50" parses as 10_050
10. Non-numeric "abc" → ValueError
11. Negative wire string "-1.00" → ValueError
12. Sub-cent precision "199.005" → ValueError (T-47-05-02 mitigation)
13. Parametrized round-trip grid (exactness pin)
14. ROUND_HALF_EVEN constant is referenced by the module (rounding-mode pin)

Off-by-100 / float-drift is BLOCKER pitfall #6 in ``research/PITFALLS.md``;
this test file is the canonical pin.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from app.integrations.yookassa._money import kopecks_to_yookassa, yookassa_to_kopecks


# ---------- kopecks_to_yookassa ----------

def test_kopecks_to_yookassa_zero() -> None:
    assert kopecks_to_yookassa(0) == "0.00"


def test_kopecks_to_yookassa_one_kopeck() -> None:
    assert kopecks_to_yookassa(1) == "0.01"


def test_kopecks_to_yookassa_99_kopecks() -> None:
    assert kopecks_to_yookassa(99) == "0.99"


def test_kopecks_to_yookassa_100_kopecks_is_one_ruble() -> None:
    assert kopecks_to_yookassa(100) == "1.00"


def test_kopecks_to_yookassa_9999999_kopecks() -> None:
    assert kopecks_to_yookassa(9_999_999) == "99999.99"


def test_kopecks_to_yookassa_rejects_negative() -> None:
    with pytest.raises(ValueError):
        kopecks_to_yookassa(-1)


# ---------- yookassa_to_kopecks ----------

def test_yookassa_to_kopecks_round_trip_199_00() -> None:
    assert yookassa_to_kopecks("199.00") == 19_900


def test_yookassa_to_kopecks_accepts_missing_decimal() -> None:
    assert yookassa_to_kopecks("199") == 19_900


def test_yookassa_to_kopecks_accepts_leading_zeros() -> None:
    assert yookassa_to_kopecks("00100.50") == 10_050


def test_yookassa_to_kopecks_rejects_non_numeric() -> None:
    with pytest.raises(ValueError):
        yookassa_to_kopecks("abc")


def test_yookassa_to_kopecks_rejects_negative() -> None:
    with pytest.raises(ValueError):
        yookassa_to_kopecks("-1.00")


def test_yookassa_to_kopecks_rejects_three_decimal_places() -> None:
    """T-47-05-02: sub-cent precision smuggled via webhook must be rejected."""
    with pytest.raises(ValueError):
        yookassa_to_kopecks("199.005")


# ---------- round-trip grid ----------

@pytest.mark.parametrize(
    "k",
    [0, 1, 99, 100, 999, 1_000, 9_999, 10_000, 99_999_999],
)
def test_round_trip_random_int_grid(k: int) -> None:
    """Exactness pin: kopecks → wire string → kopecks is identity across the grid."""
    assert yookassa_to_kopecks(kopecks_to_yookassa(k)) == k


# ---------- rounding-mode pin ----------

def test_kopecks_to_yookassa_half_even_rounding_pin() -> None:
    """Module must explicitly reference ROUND_HALF_EVEN (pinning the rounding mode).

    Since kopecks → wire is exact at the cent boundary, behavioral assertion alone
    cannot distinguish HALF_EVEN from other modes. We pin the call signature by
    inspecting the module source — the import + quantize call must both exist.
    """
    source = Path(
        Path(__file__).resolve().parents[4]
        / "app"
        / "integrations"
        / "yookassa"
        / "_money.py"
    ).read_text(encoding="utf-8")
    assert "ROUND_HALF_EVEN" in source
    assert "quantize" in source

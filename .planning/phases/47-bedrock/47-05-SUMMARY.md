---
phase: 47-bedrock
plan: 05
subsystem: integrations/yookassa
tags: [money, decimal, wire-format, yookassa, tdd]
requires:
  - 47-02  # YooKassaSettings (sibling skeleton; shared test package __init__)
provides:
  - "app.integrations.yookassa._money.kopecks_to_yookassa"
  - "app.integrations.yookassa._money.yookassa_to_kopecks"
affects: []
tech-stack:
  added: []
  patterns:
    - "Pure-function Decimal converters with ROUND_HALF_EVEN at the wire boundary"
    - "Underscore-prefix integration-internal module convention"
    - "Source-pin tests for rounding-mode constants (read module source as string)"
key-files:
  created:
    - apps/backend/app/integrations/yookassa/_money.py
    - apps/backend/tests/unit/integrations/yookassa/test_money.py
  modified: []
decisions:
  - "T-47-05-02 mitigation: reject Decimal.as_tuple().exponent < -2 instead of silently rounding sub-cent input (catches webhook tampering early)"
  - "Wrap InvalidOperation as ValueError at the parser boundary so callers don't depend on decimal internals"
  - "Module name kept underscore-prefixed (_money.py) — explicit signal that callers outside app.integrations.yookassa must NOT import; canonical display formatter app.core.formatters.format_money is separate"
metrics:
  duration: ~6 min
  completed: 2026-05-21
---

# Phase 47 Plan 05: ЮKassa wire-format money converters Summary

One-liner: Pure Decimal-based `kopecks_to_yookassa` / `yookassa_to_kopecks` converters with `ROUND_HALF_EVEN`, sub-cent rejection, and 22 unit tests pinning behavior for INFRA-39.

## What Shipped

**Files**

- `apps/backend/app/integrations/yookassa/_money.py` (~80 lines incl. module docstring) — two pure functions over `decimal.Decimal` with `ROUND_HALF_EVEN` rounding. Zero `float` arithmetic in the module; verified by `grep -n "float(" → exit 1`.
- `apps/backend/tests/unit/integrations/yookassa/test_money.py` (~120 lines) — 14 named test functions + 9 parametrized round-trip cases = 22 test items, all passing.

**Exact signatures**

```python
def kopecks_to_yookassa(kopecks: int) -> str: ...
def yookassa_to_kopecks(amount: str) -> int: ...
```

**Test inventory (14 named + 9 parametrized = 22 total)**

| # | Test name | Behavior pinned |
|---|-----------|-----------------|
| 1 | `test_kopecks_to_yookassa_zero` | `0 → "0.00"` |
| 2 | `test_kopecks_to_yookassa_one_kopeck` | `1 → "0.01"` |
| 3 | `test_kopecks_to_yookassa_99_kopecks` | `99 → "0.99"` |
| 4 | `test_kopecks_to_yookassa_100_kopecks_is_one_ruble` | `100 → "1.00"` |
| 5 | `test_kopecks_to_yookassa_9999999_kopecks` | `9_999_999 → "99999.99"` |
| 6 | `test_kopecks_to_yookassa_rejects_negative` | `-1 → ValueError` |
| 7 | `test_yookassa_to_kopecks_round_trip_199_00` | `"199.00" → 19_900` |
| 8 | `test_yookassa_to_kopecks_accepts_missing_decimal` | `"199" → 19_900` |
| 9 | `test_yookassa_to_kopecks_accepts_leading_zeros` | `"00100.50" → 10_050` |
| 10 | `test_yookassa_to_kopecks_rejects_non_numeric` | `"abc" → ValueError` |
| 11 | `test_yookassa_to_kopecks_rejects_negative` | `"-1.00" → ValueError` |
| 12 | `test_yookassa_to_kopecks_rejects_three_decimal_places` | `"199.005" → ValueError` (T-47-05-02) |
| 13 | `test_round_trip_random_int_grid` (×9) | exactness across `[0, 1, 99, 100, 999, 1_000, 9_999, 10_000, 99_999_999]` |
| 14 | `test_kopecks_to_yookassa_half_even_rounding_pin` | module source contains `ROUND_HALF_EVEN` and `quantize` |

Plan minimum was ≥10 named tests; delivered 14 + parametrized grid.

## TDD Gate Sequence

| Phase | Commit | Description |
|-------|--------|-------------|
| RED | `8bf43c2` | `test(47-05): add failing tests for ЮKassa wire-format money converters` — module did not yet exist; collection failed with `ModuleNotFoundError` as required. |
| GREEN | `b9dd76c` | `feat(47-05): implement ЮKassa wire-format money converters (INFRA-39)` — module created, all 22 tests pass, ruff + mypy --strict + import-linter green. |
| REFACTOR | (skipped) | Module is ~80 lines including docstring; two functions; no duplication. No cleanup needed. |

## Verification Results

| Gate | Command | Result |
|------|---------|--------|
| Tests | `uv run pytest tests/unit/integrations/yookassa/test_money.py -v` | 22 passed in 0.02s |
| Smoke | `uv run python -c "from app.integrations.yookassa._money import …; assert kopecks_to_yookassa(19900) == '199.00'; assert yookassa_to_kopecks('199.00') == 19900"` | Exit 0 |
| Signature count | `grep -E '^def (kopecks_to_yookassa\|yookassa_to_kopecks)' …/_money.py \| wc -l` | 2 (≥2 required) |
| Test count | `grep -E '^def test_' …/test_money.py \| wc -l` | 14 (≥10 required) |
| Ruff | `uv run ruff check app/integrations/yookassa/_money.py tests/unit/integrations/yookassa/test_money.py` | All checks passed |
| mypy --strict | `uv run mypy --strict app/integrations/yookassa/_money.py` | Success: no issues found in 1 source file |
| No float | `grep -n "float(" app/integrations/yookassa/_money.py` | (no match — exit 1) |
| import-linter | `uv run lint-imports` | Contracts: 3 kept, 0 broken |

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Lint] Fixed ruff RUF002 (en-dash) in module docstring**
- **Found during:** Verification gates after GREEN implementation
- **Issue:** Docstring contained `Phases 48–50` with an EN DASH (U+2013); ruff flagged as ambiguous Cyrillic-confusable
- **Fix:** Replaced with `Phases 48-50` (HYPHEN-MINUS)
- **Files modified:** `apps/backend/app/integrations/yookassa/_money.py`
- **Commit:** `b9dd76c` (folded into GREEN)

**2. [Rule 1 - Lint] Fixed ruff I001 import ordering in test file**
- **Found during:** Verification gates after GREEN implementation
- **Issue:** Blank line between `import pytest` and `from app...` was treated as a sub-block separator within the third-party group; ruff isort grouped them as one block instead
- **Fix:** Ran `ruff check --fix` which auto-rewrote the import block to compliant form
- **Files modified:** `apps/backend/tests/unit/integrations/yookassa/test_money.py`
- **Commit:** `b9dd76c` (folded into GREEN)

## Threat Model Verification

Threat register from PLAN had 4 dispositions, all marked `mitigate`. Each is now covered by code + test:

| Threat ID | Mitigation in code | Pinned by test |
|-----------|---------------------|----------------|
| T-47-05-01 (off-by-100 / float drift) | All arithmetic via `Decimal`; `_HUNDRED = Decimal(100)`; no `float(` in module | Tests 1-5 (boundary values), Test 13 (round-trip grid) |
| T-47-05-02 (sub-cent smuggling) | `Decimal.as_tuple().exponent < -2 → ValueError` | Test 12 (`"199.005" → ValueError`) |
| T-47-05-03 (negative misrepresentation) | Both functions raise `ValueError` on negative input | Tests 6, 11 |
| T-47-05-04 (InvalidOperation leak) | `try/except InvalidOperation` wraps as `ValueError` with caller-friendly message | Test 10 (`"abc" → ValueError`) |

## Threat Flags

(none — no new security-relevant surface introduced beyond the threat register)

## PITFALL #6 Mitigation Statement

`.planning/research/PITFALLS.md` lists "off-by-100 kopeck/ruble drift" as BLOCKER pitfall #6. This plan eliminates the bug class at the wire boundary:

- **Storage discipline:** Internal money is always `int` kopecks (CLAUDE.md domain convention).
- **Wire discipline:** Conversion to/from the ЮKassa "NNN.NN" string format goes exclusively through these two converters.
- **No float anywhere:** `grep -n "float(" apps/backend/app/integrations/yookassa/_money.py` is empty.
- **Rounding pinned:** `ROUND_HALF_EVEN` is referenced in the source and asserted by test 14.
- **Round-trip exactness:** Test 13 parametrizes across 9 representative values (0, 1, 99, 100, 999, 1_000, 9_999, 10_000, 99_999_999) and asserts `yookassa_to_kopecks(kopecks_to_yookassa(k)) == k` for every value.

Phase 48 ADAPTER-02 (YooKassaClient body construction) and Phase 49/50 webhook parsing import these two functions as the canonical money boundary; no other code may perform kopecks↔rubles arithmetic.

## Self-Check: PASSED

- `apps/backend/app/integrations/yookassa/_money.py` — FOUND
- `apps/backend/tests/unit/integrations/yookassa/test_money.py` — FOUND
- Commit `8bf43c2` (RED) — FOUND
- Commit `b9dd76c` (GREEN) — FOUND

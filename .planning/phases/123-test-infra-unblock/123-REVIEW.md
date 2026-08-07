---
phase: 123-test-infra-unblock
reviewed: 2026-07-26T00:00:00Z
depth: standard
files_reviewed: 3
files_reviewed_list:
  - apps/backend/tests/integration/bookings/test_bookings_create.py
  - apps/backend/tests/messaging/test_attachment_idor.py
  - apps/backend/tests/modules/client_portal/test_client_me_service.py
findings:
  critical: 0
  warning: 0
  info: 3
  total: 3
status: clean
---

# Phase 123: Code Review Report

**Reviewed:** 2026-07-26T00:00:00Z
**Depth:** standard
**Files Reviewed:** 3
**Status:** clean

## Summary

Reviewed the diff vs `b88eb2ee` for all three test files plus a full standard-depth read of each file in context. All three changes match their stated intent exactly, with no scope creep or semantic drift:

1. `test_attachment_idor.py` — added `from typing import Any`. Confirmed via `ruff check` at both the old and new commit that this fixes exactly the 3 pre-existing `F821 Undefined name 'Any'` errors (the file uses forward-ref string annotations `-> "Any":` for two seed helpers) and introduces no new lint findings.
2. `test_client_me_service.py` — widened `from uuid import uuid4` to `from uuid import UUID, uuid4`. Confirmed via `ruff check` that this fixes exactly the 2 pre-existing `F821 Undefined name 'UUID'` errors in `_insert_online_payment`'s type annotations, with no new findings.
3. `test_bookings_create.py` — replaced the hardcoded `2026-07-01` / `2026-06-30` Moscow-TZ boundary dates with dates computed relative to `datetime.now(UTC) + timedelta(days=365)`. This was a real time-bomb: today's date in this environment is 2026-07-26, so the old hardcoded slot date (`2026-07-01 01:00 Moscow`) was already in the past, which would very likely have caused `create_booking` to fail on a different guard (or otherwise diverge from the intended `PtPackageExpiredBeforeSlotError` path) before this fix landed.

**Fixture-fix correctness (the specific focus area):**
- The new code derives `future_moscow_date` from `datetime.now(UTC)`, not from a second hardcoded literal — it will not go stale again. This is the correct fix pattern and matches the existing `far_future_start = datetime.now(UTC) + timedelta(days=365)` idiom already used two tests down in the same file (`test_create_booking_pt_package_null_end_date_skips_validity_guard`, line 350), so it's consistent with established convention rather than a novel pattern.
- The core assertion the test exists to protect — "01:00 Moscow == 22:00 UTC the prior calendar day" — holds for any date because `Europe/Moscow` has used a fixed UTC+3 offset with no DST transitions since 2014. Constructing `datetime(year, month, day, 1, 0, tzinfo=moscow_tz)` directly (rather than via `.replace`/`fold` handling) is therefore safe for this specific zone; this would be a bug for a DST-observing zone but is not one here.
- `future_moscow_date - timedelta(days=1)` correctly returns a `date` (matching the type of the removed `date(2026, 6, 30)` literal it replaces), so `make_pt_package(end_date=...)` receives the same type as before.
- Ran the full test module and the specific test in isolation against the real local Postgres stack: all 36 tests across the three reviewed files pass, including `test_create_booking_pt_package_expired_before_slot_moscow_tz`, confirming the `PtPackageExpiredBeforeSlotError` path is genuinely reachable again.
- No semantic changes beyond the stated intent were found in any of the three files — the `import`-only diffs are pure lint fixes with zero behavioral surface, and the bookings diff only changes date derivation, not the assertions, request shape, or control flow of the test.

No Critical or Warning findings. Three pre-existing, out-of-scope Info items are noted below per the review brief ("pre-existing issues elsewhere in these files are Info-level at most") — none were introduced or touched by this phase's diff.

## Info

### IN-01: Pre-existing unused imports in test_attachment_idor.py (not touched by this diff)

**File:** `apps/backend/tests/messaging/test_attachment_idor.py:17,22`
**Issue:** `ruff check` flags `datetime.UTC` and `datetime.datetime` (line 17) and `pytest_asyncio` (line 22) as unused (`F401`) in both the pre-diff and post-diff versions of this file. These predate Phase 123 and are unrelated to the `Any` import fix — the diff neither introduced nor fixed them.
**Fix:** Remove the unused `UTC`, `datetime`, and `pytest_asyncio` imports in a future lint-cleanup pass (`ruff check --fix` handles all three automatically), or confirm intentional re-export and add `# noqa: F401` with a comment if kept for future use.

### IN-02: Redundant string-quoted forward refs given `from __future__ import annotations`

**File:** `apps/backend/tests/messaging/test_attachment_idor.py:43,59`
**Issue:** `_seed_staff(...) -> "Any":` and `_seed_client(..., staff: "Any", ...) -> "Any":` use explicit string-quoted annotations, but the module already has `from __future__ import annotations` (line 15), which makes all annotations lazily-evaluated strings automatically. The explicit quotes are redundant (pre-existing style, not introduced by this diff — the `Any` import was needed regardless, since mypy resolves the forward reference against imported names either way).
**Fix:** Drop the redundant quotes (`-> Any:`, `staff: Any`) for consistency with the rest of the module's annotation style, and consider annotating with the concrete `User`/`Client` types instead of `Any` for better test-signature clarity.

### IN-03: Pre-existing mypy errors in test_client_me_service.py unrelated to the UUID import fix

**File:** `apps/backend/tests/modules/client_portal/test_client_me_service.py:41`
**Issue:** `mypy` reports 4 `arg-type` errors on `_payload(**kwargs: object) -> ClientProfileUpdateRequest: return ClientProfileUpdateRequest(**kwargs)` (the `**dict[str, object]` kwargs don't structurally match the individual optional field types on the Pydantic model). Confirmed present identically before and after the Phase 123 diff — the `UUID` import widening only fixed the two `F821`/`name-defined` errors on lines 282/284 and did not touch (or need to touch) this helper.
**Fix:** Out of scope for this phase; if addressed later, prefer `TypedDict` or explicit keyword params over `**kwargs: object` for `_payload` to satisfy mypy without a `# type: ignore`.

---

_Reviewed: 2026-07-26T00:00:00Z_
_Reviewer: Claude (gsd-code-reviewer)_
_Depth: standard_

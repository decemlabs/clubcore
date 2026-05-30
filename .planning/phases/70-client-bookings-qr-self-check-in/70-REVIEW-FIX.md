---
phase: 70-client-bookings-qr-self-check-in
fixed_at: 2026-05-30T12:30:00Z
review_path: .planning/phases/70-client-bookings-qr-self-check-in/70-REVIEW.md
iteration: 1
findings_in_scope: 4
fixed: 4
skipped: 0
status: all_fixed
---

# Phase 70: Code Review Fix Report

**Fixed at:** 2026-05-30T12:30:00Z
**Source review:** .planning/phases/70-client-bookings-qr-self-check-in/70-REVIEW.md
**Iteration:** 1

**Summary:**
- Findings in scope: 4 (CR-01, CR-03, WR-01, WR-02 — CR-02, IN-01, IN-02 explicitly deferred)
- Fixed: 4
- Skipped: 0

## Fixed Issues

### CR-01: Rate-limit TOCTOU race allows limit bypass

**Files modified:** `apps/backend/app/modules/client_portal/router.py`
**Commit:** `72bae911`
**Applied fix:** Replaced the non-atomic GET-then-INCR pattern in both
`_enforce_qr_token_rate_limit` and `_enforce_check_in_rate_limit` with an
atomic INCR-first pipeline. The pipeline now does `INCR` + `EXPIRE(nx=True)`:
INCR atomically returns the new counter value; EXPIRE with `nx=True` sets the
TTL only on the first increment (anchoring the window to the first request,
not resetting it on each one). The comparison flips from `>= limit` (before
INCR) to `> limit` (after INCR). Limits (20/min qr-token, 60/min check-in),
key formats, and the `RateLimited("rate_limited")` raise are all preserved.

### CR-03: `verify_client_idempotency` missing from `idempotency.__all__`

**Files modified:** `apps/backend/app/core/idempotency.py`
**Commit:** `a09b91ef`
**Applied fix:** Added `"verify_client_idempotency"` to the `__all__` tuple
in the correct alphabetical/logical position — between
`"store_idempotency_response"` and `"verify_idempotency"`. Annotated with a
comment marking it as the Phase 70 addition.

### WR-01: Router summary documents wrong HTTP status for `cancel_window_expired`

**Files modified:** `apps/backend/app/modules/client_portal/router.py`,
`apps/backend/app/modules/client_portal/service.py`,
`apps/backend/tests/integration/client_portal/test_client_booking_idor.py`
**Commit:** `9ac18811`
**Applied fix:** Changed all occurrences of `422 cancel_window_expired` to
`409 cancel_window_expired` in documentation strings:
- Router `summary=` string for `client_cancel_booking`
- Service `cancel_client_booking` docstring
- Test module docstring (header list item 3)
- Test docstring for `test_client_cancel_within_window_returns_cancel_window_expired`
- Test assertion relaxed from `status_code in (409, 422)` to exact `== 409`
The `CancelWindowExpiredError` class (a `ConflictError` with `status_code=409`)
was not changed — 409 is authoritative. The 422 `no_active_pt_package` and
409 `slot_already_booked` cases were intentionally left untouched.

### WR-02: `check_in_via_qr` silently treats UUID parse failure as a valid client_id

**Files modified:** `apps/backend/app/modules/client_portal/service.py`
**Commit:** `97a85992`
**Applied fix:** Wrapped `UUID(claims.sub)` in a `try/except ValueError` block
that raises `InvalidSession("invalid_session")` on parse failure — matching the
exact pattern in `dependencies.py` at lines 794-797 and 1223-1226. Added
`InvalidSession` to the module's `app.core.exceptions` import. A malformed
`sub` that passes JWT signature verification now produces a controlled 401
`invalid_session` response instead of an unhandled 500.

---

## Gate Results

All four project gates passed after fixes:

| Gate | Result |
|------|--------|
| `uv run ruff check app tests` | PASS (pre-existing noqa warnings only) |
| `uv run mypy app/modules/client_portal/ app/core/idempotency.py` | PASS (0 issues, 6 files) |
| `uv run lint-imports` | PASS (3 contracts kept, 0 broken) |
| `uv run pytest tests/integration/client_portal/ tests/unit/core/test_qr_token.py -q` | PASS (51 passed) |

---

_Fixed: 2026-05-30T12:30:00Z_
_Fixer: Claude (gsd-code-fixer)_
_Iteration: 1_

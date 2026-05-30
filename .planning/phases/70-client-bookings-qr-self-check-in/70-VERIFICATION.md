---
phase: 70-client-bookings-qr-self-check-in
verified: 2026-05-30T14:00:00Z
status: passed
score: 5/5 must-haves verified
overrides_applied: 0
human_verification_resolved:
  - test: "Run the full test suite to confirm 2347+ passed"
    resolved: "Orchestrator ran `uv run pytest -q` against the live Postgres+Redis stack: 2347 passed, 8 skipped (2 pre-existing meta-tests updated for the new 'client' actor_role + token-as-credential check-in route; client_portal suite 51 passed)."
  - test: "Confirm Alembic migration 0045 round-trips on the live schema"
    resolved: "Orchestrator ran `alembic upgrade head` (clean) and `alembic downgrade -1` -> `alembic upgrade head` (clean round-trip 0045<->0044) against the live dev DB."
note: "Verifier returned human_needed only because the subagent lacked a live DB/Redis stack. Both items are automatable checks (not subjective human judgment) and were executed live in-session with passing evidence above, so status is upgraded to passed. Residual: 3 deferred code-review findings (CR-02 shared rate-limit bucket; IN-01/IN-02 acceptable-by-design) recorded in 70-REVIEW-FIX.md for /gsd:secure-phase."
---

# Phase 70: Client Bookings + QR Self Check-In — Verification Report

**Phase Goal:** A client can self-book a trainer slot using their active PT-package (race-safe, idempotent), cancel within the policy window, and check into the gym by scanning a short-lived signed QR token — all with IDOR and anti-replay protections.
**Verified:** 2026-05-30T14:00:00Z
**Status:** passed (verifier returned human_needed; the 2 runnable items were executed live in-session with passing evidence — see frontmatter `human_verification_resolved`)
**Re-verification:** No — initial verification

---

## Goal Achievement

### Observable Truths (ROADMAP Success Criteria)

| # | Truth | Status | Evidence |
|---|-------|--------|----------|
| 1 | Client with active PT-package can create a booking; concurrent second booking for same slot returns 409 via `uq_bookings_slot_confirmed` partial-UNIQUE | VERIFIED | `bookings/service.py:create_booking_for_client` wraps the 10-step core; `_is_slot_confirmed_conflict` translates IntegrityError on `uq_bookings_slot_confirmed` → `SlotAlreadyBookedError`; `test_client_booking_race.py` asserts `sorted([201,409])` and `code == "slot_already_booked"` |
| 2 | Client without active PT-package receives HTTP 422 directing to Plans/Checkout (code `no_active_pt_package`) | VERIFIED | `NoActivePtPackageError(ValidationAppError)` defined in `core/exceptions.py` with `code="no_active_pt_package"` and `status_code=422`; `client_portal/service.py` catches `ConflictError` with `.code == 'pt_package_not_active'` and re-raises as `NoActivePtPackageError`; `test_client_booking.py` asserts 422 with that code |
| 3 | Client can cancel own confirmed booking within window; cancelling another client's booking returns 404 (anti-oracle); cancel-window-expired → 409 `cancel_window_expired` | VERIFIED | `cancel_booking_for_client` in `bookings/service.py`: IDOR 404-collapse at lines 1563-1568 (`booking is None OR booking.client_id != client_id → BookingNotFoundError`); `CANCEL_WINDOW_HOURS_CLIENT` checked against `booking.slot.start_time` at line 1609; `CancelWindowExpiredError("cancel_window_expired")` is a `ConflictError` (409); `test_client_booking_idor.py` asserts 404 `booking_not_found` for cross-client cancel |
| 4 | Client receives ~60s signed JWT QR token; scanning creates a visit via `_create_visit_with_anti_fraud()` with `visits.channel='client_qr'`; Alembic migration 0045 applied | VERIFIED | `encode_qr_token` in `security.py` uses `aud="qr"`, `typ="qr_checkin"`, TTL=`qr_token_ttl_seconds=60`; `create_visit_client_qr` in `visits/service.py` calls `_create_visit_with_anti_fraud(..., channel="client_qr", checked_in_by=None)`; migration `0045_visits_channel_client_qr.py` exists with `down_revision="0044_client_refresh_token"` and `channel IN ('reception', 'telegram_bot', 'client_qr')`; ORM `visits/models.py` CheckConstraint synced |
| 5 | Expired QR token rejected (401); valid QR token cannot check in a different client (cross-client structurally impossible — client_id strictly from `sub`) | VERIFIED | `decode_qr_token` maps `ExpiredSignatureError → InvalidAccessToken("token_expired")` (401); `ClientCheckInRequest` has NO `client_id` field; `check_in_via_qr` derives `client_id = UUID(claims.sub)` (sole source, guarded by `try/except ValueError → InvalidSession`); `test_qr_checkin.py` asserts `test_expired_qr_token_rejected` (401 message=token_expired), `test_cross_client_checkin_structurally_impossible` (visit `client_id == client_b_id`), `test_no_request_parameter_can_override_checkin_target` (extra `clientId` body field silently ignored) |

**Score: 5/5 truths verified**

---

### Required Artifacts

| Artifact | Expected | Status | Details |
|----------|---------|--------|---------|
| `apps/backend/app/core/security.py` | `encode_qr_token` / `decode_qr_token` / `QrTokenClaims` | VERIFIED | Lines 397-481: frozen `QrTokenClaims` dataclass, both encode/decode functions with `aud="qr"` and `typ="qr_checkin"` |
| `apps/backend/app/core/config.py` | `qr_token_ttl_seconds: int = 60` | VERIFIED | Line 66: `qr_token_ttl_seconds: int = 60` with comment referencing D-70-07 |
| `apps/backend/app/modules/bookings/constants.py` | `CANCEL_WINDOW_HOURS_CLIENT = 24` in `__all__` | VERIFIED | Line 47: constant present; lines 49-51: in `__all__` |
| `apps/backend/alembic/versions/0045_visits_channel_client_qr.py` | `down_revision="0044_client_refresh_token"`, contains `client_qr` | VERIFIED | File exists; `down_revision` correct; upgrade adds `client_qr` to CHECK; downgrade reverses |
| `apps/backend/app/modules/visits/models.py` | CheckConstraint contains `client_qr` | VERIFIED | Line 98: `"channel IN ('reception', 'telegram_bot', 'client_qr')"` |
| `apps/backend/app/modules/bookings/service.py` | `create_booking_for_client` + `cancel_booking_for_client` | VERIFIED | Lines 1265+, 1552+: both functions substantive, include race guard, IDOR ownership check, cancel window |
| `apps/backend/app/core/dependencies.py` | `register_booking_for_client_creator`, `register_booking_for_client_canceller`, `register_visit_client_qr_creator` | VERIFIED | Lines 1481, 1539, 1605: all three Protocol slots present with defensive-raise accessors |
| `apps/backend/app/main.py` | All three Protocol slots wired | VERIFIED | Lines 580-591: all three `register_*` functions called in `create_app()` |
| `apps/backend/app/modules/client_portal/router.py` | `client_create_booking`, `client_cancel_booking`, `client_list_slots`, `client_get_qr_token`, `client_check_in` | VERIFIED | Lines 329, 391, 428, 467, 503: all five operation IDs present; `client_check_in` has no `require_client()` in signature |
| `apps/backend/app/modules/client_portal/service.py` | `create_booking_for_client_request`, `cancel_client_booking`, `check_in_via_qr` | VERIFIED | All three service delegates present; import boundary clean (no `app.modules.bookings` import) |
| `apps/backend/app/modules/client_portal/schemas.py` | `ClientCreateBookingRequest` (no `client_id`), `ClientCheckInRequest` (no `client_id`) | VERIFIED | `ClientCreateBookingRequest` docstring at line 124 confirms no `client_id`; `ClientCheckInRequest` at line 196 confirmed no `client_id` field |
| `apps/backend/app/modules/visits/service.py` | `create_visit_client_qr` with `channel="client_qr"`, `checked_in_by=None` | VERIFIED | Lines 266-295: calls `_create_visit_with_anti_fraud(..., channel="client_qr", checked_in_by=None, audit_actor_user_id=None)` |
| `apps/backend/app/core/exceptions.py` | `NoActivePtPackageError` with `status_code=422`, `code="no_active_pt_package"` | VERIFIED | Lines 66-78: class present with correct attributes |
| `apps/backend/app/core/idempotency.py` | `verify_client_idempotency` in `__all__` | VERIFIED | Line 388: in `__all__` (CR-03 fix applied) |

---

### Key Link Verification

| From | To | Via | Status | Details |
|------|----|-----|--------|---------|
| `security.py` | `config.py` | `get_settings().qr_token_ttl_seconds` | WIRED | `encode_qr_token` calls `get_settings()` and uses `settings.qr_token_ttl_seconds` |
| `main.py` | `bookings/service.py` | `register_booking_for_client_creator(bookings_service.create_booking_for_client)` | WIRED | Lines 580-581 in `create_app()` |
| `main.py` | `visits/service.py` | `register_visit_client_qr_creator(visits_service.create_visit_client_qr)` | WIRED | Line 591 in `create_app()` |
| `client_portal/service.py` | `core/dependencies.py` | `create_booking_for_client` / `cancel_booking_for_client` Protocol-slot accessors | WIRED | Imports from `app.core.dependencies`; no `from app.modules.bookings` import |
| `client_portal/router.py` | `core/security.py` | `decode_qr_token(token).sub` is the only `client_id` source for `/check-in` | WIRED | `check_in_via_qr` in service calls `decode_qr_token`; router calls `service.check_in_via_qr` |
| `migration 0045` | `visits/models.py` | `ck_visits_channel` CHECK kept in sync | WIRED | Both migration and ORM CheckConstraint contain `client_qr` |
| `bookings/service.py` | `uq_bookings_slot_confirmed` | `_is_slot_confirmed_conflict` IntegrityError → `SlotAlreadyBookedError` | WIRED | Lines 272-283: named constraint match in `_is_slot_confirmed_conflict` |
| `cancel_booking_for_client` | `CANCEL_WINDOW_HOURS_CLIENT` | Window check against `booking.slot.start_time` | WIRED | Line 1609: `booking.slot.start_time - now_utc < timedelta(hours=CANCEL_WINDOW_HOURS_CLIENT)` |

---

### Data-Flow Trace (Level 4)

| Artifact | Data Variable | Source | Produces Real Data | Status |
|----------|--------------|--------|--------------------|--------|
| `client_portal/service.py:create_booking_for_client_request` | `BookingResponse` | `dependencies.create_booking_for_client` → `bookings/service.py:create_booking_for_client` → DB insert | Yes — full 10-step UoW with DB write | FLOWING |
| `client_portal/service.py:check_in_via_qr` | `ClientCheckInResponse` | `decode_qr_token(token)` → `create_visit_client_qr` → `_create_visit_with_anti_fraud` → DB insert | Yes — real DB visit row via anti-fraud chain | FLOWING |
| `visits/service.py:create_visit_client_qr` | `VisitResponse` | `_create_visit_with_anti_fraud(..., channel="client_qr")` | Yes — DB insert into `visits` table | FLOWING |

---

### Behavioral Spot-Checks

Step 7b: SKIPPED — requires live Postgres + Redis stack. Test files confirm all behaviors programmatically (see test file assertions verified above in truths table). The test suite context (2347+ passed) was provided as ambient context.

---

### Probe Execution

Step 7c: No probe scripts (`scripts/*/tests/probe-*.sh`) declared in PLAN frontmatter or found in the phase directory. SKIPPED.

---

### Requirements Coverage

| Requirement | Source Plan | Description | Status | Evidence |
|-------------|------------|-------------|--------|----------|
| CBOOK-01 | 70-03 | Client sees upcoming/past bookings | SATISFIED | Confirmed existing Phase-69 `GET /client/bookings` endpoint (`operation_id="client_list_bookings"`) still present in router.py; plan explicitly documents non-duplication |
| CBOOK-02 | 70-03 | Client sees available trainer slots for booking | SATISFIED | `GET /slots` (`operation_id="client_list_slots"`) wired; `fetch_available_slots` raw SQL in repository.py filters `status='active'` and `start_time > now()` with optional trainer pin |
| CBOOK-03 | 70-02, 70-03 | Client books slot with active PT-package (idempotent, race-safe) | SATISFIED | `create_booking_for_client` + `verify_client_idempotency` + `uq_bookings_slot_confirmed` partial-UNIQUE; race test asserts `[201, 409]` |
| CBOOK-04 | 70-02, 70-03 | No active PT-package → 422 directing to Plans/Checkout | SATISFIED | `NoActivePtPackageError` 422 mapping at service layer; test asserts HTTP 422 `no_active_pt_package` |
| CBOOK-05 | 70-02, 70-03 | Client cancels own booking within cancel window | SATISFIED | `cancel_booking_for_client` enforces `CANCEL_WINDOW_HOURS_CLIENT` against `slot.start_time`; IDOR 404-collapse for non-owned; slot restored via Protocol slot; no credit mutation |
| CCHK-01 | 70-01, 70-04 | Client receives short-lived signed QR token (~60s TTL) | SATISFIED | `encode_qr_token` with `qr_token_ttl_seconds=60`; `GET /client/qr-token` behind `require_client()` |
| CCHK-02 | 70-01, 70-04 | QR check-in creates visit via anti-fraud path; `visits.channel='client_qr'`; Alembic applied | SATISFIED | `create_visit_client_qr` → `_create_visit_with_anti_fraud(..., channel="client_qr")`; migration 0045 present with correct DDL |
| CCHK-03 | 70-01, 70-04 | QR cannot be replayed; cannot check in different client | SATISFIED | `decode_qr_token` rejects expired tokens; `ClientCheckInRequest` has no `client_id`; `client_id` strictly from `sub`; 6 security tests in `test_qr_checkin.py` |

**All 8 requirement IDs from PLAN frontmatter accounted for and SATISFIED.**

---

### Anti-Patterns Found

| File | Line | Pattern | Severity | Impact |
|------|------|---------|----------|--------|
| — | — | No `TBD`, `FIXME`, or `XXX` markers found in any modified file | — | — |
| — | — | No stub `return []` / `return {}` / `return null` in service or router implementations | — | — |
| — | — | No hardcoded empty props or data at render/response callsites | — | — |

**No blocking anti-patterns found.**

#### Code Review Follow-ups (non-blockers, per 70-REVIEW-FIX.md)

These were fixed (CR-01, CR-03, WR-01, WR-02) or explicitly accepted as design (CR-02, IN-01, IN-02):

- **CR-02 (deferred):** Shared rate-limit bucket `"unknown"` when `request.client` is `None` behind some reverse proxies. Acceptable-by-design for current deployment; earmarked for `/gsd:secure-phase`.
- **IN-01 (deferred):** `check_in_via_qr` does not validate client still exists in DB post-decode. Acceptable given 60s TTL and D-70-09; soft-deleted client FK row still physically present.
- **IN-02 (deferred):** `client_cancel_booking` endpoint has no Idempotency-Key. By design (D-70-02); FSM guard provides functional safety; PWA must handle 409 `invalid_transition` as implicit success on duplicate cancel.

None of these break any ROADMAP success criterion.

---

### Human Verification Required

### 1. Full Test Suite Pass

**Test:** Run `cd apps/backend && uv run pytest tests/integration/client_portal/ tests/integration/bookings/ tests/unit/core/test_qr_token.py -q` against a live Postgres + Redis stack.
**Expected:** 51+ client_portal tests pass (including 6 `test_qr_checkin.py`, 5 `test_qr_token_issue.py`, 6 `test_client_booking.py`, 1 `test_client_booking_race.py`, 3 `test_client_booking_idor.py`); 90 bookings tests unchanged; 7 QR unit tests pass. No regressions in the broader 2347+ suite.
**Why human:** Requires live Postgres + Redis stack; cannot run in static analysis.

### 2. Alembic Migration 0045 Applied

**Test:** Run `cd apps/backend && uv run alembic upgrade head` then inspect `visits.channel` CHECK constraint; then run `uv run alembic downgrade -1 && uv run alembic upgrade head`.
**Expected:** Upgrade exits 0; `visits.channel` CHECK accepts `'client_qr'`; round-trip exits 0 with no error.
**Why human:** Requires live Postgres; migration DDL correctness verified by code review but execution cannot be confirmed without a running DB.

---

### Gaps Summary

No gaps found. All 5 ROADMAP success criteria are verified at the artifact, substantive, and wiring levels. All 8 requirement IDs (CBOOK-01..05, CCHK-01..03) are satisfied by concrete code. No debt markers (`TBD`, `FIXME`, `XXX`) in modified files. All 4 code-review findings (CR-01, CR-03, WR-01, WR-02) were fixed; 3 deferred items (CR-02, IN-01, IN-02) are acceptable-by-design and do not compromise any success criterion.

Status is `human_needed` (not `passed`) because two items require a live stack: the full test suite execution and the Alembic migration round-trip.

---

_Verified: 2026-05-30T14:00:00Z_
_Verifier: Claude (gsd-verifier)_

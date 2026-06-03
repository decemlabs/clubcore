---
phase: 80-booking-reschedule
verified: 2026-06-03T17:04:42Z
status: human_needed
score: 4/4
overrides_applied: 0
human_verification:
  - test: "Open BookingManageSheet in the PWA on a device/emulator connected to the real backend. Navigate to the reschedule view on a confirmed booking and verify that the available-slot list populates with real slots from the same trainer (not static mock data)."
    expected: "Flat list of slots from the same trainer appears, labelled with Europe/Moscow times. If no slots are available, the empty state 'Нет доступных слотов' appears."
    why_human: "useClientAvailableSlots calls a live API; jsdom tests stub the hook. The real backend + DB must be running with migration 0053 applied to confirm end-to-end data flow."
  - test: "Complete a reschedule in the PWA (select a slot, tap 'Перенести запись'). Verify the done-reschedule confirmation screen shows the correct new slot time, and that the client's Telegram account receives the reschedule DM."
    expected: "Done screen shows the new slot time. Telegram DM body matches: 'Здравствуйте, {client_name}! Ваша запись к тренеру {trainer_name} перенесена. Новое время: {new_slot_start_msk} (МСК). Ждём вас в зале!'"
    why_human: "Actual Telegram DM delivery requires a live Telegram bot token and a real linked client account — cannot verify in automated tests per project OPERATOR-PENDING convention."
---

# Phase 80: Booking Reschedule — Verification Report

**Phase Goal:** Клиент может перенести подтверждённую бронь на другой слот того же тренера.
**Verified:** 2026-06-03T17:04:42Z
**Status:** human_needed
**Re-verification:** No — initial verification

## Goal Achievement

### Observable Truths

| # | Truth | Status | Evidence |
|---|-------|--------|----------|
| 1 | `POST /client/booking/{id}/reschedule` атомарно отменяет старый слот и создаёт новый в одной транзакции; гонка возвращает 409 `slot_already_booked` | VERIFIED | `reschedule_booking_for_client` in `bookings/service.py:1740–1994` — single `session.commit()` at Step 11 (line 1895); race guard via partial UNIQUE `uq_bookings_slot_confirmed` IntegrityError → `SlotAlreadyBookedError`. Tested: `test_reschedule_booking_happy_path` (atomicity) + `test_reschedule_booking_race_slot_already_booked` (race→409). Both PASS. |
| 2 | Перенос невозможен менее 24 часов до начала исходного слота (409 `reschedule_window_expired`); чужая бронь → 404 IDOR anti-oracle | VERIFIED | Window guard at Step 3 (line 1808): `if booking.slot.start_time - now_utc < timedelta(hours=CANCEL_WINDOW_HOURS_CLIENT)`. IDOR collapse at Step 1 (line 1782): `if booking is None or booking.client_id != client_id: raise BookingNotFoundError`. Tested: `test_reschedule_booking_window_expired` (409) + `test_reschedule_booking_idor_404` (404). Both PASS. Cross-trainer guard at Step 5 (line 1821): `if new_slot.trainer_id != booking.slot.trainer_id: raise SlotTrainerMismatchError`. Tested: `test_reschedule_booking_cross_trainer`. PASS. |
| 3 | После переноса в audit_log появляется событие `booking_rescheduled`; клиент получает DM-уведомление с новым временем | VERIFIED | Audit emission at Step 10 (`service.py:1868`): `await audit.emit(session, "booking_rescheduled", ...)` with `BookingRescheduledPayload` registered in `audit_payloads.py:1307`. Event registered in `audit.py:366`. BOOKING_RESCHEDULED_DM template with OWNER-COPY-LOCK signed-off 2026-06-03 in `notifications.py:50–51`. Fire-and-forget post-commit DM (Step 13, lines 1929–1992) wrapped in `except Exception` — no exception escapes after Step 11 commit (CR-01 fix). Tested: `test_reschedule_booking_audit_row` (audit row with old/new linkage PASS), `test_reschedule_booking_dm_sent` (send_text_dm called once with correct text PASS), `test_reschedule_booking_dm_failure_does_not_fail_reschedule` (CR-01 PASS), `test_reschedule_dm_failure_returns_200_and_idempotent_replay` (CR-01+CR-02 PASS). PT credit: `test_reschedule_booking_pt_credit_preserved` asserts sessions_remaining identical before/after. PASS. |
| 4 | `BookingManageSheet` в PWA показывает реальные доступные слоты и выполняет перенос через новый endpoint; mock-календарь удалён | VERIFIED | `BookingManageSheet.jsx` imports `useClientAvailableSlots, useRescheduleBooking` from `@/data`; no CALENDAR/TIME_SLOTS/BUSY_SLOTS import. `useRescheduleBooking` in `clientQueries.ts:497–525` calls `POST /api/v1/client/booking/{booking_id}/reschedule` with Idempotency-Key; `onSettled` invalidates `bookings()` + `availableSlots()` cache keys. Trainer filter normalised to `b.trainerName ?? b.trainer` (WR-06 fix). 7/7 reschedule vitest tests PASS. |

**Score:** 4/4 truths verified

### Required Artifacts

| Artifact | Expected | Status | Details |
|----------|----------|--------|---------|
| `apps/backend/alembic/versions/0053_booking_notifications_widen_kind.py` | Widens `booking_notifications.kind` CHECK for 'rescheduled' | VERIFIED | DROP+RECREATE CHECK with 5 kinds incl. 'rescheduled'; chains from 0052; no-op alter_column (IN-02 — accepted) |
| `apps/backend/app/modules/bookings/service.py` | `reschedule_booking_for_client` 15-step atomic UoW | VERIFIED | 254 lines of substantive implementation; all guards present; fire-and-forget DM envelope post-commit |
| `apps/backend/app/modules/bookings/notifications.py` | `BOOKING_RESCHEDULED_DM` + `render_booking_rescheduled_dm` | VERIFIED | OWNER-COPY-LOCK signed-off 2026-06-03 (WR-04 fix) |
| `apps/backend/app/core/audit_payloads.py` | `BookingRescheduledPayload` + registry entry | VERIFIED | Payload at line 494; registry mapping at line 1307 |
| `apps/backend/app/core/dependencies.py` | `BookingForClientRescheduler` Protocol slot | VERIFIED | Type alias + setter + accessor at lines 1711–1758 |
| `apps/backend/app/main.py` | Protocol slot wired at startup | VERIFIED | `register_booking_for_client_rescheduler(bookings_service.reschedule_booking_for_client)` at line 609 |
| `apps/backend/app/modules/client_portal/router.py` | `POST /booking/{booking_id}/reschedule` endpoint | VERIFIED | RBAC-04 ordering: `require_client()` → `verify_client_csrf` → `verify_client_idempotency`; session_factory passed for fresh-session evidence INSERT |
| `apps/backend/app/modules/client_portal/service.py` | `reschedule_client_booking` delegate | VERIFIED | Calls `reschedule_booking_for_client` Protocol accessor; passes `session_factory` |
| `apps/backend/app/modules/client_portal/schemas.py` | `ClientRescheduleBookingRequest(BackendSchemaBase)` | VERIFIED | `extra='forbid'` via `BackendSchemaBase`; only `new_slot_id: UUID` field — no `client_id` (IDOR-safe) |
| `apps/backend/tests/integration/bookings/test_reschedule_booking_for_client.py` | 10 service-layer integration tests | VERIFIED | 10 tests (9 original + 1 CR-01 DM-failure): all PASS in 2.98s |
| `apps/backend/tests/integration/client_portal/test_client_reschedule.py` | CR-01+CR-02 HTTP-layer integration test | VERIFIED | 1 test confirming post-commit DM failure → 200 + idempotency replay → same 200: PASS |
| `apps/client-pwa/src/lib/clientQueries.ts` | `useRescheduleBooking` mutation hook | VERIFIED | POST to correct endpoint; Idempotency-Key header; `onSettled` invalidates bookings + availableSlots |
| `apps/client-pwa/src/data/index.js` | `useRescheduleBooking` re-export | VERIFIED | Exported alongside `useCancelBooking` |
| `apps/client-pwa/src/screens/sheets/BookingManageSheet.jsx` | Real-slot reschedule UI; mock calendar removed | VERIFIED | `useClientAvailableSlots` + `useRescheduleBooking` wired; trainer filter normalised; no CALENDAR/TIME_SLOTS/BUSY_SLOTS import |
| `apps/client-pwa/src/screens/sheets/BookingManageSheet.reschedule.test.jsx` | 7 PWA reschedule vitest tests | VERIFIED | All 7 PASS including WR-06 trainer normalisation test |

### Key Link Verification

| From | To | Via | Status | Details |
|------|----|-----|--------|---------|
| `client_portal/router.py` | `client_portal/service.py` | `service.reschedule_client_booking(...)` | WIRED | Router calls delegate at line 488 |
| `client_portal/service.py` | `bookings/service.py` | `reschedule_booking_for_client` Protocol slot (dependencies.py accessor) | WIRED | Accessor imported at line 46; called at line 537 |
| `bookings/service.py` | DB commit | single `await session.commit()` at Step 11 | WIRED | Line 1895; one commit; SVC001 caller-owns-txn pattern |
| `bookings/service.py` | `audit_log` | `audit.emit(session, "booking_rescheduled", ...)` | WIRED | Step 10 (line 1868); payload serialised by `BookingRescheduledPayload` |
| `bookings/service.py` | Telegram DM | `telegram_sender.send_text_dm` post-commit in fire-and-forget envelope | WIRED | Lines 1960 + `except Exception` envelope at 1984 |
| `bookings/service.py` | `booking_notifications` evidence row | `_write_reschedule_evidence` with fresh session (session_factory) | WIRED | Lines 1970–1974; fresh session when session_factory supplied (CR-01/WR-02 fix) |
| `BookingManageSheet.jsx` | `POST /api/v1/client/booking/{id}/reschedule` | `useRescheduleBooking().mutateAsync(...)` | WIRED | Lines 317–321 in component; `clientQueries.ts:509–517` |
| `BookingManageSheet.jsx` | real slot list | `useClientAvailableSlots()` filtered by `b.trainerName ?? b.trainer` | WIRED | Lines 16 + 33–40; candidateSlots memo |

### Data-Flow Trace (Level 4)

| Artifact | Data Variable | Source | Produces Real Data | Status |
|----------|---------------|--------|--------------------|--------|
| `BookingManageSheet.jsx` reschedule view | `slotsPage` / `candidateSlots` | `useClientAvailableSlots()` → `GET /api/v1/client/slots` (real DB query in backend) | Yes — real API endpoint backed by DB | FLOWING |
| `BookingManageSheet.jsx` done-reschedule state | `selectedSlot.startTime` | Set from real slot item selected by user; slot data flows from `useClientAvailableSlots` | Yes | FLOWING |

### Behavioral Spot-Checks

| Behavior | Command | Result | Status |
|----------|---------|--------|--------|
| All 10 service-layer reschedule tests | `uv run pytest tests/integration/bookings/test_reschedule_booking_for_client.py tests/integration/client_portal/test_client_reschedule.py -q` | 11 passed in 2.98s | PASS |
| All 7 PWA reschedule vitest tests | `pnpm --filter client-pwa test` (BookingManageSheet.reschedule.test.jsx) | 7 passed | PASS |
| All 5 PWA cancel tests (regression) | `pnpm --filter client-pwa test` (BookingManageSheet.cancel.test.jsx) | 5 passed | PASS |

### Probe Execution

Step 7c: SKIPPED — no `scripts/*/tests/probe-*.sh` files declared or present for Phase 80. Phase 80 is a feature slice, not a migration/tooling phase with separate probe scripts.

### Requirements Coverage

| Requirement | Source Plan | Description | Status | Evidence |
|-------------|------------|-------------|--------|----------|
| RESCH-01 | 80-02 | Atomic cancel+create endpoint with window/IDOR/cross-trainer guards | SATISFIED | `reschedule_booking_for_client` + router endpoint + 9 service tests |
| RESCH-02 | 80-01 | `booking_rescheduled` audit event + DM template | SATISFIED | `audit.py:366` + `audit_payloads.py:494,1307` + `notifications.py:50` + DM test |
| RESCH-03 | 80-03 | BookingManageSheet wired to real slots + reschedule endpoint; mock calendar removed | SATISFIED | `BookingManageSheet.jsx` — no mock imports; 7 vitest tests PASS |

### Anti-Patterns Found

| File | Line | Pattern | Severity | Impact |
|------|------|---------|----------|--------|
| `bookings/service.py` | 1721 | Fallback path reuses request session for evidence INSERT when `session_factory is None` | Info | Documented in code comment; safe because the whole block is best-effort; only applies to tests that don't supply session_factory (correct) |
| `bookings/service.py` | 1934 | Telegram-unlinked clients receive no reschedule notification (WR-05) | Info | Deliberate and documented at call site with explicit note about deferred email-fallback extension; not a stub |
| `data/index.js` | 57 | `CALENDAR, TIME_SLOTS, BUSY_SLOTS` still exported from the data barrel | Info | These constants remain in `calendar.js` (used by other screens). `BookingManageSheet.jsx` no longer imports them — the phase goal "mock calendar removed" refers to the sheet itself, which is clean. The barrel still exports them for other consumers. Not a blocker. |

No TBD/FIXME/XXX debt markers found in any Phase 80 modified files.

### Human Verification Required

#### 1. Live Slot List Population in PWA

**Test:** Log in to the client PWA with a real client account on a device/emulator connected to the backend (migration 0053 applied). Navigate to a confirmed booking in BookingManageSheet and tap "Перенести". Verify the available-slot list populates with real data from the same trainer.
**Expected:** A flat list of available slots for the same trainer appears, labelled with Europe/Moscow times. If no active slots exist for that trainer, the empty state "Нет доступных слотов" appears (not a crash or spinner).
**Why human:** `useClientAvailableSlots` calls a live API; jsdom tests stub the hook. End-to-end data flow requires a running backend with migration 0053 applied and actual slot data seeded.

#### 2. Telegram DM Delivery

**Test:** Complete a reschedule via the PWA with a Telegram-linked test client. Verify the client's Telegram account receives the reschedule DM with the correct new slot time in Moscow timezone.
**Expected:** DM text: "Здравствуйте, {client_name}! Ваша запись к тренеру {trainer_name} перенесена. Новое время: DD.MM.YYYY HH:MM (МСК). Ждём вас в зале!"
**Why human:** Actual Telegram DM delivery requires a live bot token configured against a real Telegram account. The code path (send_text_dm called with correct text) is fully proven by `test_reschedule_booking_dm_sent` using a stub — only the final network delivery requires human confirmation, consistent with the project OPERATOR-PENDING convention.

### Gaps Summary

No gaps. All four success criteria are verified at the code level. Two items requiring live infrastructure confirmation are routed to human verification per the OPERATOR-PENDING convention.

**Code Review Fixes (REVIEW.md blockers):**

- **CR-01 RESOLVED:** Post-commit DM block wrapped in `except Exception` (lines 1984–1992); `_write_reschedule_evidence` uses a fresh session when `session_factory` is supplied. Regression test: `test_reschedule_booking_dm_failure_does_not_fail_reschedule` PASS + `test_reschedule_dm_failure_returns_200_and_idempotent_replay` PASS.
- **CR-02 RESOLVED:** Response is built from the Step-12 reload BEFORE the post-commit DM block (line 1913); `idempotent_execute` always observes a clean return. Idempotency replay regression: `test_reschedule_dm_failure_returns_200_and_idempotent_replay` asserts r2.json()["data"] == body1 (byte-identical). PASS.

**Code Review Warnings addressed in code:**

- WR-01 (same-slot returns misleading error): Fixed — Step 2b short-circuits to idempotent no-op when `new_slot_id == booking.slot_id` (lines 1799–1803).
- WR-02 (DB connection held across Telegram I/O): Fixed — evidence INSERT uses fresh session via `session_factory` (CR-01 fix encompasses WR-02).
- WR-03 (redundant double reload): Fixed — Step 12 `_load_booking_with_relationships` is reused for both response projection and DM; Step 15 reload removed.
- WR-04 (OWNER-COPY-LOCK unsigned): Fixed — signed-off 2026-06-03 in notifications.py:51.
- WR-05 (no email fallback for unlinked clients): Documented at call site as deliberate; email-fallback extension deferred to a later phase.
- WR-06 (trainer filter keyed on absent field): Fixed — `bookingTrainer = b.trainerName ?? b.trainer`; regression test `renders same-trainer slots when the booking carries only 'trainer'` PASS.

---

_Verified: 2026-06-03T17:04:42Z_
_Verifier: Claude (gsd-verifier)_

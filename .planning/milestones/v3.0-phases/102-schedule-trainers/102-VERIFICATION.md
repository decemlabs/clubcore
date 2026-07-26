---
phase: 102-schedule-trainers
verified: 2026-06-13T18:30:00Z
status: human_needed
score: 12/12 must-haves verified
overrides_applied: 0
# Narrowed by the 2026-07-26 cross-phase UAT audit (quick 260726-hou).
# The P102 set was `data-setup-blocked` at v3.0 close, then largely CLOSED by
# v3.1 Phase 110 ("Live Verification — Deferred P102") against a live uvicorn on
# real seeded Postgres — see 110-VERIFICATION.md (status passed, live_http_smoke
# executed: revenue=150000k, sessions=2, accrual=115000k, status=paid):
#   - booking lifecycle create → cancel → complete-via-pt-session  → CLOSED
#   - slot-already-booked race surfaces a clean 409, not a crash    → CLOSED
#   - payroll config → preview → run → pending→paid kopecks math    → CLOSED (item 4)
#   - reception gated 403 on all 4 owner-only payroll endpoints      → CLOSED (item 5)
#   - repeatable seed path (seed_p102_walkthrough.py + verify/p102_walkthrough.sh)
# What Phase 110 did NOT cover is the BROWSER layer — it verified over HTTP and
# pytest, not through the admin UI. The remaining open items are exactly those UI
# legs (items 1–3 below); items 4–5 are retained for history only.
p102_api_legs_closed_by: 110-VERIFICATION.md (v3.1 Phase 110 — live HTTP smoke, 4/4 must-haves)
human_verification:
  - test: "Open the Schedule page as owner, publish a trainer slot, then attempt to create a time-off that overlaps a booked slot; confirm the force-override modal appears with conflict counts and the danger button triggers with force=true"
    expected: "Slot is published; time-off 409 conflict shows the conflict Callout + force button; forcing creates the time-off and cancels the conflicting booking server-side"
    why_human: "Requires a running backend + docker stack; race-condition flow cannot be verified by static analysis or unit tests alone"
  - test: "Click an available slot on the calendar as reception staff; book a client + PT-package; verify the calendar refreshes and the slot shows as 'booked'"
    expected: "Booking is created; slot type flips to 'booked' without page crash; BookingDetailModal shows the booking with cancel/complete affordances"
    why_human: "Requires live backend for the full create-booking → calendar-refresh round-trip"
  - test: "As reception, attempt to cancel a booking within 24h of the slot start time"
    expected: "Cancel button is hidden (UI ≤24h gate) or backend returns 409 cancel_window_expired with the friendly toast; modal closes calmly, no crash"
    why_human: "24h window evaluation depends on real slot timestamps and live backend enforcement"
  - test: "As owner, open Trainer detail → Payouts tab; configure comp-config, run a preview, then run an accrual; verify amounts displayed in rubles and percent match what was entered"
    expected: "Config PUT sends integer kopecks/bps; preview shows correct rubles/kopecks display; accrual run returns totalKopecks formatted via formatMoney"
    why_human: "Money conversion round-trip (kopecks÷100↔rubles, bps÷100↔percent) requires a backend storing and returning the values to confirm no float drift"
  - test: "Open Trainer detail → Payouts tab as reception; verify no payroll API calls are made"
    expected: "Lock EmptyState shown; browser DevTools Network shows zero /api/v1/payroll/* requests"
    why_human: "The 'zero API calls' invariant is tested by unit tests, but the visual Lock EmptyState in a real browser confirms the gate is wired correctly end-to-end"
---

# Phase 102: Schedule + Trainers Verification Report

**Phase Goal:** Staff can manage trainer availability and PT bookings, and owner can configure trainer payroll — all on real backend data.
**Verified:** 2026-06-13T18:30:00Z
**Status:** human_needed
**Re-verification:** No — initial verification

---

## Goal Achievement

### Observable Truths

| # | Truth | Status | Evidence |
|---|-------|--------|----------|
| 1 | Owner publishes a trainer slot from ScheduleManagementModal on real /trainer-slots | VERIFIED | `features/schedule/api.ts` line 104: `staffRequest('post', '/api/v1/trainer-slots', ...)` with `Idempotency-Key: crypto.randomUUID()` INSIDE mutationFn; ScheduleManagementModal.tsx imports and calls `usePublishSlot` |
| 2 | Owner creates recurring template and time-off block on real backend data | VERIFIED | `api.ts` exports `useCreateTemplate` (POST /api/v1/recurring-templates) and `useCreateTimeOff` (POST /api/v1/time-off); ScheduleManagementModal.tsx lines 210, 341 call them |
| 3 | Time-off 409 time_off_booked_conflict transitions modal to force-override confirm (modal stays open) | VERIFIED | ScheduleManagementModal.tsx lines 350, 379: catches `err.code === 'time_off_booked_conflict'`, stores conflict data in state, renders conflict Callout + danger «Заблокировать принудительно» button; modal stays open (no onOpenChange(false) called on 409) |
| 4 | All schedule mutations carry a fresh per-attempt Idempotency-Key | VERIFIED | Every mutation in `features/schedule/api.ts` calls `crypto.randomUUID()` inside its `mutationFn` body, not at hook init time; comment: "crypto.randomUUID() called at submit time — fresh key per attempt (T-102-IDEM)" |
| 5 | Reception cannot reach the management modal (FAB hidden by can()) | VERIFIED | ScheduleManagementModal.tsx line 547: `if (!can(role, 'create', 'schedule-slots')) return null`; SchedulePage.tsx line 294/328: FAB wrapped in `can(role,'create','schedule-slots')` |
| 6 | Calendar merges real /trainer-slots + /bookings over the visible-week window | VERIFIED | SchedulePage.tsx lines 206–222: `useTrainerSlots` + `useBookingsByWeek` called in parallel; `mergeSlotBookings(slots, bookings, trainerColorMap, trainerNameMap, weekStart)` produces `CalendarEvent[]` with type discriminator (available/booked/cancelled/time-off) |
| 7 | Race 409 slot_already_booked surfaces calm «слот занят» inline state + calendar refetch — never a crash | VERIFIED | BookingModal.tsx lines 123–129: catches `slot_already_booked`, renders inline Callout, calls `qc.invalidateQueries({ queryKey: scheduleKeys.all })`; modal stays open; bookings/api.test.tsx verifies no toast fired for this code |
| 8 | Staff cancels a booking (reception ≤24h window / owner anytime); complete records a PT-session | VERIFIED | BookingDetailModal.tsx: `useCancelBooking` + `useCompleteBooking` wired; cancel 24h-window guard in footer logic; `useCompleteBooking` in bookings/api.ts line 220: `staffRequest('post', '/api/v1/pt-sessions', ...)` with `{ptPackageId, trainerId, performedAt, bookingId}` — no clientId |
| 9 | Trainers Roster lists real /trainers data (fullName, specialization, isActive, photoUrl) | VERIFIED | TrainersPage.tsx line 49: `useTrainers({ active: true })`; TrainerHero.tsx renders real `fullName`, `specialization`, `photoUrl` (fallback initials), `isActive` badge; Load/Requests/Earnings removed |
| 10 | Owner can create + edit + delete trainers; reception sees no CRUD affordances | VERIFIED | TrainersPage.tsx lines 76–82, 106, 132: `can(role,'create'/'edit'/'delete','trainers')` gates; TrainerFormModal.tsx imports `useCreateTrainer`, `useUpdateTrainer`; 409 `phone_exists` → inline Callout (not toasted), `trainer_in_use` → friendly toast |
| 11 | Owner views trainer payroll: comp-config, preview→run, accruals list, pending→paid | VERIFIED | `features/payroll/api.ts`: `usePayrollConfig`, `useAccrualPreview`, `useRunAccrual`, `useAccruals`, `useMarkAccrualPaid` all wired; PayoutsTab.tsx line 60–64: `can(role,'view','payroll')` Lock gate before any hook fires |
| 12 | Reception is 403-gated on PayoutsTab with zero payroll API calls | VERIFIED | PayoutsTab.tsx line 60: early return to Lock EmptyState BEFORE `OwnerPayoutsTab` sub-component mounts; all payroll hooks have `enabled: !!trainerId && can(role,'view','payroll')`; PayoutsTab.test.tsx asserts `staffRequest` never called for reception |

**Score:** 12/12 truths verified

---

### Required Artifacts

| Artifact | Expected | Status | Details |
|----------|----------|--------|---------|
| `apps/admin-app/src/features/schedule/schemas.ts` | Zod wire schemas + mutation input schemas | VERIFIED | Contains `TrainerSlotSchema`, `PublishSlotSchema`, `CreateTemplateSchema`, `CreateTimeOffSchema`, etc. |
| `apps/admin-app/src/features/schedule/api.ts` | useTrainerSlots + all mutations | VERIFIED | Contains `usePublishSlot`, `useCreateTemplate`, `useCreateTimeOff`, `useCancelSlot`, `useDeactivateTemplate`, `useDeleteTimeOff`; mock replaced |
| `apps/admin-app/src/features/schedule/keys.ts` | scheduleKeys query-key factory | VERIFIED | Exports `scheduleKeys` with `all`, `slots()`, `week(params)`, `templates()`, `timeOff()` |
| `apps/admin-app/src/components/modals/ScheduleManagementModal.tsx` | Owner-only 3-tab modal + force-override | VERIFIED | 547-line file; three ChipGroup tabs; `can(role,'create','schedule-slots')` early-return guard; conflict state handling |
| `apps/admin-app/src/features/trainers/schemas.ts` | TrainerSchema + input schemas | VERIFIED | Contains `TrainerSchema`, `TrainersListResponseSchema`, `TrainerUpdateSchema`, `TrainerCreateSchema` |
| `apps/admin-app/src/features/trainers/api.ts` | useTrainers/useTrainer + CRUD mutations (http) | VERIFIED | Contains `useUpdateTrainer`, `useCreateTrainer`, `useDeleteTrainer`, `useTrainers`, `useTrainer`; mock replaced |
| `apps/admin-app/src/pages/trainers/TrainersPage.tsx` | Roster on real data; Load/Requests/Earnings removed | VERIFIED | `useTrainers({ active: true })`; comment confirms Load/Requests/Earnings removed; owner CRUD affordances gated by `can()` |
| `apps/admin-app/src/features/bookings/api.ts` | useBookingsByWeek/useBookingsByTrainer + create/cancel/complete | VERIFIED | Contains `useCreateBooking` (POST /api/v1/bookings), `useCompleteBooking` (POST /api/v1/pt-sessions with bookingId) |
| `apps/admin-app/src/components/modals/BookingModal.tsx` | Race-safe booking create with 409 handling | VERIFIED | Catches `slot_already_booked`/`slot_not_available`, renders inline Callout, invalidates scheduleKeys |
| `apps/admin-app/src/components/modals/BookingDetailModal.tsx` | Booking detail + cancel + complete | VERIFIED | 197 lines; `useCancelBooking` + `useCompleteBooking` wired; 24h-window footer logic |
| `apps/admin-app/src/pages/schedule/SchedulePage.tsx` | Calendar merge + FAB + slot routing | VERIFIED | `useTrainerSlots` + `useBookingsByWeek` in parallel; `mergeSlotBookings`; owner FAB; slot-click routing |
| `apps/admin-app/src/features/payroll/schemas.ts` | PayrollConfigSchema + input schemas | VERIFIED | `PayrollConfigSchema` with integer `commissionPctBps` (0-10000) and `sessionFeeKopecks` (≥0); Russian validation messages |
| `apps/admin-app/src/features/payroll/api.ts` | All 6 owner-only enabled-gated hooks | VERIFIED | `usePayrollConfig`, `useSetPayrollConfig`, `useAccrualPreview`, `useRunAccrual`, `useAccruals`, `useMarkAccrualPaid` |
| `apps/admin-app/src/pages/trainer/components/PayoutsTab.tsx` | Wired comp-config editor + preview→run + accruals + mark-paid | VERIFIED | Reception Lock gate before hooks; comp-config StatRows; preview→run panel; accruals list with status badges; mark-paid ConfirmModal |

---

### Key Link Verification

| From | To | Via | Status | Details |
|------|-----|-----|--------|---------|
| `features/schedule/api.ts` | `/api/v1/trainer-slots` | `staffRequest('post', '/api/v1/trainer-slots', ...)` with Idempotency-Key | WIRED | Line 104: exact match of required pattern; crypto.randomUUID() inside mutationFn |
| `ScheduleManagementModal.tsx` | `features/schedule/api` | `useCreateTimeOff` import and call | WIRED | Line 34: `import { usePublishSlot, useCreateTemplate, useCreateTimeOff, ApiError } from '@/features/schedule/api'`; called at lines 106, 210, 341 |
| `features/trainers/api.ts` | `/api/v1/trainers` | `staffRequest('patch', '/api/v1/trainers/{trainer_id}', ...)` | WIRED | Line 105: PATCH call confirmed; no Idempotency-Key (correct — not required by contract) |
| `TrainerFormModal.tsx` | `features/trainers/api` | `useUpdateTrainer` / `useCreateTrainer` | WIRED | Line 34: import; lines 126-127: hooks called |
| `features/bookings/api.ts` | `/api/v1/bookings` | `staffRequest('post', '/api/v1/bookings', ...)` with Idempotency-Key | WIRED | Line 128-130: POST with `Idempotency-Key: crypto.randomUUID()` inside mutationFn |
| `features/bookings/api.ts` | `/api/v1/pt-sessions` | complete records a session linked by bookingId | WIRED | Line 220: `staffRequest('post', '/api/v1/pt-sessions', ...)` |
| `SchedulePage.tsx` | `features/schedule/api + features/bookings/api` | `useTrainerSlots + useBookingsByWeek` merged | WIRED | Lines 36-37: both imported; lines 206-222: parallel queries + merge |
| `features/payroll/api.ts` | `/api/v1/payroll/trainer-configs/{trainer_id}` | `staffRequest('put', '/api/v1/payroll/trainer-configs/{trainer_id}', ...)` | WIRED | Lines 37/49/133: GET and PUT calls confirmed |
| `PayoutsTab.tsx` | `features/payroll/api` | `usePayrollConfig/useAccrualPreview/useRunAccrual/useAccruals/useMarkAccrualPaid` | WIRED | Line 27-32: all 6 hooks imported; line 86: `usePayrollConfig(trainerId)` called; line 116: `useMarkAccrualPaid()` called |

---

### Data-Flow Trace (Level 4)

| Artifact | Data Variable | Source | Produces Real Data | Status |
|----------|---------------|--------|-------------------|--------|
| `SchedulePage.tsx` | `slotsQuery.data`, `bookingsQuery.data` | `useTrainerSlots` → `staffRequest('get', '/api/v1/trainer-slots', ...)`, `useBookingsByWeek` → `staffRequest('get', '/api/v1/bookings', ...)` | Yes — HTTP GET calls to real backend endpoints | FLOWING |
| `TrainersPage.tsx` | `data` (from `useTrainers`) | `useTrainers({ active: true })` → `staffRequest('get', '/api/v1/trainers', ...)` → `TrainersListResponseSchema.parse(raw).data` | Yes — HTTP GET; real paginated response parsed | FLOWING |
| `TrainerHero.tsx` | `t` (TrainerData prop) | `useTrainer(id)` in TrainerPage → `staffRequest('get', '/api/v1/trainers/{trainer_id}', ...)` | Yes — HTTP GET; `fullName/specialization/photoUrl/isActive/bio` from real response | FLOWING |
| `PayoutsTab.tsx` | `configQuery.data`, `accrualsQuery.data` | `usePayrollConfig(trainerId)` + `useAccruals(trainerId)` → real `/api/v1/payroll/*` GET calls; `enabled` gated | Yes — enabled-gated real HTTP calls; 404 comp_config_missing handled as expected state | FLOWING |
| `OverviewTab.tsx` | `bookingsQuery.data` | `useBookingsByTrainer(trainerId, todayRange, 'confirmed')` → `staffRequest('get', '/api/v1/bookings', ...)` | Yes — HTTP GET with trainerId+fromTime+toTime+status=confirmed | FLOWING |

---

### Behavioral Spot-Checks

| Behavior | Command | Result | Status |
|----------|---------|--------|--------|
| Admin-app typecheck passes | `pnpm -F @clubcore/admin-app typecheck` | Exit 0, 0 errors | PASS |
| Admin-app lint passes | `pnpm -F @clubcore/admin-app lint` | Exit 0, 0 errors, 0 warnings | PASS |
| 274 tests pass | `pnpm -F @clubcore/admin-app test` | 21 test files, 274/274 tests passed | PASS |
| Build produces output | `pnpm -F @clubcore/admin-app build` | Built in 2.61s, dist/ produced | PASS |
| Test files enumerate schedule, bookings, payroll suites | `pnpm -F @clubcore/admin-app test` | schedule/api.test.tsx, bookings/api.test.tsx, payroll/api.test.tsx, BookingModal.test.tsx, ScheduleManagementModal.test.tsx, PayoutsTab.test.tsx all present in 21-file run | PASS |

---

### Requirements Coverage

| Requirement | Source Plan | Description | Status | Evidence |
|-------------|-------------|-------------|--------|----------|
| SCH-01 | 102-01-PLAN | Schedule screen renders real trainer-slots/recurring-templates/time-off; create/edit owner-only | SATISFIED | `features/schedule/api.ts` wires all three endpoints; ScheduleManagementModal provides owner-only write UI; SchedulePage uses real `useTrainerSlots`; calendar merge (plan 03 completes read half) |
| SCH-02 | 102-03-PLAN | Staff books/cancels/completes PT booking against a slot; race-safe conflicts | SATISFIED | `features/bookings/api.ts` wires POST /bookings, POST /bookings/{id}/cancel, POST /pt-sessions with bookingId; BookingModal handles 409 inline; BookingDetailModal handles cancel+complete |
| TRN-01 | 102-02-PLAN | Trainers list + detail render real /trainers (catalog + bio/specialization) | SATISFIED | `features/trainers/api.ts` http layer; TrainersPage uses `useTrainers`; TrainerHero renders real fullName/bio/specialization/photoUrl/isActive |
| TRN-02 | 102-04-PLAN | Trainer payroll wired on trainer detail / finance surface (owner-only) | SATISFIED | `features/payroll/api.ts` hooks; PayoutsTab wired with reception Lock gate; comp-config editor, preview→run, accruals list, mark-paid all implemented |

---

### Anti-Patterns Found

| File | Line | Pattern | Severity | Impact |
|------|------|---------|----------|--------|
| `pages/trainer/TrainerPage.tsx` | ~62 | `// TODO Phase 104: wire history to real endpoint` on HistoryTab | INFO (intentional deferral) | HistoryTab stays on mock data; documented in 102-02-SUMMARY; no backend endpoint exists in Phase 102; does not affect SCH/TRN requirements |
| `pages/trainer/components/TrainerKpis.tsx` | 9-11 | `return null` + `// TODO Phase 104` | INFO (intentional deferral) | No aggregate KPI endpoint in Phase 102; documented in 102-02-SUMMARY; per plan direction |
| `pages/trainer/components/OverviewTab.tsx` | ~36 | Regulars section still on mock `trainerDetail` with `// TODO Phase 104` | INFO (intentional deferral) | No regulars endpoint in Phase 102; Phase 104 owns this; does not affect today-schedule which IS wired |

No `TBD`, `FIXME`, or `XXX` markers found in any phase-modified file. All stubs are intentional with documented phase references (Phase 104), not unauditable debt.

---

### Human Verification Required

The automated gate is fully green (274/274 tests, typecheck clean, lint clean, build clean). The following items require a live backend to confirm the full round-trip:

#### 1. Time-off force-override with live booking conflict

**Test:** As owner, publish a trainer slot, book a client into it, then try to create a time-off block that overlaps it; observe the force-override conflict modal.
**Expected:** 409 response contains `conflictingSlotIds` + `conflictingBookingIds`; conflict Callout shows correct counts; clicking «Заблокировать принудительно» sends `force=true` with a fresh Idempotency-Key; backend cascades the booking cancellation.
**Why human:** Requires a running backend producing the 409 with real conflict ids; cannot be verified by static analysis.

#### 2. Booking create → calendar refresh round-trip

**Test:** Click an available slot on the Schedule calendar as staff, select a client + PT-package, click «Записать»; confirm the slot in the calendar flips to «занято».
**Expected:** Booking created (HTTP 200); calendar auto-refreshes (scheduleKeys invalidation triggers refetch); slot EventBlock shows «занято» badge.
**Why human:** Requires live backend + browser to observe the real-time refetch and badge update.

#### 3. Reception 24h cancel window enforcement

**Test:** Log in as reception and attempt to cancel a booking whose slot starts in less than 24 hours (use or seed a near-future slot).
**Expected:** Cancel button is hidden in BookingDetailModal (≤24h detection from slot startTime vs now); if somehow reached, backend returns 409 cancel_window_expired with the friendly toast; modals close calmly, no crash or blank screen.
**Why human:** Requires real slot timestamps to evaluate the 24h comparison against current time.

#### 4. Payroll comp-config kopecks round-trip

**Test:** As owner, set sessionFeeKopecks via the Payouts tab editor (e.g. enter 500₽), save, then reload the tab; verify the displayed value is 500₽ (not 50000 or 5).
**Expected:** PUT body sends `sessionFeeKopecks: 50000` (Math.round(500 * 100)); GET returns 50000; display shows 500₽ (50000/100).
**Why human:** Float conversion correctness confirmed by unit test (PayoutsTab.test.tsx), but a live round-trip confirms no backend transformation or JSON serialization issue.

#### 5. Reception Payouts tab: visual Lock state + zero network calls

**Test:** Log in as reception, navigate to any trainer detail page, open the Payouts tab; open browser DevTools Network tab first.
**Expected:** Lock EmptyState «Недостаточно прав» is displayed; DevTools shows zero requests to `/api/v1/payroll/*`.
**Why human:** Unit test asserts `staffRequest` not called (via mock), but visual confirmation in a real browser confirms the guard is wired E2E.

---

### Gaps Summary

No gaps found. All 12 must-have truths are VERIFIED. The four intentional stubs (HistoryTab, TrainerKpis, OverviewTab Regulars, SchedulePage mock during plan 01 — subsequently replaced in plan 03) are all documented deferrals to Phase 104 with explicit TODO comments, not unresolved debt.

The full admin-app gate passes: typecheck (0 errors), lint (0 errors/warnings), test (274/274), build (success). No backend or openapi.json/schema.d.ts changes were made (drift gate safe).

Status is `human_needed` because 5 items require a live backend + browser to verify the full round-trip behavior (conflict cascade, calendar refetch, 24h window, money round-trip, reception network gate).

---

_Verified: 2026-06-13T18:30:00Z_
_Verifier: Claude (gsd-verifier)_

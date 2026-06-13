# Phase 102: Schedule + Trainers - Context

**Gathered:** 2026-06-13
**Status:** Ready for planning

<domain>
## Phase Boundary

Wire the admin-app **schedule** (trainer slots + recurring templates + time-off),
**bookings** (PT booking lifecycle), **trainers** (catalog + CRUD), and **payroll**
(owner-only comp-config + accruals) domains from mocks to the real backend over the
P100 transport seam. Staff manage trainer availability and PT bookings; owner
configures trainer payroll — all on real data.

**In scope:** trainer-slots list/publish/cancel + recurring-templates + time-off
(owner-only management, force-override on conflict); booking create/cancel/complete
(race-safe); trainers list/detail read + owner-only edit (create/delete gated);
trainer-detail Payouts tab wired to real payroll (comp-config, preview, accrual run,
mark-paid); Overview schedule-today wired to real bookings; per-domain zod layers.

**Out of scope:** Attendance (visits) check-in screen (Phase 103); Finance/cashbox
(Phase 103); reports incl. trainer Earnings (Phase 104); dashboard/settings (Phase
104); any new backend endpoints (wire-only).
</domain>

<decisions>
## Implementation Decisions

### Schedule (slots / recurring-templates / time-off)
- Wire `/api/v1/trainer-slots` (list reception+owner; publish + cancel OWNER_ONLY),
  `/api/v1/recurring-templates` (list reception+owner; create + deactivate OWNER_ONLY),
  `/api/v1/time-off` (list reception+owner; create + delete OWNER_ONLY).
- The week calendar **merges real slots (availability) + bookings (booked sessions)**
  by time. Query the **visible week's `fromTime`/`toTime`** bounds (not the backend
  14d default).
- **Net-new owner-only management UI** (panel/modal) to publish a slot, create a
  recurring template, and create a time-off block. Time-off create returns `409`
  `time_off_booked_conflict` with `{data:{conflictingSlotIds,conflictingBookingIds}}`
  — offer a `force=true` override with a warning (cascades booking cancellations).
  Reception sees a **read-only** calendar.
- Slot create body: `{trainerId, startTime, endTime}` (D-38-05, 3 fields only);
  409s: `slot_overlap`/`slot_too_close`/`slot_in_past`/`trainer_inactive`. Slot cancel:
  `{cancelReason 1-200}`. All schedule mutations carry an **Idempotency-Key**.

### Bookings lifecycle (book / cancel / complete)
- **Book from the calendar**: click an available slot → booking modal (pick client +
  PT-package). `POST /api/v1/bookings {slotId, clientId, ptPackageId}` + per-attempt
  `crypto.randomUUID()` Idempotency-Key. (reception+owner — NOT owner-only.)
- **Cancel** `POST /bookings/{id}/cancel {reason 1-200}`: surface the **reception
  ≤24h-before-slot window** rule; `409 cancel_window_expired` → clear state; owner
  cancels anytime.
- **Complete**: the planner MUST confirm the completion mechanism — per the v1.5
  pattern, **PT-session recording with `bookingId` atomically completes the booking**
  (there is no obvious `/bookings/{id}/complete`). Locate the pt-sessions POST and wire
  "complete/record session" to it. **If no such endpoint exists, defer "complete" with
  an explicit note** (book + cancel still ship).
- **Race-safe conflict**: `409 slot_already_booked` / `slot_not_available` (also
  `pt_package_not_active`/`exhausted`/`expired_before_slot`) → a clear inline state
  («слот уже занят» etc.) + refetch the calendar. **Never a crash** (criterion 2).

### Trainers catalog & CRUD
- Wire the **Roster** section to real `GET /api/v1/trainers` (reception+owner). **HIDE
  the Load + Requests sections** (no backend). **Defer the Earnings section to Phase
  104** (it maps to the trainer report).
- List + detail are **read** (reception+owner). **Owner-only edit** via
  `PATCH /trainers/{id}` (bio/specialization/photoUrl/isActive/fullName/phone — PATCH
  semantics, omit = no change). Trainer **create** (`POST`, owner-only, 409 phone_exists)
  + **delete** (`DELETE`, owner-only, 409 trainer_in_use) are can()-gated; build the
  forms if the existing modal scaffolding makes it cheap, else stub with a note
  (avoid a hard requirement — like the P101 plans deferral pattern).
- **Trainer detail tabs:** wire **Payouts** (real payroll — see below) and **Overview
  "schedule today"** (real bookings for that trainer). Keep **regulars/History** on
  mock if there's no clean endpoint (note it). Render real `bio`/`specialization`/
  `photoUrl` (criterion 3).

### Payroll (owner-only — all of it)
- Wire the existing **trainer-detail `PayoutsTab`** to `/api/v1/payroll`. Reception is
  **403-gated** on every payroll endpoint → friendly «Недостаточно прав».
- **Comp-config**: owner editor — `PUT /payroll/trainer-configs/{trainerId}`
  `{commissionPctBps 0-10000, sessionFeeKopecks ≥0, effectiveFrom: date}` — **INSERT-only
  versioned** (each save is a new version; never UPDATE). `GET` active config; `404`
  comp_config_missing on GET / `422` comp_config_missing on preview+accrual.
- **Accrual**: **preview → run** flow. `GET /payroll/preview?trainerId&periodStart&periodEnd`
  → `{sessionCount, fixedKopecks, commissionKopecks, totalKopecks}` (zero-persistence);
  then `POST /payroll/accruals {trainerId, periodStart, periodEnd}` (append-only;
  `409 payroll_period_already_run` → clear state). Period picker.
- **Accruals list** `GET /payroll/accruals?trainerId` (paginated, accrued_at DESC,
  pending+paid+clawbacks). **Mark paid** `POST /payroll/accruals/{accrualId}/mark-paid`
  with a confirm; `409 already_paid` (terminal) handled.
- All amounts integer kopecks; format with the existing money helper.

### Claude's Discretion
- New `features/schedule/`, `features/bookings/`, `features/payroll/` layout (api +
  schemas + query-key factories), calendar merge/rendering approach, the management
  panel/modal decomposition, and test organization — following the P100/P101
  `features/{auth,clients,memberships}` exemplars + admin-app conventions.
</decisions>

<code_context>
## Existing Code Insights (verified — wire is camelCase via Pydantic aliases)

### Backend endpoints
- **Slots** `/api/v1/trainer-slots`: GET list (`trainerId?,fromTime?,toTime?,status=active`,
  paginated) reception+owner; POST publish (OWNER_ONLY, Idem); PATCH `/{id}/cancel`
  (OWNER_ONLY, Idem). 409s: slot_overlap/slot_too_close/slot_in_past/trainer_inactive.
- **Recurring templates** `/api/v1/recurring-templates`: GET list; POST create
  (`{trainerId,dayOfWeek 0-6,startTime,endTime,validFrom,validUntil?}`, OWNER_ONLY, Idem);
  POST `/{id}/deactivate` (OWNER_ONLY, Idem).
- **Time-off** `/api/v1/time-off`: GET list; POST create (`{trainerId,blockStart,blockEnd,
  reason?}` + `?force=true`, OWNER_ONLY, Idem; 409 time_off_booked_conflict w/ conflict
  ids in data); DELETE `/{id}` (OWNER_ONLY, Idem).
- **Bookings** `/api/v1/bookings`: POST create (`{slotId,clientId,ptPackageId}`,
  reception+owner, Idem; 409 slot_already_booked/slot_not_available/trainer_mismatch/
  pt_package_*); POST `/{id}/cancel` (`{reason 1-200}`, reception+owner w/ 24h window,
  Idem; 409 cancel_window_expired); GET list (`clientId?,trainerId?,fromTime?,toTime?,
  status?`); GET `/{id}` (BookingDetailResponse: + slot snapshot + ptPackage); GET
  `/api/v1/clients/{client_id}/bookings`. Status: confirmed|cancelled|no_show|completed.
  **Completion endpoint NOT located — planner confirms pt-sessions path.**
- **Trainers** `/api/v1/trainers`: GET list (`active?`, paginated) + GET `/{id}`
  reception+owner; POST create (`{fullName,phone?}`, OWNER_ONLY, 409 phone_exists);
  PATCH `/{id}` (`{fullName?,phone?,isActive?,bio?,specialization?,photoUrl?}`, OWNER_ONLY);
  DELETE `/{id}` (OWNER_ONLY, 409 trainer_in_use). Response: id/fullName/phone/isActive/
  bio/specialization/photoUrl/createdAt/updatedAt.
- **Payroll** `/api/v1/payroll` (ALL OWNER_ONLY): PUT `/trainer-configs/{trainerId}`
  (set, INSERT-only) + GET `/trainer-configs/{trainerId}` (active, 404 missing);
  GET `/preview?trainerId&periodStart&periodEnd` (422 if no config); POST `/accruals`
  (`{trainerId,periodStart,periodEnd}`, 409 payroll_period_already_run, 422 no config);
  GET `/accruals?trainerId` (paginated); POST `/accruals/{accrualId}/mark-paid`
  (409 already_paid). Money = integer kopecks.

### admin-app current (files to flip — apps/admin-app/src/)
- `features/schedule/{api.ts,types.ts}` (`useSchedule`, scheduleKeys) + `mocks/schedule.ts`
  (SessionEvent[]); page `pages/schedule/SchedulePage.tsx` (WeekCalendar + ScheduleToolbar
  + FAB). **No slot/booking create UI today — net-new.**
- `features/trainers/{api.ts,types.ts}` (`useTrainers`,`useTrainer`) + `mocks/trainers.ts`
  + `mocks/trainer-detail.ts`; pages `pages/trainers/TrainersPage.tsx` (Roster/Load/
  Earnings/Requests) + `pages/trainer/TrainerPage.tsx` (Overview/Payouts/History tabs;
  `components/PayoutsTab.tsx` is the payroll mock to wire).
- **NEW** `features/bookings/` + `features/payroll/` (+ extend schedule/trainers).
- **Exemplars:** `features/{auth,clients,memberships}/{api.ts,schemas.ts}` (P100/P101) —
  staffRequest + `Schema.parse(raw).data` + query-key factory + can()-gating +
  per-attempt Idempotency-Key via the existing `headers` field; optimistic onMutate
  rollback shape (memberships freeze/unfreeze) if any schedule/booking mutation warrants it.
- can() resources: `schedule-slots` (slot/template/time-off owner-only mutations),
  `bookings` (reception+owner), `trainers` (owner-only CRUD), `payroll`/`compensation`
  (owner-only) — verify exact strings in `src/shared/session/can.ts`.

### admin-web analog
- Only `features/trainers/` is wired in admin-web (hooks/keys/schema) — a porting analog
  for trainers CRUD. **No schedule/bookings/payroll** in admin-web → use P100/P101
  admin-app patterns as the primary exemplar for those.
</code_context>

<specifics>
## Specific Ideas

- Booking "complete" almost certainly happens via PT-session recording (booking_id) —
  confirm the endpoint before wiring; defer with a note if absent.
- TrainersPage Load/Requests have no backend → hidden (not faked), like the P101 clients
  filter reduction. Earnings → Phase 104 (trainer report).
- Race-safe booking conflict must render a calm «слот занят» state + refetch, never crash.
- All money integer kopecks; dates ISO + Europe/Moscow display.
</specifics>

<deferred>
## Deferred Ideas

- Attendance check-in + Finance/cashbox → Phase 103.
- Trainer Earnings section + all reports → Phase 104.
- Trainer create/delete forms — built only if cheap given existing scaffolding; else
  gated + stubbed with a note (follow-up).
- Booking "complete" — deferred ONLY if no PT-session-completion endpoint exists.
- regulars / trainer History tab — stay on mock if no clean endpoint.
</deferred>

# Phase 108: Editable Settings — Backend + Wiring - Context

**Gathered:** 2026-06-14
**Status:** Ready for planning
**Mode:** Smart discuss (autonomous)

<domain>
## Phase Boundary

Owner can edit the single-club operational settings — **gym card**, **working hours / breaks / closures**, **online-booking rules**, and the **client-notification matrix** — and the changes persist and are honored by the schedule, the booking window, the client PWA (via the backend it reads), and the notification dispatcher.

Four feature requirements: CFG-01 (gym card), CFG-02 (hours/breaks/closures), CFG-03 (booking rules), CFG-04 (notification matrix). Plus the cross-cutting RBAC/UI-gating success criterion (CFG-05-equivalent: owner-gated surfaces, reception sees a friendly Lock/403 state, every new endpoint is RBAC byte-parity safe and additive to the staff contract).

**In scope:** new/extended backend persistence + endpoints for CFG-02/03/04, FE wiring for all four stubbed Settings sections, backend enforcement of high-value rules, club-wide notification matrix honored by the dispatcher.

**Out of scope (deferred):** client PWA UI changes (separate repo `clubcore-client-pwa`), per-client notification preferences, no-show-penalty automation mechanism, deferred/queued quiet-hours delivery.
</domain>

<decisions>
## Implementation Decisions

### Scope & Integration Depth
- **Client PWA UI is NOT changed in this phase.** The backend persists + serves booking rules so the PWA *can* honor them; the PWA UI port stays deferred (separate repo). Verify via the booking endpoint/contract returning the rules, not via PWA screens.
- **Enforce high-value rules now:** booking-ahead window, booking cutoff, and holiday/closure dates block bookings; the schedule respects working hours. Softer rules (no-show penalty automation) are persisted but NOT fully enforced this phase (no penalty-charging mechanism built).
- **Notification matrix is club-wide** (a single owner-set matrix), not per-client preferences — consistent with the single-club milestone.
- **Quiet hours suppress** non-critical notifications during the window (no deferred/queued delivery).

### Notification Matrix Details
- Matrix covers the channels the dispatcher actually supports today (in-app + Telegram + email/push) — toggles only gate channels that exist; plan-phase grounds the exact channel list against the dispatcher code.
- All existing notification trigger kinds are owner-toggleable (the 7 booking/payment/autopay kinds found in `notifications/models.py`).
- **Always-on (non-disablable) triggers:** payment/autopay-failure + security notifications cannot be silenced.
- **Sender signature** is appended to outbound text channels (Telegram/email), not to in-app notifications.

### Frontend UX
- Keep the existing **global SaveBar** (dirty count, bottom-right); Save dispatches per-dirty-section mutations (each Settings section maps to its own endpoint).
- Reception (non-owner) sees a **Lock card** ("Доступно только владельцу") — the section stays visible but gated, never crashes.
- Forms use **react-hook-form + Zod** (project standard, matches the already-wired Profile/Security sections).
- **Unsaved-changes guard:** warn on navigate-away when sections are dirty (the existing `markDirty` infra supports it).

### Data & Safety
- **RBAC resource granularity:** gym card stays on `Resource.GYM` (`PUT /gym` already locked); hours/booking/notifications go under a new `Resource.SETTINGS` (edit) added additively to `OWNER_ONLY` on BOTH backend `permissions.py` and frontend `can.ts` (byte-parity test must stay green).
- **Seed sane defaults** in the Alembic migration — the current hardcoded constants (e.g. `CANCEL_WINDOW_HOURS_*`) become the seeded values so the existing single club has working settings on day one.
- **Per-surface LOCKED audit events** (gym / hours / booking / notifications updated), pre-registered before any callsite per INFRA-15.
- **Gym coordinates:** add nullable `latitude` / `longitude` columns to `GymInfo` (additive migration).

### Claude's Discretion
- Backend data-model shape (JSONB on the gym/settings singleton vs normalized child tables) is left to plan-phase per STATE.md's investigation flag. Reuse the v2.4 `gym` singleton pattern + existing JSONB `hours` array where it fits; keep minimal + single-club.
- Exact endpoint paths/verbs (PATCH vs PUT, nesting under `/gym` vs new `/settings/*` routes) at plan-phase discretion, as long as they're additive to the contract and RBAC-gated.
- Default seed values and the precise channel list grounded against dispatcher code during plan-phase research.
</decisions>

<code_context>
## Existing Code Insights

### Reusable Assets
- **Gym module (CFG-01 backend done):** `app/modules/gym/router.py:59-80` (`PUT /gym`, RBAC `require_permission(Action.EDIT, Resource.GYM)` + `verify_csrf`), `models.py:20-60` (`GymInfo` singleton, pk `00000000-...0001`; fields name/address/tagline/city/metro/phone/email + JSONB `hours`/`amenities`/`rules`/`social`), `schemas.py:29-76` (`GymInfoResponse` + `GymInfoUpdateRequest`, `extra='forbid'`). FE `can.ts:78` already has `{action:'edit', resource:'gym'}`.
- **RBAC infra:** `app/core/permissions.py` (`Role`/`Action`/`Resource` enums, `OWNER_ONLY` frozenset 41 tuples, `can()`); byte-parity test `test_rbac_parity()` asserts backend `OWNER_ONLY` ⊆ frontend `apps/admin-app/src/shared/session/can.ts` `OWNER_ONLY`.
- **Notification service:** `app/modules/notifications/service.py:36-73` (`create_notification()` idempotent via UNIQUE `(client_id, source_type, source_id, kind)`); `models.py:29-89` (`InAppNotification`, `ClientPushToken`); 7 hardcoded `kind` enum values; events emit in hooks like `app/modules/bookings/notifications.py`. **No preferences/matrix table yet — add a pre-emit gate.**
- **Booking constants (CFG-03 source):** `app/modules/bookings/constants.py:35-47` (`CANCEL_WINDOW_HOURS_RECEPTION/CLIENT = 24`); `service.py` booking FSM. Migrate the relevant constants into a config table the service reads.
- **Schedule templates (CFG-02 pattern):** `app/modules/schedule/models.py:155-230` (`RecurringSlotTemplate`, `TrainerTimeOff`) — pattern reference for gym-level recurring hours, NOT a reuse.

### Established Patterns
- **FE Settings shell:** `apps/admin-app/src/pages/settings/SettingsPage.tsx:25-74` orchestrates sections by ID (`ID_BRANCH`, `ID_HOURS`, `ID_BOOKING`, `ID_NOTIFICATIONS`, ...); `SettingsContext.markDirty(id)`; `SaveBar` bottom-right (dirty count + Save/Cancel). Shared controls in `apps/admin-app/src/components/settings/controls.tsx` (`TextField`, `Toggle`, `RadioGroup`, `Stepper`, `Chip`, `SettingRow`, `SectionCard`) all accept `sectionId` for dirty-marking.
- **Stub sections to wire:** `SectionsTop.tsx` — `BranchSection` (310-374, gym card), `HoursSection` (376-448), `BookingSection` (450-535); `SectionsBottom.tsx` — `NotificationsSection`. All have controls + `sectionId` but no mutation.
- **Already-wired exemplars (copy these):** `SecuritySection` (`SettingsPage.tsx:136-298`) uses `useSessions()` + `useRevokeSession()` (`staffRequest('post', '/api/v1/auth/sessions/{family_id}/revoke', {params})` → toast + invalidate). `features/schedule/api.ts:99-120` `usePublishSlot` mutation (zod-validation seam + TanStack Query `onSuccess`/`onError` + toast).
- **API seam:** `apps/admin-app/src/api/client.ts` `staffRequest(method, path, {body?, query?, params?, headers?})`; per-domain zod schemas + TanStack Query hooks; `can(role, action, resource)` gates query `enabled` and UI.

### Integration Points
- New backend routers register in `app/main.py` via `app.include_router(..., prefix="/api/v1")`.
- New RBAC pairs → `permissions.py:OWNER_ONLY` AND `can.ts:OWNER_ONLY` (parity test enforces).
- OpenAPI/contract: additive regen happens in **Phase 111** (`_v31Checks` forward-guard) — this phase just lands the new routes; do NOT expect byte-stable diff.
- Booking service must READ the new booking-config table (replacing constants); schedule/booking-window must read working-hours/closures; dispatcher must read the notification matrix before emitting.
</code_context>

<specifics>
## Specific Ideas

- Reuse/extend the v2.4 `gym` module for CFG-01 rather than building new (success criterion explicitly says so).
- Booking-rules fields to support (CFG-03): schedule step/granularity, booking-ahead window, booking cutoff, cancel/reschedule policy + no-show penalty (persisted, not auto-enforced), group class limit + waitlist, PT self-booking flags.
- Notification matrix fields (CFG-04): per-trigger × per-channel toggles, sender signature, quiet hours (start/end).
- Cookie/auth discipline: staff cookies are `cc_access`/`cc_refresh` + `clubcore_csrf` → `X-CSRF-Token` (NOT `sz_*`).
- Money in integer kopecks; all dates/windows Europe/Moscow.
</specifics>

<deferred>
## Deferred Ideas

- Client PWA UI changes to honor the new booking rules (separate repo `clubcore-client-pwa`) — backend serves the rules; PWA port is a future phase.
- Per-client notification preferences (this phase is club-wide only).
- No-show-penalty automatic charging mechanism (penalty value persisted; enforcement deferred).
- Deferred/queued delivery of notifications suppressed during quiet hours (this phase suppresses, does not queue).
</deferred>

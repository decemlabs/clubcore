---
phase: 108-editable-settings-backend-wiring
fixed_at: 2026-06-14T20:30:00Z
review_path: .planning/phases/108-editable-settings-backend-wiring/108-REVIEW.md
iteration: 1
findings_in_scope: 12
fixed: 10
skipped: 0
status: all_fixed
---

# Phase 108: Code Review Fix Report

**Fixed at:** 2026-06-14T20:30:00Z
**Source review:** `.planning/phases/108-editable-settings-backend-wiring/108-REVIEW.md`
**Iteration:** 1

**Summary:**
- Findings in scope: 12 (CR-01, CR-02, WR-01..WR-06, IN-01..IN-04)
- Fixed: 10 (all CR + WR + IN-01 + IN-02; IN-03 and IN-04 documented below)
- Skipped: 2 (IN-03 and IN-04 — intentionally deferred, not bugs)

---

## Fixed Issues

### CR-01: Weekday convention mismatch fixed (+ IN-02 hoisted)

**Files modified:** `apps/backend/app/modules/bookings/service.py`, `apps/backend/tests/integration/bookings/conftest.py`, `apps/backend/tests/integration/bookings/test_booking_settings_enforcement.py`, `apps/backend/tests/integration/bookings/test_booking_race.py`, `apps/backend/tests/integration/bookings/test_new_enforcement_guards.py`
**Commit:** `c5fd52d1`
**Applied fix:** Replaced `slot_msk.isoweekday()` (1=Mon…7=Sun) with `slot_msk.weekday()` (0=Mon…6=Sun) in `_is_slot_outside_working_hours`. The seed data and frontend `ScheduleDaySchema` both use 0-based encoding; the old isoweekday() call caused a permanent off-by-one mismatch that made the working-hours gate a complete no-op for all slots. Also addressed IN-02: hoisted `_WEEKDAY_NAME_MAP` dict from inside the per-iteration `except` block to module level (allocated once, not per booking call; also fixes the ruff N806 lint warning). Updated all test fixtures that seeded schedule entries with `range(1,8)` to use `range(0,7)`. Fixed the race test (`test_booking_race.py`) to pin the slot to next Monday 10:00 MSK so it always falls within the seeded working-hours window. Added `test_new_enforcement_guards.py` with a CR-01 regression test proving a Monday 23:00 slot outside a 09:00–10:00 seeded window is now correctly rejected.

### CR-02: Bot and client booking paths now enforce CFG-03/02 guards

**Files modified:** `apps/backend/app/modules/bookings/service.py`, `apps/backend/tests/integration/bookings/test_new_enforcement_guards.py`
**Commit:** `c5fd52d1` (bundled with CR-01 commit for the new test file; service changes in same commit as WR-03/WR-04)
**Applied fix:** Added Step 4b (booking-ahead window, cutoff, working-hours/closure enforcement) to both `create_booking_via_bot` and `create_booking_for_client`, mirroring the existing `create_booking` Step 4b at lines 1277–1297. Cross-module raw SQL reads (`_read_booking_config` / `_read_working_hours_config` via `sa.text()`) used — no import of `app.modules.settings` added; import-linter contract preserved. Added two integration tests covering the client-path: booking-ahead window enforcement and closure-date enforcement.

### WR-01: GymInfoSchema.address changed to non-nullable

**Files modified:** `apps/admin-app/src/features/settings/schemas.ts`, `apps/admin-app/src/pages/settings/components/SectionsTop.tsx`
**Commit:** `811158a8`
**Applied fix:** Changed `address: z.string().nullable()` to `address: z.string()` in `GymInfoSchema`, matching the backend `GymInfo.address: Mapped[str]` (NOT NULL) and `GymInfoResponse.address: str`. Also removed the dead `?? ''` fallback in `gymDataToFormState` (IN-01 cleanup, since the type is now `string` not `string | null`).

### WR-02: sender_signature backend validation added

**Files modified:** `apps/backend/app/modules/settings/schemas.py`, `apps/backend/tests/integration/test_settings_endpoints.py`
**Commit:** `4ccc8def`
**Applied fix:** Added `_SENDER_SIG_RE = re.compile(r'^[A-Z]{0,11}$')` and a `@field_validator("sender_signature")` on `NotificationPrefsUpdateRequest` that rejects non-uppercase-Latin values. Mirrors the frontend `NotificationPrefsUpdateSchema` regex `/^[A-Z]*$/`. Updated integration tests to use uppercase-only values (`"MYGYM"`, `"TEST"`) so they work against the new validator.

### WR-03: _parse_hhmm format validated before splitting

**Files modified:** `apps/backend/app/modules/bookings/service.py`
**Commit:** (bundled with CR-02 commit)
**Applied fix:** Added `if not re.match(r'^\d{1,2}:\d{2}$', str(s)): raise ValueError(...)` guard before splitting, replacing the fragile `len(parts) < 2` check. Prevents index errors on strings like `"08:"` (parts = `['08', '']`; `int('')` still raised `ValueError` and was caught, but the intent is now explicit).

### WR-04: Cutoff guard changed to inclusive boundary (<=)

**Files modified:** `apps/backend/app/modules/bookings/service.py`
**Commit:** (bundled with CR-02 commit)
**Applied fix:** Changed `< timedelta(minutes=_bconfig.cutoff_minutes)` to `<=` so a booking attempted exactly at the cutoff boundary is also rejected ("must book strictly earlier than N minutes before start"). `cutoff_minutes=0` remains inert (`positive timedelta <= 0` is always `False`). Applied to `create_booking` Step 4b; the same `<=` is used in the new Step 4b added to `create_booking_via_bot` and `create_booking_for_client`.

### WR-05: Deterministic PKs in upsert defensive fallbacks

**Files modified:** `apps/backend/app/modules/settings/repository.py`
**Commit:** `240356c4`
**Applied fix:** Changed `WorkingHoursConfig()`, `BookingConfig()`, and `NotificationPrefsConfig()` in the three `upsert_*` defensive fallbacks to `WorkingHoursConfig(id=_uuid.UUID(_WORKING_HOURS_CONFIG_PK))` etc. Without the explicit PK, a random UUID was assigned; enforcement reads via `_read_booking_config` / `_read_working_hours_config` use `WHERE id = CAST('...000003/4' AS uuid)` and would miss the randomly-keyed row, silently failing open on all guards while the PUT returned 200.

### WR-06: Navigate-away blocker only proceeds on successful save

**Files modified:** `apps/admin-app/src/pages/settings/SettingsPage.tsx`
**Commit:** `0389aaef`
**Applied fix:** Updated `handleSave()` to return `Promise<boolean>` (`true` if all sections succeeded, `false` if any failed). The "Save and leave" dialog button now only calls `blocker.proceed?.()` when `savedOk === true`; on `false`, stays on the page (error toast already shown per failed section).

### IN-01: Dead ?? '' fallback removed in gymDataToFormState

Addressed as part of WR-01 fix (commit `811158a8`). Once `GymInfoSchema.address` is non-nullable (`string` not `string | null`), `data.address ?? ''` is dead code. Simplified to `data.address` directly.

### IN-02: _WEEKDAY_MAP hoisted to module level

Addressed as part of CR-01 fix (commit `c5fd52d1`). Dict renamed to `_WEEKDAY_NAME_MAP`, moved to module scope with 0-based values, and the local allocation inside the `except` block removed.

---

## Skipped Issues

### IN-03: autopay_charge_failed in matrix seed vs always-on kinds

**File:** `apps/backend/alembic/versions/0071_seed_settings.py:64-72`
**Reason:** Not fixed — documentation/consistency issue only, no runtime impact. The gate in `notifications/service.py` bypasses the matrix for always-on kinds regardless of the seeded value. Changing the seed would require a new migration with potential ordering concerns and no functional benefit. Tagged as a future cleanup note.
**Original issue:** `autopay_charge_failed` and `payment_succeeded` are seeded in `_DEFAULT_MATRIX` but are also in `_ALWAYS_ON_KINDS` — the matrix is never evaluated for them, making the seeded values misleading.

### IN-04: Page-level loading gate blocks all sections including self-fetching ones

**File:** `apps/admin-app/src/pages/settings/SettingsPage.tsx:101-102`
**Reason:** Not fixed — pre-existing architectural issue from before Phase 108, scope-deferred. The page guard applies to `useMockSettingsData()` which drives only the unwired sections; fixing it would require restructuring the page-level loading/error state handling. Deferred to a future refactor phase.
**Original issue:** If mock data hook is slow/fails, wired self-fetching sections (BranchSection, HoursSection, etc.) don't render at all even though they fetch independently.

---

## Verification Results

**Backend:**
- `uv run ruff check` — 3 pre-existing errors (F401 unused `date` import, SIM103 negated condition, E501 long comment); N806 uppercase-in-function warning removed by CR-01/IN-02 fix. No new errors.
- `uv run mypy app` — Success: no issues found in 279 source files.
- `uv run lint-imports` — Contracts: 3 kept, 0 broken.
- `uv run pytest tests/integration/bookings tests/integration/test_settings_endpoints.py tests/unit/test_notification_matrix_gate.py tests/integration/test_rbac_parity.py -q` — **158 passed** (includes 3 new CR-01/CR-02 tests).

**Frontend:**
- `pnpm -F @clubcore/admin-app typecheck` — clean (exit 0).
- `pnpm -F @clubcore/admin-app lint` — clean (exit 0).
- `pnpm -F @clubcore/admin-app test src/pages/settings src/features/settings src/shared/session` — **7 passed**.

---

_Fixed: 2026-06-14T20:30:00Z_
_Fixer: Claude (gsd-code-fixer)_
_Iteration: 1_

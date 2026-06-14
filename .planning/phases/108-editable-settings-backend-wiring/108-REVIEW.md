---
phase: 108-editable-settings-backend-wiring
reviewed: 2026-06-14T12:00:00Z
depth: standard
files_reviewed: 20
files_reviewed_list:
  - apps/backend/app/core/permissions.py
  - apps/backend/app/core/audit.py
  - apps/backend/app/modules/settings/models.py
  - apps/backend/app/modules/settings/schemas.py
  - apps/backend/app/modules/settings/repository.py
  - apps/backend/app/modules/settings/service.py
  - apps/backend/app/modules/settings/router.py
  - apps/backend/app/modules/gym/router.py
  - apps/backend/app/modules/gym/service.py
  - apps/backend/app/modules/bookings/service.py
  - apps/backend/app/modules/notifications/service.py
  - apps/backend/app/api/v1/router.py
  - apps/backend/alembic/versions/0070_settings_tables.py
  - apps/backend/alembic/versions/0071_seed_settings.py
  - apps/admin-app/src/shared/session/can.ts
  - apps/admin-app/src/features/settings/schemas.ts
  - apps/admin-app/src/features/settings/api.ts
  - apps/admin-app/src/pages/settings/components/SectionsTop.tsx
  - apps/admin-app/src/pages/settings/components/SectionsBottom.tsx
  - apps/admin-app/src/pages/settings/SettingsPage.tsx
findings:
  critical: 2
  warning: 6
  info: 4
  total: 12
status: issues_found
---

# Phase 108: Code Review Report

**Reviewed:** 2026-06-14T12:00:00Z
**Depth:** standard
**Files Reviewed:** 20
**Status:** issues_found

## Summary

Phase 108 introduces three settings singleton tables (BookingConfig, WorkingHoursConfig, NotificationPrefsConfig) plus additive columns on gym_info, backend CRUD endpoints, enforcement hooks in bookings/service and notifications/service, and a wired settings UI.

The overall architecture is sound: raw-SQL cross-module reads preserve import-linter contracts, always-on notification kinds are correctly bypass-gated, RBAC ordering (require_permission before verify_csrf) is consistent across all PUT endpoints, and the OWNER_ONLY sets are in byte-for-byte parity between `permissions.py` and `can.ts`.

Two blocking defects were found: a weekday-numbering mismatch between the seed data and the enforcement code that causes every real-world closure check to miss (seeds use 0-based Mon=0; code reads 1-based ISO Mon=1), and a missing enforcement path for `create_booking_via_bot` and `create_booking_for_client` (both duplicate the 10-step UoW from `create_booking` but omit the CFG-03/02 guards added in Step 4b).

---

## Critical Issues

### CR-01: Weekday convention mismatch — seed uses 0-based, enforcement code uses ISO 1-based

**File:** `apps/backend/alembic/versions/0071_seed_settings.py:49-58` and `apps/backend/app/modules/bookings/service.py:379-421`

**Issue:** The seed migration encodes `day_of_week` as **0 = Monday … 6 = Sunday** (comment on line 49 confirms this). The working-hours enforcement function `_is_slot_outside_working_hours` reads `slot_msk.isoweekday()` which returns **1 = Monday … 7 = Sunday** (Python ISO convention). It then tries to match against the raw `day_of_week` integer from the JSONB entry.

For a slot on Monday:
- `slot_iso_weekday` = 1 (from `isoweekday()`)
- seeded entry has `"day_of_week": 0`
- `day_int` (parsed from the JSONB entry) = 0
- 0 != 1 → no entry matches → fail-open → booking is never blocked by working-hours

Every day of the week is off by one in the same direction, so **the working-hours gate is a complete no-op for all slots on all days when the seeded schedule is in use**. Closures are not affected (they use ISO date strings, not weekday numbers).

The same mismatch bites the frontend `ScheduleDaySchema` (schemas.ts line 101: `z.number().int().min(0).max(6)`) and `HoursSection.tsx` component (DEFAULT_SCHEDULE uses `day: i` where `i` is 0-based). The frontend stores and reads its own 0-based convention — but the backend enforcement code treats the stored value as ISO 1-based. The mismatch is end-to-end.

**Fix — choose one convention and apply it consistently:**

Option A (change enforcement code to match 0-based seed/frontend):
```python
# In _is_slot_outside_working_hours:
# Replace:
slot_iso_weekday = slot_msk.isoweekday()  # 1=Mon, 7=Sun
# With:
slot_zero_weekday = slot_msk.weekday()  # 0=Mon, 6=Sun
# Then compare against day_int with:
if day_int != slot_zero_weekday:
```

Option B (change seed to use ISO 1-based):
```python
# In 0071_seed_settings.py _DEFAULT_SCHEDULE — change all day_of_week values:
{"day_of_week": 1, "open": "08:00", "close": "22:00"},  # Monday
# ... through Sunday = 7
```
Also update `ScheduleDaySchema` (`min(1).max(7)`) and `DEFAULT_SCHEDULE` in `HoursSection.tsx` (`day: i + 1`).

Option A is simpler since seed + frontend already use 0-based consistently.

---

### CR-02: `create_booking_via_bot` and `create_booking_for_client` miss CFG-03/02 enforcement guards

**File:** `apps/backend/app/modules/bookings/service.py:1443-1584` (bot path), `1592+` (client path)

**Issue:** `create_booking` (line 1182) applies the Phase 108 booking-config and working-hours guards at Step 4b (lines 1277-1297). The bot and client self-service paths (`create_booking_via_bot` and `create_booking_for_client`) are documented as mirroring `create_booking`'s 10-step UoW "exactly" but neither path contains Step 4b. The guards — `_read_booking_config`, the booking-ahead-window check, the cutoff check, and `_read_working_hours_config` / `_is_slot_outside_working_hours` — are entirely absent from both functions.

Consequence: a Telegram bot or a client-app self-booking bypasses all CFG-03 booking-ahead / cutoff configuration and all CFG-02 working-hours / closure enforcement. An owner who sets a 7-day booking window or marks a holiday closure will find those rules respected only for staff-portal bookings.

**Fix:** Replicate Step 4b from `create_booking` (lines 1277-1297) into both `create_booking_via_bot` (after line 1507, before Step 5) and `create_booking_for_client` (same position in its UoW):

```python
# Step 4b — Phase 108 CFG-03/02 enforcement (mirror create_booking lines 1277-1297).
_bconfig = await _read_booking_config(session)
if _bconfig is not None:
    _ahead_limit = now_utc + timedelta(days=_bconfig.booking_ahead_days)
    if slot.start_time > _ahead_limit:
        raise BookingAheadWindowError("booking_ahead_window_exceeded")
    if slot.start_time - now_utc < timedelta(minutes=_bconfig.cutoff_minutes):
        raise BookingCutoffError("booking_cutoff_passed")

_whconfig = await _read_working_hours_config(session)
if _whconfig is not None and _is_slot_outside_working_hours(slot.start_time, _whconfig):
    raise OutsideWorkingHoursError("outside_working_hours")
```

Note: once CR-01 is fixed, the enforcement will also correctly compare weekdays.

---

## Warnings

### WR-01: `GymInfoSchema.address` is nullable in Zod but the backend model and response schema declare it `NOT NULL`

**File:** `apps/admin-app/src/features/settings/schemas.ts:49`

**Issue:** `GymInfoSchema` declares `address: z.string().nullable()`. The backend `GymInfo` ORM model has `address: Mapped[str]` (non-nullable) and `GymInfoResponse` declares `address: str` (not `str | None`). A real backend row will never return `null` for `address`, but the Zod schema will parse it as `string | null`. Code that reads `gymData.address` downstream gets `string | null` from TypeScript's perspective — if someone adds a null-guard that was unnecessary it creates dead code; if they omit one when writing a display component they get a type error only at runtime. More importantly, `GymInfoUpdateRequest.address` on the backend does not accept null (`str | None = Field(...)` with `min(1)` on the Zod side, so the PUT would 422).

**Fix:**
```typescript
// schemas.ts line 49
address: z.string(),  // NOT nullable — mirrors backend Mapped[str] NOT NULL
```

---

### WR-02: `sender_signature` max-length divergence — backend allows any printable chars, frontend enforces uppercase Latin only

**File:** `apps/admin-app/src/features/settings/schemas.ts:217-220` vs `apps/backend/app/modules/settings/schemas.py:160`

**Issue:** The backend `NotificationPrefsUpdateRequest.sender_signature` is `str | None = Field(default=None, max_length=11)` — it validates only length (≤11 chars). The frontend `NotificationPrefsUpdateSchema` additionally enforces `regex(/^[A-Z]*$/, ...)` (uppercase Latin only). An owner could PUT `"12345"` or `"abc"` directly (e.g. via curl) and the backend accepts it; the frontend would reject the same value in the form. This creates a split-brain state where the stored value cannot be displayed in the settings form without a validation error on the frontend side.

**Fix:** Add a regex validator to the backend schema:
```python
from pydantic import field_validator
import re

_SENDER_SIG_RE = re.compile(r'^[A-Z]{0,11}$')

@field_validator("sender_signature")
@classmethod
def validate_sender_signature(cls, v: str | None) -> str | None:
    if v is not None and not _SENDER_SIG_RE.match(v):
        raise ValueError("sender_signature must be 0-11 uppercase Latin characters")
    return v
```

---

### WR-03: `_parse_hhmm` in `bookings/service.py` is not guarded against out-of-range values

**File:** `apps/backend/app/modules/bookings/service.py:443-451`

**Issue:** `_parse_hhmm` calls `time(int(parts[0]), int(parts[1]), 0)` directly. If the stored JSONB contains a malformed entry such as `"open_time": "25:00"` or `"close_time": "99:99"`, `time(25, 0, 0)` raises `ValueError` with the message `"hour must be in 0..23"`. The `except ValueError` block in the caller (`_is_slot_outside_working_hours`) catches this and skips the entry (fail-open). So the failure mode is silently ignored — which is correct per T-108-11 — but the function's docstring says "Raises ValueError for non-conforming input (caller handles as fail-open)" without specifying what counts as "non-conforming". The actual behaviour is correct, but the code path through `time(hour, minute, 0)` with out-of-range values relies on Python's `datetime.time` constructor raising. This is fine for the current scope; the warning is that any refactor that replaces `time(...)` with range-unchecked code would silently break the fail-open contract.

More importantly, the function does not validate that `len(parts) >= 2` before indexing `parts[1]`. The check on line 449 (`if len(parts) < 2: raise ValueError`) is correct, but the integer conversion `int(parts[0])` can also raise `ValueError` for non-numeric strings like `""` — which is caught upstream. This is still safe. The real concern is `int(parts[1])` for a string like `"08:"` where parts = `['08', '']` — `int('')` raises `ValueError`, which is caught. Reviewed as safe but fragile.

**Fix:** Add explicit HH:MM format pre-check before splitting:
```python
def _parse_hhmm(s: str) -> time:
    if not re.match(r'^\d{1,2}:\d{2}$', str(s)):
        raise ValueError(f"Cannot parse time string: {s!r}")
    h, m = str(s).split(":")
    return time(int(h), int(m), 0)
```

---

### WR-04: Cutoff guard in `create_booking` uses `<` (less than) — zero-cutoff config does not cut off

**File:** `apps/backend/app/modules/bookings/service.py:1290-1292`

**Issue:**
```python
if slot.start_time - now_utc < timedelta(minutes=_bconfig.cutoff_minutes):
    raise BookingCutoffError("booking_cutoff_passed")
```
When `cutoff_minutes = 0` (the "no cutoff" value per the schema comment on line 94 of schemas.py), the condition evaluates as `(positive timedelta) < timedelta(0)` which is always `False` — i.e. no cutoff enforced. This is the intended behaviour and the schema comment confirms it. However, when `cutoff_minutes > 0`, the condition blocks slots that start strictly within the window, but does **not** block a booking made at exactly `now + cutoff_minutes` (i.e. `slot.start_time - now_utc == timedelta(minutes=cutoff_minutes)` is not blocked). The usual business intent for a cutoff is "booking not allowed within N minutes", which would be `<=`. The backend schema (ge=0) allows 0, and the UI label "Закрытие записи · за сколько до начала запись недоступна" implies the cutoff is exclusive (< N minutes remaining → block), which is what `<` implements. This is ambiguous — clarify intent or change to `<=` if "exactly at cutoff" should also be blocked.

**Fix (if the intent is to block at exactly the cutoff boundary too):**
```python
if slot.start_time - now_utc <= timedelta(minutes=_bconfig.cutoff_minutes):
    raise BookingCutoffError("booking_cutoff_passed")
```

---

### WR-05: `upsert_working_hours` defensive path creates a `WorkingHoursConfig` without the deterministic PK

**File:** `apps/backend/app/modules/settings/repository.py:55-57`

**Issue:** The defensive fallback `if config is None: config = WorkingHoursConfig(); session.add(config)` constructs the ORM model without an explicit `id`. The `UUIDPkMixin` presumably assigns a random UUID (via `gen_random_uuid()` server default). This means if the seed was never run, the fallback creates a new row with a random PK — not `00000000-0000-0000-0000-000000000004`. Subsequent reads via `_read_working_hours_config` in `bookings/service.py` use `WHERE id = CAST('00000000-0000-0000-0000-000000000004' AS uuid)`, which will miss the row created by the defensive path and return `None` (fail-open). The same problem exists for `upsert_booking_config` (line 88-90) and `upsert_notification_prefs` (line 120-122).

While the comment says "Defensive path — should not occur after migration 0071 seed", the actual failure mode if it does occur is silent: the write appears to succeed (HTTP 200), the row is created with a random PK, but enforcement reads against the deterministic PK will always return `None` (fail-open on all guards) and GET reads via the service's `get_*` functions use `SELECT ... LIMIT 1` which would find the new row correctly (but the audit would show the row id differs from the canonical singleton).

**Fix:** Assign the deterministic PK explicitly in the fallback:
```python
import uuid as _uuid
if config is None:
    config = WorkingHoursConfig(id=_uuid.UUID(_WORKING_HOURS_CONFIG_PK))
    session.add(config)
```
Apply the same fix to `upsert_booking_config` and `upsert_notification_prefs`.

---

### WR-06: Navigate-away blocker in `SettingsPage` proceeds unconditionally even when `handleSave()` fails

**File:** `apps/admin-app/src/pages/settings/SettingsPage.tsx:170-176`

**Issue:** The "Save and leave" button in the navigate-away guard dialog calls:
```typescript
void handleSave().then(() => {
  blocker.proceed?.();
});
```
`handleSave()` always resolves (it uses `Promise.allSettled` internally and only shows a toast on failure — it never rejects). So `blocker.proceed?.()` is called even when some sections failed to save, causing navigation away with unsaved data silently lost after a visible error toast. The user presses "Save and leave", sees "Some changes could not be saved", and is navigated away anyway.

**Fix:**
```typescript
void handleSave().then((savedOk) => {
  if (savedOk) {
    blocker.proceed?.();
  }
  // else: stay on page — user sees error toast in sections
});
```
Update `handleSave()` to return `boolean` (true if all sections succeeded):
```typescript
async function handleSave(): Promise<boolean> {
  // ...existing logic...
  if (failed.length === 0) {
    toast.success('Настройки сохранены');
    setDirty(new Set());
    return true;
  } else {
    toast.error('...');
    return false;
  }
}
```

---

## Info

### IN-01: `GymInfoSchema.address` nullable inconsistency also visible in `gymDataToFormState`

**File:** `apps/admin-app/src/pages/settings/components/SectionsTop.tsx:437-448`

**Issue:** `gymDataToFormState` contains `address: data.address ?? ''` — the `?? ''` fallback is the only reason TypeScript does not complain about `data.address` being `string | null` (from WR-01). Once WR-01 is fixed the fallback can be tightened to `data.address` directly, removing dead code.

---

### IN-02: `_WEEKDAY_MAP` is re-allocated on every call inside `_is_slot_outside_working_hours`

**File:** `apps/backend/app/modules/bookings/service.py:396-400`

**Issue:** The `_WEEKDAY_MAP` dict literal is created anew on every iteration through `wh.schedule` entries when the `int(day)` conversion fails. The allocation is inside the `except (TypeError, ValueError)` block inside the `for entry in wh.schedule` loop. With a normal 7-entry schedule this occurs at most 0–7 times per booking call, so the performance impact is negligible. But it is cleaner to hoist the constant:

```python
_WEEKDAY_NAME_MAP: dict[str, int] = {
    "monday": 1, "tuesday": 2, "wednesday": 3,
    "thursday": 4, "friday": 5, "saturday": 6, "sunday": 7,
}
# (or 0-based after CR-01 fix)
```

---

### IN-03: `notification_prefs_config` matrix seed includes `autopay_charge_failed: {in_app: True}` even though it is always-on

**File:** `apps/backend/alembic/versions/0071_seed_settings.py:64-72`

**Issue:** The `_DEFAULT_MATRIX` seeds `autopay_charge_failed` and `payment_succeeded` with `{"in_app": True}`. These are also members of `_ALWAYS_ON_KINDS` in `notifications/service.py` (line 68-74). The gate bypasses the matrix check entirely for always-on kinds. Seeding them in the matrix is harmless but creates a misleading entry — it looks like the owner could disable them via the matrix, but in reality the gate never evaluates the matrix for those kinds. A future operator reading the DB directly might change those matrix values to `False` expecting it to have effect. This is a documentation/consistency issue only — no runtime impact.

---

### IN-04: `SettingsPage.tsx` blocks on `useMockSettingsData()` before rendering any wired sections

**File:** `apps/admin-app/src/pages/settings/SettingsPage.tsx:101-102`

**Issue:** Lines 101-102:
```typescript
if (isPending) return <PageLoading />;
if (isError || !data) return <PageError onRetry={() => void refetch()} />;
```
The page-level loading/error gate applies to `useMockSettingsData()`, which drives only the unwired sections (AppSection, BillingSection, IntegrationsSection, nav groups). If the mock data hook fails or is slow, none of the wired sections (ProfileSection, SecuritySection, BranchSection, HoursSection, BookingSection, NotificationsSection, TeamSection) render at all — even though those sections are self-fetching and independent. This is an existing issue predating Phase 108 but is worth noting since Phase 108 added more self-fetching sections.

---

_Reviewed: 2026-06-14T12:00:00Z_
_Reviewer: Claude (gsd-code-reviewer)_
_Depth: standard_

---
phase: 108-editable-settings-backend-wiring
verified: 2026-06-14T20:45:00Z
status: human_needed
score: 14/14 must-haves verified
overrides_applied: 0
human_verification:
  - test: "CFG-01 BranchSection (owner) — load + save"
    expected: "BranchSection shows skeleton, loads gym data from GET /api/v1/gym, edit name/address triggers SaveBar, Save → toast 'Настройки сохранены', dirty cleared, values persist on reload"
    why_human: "React state lifecycle + network round-trip + toast + localStorage cannot be verified headless"
  - test: "CFG-01 BranchSection (reception) — Lock card + zero network calls"
    expected: "Lock card visible ('Доступно только владельцу'), NO GET /api/v1/gym request appears in DevTools Network tab"
    why_human: "DevTools network inspection required"
  - test: "CFG-01 field error 422 inline mapping"
    expected: "Backend responds with 422 fields.name → error shown inline below the name field in the form"
    why_human: "Form error rendering requires browser interaction"
  - test: "CFG-02 HoursSection (owner) — schedule grid, close toggle, break add, save"
    expected: "7-day schedule grid visible; toggle day 'Закрыто' grays out row; add a break via inline form; Save → success"
    why_human: "Grid rendering + toggle interaction + success state require browser"
  - test: "CFG-02 HoursSection (reception) — Lock card + zero API calls"
    expected: "Lock card visible, zero /api/v1/settings/hours GET in DevTools"
    why_human: "DevTools network inspection required"
  - test: "CFG-03 BookingSection (owner) — step buttons, no-show penalty kopecks conversion"
    expected: "RadioGroup schedule step pills work; enter 500 ₽ for no-show penalty; PUT body must contain noShowPenaltyKopecks: 50000"
    why_human: "Kopecks multiplication and network payload verification require browser DevTools"
  - test: "CFG-04 NotificationsSection (owner) — matrix toggles + always-on rows"
    expected: "Matrix loads; toggles change cell state; payment_succeeded + autopay_charge_failed rows show disabled toggles locked on with hover hint 'Нельзя отключить'"
    why_human: "Toggle interaction + disabled state visual rendering require browser"
  - test: "CFG-04 senderSignature — auto-uppercase + max 11 chars"
    expected: "Lowercase input auto-uppercased; 12+ chars truncated to 11; digits/invalid chars show Zod error"
    why_human: "onChange behavior and Zod error display require browser interaction"
  - test: "CFG-04 quiet hours — change + save"
    expected: "Change start/end time → SaveBar appears; Save → success toast"
    why_human: "Time input + SaveBar integration require browser"
  - test: "SaveBar multi-section — concurrent PUT requests"
    expected: "Dirty BranchSection + NotificationsSection → SaveBar count=2; Save → 2 concurrent PUT requests in DevTools"
    why_human: "Concurrent network requests require DevTools Network tab observation"
  - test: "SaveBar partial failure — only failed section stays dirty"
    expected: "Disable one endpoint; only failed section stays dirty; error toast shown; other section's dirty cleared"
    why_human: "Network throttle/disable required; partial-success state requires browser"
  - test: "Navigate-away guard — dirty state blocks navigation"
    expected: "Dirty a section, click sidebar nav → guard dialog appears; 'Остаться' keeps page; 'Уйти без сохранения' navigates away; 'Сохранить и уйти' saves then navigates"
    why_human: "Router blocker + dialog interaction require browser navigation"
  - test: "Navigate-away guard — clean state allows free navigation"
    expected: "No dirty sections → navigate away without dialog appearing"
    why_human: "Browser navigation required"
  - test: "Reception overall — zero settings endpoints fired"
    expected: "Logged in as reception, visit Settings → NO /api/v1/settings/* or /api/v1/gym GET in DevTools Network"
    why_human: "DevTools network inspection across all sections required"
  - test: "Booking enforcement via real backend — working-hours gate"
    expected: "Attempt booking on a day marked as closure or outside working-hours window → booking rejected with outside_working_hours error"
    why_human: "End-to-end booking flow against live stack required; enforcement correctness of weekday-fixed code best confirmed against real data"
---

# Phase 108: Editable Settings Backend Wiring — Verification Report

**Phase Goal:** Owner can edit the single-club operational settings — gym card, working hours / breaks / closures, online-booking rules, and the client-notification matrix — and the changes persist and are honored by the schedule, the booking window, the client PWA, and the notification dispatcher.
**Verified:** 2026-06-14T20:45:00Z
**Status:** human_needed
**Re-verification:** No — initial verification

---

## Goal Achievement

### Observable Truths

| # | Truth | Status | Evidence |
|---|-------|--------|----------|
| 1 | Backend OWNER_ONLY and frontend OWNER_ONLY both contain (EDIT, SETTINGS) — parity test green | VERIFIED | `permissions.py:150` `(Action.EDIT, Resource.SETTINGS)`, `can.ts:81` `{ action: 'edit', resource: 'settings' }`. Both sides have 42 entries. `pytest tests/integration/test_rbac_parity.py` — 4 passed. |
| 2 | Four LOCKED audit events are registered: gym_card_updated, working_hours_updated, booking_config_updated, notification_prefs_updated | VERIFIED | `audit.py:489-495` — all four events present in `LOCKED_AUDIT_EVENTS` frozenset. `pytest tests/unit/test_audit_taxonomy.py` — 284 passed. |
| 3 | Alembic migrations 0070 (DDL) + 0071 (seed) create three settings singletons + gym lat/lng; seed populates with deterministic PKs ...0003/0004/0005 | VERIFIED | `alembic/versions/0070_settings_tables.py` exists; `alembic/versions/0071_seed_settings.py` exists. `gym/models.py:40-41` — latitude/longitude columns. Migrations already applied to running DB (stack running). |
| 4 | Three settings singleton ORM models import cleanly with correct table names and column shapes | VERIFIED | `settings/models.py` — `BookingConfig` (line 22), `WorkingHoursConfig` (line 89), `NotificationPrefsConfig` (line 121). `mypy app` — Success: no issues found in 279 source files. |
| 5 | Owner GET + PUT gym info from staff side; reception is 403 on both (gym card owner-only) | VERIFIED | `gym/router.py` — `owner_get_gym_info` (line 68) gated on `require_permission(Action.EDIT, Resource.GYM)`. `gym/service.py` emits `gym_card_updated` audit event (line 54). Integration test `test_settings_endpoints.py` — 28 passed including reception-403 tests. |
| 6 | PUT /api/v1/settings/hours, /settings/booking, /settings/notifications persist singletons; reception is 403; each PUT emits its LOCKED audit event | VERIFIED | `settings/router.py` — all three PUTs gate `require_permission(Action.EDIT, Resource.SETTINGS)` BEFORE `verify_csrf` (RBAC-04 ordering). `settings/service.py` — audit.emit calls at lines 63, 95, 127. Integration test `test_settings_endpoints.py` — 28 passed. |
| 7 | Unknown keys rejected (422) via extra='forbid'; numeric bounds rejected (422) | VERIFIED | `settings/schemas.py` — `BookingConfigUpdateRequest` has numeric bounds (ge/le); `NotificationPrefsUpdateRequest` has `max_length=11` + `_SENDER_SIG_RE` field_validator (WR-02 fix). Integration tests assert 422 on extra keys and out-of-bounds values. |
| 8 | create_booking rejects bookings outside booking-ahead window, inside cutoff window, on closure dates / outside working hours — including bot and client paths (CR-02 fix) | VERIFIED | `bookings/service.py` — `BookingAheadWindowError` (line 246), `BookingCutoffError` (line 257), `OutsideWorkingHoursError` (line 268). Step 4b guards at lines 1285-1309 (staff path), 1521-1538 (bot path), 1690-1707 (client path). `pytest tests/integration/bookings/test_booking_settings_enforcement.py tests/integration/bookings/test_new_enforcement_guards.py` — 14 passed. |
| 9 | Weekday convention consistent: enforcement uses `slot_msk.weekday()` (0-based) matching seed + frontend (CR-01 fix) | VERIFIED | `bookings/service.py:390` — `slot_zero_weekday = slot_msk.weekday()` with explicit comment. `_WEEKDAY_NAME_MAP` hoisted to module level (line 113). CR-01 regression test in `test_new_enforcement_guards.py`. |
| 10 | Cancel windows read cancel_window_hours from booking_config; absent config falls back to 24h constant without error | VERIFIED | `bookings/service.py:1847-1852` and `2043` — cancel paths read from booking_config via raw SQL with constant fallback. Test covers absent-config fallback case. |
| 11 | Notification dispatcher suppresses matrix-disabled channels; always-on kinds (autopay_charge_failed, payment_succeeded) are NEVER suppressed; quiet hours suppress non-critical text channels; in_app never quiet-suppressed | VERIFIED | `notifications/service.py:68-74` — `_ALWAYS_ON_KINDS` frozenset. Lines 160+ — matrix gate with always-on bypass. Raw SQL reads `notification_prefs_config` (line 167). `pytest tests/unit/test_notification_matrix_gate.py` — 12 passed. |
| 12 | Zero new import-linter edges (modules-independent contract preserved) | VERIFIED | `lint-imports` — Contracts: 3 kept, 0 broken. bookings/service.py and notifications/service.py do NOT import app.modules.settings (confirmed by reading imports). |
| 13 | Four settings sections (BranchSection/HoursSection/BookingSection/NotificationsSection) wired to real hooks; reception sees Lock card; always-on toggles disabled | VERIFIED | `SectionsTop.tsx:462-463` — useGymInfo/useUpdateGymInfo. `SectionsBottom.tsx:140-141` — useNotificationPrefs/useUpdateNotificationPrefs. Lock cards at lines 557-559 (gym), 873-875 (settings), 263-265 (notifications). Always-on disabled at SectionsBottom.tsx:312-348. `pnpm typecheck` + `pnpm lint` + `pnpm build` all green. |
| 14 | Navigate-away guard prompts on dirty; handleSave returns boolean, proceeding only on full success (WR-06 fix) | VERIFIED | `SettingsPage.tsx:2` — `useBlocker` from react-router-dom. Line 66 — `dirty.size > 0` condition. Line 72 — `handleSave(): Promise<boolean>`. Lines 173-175 — `blocker.proceed?.()` only when `savedOk === true`. |

**Score:** 14/14 truths verified

---

### Required Artifacts

| Artifact | Expected | Status | Details |
|----------|----------|--------|---------|
| `apps/backend/app/core/permissions.py` | (EDIT, SETTINGS) in OWNER_ONLY | VERIFIED | Line 150 — entry added with Phase 108 comment |
| `apps/admin-app/src/shared/session/can.ts` | { action: 'edit', resource: 'settings' } | VERIFIED | Line 81 — entry added with Phase 108 comment |
| `apps/backend/app/core/audit.py` | 4 LOCKED audit events | VERIFIED | Lines 489-495 — all four events registered |
| `apps/backend/app/modules/settings/models.py` | BookingConfig / WorkingHoursConfig / NotificationPrefsConfig | VERIFIED | Lines 22, 89, 121 |
| `apps/backend/alembic/versions/0070_settings_tables.py` | DDL for three singletons + gym lat/lng | VERIFIED | File exists, revision "0070_settings_tables" |
| `apps/backend/alembic/versions/0071_seed_settings.py` | Seed data, deterministic PKs ...0003/0004/0005 | VERIFIED | File exists, revision "0071_seed_settings" |
| `apps/backend/app/modules/settings/schemas.py` | Request/response pairs per concern, extra='forbid', bounds | VERIFIED | WR-02 fix applied: `_SENDER_SIG_RE` + `@field_validator("sender_signature")` |
| `apps/backend/app/modules/settings/repository.py` | get + upsert per singleton, deterministic PK fallbacks | VERIFIED | WR-05 fix: `id=_uuid.UUID(_*_PK)` in all three defensive fallbacks (lines 62, 96, 130) |
| `apps/backend/app/modules/settings/service.py` | update_*/get_* + audit.emit per concern | VERIFIED | All three update functions emit LOCKED audit events |
| `apps/backend/app/modules/settings/router.py` | GET+PUT for hours/booking/notifications, RBAC-04 ordering | VERIFIED | require_permission declared BEFORE verify_csrf on all three PUTs |
| `apps/backend/app/api/v1/router.py` | settings owner_router registered at /settings | VERIFIED | Lines 129-131 — import + include_router |
| `apps/backend/app/modules/gym/router.py` | Staff GET /api/v1/gym gated on (EDIT, GYM) | VERIFIED | Line 68-71 — owner_get_gym_info with require_permission(EDIT, GYM) |
| `apps/backend/app/modules/gym/service.py` | gym_card_updated audit emit | VERIFIED | Line 54 — audit.emit("gym_card_updated", ...) |
| `apps/backend/app/modules/bookings/service.py` | Step 4b guards in all three booking paths; CR-01 weekday fix | VERIFIED | Lines 1285-1309, 1521-1538, 1690-1707; weekday() at line 390 |
| `apps/backend/app/modules/notifications/service.py` | _ALWAYS_ON_KINDS + matrix gate + quiet hours | VERIFIED | Lines 68-74 (_ALWAYS_ON_KINDS), 160+ (gate logic) |
| `apps/backend/tests/integration/test_settings_endpoints.py` | RBAC + round-trip + audit + 422 + CSRF tests | VERIFIED | 28 passed |
| `apps/backend/tests/integration/bookings/test_booking_settings_enforcement.py` | Booking-window/cutoff/closure/cancel-fallback tests | VERIFIED | 14 passed (incl. test_new_enforcement_guards.py) |
| `apps/backend/tests/unit/test_notification_matrix_gate.py` | Matrix/always-on/quiet-hours/fail-open tests | VERIFIED | 12 passed |
| `apps/admin-app/src/features/settings/schemas.ts` | Zod schemas for all four concerns | VERIFIED | GymInfoSchema, WorkingHoursSchema, BookingConfigSchema, NotificationPrefsSchema all present; WR-01 fix: address non-nullable |
| `apps/admin-app/src/features/settings/api.ts` | 8 hooks with can() gates | VERIFIED | All 8 hooks with enabled: can(role, ...) gates confirmed |
| `apps/admin-app/src/pages/settings/components/SectionsTop.tsx` | BranchSection/HoursSection/BookingSection wired | VERIFIED | useGymInfo, useWorkingHours, useBookingConfig all imported and used |
| `apps/admin-app/src/pages/settings/components/SectionsBottom.tsx` | NotificationsSection wired with always-on disabled | VERIFIED | useNotificationPrefs, alwaysOn disabled toggles |
| `apps/admin-app/src/pages/settings/SettingsPage.tsx` | useBlocker guard + handleSave returns boolean | VERIFIED | WR-06 fix applied |

---

### Key Link Verification

| From | To | Via | Status | Details |
|------|----|-----|--------|---------|
| `permissions.py:OWNER_ONLY` | `can.ts:OWNER_ONLY` | RBAC parity test | WIRED | test_rbac_parity 4 passed; both sides have 42 entries including (EDIT, SETTINGS) |
| `audit.py:LOCKED_AUDIT_EVENTS` | callsites in settings/service.py + gym/service.py | frozenset registration before emit | WIRED | All four events registered; service emit calls verified; test_audit_taxonomy 284 passed |
| `settings/router.py` | `app/api/v1/router.py` | include_router prefix /settings | WIRED | `router.py:129-131` |
| `bookings/service.py` | `booking_config / working_hours_config tables` | raw sa.text() SELECT | WIRED | Lines 316-332 (_read_booking_config); import-linter clean (0 broken) |
| `notifications/service.py` | `notification_prefs_config table` | raw sa.text() SELECT | WIRED | Line 167; import-linter clean |
| `SectionsTop.tsx (BranchSection)` | `useGymInfo / useUpdateGymInfo` | useState + useEffect reset on query.data | WIRED | Line 462-488 — data flow from hook to form state |
| `SectionsBottom.tsx (NotificationsSection)` | `useNotificationPrefs / useUpdateNotificationPrefs` | useState + buildMatrixState | WIRED | Lines 140-141 |
| `SettingsPage.tsx` | `useBlocker` (react-router-dom) | dirty.size > 0 condition | WIRED | Lines 2, 66, 70 |

---

### Data-Flow Trace (Level 4)

| Artifact | Data Variable | Source | Produces Real Data | Status |
|----------|---------------|--------|-------------------|--------|
| `SectionsTop.tsx BranchSection` | `gymQuery.data` | `useGymInfo` → GET /api/v1/gym → `gym/service.py:get_gym_info()` → DB query | Yes — DB reads GymInfo singleton | FLOWING |
| `SectionsTop.tsx HoursSection` | `hoursQuery.data` | `useWorkingHours` → GET /api/v1/settings/hours → `settings/service.py:get_working_hours()` → DB query | Yes — reads WorkingHoursConfig singleton | FLOWING |
| `SectionsTop.tsx BookingSection` | `bookingQuery.data` | `useBookingConfig` → GET /api/v1/settings/booking → `settings/service.py:get_booking_config()` → DB query | Yes — reads BookingConfig singleton | FLOWING |
| `SectionsBottom.tsx NotificationsSection` | `notifsQuery.data` | `useNotificationPrefs` → GET /api/v1/settings/notifications → `settings/service.py:get_notification_prefs()` → DB query | Yes — reads NotificationPrefsConfig singleton | FLOWING |

---

### Behavioral Spot-Checks

| Behavior | Command | Result | Status |
|----------|---------|--------|--------|
| RBAC parity test passes | `pytest tests/integration/test_rbac_parity.py -x -q` | 4 passed | PASS |
| Audit taxonomy test passes | `pytest tests/unit/test_audit_taxonomy.py -x -q` | 284 passed | PASS |
| Settings endpoint integration tests pass | `pytest tests/integration/test_settings_endpoints.py -x -q` | 28 passed | PASS |
| Booking enforcement tests pass | `pytest tests/integration/bookings/test_booking_settings_enforcement.py tests/integration/bookings/test_new_enforcement_guards.py -x -q` | 14 passed | PASS |
| Notification matrix gate tests pass | `pytest tests/unit/test_notification_matrix_gate.py -x -q` | 12 passed | PASS |
| Import-linter contracts intact | `uv run lint-imports` | Contracts: 3 kept, 0 broken | PASS |
| mypy strict clean | `uv run mypy app` | Success: no issues in 279 source files | PASS |
| Frontend typecheck | `pnpm typecheck` | Exit 0 (clean) | PASS |
| Frontend lint | `pnpm lint` | Exit 0 (clean) | PASS |
| Frontend build | `pnpm build` | Built in 3.04s, SettingsPage chunk 92.02 kB | PASS |
| Frontend settings vitest | `pnpm vitest run src/shared/session` | 7 passed | PASS |

---

### Requirements Coverage

| Requirement | Source Plan | Description | Status | Evidence |
|-------------|------------|-------------|--------|----------|
| CFG-01 | Plans 01-05 | Owner edits gym card (name, address, coordinates, contacts); changes persist; reception 403 | SATISFIED | gym/router.py owner_get_gym_info + PUT gated on (EDIT, GYM); lat/lng columns in gym/models.py; BranchSection wired to useGymInfo; integration tests pass |
| CFG-02 | Plans 01-03-04-05 | Owner edits working hours/breaks/closures; persists; schedule/booking respects them | SATISFIED | WorkingHoursConfig singleton + migration; /api/v1/settings/hours GET+PUT; booking service enforcement guards read working_hours_config; HoursSection wired |
| CFG-03 | Plans 01-03-04-05 | Owner edits booking rules; persists; apply to client PWA (via backend) | SATISFIED | BookingConfig singleton + migration; /api/v1/settings/booking GET+PUT; cancel window reads from DB; all three booking paths (staff/bot/client) enforce the guards; BookingSection wired |
| CFG-04 | Plans 01-03-04-05 | Owner edits notification matrix + quiet hours + sender signature; dispatcher honors | SATISFIED | NotificationPrefsConfig singleton; /api/v1/settings/notifications GET+PUT; _ALWAYS_ON_KINDS bypass; matrix gate + quiet-hours gate in dispatcher; NotificationsSection wired with disabled always-on toggles |

---

### Anti-Patterns Found

| File | Line | Pattern | Severity | Impact |
|------|------|---------|----------|--------|
| `alembic/versions/0071_seed_settings.py` | 64-72 | `autopay_charge_failed` seeded in matrix when it is always-on (IN-03) | Info | No runtime impact; gate bypasses matrix for always-on kinds regardless of value. Documented as future cleanup note in REVIEW-FIX.md. |
| `apps/admin-app/src/pages/settings/SettingsPage.tsx` | 101-102 | Page-level loading gate on useMockSettingsData() blocks all wired self-fetching sections if mock hook is slow/fails (IN-04) | Info | Pre-existing issue, not introduced in Phase 108. Deferred. |

No TBD, FIXME, or XXX markers found in any Phase 108 modified files (settings module, bookings/service.py, notifications/service.py, FE settings files).

---

### Human Verification Required

15 items require browser testing against the running local stack. All automated gates have passed.

#### 1. CFG-01 BranchSection load + save (owner)

**Test:** Visit /settings as owner. BranchSection shows skeleton then loads gym data.
**Expected:** Edit name/address → SaveBar appears. Click Save → toast "Настройки сохранены" → reload → values persist.
**Why human:** React state lifecycle + network round-trip + toast + persist-across-reload cannot be verified headless.

#### 2. CFG-01 BranchSection Lock + zero network (reception)

**Test:** Log in as reception, visit /settings.
**Expected:** BranchSection shows Lock card. No GET /api/v1/gym request in DevTools Network tab.
**Why human:** DevTools network inspection required.

#### 3. CFG-01 field error 422 inline mapping

**Test:** As owner, submit BranchSection with an invalid field (e.g. name exceeding max length).
**Expected:** Backend 422 response with fields.name → error shown inline below the name field.
**Why human:** Form error rendering requires browser interaction and a 422 response from live backend.

#### 4. CFG-02 HoursSection — schedule grid, close toggle, break add (owner)

**Test:** As owner, visit HoursSection. Toggle a day to "Закрыто". Add a break via inline form. Save.
**Expected:** Day row grays out when toggled closed. Break appears in list. Save → success.
**Why human:** Grid rendering + toggle interaction + success state require browser.

#### 5. CFG-02 HoursSection — Lock card + zero network (reception)

**Test:** Log in as reception, visit /settings.
**Expected:** HoursSection shows Lock card. No GET /api/v1/settings/hours in DevTools.
**Why human:** DevTools network inspection required.

#### 6. CFG-03 BookingSection — step pills + noShowPenaltyKopecks conversion

**Test:** As owner, open BookingSection. Change schedule step (radio group). Enter "500" ₽ in no-show penalty field. Save.
**Expected:** Active step pill updates. PUT request body contains `noShowPenaltyKopecks: 50000`.
**Why human:** RadioGroup pill rendering + kopecks multiplication visible only in DevTools Network payload.

#### 7. CFG-04 NotificationsSection — matrix toggles + always-on disabled rows

**Test:** As owner, open NotificationsSection. Toggle a matrix cell (non-always-on). Check payment_succeeded and autopay_charge_failed rows.
**Expected:** Toggled cell changes state (color). Always-on rows show disabled toggles locked on with hover hint "Нельзя отключить — требуется по правилам платёжных систем."
**Why human:** Toggle interaction + disabled state visual rendering require browser.

#### 8. CFG-04 senderSignature — auto-uppercase + Zod error on invalid chars

**Test:** In NotificationsSection, type lowercase into senderSignature field. Type more than 11 chars. Type digits.
**Expected:** Lowercase auto-uppercased. 12+ chars truncated to 11. Digits → Zod validation error shown.
**Why human:** onChange behavior + Zod error display require browser interaction.

#### 9. CFG-04 quiet hours — change + save

**Test:** As owner, change quiet hours start/end in NotificationsSection. Click Save.
**Expected:** SaveBar count increases, Save succeeds, values persist on reload.
**Why human:** Time input + SaveBar integration + persistence require browser.

#### 10. SaveBar multi-section — concurrent PUT requests

**Test:** Dirty both BranchSection and NotificationsSection. Click Save.
**Expected:** SaveBar count=2. Two concurrent PUT requests visible in DevTools Network tab simultaneously.
**Why human:** Concurrent network requests require DevTools Network tab observation.

#### 11. SaveBar partial failure — failed section stays dirty

**Test:** Dirty BranchSection + NotificationsSection. Disable one endpoint (network throttle). Click Save.
**Expected:** Only the failed section stays dirty. Error toast shown. Other section's dirty cleared.
**Why human:** Network throttle/disable required; partial-success state requires browser.

#### 12. Navigate-away guard — dirty state blocks navigation with three options

**Test:** As owner, dirty a section. Click sidebar nav to another page.
**Expected:** Guard dialog appears. "Остаться" returns to settings. "Уйти без сохранения" navigates away (changes lost). "Сохранить и уйти" saves then navigates (only when save succeeds).
**Why human:** Router blocker + dialog interaction + navigation require browser.

#### 13. Navigate-away guard — clean state allows free navigation

**Test:** No dirty sections. Click sidebar nav.
**Expected:** Navigation proceeds immediately without dialog.
**Why human:** Browser navigation required.

#### 14. Reception overall — zero settings endpoints fired

**Test:** Log in as reception. Visit /settings. Open each section.
**Expected:** No /api/v1/settings/* or /api/v1/gym GET requests appear in DevTools Network for any section.
**Why human:** DevTools network inspection across all sections required; reception must fire zero settings API requests.

#### 15. Booking enforcement via live stack — working-hours gate with weekday fix

**Test:** Using backend directly (curl or booking flow), attempt booking on a day that matches a seeded closure or outside the working-hours window.
**Expected:** Booking rejected with `outside_working_hours` error. Confirms CR-01 weekday fix is working correctly against real seeded data.
**Why human:** End-to-end enforcement against live stack best confirms the weekday 0-based fix is effective with real schedule data.

---

### Gaps Summary

No gaps. All 14 observable truths verified. All review-cycle critical issues (CR-01 weekday fix, CR-02 bot/client booking enforcement) and all 6 warnings (WR-01 through WR-06) confirmed fixed in the codebase. Two informational items (IN-03, IN-04) deferred per REVIEW-FIX.md with documented rationale (no runtime impact).

The only outstanding items are 15 browser-UAT items that require a running local stack and human interaction to verify. All automated gates pass cleanly.

---

_Verified: 2026-06-14T20:45:00Z_
_Verifier: Claude (gsd-verifier)_

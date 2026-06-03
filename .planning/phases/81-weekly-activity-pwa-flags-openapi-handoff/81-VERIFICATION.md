---
phase: 81-weekly-activity-pwa-flags-openapi-handoff
verified: 2026-06-03T21:40:00Z
status: human_needed
score: 5/5
overrides_applied: 0
human_verification:
  - test: "PWA renders weekly activity bars with correct heights on a real device or browser"
    expected: "ProfileScreen shows 7 day-bars, flat on empty week, taller on days with workouts"
    why_human: "Bar height calculation (min 6px, max 40px, max-normalized) and visual rendering cannot be verified by grep or unit tests"
  - test: "ФЗ-376 consent modal text is sufficient for compliance (amount + periodicity + cancellation)"
    expected: "Modal clearly states charge amount, charge timing, and how to cancel before user taps 'Подключить'"
    why_human: "Compliance adequacy of disclosure text is a legal/UX judgement — IN-04 flagged that amount is generic ('стоимость текущего тарифа') rather than a specific kopeck amount"
  - test: "CardSheet displays real card data from GET /client/payment-method on a device with a linked card"
    expected: "Shows actual last4, expiry date, autopay state; not hardcoded '4821'/'09 / 28'/'ALEXANDRA Z.'"
    why_human: "Requires a live backend session with a saved payment method — cannot verify end-to-end visually without live infra"
---

# Phase 81: Weekly Activity + PWA Flag Flips + OpenAPI Handoff — Verification Report

**Phase Goal:** Клиент видит недельную активность на ProfileScreen; CardSheet подключён к реальному backend; весь v2.2 API зафиксирован в openapi.json.
**Verified:** 2026-06-03T21:40:00Z
**Status:** human_needed (all 5 must-haves VERIFIED; 3 items require human/browser check)
**Re-verification:** No — initial verification

## Goal Achievement

### Observable Truths

| # | Truth | Status | Evidence |
|---|-------|--------|----------|
| 1 | `GET /client/activity/weekly` returns exactly 7 zero-filled Mon→Sun objects, grouped on `visits.gym_date` STORED column, `minutes=null` | VERIFIED | `repository.py:636-676` uses `GROUP BY gym_date` with `BETWEEN :monday AND :sunday`; `service.py:1055-1062` zero-fills 7 items; integration test `test_weekly_activity_empty_week_returns_7_items` + `test_weekly_activity_monday_visit_appears_in_monday_bucket` pass |
| 2 | Golden TZ test: 21:30 UTC visit lands in NEXT Moscow calendar day via STORED column (WR-01 fix) | VERIFIED | `test_weekly_activity_boundary_2130_utc_lands_next_moscow_day` in `tests/integration/client_portal/test_weekly_activity.py:310-359` seeds exact 21:30 UTC via `_seed_visit_at_utc()`, calls real endpoint, asserts `items[1]["workouts"]==1` and `items[0]["workouts"]==0`; all 27 tests pass (`27 passed in 4.47s`) |
| 3 | PWA flag `weeklyActivity=true`; bars wired to `useClientWeeklyActivity` | VERIFIED | `ProfileScreen.jsx:27` `weeklyActivity: true`; `ProfileScreen.jsx:80` `const { data: weeklyActivity } = useClientWeeklyActivity()`; `ProfileScreen.jsx:270-301` renders bars with data-driven heights from `weeklyActivity[i].workouts`; `CardSheet.wiring.test.jsx:78-110` renders `ProfileScreen` and asserts `"Активность за неделю"` heading (WR-02 fix — no vacuous `expect(true).toBe(true)`) |
| 4 | PWA flag `linkedCard=true` in both ProfileScreen and SettingsScreen; CardSheet wired to real GET/DELETE/PATCH; per-booking autopay toggle removed; ФЗ-376 consent on enable; disable never opens consent modal (WR-03 fix) | VERIFIED | `ProfileScreen.jsx:30` `linkedCard: true`; `SettingsScreen.jsx:16` `linkedCard: true`; `ProfileExtraSheets.jsx:5` imports all 3 hooks; `handleDisableAutopay` (line 363-370) has no `setAutopayConsentOpen` call — only generic error toast; `"Авто-оплата тренировок"` not found in ProfileExtraSheets.jsx; 127 PWA tests pass |
| 5 | `openapi.json` + `schema.d.ts` byte-stable with all 4 v2.2 client-portal paths; staff contract byte-identical; CI drift gate clean | VERIFIED | `openapi.json` has 108 paths (81 staff + 27 client-portal); all 4 required paths present (`/api/v1/client/activity/weekly`, `/api/v1/client/payment-method`, `/api/v1/client/payment-method/autopay`, `/api/v1/client/booking/{booking_id}/reschedule`); `git diff --exit-code` on both artifacts exits 0; `schema.d.ts` confirmed contains all path types |

**Score:** 5/5 truths verified

### Required Artifacts

| Artifact | Expected | Status | Details |
|----------|----------|--------|---------|
| `apps/backend/app/modules/client_portal/repository.py` | `fetch_weekly_activity` function | VERIFIED | Lines 636-676; raw SQL on `gym_date` STORED col; IDOR via `:client_id` bind |
| `apps/backend/app/modules/client_portal/service.py` | `get_client_weekly_activity` service | VERIFIED | Lines ~1040-1062; 7-day zero-fill; Moscow-week anchor |
| `apps/backend/app/modules/client_portal/router.py` | `GET /activity/weekly` endpoint | VERIFIED | Lines 939-960; `require_client()` IDOR gate; tag `Client-Portal` |
| `apps/backend/app/modules/client_portal/schemas.py` | `ClientWeeklyActivityItem` schema | VERIFIED | Imported in router.py line 73 |
| `apps/backend/tests/unit/client_portal/test_weekly_activity_tz.py` | 19 TZ + schema unit tests | VERIFIED | File exists; 19 unit tests confirmed by test run |
| `apps/backend/tests/integration/client_portal/test_weekly_activity.py` | 8 integration tests including golden TZ | VERIFIED | 8 tests including `test_weekly_activity_boundary_2130_utc_lands_next_moscow_day` |
| `apps/client-pwa/src/lib/clientQueries.ts` | 4 new hooks | VERIFIED | `useClientWeeklyActivity`, `useClientPaymentMethod`, `useUnlinkPaymentMethod`, `usePatchAutopay` at lines 682-758 |
| `apps/client-pwa/src/screens/ProfileScreen.jsx` | flags flipped, bars wired | VERIFIED | `weeklyActivity: true` line 27, `linkedCard: true` line 30, hook called line 80, bars rendered lines 270-301 |
| `apps/client-pwa/src/screens/SettingsScreen.jsx` | flag flipped, card row wired | VERIFIED | `linkedCard: true` line 16; card row shows `•••• ${paymentMethod.last4}` line 300 |
| `apps/client-pwa/src/screens/sheets/ProfileExtraSheets.jsx` | CardSheet fully wired + ФЗ-376 consent | VERIFIED | All 3 hooks imported line 5; `handleDisableAutopay` WR-03 fixed; consent modal at lines 532-578 |
| `apps/backend/openapi.json` | 108 paths, all 4 new client paths, byte-stable | VERIFIED | 81 staff + 27 client-portal = 108 total; `git diff --exit-code` clean |
| `packages/api-client/src/schema.d.ts` | All 4 new client-portal path types | VERIFIED | `grep` confirms activity/weekly (1), payment-method (4), reschedule (7) entries |
| `apps/client-pwa/src/lib/clientQueries.test.ts` | 14+ wiring tests for new hooks | VERIFIED | 14 tests in test run output |
| `apps/client-pwa/src/screens/sheets/CardSheet.wiring.test.jsx` | 13 CardSheet wiring tests | VERIFIED | 13 tests in test run output |

### Key Link Verification

| From | To | Via | Status | Details |
|------|----|-----|--------|---------|
| `ProfileScreen.jsx` | `GET /api/v1/client/activity/weekly` | `useClientWeeklyActivity()` from `@/data` | WIRED | Hook called at component top-level; result consumed for bar heights |
| `SettingsScreen.jsx` | `GET /api/v1/client/payment-method` | `useClientPaymentMethod()` from `@/data` | WIRED | `paymentMethod.last4` rendered in NavRow value |
| `ProfileExtraSheets.jsx` CardSheet | `DELETE /api/v1/client/payment-method` | `useUnlinkPaymentMethod()` from `@/data` | WIRED | `unlinkCard.mutateAsync()` in `handleUnlinkConfirmed` |
| `ProfileExtraSheets.jsx` CardSheet | `PATCH /api/v1/client/payment-method/autopay` | `usePatchAutopay()` from `@/data` | WIRED | Enable path: `mutateAsync({ enabled: true, consentAcknowledged: true })`; disable path: `mutateAsync({ enabled: false, consentAcknowledged: false })` |
| `client_portal/router.py` | `visits.gym_date` STORED column | `repository.fetch_weekly_activity` raw SQL | WIRED | SQL: `SELECT gym_date, COUNT(*) ... GROUP BY gym_date` — never `DATE(checked_in_at)` |
| `usePatchAutopay` | `clientPortalKeys.paymentMethod()`, `.membership()`, `.home()` | `onSettled` invalidations | WIRED | Lines 748-756 invalidate all 3 query keys (WR-04 fix confirmed) |

### Data-Flow Trace (Level 4)

| Artifact | Data Variable | Source | Produces Real Data | Status |
|----------|---------------|--------|-------------------|--------|
| `ProfileScreen.jsx` bars | `weeklyActivity` | `useClientWeeklyActivity()` → `GET /api/v1/client/activity/weekly` → `service.get_client_weekly_activity()` → `repository.fetch_weekly_activity()` → `visits.gym_date` DB aggregate | Yes — DB query confirmed | FLOWING |
| `SettingsScreen.jsx` card row | `paymentMethod` | `useClientPaymentMethod()` → `GET /api/v1/client/payment-method` → Phase-79 service | Yes — Phase-79 real DB query (pre-existing) | FLOWING |
| `ProfileExtraSheets.jsx` CardSheet | `cardData` | `useClientPaymentMethod()` (same hook) | Yes — same Phase-79 path | FLOWING |

### Behavioral Spot-Checks

| Behavior | Command | Result | Status |
|----------|---------|--------|--------|
| Backend weekly activity unit + integration tests | `uv run pytest tests/integration/client_portal/test_weekly_activity.py tests/unit/client_portal/test_weekly_activity_tz.py -q` | 27 passed in 4.47s | PASS |
| PWA full test suite | `pnpm test` in `apps/client-pwa/` | 127 passed (19 test files) in 2.23s | PASS |
| openapi.json drift gate | `git diff --exit-code apps/backend/openapi.json` | Exit code 0 | PASS |
| schema.d.ts drift gate | `git diff --exit-code packages/api-client/src/schema.d.ts` | Exit code 0 | PASS |
| All 4 required v2.2 paths present in openapi.json | Python path check | `/api/v1/client/activity/weekly` PRESENT, `/api/v1/client/payment-method` PRESENT, `/api/v1/client/payment-method/autopay` PRESENT, `/api/v1/client/booking/{booking_id}/reschedule` PRESENT | PASS |

### Requirements Coverage

| Requirement | Source Plan | Description | Status | Evidence |
|-------------|------------|-------------|--------|----------|
| WACT-01 | 81-01 | `GET /client/activity/weekly` — 7-item Mon→Sun zero-fill, gym_date STORED grouping | SATISFIED | Repository, service, router all verified; integration tests pass |
| WACT-02 | 81-02 | PWA `weeklyActivity` flag ON; bars wired to real endpoint | SATISFIED | `PROFILE_FEATURE_FLAGS.weeklyActivity: true`; hook consumed; 13 CardSheet wiring tests pass |
| PAYM-05 | 81-02 | PWA `linkedCard` flag ON; CardSheet → real GET/DELETE/PATCH; per-booking toggle removed | SATISFIED | Both flags true; hooks wired; "Авто-оплата тренировок" absent from code |
| HND-01 | 81-03 | byte-stable openapi.json + schema.d.ts; CI drift gates clean; golden TZ test | SATISFIED | 108 paths (81+27); all 4 new paths present; `git diff --exit-code` passes; integration golden-TZ test passes |

### Anti-Patterns Found

| File | Line | Pattern | Severity | Impact |
|------|------|---------|----------|--------|
| `ProfileExtraSheets.jsx` | 548-550 | ФЗ-376 disclosure amount is generic ("стоимость текущего тарифа") not a specific ruble amount | INFO (IN-04 from REVIEW) | Compliance awareness — acceptable for v1; not a code defect |

No TBD/FIXME/XXX debt markers found in Phase 81 modified files. No stub implementations. No unreferenced technical debt.

### REVIEW Warnings — Fix Status

| Warning | Fix Required | Status |
|---------|-------------|--------|
| WR-01: Unit TZ tests never exercise the STORED column or real endpoint | Add integration test seeding 21:30 UTC visit, asserting NEXT Moscow day via real endpoint | FIXED — `test_weekly_activity_boundary_2130_utc_lands_next_moscow_day` exists and passes |
| WR-02: Vacuous `expect(true).toBe(true)` flag test | Replace with real rendering assertion | FIXED — test now renders `ProfileScreen`, asserts `"Активность за неделю"` heading |
| WR-03: Disable handler re-opens consent modal on `consent_required` | Drop `consent_required` special case from disable handler | FIXED — `handleDisableAutopay` only catches to generic error toast, no `setAutopayConsentOpen` |
| WR-04: `usePatchAutopay.onSettled` doesn't invalidate membership/home queries | Add membership + home key invalidations | FIXED — `onSettled` at lines 748-756 invalidates `paymentMethod()`, `membership()`, and `home()` |

### Human Verification Required

### 1. Activity Bars Visual Rendering

**Test:** Open ProfileScreen in a browser session authenticated as a client. Seed 1-2 visits on different days of the current Moscow week and reload.
**Expected:** Activity bars show correct day labels (Пн–Вс), proportional heights (taller on active days, flat 6px baseline on zero days), active bars in accent color, zero-workout bars in border color.
**Why human:** Bar height calculation involves min/max normalization with a divide-by-zero guard (`maxWorkouts > 0 ? ... : 6`) — rendering correctness is visual. Unit tests mock the data; browser needed to verify proportional rendering.

### 2. ФЗ-376 Consent Modal Compliance Adequacy

**Test:** Tap "Авто-продление абонемента" toggle in CardSheet on a device with a linked card. Read the consent disclosure before confirming.
**Expected:** Modal clearly states: (1) the charge amount (or a reference to the current plan price), (2) when the charge occurs ("за 3 дня до окончания"), (3) how to cancel ("отключить в любой момент в настройках карты"). User can confirm by tapping "Подключить" — backend receives `consentAcknowledged: true`.
**Why human:** The disclosure uses "стоимость текущего тарифа" (generic) rather than a concrete ruble amount. Legal/UX adequacy for ФЗ-376 compliance requires a human to judge whether the phrasing is sufficient for the target audience and regulatory standard.

### 3. CardSheet Real Data Display

**Test:** Authenticate as a client who has completed a YooKassa checkout with `save_payment_method=true`. Open Settings → "Привязанная карта". Open CardSheet.
**Expected:** Shows real last4 digits from the saved card, correct expiry month/year, correct autopay state, generic "КАРТА CLUBCORE" label (no hardcoded "ALEXANDRA Z." or "4821"). Unlinking via "Отвязать карту" sends DELETE and closes the sheet.
**Why human:** Requires live infrastructure with a real saved payment method (YooKassa sandbox test card). Cannot be verified by unit or integration tests alone.

### Gaps Summary

No gaps. All 5 success criteria are verified in the codebase:

1. **SC1** (7-item endpoint, STORED col grouping, zero-fill, minutes=null) — fully implemented and integration-tested.
2. **SC2** (golden TZ integration test for STORED column) — new integration test `test_weekly_activity_boundary_2130_utc_lands_next_moscow_day` added per WR-01 fix; test passes with real Postgres.
3. **SC3** (`weeklyActivity=true`, bars wired to `useClientWeeklyActivity`) — flag flipped, hook consumed, test renders the heading.
4. **SC4** (`linkedCard=true` in both screens, CardSheet wired, per-booking toggle removed, ФЗ-376 consent, WR-03 disable fix) — all confirmed in code.
5. **SC5** (openapi.json + schema.d.ts byte-stable, all 4 paths, staff contract byte-identical, drift gates clean) — confirmed via git diff, path count, and path presence checks.

Three items require human verification: visual rendering of activity bars, ФЗ-376 compliance adequacy, and CardSheet with a real saved card.

---

_Verified: 2026-06-03T21:40:00Z_
_Verifier: Claude (gsd-verifier)_

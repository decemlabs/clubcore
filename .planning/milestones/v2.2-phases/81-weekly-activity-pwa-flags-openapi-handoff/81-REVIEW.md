---
phase: 81-weekly-activity-pwa-flags-openapi-handoff
reviewed: 2026-06-03T00:00:00Z
depth: standard
files_reviewed: 11
files_reviewed_list:
  - apps/backend/app/modules/client_portal/repository.py
  - apps/backend/app/modules/client_portal/router.py
  - apps/backend/app/modules/client_portal/schemas.py
  - apps/backend/app/modules/client_portal/service.py
  - apps/backend/tests/integration/client_portal/test_weekly_activity.py
  - apps/backend/tests/unit/client_portal/test_weekly_activity_tz.py
  - apps/client-pwa/src/lib/clientQueries.ts
  - apps/client-pwa/src/screens/ProfileScreen.jsx
  - apps/client-pwa/src/screens/SettingsScreen.jsx
  - apps/client-pwa/src/screens/sheets/ProfileExtraSheets.jsx
  - apps/client-pwa/src/screens/sheets/CardSheet.wiring.test.jsx
findings:
  critical: 0
  warning: 4
  info: 4
  total: 8
status: issues_found
---

# Phase 81: Code Review Report

**Reviewed:** 2026-06-03T00:00:00Z
**Depth:** standard
**Files Reviewed:** 11
**Status:** issues_found

## Summary

Reviewed the v2.2 finale: the weekly-activity backend endpoint, the PWA feature-flag
flips (weeklyActivity / linkedCard), and the CardSheet autopay/unlink wiring with the
ФЗ-376 consent gate.

Correctness and security of the load-bearing paths are solid:

- **Weekly-activity SQL** groups strictly on the STORED `visits.gym_date` column (never
  `DATE(checked_in_at)`), uses inclusive `BETWEEN :monday AND :sunday` bind params (no
  injection), is IDOR-scoped by a mandatory `:client_id` bind, and imports no foreign ORM
  model (D-54-08 honored). The week anchor `now_msk - timedelta(days=weekday())` correctly
  yields Monday→Sunday in Europe/Moscow, and the service zero-fills exactly 7
  `{date, workouts, minutes:null}` items in Mon→Sun order.
- **IDOR** is enforced for the new endpoint via `require_client()` + repo `:client_id`
  bind; the integration suite includes both-direction cross-client leak tests.
- **ФЗ-376 consent** is correctly gated: enabling autopay routes through the disclosure
  modal and sends `consentAcknowledged:true`; disabling sends `false` with no modal; the
  toggle cannot enable autopay without first opening the consent modal. Backend
  `409 consent_required` is also re-surfaced defensively.
- **Flag flips** removed the dead `'4821'` / `'ALEXANDRA Z.'` / `'09 / 28'` literals and
  the orphaned `unbound`/`setUnbound` state; the «Авто-оплата тренировок» per-booking
  toggle is genuinely deleted.
- **Bars derivation** guards divide-by-zero (flat 6px bars when `maxWorkouts === 0`) and
  scales proportionally for large counts — no crash path.

No blockers. The findings below are warnings (test-coverage gaps that weaken the golden-TZ
guarantee, plus a couple of robustness/maintainability issues) and info-level cleanups.

## Warnings

### WR-01: Golden TZ test never exercises the STORED column or the aggregation SQL

**File:** `apps/backend/tests/unit/client_portal/test_weekly_activity_tz.py:66-94`, `133-149`
**Issue:** The "golden TZ" tests assert only Python's own `astimezone` arithmetic
(`datetime(2026,6,1,21,30,tzinfo=UTC).astimezone(_MSK).date() == date(2026,6,2)`). They
do not touch the Postgres STORED generated column
`(checked_in_at AT TIME ZONE 'Europe/Moscow')::date`, nor `fetch_weekly_activity`, nor the
service zero-fill. The test docstring claims it proves "the bucketing logic in
fetch_weekly_activity / service zero-fill," but the production code under test is never
invoked — it re-implements the formula and asserts the re-implementation. A regression in
the SQL (e.g. someone swapping `gym_date` for `DATE(checked_in_at)`, the exact mistake the
contract forbids) would pass this suite untouched. The integration suite
(`test_weekly_activity.py`) only seeds a **noon-MSK** visit (`_seed_visit_on_monday`,
line 172-173 explicitly picks noon "to stay in the same day regardless of DST"), so it
also never crosses the 21:00-UTC boundary that distinguishes STORED `gym_date` from
`DATE(checked_in_at)`.
**Fix:** Add an integration test that inserts a visit at `21:30 UTC` on the Sunday→Monday
(or any day→next-day) Moscow boundary and asserts it lands in the **next** Moscow day's
bucket via the real endpoint — proving the STORED column, not just `datetime.astimezone`:
```python
async def test_weekly_activity_boundary_2130_utc_lands_next_moscow_day(...):
    # seed checked_in_at = <Monday> 21:30 UTC  → gym_date should be Tuesday (MSK)
    # assert items[1]["workouts"] == 1 and items[0]["workouts"] == 0
```

### WR-02: Vacuous tautology assertion masquerading as a flag test

**File:** `apps/client-pwa/src/screens/sheets/CardSheet.wiring.test.jsx:78-108`
**Issue:** The test `'PROFILE_FEATURE_FLAGS.weeklyActivity is true'` sets up several
`vi.fn()` mocks and a `vi.doMock`, then never renders ProfileScreen or reads the flag — it
ends with `expect(true).toBe(true)`. The comment even admits "structural: if code compiled
+ hooked, flag is true." This asserts nothing about the flag value; if a future edit flips
`weeklyActivity` back to `false`, this test stays green. The `mod`, `PROFILE_FEATURE_FLAGS`,
and all the local mock fns are dead setup. This is a false-confidence test.
**Fix:** Either render `ProfileScreen` with mocked `@/data` and assert the
`"Активность за неделю"` heading is present (the actual observable consequence of the flag
being `true`), or delete the test. Do not ship a `expect(true).toBe(true)` gate.

### WR-03: Autopay-disable path re-opens the consent modal on `consent_required`

**File:** `apps/client-pwa/src/screens/sheets/ProfileExtraSheets.jsx:358-370`
**Issue:** `handleDisableAutopay` sends `{enabled:false, consentAcknowledged:false}`. In
its `catch`, if the backend returns `consent_required`, it calls
`setAutopayConsentOpen(true)` — popping the "Подключить автопродление?" (enable-autopay)
consent disclosure in response to a **disable** action. Disabling autopay never requires
consent (confirmed by the router doc: `409 consent_required` only fires "when enabling
without consent_acknowledged=True"), so this branch should be unreachable; but if it ever
fires (backend bug, contract drift), the user disabling autopay is shown an enable-consent
modal whose "Подключить" button would then *enable* autopay — the opposite of intent.
**Fix:** Drop the `consent_required` special-case from the disable handler; treat any error
on disable as the generic failure toast:
```js
const handleDisableAutopay = async () => {
  setAutopayError(null)
  try {
    await patchAutopay.mutateAsync({ enabled: false, consentAcknowledged: false })
  } catch {
    setAutopayError('Не удалось изменить автопродление. Попробуйте ещё раз.')
  }
}
```

### WR-04: `usePatchAutopay` success does not refetch membership view of autopay

**File:** `apps/client-pwa/src/lib/clientQueries.ts:732-751`
**Issue:** `usePatchAutopay.onSettled` invalidates only `clientPortalKeys.paymentMethod()`.
The membership hero in `ProfileScreen.jsx:199-211` renders an "Автопродление
Включено/Выключено" row driven by `useClientMembership()` (`membership.autoRenew`). After a
successful autopay enable/disable, the membership query is not invalidated, so that row can
display a stale autopay state until the 30s staleTime lapses or another trigger refetches.
(Today `autoRenew` is always `null` so the row is hidden — but the wiring is latent and
will surface incorrect state the moment `autoRenew` becomes non-null.)
**Fix:** Invalidate the membership/home keys alongside paymentMethod on autopay settle:
```js
onSettled: () => {
  void qc.invalidateQueries({ queryKey: clientPortalKeys.paymentMethod() })
  void qc.invalidateQueries({ queryKey: clientPortalKeys.membership() })
  void qc.invalidateQueries({ queryKey: clientPortalKeys.home() })
}
```

## Info

### IN-01: Dead component `ToggleRow` left behind after toggle removal

**File:** `apps/client-pwa/src/screens/sheets/ProfileExtraSheets.jsx:623-645`
**Issue:** The phase replaced both old `ToggleRow` instances with `AutopayToggleRow` and
removed the «Авто-оплата тренировок» row, but the `ToggleRow` function definition remains
with no callers anywhere in the PWA (`grep` confirms only the definition site). It is dead
code.
**Fix:** Delete the `ToggleRow` function (lines 623-645).

### IN-02: Weekly-activity `minutes` field count claim vs. schema

**File:** `apps/backend/app/modules/client_portal/schemas.py:390-401`
**Issue:** Minor doc/robustness: `minutes` is hardcoded `None` everywhere (service line
1059 passes `minutes=None`, repo never reads a duration column). This is intentional
(WACT-03 deferred) and the PWA types it as `minutes: null` (clientQueries.ts:678). No
defect, just confirming the contract is internally consistent. Consider a comment in the
repo `fetch_weekly_activity` noting the COUNT(*) is workouts-only so a future WACT-03
duration join does not silently double-count.
**Fix:** Optional comment only.

### IN-03: `useClientWeeklyActivity` has no `enabled` gate

**File:** `apps/client-pwa/src/lib/clientQueries.ts:682-691`
**Issue:** Unlike `useClientMembership`/`useClientMe`, the weekly-activity hook always
fires on mount with no `enabled` guard. On an unauthenticated ProfileScreen mount it will
issue a request that 401s. Harmless (it just errors and renders flat bars), but
inconsistent with the auth-gated hooks in the same file.
**Fix:** Optional — accept an `enabled = true` param mirroring `useClientMembership` if
ProfileScreen can mount pre-auth.

### IN-04: ФЗ-376 disclosure amount is non-specific

**File:** `apps/client-pwa/src/screens/sheets/ProfileExtraSheets.jsx:548-551`
**Issue:** The consent disclosure says "Сумма списания — стоимость текущего тарифа" rather
than a concrete ruble amount. For strict ФЗ-376 compliance the disclosure should ideally
state the exact charge amount; the generic phrasing relies on the client knowing their
current plan price. Acceptable for v1 (the amount is derivable from the membership hero on
the same flow), flagged for compliance awareness.
**Fix:** Optional — interpolate `formatMoney(membership.priceKopecks)` into the disclosure
when an active membership price is available.

---

_Reviewed: 2026-06-03T00:00:00Z_
_Reviewer: Claude (gsd-code-reviewer)_
_Depth: standard_

---
phase: 74-downloads-profile-html-downloads-settings-html
fixed_at: 2026-06-02T13:13:43Z
review_path: .planning/phases/74-downloads-profile-html-downloads-settings-html/74-REVIEW.md
iteration: 1
findings_in_scope: 6
fixed: 6
skipped: 0
status: all_fixed
---

# Phase 74: Code Review Fix Report

**Fixed at:** 2026-06-02T13:13:43Z
**Source review:** .planning/phases/74-downloads-profile-html-downloads-settings-html/74-REVIEW.md
**Iteration:** 1

**Summary:**
- Findings in scope: 6 (1 Critical + 5 Warning; Info findings IN-01..IN-03 out of scope)
- Fixed: 6
- Skipped: 0

All fixes were verified by running the full client-pwa Vitest suite inside the
isolated worktree (linked against the original install's `node_modules`):
**11 test files / 62 tests passed**, including the `toSubInfo` adapter and
identity tests that exercise the WR-05 extraction.

## Fixed Issues

### CR-01: `NavRow` uses `<div onClick>` — not keyboard accessible

**Files modified:** `apps/client-pwa/src/screens/SettingsScreen.jsx`
**Commit:** 1edbe2a4
**Applied fix:** Converted `NavRow` from a `<div onClick>` to a semantic
`<button type="button">` with `width: 100%`, transparent background, zero
border, `fontFamily: 'inherit'`, and `textAlign: 'left'` so the four Account
rows are now Tab-reachable and Enter/Space-activatable, picking up the
project's existing `button:focus-visible` ring.

### WR-01: Wrong skeleton shown for 320 ms when navigating to `/settings`

**Files modified:** `apps/client-pwa/src/App.jsx`
**Commit:** 67cebdcd
**Applied fix:** Added `'/settings': 'settings'` to `TAB_BY_PATH` so
`useTabFromRoute()` returns a stable `'settings'` value instead of falling back
to `'home'`, and extended `TabFallback` with `if (tab === 'settings') return
<SettingsSkeleton />;`. `SettingsSkeleton` was already imported. `PATH_BY_TAB`
was intentionally left unchanged — the tab bar is hidden on `/settings`, so no
tab-bar navigation path needs the reverse mapping.

### WR-02: Russian plural forms wrong for day values ≥ 21

**Files modified:** `apps/client-pwa/src/screens/ProfileScreen.jsx`
**Commit:** 9d67c11b
**Applied fix:** Added a `pluralDays(n)` helper implementing the full Russian
plural rule (mod100 11–14 → "дней"; mod10 1 → "день"; mod10 2–4 → "дня"; else
"дней"), then replaced both simplified ternaries (days-left badge and
elapsed-days caption). The "до\n<br/>продления" markup was preserved by
rendering `{pluralDays(sub.daysLeft)} до`.
**Note:** This is a logic-classified finding. The unit semantics were
confirmed by the passing adapter suite, but the human-facing plural output for
edge counts (0, 11–14, 21, 22) is flagged for a quick manual eyeball.

### WR-03: Money amounts displayed with raw `/100` and `toLocaleString`

**Files modified:** `apps/client-pwa/src/screens/ProfileScreen.jsx`
**Commit:** aa825036
**Applied fix:** Imported `formatMoney` from `@/utils/format.js` (the existing
client-pwa helper, not the path guessed in the review). Removed the
`const total = totalKopecks / 100` and `const amountRub = … / 100` divisions
and rendered the summary total as `{formatMoney(totalKopecks)}` and each row as
`{isRefund ? '+' : '−'}{formatMoney(Math.abs(p.amountKopecks))}`. `formatMoney`
takes kopecks directly and emits NBSP + ₽ via `Intl.NumberFormat`.

### WR-04: Toggle `SettingRow` has no accessibility role or label

**Files modified:** `apps/client-pwa/src/screens/SettingsScreen.jsx`
**Commit:** e69172e8
**Applied fix:** Added `role="switch"`, `aria-checked={value}`, and
`aria-label={label}` to the notification toggle `<button>` so screen readers
announce it as a switch with on/off state mirroring the adjacent label.

### WR-05: `toSubInfo` and `subTotalDays` duplicated across screens

**Files modified:** `apps/client-pwa/src/lib/membership.js` (new),
`apps/client-pwa/src/screens/ProfileScreen.jsx`,
`apps/client-pwa/src/screens/HomeScreen.jsx`
**Commit:** 56584ace
**Applied fix:** Created `@/lib/membership.js` as the single source of truth for
`toSubInfo` and `subTotalDays`. Both screens now `import { toSubInfo } from
'@/lib/membership.js'` and `export { toSubInfo }` (re-export) so the existing
`*.adapters.test.jsx` files that import `toSubInfo` from the screen modules keep
resolving without test changes. The duplicated function bodies were removed from
both screens. Verified: all 16 HomeScreen adapter tests + 2 ProfileScreen
adapter tests + identity tests pass against the extracted module.

## Skipped Issues

None.

---

_Fixed: 2026-06-02T13:13:43Z_
_Fixer: Claude (gsd-code-fixer)_
_Iteration: 1_

---
phase: 74-downloads-profile-html-downloads-settings-html
reviewed: 2026-06-02T00:00:00Z
depth: standard
files_reviewed: 5
files_reviewed_list:
  - apps/client-pwa/src/screens/SettingsScreen.jsx
  - apps/client-pwa/src/screens/ProfileScreen.jsx
  - apps/client-pwa/src/App.jsx
  - apps/client-pwa/src/components/skeletons.jsx
  - apps/client-pwa/src/styles.css
findings:
  critical: 1
  warning: 5
  info: 3
  total: 9
status: issues_found
---

# Phase 74: Code Review Report

**Reviewed:** 2026-06-02T00:00:00Z
**Depth:** standard
**Files Reviewed:** 5
**Status:** issues_found

## Summary

Phase 74 delivers a pass-style membership hero, a count-up stat strip, and a standalone `/settings` route with notification toggles. The React hooks, localStorage resilience, count-up RAF cleanup, and Suspense boundary wiring are all sound. The most serious issue is that `NavRow` in `SettingsScreen.jsx` is a `<div onClick>` rather than a `<button>`, making four account navigation rows inaccessible to keyboard users. Beyond that, there are wrong-skeleton flashes when navigating to `/settings`, incorrect Russian plural forms for day counts over 20, money formatted with raw division rather than `formatMoney()`, and two shared helpers (`toSubInfo` / `subTotalDays`) duplicated across screens.

---

## Critical Issues

### CR-01: `NavRow` uses `<div onClick>` — not keyboard accessible

**File:** `apps/client-pwa/src/screens/SettingsScreen.jsx:348-371`
**Issue:** `NavRow` is implemented as a plain `<div onClick>`. The four rows in the Account section ("Тариф и подписка", "Личные данные", "Помощь и FAQ", and the gated "Привязанная карта") are unreachable via Tab key, cannot be activated with Enter/Space, and have no `role` for assistive technology. The project's own CSS already defines `button:focus-visible` styles and suppresses raw `outline`, meaning there is a complete keyboard-navigation path for `<button>` elements but none for these divs.

**Fix:**
```jsx
function NavRow({ label, value, onClick }) {
  return (
    <button
      type="button"
      onClick={onClick}
      style={{
        padding: '14px 14px',
        display: 'flex',
        alignItems: 'center',
        gap: 12,
        cursor: 'pointer',
        width: '100%',
        background: 'transparent',
        border: 0,
        fontFamily: 'inherit',
        textAlign: 'left',
      }}
    >
      <div style={{ flex: 1 }} className="t-h3">{label}</div>
      {value && (
        <div className="t-small" style={{ color: 'var(--text-2)' }}>{value}</div>
      )}
      <Icon name="chevronRight" size={16} color="var(--text-3)" />
    </button>
  );
}
```

---

## Warnings

### WR-01: Wrong skeleton shown for 320 ms when navigating to `/settings`

**File:** `apps/client-pwa/src/App.jsx:73-92, 194-199, 254`
**Issue:** `useTabFromRoute()` maps `/settings` to `'home'` via the `TAB_BY_PATH` fallback (`|| 'home'`). `useTabLoading()` fires whenever `tab` changes, so navigating from `/profile` to `/settings` triggers `tab: 'profile' → 'home'`, which starts a 320 ms `tabLoading=true` window. During that window, `<TabFallback tab="home" />` renders `<HomeSkeleton />` — the wrong shape entirely — before the correct inner `<SettingsSkeleton />` takes over. The user briefly sees a home-shaped flash.

**Fix:**
Add `/settings` to `TAB_BY_PATH` so `useTabFromRoute` returns a stable value that `TabFallback` can use:
```js
const TAB_BY_PATH = {
  '/home': 'home',
  '/book': 'book',
  '/chat': 'chat',
  '/profile': 'profile',
  '/settings': 'settings',   // ← add
};
```
Then extend `TabFallback`:
```jsx
function TabFallback({ tab }) {
  if (tab === 'home') return <HomeSkeleton />;
  if (tab === 'profile') return <ProfileSkeleton />;
  if (tab === 'settings') return <SettingsSkeleton />;   // ← add
  return <ListSkeleton rows={5} withHero />;
}
```

### WR-02: Russian plural forms wrong for day values ≥ 21

**File:** `apps/client-pwa/src/screens/ProfileScreen.jsx:175, 191`
**Issue:** Both the "days left" badge and the "elapsed days" caption use the simplified ternary `=== 1 ? 'день' : < 5 ? 'дня' : 'дней'`. This is wrong for values 21, 31, 41 … (should be "день"), values 22–24, 32–34 … (should be "дня"), and value 0 (should be "дней" — rendered as "0 дня" today because `0 < 5` is true).

Concrete bad output today:
- 0 elapsed days → "Пройдено 0 дня" (wrong; should be "дней")
- 21 days remaining → "21 дней до продления" (wrong; should be "21 день")
- 22 days remaining → "22 дней до продления" (wrong; should be "22 дня")

**Fix:** Extract a proper Russian plural helper:
```js
// Returns the correct Russian plural form for integer N.
function pluralDays(n) {
  const abs = Math.abs(n);
  const mod10 = abs % 10;
  const mod100 = abs % 100;
  if (mod100 >= 11 && mod100 <= 14) return 'дней';
  if (mod10 === 1) return 'день';
  if (mod10 >= 2 && mod10 <= 4) return 'дня';
  return 'дней';
}
```
Then replace inline ternaries:
```jsx
// line 175
{sub.daysLeft} {pluralDays(sub.daysLeft)} до продления

// line 191
`Пройдено ${elapsedDays} ${pluralDays(elapsedDays)}`
```

### WR-03: Money amounts displayed with raw `/100` and `toLocaleString`, bypassing `formatMoney()`

**File:** `apps/client-pwa/src/screens/ProfileScreen.jsx:616, 628, 667, 703`
**Issue:** `PurchasesList` and `PurchaseRow` convert kopecks to rubles via `/ 100` and format with `(value).toLocaleString('ru-RU')`. The CLAUDE.md domain convention mandates `formatMoney(minor)` (which uses `Intl.NumberFormat('ru-RU', { currency: 'RUB' })` producing NBSPs and the ₽ symbol). The raw division + `toLocaleString` approach can emit a plain space or no space before the ₽, will not consistently format kopeck fractions, and diverges from every other money display in the codebase.

**Fix:**
```jsx
import { formatMoney } from '@/lib/money.js';   // adjust to actual path

// PurchasesList line 628 — "Потрачено всего"
{formatMoney(totalKopecks)}

// PurchaseRow line 703 — individual row amount
{isRefund ? '+' : '−'}{formatMoney(Math.abs(p.amountKopecks))}
```
Remove the `/ 100` divisions; `formatMoney` accepts kopecks directly.

### WR-04: Toggle `SettingRow` has no accessibility role or label

**File:** `apps/client-pwa/src/screens/SettingsScreen.jsx:310-346`
**Issue:** The notification toggle `<button>` renders as a plain button with no `role="switch"` and no `aria-checked` attribute. Screen readers will announce it as "button" with no on/off state. The project's `styles.css` has a complete `:focus-visible` ring system for buttons; the switch just needs semantic markup to be usable.

**Fix:**
```jsx
<button
  role="switch"
  aria-checked={value}
  aria-label={label}   // mirrors the adjacent text for AT users
  onClick={() => onChange(!value)}
  ...
>
```

### WR-05: `toSubInfo` and `subTotalDays` duplicated in `ProfileScreen.jsx` and `HomeScreen.jsx`

**File:** `apps/client-pwa/src/screens/ProfileScreen.jsx:31-59` / `apps/client-pwa/src/screens/HomeScreen.jsx:29-...`
**Issue:** Both screens define identical `toSubInfo` and `subTotalDays` functions. Any future fix to either (e.g., the WR-02 plural fix, or a change in API field name) must be applied twice. The comment in `ProfileScreen.jsx` already acknowledges this ("Mirrors the adapter in HomeScreen.jsx"), signalling the debt is known but unresolved.

**Fix:** Extract both functions to a shared module, e.g., `apps/client-pwa/src/lib/membership.js`, and import from both screens. Each screen already has a `ProfileScreen.adapters.test.jsx` / `HomeScreen.adapters.test.jsx` test file — they can share the same test suite against the extracted module.

---

## Info

### IN-01: `Divider2` duplicates existing `Divider` from `RowItem.jsx`

**File:** `apps/client-pwa/src/screens/SettingsScreen.jsx:373-375`
**Issue:** `Divider2` is a one-line function that is visually identical to `Divider` exported from `apps/client-pwa/src/components/RowItem.jsx`. The "2" suffix and file-local definition suggest it was copy-pasted. Six call sites in the same file could simply use the shared component.

**Fix:**
```jsx
import { Divider } from '@/components/RowItem.jsx';
// Remove the local Divider2 function and replace all 6 call sites.
```

### IN-02: Version string `"Версия 2.4.1"` is hardcoded and disagrees with `package.json`

**File:** `apps/client-pwa/src/screens/SettingsScreen.jsx:301`
**Issue:** The footer line reads `"Версия 2.4.1 · Мой зал"` but `apps/client-pwa/package.json` declares `version: "0.0.1"`. One of these will become stale at every release. The version shown to users should come from a single source of truth.

**Fix:**
```jsx
// vite.config.js: expose version via define
import pkg from './package.json'
define: { __APP_VERSION__: JSON.stringify(pkg.version) }

// SettingsScreen.jsx
<div ...>Версия {__APP_VERSION__} · Мой зал</div>
```
Or read from `import.meta.env.VITE_APP_VERSION` if that's already in the Vite config.

### IN-03: Toggle knob uses hardcoded `'#fff'` instead of `var(--surface)`

**File:** `apps/client-pwa/src/screens/SettingsScreen.jsx:338`
**Issue:** The toggle thumb uses `background: '#fff'`. In dark mode, the toggle pill background is `var(--border-strong)` (a warm stone color), and a pure white `#fff` thumb creates a harsher contrast than the `var(--surface)` (`#221f1d`-based) white the rest of the UI uses. The styles.css comment pattern for this codebase explicitly limits raw hexes to UI-SPEC-sanctioned values (`#06120c`, `#a36a16`); `#fff` is not in that list.

**Fix:**
```jsx
background: 'var(--surface)',
```

---

_Reviewed: 2026-06-02T00:00:00Z_
_Reviewer: Claude (gsd-code-reviewer)_
_Depth: standard_

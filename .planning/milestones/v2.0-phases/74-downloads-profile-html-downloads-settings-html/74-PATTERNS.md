# Phase 74: Обновить экраны «Профиль» и «Настройки» — Pattern Map

**Mapped:** 2026-06-02
**Files analyzed:** 5 new/modified files
**Analogs found:** 5 / 5

---

## File Classification

| New/Modified File | Role | Data Flow | Closest Analog | Match Quality |
|---|---|---|---|---|
| `apps/client-pwa/src/screens/ProfileScreen.jsx` | screen (restyled) | request-response, CRUD-read | self (existing file) | exact — modify in place |
| `apps/client-pwa/src/screens/SettingsScreen.jsx` | screen (new) | request-response | `ProfileScreen.jsx` `SettingsList` component (lines 440–509) | role-match (extracted component → full screen) |
| `apps/client-pwa/src/App.jsx` | router/shell | request-response | self `ProfileRoute` (lines 157–174), `hideTabBar` (line 226) | exact — add alongside existing patterns |
| `apps/client-pwa/src/components/skeletons.jsx` | UI utility | transform | `ProfileSkeleton` (lines 72–93) | role-match (new `SettingsSkeleton` modelled on `ProfileSkeleton`) |
| `apps/client-pwa/src/context/TweaksContext.jsx` | context/provider | event-driven | self (theme via `data-theme` read-only) | exact — no changes needed |

---

## Pattern Assignments

### `apps/client-pwa/src/screens/ProfileScreen.jsx` (restyled screen)

**Analog:** self — modify in place. Key excerpts below give the before-state to diff against.

**Feature-flag scaffolding to ADD at module top** — copy 1:1 from `CheckoutSheet.jsx` lines 32–48:

```jsx
// ─── Deferred-feature scaffolding (BUILT, HIDDEN) ─────────────────────────
// Flip a flag to true when the corresponding backend data lands.
//
//  • weeklyActivity — activity bars card (needs workout minutes/type per day)
//  • tenureBadge    — "PREMIUM · N ЛЕТ" badge (needs tier + tenure from API)
//  • weeksStat      — third stat strip cell "N недель" (needs tenure data)
//  • linkedCard     — "Привязанная карта •••• 4821" row in Settings (needs card-on-file)
const PROFILE_FEATURE_FLAGS = {
  weeklyActivity: false,
  tenureBadge:    false,
  weeksStat:      false,
  linkedCard:     false,
};
```

**Gate pattern** (from `CheckoutSheet.jsx` usage downstream of the flags):
```jsx
{PROFILE_FEATURE_FLAGS.weeklyActivity && (
  <WeeklyActivityCard />
)}
{PROFILE_FEATURE_FLAGS.tenureBadge && (
  <span className="badge">...</span>
)}
{PROFILE_FEATURE_FLAGS.weeksStat && (
  <StatCell label="недель" value={tenure?.weeks ?? 0} />
)}
```

**`toSubInfo` / `subTotalDays` adapter — REUSE unchanged** (lines 18–46):
```jsx
export function toSubInfo(membership) {
  if (!membership) {
    return { daysLeft: 0, total: 0, until: '—', label: 'Нет абонемента', tone: 'danger' };
  }
  const daysLeft = Math.max(0, membership.daysUntilEnd ?? 0);
  const tone = membership.expiringSoon
    ? (daysLeft === 0 ? 'danger' : 'warn')
    : 'ok';
  return {
    daysLeft,
    total: subTotalDays(membership.startDate, membership.endDate),
    until: membership.endDate ?? '—',
    label: membership.planNameSnapshot ?? 'Абонемент',
    tone,
  };
}

function subTotalDays(startDate, endDate) {
  if (!startDate || !endDate) return 0;
  const start = Date.parse(`${startDate}T00:00:00Z`);
  const end   = Date.parse(`${endDate}T00:00:00Z`);
  if (Number.isNaN(start) || Number.isNaN(end)) return 0;
  return Math.max(0, Math.round((end - start) / 86_400_000));
}
```

**Membership-hero CSS variables** — `--mh-*` theme-flip from `Profile.html` (light → dark graphite, dark → beige):
```css
/* add to apps/client-pwa/src/styles.css or inline on the hero div */
.membership-hero {
  --mh-text: #f3f1ea;
  --mh-text-2: rgba(255,255,255,0.62);
  --mh-text-3: rgba(255,255,255,0.45);
  --mh-track: rgba(255,255,255,0.10);
  --mh-divider: rgba(255,255,255,0.12);
  --mh-accent: var(--accent);
  --mh-ghost-bg: rgba(255,255,255,0.08);
  --mh-ghost-border: rgba(255,255,255,0.16);
  --mh-cta-bg: var(--accent);
  --mh-cta-fg: #06120c;
  background: #0e0e0e !important;
  border-color: rgba(255,255,255,0.14) !important;
}
[data-theme="dark"] .membership-hero {
  --mh-text: #1a1511;
  --mh-text-2: #6f6453;
  --mh-text-3: #9c8c72;
  --mh-track: rgba(26,21,17,0.09);
  --mh-cta-bg: #0f9b76;
  --mh-cta-fg: #ffffff;
  --mh-ghost-bg: rgba(255,255,255,0.55);
  --mh-ghost-border: #ddccb2;
  background: #ece0cd !important;
  border-color: #ddccb2 !important;
}
```
Note: the mockup uses `body.dark` class toggle; the PWA uses `data-theme` on `<html>` (from `TweaksContext.jsx` line 27). Use `[data-theme="dark"]` selector, not `.dark`.

**Gear button → navigate** — add to identity card section:
```jsx
import { useNavigate } from 'react-router-dom';
// inside ProfileScreen component:
const navigate = useNavigate();
// in identity card JSX:
<button
  onClick={() => navigate('/settings')}
  aria-label="Настройки"
  className="press"
  style={{
    flexShrink: 0, width: 38, height: 38, borderRadius: 999, padding: 0,
    cursor: 'pointer', background: 'var(--surface-2)',
    border: '0.5px solid var(--border-strong)',
    display: 'inline-flex', alignItems: 'center', justifyContent: 'center',
  }}
>
  <Icon name="settings" size={19} color="var(--text)" strokeWidth={2} />
</button>
```

**Tabs — remove `settings`, keep 3** (current lines 224–239 show all 4 tabs; the `id: 'settings'` entry and its corresponding `{tab === 'settings' && ...}` panel are deleted):
```jsx
// BEFORE (lines 225–230):
[
  { id: 'visits',    label: 'Визиты' },
  { id: 'trainings', label: 'Тренировки' },
  { id: 'purchases', label: 'Покупки' },
  { id: 'settings',  label: 'Настройки' },   // ← DELETE
]

// AFTER:
[
  { id: 'visits',    label: 'Визиты' },
  { id: 'trainings', label: 'Тренировки' },
  { id: 'purchases', label: 'Покупки' },
]
```

**Stat strip — 2 cells + optional gated 3rd** (from `Profile.html` lines 403–419):
```jsx
<div className="card" style={{ padding: 4, display: 'flex', overflow: 'hidden' }}>
  <StatCell label="визитов"    value={visitData?.total ?? 0} />
  <StatDivider />
  <StatCell label="тренировки" value={ptData?.total ?? 0} />
  {PROFILE_FEATURE_FLAGS.weeksStat && (
    <>
      <StatDivider />
      <StatCell label="недель" value={tenureWeeks} />
    </>
  )}
</div>
```

**Data hooks already imported** (lines 7–13 of `ProfileScreen.jsx`):
```jsx
import {
  useClientHome,
  useClientMe,
  useClientVisitHistory,
  useClientPtHistory,
  useClientPaymentHistory,
} from '@/data';
```
Add `useClientVisitHistory` and `useClientPtHistory` results to stat strip (`.total` field).

---

### `apps/client-pwa/src/screens/SettingsScreen.jsx` (new screen)

**Analog:** `ProfileScreen.jsx` `SettingsList` component (lines 440–509) + `ProfileExtraSheets.jsx` structure.

**Screen shell pattern** — copy from `ProfileScreen.jsx` outer wrapper (lines 66–70) + add back-header like `SubSheetHeader` from `ProfileExtraSheets.jsx` lines 7–36:

```jsx
import React from 'react';
import { useNavigate } from 'react-router-dom';
import { Avatar } from '@/components/Avatar.jsx';
import { Icon } from '@/components/Icon.jsx';
import { StatusBar } from '@/components/StatusBar.jsx';
import { useClientMe } from '@/data';
import { useAuth } from '@/context/AuthContext.jsx';

// ─── Deferred-feature scaffolding (BUILT, HIDDEN) ─────────────────────────
// See ProfileScreen.jsx PROFILE_FEATURE_FLAGS for the master flag object.
// SettingsScreen reads the same flags from a shared import (or re-declares
// linkedCard locally if PROFILE_FEATURE_FLAGS lives in ProfileScreen).
const SETTINGS_FEATURE_FLAGS = {
  linkedCard: false,   // "Привязанная карта •••• 4821" row (needs card-on-file API)
  tenureBadge: false,  // "PREMIUM · N ЛЕТ" identity badge
};

export const SettingsScreen = ({
  tweaks, setTweak,
  onOpenPlans, onOpenPersonalData, onOpenCard, onOpenFAQ,
}) => {
  const navigate = useNavigate();
  const { data: me } = useClientMe();
  const { logout } = useAuth();

  // ── Notification prefs — local persist, no server send (D-74-04) ──
  const NOTIF_STORAGE_KEY = 'clubcore:notif:v1';
  const NOTIF_DEFAULTS = { promo: true, schedule: true, trainer: true, sound: false };
  const [notif, setNotif] = React.useState(() => {
    try {
      return { ...NOTIF_DEFAULTS, ...JSON.parse(localStorage.getItem(NOTIF_STORAGE_KEY) || '{}') };
    } catch { return NOTIF_DEFAULTS; }
  });
  const setNotifKey = (key, val) => {
    const next = { ...notif, [key]: val };
    setNotif(next);
    try { localStorage.setItem(NOTIF_STORAGE_KEY, JSON.stringify(next)); } catch { /* noop */ }
  };

  const handleBack = () => {
    if (window.history.length > 1) window.history.back();
    else navigate('/profile');
  };

  const fullName = `${me?.firstName ?? ''} ${me?.lastName ?? ''}`.trim();
  const displayName = me?.firstName || tweaks?.userName || '';

  return (
    <div className="page">
      <StatusBar />
      {/* Header with back button — mirrors Settings.html .header/.hbtn/.htitle */}
      <div style={{
        position: 'relative', flexShrink: 0,
        height: 52, padding: '0 12px',
        display: 'flex', alignItems: 'center', justifyContent: 'space-between',
        gap: 8,
      }}>
        <button onClick={handleBack} aria-label="Назад" className="press" style={{
          width: 36, height: 36, borderRadius: 999,
          border: '0.5px solid var(--border)', background: 'var(--surface)',
          boxShadow: 'var(--sh-1)',
          display: 'inline-flex', alignItems: 'center', justifyContent: 'center',
          color: 'var(--text)', cursor: 'pointer', padding: 0,
        }}>
          <Icon name="chevronLeft" size={18} color="var(--text)" strokeWidth={2.2} />
        </button>
        <span className="t-h3" style={{
          position: 'absolute', left: '50%', top: '50%',
          transform: 'translate(-50%, -50%)',
          fontSize: 17, pointerEvents: 'none', whiteSpace: 'nowrap',
        }}>Настройки</span>
        <div style={{ width: 36 }} />
      </div>

      <div className="scroller" style={{ paddingTop: 0, padding: '0 16px 28px' }}>
        {/* Identity strip */}
        {/* ... avatar + name + gated SETTINGS_FEATURE_FLAGS.tenureBadge badge ... */}

        {/* Appearance */}
        {/* theme seg — calls setTweak('theme', 'light'|'dark') like SettingsList */}

        {/* Notifications — 4 toggles persisted to NOTIF_STORAGE_KEY */}

        {/* Account */}
        {/* NavRow: Тариф → onOpenPlans */}
        {/* NavRow: Привязанная карта — SETTINGS_FEATURE_FLAGS.linkedCard && (...) */}
        {/* NavRow: Личные данные → onOpenPersonalData */}
        {/* NavRow: Помощь и FAQ → onOpenFAQ */}

        {/* Logout */}
        <button className="btn" onClick={() => { void logout(); }} style={{
          marginTop: 22, width: '100%', height: 50,
          background: 'transparent', color: 'var(--danger)',
          border: '0.5px solid var(--border-strong)',
        }}>
          <Icon name="logout" size={18} color="var(--danger)" strokeWidth={2} />
          Выйти из аккаунта
        </button>

        <div className="t-small" style={{ textAlign: 'center', color: 'var(--text-3)', marginTop: 16 }}>
          Версия 2.4.1 · Мой зал
        </div>
      </div>
    </div>
  );
};
```

**SettingRow (toggle) pattern** — copy unchanged from `ProfileScreen.jsx` lines 511–530:
```jsx
function SettingRow({ label, value, onChange }) {
  return (
    <div style={{ padding: '12px 14px', display: 'flex', alignItems: 'center', gap: 12 }}>
      <div style={{ flex: 1 }} className="t-h3">{label}</div>
      <button onClick={() => onChange(!value)} style={{
        width: 44, height: 26, borderRadius: 999, border: 0, padding: 0,
        background: value ? 'var(--accent)' : 'var(--border-strong)',
        cursor: 'pointer', position: 'relative',
        transition: 'background 0.15s',
      }}>
        <span style={{
          position: 'absolute', top: 2, left: value ? 20 : 2,
          width: 22, height: 22, borderRadius: 999, background: '#fff',
          boxShadow: '0 1px 3px rgba(0,0,0,0.25)',
          transition: 'left 0.18s ease',
        }} />
      </button>
    </div>
  );
}
```

**NavRow pattern** — copy from `ProfileScreen.jsx` lines 532–540:
```jsx
function NavRow({ label, value, onClick }) {
  return (
    <div onClick={onClick} style={{
      padding: '14px 14px', display: 'flex', alignItems: 'center', gap: 12, cursor: 'pointer',
    }}>
      <div style={{ flex: 1 }} className="t-h3">{label}</div>
      {value && <div className="t-small" style={{ color: 'var(--text-2)' }}>{value}</div>}
      <Icon name="chevronRight" size={16} color="var(--text-3)" />
    </div>
  );
}
```

**Notification localStorage persist pattern** — modelled on `Settings.html` lines 413–425 but adapted to PWA storage key convention (`clubcore:notif:v1`, not `myzal_notif`):
```jsx
const NOTIF_STORAGE_KEY = 'clubcore:notif:v1';
const NOTIF_DEFAULTS = { promo: true, schedule: true, trainer: true, sound: false };
// init from localStorage with graceful fallback:
const [notif, setNotif] = React.useState(() => {
  try {
    return { ...NOTIF_DEFAULTS, ...JSON.parse(localStorage.getItem(NOTIF_STORAGE_KEY) || '{}') };
  } catch { return NOTIF_DEFAULTS; }
});
// persist on change:
const setNotifKey = (key, val) => {
  const next = { ...notif, [key]: val };
  setNotif(next);
  try { localStorage.setItem(NOTIF_STORAGE_KEY, JSON.stringify(next)); } catch { /* noop */ }
};
```

---

### `apps/client-pwa/src/App.jsx` (route additions + hideTabBar)

**Analog:** self — two existing patterns to replicate/extend.

**1. Lazy import + SettingsRoute wrapper** — copy `ProfileScreen` lazy import pattern (lines 40–41) and `ProfileRoute` wrapper shape (lines 157–174):
```jsx
// Add alongside ProfileScreen lazy import (line 40):
const SettingsScreen = lazy(() =>
  import('@/screens/SettingsScreen.jsx').then(m => ({ default: m.SettingsScreen }))
);

// Add SettingsRoute after ProfileRoute (after line 174):
function SettingsRoute() {
  const { t, setTweak } = useTweaksCtx();
  const ui = useUI();
  return (
    <SettingsScreen
      tweaks={t}
      setTweak={setTweak}
      onOpenPlans={() => ui.setPlansOpen(true)}
      onOpenPersonalData={() => ui.setPersonalOpen(true)}
      onOpenCard={() => ui.setCardOpen(true)}
      onOpenFAQ={() => ui.setFaqOpen(true)}
    />
  );
}
```

**2. hideTabBar** — extend line 226 to include `/settings`:
```jsx
// BEFORE (line 224–227):
const isLoginRoute = pathname === '/login';
const isOnboardingRoute = pathname === '/onboarding';
const isPaymentReturnRoute = pathname === '/payment/return';
const hideTabBar = ui.anySheetOpen || ui.chatThreadOpen || ui.bookConfirmOpen
  || isLoginRoute || isOnboardingRoute || isPaymentReturnRoute
  || status === 'unknown' || status === 'anon';

// AFTER — add isSettingsRoute:
const isLoginRoute = pathname === '/login';
const isOnboardingRoute = pathname === '/onboarding';
const isPaymentReturnRoute = pathname === '/payment/return';
const isSettingsRoute = pathname === '/settings';
const hideTabBar = ui.anySheetOpen || ui.chatThreadOpen || ui.bookConfirmOpen
  || isLoginRoute || isOnboardingRoute || isPaymentReturnRoute || isSettingsRoute
  || status === 'unknown' || status === 'anon';
```

**3. Route element** — add after `/profile` route (line 245), matching identical `RequireAuth` + `Suspense` wrapper pattern:
```jsx
// Add after line 245:
<Route path="/settings" element={<RequireAuth><SettingsRoute /></RequireAuth>} />
```

**4. TabFallback skeleton** — add `SettingsSkeleton` for `/settings` path:
```jsx
// BEFORE (lines 177–181):
function TabFallback({ tab }) {
  if (tab === 'home')    return <HomeSkeleton />;
  if (tab === 'profile') return <ProfileSkeleton />;
  return <ListSkeleton rows={5} withHero />;
}

// AFTER — note: /settings is not a tab so TabFallback is not called for it;
// use Suspense fallback={<SettingsSkeleton />} on the SettingsRoute Suspense boundary,
// or reuse <ProfileSkeleton /> as the Suspense fallback for the /settings route chunk.
```

---

### `apps/client-pwa/src/components/skeletons.jsx` (add `SettingsSkeleton`)

**Analog:** `ProfileSkeleton` (lines 72–93) — same structure with a back-button header instead of the profile avatar header.

```jsx
// Add after ProfileSkeleton (after line 93):
export function SettingsSkeleton() {
  return (
    <div className="page">
      {/* Header row: back button + centered title */}
      <div style={{ padding: '0 12px', height: 52, display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
        <div className="sk sk-circle" style={{ width: 36, height: 36 }} />
        <SkLine w={80} h={14} />
        <div style={{ width: 36 }} />
      </div>
      {/* Identity strip */}
      <div style={{ padding: '8px 20px 16px', display: 'flex', alignItems: 'center', gap: 14 }}>
        <SkCircle size={62} />
        <div style={{ flex: 1, display: 'flex', flexDirection: 'column', gap: 8 }}>
          <SkLine w="50%" h={16} />
          <SkLine w="30%" h={11} />
        </div>
      </div>
      {/* Section rows */}
      <div style={{ padding: '0 16px', display: 'flex', flexDirection: 'column', gap: 10 }}>
        <SkLine w={80} h={10} style={{ marginBottom: 4 }} />
        <SkBlock h={52} r={16} />
        <SkLine w={100} h={10} style={{ marginTop: 6, marginBottom: 4 }} />
        <SkBlock h={180} r={16} />
        <SkLine w={60} h={10} style={{ marginTop: 6, marginBottom: 4 }} />
        <SkBlock h={160} r={16} />
      </div>
    </div>
  );
}
```

---

## Shared Patterns

### Theme application — `data-theme` NOT `.dark` class
**Source:** `apps/client-pwa/src/context/TweaksContext.jsx` lines 26–27
**Apply to:** All new CSS selectors for `.membership-hero` dark variant, identity badge, etc.
```jsx
// TweaksContext sets:
r.setAttribute('data-theme', t.theme || 'light');
// Therefore use [data-theme="dark"] .membership-hero { ... }
// NOT body.dark .membership-hero { ... }  (that's the HTML mockup's pattern — do not copy)
```

### Seg-control (theme picker)
**Source:** `ProfileScreen.jsx` `SettingsList` lines 449–465
**Apply to:** Appearance section of `SettingsScreen`
```jsx
<div className="seg" style={{ padding: 3 }}>
  <button
    className={`seg-item ${(tweaks?.theme || 'light') === 'light' ? 'active' : ''}`}
    onClick={() => setTweak('theme', 'light')}
    style={{ padding: '0 14px' }}
  >Светлая</button>
  <button
    className={`seg-item ${tweaks?.theme === 'dark' ? 'active' : ''}`}
    onClick={() => setTweak('theme', 'dark')}
    style={{ padding: '0 14px' }}
  >Тёмная</button>
</div>
```

### Logout pattern
**Source:** `ProfileScreen.jsx` `SettingsList` lines 491–503; `useAuth` from `@/context/AuthContext.jsx`
**Apply to:** `SettingsScreen` logout button
```jsx
const { logout } = useAuth();
// onClick:
onClick={() => { void logout(); }}
```

### Feature flag object (canonical)
**Source:** `apps/client-pwa/src/screens/sheets/CheckoutSheet.jsx` lines 32–48
**Apply to:** Top of `ProfileScreen.jsx` (new `PROFILE_FEATURE_FLAGS`) and top of `SettingsScreen.jsx` (new `SETTINGS_FEATURE_FLAGS`)
```jsx
// ─── Deferred-feature scaffolding (BUILT, HIDDEN) ─────────────────────────
// Comment block explains what each flag unlocks and why it is currently off.
const CHECKOUT_FEATURE_FLAGS = {
  recommendedPromo: false,
  clubBonuses:      false,
};
// Gate usage: {CHECKOUT_FEATURE_FLAGS.clubBonuses && (<ClubBonusesRow />)}
```

### Card + section label layout
**Source:** `ProfileScreen.jsx` `SettingsList` lines 444–447 and `ProfileExtraSheets.jsx` lines 104–107
**Apply to:** Every section in `SettingsScreen`
```jsx
<div className="t-mini" style={{ color: 'var(--text-3)', padding: '4px 4px 8px' }}>
  Внешний вид
</div>
<div className="card" style={{ padding: 4 }}>
  {/* rows */}
</div>
```

### Row divider within card
**Source:** `ProfileScreen.jsx` `Divider2` (lines 542–544) / `ProfileExtraSheets.jsx` `Divider3` (line 174–176)
**Apply to:** All multi-row cards in `SettingsScreen`
```jsx
function Divider() {
  return <div style={{ height: 0.5, background: 'var(--border)', marginLeft: 14 }} />;
}
```

### RequireAuth route wrapper
**Source:** `apps/client-pwa/src/App.jsx` line 244
**Apply to:** `/settings` route
```jsx
<Route path="/settings" element={<RequireAuth><SettingsRoute /></RequireAuth>} />
```

---

## No Analog Found

All files have close analogs. No file requires purely RESEARCH.md–based patterns.

---

## Metadata

**Analog search scope:** `apps/client-pwa/src/screens/`, `apps/client-pwa/src/context/`, `apps/client-pwa/src/components/`, `apps/client-pwa/src/App.jsx`
**Files scanned:** 8 (ProfileScreen.jsx, CheckoutSheet.jsx, ProfileExtraSheets.jsx, App.jsx, skeletons.jsx, TweaksContext.jsx, UIContext.jsx, clientQueries.ts)
**Design mockups read:** Profile.html, Settings.html
**Pattern extraction date:** 2026-06-02

---
phase: 73-downloads-home-html
reviewed: 2026-06-02T00:00:00Z
depth: standard
files_reviewed: 3
files_reviewed_list:
  - apps/client-pwa/src/screens/HomeScreen.jsx
  - apps/client-pwa/src/styles.css
  - apps/client-pwa/src/screens/HomeScreen.identity.test.jsx
findings:
  critical: 2
  warning: 3
  info: 2
  total: 7
status: issues_found
---

# Phase 73: Code Review Report

**Reviewed:** 2026-06-02
**Depth:** standard
**Files Reviewed:** 3
**Status:** issues_found

## Summary

Reviewed the pure visual restyle of `HomeScreen.jsx` (active/lapsed branch), the `styles.css` keyframe additions, and the realigned identity test. The CSS changes are correct and minimal. The test realignment is accurate. The JSX restyle is largely sound — real API data flows correctly, no demo-only imports (NOTIFICATIONS/UPCOMING_BOOKING/getSubInfo) leaked in, no `setInterval` or `Math.random`, and the App.jsx prop contract is preserved.

Two critical issues were found: a referenced but never-defined `SubCardPremium` component (latent crash if `subCardStyle` is ever set to `'ring'`), and broken `ChatTile` dot animation (`className="chat-dot"` applied where no CSS class exists — only the `@keyframes` is defined, not a class selector). Three warnings cover dead code from the restyle and an unused prop.

---

## Critical Issues

### CR-01: `SubCardPremium` referenced in `HomeClassic` but never defined — latent `ReferenceError`

**File:** `apps/client-pwa/src/screens/HomeScreen.jsx:1354-1356`
**Issue:** `HomeClassic` contains:
```jsx
{subCardStyle === 'ring'
  ? <SubCardPremium sub={sub} pct={pct} onOpenPlans={onOpenPlans} />
  : <SubCardSpot sub={sub} pct={pct} userName={userName} onOpenPlans={onOpenPlans} />}
```
`SubCardPremium` is not defined anywhere in the file (not in the pre-restyle baseline either). If `tweaks.subCardStyle` is ever set to `'ring'` — possible via direct `localStorage` edit or a future tweaks panel option — React will throw `ReferenceError: SubCardPremium is not defined` and crash the screen.

The plan explicitly says: "If SubCardPremium is not present in prod, port it from mockup L614-700 OR simply always render SubCardSpot." The executor chose to add the branch without providing the implementation or removing the unreachable arm.

**Fix:** Remove the dead `'ring'` branch entirely and always render `SubCardSpot` (the canonical default per D-05), since `SubCardPremium` does not exist:
```jsx
{/* Subscription card — canonical SubCardSpot dark club-card (D-05/D-06) */}
<SubCardSpot sub={sub} pct={pct} userName={userName} onOpenPlans={onOpenPlans} />
```
If the `'ring'`/`SubCardPremium` variant is desired later, it must be ported from `mockup-src/screens/HomeScreen.jsx` lines 614-700 at that time.

---

### CR-02: `ChatTile` typing-dot animation is broken — `className="chat-dot"` has no CSS class definition

**File:** `apps/client-pwa/src/screens/HomeScreen.jsx:1311`
**Issue:** The new `ChatTile` component renders its three typing dots as:
```jsx
<span key={i} className="chat-dot" style={{
  width: 6, height: 6, borderRadius: 999, background: 'var(--accent)',
  opacity: 1 - i * 0.28, animationDelay: (i * 0.2) + 's',
}} />
```
`className="chat-dot"` is the only source of the animation. However, `styles.css` defines only `@keyframes chat-dot { ... }` — there is no `.chat-dot` CSS class rule. Without a class rule that sets `animation: chat-dot 1.4s ease-in-out infinite`, the class name does nothing and the dots are static.

Contrast with the pre-existing `HomeNewbie` chat tile (line 1056) which correctly applies the animation via inline style:
```jsx
animation: 'chat-dot 1.4s ease-in-out infinite',
animationDelay: `${delay}s`,
```
The plan says "port ChatTile from mockup L1127-1164 EXCEPT delete the inline `<style>` block (chat-dot already in styles.css)." The mockup had an inline `<style>` that defined both the `@keyframes` and a `.chat-dot { animation: ... }` class rule. Only the `@keyframes` survived the move to `styles.css`; the class selector was dropped.

**Fix — option A** (minimal): Add a `.chat-dot` class rule to `styles.css` adjacent to the existing `@keyframes chat-dot` block:
```css
/* chat-dot: typing bubble dots bounce */
@keyframes chat-dot {
  0%, 100% { transform: translateY(0); }
  50%      { transform: translateY(-3px); }
}
.chat-dot {
  animation: chat-dot 1.4s ease-in-out infinite;
}
```

**Fix — option B** (self-contained): Drop `className="chat-dot"` and apply animation inline, matching the working `HomeNewbie` pattern:
```jsx
{[0, 1, 2].map(i => (
  <span key={i} style={{
    width: 6, height: 6, borderRadius: 999, background: 'var(--accent)',
    opacity: 1 - i * 0.28,
    animation: 'chat-dot 1.4s ease-in-out infinite',
    animationDelay: (i * 0.2) + 's',
  }} />
))}
```

---

## Warnings

### WR-01: `greeting` variable computed and passed to `HomeNewbie` but silently ignored — dead code

**File:** `apps/client-pwa/src/screens/HomeScreen.jsx:284-333`
**Issue:** `greeting` is still computed at line 284:
```js
const greeting = (() => {
  const h = 9; // demo time
  if (h < 5) return 'Доброй ночи';
  if (h < 12) return 'Доброе утро';
  ...
})();
```
It is then passed to `HomeNewbie` at line 333:
```jsx
greeting={greeting}
```
But `HomeNewbie`'s function signature (line 853) does not destructure `greeting`:
```js
export function HomeNewbie({ me, homeData, bookings, userName, isDark, onOpenPlans, onOpenGymInfo, onOpenNotifications, onTab, onOpenOnboarding })
```
Before this restyle, `greeting` was rendered in the non-newbie header (the old inline greeting+pill block). The restyle removed that header and replaced it with `HomeHeroCard`, but did not clean up the now-dead `greeting` computation or its prop passing.

The computation also contains `const h = 9; // demo time` — a hardcoded hour that was a legacy placeholder. Since `greeting` is no longer rendered anywhere, this is pure dead code.

**Fix:** Remove the `greeting` computation block and the `greeting={greeting}` prop:
```js
// Delete lines 284-290 (the greeting IIFE)
// Remove greeting={greeting} from the HomeNewbie call at line 333
```
`HomeNewbie` has no display use for a greeting string in v2; it derives its header content from `me.firstName` and GYM_INFO directly.

---

### WR-02: `SubCardSpot` accepts `userName` prop but never renders it — unused parameter

**File:** `apps/client-pwa/src/screens/HomeScreen.jsx:1161`
**Issue:**
```js
export function SubCardSpot({ sub, pct, userName = '', onOpenPlans }) {
```
`userName` is accepted but nowhere in the JSX body of `SubCardSpot` (lines 1167-1253) is it rendered or used. The prop is passed through the chain: `HomeScreen` → `HomeClassic` → `SubCardSpot`, carrying real API data all the way to a dead end.

The mockup source (`mockup-src/screens/HomeScreen.jsx:722`) has the same unused parameter — it was reserved for a future "embossed cardholder name" feature. Since the feature is not implemented, the parameter is dead code that misleads callers into thinking it affects rendering.

**Fix (short-term):** Document the intent with a TODO so callers understand the prop is a placeholder:
```js
export function SubCardSpot({ sub, pct, userName = '', onOpenPlans }) {
  // TODO: userName reserved for embossed cardholder name on the dark card (not yet rendered)
```
**Fix (if not implementing):** Remove the parameter and all its call-site passing until the feature is built.

---

### WR-03: `bellBtn` and `gymTitle` buttons in `HomeHeroCard` missing `type="button"`

**File:** `apps/client-pwa/src/screens/HomeScreen.jsx:160, 207`
**Issue:** Both interactive buttons in `HomeHeroCard` omit `type="button"`:
```jsx
const bellBtn = (
  <button onClick={onOpenNotifications} className="press" aria-label="Уведомления" ...>
```
```jsx
const gymTitle = (
  <button onClick={onOpenGymInfo} className="press" ...>
```
Without an explicit `type`, HTML buttons default to `type="submit"`. If `HomeHeroCard` is ever wrapped in a `<form>` element (e.g., during a future refactor or if the shell changes), these buttons will submit the form instead of firing their handlers.

The rest of the file uses `type="button"` consistently (e.g., HomeNewbie bell at line 890, stagger tile at line 980, `HeroNewbie` tariff buttons at line 519, `OnboardingStrip` dismiss at line 676). The inconsistency here is introduced by this phase.

**Fix:**
```jsx
const bellBtn = (
  <button type="button" onClick={onOpenNotifications} className="press" aria-label="Уведомления" ...>
```
```jsx
const gymTitle = (
  <button type="button" onClick={onOpenGymInfo} className="press" ...>
```

---

## Info

### IN-01: Incomplete Russian day-count pluralization in `SubCardSpot`

**File:** `apps/client-pwa/src/screens/HomeScreen.jsx:1165`
**Issue:** The unit string for `sub.daysLeft` uses a simplified three-bucket rule:
```js
const unit = sub.daysLeft === 1 ? 'день' : (sub.daysLeft > 1 && sub.daysLeft < 5) ? 'дня' : 'дней';
```
This is incorrect for Russian numbers ending in 1 (21, 31, 41 … → «день») and 2-4 (22-24, 32-34 … → «дня»). A member with 21 days left sees "21 дней" instead of "21 день".

The same simplified logic exists in other sub-card variants (`HomeQrHero` line 1484, `HomeMinimal` line 1615) as a pre-existing issue. This phase introduces a new occurrence in `SubCardSpot` rather than fixing it.

The project's CLAUDE.md lists `plural()` from `src/shared/i18n/ru.ts` as the canonical helper for this, but that helper lives in the admin-web app, not in client-pwa. Client-pwa has no shared plural utility.

**Fix:** Implement or inline the standard Russian modular-arithmetic plural:
```js
function ruDays(n) {
  const mod10 = n % 10;
  const mod100 = n % 100;
  if (mod10 === 1 && mod100 !== 11) return 'день';
  if (mod10 >= 2 && mod10 <= 4 && (mod100 < 10 || mod100 >= 20)) return 'дня';
  return 'дней';
}
const unit = ruDays(sub.daysLeft);
```

---

### IN-02: `TweaksRoot` subCardStyle panel shows stale default display and options after this phase

**File:** `apps/client-pwa/src/components/Tweaks/TweaksRoot.jsx:99-104`
**Issue:** The tweaks panel `value={t.subCardStyle || 'eyebrow'}` still falls back to `'eyebrow'` as the display default, but the production default was changed in this phase to `'spot'`. The panel also lists options `eyebrow`, `split`, `stripe` — none of which includes `'spot'` (the new canonical) or `'ring'` (the newly-introduced but unimplemented branch). This is not in the changed files for this phase, but the inconsistency was created by it.

**Fix:** Update `TweaksRoot.jsx` to reflect the new canonical default and remove the `'ring'` dead option if it is not being added back:
```jsx
value={t.subCardStyle || 'spot'}
options={[
  { value: 'spot',   label: 'Spot (default)' },
  { value: 'eyebrow', label: 'Eyebrow (legacy)' },
  { value: 'split',   label: 'Split' },
  { value: 'stripe',  label: 'Stripe' },
]}
```

---

_Reviewed: 2026-06-02_
_Reviewer: Claude (gsd-code-reviewer)_
_Depth: standard_

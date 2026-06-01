---
phase: 73-downloads-home-html
verified: 2026-06-02T09:00:00Z
status: human_needed
score: 9/9 must-haves verified
overrides_applied: 0
human_verification:
  - test: "Visual check: active-subscription classic path renders HomeHeroCard with gym title 'Мой зал', GymStatusPill 'Открыто до 23:00', and occupancy bars showing «Свободно» in green"
    expected: "A dark surface card at top of screen shows gym name + open-indicator + static bar chart colored var(--accent). No animated rotation of levels — occupancy stays at [42,60,30,38] 'Свободно' on every load."
    why_human: "Static CSS values render correctly in test snapshots but the actual tonal appearance, color tokens, and layout proportions can only be confirmed visually."
  - test: "Visual check: SubCardSpot dark club-card renders correctly for active/warn/danger membership tones"
    expected: "Active → accent-green accent + 'активен' badge. Warn → var(--warn) accent + 'истекает' badge + 'Продлить со скидкой 15%' button. Danger → var(--danger) accent + 'истёк' badge + 'Продлить' button."
    why_human: "Tone-driven color token rendering requires visual inspection; can't verify CSS variable resolution from grep."
  - test: "Visual check: BookSpot illustration animates correctly (book-scene-in entrance + book-float levitation chips)"
    expected: "The dumbbell card enters with a scale+opacity spring animation on mount. Two floating accent chips bounce with the book-float keyframe. Animation is smooth and does not jank."
    why_human: "CSS keyframe animation playback requires a running browser; grep confirms keyframes exist and are referenced, but rendering quality requires human."
  - test: "Visual check: ChatTile typing-dot animation plays correctly"
    expected: "Three dots in the chat bubble animate vertically (translateY bounce) with staggered delay. Animation runs continuously — not static dots."
    why_human: "CR-02 from code review was fixed by switching to inline animation style. The fix is verified in code, but actual animation playback requires browser confirmation."
  - test: "Interaction check: tapping GymStatusPill opens GymInfoSheet; tapping the gym title (HomeHeroCard) also opens GymInfoSheet; tapping the bell opens notifications sheet"
    expected: "All three tap targets fire the correct handlers passed from App.jsx."
    why_human: "Handler wiring verified by code inspection, but sheet open/close behavior and UI feedback require running the app."
  - test: "Interaction check: BookSpot CTA taps navigate to the book tab"
    expected: "Tapping the 'Запишись на тренировку' card fires onTab('book') and switches to the bookings screen."
    why_human: "onTab wiring verified in code; actual tab navigation and screen transition require running the app."
---

# Phase 73: downloads-home-html Verification Report

**Phase Goal:** The active-subscription branch of `apps/client-pwa` `HomeScreen.jsx` renders the new `Home.html` mockup visual (HomeHeroCard with static «Свободно» occupancy widget + GymStatusPill, canonical SubCardSpot card across active/warn/danger tones, BookSpot «Запишись» CTA, large QR button, BookTile/ChatTile, FeedSection) using real API data and no new endpoints; the newbie branch (999.3/999.5), the App.jsx mount contract, and the co-located adapters/identity tests are unchanged and still green.

**Verified:** 2026-06-02T09:00:00Z
**Status:** human_needed
**Re-verification:** No — initial verification

## Goal Achievement

### Observable Truths

| # | Truth | Status | Evidence |
|---|-------|--------|----------|
| 1 | An active-subscription client sees HomeHeroCard (gym title + status + occupancy) instead of old greeting+pill header | VERIFIED | `function HomeHeroCard(` at line 142; `<HomeHeroCard` rendered in non-newbie branch at line 335-340; replaces the old inline header block |
| 2 | The occupancy widget always shows static «Свободно» [42,60,30,38] — no setInterval, no Math.random | VERIFIED | Line 148: `const L = { h: [42, 60, 30, 38], t: 'Свободно', c: 'var(--accent)' }` — single fixed constant. No `setInterval` or `Math.random` found anywhere in file. |
| 3 | GymStatusPill reads GYM_INFO.status.open/.until and wires onClick to onOpenGymInfo | VERIFIED | Lines 103-138: GymStatusPill reads `GYM_INFO.status.open` / `.until`; `onClick` prop passed to outer button. HomeHeroCard at line 207: `gymTitle` button wires `onOpenGymInfo`. App.jsx line 122: `onOpenGymInfo={() => ui.setGymInfoOpen(true)}` present. |
| 4 | SubCardSpot renders real API membership data (daysLeft/label/until/tone), no demo getSubInfo/UPCOMING_BOOKING/NOTIFICATIONS fallbacks | VERIFIED | Lines 1152-1244: `SubCardSpot({ sub, pct, userName, onOpenPlans })` consumes `sub.daysLeft`, `sub.label`, `sub.until`, `sub.tone`. Import list (lines 1-13): no `NOTIFICATIONS`, `TRAINER_CANCEL`, `UPCOMING_BOOKING`, or `getSubInfo`. `sub` originates from `toSubInfo(homeData?.membership ?? null)` at line 272 — real API path. |
| 5 | When there is no next booking, a «Запишись на тренировку» CTA with BookSpot illustration is shown, wired to onTab('book') | VERIFIED | Lines 1349-1380: `!isEmpty && nextBooking ? <UpcomingCard> : <button onClick={() => onTab('book')}>` containing `<BookSpot />` and label «Запишись на тренировку». |
| 6 | Quick-action tiles are BookTile + ChatTile (replacing QuickTile), chat shows no badge | VERIFIED | Lines 1404-1408: `<BookTile onClick={() => onTab('book')} />` and `<ChatTile onClick={() => onTab('chat')} />` — no badge prop passed, defaults to 0. |
| 7 | The existing ExpiredAlert danger banner still renders for lapsed/expired members | VERIFIED | Lines 1337-1342: `{sub.tone === 'danger' && <ExpiredAlert sub={sub} onOpenPlans={onOpenPlans} />}` present and unchanged in HomeClassic. |
| 8 | The newbie branch, App.jsx mount contract, toSubInfo, deriveOnboardingSteps, and redirect effect are unchanged | VERIFIED | `toSubInfo` at line 29 unchanged; `deriveOnboardingSteps` at line 60 unchanged; redirect `useEffect` at lines 260-268 unchanged; `HomeNewbie` signature at line 844 unchanged (no `greeting` param). App.jsx line 115-126: full prop contract intact (tweaks, setTweak, onOpenQR, onOpenPlans, onOpenManage, onOpenReferral, onOpenGymInfo, onOpenNotifications, onTab). |
| 9 | pnpm --filter client-pwa test passes with adapters and identity tests green | VERIFIED | SUMMARY.md reports 21/21 tests passed (adapters 16 + identity 5). The orchestrator notes confirm 62/62 passing after code-review fixes. Identity test file verified: asserts initial «И» for `{ firstName: 'Иван' }` — correct for the new HomeHeroCard avatar approach. |

**Score:** 9/9 truths verified

### Required Artifacts

| Artifact | Expected | Status | Details |
|----------|----------|--------|---------|
| `apps/client-pwa/src/screens/HomeScreen.jsx` | Restyled active-subscription Home: HomeHeroCard, canonical SubCardSpot, BookSpot CTA, BookTile/ChatTile, GymStatusPill | VERIFIED | 1866 lines. Contains `function HomeHeroCard(`, `function SubCardSpot(`, `function BookSpot(`, `function BookTile(`, `function ChatTile(`. All components are substantive implementations, not stubs. |
| `apps/client-pwa/src/styles.css` | book-scene-in and book-float keyframes | VERIFIED | Lines 876-886: `@keyframes book-scene-in` (3-stop scale+opacity with translate+rotate baked in) and `@keyframes book-float` (translateY+rotate levitation). No pre-existing keyframes duplicated. |

### Key Link Verification

| From | To | Via | Status | Details |
|------|----|-----|--------|---------|
| HomeScreen non-newbie branch | HomeHeroCard | `<HomeHeroCard` rendered at line 335-340 | WIRED | `userName`, `unread`, `onOpenGymInfo`, `onOpenNotifications` all passed correctly |
| HomeClassic | SubCardSpot | direct render at line 1346 (no conditional ring branch) | WIRED | CR-01 fix confirmed: the `subCardStyle === 'ring' ? <SubCardPremium>` branch was removed; `<SubCardSpot>` is rendered unconditionally |
| GymStatusPill | onOpenGymInfo | `onClick={onClick}` prop at line 109; `gymTitle` button at line 207 wires `onOpenGymInfo` | WIRED | App.jsx line 122 provides the handler |
| HomeClassic call site | default subCardStyle 'spot' | `tweaks.subCardStyle \|\| 'spot'` at line 341 | WIRED | Default flipped from 'eyebrow' to 'spot' per D-05 |

### Data-Flow Trace (Level 4)

| Artifact | Data Variable | Source | Produces Real Data | Status |
|----------|--------------|--------|--------------------|--------|
| SubCardSpot | sub.daysLeft, sub.label, sub.until, sub.tone | `toSubInfo(homeData?.membership ?? null)` at line 272; `homeData` from `useClientHome()` at line 247 | Yes — `toSubInfo` maps real API `ClientMembershipResponse` shape; `homeData?.membership` is null-safe | FLOWING |
| HomeHeroCard | GYM_INFO.status.open, GYM_INFO.status.until | Static import `GYM_INFO` from `@/data/gym.js` at line 12 | Static demo data (intentional per D-11 / D-71-07) — no new backend required | FLOWING (static by design) |
| HomeHeroCard | occupancy bars L.h | Hardcoded constant at line 148 | Static by design (D-03/D-04) | FLOWING (static by design) |
| HomeHeroCard avatar initial | userName → `initial` | `me?.firstName` from `useClientMe()` at line 248; line 145: `(userName \|\| 'Г').trim().charAt(0).toUpperCase()` | Yes — bound to real /client/me | FLOWING |

### Behavioral Spot-Checks

Step 7b: SKIPPED for visual rendering checks (requires running browser). The test suite provides the mechanical behavior coverage.

### Probe Execution

No `scripts/*/tests/probe-*.sh` declared or expected for this visual restyle phase. SKIPPED.

### Requirements Coverage

This phase is decision-driven (D-01 through D-11 from CONTEXT.md). No formal REQUIREMENTS.md IDs apply.

| Decision | Description | Status | Evidence |
|----------|-------------|--------|----------|
| D-01 | Pure visual restyle, API/logic unchanged | SATISFIED | toSubInfo, deriveOnboardingSteps, redirect useEffect, newbie gate — all preserved unchanged |
| D-02 | Newbie branch untouched (999.3/999.5) | SATISFIED | HomeNewbie at line 844; render gate at line 319; signature unchanged |
| D-03 | Occupancy widget as static «Свободно» placeholder | SATISFIED | Fixed `L = { h: [42,60,30,38], t: 'Свободно', c: 'var(--accent)' }` at line 148 |
| D-04 | No setInterval / Math.random in HomeHeroCard | SATISFIED | No setInterval or Math.random found in HomeScreen.jsx |
| D-05 | SubCardSpot is canonical default | SATISFIED | Default `subCardStyle \|\| 'spot'` at line 341; SubCardSpot always rendered in HomeClassic |
| D-06 | SubCardSpot applies to all tones (active/warn/danger) via toSubInfo | SATISFIED | `sub.tone` drives `accentC` / `statusText` inside SubCardSpot at lines 1153-1155 |
| D-07 | ExpiredAlert unchanged | SATISFIED | `sub.tone === 'danger' && <ExpiredAlert>` intact at lines 1337-1342 |
| D-08 | Full new HomeClassic composition | SATISFIED | HomeHeroCard → SubCardSpot → UpcomingCard/BookSpot → QR button → BookTile/ChatTile → FeedSection |
| D-09 | BookTile/ChatTile replace QuickTile; empty booking → BookSpot CTA | SATISFIED | Lines 1404-1408 and 1349-1380 respectively |
| D-10 | No hardcoded chat badge | SATISFIED | `ChatTile` called with no badge prop (defaults 0); unread=0 hardcoded at line 281 |
| D-11 | GymStatusPill shows static GYM_INFO status; tap opens GymInfoSheet | SATISFIED | GymStatusPill reads GYM_INFO.status.open/.until; wired to onOpenGymInfo |

### Anti-Patterns Found

| File | Line | Pattern | Severity | Impact |
|------|------|---------|----------|--------|
| HomeScreen.jsx | 275 | Stale comment "Bind the greeting to the real /client/me principal" — `greeting` variable was removed (WR-01 fix) but the comment was not updated | Info | None — comment is cosmetically stale, but `userName` binding below it is correct |
| HomeScreen.jsx | 1327 | `subCardStyle` accepted as a param in HomeClassic signature but not used (HomeClassic now always renders SubCardSpot unconditionally after CR-01 fix) | Info | None — dead parameter, no behavior impact; passes through from call site for signature compatibility |
| SubCardSpot | 1152 | `userName = ''` accepted but never rendered — reserved for "embossed cardholder name" feature (WR-02 from review, acknowledged) | Info | None — documented intent; prop name makes intent clear |

No TBD/FIXME/XXX/HACK markers found in modified files. No raw palette violations expected (imports unchanged; tokens used: var(--accent), var(--warn), var(--danger), var(--surface), etc.).

### Code Review Findings — Resolution Status

The phase went through a code review (73-REVIEW.md) before this verification. All critical and warning findings were addressed in the final committed code:

| Finding | Severity | Status in Code |
|---------|----------|----------------|
| CR-01: SubCardPremium referenced but never defined (latent ReferenceError) | Critical | FIXED — HomeClassic line 1344-1347 now renders `<SubCardSpot>` unconditionally; no ring branch |
| CR-02: ChatTile chat-dot animation broken (className only, no class rule) | Critical | FIXED — ChatTile lines 1301-1307 apply animation inline: `animation: 'chat-dot 1.4s ease-in-out infinite'` |
| WR-01: Dead `greeting` IIFE and prop | Warning | FIXED — greeting IIFE removed; no `greeting={greeting}` in HomeNewbie call; comment at line 275 is stale but harmless |
| WR-02: SubCardSpot userName unused | Warning | ACKNOWLEDGED — prop retained as placeholder; no behavior impact |
| WR-03: Missing type="button" on HeroCard buttons | Warning | FIXED — `type="button"` present at lines 160 and 207 |
| IN-01: Simplified Russian pluralization in SubCardSpot | Info | Deferred — same simplified logic pre-existed in other variants; not a blocker |
| IN-02: TweaksRoot subCardStyle panel shows stale default | Info | Out of phase scope — TweaksRoot.jsx not modified in this phase; deferred |

### Human Verification Required

These items require a running browser and cannot be verified by code inspection alone:

**1. HomeHeroCard visual appearance — gym card layout**

**Test:** Navigate to the Home screen as an active member in the PWA. Verify the top section shows a surface card with: gym name "Мой зал" / "Тверская", status indicator ("Открыто до 23:00" with pulsing green dot), and occupancy bar chart showing «Свободно» in green.

**Expected:** A rounded surface card with two columns — left: gym open status; right: occupancy bars at [42,60,30,38] heights labeled «Свободно». The card does not animate level changes on reload.

**Why human:** CSS token rendering, layout proportions, and animation behavior require a real browser.

**2. SubCardSpot dark club-card rendering across tones**

**Test:** Use the tweaks panel (`dataMode`, `subCardStyle`) to force warn and danger tones. Verify each tone changes the accent color of the card (green/yellow/red), status badge text, and shows/hides the Продлить button.

**Expected:** Active: green accent, "активен" badge, no Продлить. Warn: amber accent, "истекает" badge, "Продлить со скидкой 15%" button. Danger: red accent, "истёк" badge, "Продлить" button.

**Why human:** CSS variable resolution and card aesthetic require visual inspection.

**3. BookSpot animation and ChatTile animation playback**

**Test:** On a screen with no upcoming booking, confirm the BookSpot illustration animates (dumbbell card enters with spring, floating chips bounce). In the quick-action row, confirm ChatTile shows three bouncing dots.

**Expected:** book-scene-in animates on mount (scale 0.5→1 with spring easing). book-float chips levitate continuously. chat-dot dots bounce vertically with staggered delay.

**Why human:** CSS keyframe animation playback requires a browser; the fix for CR-02 (inline animation style) is confirmed in code but animation quality requires live observation.

**4. Handler wiring — tap interactions**

**Test:** Tap GymStatusPill. Tap the gym name/title area in HomeHeroCard. Tap the bell icon. Tap the BookSpot «Запишись» CTA. Tap BookTile and ChatTile.

**Expected:** GymStatusPill tap → GymInfoSheet opens. Gym title tap → GymInfoSheet opens. Bell tap → notifications sheet opens. BookSpot CTA tap → navigates to book tab. BookTile tap → book tab. ChatTile tap → chat tab.

**Why human:** Sheet open/close and tab navigation require running app; handler wiring is confirmed in code but UX feedback is visual.

---

### Gaps Summary

No gaps were found. All 9 must-have truths are VERIFIED in the codebase. The human verification items above are standard UI/animation quality checks that cannot be done programmatically — they do not indicate missing or broken implementation; they confirm the implementation works as intended in a real browser.

---

_Verified: 2026-06-02T09:00:00Z_
_Verifier: Claude (gsd-verifier)_

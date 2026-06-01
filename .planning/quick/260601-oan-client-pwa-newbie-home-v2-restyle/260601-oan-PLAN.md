---
phase: quick-260601-oan
plan: 01
type: execute
wave: 1
depends_on: []
files_modified:
  - apps/client-pwa/src/styles.css
  - apps/client-pwa/src/screens/HomeScreen.jsx
autonomous: false
requirements: [QUICK-260601-oan]
must_haves:
  truths:
    - "Newbie Home renders the v2 hero-card (gym title «Мой зал», location row, bell, avatar, two mini stat widgets)"
    - "Newbie Home renders the v2 plan-card with accent top panel, pass illustration, 3 tariff buttons, CTA and footer"
    - "Onboarding strip shows a circular SVG progress ring (N/4) driven by deriveOnboardingSteps doneCount"
    - "First-visit promo renders the branded ticket card; QR placeholder restyled; trainers tile has avatar stack; chat tile has typing bubble"
    - "Plan CTA and each tariff still call onOpenPlans (no fabricated checkout); dismiss × and step routing preserved"
    - "Non-API data (occupancy, open-hours, location, trainer identities, chat badge, tariff prices) is rendered as graceful fallback, never hardcoded as fact for real users"
    - "pnpm --filter client-pwa typecheck, lint, and test all pass; HomeScreen.adapters.test.jsx stays green"
  artifacts:
    - path: "apps/client-pwa/src/styles.css"
      provides: "Shared keyframes pulse-soft, pulse-dot, chat-dot, pass-in, chip-in, cta-pulse, bar-breathe"
      contains: "@keyframes pulse-soft"
    - path: "apps/client-pwa/src/screens/HomeScreen.jsx"
      provides: "Restyled HomeNewbie composition + HeroNewbie/OnboardingStrip/FirstVisitNudge/QrPlaceholder/QuickTile newbie usage"
      contains: "function HomeNewbie"
  key_links:
    - from: "HomeNewbie plan-card CTA + tariff buttons"
      to: "onOpenPlans"
      via: "onClick handler"
      pattern: "onOpenPlans"
    - from: "OnboardingStrip ring + chips"
      to: "deriveOnboardingSteps doneCount / step.state"
      via: "props (doneCount, steps)"
      pattern: "doneCount"
---

<objective>
Restyle the **newbie** Home state of `apps/client-pwa/src/screens/HomeScreen.jsx` to faithfully reproduce the v2 mockup at `/Users/andre/Downloads/Home (newbie) v2.html`. The restyle touches only the newbie components: `HomeNewbie` composition and its children (`HeroNewbie`, `OnboardingStrip`, `FirstVisitNudge`, `QrPlaceholder`) plus the newbie usage of `QuickTile`.

Purpose: Bring the newbie onboarding experience to the v2 visual bar (hero gym card, premium plan-card, circular progress ring, branded promo, composed tiles) while keeping all live data bindings honest (D-LIVE: live-bind real API fields, graceful fallback for everything else — never fabricate values).

Output: Updated `styles.css` (shared keyframes) and `HomeScreen.jsx` (restyled newbie components). No new files, no new dependencies. Non-newbie variants (`HomeClassic`/`HomeQrHero`/`HomeMinimal`), `OnboardingScreen.jsx`, and the exported helpers (`deriveOnboardingSteps`, `toSubInfo`) are untouched.
</objective>

<execution_context>
@/Users/andre/Workspace/Development/clubcore/.claude/get-shit-done/workflows/execute-plan.md
@/Users/andre/Workspace/Development/clubcore/.claude/get-shit-done/templates/summary.md
</execution_context>

<context>
@CLAUDE.md
@.planning/STATE.md
@/Users/andre/Downloads/Home (newbie) v2.html
@apps/client-pwa/src/screens/HomeScreen.jsx
@apps/client-pwa/src/screens/HomeScreen.adapters.test.jsx
@apps/client-pwa/src/components/Icon.jsx
@.planning/phases/999.3-client-pwa-home-newbie-state/999.3-UI-SPEC.md

<conventions>
HARD project rules (from CLAUDE.md) the executor MUST follow:
- NO semicolons (ASI). Single quotes for strings. 100-char width. Trailing commas.
- NO raw Tailwind palette classes. Use semantic CSS-variable tokens exactly as the mockup does (`var(--accent)`, `var(--on-accent)`, `var(--text)`, `var(--text-2)`, `var(--text-3)`, `var(--surface)`, `var(--surface-2)`, `var(--border)`, `var(--border-strong)`, `var(--accent-deep)`, `var(--accent-soft)`, radius/shadow tokens `var(--r-md)` `var(--r-lg)` `var(--r-xl)` `var(--r-pill)` `var(--sh-1)` `var(--sh-2)`). The greens `#10b981`/`#34d399`/`#fb7185`/`#f43f5e` in the mockup are literal status-LED hexes — port them verbatim as inline values (the file already uses literal `#10b981` and `#06120c` in places).
- Match existing file style: components are plain React function components using inline `style={{}}` objects + existing utility classes (`card`, `press`, `btn`, `btn-accent`, `progress-track`). Icons via `<Icon name=... size=... color=... strokeWidth=... />`.
</conventions>

<interfaces>
Existing data hooks (already wired in `HomeScreen`):
- `useClientMe()` → `me` with `firstName`, `goal`, `heightCm`, `weightKg`, `onboardingCompletedAt`
- `useClientHome()` → `homeData` with `membershipState` ('newbie' gates this whole branch), `membership` (null for newbie), `nextBooking`
- `useClientBookings()` → `bookings` with `items`, `total`

Existing exported helper (DO NOT change signature/behavior — adapter tests depend on it):
- `deriveOnboardingSteps(me, homeData, bookings)` → `{ steps, doneCount, title, badge }`
  - `steps[]` each: `{ key: 'account'|'plan'|'profile'|'visit', label, meta, state: 'done'|'next'|'pending' }`
  - `doneCount` = count of state==='done' (the 'next' step is NOT counted). For a fresh newbie doneCount===1.
  - `badge` = `'N / 4'`, `title` = `'Ещё {4-doneCount} шага до полного старта'`

`HomeNewbie` props (current, keep all): `{ me, homeData, bookings, userName, greeting, onOpenPlans, onOpenGymInfo, onTab, onOpenOnboarding }`.

Routing already preserved in `HomeScreen`: `onOpenOnboarding = () => navigate('/onboarding')`. Bell action → `onOpenNotifications` is NOT currently passed into `HomeNewbie`; see Task 2 note on bell wiring.

Available `<Icon>` names (from Icon.jsx): `mapPin`, `bell`, `card`, `calendar`, `user`, `users`, `chat`, `qr`, `lock`, `check`, `close`, `chevronRight`, `arrowRight`, `lightning`, `barbell`, `star`, `tag`, `flame`, `clock`, `shield`. There is NO `ticket` icon — the promo ticket illustration must reuse `tag` (closest) OR add a new `ticket` entry to Icon.jsx (preferred, see Task 3).
</interfaces>
</context>

<tasks>

<task type="auto">
  <name>Task 1: Add shared keyframes + any missing icon to global stylesheet</name>
  <files>apps/client-pwa/src/styles.css, apps/client-pwa/src/components/Icon.jsx</files>
  <action>
The v2 mockup relies on several `@keyframes` that do NOT yet exist as global rules in `apps/client-pwa/src/styles.css`. Confirmed present already (do NOT redefine): `fade-up`, `.stagger` stagger delays, `onboard-collapse`, `.onboard-card.dismissing`, `spot-float`, `.progress-track`, `.onboard-fill`, and the `prefers-reduced-motion` reset block. Confirmed MISSING (must add): `pulse-soft`, `pulse-dot`, `chat-dot`, `pass-in`, `chip-in`, `cta-pulse`, `bar-breathe`.

Note: `pulse-soft` is currently defined ONLY inside an inline `<style>` block in `ExpiredAlert` (HomeScreen.jsx ~line 1110). Promote it to a single global definition in `styles.css` so the newbie components can use it without a duplicate inline block, and DELETE the now-redundant inline `<style>{...pulse-soft...}</style>` block in `ExpiredAlert` (the ExpiredAlert element keeps `animation: pulse-soft ...` and will now resolve against the global rule — verify ExpiredAlert still animates).

Add to `styles.css` (verbatim values from the mockup `<style>`; reproduce the keyframe percentages exactly):
- `@keyframes pulse-soft` — 0%,100% scale(1) opacity 1; 50% scale(1.18) opacity 0.85 (mockup plan-card variant). This is the single canonical definition; ExpiredAlert's old inline used scale(1.05) at 50% — adopt the mockup's 1.18/0.85 version since the newbie eyebrow + ExpiredAlert pulse can share it (acceptable visual parity).
- `@keyframes pulse-dot` — 0%,100% scale(1); 50% scale(1.15).
- `@keyframes chat-dot` — 0%,100% translateY(0); 50% translateY(-3px).
- `@keyframes pass-in` — the 3-stop pass entrance (verbatim from mockup lines ~659-663, including the rotate(-7deg) translateY(-50%) transform values).
- `@keyframes chip-in` — from opacity 0 translateY(8px) scale(0.96) → to opacity 1 translateY(0) scale(1).
- `@keyframes cta-pulse` — 0%,100% box-shadow 0 spread transparent; 50% box-shadow 0 0 0 7px accent@13% (use `color-mix(in oklab, var(--accent) 13%, transparent)`).
- `@keyframes bar-breathe` — 0%,100% opacity 1; 50% opacity 0.5.

Do NOT add the mockup's device-frame / `.tweaks` / `.tabbar` / `.status-bar` / `.toast` / `.hero-slim` / `.hero-dark` / `.hero-bar` CSS — those are demo scaffolding or unused hero variants. Only the keyframes above are shared; all component visuals are ported as inline-style objects in Tasks 2-4 (matching the file convention), so do NOT port the `.hero-card`/`.plan-card`/`.step`/`.promo`/`.tile` class blocks into styles.css.

ICON: The promo illustration uses a ticket glyph. Add a `ticket` entry to `Icon.jsx` `paths` using the mockup's ticket SVG path (lines ~1395-1398: the rounded ticket body `M3 8a2 2 0 0 1 2-2h14...` plus dashed perforation `M14 6v12`). Follow the existing Icon.jsx entry format exactly: a React fragment of `<path .../>` elements using `stroke={color} strokeWidth={s} fill="none"` and `strokeLinecap`/`strokeLinejoin` as in siblings. (If you prefer not to add an icon, the alternative is reusing `tag` — but `ticket` is the faithful match, so add it.)
  </action>
  <verify>
    <automated>cd apps/client-pwa && pnpm exec tsc -b --noEmit && pnpm exec eslint src/styles.css src/components/Icon.jsx</automated>
    <automated>grep -v '^\s*/\*' apps/client-pwa/src/styles.css | grep -c 'keyframes pulse-soft\|keyframes pulse-dot\|keyframes chat-dot\|keyframes pass-in\|keyframes chip-in\|keyframes cta-pulse\|keyframes bar-breathe'</automated>
  </verify>
  <done>All seven keyframes exist exactly once as global rules in styles.css; the duplicate inline pulse-soft block in ExpiredAlert is removed and ExpiredAlert still animates; a `ticket` icon is registered in Icon.jsx; typecheck and lint pass.</done>
</task>

<task type="auto">
  <name>Task 2: Restyle hero-card header + premium plan-card (HomeNewbie + HeroNewbie)</name>
  <files>apps/client-pwa/src/screens/HomeScreen.jsx</files>
  <action>
Restyle the first two sections of the newbie screen. Port ONLY the screen content from the mockup (`.scroller` children) — never the device frame, tab bar, status bar, or toast. The app already provides `<StatusBar/>`, the app-shell tab bar, and `<PullToRefresh>`.

Keep the `HomeNewbie` outer `<div className="stagger">` so each direct child fades up in order (the stagger CSS targets `> *:nth-child(N)`). Maintain the existing render order so stagger delays line up: (1) hero-card header, (2) plan-card, (3) onboarding strip, (4) promo + qr group, (5) tiles grid, (6) spacer.

(A) HERO-CARD HEADER — replace the current greeting+name+`GymStatusPill` header block (HomeNewbie lines ~570-587) with the mockup `.hero-card` (mockup lines 1227-1261), ported as an inline-styled `<div>` (NOT a new CSS class). Structure:
- Outer card: `var(--surface)` bg, `0.5px solid var(--border)`, `borderRadius: 20`, `boxShadow: var(--sh-2)`, `padding: '11px 14px'`, `position: relative`, `margin: '0 16px 12px'` (the original header had `padding: '4px 16px 18px'`; the new card needs its own horizontal margin since stagger children are full-width — use `margin: '0 16px 12px'` to match other newbie cards).
- Top row (`htop`): left = title block («Мой зал» at 18px/750/-0.4px + location row); right = bell button + avatar.
  - Title «Мой зал» — this is the gym name. Render the literal «Мой зал» (it is the app/gym brand label, not user data) per mockup.
  - Location row «Тверская» with `<Icon name="mapPin" size={13} color="var(--accent-deep)" />`. D-LIVE: gym location name is NOT API-backed → it is a constant brand/venue label, acceptable as a static string here (it is the single known venue, not fabricated per-user data). Render «Тверская».
  - Bell button: 38×38, `borderRadius: 12`, `0.5px solid var(--border)`, `var(--surface)` bg, `var(--sh-1)`, `<Icon name="bell" size={19} />`. Wire `onClick` to open notifications. The notifications affordance: `HomeNewbie` does NOT currently receive `onOpenNotifications`. Thread it through: add `onOpenNotifications` to `HomeNewbie`'s props and pass it from `HomeScreen` (it already exists as a `HomeScreen` prop). The red unread dot (`.nd`) is NOT API-backed (unread count is hardcoded 0 in HomeScreen) → GRACEFUL FALLBACK: render the bell WITHOUT the red dot (omit the `.nd` element) since there is no real unread signal. aria-label «Уведомления».
  - Avatar: 38×38, `borderRadius: 12`, `var(--accent)` bg, `var(--on-accent)` color, bold initials. Derive initials from real `me.firstName` (first grapheme, uppercased) — this IS API-backed. If `userName` is empty, fall back to a neutral single glyph (e.g. render nothing or a generic person — prefer hiding initials and showing `<Icon name="user" size={18} color="var(--on-accent)" />`). The green online dot (`.on`) is presence state, NOT API-backed → GRACEFUL FALLBACK: omit the `.on` dot (do not fake presence).
- Stats row (`hero-stats` inside hero-card): top divider `0.5px solid var(--border)`, `marginTop: 10`, `paddingTop: 10`, two equal `stat` segments split by a left border on the second.
  - Stat 1 «Зал»: label «ЗАЛ» (10px/700/uppercase/`var(--text-3)`) + value row with a live-dot and open-hours text. Open hours («Открыт до 23:00») and the live green dot are NOT API-backed → GRACEFUL FALLBACK: do NOT print a fabricated closing time. Replace with a truthful neutral value — render the gym status label that IS available, i.e. reuse the existing neutral concept from `GymStatusPill` («О зале» / a neutral state). Concretely: show the «Зал» label with a neutral value «Расписание» (or «О зале») and NO fake live-dot/closing-time; tapping this stat may call `onOpenGymInfo` to preserve the existing gym-info entry point that the removed `GymStatusPill` provided. Keep it visually a stat segment.
  - Stat 2 «Наполненность»: occupancy load-bars + occupancy text are NOT API-backed → GRACEFUL FALLBACK: hide this entire second stat segment (render only Stat 1, which then spans the row) OR replace with another truthful API-backed stat if one is trivially available — none is, so HIDE the occupancy segment. Do NOT render animated load-bars with invented levels for real users. (The `bar-breathe`/load-bars keyframes added in Task 1 remain available but unused here; that is fine.)

  Net effect of (A): a clean surface hero-card with «Мой зал» + «Тверская», a real bell→notifications button (no fake badge), a real initials avatar (no fake presence dot), and a single truthful «Зал» stat that opens gym info. This honors D-LIVE: every fabricated-for-real-user element (occupancy, closing time, presence, unread dot) is gracefully dropped, not hardcoded.

(B) PLAN-CARD — replace `HeroNewbie` (lines 257-356) entirely with the mockup `.plan-card` (mockup lines 1263-1327), ported as inline-styled JSX inside the existing `HeroNewbie` export (keep the export name + its `{ onOpenPlans }` prop so the call site in HomeNewbie is unchanged; you may extend props if needed but keep `onOpenPlans`). Structure:
- Card: `var(--surface)`, `0.5px solid var(--border)`, `borderRadius: 28`, layered shadow `0 18px 44px rgba(28,25,23,0.13), 0 2px 6px rgba(28,25,23,0.05)`, `overflow: hidden`, `margin: '0 16px 14px'`.
- Top panel (`pc-top`): height 134, `var(--accent)` bg, `var(--on-accent)` text, `overflow: hidden`, `position: relative`. Reproduce the decorative layers as absolutely-positioned child `<div>`s / `<span>`s with inline styles:
  - dot-grid pattern (radial-gradient `rgba(255,255,255,0.5)` dots `background-size:16px 16px`, opacity 0.4, with the diagonal `mask`/`-webkit-mask` linear-gradient) — implement as an absolute inset div with these inline styles (camelCase `WebkitMask`).
  - two decorative rings (`pc-ring` solid + `pc-ring r2` dashed) top-right, verbatim sizes/offsets.
  - two floating chips (`pc-chip c1`, `c2`) with `animation: 'spot-float 3.6s ease-in-out infinite'` (spot-float already global) — c2 delayed 0.7s.
  - eyebrow «Аккаунт создан» top-left with a pulsing dot (`animation: 'pulse-soft 2.4s ease-in-out infinite'`).
  - kicker «Время<br/>тренироваться» bottom-left (use a `<br/>` or two lines), 19px/750/-0.5px.
  - composed membership-pass illustration (`pc-pass`) absolutely right-centered, rotated -7deg, with `animation: 'pass-in 0.55s cubic-bezier(0.32,1.5,0.36,1) both'`. Inner: a star badge (`pp-star`, use the inline star SVG or `<Icon name="star" .../>` recolored), a header row with a barbell mark (`<Icon name="barbell" size={14} .../>` inside a `pp-mark` chip) + two skeleton lines (`pp-lines i`), and a row of 10 bars (`pp-bars i`) with the nth-child height/opacity variations. Mark the whole pass `aria-hidden`.
- Body (`pc-body`, padding `18px 20px 20px`):
  - title «Выбери свой абонемент» (25px/750/-0.7px).
  - sub «QR-пропуск активируется сразу после оплаты. Заморозка и смена тарифа — в любой момент.» (13.5px/`var(--text-2)`).
  - tariff selector (`pc-tariffs`, 3 buttons): D-LIVE — tariff names AND prices are NOT wired to a live catalog on this screen. DECISION (locked by this plan): render the 3 tariff buttons as a faithful visual selector using the mockup's plan LABELS only («Месяц», «Полгода» with «ХИТ» flag, «Год») — these are stable plan-tier names, acceptable — but DO NOT render any fabricated price (`tp`/`tu` price lines). Omit the «3 500 ₽» / «в месяц» price text entirely. Each tariff button is selectable (local `useState` for selected index, default the «Полгода» popular one to `sel`) purely as a visual affordance. The «ХИТ» flag stays on «Полгода». Selecting a tariff updates local selected state for the highlight only.
  - CTA (`pc-cta`): label «Оформить абонемент» (NOT «Оформить · {price}» — no fabricated price). `var(--text)` bg, `var(--bg)` text, height 54, `borderRadius: var(--r-pill)`, trailing arrow `<Icon name="arrowRight" size={18} color="currentColor" .../>`, `animation: 'cta-pulse 3s ease-in-out infinite'`. CTA `onClick` MUST call `onOpenPlans` (open the real Plans sheet). Tapping ANY tariff button MUST also call `onOpenPlans` (the inline selector is visual only and must never replace the real plans/checkout flow) — i.e. each tariff `onClick` both sets local selected state AND calls `onOpenPlans`. (D-LIVE CTA rule.)
  - footer (`pc-foot`): centered «Пропуск откроется за пару секунд» with a leading `<Icon name="lightning" size={13} color="var(--accent-deep)" .../>`.

Keep the `HomeNewbie` call site `<HeroNewbie onOpenPlans={onOpenPlans} />` working. Remove the now-unused `GymStatusPill` import/usage from the newbie header only — but DO NOT delete the `GymStatusPill` export itself (the non-newbie shared header at HomeScreen lines ~226-241 still uses it).
  </action>
  <verify>
    <automated>cd apps/client-pwa && pnpm exec tsc -b --noEmit && pnpm exec eslint src/screens/HomeScreen.jsx && pnpm exec vitest run src/screens/HomeScreen.adapters.test.jsx</automated>
    <automated>grep -c 'onOpenPlans' apps/client-pwa/src/screens/HomeScreen.jsx</automated>
  </verify>
  <done>Newbie header is the v2 hero-card (Мой зал / Тверская / real bell→notifications / real initials avatar / single truthful «Зал» stat — no fabricated occupancy, closing time, presence dot, or unread badge). HeroNewbie renders the v2 plan-card with accent panel, pass illustration, label-only tariff selector (no fake prices), CTA «Оформить абонемент», and footer. CTA and every tariff tap call onOpenPlans. Adapter tests stay green; typecheck + lint pass.</done>
</task>

<task type="auto">
  <name>Task 3: Restyle onboarding ring, promo, QR placeholder, and quick tiles</name>
  <files>apps/client-pwa/src/screens/HomeScreen.jsx</files>
  <action>
Restyle the remaining newbie sections. All visuals are ported as inline-style objects (matching file convention); reuse the keyframes added in Task 1.

(A) ONBOARDING STRIP (`OnboardingStrip`, lines 359-487) — replace the linear progress bar with the mockup circular progress RING and update the header layout (mockup lines 1329-1390). KEEP all existing behavior: `dismissed`/`dismissing` state, `handleDismiss`, `handleStepClick` routing (`plan`→`onOpenPlans`, `profile`→`onOpenOnboarding`, `visit`→`onTab('book')`, `account`→inert), the `onboard-card`/`dismissing` classes, and props `{ steps, doneCount, title, badge, onOpenPlans, onTab, onOpenOnboarding }`.
- Header (`onboard-head`): a flex row with `gap: 14`, vertically centered: [ring] [titles] [dismiss ×].
  - Ring (`ob-ring`): 56×56, an inline `<svg viewBox="0 0 56 56">` rotated -90deg containing a track circle (`stroke: var(--border)`, `strokeWidth: 5`, `fill: none`, r=24) and a progress circle (`stroke: var(--accent)`, `strokeLinecap: round`, `strokeWidth: 5`, r=24) with `strokeDasharray` = circumference (2·π·24 ≈ 150.8) and `strokeDashoffset` computed LIVE from `doneCount`: `offset = 150.8 * (1 - doneCount/4)`. Center fraction overlay (`ob-frac`): big `{doneCount}` + small `<small>/4</small>` (15px/800 + 10px/600 `var(--text-3)`), absolutely centered over the svg, `fontVariantNumeric: 'tabular-nums'`. Drive the ring from the SAME `doneCount` prop the badge uses — this is API-derived (deriveOnboardingSteps), so it is live-bound. Add `transition: 'stroke-dashoffset 0.7s cubic-bezier(0.32,0.72,0.2,1)'` on the progress circle for the animated fill. Mark ring `aria-hidden`.
  - Titles (`onboard-titles`): eyebrow «Старт новичка» (11px/700/uppercase/`var(--accent-deep)`) with a small pin dot, then `{title}` (16px/700/-0.3px) — `title` from props (live).
  - Dismiss × (`onboard-x`): keep the existing dismiss button + `<Icon name="close" size={14} .../>`, aria-label «Скрыть», `onClick={handleDismiss}`. Note the mockup moved the count badge OUT of the header (the ring now shows the fraction), so REMOVE the separate «N/4» pill badge element — the ring's center fraction replaces it. (The `badge` prop may remain unused, or you can keep it for the ring's `{doneCount}` text; do not break the prop list.)
- Steps (`onboard-steps`): horizontally-scrolling row of 4 step chips, `gap: 8`, `overflowX: 'auto'`, `scrollbarWidth: 'none'`, `min-width: 124` per chip. Each chip (`step`) keeps the existing done/next/pending visual logic and `handleStepClick` wiring, restyled to the mockup `.step` look: `var(--surface-2)` bg / `0.5px solid var(--border)`, `borderRadius: 14`, `padding: '10px 12px 11px'`, column layout `gap: 7`, with an icon ring (`ico` 26×26) + label (`lbl` 12.5px/600) + meta (`meta` 11px). Done chip: accent-soft tint bg + accent border + accent icon fill + `var(--accent-deep)` meta. Next chip: `var(--text)` border + `var(--text)` icon bg + `var(--bg)` icon color + subtle ring shadow `0 0 0 2px color-mix(in oklab, var(--text) 7%, transparent)`. Keep step icons map (`account:'check' when done else 'user'`, `plan:'card'`, `profile:'user'`, `visit:'calendar'`) — done step always shows `check`. Add `animation: 'chip-in ...'` per-chip entrance only if it does not fight the parent `.stagger`/`fade-up` — SAFER: omit per-chip `chip-in` to avoid double-animation (the keyframe stays available globally); the chips already animate via the card's stagger entry. Step labels/meta come from `step.label`/`step.meta` (live, from deriveOnboardingSteps).

(B) FIRST-VISIT PROMO (`FirstVisitNudge`, lines 490-524) — replace the dashed-border row with the mockup branded `.promo` (mockup lines 1392-1409). Keep it a `<button>` with `className="press"`, `onClick={() => onTab?.('book')}`, prop `{ onTab }`. Structure:
- Card: `var(--surface)`, `0.5px solid var(--border)`, `borderRadius: 22`, `var(--sh-1)`, `padding: '15px 16px'`, flex row `gap: 14`, `margin: '0 16px 12px'`, `position: relative`, `overflow: hidden`.
- Illustration (`promo-ill`): 56×56, `borderRadius: 17`, `var(--accent)` bg, `var(--on-accent)` color, glow shadow `0 10px 22px color-mix(in oklab, var(--accent) 32%, transparent)`, containing `<Icon name="ticket" size={28} color="currentColor" .../>` (ticket icon added in Task 1) and a «0 ₽» free badge (`promo-ill .free`) bottom-right (`var(--text)` bg, `var(--bg)` text, 10px/700, bordered). The «бесплатно/0 ₽» first-visit offer is a stable program label (not per-user fabricated data) → acceptable.
- Body (`promo-body`): eyebrow «Для новичков» (10.5px/700/uppercase/`var(--accent-deep)`), title «Первый визит — бесплатно» (16px/700/-0.3px), sub «Экскурсия с тренером · 30 минут» (12.5px/`var(--text-2)`).
- Go button (`promo-go`): 32×32 round, `var(--text)` bg, `var(--bg)` color, `<Icon name="chevronRight" size={15} color="currentColor" .../>`.

(C) QR PLACEHOLDER (`QrPlaceholder`, lines 527-562) — keep functionally identical (static, non-interactive, `role="img"`), restyle to the mockup `.qr-placeholder` (mockup lines 1411-1431): `var(--surface-2)` bg, `0.5px solid var(--border)`, `borderRadius: var(--r-md)`, `padding: '10px 14px'`, flex row `gap: 12`, `margin: '0 16px 14px'`. Icon chip (`qrp-ico`) 32×32 `borderRadius: 9` `var(--surface)` bg with `<Icon name="qr" size={18} color="var(--text-3)" .../>`; body title «QR-пропуск» (13.5px/600/`var(--text-2)`) + sub «Активируется после оплаты абонемента» (12px/`var(--text-3)`); trailing lock `<Icon name="lock" size={16} color="var(--text-3)" .../>`. (Largely matches current — align spacing/sizes to mockup exactly.)

(D) QUICK TILES — in `HomeNewbie`, replace the two generic `QuickTile` usages (lines 611-614) with the mockup's two composed tiles (`.tile.trainers` + `.tile.chat`, mockup lines 1433-1457), implemented inline (do NOT alter the shared `QuickTile` export used by the non-newbie variants). Grid: `padding: '0 16px 16px'`, `display: 'grid'`, `gridTemplateColumns: '1fr 1fr'`, `gap: 10`. Both tiles `borderRadius: 20`, `0.5px solid var(--border)`, `padding: '15px 15px 16px'`, `minHeight: 132`, flex column space-between, `<button>` with `onClick`.
- Trainers tile (light, `var(--surface)`): overlapping avatar stack (`avatars`): 3 initial circles (34×34, `-11px` overlap, `2.5px solid var(--surface)` ring, colors `var(--accent)` / `color-mix(in oklab, var(--accent) 60%, #6ee7c4)` / `var(--accent-deep)`) + a «+9» more circle (`var(--surface-2)` bg). D-LIVE: trainer avatar IDENTITIES and the «+9»/«12 в зале» counts are NOT API-backed → GRACEFUL FALLBACK: do NOT render fabricated initials/counts. Render the avatar stack as ANONYMOUS placeholder circles (generic person glyph via `<Icon name="user" .../>` or empty accent-tinted circles, NO fake initials) and drop the «+9» count and the «12 в зале» sub. Title «Тренеры», sub «кто работает в зале» (the existing truthful sub, not «12 в зале · подберём своего»). `onClick={() => onTab?.('book')}`.
- Chat tile (dark, `var(--text)` bg, `var(--bg)` text): typing bubble (`chat-ill .bubble`, 50×38, `borderRadius: '15px 15px 15px 5px'`, `rgba(255,255,255,0.13)` bg) with 3 animated dots (`bubble i`, 6×6, `var(--accent)`, `animation: 'chat-dot 1.4s ease-in-out infinite'`, dots 2 & 3 delayed 0.2s/0.4s + reduced opacity). Title «Чат», sub «админ + тренер» (existing truthful sub, not «Админ ответит за ~5 мин» which is a fabricated SLA). The unread badge (`.badge` «1») is NOT API-backed (unread hardcoded 0) → GRACEFUL FALLBACK: omit the badge entirely (do not render a fake «1»). `onClick={() => onTab?.('chat')}`.

Throughout: honor D-LIVE — anything not exposed by the API (trainer identities/counts, chat SLA/unread, occupancy) is dropped or shown neutral, never fabricated. Preserve the `<div className="stagger">` child ordering so fade-up delays remain correct: child 4 is the `<div>` wrapping promo + qr; child 5 is the tiles grid; child 6 is the spacer.
  </action>
  <verify>
    <automated>cd apps/client-pwa && pnpm exec tsc -b --noEmit && pnpm exec eslint src/screens/HomeScreen.jsx && pnpm exec vitest run</automated>
    <automated>grep -c "onOpenOnboarding\|onTab?.('book')\|onTab?.('chat')" apps/client-pwa/src/screens/HomeScreen.jsx</automated>
  </verify>
  <done>Onboarding strip shows an SVG progress ring driven by live doneCount with fraction N/4; step chips keep done/next/pending visuals and click routing; dismiss × works. FirstVisitNudge is the branded promo (ticket + 0₽). QrPlaceholder restyled, still static. Trainers tile has an anonymous avatar stack (no fake identities/counts), chat tile has an animated typing bubble (no fake unread badge/SLA). Full `vitest run` green; typecheck + lint pass.</done>
</task>

<task type="checkpoint:human-verify" gate="blocking">
  <what-built>Restyled the newbie Home screen of client-pwa to the v2 mockup: hero gym-card, premium plan-card, circular onboarding ring, branded first-visit promo, restyled QR placeholder, and composed trainers/chat tiles — with all non-API data gracefully dropped per D-LIVE.</what-built>
  <how-to-verify>
1. Run the client-pwa dev server: `pnpm --filter client-pwa dev` and open the app in a browser (default Vite port 5173, path that renders the client Home as a newbie / no-subscription account).
2. Confirm the newbie Home now shows: (a) a surface hero-card with «Мой зал» + «Тверская» + a bell button + an avatar with your real first-name initial; (b) the premium accent plan-card with the rotated pass illustration, 3 tariff buttons (Месяц / Полгода·ХИТ / Год) WITHOUT prices, CTA «Оформить абонемент», footer «Пропуск откроется за пару секунд»; (c) the onboarding card with a circular progress ring showing «1/4» (fresh newbie); (d) the «Первый визит — бесплатно» promo with the 0₽ ticket; (e) the QR-пропуск locked strip; (f) Тренеры (avatar stack) + Чат (typing bubble) tiles.
3. Tap the plan-card CTA AND tap each tariff button — every one must open the real Plans sheet (not a fake inline checkout).
4. Tap the onboarding step chips: «Абонемент» opens Plans, «Профиль» goes to /onboarding, «Первый визит» switches to the Запись tab. Tap the × on the onboarding card — it collapses/dismisses.
5. Tap the bell — it should open notifications. Tap Тренеры and Чат tiles — they switch tabs.
6. Toggle dark theme (if available) and confirm the screen stays legible (uses semantic tokens).
7. Confirm NO fabricated data is shown for a real user: no fake occupancy bars, no «Открыт до 23:00», no «12 в зале», no fake trainer names, no chat unread «1» badge, no fake prices.
  </how-to-verify>
  <resume-signal>Type "approved" or describe visual/interaction issues to fix</resume-signal>
</task>

</tasks>

<verification>
- `pnpm --filter client-pwa typecheck` passes (alias for `tsc -b --noEmit`).
- `pnpm --filter client-pwa lint` passes (`eslint .`) — no semicolons, single quotes, no raw Tailwind palette.
- `pnpm --filter client-pwa test` passes (`vitest run`) — `HomeScreen.adapters.test.jsx` (deriveOnboardingSteps / toSubInfo) stays green.
- No new npm dependency added. `OnboardingScreen.jsx` and non-newbie Home variants untouched. `deriveOnboardingSteps` / `toSubInfo` signatures unchanged.
</verification>

<success_criteria>
- Newbie Home visually matches the v2 mockup section-by-section (hero-card, plan-card, onboarding ring, promo, QR placeholder, composed tiles), ported as inline-style objects + the seven shared keyframes in styles.css.
- D-LIVE satisfied: membership state, first-name initials, and onboarding ring/chips are live-bound to the real API/helper; occupancy, open hours, location presence, trainer identities/counts, chat unread/SLA, and tariff prices are gracefully dropped or neutral — never hardcoded as fact.
- D-LIVE CTA satisfied: plan-card CTA and every tariff tap call `onOpenPlans` (real Plans sheet); inline tariff selector is visual-only.
- Interaction parity preserved: dismiss ×, step routing (plan→onOpenPlans, profile→onOpenOnboarding, visit→onTab('book')), tile clicks, bell→notifications.
- All three commands (typecheck, lint, test) pass.
</success_criteria>

<output>
Create `.planning/quick/260601-oan-client-pwa-newbie-home-v2-restyle/260601-oan-SUMMARY.md` when done.
</output>

# Login / Auth — design spec

Source: `design/Login.html`. Route: not yet mapped — this is the unauthenticated auth screen (add a `ROUTES.login` outside `AppLayout`, since it has no Sidebar/Header chrome). UI strings Russian.

## 1. Overview

Full-screen (`min-h-screen`) **two-column split**:

- **Left = brand/hero panel** — dark, decorative, marketing copy + feature list. Fixed dark background regardless of theme.
- **Right = form panel** — centered auth card on the app surface. Hosts **7 distinct auth states/screens** (login, forgot, sent, reset, 2FA, expired, logout), only one visible at a time.

Desktop split is `grid-template-columns: 1.05fr 1fr` (brand panel slightly wider). A theme toggle (sun/moon) floats top-right of the form panel.

**Responsive collapse:** below **860px** the brand panel is hidden entirely and the form panel becomes single-column full-width; a compact inline brand lockup (mark + "Мой зал") appears at the top of the card to compensate. Below **420px** padding tightens and the card title shrinks.

> The HTML ships a fixed bottom-center "Состояния" state-switcher pill — that's a **review/demo tool only; do NOT port it.** In React these become routes/sub-views (see §5).

## 2. Layout & regions

| Region | Content | Notes |
|---|---|---|
| Brand panel (`aside`) | brand lockup (top), hero headline + sub + 3 features (vertical-centered), footer line (bottom) | `padding: 48px 56px`; `flex-column`; dark bg `#131110` (light) / `#050505` (dark); `overflow: hidden` to clip the glow |
| Form panel (`main`) | theme-toggle (absolute top-right), centered auth card | `flex` centered both axes; `padding: 40px 24px`; `position: relative` |
| Auth card | one active screen | `width: 100%; max-width: 380px` |

Brand-panel internal vertical rhythm: top lockup → `margin: auto 0` mid block (so headline group is vertically centered) → footer. Mid block `max-width: 420px`.

## 3. Brand / hero panel

- **Background:** flat `#131110` (light theme) / `#050505` (dark theme, with `0.5px` right border in `--border`). This is a custom near-black, *not* the project's dark-card gradient — see §7 for the recommended substitution.
- **Decorative glow:** single radial circle, top-right, bleeding off-canvas. `460×460px`, `border-radius: 50%`, positioned `top: -180px; right: -160px`. Fill: `radial-gradient(circle, color-mix(in oklab, var(--accent) 26%, transparent), transparent 68%)` — i.e. an **emerald glow at ~26% opacity** fading to transparent at 68%. `pointer-events: none`.
- **Brand lockup (top):** square mark `34×34`, `radius 10px`, emerald bg (`--primary`), ink glyph `#06120c`, letter "М", `font-weight 800`, `17px`. Wordmark "Мой зал" (`nbsp` between words) `16px / 700`. Pill tag "ADMIN" pushed right (`margin-left: auto`): `10px / 700`, `letter-spacing .5px`, translucent white text `rgba(245,245,244,.55)` on `rgba(255,255,255,.07)`, pill radius, padding `3px 9px`.
- **Headline:** "Управляйте залом **из одного окна.**" — `34px / 700`, `line-height 1.12`, `letter-spacing -0.8px`, `text-wrap: balance`. The trailing fragment "из одного окна." is emerald (`.hl` → `--primary`).
- **Sub:** "Клиенты, абонементы, расписание и касса — всё под рукой. Войдите, чтобы продолжить работу." — `14.5px`, `line-height 1.6`, translucent white `rgba(245,245,244,.62)`.
- **Feature list** (3 items, `gap 13px`, top margin `30px`): each row = `28×28` rounded icon tile (`radius 8px`, bg `rgba(45,212,164,.14)`, emerald icon) + label `13.5px`, text `rgba(245,245,244,.82)`. Icons (lucide): `Lock`, `ShieldCheck`/`Shield`, `CheckCircle`.
  1. Шифрованное соединение и двухфакторная защита
  2. Гибкие роли и права доступа для сотрудников
  3. Журнал входов и активность по филиалам
- **Footer:** `12px`, `rgba(245,245,244,.42)`, `gap 16px`, three inline spans: `© 2026 «Мой зал»` · (dot) · `Тверская · Сокольники · Новокосино`.

## 4. Login form (primary state)

Card header: title **"С возвращением"** (`25px / 700`, `letter-spacing -0.6px`) + sub **"Войдите в админ-панель, чтобы управлять залом."** (`14px`, `--fg-muted`, `margin-bottom 26px`).

**Fields (in order):**

| # | Label | Type | Placeholder | Lead icon | Notes |
|---|---|---|---|---|---|
| 1 | Эл. почта | `email` | `you@moizal.ru` | `Mail` | `autocomplete=username`. Demo prefill `m.kostina@moizal.ru` — drop in React. |
| 2 | Пароль | `password` | `Введите пароль` | `Lock` | `autocomplete=current-password`; trailing eye toggle; label-row has right-aligned link **"Забыли пароль?"** (→ forgot). Error msg slot: **"Неверная почта или пароль"** (hidden unless `.err`). |

- **Field anatomy:** label row `12.5px / 600` `--fg-muted`, `margin-bottom 7px`; label-row links emerald (`--primary-deep` light / `--primary` dark), underline on hover. Input: `height 46px`, `radius 10px` (`--r-sm`), `1px` border `--border-strong`, bg `--surface`, `font 14.5px`, left padding `40px` to clear the lead icon (`14px` if no icon via `.no-lead`). Lead icon absolutely positioned `left: 13px`, `--fg-subtle`, non-interactive. Placeholder `--fg-subtle`.
- **Password eye:** `32×32` button at `right: 8px`, transparent, `--fg-subtle`; hover → `--fg-muted` + `--surface-3` bg. Toggles input `type` password↔text. Icon `Eye` (lucide). `aria-label="Показать пароль"`.

**Remember-me row** (`row-between`, `margin 4px 0 22px`): single checkbox **"Запомнить меня"**, checked by default. Custom box `18×18`, `radius 5px`, `1.5px` border. Checked state: **light** = fill/border `--fg` (ink) with check in `--bg`; **dark** = fill/border `--primary` with check `#06120c`. (No "forgot password" here — it lives in the password label row.) The right side of this row is empty in login.

**Primary submit:** full-width button **"Войти"** + trailing `ArrowRight` icon. See button tokens §7. In our app, submit → navigate to dashboard (template advances to 2FA first; treat 2FA as optional, see §5/§9).

**Divider:** centered **"или"** — flex with `1px` `--border` rules either side, label `12px` `--fg-subtle`, `margin 22px 0`.

**SSO:** exactly **one** provider button, full-width ghost style: **"Войти через Google Workspace"** with the Google "G" glyph (multicolor in real Google branding, but template uses a single `currentColor` G — keep brand-colored G or a lucide stand-in). `height 44px`, ghost styling (surface bg, `--border-strong`, hover `--surface-3`). The `.sso` container is a column with `gap 9px` (built to hold more providers; only Google present).

**Footer link:** centered **"Нет доступа? Запросить у администратора"** (`13px`, link emerald). In the template this deep-links to `Errors.html#permission`; in React point at the permission/support route (TBD).

## 5. States / screens

Seven sibling `.screen` blocks, one `.active` at a time, with an enter animation (`fade + 8px translateY rise`, `.32s cubic-bezier(.32,.72,.2,1)`). Model these as routes or a small state machine on the auth route; the bottom switcher pill is **demo-only, omit**.

| Screen | Title | Sub / body | Key elements | Primary action |
|---|---|---|---|---|
| **login** | С возвращением | Войдите в админ-панель… | §4 form | Войти → (2FA or) dashboard |
| **forgot** | Восстановление пароля | Укажите почту… вышлем ссылку для сброса | back-link "Назад ко входу"; `Mail` scr-icon; one email field; footer "Вспомнили пароль? Войти" | **Отправить ссылку** → forgot-sent |
| **forgot-sent** | Проверьте почту | …ссылка действует **30 минут** | `CheckCircle` scr-icon; `sent-to` pill showing email; footer "Письмо не пришло? …вернитесь ко входу" | **Открыть ссылку из письма** → reset; secondary ghost **Отправить ещё раз** → forgot |
| **reset** | Новый пароль | Придумайте надёжный пароль… для всех филиалов | `Lock` scr-icon; password field w/ strength meter + reqs; confirm-password field | **Сохранить и войти** → login (then dashboard) |
| **twofa** | Подтверждение входа | Введите 6-значный код… for `<b>m.kostina@moizal.ru</b>` | back-link "Назад"; `ShieldCheck` scr-icon; **6-box OTP**; resend timer/meta; footer "Нет доступа к приложению? Ввести резервный код" | **Подтвердить** → dashboard |
| **expired** | Сессия истекла | Неактивны более **30 минут**… | warn `Clock` scr-icon (amber); warn callout "Несохранённые изменения… могли быть потеряны" | **Войти снова** → login |
| **logout** | Вы вышли из системы | Сессия безопасно завершена. До скорой встречи, Маша! | centered layout; `LogOut` scr-icon (centered); footer "…можно просто закрыть вкладку" | **Войти снова** → login |

**Shared sub-components across states:**

- **`scr-icon`** — `52×52` rounded tile (`radius 15px`), `margin-bottom 22px`, holds a `24px` lucide icon. Variants: default = `--primary-soft` bg / `--primary-deep` icon (light) or `--primary` (dark); `.warn` = `--warning-soft` / `--warning-deep`; `.danger` = `--danger-soft` / `--danger` (danger variant defined but unused).
- **`back-link`** — `ArrowLeft` + text, `13px / 600`, `--fg-muted`, hover `--fg`, `margin-bottom 26px`.
- **`scr-foot`** — centered `13px` `--fg-muted` footer with emerald links.

**Error state (login):** field-level only — `.field.err` turns input border `--danger` (focus ring `--danger-soft`) and reveals an inline message row (`AlertCircle` icon + text `12px` `--danger`). Copy: "Неверная почта или пароль". No top-of-form banner. The template's button always advances regardless; in React, wire real validation.

**Loading state:** none in the template — buttons have no spinner. Add a disabled+spinner busy state on submit per our conventions.

**OTP (twofa) details:** 6 separate inputs, `inputmode=numeric`, `maxlength=1`, `flex: 1` each (`gap 10px`), `height 56px`, centered `23px / 700` `tabular-nums`. Focus → emerald border + soft ring; `.filled` → border `--fg` (light) / `--primary` (dark). Behaviors: typing a digit auto-advances; Backspace on empty box moves back; paste distributes up to 6 digits across boxes and focuses the next empty. Meta row: left **"Новый код через 0:28"** countdown (`tabular-nums`, bold value), right **"Отправить снова"** button — disabled while counting, enabled at 0 (timer text then hidden via visibility). Default countdown = 28s.

**Password strength (reset):** 4-segment meter bar (`pw-meter`, `data-score=0..4`); each filled segment colored by score: 1=`--danger`, 2&3=`--warning`, 4=`--primary-deep`. Hint text under it maps score→label: `0` "Используйте буквы, цифры и символы.", 1 "Слабый пароль", 2 "Средний пароль", 3 "Хороший пароль", 4 "Надёжный пароль". Requirements list (`pw-reqs`, 2-col grid → 1-col under 420px), each a `16px` round check chip that turns emerald (`--primary`, ink check) + text `--fg-muted` when met:
  - `len`: 8+ символов (`length >= 8`)
  - `case`: Буквы разного регистра (has lower **and** upper, Latin or Cyrillic)
  - `num`: Хотя бы одна цифра (`\d`)
  - `sym`: Символ (!@#$…) (`[^\w\s]`)
  Score = count of satisfied checks. (No explicit confirm-match validation in the template — add one.)

**Callout** (used in `expired`, `.warn` variant): flex row, `AlertTriangle` icon + text, `radius 10px`, padding `13px 15px`, `12.5px / 1.5`. Default = `--surface-2` bg + `0.5px --border`; `.warn` = `--warning-soft` bg, transparent border, `--warning-deep` text.

**`sent-to` pill** (forgot-sent): inline pill, `--surface-3` bg, pill radius, padding `7px 14px 7px 11px`, `13px / 600` `--fg`, leading `7px` emerald dot.

## 6. Interactions

- **Theme toggle** (top-right `icon-btn`, `36×36` circle, `0.5px --border` border, `--surface` bg): swaps sun↔moon icon by theme and flips `data-theme` on `<html>`. In React use the existing app theme mechanism (set `data-theme`); don't reimplement localStorage if a provider exists.
- **`data-go` navigation:** every link/button with a target advances the visible screen; two targets are real navigations — `dashboard` → Dashboard route, `permission-hint` → errors/permission route. Map `data-go` to React routing / local step state.
- **Focus states:** inputs & OTP boxes → emerald border + `0 0 0 3px var(--primary-soft)` ring. Error fields → danger border + `--danger-soft` ring.
- **Hover:** primary btn → `#000` (light) / `#5ee9b8` (dark); ghost/sso btn → `--surface-3`; icon-btn → `--surface-3` + `--fg`; links underline.
- **Active:** all `.btn` scale to `0.99` (`transform`, `.04s`).
- **Submit (our app):** "Войти" should validate then navigate to the dashboard route. Decide whether to keep the 2FA hop (§9).
- **Deep-linking:** template supports `Login.html#<state>` to open a specific screen (e.g. `#expired`). Consider equivalent routes/query for `expired` and `logout`.

## 7. Theme / tokens

Template vars map onto existing project tokens almost 1:1 — **reuse semantic classes, introduce no new tokens** except where flagged:

| Template var | Value (light) | Project token / class |
|---|---|---|
| `--accent` | `#2dd4a4` | `--primary` / `bg-primary`, `text-primary` |
| `--accent-deep` | `#0f9b76` | `--primary-deep` |
| `--accent-soft` | `#d6f5ea` | `--primary-soft` (focus rings) |
| `--bg` | `#f5f5f4` | `--bg` / `bg-bg` |
| `--surface` | `#ffffff` | `--surface` |
| `--surface-2/3` | `#fafaf9` / `#f1f0ee` | `--surface-2` / `--surface-3` |
| `--border` / `--border-strong` | `#e7e5e4` / `#d6d3d1` | same names |
| `--text` / `--text-2` / `--text-3` | `#1c1917` / `#57534e` / `#a8a29e` | `--fg` / `--fg-muted` / `--fg-subtle` |
| `--warn` / `--warn-soft` | `#e9a23b` / `#fef3e2` | `--warning` / `--warning-soft`; amber-on-light text `#a36a16` = `--warning-deep` |
| `--danger` / `--danger-soft` | `#dc2626` / `#fee2e2` | `--danger` / `--danger-soft` |
| `#06120c` (emerald ink) | — | `--primary-foreground` |

**Radii:** `--r-sm 10px` (inputs, buttons, callout), `--r-md 14px`, `--r-lg 18px`, pill `999px`. scr-icon uses `15px`. Mark tiles `9–10px`.

**Typography:** system font stack (SF/Inter/system-ui), base `14px / 1.45`. Heading scale: hero `34px/700`, card title `25px/700` (22px <420px), labels `12.5px/600`, body/sub `14–14.5px`, footers/hints `12–13px`. Note non-standard weight `650`/`655` on buttons & emphasized text — round to `600`/`700` with our token scale.

**Shadows:** `--sh-2` (subtle) and `--sh-3` (elevated) match project `--sh-2/--sh-3`. The card itself has **no shadow** (flat on the surface); only the demo switcher uses `--sh-3` (omitted).

**Primary button — important nuance:** in **light** mode the primary CTA is **ink, not emerald** — `background: var(--text)` (near-black) / text `--bg` (light); hover `#000`. In **dark** mode it flips to **emerald** — `background: var(--primary)` / text `#06120c`; hover `#5ee9b8`. Same for the checked checkbox and active switcher. Reproduce this theme-dependent inversion (likely a `.btn-primary` variant using `--fg` bg in light + `--primary` in dark, e.g. via the `dark:` custom variant).

**Dark theme:** full parity — surfaces/text/borders redefined under `[data-theme="dark"]` (identical to project tokens), soft colors become translucent rgba, brand panel bg → `#050505`. Semantic classes switch automatically; no `dark:` needed except the primary-button/checkbox/OTP-filled inversions noted above.

**Brand-panel background — project substitution:** the raw `#131110` / `#050505` is bespoke. Per project convention, dark hero surfaces use `linear-gradient(160deg,#1c1917,#2a2826)` + an emerald radial glow, and emerald-on-dark ink is `#06120c`. **Recommendation:** render the brand panel with that project gradient (or a dedicated `--elevated`-based dark token) instead of the flat raw hex, keeping the `~26%` emerald radial glow described in §3. Flag for design sign-off if exact `#131110` is required.

## 8. Responsive notes

- **> 860px (desktop):** two-column split `1.05fr / 1fr`; brand panel visible; inline mobile lockup hidden.
- **≤ 860px (tablet/mobile):** `grid-template-columns: 1fr` → brand panel `display:none`; form panel full-width, card still capped at `380px` and centered. Inline brand lockup shows atop the card (`card-mobile-brand`, `margin-bottom 30px`): `30×30` mark (`radius 9px`) — **light:** `--fg` bg / emerald glyph; **dark:** `--primary` bg / `#06120c` glyph — plus "Мой зал" `15px/700`.
- **≤ 420px (small mobile):** form panel padding `28px 18px 90px` (extra bottom for the demo pill — drop the 90px in React), card title `22px`, password requirements collapse to single column.
- No horizontal scroll/overlap at any width; OTP boxes use `flex:1 min-width:0` so the 6-up row shrinks cleanly on narrow screens.

## 9. Open questions / ambiguities

- **2FA mandatory?** Template login → 2FA → dashboard, but 2FA inputs aren't validated (any/empty advances). Decide: always require 2FA, make it conditional, or skip and go straight to dashboard. CLAUDE/task note says submit should navigate to dashboard — simplest is login → dashboard, with 2FA as a separately reachable state.
- **Backup-code link** ("Ввести резервный код") points back to `login` in the template — no real backup-code screen exists. Stub or omit.
- **Reset flow entry:** `reset` is reached from the "Открыть ссылку из письма" demo button; in production it'd be a tokenized email link (`/reset?token=…`). Treat as its own route.
- **`expired` / `logout`** are post-auth/system states surfaced on the auth screen via deep-link. Confirm how they're triggered (session middleware redirect, logout action) and whether they get dedicated routes.
- **Google "G" glyph:** template uses a single-color `currentColor` G; decide between the official multicolor Google mark vs. a monochrome lucide/icon stand-in.
- **Demo prefilled values** (email `m.kostina@moizal.ru`, masked password, the personalized "Маша" in logout) are mock content — drive from real user/session data or remove.
- **No loading/submitting state** in the template — add per project conventions (disabled + spinner on the active CTA).
- **State-switcher pill & inter-screen animation** are demo affordances; the rise-in animation is optional polish, the switcher must not ship.

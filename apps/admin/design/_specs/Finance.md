# Finance — «Финансы» (structural spec)

> Source: `design/Finance.html`. Scope: page main content only — shared `AppLayout` (sidebar, topbar, theme toggle, `.g2-*` mobile dock) is provided elsewhere and is OUT OF SCOPE.

## 1. Purpose
Finance overview for a fitness-club admin: a 4-tile KPI strip plus three tabbed tables — payment register, failed payments, and trainer payouts — with transaction-detail / refund / payout modals.

> Note: despite being filed under "Аналитика", this screen has **no charts**. It's KPI-tiles + tabs + tables + modals. AreaTrendChart/DonutChart do NOT apply here. KPI tiles map to existing KPI-tile components.

## 2. Page head
- **H1**: `Финансы` (23px / 700 / letter-spacing −0.5px).
- **Subtitle** (`.sub`, 13.5px, `fg-muted`), verbatim: `Все платежи, возвраты и выплаты тренерам · апрель 2026`
- **Header action** (right-aligned via `margin-left:auto`): one ghost button `Экспорт` with a download icon (lucide `download`). On click it shows a loading spinner then a transient "done" state, and fires toast `Реестр выгружен в Excel`. No period selector / date-range / branch filter in the page head — branch is the global sidebar control; period is fixed copy ("апрель 2026").
- Layout: `display:flex; align-items:flex-start; gap:16px; flex-wrap:wrap; margin-bottom:16px`.

## 3. Overall content layout
Single column, `.content` max-width **1160px**, padding `24px 26px 60px` (mobile `18px 14px 60px`). Top-to-bottom:
1. **Page head** (H1 + subtitle + Экспорт).
2. **KPI strip** — 4 tiles, `grid-template-columns:repeat(4,1fr); gap:12px; margin-bottom:18px`.
3. **Tab bar** — segmented control, 3 tabs (`margin-bottom:16px`).
4. **Tab panes** — exactly one visible at a time; each is a single `.panel` card containing a toolbar + a table. Three panes: `reg` (default active), `fail`, `pay`.

No sticky elements inside content (topbar/sidebar sticky belong to layout). Reveal animations: page head + each KPI tile + tab bar + first panel fade-up with staggered `--d` delays (40/100/160/220/260/300 ms); table rows skeleton-load then stagger in. Respect `prefers-reduced-motion` (render final state, no count-up/skeleton).

## 4. Sections / components

### 4.1 KPI strip (`.strip .s`) — 4 tiles → KPI-tile component
Tile: `surface` bg, `0.5px border`, radius `--r-md` (14px), `box-shadow sh-1`, padding `14px 16px`. Hover: lift `translateY(-2px)`, `sh-2`, border→`border-strong`.
- **Label** (`.s-l`): 12px `fg-muted`, leading 13px icon in `fg-subtle`, `gap:6px`.
- **Value** (`.s-v`): 21px / 700 / −0.5px, `tabular-nums`, `margin-top:6px`. Optional unit suffix `.u` (` ₽`) at 12px / 600 / `fg-subtle`. Count-up animation from 0 over 1100ms (ease-out cubic), ru-RU grouping with NBSP thousands separators. Variants: `.danger` → `danger` color; `.accent` → `primary-deep` (light) / `primary` (dark).

| # | Label | Value | Icon (lucide) | Value variant |
|---|-------|-------|---------------|---------------|
| 1 | `Оборот за месяц` | `2 248 000` + ` ₽` | dollar-sign | default |
| 2 | `Успешных` | `1 284` | check | accent (primary) |
| 3 | `Неудачных` | `18` | x-circle | danger |
| 4 | `К выплате тренерам` | `428 000` + ` ₽` | users (single-person) | default |

### 4.2 Tab bar (`.tabs` segmented control)
Pill container: `surface-3` bg, radius 11px, padding 4px, `width:fit-content`, horizontally scrollable on overflow (hidden scrollbar). Tabs (`.tab`): 13px / 600, `fg-muted`, height 34px, padding `0 15px`, radius 8px. Active tab: `surface` bg, `fg` text, `sh-1`. Optional count badge `.tb` on a tab: 10.5px / 700, `danger` bg, white text, pill, min 16px.
- Tab 1: `Реестр платежей` (active by default) → pane `reg`.
- Tab 2: `Неудачные` + badge `18` → pane `fail`.
- Tab 3: `Выплаты тренерам` → pane `pay`.

### 4.3 Panel + toolbar (shared shell for all panes)
`.panel`: `surface`, `0.5px border`, radius `--r-lg` (18px), `sh-2`, `overflow:hidden`.
`.toolbar`: `display:flex; align-items:center; gap:10px; padding:12px 16px`, bottom `0.5px border`, `surface-2` bg.
- **Search** (`.search`): grows, `max-width:300px`, 36px input, radius 9px, `border-strong`, leading search icon in `fg-subtle` at left:12px. Focus: border→`primary`, ring `0 0 0 3px primary-soft`.
- **Filter selects** (`.filt`): 36px, radius 9px, `border-strong`, 12.5px / 600, custom chevron (right). `appearance:none`.
- **Right count** (`.tcount`): `margin-left:auto`, 12.5px `fg-muted`, bold portion in `fg`.

### 4.4 Table primitive (`.thead` / `.trow`)
CSS grid rows; `gap:14px; align-items:center; padding:12px 16px`. Per-pane column templates:
- **reg**: `92px 1.5fr 1fr 0.9fr 110px`
- **fail**: `92px 1.4fr 1.3fr 100px 120px`
- **pay**: `1.4fr 0.9fr 1fr 1fr 130px`

`.thead`: 10.5px / 700 uppercase, letter-spacing 0.5px, `fg-subtle`, bottom border. `.trow`: bottom border (last row none), `cursor:pointer`, hover→`surface-2`, active `scale(.997)`.

Cell pieces:
- `.t-date`: 12.5px `fg-muted` tabular; sub time `.tm` 11px `fg-subtle`. (e.g. `28 апр` / `14:12`).
- Client cell `.cl`: 32px round avatar (`.cl-ava`, gradient bg per-row, white 11.5px/700 initials) + name (`.cl-name` 13px/600, ellipsis) + sub (`.cl-sub` 11.5px `fg-subtle`).
- `.t-method`: 12.5px `fg-muted`.
- `.t-amt`: 700, tabular, right-aligned. `.minus` variant → `danger` (refunds, prefixed `−`).
- `.t-reason`: 12px `danger`.
- Status pill `.st`: 11px / 700, padding `3px 10px`, pill. Variants (token map):
  - `.ok` / `.paid` → bg `primary-soft`, text `primary-deep` (light) / `primary` (dark) — labels `Успешно` / `Выплачено`.
  - `.refund` → bg `surface-3`, text `fg-muted` — label `Возврат`.
  - `.pending` → bg `warning-soft`, text `#a36a16` (light) / `warning` (dark) — label `Ожидание`.
  - `.fail` → bg `danger-soft`, text `danger`.

Loading: skeleton rows (shimmer bars + round avatar placeholder) render first, then real rows swap in with staggered `--d` (~32–38ms × index).

### 4.5 Pane A — Реестр платежей (`reg`)
Toolbar: search `Поиск по клиенту, ID…`; select `[Все статусы | Успешные | Возвраты | Ожидание]`; select `[Все способы | Карта | СБП | Наличные]`; count `Всего 1 302` (bold 1 302).
Header columns: `Дата` · `Клиент / операция` · `Способ` · `Сумма`(right) · `Статус`(right).
Rows are clickable → open transaction-detail modal (4.7). 6 seed rows (see §5.1).

### 4.6 Pane B — Неудачные (`fail`)
Toolbar: search `Поиск…`; count `Требуют внимания · 18` (bold 18). No filter selects.
Header columns: `Дата` · `Клиент` · `Причина` · `Сумма`(right) · `Действие`(right).
Client sub-line is the **phone** here (not a plan). Last column is a small ghost button `Повторить` (lucide `rotate-cw` icon) — on click: spinner → done state `Отправлено`, toast `Повторный платёж отправлен · <name>`. 4 seed rows (§5.2).

### 4.6b Pane C — Выплаты тренерам (`pay`)
Toolbar: plain label `Период: апрель 2026` (13px/600) + count `К выплате 428 000 ₽ · 6 тренеров` (bold amount). No search.
Header columns: `Тренер` · `Тренировок`(right) · `Начислено`(right) · `К выплате`(right) · `Статус`(right).
Note: the `Тренировок` data cell renders an em-dash `—` in `fg-subtle` (count not shown per-row; count is in the spec line). `Начислено` 600-weight; `К выплате` 700-weight.
Last column: if `paid` → status pill `Выплачено`; else a small primary button `Выплатить` → opens payout modal (4.9). 4 seed rows (§5.3).

### 4.7 Modal — Transaction detail (`data-screen="detail"`)
Centered modal (mobile: bottom sheet), `width min(480px, 100vw−32px)`, radius 18px, `sh-3m`, pop-in animation.
- **Head**: 42px rounded icon tile (`primary-soft` bg, dollar-sign), title `Транзакция`, mono sub = txn id `#TXN-48201`, round close button.
- **Body**: big amount `.big-amt` (30px/700, e.g. `24 000 ₽`; prefixed `−` for refunds) → status pill below → definition rows (`.drow`, dashed separators, key `fg-subtle` left / value 600 right):
  - `Клиент` → name
  - `Назначение` → plan/desc
  - `Способ` → method
  - `Комиссия эквайринга` → `−480 ₽ (2%)`
  - `Зачислено` → `23 520 ₽`
  - `Дата` → `28 апр 2026, 14:12`
  - Then label `Журнал` + a small timeline (`.tl`): items with a 16px round check dot (`primary-soft`), title + mono time. Seed entries: `Платёж подтверждён банком` (14:12:08), `Чек отправлен на email` (14:12:10).
- **Foot**: ghost `Чек` (toast `Чек отправлен повторно`) + ghost `Оформить возврат` (switches modal to refund screen).
- Client/desc/method/amount/date/status are populated from the clicked row.

### 4.8 Modal — Refund (`data-screen="refund"`)
- **Head**: warn icon tile (`warning-soft`, lucide `reply`/`corner-up-left`), title `Возврат средств`, sub `#TXN-48201 · 24 000 ₽`.
- **Body**:
  - label `Сумма возврата` + chip group: `Полный · 24 000 ₽` (selected) / `Частичный`. Selecting `Частичный` reveals an amount input (`Сумма`, default `12 000`).
  - label `Причина` + select `[Клиент отказался от абонемента | Ошибка при оплате | Двойное списание | Другое]`.
  - Danger callout (`danger-soft` bg, warning-triangle icon): text `Деньги вернутся на карту •• 4417 за 3–5 дней. Абонемент станет неактивным.` (bold `3–5 дней`).
- **Foot**: ghost `Отмена` + **danger** button whose label/toast track the chip: full → `Вернуть 24 000 ₽` / toast `Возврат 24 000 ₽ оформлен`; partial → `Вернуть 12 000 ₽` / toast `Возврат 12 000 ₽ оформлен`. On click: spinner → close modal → toast.
- Chip selected state `.chip.on`: bg `fg` / text `bg` (light), bg `primary` / text `#06120c` (dark).

### 4.9 Modal — Trainer payout (`data-screen="payout"`)
- **Head**: primary icon tile (dollar-sign), title `Выплата тренеру`, sub `<name> · апрель 2026`.
- **Body**: definition rows:
  - `Начислено за тренировки` → `152 250 ₽`
  - `Бонус за заполняемость` → `7 650 ₽`
  - `Удержан НДФЛ (6%)` → `−8 568 ₽`
  - `Комиссия зала (30%)` → `−45 900 ₽`
  - separator row (solid top border) `К выплате` (bold `fg`) → amount (18px), populated from the clicked row (e.g. `106 182 ₽`).
  - label `Способ выплаты` + select `[Карта •• 8842 | СБП по телефону | Наличные из кассы]`.
- **Foot**: ghost `Отмена` + **primary** `Выплатить`. On click: spinner → close → toast `Выплата <amount> ₽ проведена` (template uses `106 182 ₽`).
- Name + payout amount come from the row's `Выплатить` button.

### 4.10 Toast
Centered-bottom pill, `fg` bg / `bg` text (light), `primary`/`#06120c` (dark), check icon + message, auto-hides ~2.2s.

## 5. Data (for TS types + mocks)

### 5.1 Register rows (`reg`)
| date | time | initials | gradient | name | desc | method | amount ₽ | status |
|------|------|----------|----------|------|------|--------|---------|--------|
| 28 апр | 14:12 | АП | `#6366f1→#818cf8` | Анна Петрова | Абонемент «12 месяцев» | Карта •• 4417 | 24 000 | ok |
| 28 апр | 12:55 | МС | `#10b981→#34d399` | Максим Соколов | Продление · 3 месяца | СБП | 9 000 | ok |
| 28 апр | 12:30 | ИК | `#0ea5e9→#38bdf8` | Игорь Климов | Возврат · абонемент | Карта •• 1180 | 9 000 (−) | refund |
| 27 апр | 19:40 | КЛ | `#f43f5e→#fb7185` | Карина Левчук | Персональные · 8 занятий | Карта •• 0921 | 14 400 | ok |
| 27 апр | 18:02 | НГ | `#8b5cf6→#a78bfa` | Нина Громова | Абонемент «6 месяцев» | Онлайн-ссылка | 16 000 | pending |
| 27 апр | 11:18 | АМ | `#f59e0b→#fbbf24` | Алина Маркова | Абонемент «3 месяца» | СБП | 9 000 | ok |

Toolbar count: `Всего 1 302`.

### 5.2 Failed rows (`fail`)
| date | time | initials | gradient | name | phone | reason | amount ₽ |
|------|------|----------|----------|------|-------|--------|---------|
| 28 апр | 10:02 | ИК | `#0ea5e9→#38bdf8` | Игорь Климов | +7 916 332-09-11 | Карта отклонена банком | 24 000 |
| 27 апр | 21:15 | ОР | `#f43f5e→#fb7185` | Олег Романов | +7 903 209-67-31 | Недостаточно средств | 9 000 |
| 27 апр | 16:40 | СБ | `#10b981→#34d399` | Семён Бойко | +7 925 110-08-44 | Истёк срок действия карты | 16 000 |
| 26 апр | 13:22 | ВД | `#f59e0b→#fbbf24` | Вера Дроздова | +7 909 442-18-77 | Таймаут эквайринга | 3 500 |

Toolbar count: `Требуют внимания · 18`.

### 5.3 Payout rows (`pay`)
| initials | gradient | name | spec | accrued ₽ | payout ₽ | status |
|----------|----------|------|------|-----------|----------|--------|
| ОВ | `#8b5cf6→#ec4899` | Ольга Власова | Йога · 96 трен. | 159 900 | 106 182 | pending |
| АП | `#6366f1→#818cf8` | Артём Поляков | Силовые · 88 трен. | 141 200 | 93 600 | pending |
| ВД | `#0ea5e9→#38bdf8` | Вадим Дроздов | Бокс · 72 трен. | 118 800 | 78 700 | paid |
| НЖ | `#10b981→#34d399` | Наталья Жук | Стретчинг · 64 трен. | 96 000 | 63 200 | pending |

Toolbar: `Период: апрель 2026` · count `К выплате 428 000 ₽ · 6 тренеров`.

> The avatar gradients above are decorative/random per row — not from the token palette. Either store a deterministic gradient per row or derive one from initials. Do NOT map them to chart-1..5.

### 5.4 KPI values
`2 248 000 ₽`, `1 284`, `18`, `428 000 ₽` (see §4.1).

### 5.5 Payout breakdown (modal, seed)
Начислено `152 250 ₽` · Бонус `7 650 ₽` · НДФЛ −`8 568 ₽` · Комиссия −`45 900 ₽` · К выплате `106 182 ₽`. (These are static template figures; the row click only overrides name + final payout amount.)

## 6. Interactions
- **Tab switching**: click tab → toggle active tab + matching pane; re-trigger row stagger animation on the now-visible table.
- **Search / filter selects**: present and styled but static in the mock (no live filtering wired). Build as controlled inputs; client-side filter is a reasonable enhancement.
- **Register row click** → opens transaction-detail modal populated from the row.
- **Detail → "Оформить возврат"** → switches to refund modal screen (same overlay).
- **Refund chip toggle** (Полный/Частичный) → shows/hides amount field; updates the danger button label + success toast text.
- **Payout button** (per row) → opens payout modal with name + amount.
- **Action buttons with async feedback** (`Экспорт`, `Повторить`, refund confirm, payout confirm): show inline spinner ~0.85–1.1s; modal-confirm buttons close the modal then toast; `Экспорт`/`Повторить` flip to a green "done"/"Отправлено" state for ~1.5s then revert. Reduced-motion: skip spinner, fire toast immediately.
- **Modal dismiss**: backdrop click, close (×) button, and (for sheet) Esc.
- Hover/active states: KPI tile lift; row hover bg + active scale; button `:active scale(.99)`; segmented tab hover text-darken.

## 7. Empty / special states
No explicit empty states in the mock. Provide skeleton loading (already part of table primitive) and a sensible "no results" placeholder if search/filter is wired. Failed-payments tab badge `18` and toolbar "Требуют внимания · 18" imply more rows than the 4 seeded — treat counts as independent of `rows.length`.

## 8. Responsive (`@media`)
- **≤900px**: KPI strip → 2 columns (`grid-template-columns:repeat(2,1fr)`). (Sidebar/dock behavior is layout-level, out of scope.)
- **≤760px**: content padding `18px 14px 60px`. **Tables become stacked cards**: `.thead` hidden; each `.trow` becomes a 2-col card (`1fr auto`, gap `6px 10px`) with `0.5px border`, radius 12px, margin 10px, padding 13px. Client cell + date + method + reason span full width (`grid-column:1/3`); inline cell labels (`.t-cell-lbl`, e.g. `Способ:`, `Причина:`) appear at 11px `fg-subtle`. Modals dock to bottom as full-width sheets (radius `22px 22px 0 0`, footer stacks `column-reverse`, buttons full-width).
- **≤640px** (from shared dock CSS, but relevant): non-small buttons get `min-height:44px` touch targets.
- Tab bar is always horizontally scrollable if it overflows.

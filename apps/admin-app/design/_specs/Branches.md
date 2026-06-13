# Branches page spec — extracted from `design/Branches.html`

The "Филиалы" (branches) list screen for the ClubCore admin panel — manages the chain's gym locations. This doc is the SOLE source for the React rebuild. Reproduce the **visual identity**, not the HTML; build clean, responsive, token-driven components. **Ignore** the shared chrome (`.sidebar`, `.topbar`, theme-toggle, and the `.g2-*` mobile-dock IIFE) — `AppLayout` provides those. Spec covers ONLY `.content`.

Token map (raw → semantic): `--accent #2dd4a4`→`primary`; `--accent-deep #0f9b76`→`primary-deep`; `--accent-soft`→`primary-soft`; `--text`→`fg`; `--text-2`→`fg-muted`; `--text-3`→`fg-subtle`; `--bg`→`bg`; `--surface`→`surface`; `--surface-2`→`surface-2`; `--surface-3`→`surface-3`; `--border`→`border`; `--border-strong`→`border-strong`; `--warn #e9a23b`→`warning`, `--warn-soft`→`warning-soft` (paused-pill text uses raw `#a36a16` light / `--warn` dark); `--danger`→`danger`; `--indigo #6366f1`→`indigo`, `--indigo-soft`→`indigo-soft` (soon-pill text raw `#a5b4fc` in dark); `--mono`→monospace. Radii: `--r-sm 10px`, `--r-md 14px`, `--r-lg 18px`, pill `999px`. Shadows: `--sh-1` (subtle), `--sh-2` (card), `--sh-3`/`--sh-3m` (modal). **Per-branch mark + manager-avatar use raw CSS gradients (do NOT tokenize)** — see data table.

---

## 1. Purpose
Card-grid overview of every gym branch in the chain, with network KPI totals, per-branch stats, and create/edit-branch flow.

## 2. Page head (`.page-head`, flex, `align-items:flex-start`, wraps, `margin-bottom:20px`)
- **H1**: `Филиалы` — 23px / 700 / `-0.5px` tracking.
- **Subtitle** (`.sub`, 13.5px `fg-muted`, `max-width:560px`, line-height 1.5; `<b>` parts in `fg`): verbatim — **`3 действующих` филиала и 1 в подготовке. Управляйте картотекой, командой и настройками каждого зала.** (the "3 действующих" is bold.)
- **Header actions** (`.ha`, pushed right via `margin-left:auto`, gap 9px): single button **`Добавить филиал`** — `.btn .btn-primary`, leading `+` plus icon (lucide `plus`, 15px). Opens the create-branch modal. **No view toggle, no export, no search on this page.**

## 3. Overall content layout (`.content`, padding `26px 26px 60px`, `max-width:1160px`)
Top-to-bottom, single column:
1. **Page head** (above).
2. **Network summary strip** (`.strip`) — 4 KPI tiles, `grid-template-columns:repeat(4,1fr)`, gap 12px, `margin-bottom:20px`.
3. **Branch card grid** (`.branches`) — `grid-template-columns:repeat(auto-fill, minmax(330px,1fr))`, gap 16px. Holds branch cards + one trailing dashed "add" draft card.

No map, no comparison table, nothing sticky in the content area. The grid is the only "card grid"; there's no table view.

## 4. Sections / components

### 4a. Summary strip tile (`.strip .s`)
`surface` bg, `0.5px border`, radius `--r-md` (14px), `--sh-1`, padding `14px 16px`.
- `.s-l` label: 12px `fg-muted`.
- `.s-v` value: 22px / 700 / `-0.5px`, `tabular-nums`, `margin-top:6px`. Optional `.u` unit suffix: 13px `fg-subtle` 600 (used for ` + 1` and ` ₽`).

Four tiles (label → value):
| Label | Value | Unit suffix |
|---|---|---|
| `Филиалов` | `3` | ` + 1` |
| `Клиентов всего` | `847` | — |
| `Тренеров` | `12` | — |
| `Выручка · апрель` | `2 248 000` | ` ₽` |

### 4b. Branch card (`.bcard`)
`surface` bg, `0.5px border`, radius `--r-lg` (18px), `--sh-2`, `overflow:hidden`, flex column. Four stacked regions:

**(1) Top (`.bcard-top`, padding `18px 18px 14px`, flex, gap 13px):**
- **Mark** (`.bcard-mark`): 46×46px, radius 13px, white 800 17px letter, centered. Background = per-branch raw gradient (see data).
- Name+address block (`flex:1`, `min-width:0`):
  - **Name** (`.bcard-name`): 16px / 700 / `-0.3px`, flex row gap 8px wrap. Followed inline by status pill.
  - **Status pill** (`.b-status`): 10px / 700 / uppercase / `0.3px` tracking, padding `2px 8px`, pill radius. Variants:
    - `.active` → `primary-soft` bg, `primary-deep` text (dark: `primary`). Label `Активен`.
    - `.soon` → `indigo-soft` bg, `indigo` text (dark: raw `#a5b4fc`). Label `Скоро`.
    - `.paused` → `warning-soft` bg, raw `#a36a16` text (dark: `--warn`). Label `Пауза`. *(defined; not used by current data)*
  - **Address** (`.bcard-addr`): 12.5px `fg-subtle`, `margin-top:4px`, flex gap 6px, leading lucide `map-pin` (13px). Text = `{metro} · {addr}`.

**(2) Manager bar (`.bcard-mgr`, padding `12px 18px`, top+bottom `0.5px border`, `surface-2` bg, flex gap 9px):**
- **Avatar** (`.mgr-ava`): 28×28px circle, white 700 11px initials, centered. Bg = per-branch raw `mgrC` gradient. For `soon` branches with no manager, bg is `surface-3` and text color forced to `fg-subtle` (initials shown as `—`).
- `.mgr-name`: 12.5px / 600. `.mgr-role`: 11px `fg-subtle`, always literal **`Управляющий`**.

**(3) KPI grid (`.bcard-kpis`, `grid-template-columns:repeat(2,1fr)`, `gap:1px` over a `border`-colored bg → 1px hairline separators):**
Each cell `.bk` = `surface` bg, padding `13px 16px`.
- `.bk-l` label: 11px `fg-subtle`, flex gap 6px, leading 13px lucide icon.
- `.bk-v` value: 17px / 700 / `-0.3px`, `tabular-nums`, `margin-top:4px`. Optional `.u` unit: 12px `fg-subtle` 600.

For **active/paused** branches → 4 cells (2×2):
| Cell | Icon (lucide) | Label | Value | Unit |
|---|---|---|---|---|
| 1 | `users` | `Клиенты` | `{clients}` | — |
| 2 | `user` (circle+arc) | `Тренеры` | `{trainers}` | — |
| 3 | `clock` | `Заполн.` | `{occ}` | `%` |
| 4 | `dollar-sign` | `Выручка` | `{mrr}` | ` ₽` |

For **soon** branches → single full-width cell (`grid-column:1/3`): `clock` icon + `{opening}` text as the label, and value line `Идёт подготовка зала` rendered at 14px `fg-muted` (overrides `.bk-v`).

**(4) Footer (`.bcard-foot`, padding `13px 18px`, `margin-top:auto`, flex gap 8px):** two equal-width (`flex:1`) `.btn-ghost .btn-sm` buttons:
- **`Настройки`** — leading lucide `settings` (gear, 14px). **Navigates to the per-branch settings/detail page** (`Branch-Settings.html` → route like `ROUTES.branchSettings(id)`).
- **`Изменить`** — leading lucide `edit`/`pencil-square` (14px). Opens the edit-branch modal pre-filled for this branch (does NOT navigate).

`.btn-ghost` = `surface` bg, `0.5px border-strong`, `fg` text; hover → `surface-3`. `.btn-sm` = h34px, padding `0 12px`, 12.5px, radius 9px.

### 4c. "Add branch" draft card (`.bcard.draft`, last grid item)
Dashed border (`border-style:dashed`), no shadow, `surface-2` bg, centered content, `min-height:280px`.
- `.draft-ico`: 52×52px, radius 15px, `surface-3` bg, `fg-subtle` lucide `plus` (24px), `margin:0 auto 14px`.
- `.draft-t`: 14.5px / 650 — **`Добавить филиал`**.
- `.draft-s`: 12.5px `fg-subtle`, `max-width:220px`, margins `5px 0 16px` — **`Новый зал появится в переключателе и отчётах`**.
- Button `.btn-ghost .btn-sm` — **`Создать`**. Opens the create-branch modal.

### 4d. Create / Edit branch modal (`#modal`, `.am-overlay`/`.am-modal`)
Shared `am-*` modal shell (same family as `shared-modals.md`): overlay `rgba(0,0,0,.4)` + `blur(7px)`, modal `surface`, radius 18px, `--sh-3m`, `width:min(520px, calc(100vw-32px))`, `max-height:calc(100dvh-48px)`, `pop` entry animation (`scale(.96) translateY(8px)`→none, 0.26s).
- **Head** (`.am-modal-head`, padding `18px 22px`, bottom border): icon tile (`.am-modal-ico` 44×44, radius 13px, `primary-soft` bg, `primary-deep`/`primary` icon — lucide `building`/branch glyph 20px) + title block + close button (`.am-modal-close`, 32px circle, `surface-3` bg).
  - Create mode: title **`Новый филиал`**, sub **`Заполните данные зала`**.
  - Edit mode: title **`Редактировать филиал`**, sub **`{name} · #BR-{ID}`** (ID = uppercased branch id, e.g. `#BR-TVER`).
- **Body** (`.am-modal-body`, padding `6px 22px 18px`). Fields (`.field` mb13; `.field-row` = 2-col grid gap 10px → 1-col on mobile). Inputs `.am-input`/`.am-select`: full-width, h42, `0.5px border-strong`, `surface-2` bg, radius 11px, 14px text; focus → `primary` border + `surface` bg + `0 0 0 3px primary-soft` ring. Selects have custom chevron bg-image.
  - **Название** — text, placeholder `Например, Арбат`.
  - Row: **Город** (text, default value `Москва`) | **Метро** (text, placeholder `Станция`).
  - **Адрес** — text, placeholder `Улица, дом`.
  - Row: **Телефон** (tel, placeholder `+7 ___ ___-__-__`) | **Управляющий** (select: `Не назначен`, `Ольга Воронина`, `Роман Ким`, `Сергей Белов`).
  - Row: **Статус** (select: `Скоро открытие`, `Активен`, `На паузе`) | **Цвет на карте** (`.swatches`, 5 swatches 30×30 radius 9px; selected has `.on` double-ring). Swatch gradients: `#2dd4a4→#0f9b76` (default/on), `#6366f1→#818cf8`, `#f59e0b→#fbbf24`, `#f43f5e→#fb7185`, `#0ea5e9→#38bdf8`.
- **Foot** (`.am-modal-foot`, padding `14px 22px`, top border, `surface-2` bg, right-aligned, gap 8px; mobile → `column-reverse`): `.btn-ghost` **`Отмена`** (closes) + `.btn-primary` save (create label **`Создать филиал`**, edit label **`Сохранить`**).

### 4e. Toast (`.toast`, bottom-center pill)
`fg` bg / `bg` text (dark: `primary` bg), padding `11px 16px`, pill, `--sh-3`, leading lucide `check` (15px), slide-up `.show`, auto-hides ~2.2s. Messages: **`Филиал создан`** (create) / **`Изменения сохранены`** (edit).

## 5. All data (for TS types + mocks)

**Network totals (strip):** branchesActive `3`, branchesUpcoming `1`, clientsTotal `847`, trainersTotal `12`, revenueApril `2 248 000 ₽` (label `Выручка · апрель`).

**Branches** (4 total — fields: `id, name, mark, gradient, status, metro, addr, manager{name,initials,gradient}, clients, trainers, occ%, mrr, opening?`):

| id | name | mark | mark gradient | status | metro | addr | manager | initials | mgr gradient | clients | trainers | occ% | mrr (₽) | opening |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| `tver` | Тверская | Т | `135deg,#2dd4a4,#0f9b76` | active | м. Тверская | ул. Тверская, 18 | Ольга Воронина | ОВ | `135deg,#8b5cf6,#ec4899` | 247 | 5 | 88 | 742 000 | — |
| `sokol` | Сокольники | С | `135deg,#6366f1,#818cf8` | active | м. Сокольники | ул. Стромынка, 4 | Роман Ким | РК | `135deg,#0ea5e9,#38bdf8` | 312 | 4 | 81 | 905 000 | — |
| `novok` | Новокосино | Н | `135deg,#f59e0b,#fbbf24` | active | м. Новокосино | Суздальская ул., 26 | Сергей Белов | СБ | `135deg,#10b981,#34d399` | 288 | 3 | 74 | 601 000 | — |
| `city` | Москва-Сити | М | `135deg,#0ea5e9,#38bdf8` | soon | м. Деловой центр | Пресненская наб., 8 | Не назначен | — | `var(--surface-3)` | 0 | 0 | 0 | 0 | Открытие 1 июня |

Status enum → pill label map: `active`→`Активен`, `soon`→`Скоро`, `paused`→`Пауза`. (Modal status select uses longer labels: `Активен` / `Скоро открытие` / `На паузе`.) `occ` and `mrr` are display strings; `mrr` is pre-grouped with thin-space thousands and gets a ` ₽` suffix — prefer storing numbers and formatting via `formatRub`/`formatInt`.

**Note / discrepancy to resolve:** prose + strip claim "3 действующих + 1 в подготовке" but data has exactly 4 branches (3 active, 1 soon) — strip's "Филиалов 3 +1" = 3 active plus 1 upcoming. Keep totals derived from the branch list. `clients/trainers/occ/mrr` sums of active branches = 847 clients (247+312+288), 12 trainers (5+4+3), 2 248 000 ₽ (742k+905k+601k) — these match the strip exactly, so compute them.

## 6. Interactions
- **Add branch**: header `Добавить филиал` OR draft card `Создать` → open modal in **create** mode (resets fields; Город=`Москва`, Статус=`Скоро открытие`, Управляющий=`Не назначен`).
- **Edit branch**: card footer `Изменить` → open modal in **edit** mode pre-filled from that branch (name, metro w/o `м. ` prefix, addr, manager, status; phone is mocked).
- **Open branch (navigation)**: card footer **`Настройки`** is the only nav control → per-branch settings/detail route. (No whole-card click navigation in the source; consider making the card/name a link in React, but `Настройки` is the canonical target.)
- **Modal close**: `×` button, `Отмена`, or overlay backdrop click. Save button closes modal AND fires toast.
- **Swatch picker**: clicking a swatch toggles `.on` (single-select).
- **No** kebab menu, no status switches, no view toggle, no filters/search on this page.
- **Hover/active**: `.bcard` static (no hover transform in source). Ghost buttons hover → `surface-3`. Primary button hover → `#000` (light) / stays `primary` (dark); all `.btn:active` → `scale(.99)`. Inputs focus ring as in 4d.

## 7. Empty / special states
- **`soon` branch**: no manager (avatar `—` on `surface-3`), single full-width KPI cell showing opening date + `Идёт подготовка зала`.
- **Draft "add" card** always present as the final grid item (acts as the empty-slot affordance). No separate "no branches" empty state exists in the source — if branch list is empty, only the draft card would show; design a minimal empty message if desired.

## 8. Responsive (`@media`)
- **≤900px**: strip → `repeat(2,1fr)` (2 cols). (Sidebar/topbar/dock behavior is shared chrome — ignore.)
- **≤720px**: `.content` padding → `18px 14px 60px`; header `.ha` becomes full-width with the button stretching (`flex:1`, `margin-left:0`); `.branches` → single column (`1fr`); modal docks to bottom sheet (`align-items:flex-end`, full-width, radius `22px 22px 0 0`, `max-height:92dvh`), footer stacks `column-reverse` full-width, `.field-row` collapses to 1 column.
- Branch grid is intrinsically responsive via `auto-fill minmax(330px,1fr)` between these breakpoints. Ensure no horizontal scroll/overlap at any width.

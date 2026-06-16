# Audit — «Журнал действий» (audit log)

## 1. Purpose
A chronological, filterable audit log of who changed what and when in the admin system, with per-event detail (before/after diff) in a modal.

## 2. Page head
- **H1**: `Журнал действий` — 23px / 700 / letter-spacing -.5px, color `fg`, margin-bottom 5px.
- **Subtitle** (verbatim): `Кто, что и когда менял в системе. Записи хранятся 12 месяцев.` — 13.5px, color `fg-muted`.
- **Header action** (right-aligned via `margin-left:auto`): a single ghost button **Экспорт** with a download icon (lucide `download`: tray + downward arrow), 14px icon. On click shows a toast `Экспорт журнала`. Button is `.btn .btn-ghost`: height 38px, radius `r-sm` (10px), padding 0 15px, 13px/600, bg `surface`, 0.5px border `border-strong`, hover bg `surface-3`.
- `.page-head` is `display:flex; align-items:flex-start; gap:16px; flex-wrap:wrap; margin-bottom:16px`.

## 3. Overall content layout
Single column, top-to-bottom; no sidebars/KPI tiles.
- `.content`: padding `24px 26px 60px`, `max-width:1100px`, full width.
- Order: **page-head** → one **`.panel`** card containing a sticky-less **toolbar** (filters) then the **log** (`#log`) of day-grouped event rows.
- `.panel`: bg `surface`, 0.5px border `border`, radius `r-lg` (18px), shadow `sh-2`, `overflow:hidden`.
- A **detail modal** (`#modal`) and a **toast** (`#toast`) live outside the panel.
- No sticky elements within the content (topbar sticky is shared chrome, ignore).

## 4. Sections / components

### 4.1 Toolbar (filters) — `.toolbar`
Flex row, `gap:10px`, padding `12px 16px`, bottom border 0.5px `border`, bg `surface-2`, `flex-wrap:wrap`. Controls left→right:
1. **Search** (`.search`, `flex:1; min-width:180px`): left-inset search icon (lucide `search`, 14px, color `fg-subtle` at left 12px). Input: full width, height 36px, 0.5px border `border-strong`, radius 9px, bg `surface`, padding `0 12px 0 34px`, 13px, color `fg`. Placeholder: `Поиск по объекту, действию…`. Focus: border `primary` + ring `0 0 0 3px` `primary-soft`.
2. **Select — employee** (`.filt`): options `Все сотрудники`, `Артём Лебедев`, `Маша Костина`, `Дмитрий Сомов`.
3. **Select — action type** (`.filt`): options `Все действия`, `Создание`, `Изменение`, `Удаление`, `Вход`.
4. **Select — time range** (`.filt`): options `За 7 дней`, `Сегодня`, `За 30 дней`.

`.filt` style: height 36px, 0.5px border `border-strong`, radius 9px, bg `surface`, 12.5px/600, color `fg`, custom chevron (down) SVG as right-aligned background (`fg-subtle`), padding `0 30px 0 12px`, `appearance:none`.

### 4.2 Log list — `#log`
Events grouped by day. Each group = a **day label** then its event rows.

**Day separator** (`.day-lbl`): 11px / 700 / uppercase / letter-spacing .5px, color `fg-subtle`, padding `14px 18px 4px`. Text is the group label (e.g. `Сегодня · 30 апреля`).

**Event row** (`.arow`) — clickable (`cursor:pointer`, opens detail modal):
- Grid: `grid-template-columns: 62px 30px 1fr auto; gap:12px; align-items:center`.
- padding `11px 18px`; bottom border 0.5px `border` (last row none); hover bg `surface-2`.
- **Col 1 — time** (`.a-time`): 12px, color `fg-subtle`, `font-variant-numeric:tabular-nums` (e.g. `14:12`).
- **Col 2 — action icon** (`.a-ico`): 30×30, radius 9px, grid-centered, 15px lucide icon. Color/bg by action type:
  - `create` → bg `primary-soft`, icon `primary-deep` (dark: `primary`). Icon = plus (`+`).
  - `edit` → bg indigo-soft (`--indigo-soft`, no direct token; use indigo @ ~13% light / ~22% dark), icon `indigo` (dark: `#a5b4fc`). Icon = pencil/edit (square + pen).
  - `delete` → bg `danger-soft`, icon `danger`. Icon = trash.
  - `login` → bg `surface-3`, icon `fg-muted`. Icon = log-in (door + arrow).
- **Col 3 — text block** (`min-width:0`):
  - **Title** (`.a-t`): 13px / 550; embedded `<b>` (700) bolds the object noun. e.g. `Изменён **абонемент** · Анна Петрова`.
  - **Sub-line** (`.a-sub`): 11.5px, color `fg-subtle`, flex `gap:6px`, wraps. Contains:
    - **Actor** (`.a-actor`, inline-flex gap 6px): a 16×16 round gradient avatar (`.a-ava`) with white 8px/700 initials, then the actor name.
    - **Chip** (`.a-chip`): the action label, 10px / 700 / uppercase / letter-spacing .3px, bg `surface-3`, color `fg-muted`, padding `1px 7px`, radius 999px. Values: `Создание` / `Изменение` / `Удаление` / `Вход`.
- **Col 4 — right block** (flex, gap 12px):
  - **IP** (`.a-ip`): 11px, color `fg-subtle`, **monospace** (`--mono`), `white-space:nowrap`.
  - **Chevron** (`.a-arrow`): right-chevron, 15px, color `fg-subtle`.

### 4.3 Detail modal — `#modal` / `.am-modal`
Opens on row click. Overlay `.am-overlay`: fixed inset 0, z 100, flex-centered, padding 24px, bg `rgba(0,0,0,.4)`, `backdrop-filter:blur(7px)`; shown via `.open`.
Modal `.am-modal`: bg `surface`, 0.5px border `border`, radius 18px, shadow `sh-3m`, `width:min(540px, calc(100vw-32px))`, `max-height:calc(100dvh-48px)`, flex column, pop-in animation (`scale(.96) translateY(8px)`→none, .24s).
- **Head** (`.am-modal-head`, padding `18px 22px 14px`, flex gap 13px):
  - **Icon** (`.am-modal-ico`): 42×42, radius 12px, bg indigo-soft, color `indigo` (dark `#a5b4fc`) — in static markup an edit/pencil icon (20px). (Dynamically could vary by action; markup hardcodes edit.)
  - **Title** (`.am-modal-title`, 16.5px/700): the row title with HTML tags stripped (e.g. `Изменение абонемента`).
  - **Sub / event id** (`.am-modal-sub`, 12px, `fg-subtle`): `Событие #EV-90412` (id generated as `EV-` + (90000 + random 0–998)).
  - **Close** (`.am-modal-close`): 32×32 round, bg `surface-3`, color `fg-muted`, X icon; hover bg `border` + color `fg`.
- **Body** (`.am-modal-body`, padding `6px 22px 18px`, scrollable):
  - **Meta grid** (`.meta`): 2 columns, gap 10px. Each tile (`.m`): bg `surface-2`, 0.5px border `border`, radius 11px, padding `10px 12px`; key (`.mk`) 11px `fg-subtle`; value (`.mv`) 13px/600. Four tiles:
    - `Сотрудник` → actor name.
    - `Дата и время` → day-name (label after `·`) + `, ` + time, e.g. `30 апреля, 14:12`.
    - `Объект` → object string (e.g. `Абонемент · Анна Петрова`).
    - `IP-адрес` → IP, rendered monospace 12px.
  - **Diff label** (`.difflbl`): `Что изменилось` — 11px/700/uppercase/.5px, `fg-subtle`.
  - **Diff table** (`.diff`): 0.5px border `border`, radius 12px. Each `.diffrow`: grid `120px 1fr`, bottom border 0.5px `border` (last none), 12.5px.
    - Key cell (`.diff-k`): padding `10px 12px`, bg `surface-2`, color `fg-muted`, 600.
    - Value cell (`.diff-v`): padding `10px 12px`, flex column gap 3px:
      - **Old value** (`.diff-old`): color `danger`, line-through (1px). If old value is `—`, render a plain dash in `fg-subtle` instead of struck-through.
      - **New value** (`.diff-new`): color `primary-deep` (dark `primary`), 600.
- **Footer** (`.am-modal-foot`, padding `14px 22px`, top border 0.5px `border`, bg `surface-2`, flex end gap 8px):
  - **Откатить** — `.btn .btn-ghost`; click → toast `Откат изменения`.
  - **Закрыть** — `.btn .btn-primary` (bg `fg`/`text`, color `bg`; dark: bg `primary`, color near-black `#06120c`); click closes modal.

### 4.4 Toast — `#toast` / `.toast`
Bottom-center pill: bg `fg`(`--text`), color `bg`, padding `11px 16px`, radius 999px, 13px/600, shadow `sh-3`, check icon + message; slides up + fades in on `.show` (auto-hide ~2200ms). Dark: bg `primary`, color `#06120c`. (Note: shared `mobile-dock.js` also injects a `.g2-toast`; ignore — covered by AppLayout.)

## 5. All data shown (for TS types + mocks)

**Actors** (name, gradient, initials):
- Маша Костина — `linear-gradient(135deg,#8b5cf6,#ec4899)` — `МК`
- Артём Лебедев — `linear-gradient(135deg,#6366f1,#818cf8)` — `АЛ`
- Дмитрий Сомов — `linear-gradient(135deg,#0ea5e9,#38bdf8)` — `ДС`

**Action types** (`create|edit|delete|login`) → label `Создание|Изменение|Удаление|Вход`.

**Event shape**: `{ time, action, actor{name,gradient,initials}, title(html w/ <b>), object, ip, diff: [label, oldVal, newVal][] }`. Old value `—` means "none/created".

**Group 1 — `Сегодня · 30 апреля`:**
1. `14:12` · edit · Маша Костина · `Изменён <b>абонемент</b> · Анна Петрова` · obj `Абонемент · Анна Петрова` · ip `31.184.220.14` · diff: `[Тариф, «6 месяцев», «12 месяцев»]`, `[Действует до, 14.08.2026, 14.02.2027]`.
2. `13:40` · create · Маша Костина · `Создан <b>клиент</b> · Алина Маркова` · obj `Клиент · Алина Маркова` · ip `31.184.220.14` · diff: `[Имя, —, Алина Маркова]`, `[Телефон, —, +7 916 770-22-10]`.
3. `12:30` · delete · Артём Лебедев · `Удалён <b>тариф</b> · «Пробный»` · obj `Тариф · Пробный` · ip `95.24.18.7` · diff: `[Статус, активен, удалён]`.
4. `11:05` · edit · Дмитрий Сомов · `Изменена <b>роль</b> · Ресепшн` · obj `Роль · Ресепшн` · ip `176.59.40.2` · diff: `[Доступ к «Касса», нет, просмотр]`, `[Доступ к «Отчёты», просмотр, нет]`.

**Group 2 — `Вчера · 29 апреля`:**
5. `21:30` · login · Маша Костина · `Вход в систему` · obj `Сессия` · ip `31.184.220.14` · diff: `[Устройство, —, Chrome · macOS]`, `[Филиал, —, Тверская]`.
6. `18:02` · edit · Артём Лебедев · `Изменены <b>настройки филиала</b> · Тверская` · obj `Филиал · Тверская` · ip `95.24.18.7` · diff: `[Комиссия зала, 25%, 30%]`, `[Часы (Сб), 10:00–20:00, 10:00–22:00]`.
7. `09:14` · create · Дмитрий Сомов · `Создана <b>тренировка</b> · Йога 15:00` · obj `Тренировка · Йога` · ip `176.59.40.2` · diff: `[Направление, —, Йога]`, `[Тренер, —, Ольга Власова]`.

Day-label convention: `<Relative> · <D месяца>` (e.g. `Сегодня · 30 апреля`). Devices/IPs are realistic Russian ISP IPs; device strings like `Chrome · macOS`.

## 6. Interactions
- **Filters & search**: present but inert in mockup (no JS filtering). React should wire them to filter the list client-side: text search over object/title, employee select, action-type select, time-range select.
- **Row click** (`.arow`): opens the detail modal populated from that event (title stripped of HTML, meta tiles, generated event id, diff rendered). Whole row is the hit target.
- **Modal close**: clicking the overlay backdrop, the X button, or **Закрыть** closes it. (Esc closes only the shared mobile sheet in mockup; React should also close this modal on Esc.)
- **Откатить** (modal footer): toast `Откат изменения` (no real rollback).
- **Экспорт** (header): toast `Экспорт журнала` (no real export).
- **No pagination / load-more / infinite scroll** in the mockup — full list rendered at once.
- **Hover states**: rows → bg `surface-2`; ghost btn → bg `surface-3`; close btn → bg `border`; selects/search focus rings as noted.

## 7. Empty / special states
None defined in the mockup. React should add a sensible empty state (e.g. "Записей не найдено") when filters/search yield no events, and ideally an empty-per-day guard. The `12 месяцев` retention note in the subtitle is informational only.

## 8. Responsive notes (`@media`)
- **≤900px**: only shared-chrome changes (sidebar drawer, hamburger) — not page content. Ignore.
- **≤720px**:
  - `.content` padding → `18px 14px 60px`.
  - **`.arow` becomes a card**: grid collapses to `30px 1fr` (icon + text), `gap:8px 10px`, gains 0.5px `border` + radius 12px + `margin:10px` + padding 12px (rows become standalone cards, not divider-separated rows).
  - `.a-time` spans full width (`grid-column:1/3`) — time moves to its own top line.
  - `.a-ip` hidden; `.a-arrow` hidden.
  - **Modal**: `.meta` → single column; `.diffrow` → single column (key stacks above value); overlay aligns to bottom (`align-items:flex-end`, padding 0); modal becomes full-width bottom sheet (`width:100%`, radius `22px 22px 0 0`, `max-height:92dvh`).

### Token notes / non-mapping colors
- `--indigo` → indigo (lucide/edit accent); dark icon override `#a5b4fc`. No semantic token — define an `indigo` token or use raw.
- `--indigo-soft`: light `rgba(99,102,241,.13)`, dark `rgba(99,102,241,.22)` — edit icon bg; no token.
- Avatar gradients (`#8b5cf6→#ec4899`, `#6366f1→#818cf8`, `#0ea5e9→#38bdf8`) are per-actor data, not theme tokens.
- `#06120c` (near-black on emerald in dark primary buttons) is the standard dark-mode primary-foreground used project-wide.
- `--warn`/`--warn-soft` declared in `:root` but **unused** on this screen.

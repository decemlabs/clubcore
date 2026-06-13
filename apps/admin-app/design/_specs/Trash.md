# Корзина (Trash / Recycle Bin) — Structural Spec

> Source: `design/Trash.html`. Spec covers the page **main content only** — shared chrome (sidebar, topbar, theme toggle, `.g2-*` mobile dock) is provided by `AppLayout`. Token map applied per instructions; raw colors that don't map to a token are flagged inline.

## 1. Purpose
A recycle bin for recently soft-deleted admin entities (clients, trainers, plans, sessions), each kept 30 days with restore and permanent-delete affordances.

## 2. Page head
- **H1**: `Корзина` — 23px / 700, letter-spacing -.5px, `fg`.
- **Subtitle** (`.sub`, 13.5px, `fg-muted`, max-width 560px, line-height 1.5): `Удалённые записи хранятся 30 дней, затем стираются безвозвратно. Их можно восстановить.`
- **Header action** (right-aligned via `margin-left:auto`): single ghost-danger button `Очистить корзину` (empty-trash). Trash-can icon (lucide `trash-2`/`trash`, 14px) + label. Style `.btn.btn-ghost.danger`: height 38px, radius 10px (`r-sm`), `surface` bg, .5px border = `color-mix(danger 35%, border-strong)`, text `danger`; hover bg `danger-soft`. **No type-to-confirm** — opens a simple confirm modal (see §6).

## 3. Overall content layout
`.content`: max-width **1080px**, padding `24px 26px 60px` (mobile `18px 14px 60px`). Single column, stacked top→bottom:
1. **Page head** (flex row, wraps; actions push right).
2. **Retention info callout** (`.am-callout`) — full-width warning banner, mb 16px.
3. **Category filter tabs** (`.tabs`) — horizontal pill row, mb 14px, horizontally scrollable (`overflow-x:auto`, hidden scrollbar) on overflow.
4. **Panel** (`.panel`) — the deleted-items container: rounded card (radius 18px `r-lg`, `surface`, .5px `border`, shadow `sh-2`, `overflow:hidden`) containing, in order:
   - **Toolbar** (search + count)
   - **Bulk-action bar** (hidden until selection)
   - **Rows list** (`#rows`)
   - **Empty state** (`#empty`, hidden unless list empty)

No sticky elements within content (page scrolls normally; topbar sticky belongs to chrome).

## 4. Sections & components

### 4.1 Retention callout `.am-callout`
- Flex row, gap 10px, padding `12px 15px`, radius 14px (`r-md`), bg `warning-soft` (dark: `rgba(233,162,59,.12)`).
- Icon: lucide `clock` (circle + hands), 17px. Color **`#a36a16`** (flag: a darkened warning amber, no token — map to `warning-deep`; dark theme uses `warning`).
- Text (`.am-callout-text`, 12.5px, line-height 1.5): color **`#8a5a13`** (flag: dark amber text, no token — map to `warning-deep`; dark uses `warning`). Content: `Автоочистка включена. ` + bold `2 записи` + ` будут удалены безвозвратно в ближайшие 3 дня.` (the "2" should be derived from items with `daysLeft ≤ 3`).

### 4.2 Category filter tabs `.tabs` → `.tab`
Pill buttons, gap 6px. Each tab: padding `8px 14px`, radius 999px, .5px `border`, `surface` bg, text 13px/600 `fg-muted`. Hover: border `border-strong`, text `fg`. **Active** (`.tab.active`): bg `fg`, text `bg`, border `fg` (dark: bg `surface-3`, text `fg`, border `border-strong`).
Count badge `.cnt` inside each: 11px/700, padding `1px 7px`, radius 999px, bg `surface-3`, text `fg-muted`; on active tab bg `rgba(255,255,255,.18)` (dark: `surface`).

Tabs (label + count, `data-f` key):
| key | Label | count |
|-----|-------|-------|
| `all` | `Всё` | 9 |
| `client` | `Клиенты` | 4 |
| `trainer` | `Тренеры` | 2 |
| `plan` | `Тарифы` | 2 |
| `session` | `Тренировки` | 1 |

Counts are totals per type across all items (independent of search). `all` is the sum.

### 4.3 Panel toolbar `.toolbar`
Flex row, gap 10px, padding `12px 16px`, bottom .5px `border`, bg `surface-2`.
- **Search** `.search`: flex 1, max-width 300px. Input height 36px, .5px `border-strong`, radius 9px, `surface` bg, padding `0 12px 0 34px`, 13px. Leading search icon (lucide `search`, 14px, `fg-subtle`) absolutely positioned left 12px. Placeholder `Поиск в корзине…`. Focus: border `primary` + ring `0 0 0 3px primary-soft`.
- **Count** `.tcount` (right, `margin-left:auto`, 12.5px `fg-muted`): `В корзине <b>{n}</b>` where n = filtered visible count; `<b>` is `fg`.

### 4.4 Bulk-action bar `.bulk`
Hidden by default; shown (`display:flex`) when ≥1 row selected. Flex row, gap 12px, padding `10px 16px`, bg `primary-soft` (dark `rgba(45,212,164,.1)`), bottom .5px `border`.
- Left label `.bt` (13px/650, `primary-deep`; dark `primary`): `Выбрано {n}`.
- Right group `.ba` (`margin-left:auto`, gap 8px):
  - `Снять` — `.btn.btn-ghost.btn-sm` (clears selection).
  - `Восстановить` — `.btn.btn-primary.btn-sm`, restore icon (lucide `rotate-ccw`/`refresh`, 13px) + label. Primary btn = bg `fg`, text `bg` (dark: bg `primary`, text near-black `#06120c` — flag: hard-coded dark-on-accent ink, no token).

`.btn-sm`: height 32px, padding `0 11px`, 12.5px, radius 9px.

### 4.5 Deleted-item ROW `.row`
Desktop grid: `grid-template-columns: 40px 1fr 130px 150px 150px`, gap 14px, align center, padding `12px 16px`, bottom .5px `border` (last row none). Hover bg `surface-2`. Columns:

1. **Checkbox cell** `.ckcell` → `.ck`: 18×18, radius 5px, 1.5px `border-strong`, `surface` bg, centered check (transparent until on). Selected `.ck.on`: bg `fg`, border `fg`, check `bg` (dark: bg/border `primary`, check `#06120c` flag). Check glyph = lucide `check`, 11px, stroke-width 3.4.
2. **Item identity** `.it` (flex, gap 11px, min-width 0):
   - **Icon** `.it-ico`: 36×36, radius 10px, centered, `color:#fff`, 12px/700.
     - Person entities (client/trainer) → gradient background + 2-letter Cyrillic initials (`ini`).
     - Non-person (plan/session) → `.it-ico.sq`: bg `surface-3`, color `fg-muted`, holds a 16px lucide glyph (no initials).
   - **Name** `.it-n` (13.5px/600, `fg`) + **subtitle** `.it-s` (11.5px, `fg-subtle`, mt 1px). Subtitle encodes secondary info + who-deleted (e.g. phone · deleted-by, or category · deleted-by).
3. **Type chip column** → `.type-chip`: 11px/600, padding `3px 10px`, radius 999px, bg `surface-3`, text `fg-muted`, inline-flex gap 5px, leading 12px type icon. Labels: `Клиент` / `Тренер` / `Тариф` / `Тренировка`.
4. **Time-left column** `.left` (12.5px, tabular-nums): line 1 = bold `{daysLeft}` + pluralized `день/дня/дней`; line 2 (11px, `fg-subtle`): `в корзине с {deletedAt}`. When `daysLeft ≤ 3` add `.soon` → whole block colored `danger`. (On mobile a `.cell-lbl` prefix `Удалится через:` becomes visible.)
5. **Actions** `.acts` (flex, gap 6px, justify end):
   - `Вернуть` (restore) — `.btn.btn-ghost.btn-sm` + restore icon (lucide `rotate-ccw`, 13px). Per-row restore → toast (no confirm).
   - Delete-forever — icon-only `.btn.btn-ghost.btn-sm.danger`, trash icon (13px), `title="Удалить навсегда"`. → opens type-named confirm modal (§6).

### 4.6 Empty state `.state-msg#empty`
Centered, padding `60px 24px`, shown only when filtered list is empty. Icon tile `.state-ico` 54×54 radius 15px, bg `primary-soft`, color `primary-deep` (dark `primary`), 24px lucide trash icon. Title `.state-t` 16px/700 `Корзина пуста`. Subtitle `.state-s` 13px `fg-muted` mt 6px: `Удалённые записи появятся здесь и будут храниться 30 дней.`

## 5. Data (for TS types + mocks)

Per-item shape: `{ id, type: 'client'|'trainer'|'plan'|'session', name, sub, gradient?, initials?, deletedAt (string, ru short date), daysLeft (number) }`. Person types carry `gradient`+`initials`; plan/session leave them empty and render the type's stock icon on `surface-3`.

Type meta (label + icon): `client`→`Клиент` (users icon), `trainer`→`Тренер` (single-user icon), `plan`→`Тариф` (card: rect+divider line), `session`→`Тренировка` (calendar icon).

Items (all 9, in display order):

| id | type | name | sub (subtitle) | gradient | initials | deletedAt | daysLeft |
|----|------|------|----------------|----------|----------|-----------|----------|
| 1 | client | `Олег Романов` | `+7 903 209-67-31 · удалил Артём Л.` | `135deg,#f43f5e,#fb7185` | `ОР` | `19 фев` | 2 |
| 2 | client | `Мария Кузьмина` | `+7 925 661-29-40 · удалила Маша К.` | `135deg,#ec4899,#f472b6` | `МК` | `30 янв` | 1 |
| 3 | plan | `Тариф «Пробный»` | `Удалил Артём Л.` | — | — | `12 апр` | 18 |
| 4 | client | `Семён Дудин` | `+7 916 110-44-02 · удалила Маша К.` | `135deg,#6366f1,#818cf8` | `СД` | `08 апр` | 14 |
| 5 | trainer | `Кирилл Шварц` | `Функционал · удалил Артём Л.` | `135deg,#10b981,#34d399` | `КШ` | `02 апр` | 8 |
| 6 | session | `Йога · группа · 1 мая 19:00` | `Отменена и удалена · Дмитрий С.` | — | — | `28 мар` | 5 |
| 7 | plan | `Тариф «Корпоратив-10»` | `Удалил Артём Л.` | — | — | `21 мар` | 9 |
| 8 | trainer | `Наталья Жук` | `Йога · удалил Артём Л.` | `135deg,#f59e0b,#fbbf24` | `НЖ` | `15 мар` | 11 |
| 9 | client | `Виктор Лагода` | `+7 909 220-18-77 · удалила Маша К.` | `135deg,#0ea5e9,#38bdf8` | `ВЛ` | `10 мар` | 6 |

Counts (derive from data): all 9 · client 4 · trainer 2 · plan 2 · session 1. Items with `daysLeft ≤ 3`: ids 1 (2d) & 2 (1d) — these render `.soon` (danger) and feed the callout's "2 записи … 3 дня". Avatar gradient ink is `#fff`; gradients are decorative — store as the raw CSS string or a small palette enum (no semantic token).

## 6. Interactions
- **Filter tabs**: click sets active filter (`all`/type). Re-renders list; only matching `type` shown (or all). Active styling moves; tab counts stay constant.
- **Search**: input filters by `name` substring (case-insensitive), combined (AND) with the active tab filter. Live on input. Empty result → empty state shown, toolbar count = 0.
- **Row checkbox**: toggles membership in a selection set; re-renders. Any selection → bulk bar appears with `Выбрано {n}`.
- **Bulk `Снять`**: clears selection (bar hides).
- **Bulk `Восстановить`**: restores all selected → removes them from list, clears selection, fires success toast (pluralized: `Запись восстановлена` for 1, else `{n} записи/записей восстановлено`) **with an `Отменить` (undo) action** in the toast.
- **Per-row `Вернуть`**: restores that single item immediately (no confirm) → removed from list → toast `Запись восстановлена` with undo.
- **Per-row delete-forever** (trash icon): opens confirm modal with **entity name interpolated** into the title — `Удалить «{name}» навсегда?`; body `Запись будет стёрта безвозвратно. Это действие нельзя отменить.` (note bold `безвозвратно`). Confirm permanently removes the item. (Not a type-the-name confirm — just a destructive confirm button.)
- **Header `Очистить корзину`**: opens same modal styled for bulk — title `Очистить корзину?`, body `Все {N} записей будут удалены безвозвратно.` Confirm purges **all** items, clears selection.
- **Confirm modal** action: `Удалить навсегда` (danger) removes target(s) → close modal → re-render → toast `Удалено безвозвратно` (no undo). `Отмена` / overlay click / Esc closes without action.
- **Toast undo**: clicking `Отменить` dismisses and shows `Действие отменено` (mockup is illustrative; real impl should actually re-insert restored rows).
- **Hover/active states**: rows hover `surface-2`; tabs/buttons per §4; ghost buttons hover `surface-3`, danger-ghost hover `danger-soft`; primary danger button hover `#b91c1c` (flag: hard-coded dark-red hover, no token — use a `danger` darker step).

### Confirm modal `.am-modal`
Overlay `.am-overlay`: fixed, z 100, `rgba(0,0,0,.4)` + blur 7px, centered (becomes bottom-sheet ≤640px — see §8). Modal card: `surface`, .5px `border`, radius 18px, shadow `sh-3m`, width `min(440px, 100vw-32px)`, pop animation (scale .96→1, 240ms).
- Body `.am-body` (padding 22px, flex gap 14px): icon tile `.am-ico` 42×42 radius 12px bg `danger-soft` color `danger` (trash icon 20px) + `{ .am-t 16px/700 title, .am-s 13px fg-muted body (bold spans → fg) }`.
- Footer `.am-foot` (padding `13px 22px`, top .5px `border`, bg `surface-2`, flex end, gap 8px): `Отмена` (`.btn.btn-ghost`) + `Удалить навсегда` (`.btn.btn-danger`: bg `danger`, text #fff, hover `#b91c1c`).

### Toast `.toast`
Fixed bottom-center pill: bg `fg`, text `bg` (dark: bg `primary`, ink `#06120c` flag), padding `11px 16px`, radius 999px, 13px/600, shadow `sh-3`, slide-up + fade in (.22s), auto-hide ~3s. Leading check icon (lucide `check`, 15px). Optional trailing `.undo` chip `Отменить`: bg `rgba(255,255,255,.16)` (dark `rgba(0,0,0,.14)`), 12px/700, radius 999px — shown only for restore toasts.

## 7. Empty / special states
- **Filtered-empty** (search/tab yields nothing) and **fully-empty** both render `#empty` (§4.6) inside the panel; toolbar still visible with count `В корзине 0`. No distinct message variant in source — reuse the single empty state.
- No loading/error states in the mockup (add Query loading skeleton + error per project conventions).

## 8. Responsive (`@media`)
- **≤900px**: sidebar/dock = chrome concern (ignore). Content unaffected here aside from chrome.
- **≤760px**: `.content` padding `18px 14px 60px`. **Rows become cards**: `.row` → single column (`grid-template-columns:1fr`), gap 10px, becomes a bordered card (.5px `border`, radius 12px, margin 10px, padding 13px, `position:relative`). Checkbox `.ckcell` absolutely positioned top 14px / right 14px; item `.it` gets `padding-right:28px` to clear it. Hidden desktop labels `.cell-lbl` (e.g. `Удалится через:`) become visible inline (11px `fg-subtle`). Actions `.acts` stretch full-width: each `.btn` `flex:1`.
- **≤640px** (modal → bottom sheet): `.am-overlay` aligns to bottom (`align-items:flex-end`, padding 0); `.am-modal` full-width, radius `22px 22px 0 0`, max-height 92dvh; footer `.am-foot` stacks reverse (`flex-direction:column-reverse`, full-width buttons, bottom padding respects safe-area). Buttons (non-sm, non-icon) get `min-height:44px` via the dock stylesheet.
- Tabs row scrolls horizontally with hidden scrollbar at any width when it overflows.

### Token-map flags (raw values with no clean token)
- Callout icon `#a36a16` & text `#8a5a13` → treat as `warning-deep` (dark uses `warning`).
- Accent-ink `#06120c` (dark-theme text on `primary`) — keep as a fixed on-primary ink constant.
- Danger-button hover `#b91c1c` — use a darker `danger` step.
- Avatar gradients (`#f43f5e…`, etc.) — decorative palette, not semantic tokens.

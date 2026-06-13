# Roles & permissions — «Роли и права доступа»

Spec for the page main content only. Shared `AppLayout` (sidebar, topbar, mobile dock) is out of scope. Route lives under Settings; breadcrumb is `Настройки · Роли и права доступа`.

## 1. Purpose

A master–detail permissions editor: pick a role on the left, edit per-module access (None / View / Manage) on the right. System roles are read-only; custom roles are editable with autosave-style messaging.

## 2. Page head

`.page-head` — flex row, `align-items: flex-start`, gap 16px, `margin-bottom: 22px`, `flex-wrap: wrap`.
- **H1**: `Роли и права доступа` — 23px / weight 700 / letter-spacing -0.5px.
- **Subtitle** (`.sub`, 13.5px, `fg-muted`, max-width 560px, line-height 1.5): `Настройте, что видят и могут делать сотрудники. Системные роли изменять нельзя — создавайте собственные под задачи зала.`
- **Actions** (`.ha`, `margin-left: auto`, gap 9px) — two buttons, height 40px, radius 10px (`--r-sm`), 13.5px/600:
  - `.btn-ghost` **Журнал доступа** — file-text icon (lucide `file-text`); link, no JS handler in mock (access log).
  - `.btn-primary` **Создать роль** — plus icon (lucide `plus`); fires toast `Откроется мастер создания роли` (opens a create-role wizard — not built here).
  - Primary btn = `bg fg` / `text bg` in light (dark: `bg primary` / `text #06120c`). Ghost = `surface` + 0.5px `border-strong`.

## 3. Overall content layout

`.content` max-width 1280px, padding `26px 26px 60px`.

- `.settings-layout` is a passthrough wrapper here (`display:block`; it has settings-nav styling defined but **no settings-nav markup is rendered on this page** — ignore the `.settings-nav` CSS).
- `.roles-grid` — **CSS grid `320px 1fr`**, gap 18px, `align-items: start`, `min-width: 0`.
  - Left column: **Role list** card.
  - Right column: **Role detail** card (header + perms toolbar + perm table + footer).
- **Responsive collapse**:
  - ≤1080px: `.roles-grid` → single column (`1fr`); detail card stacks under the list. Perm rows/colhead inner grid `1fr 280px` (from `1fr 312px`).
  - ≤720px: perm rows become stacked cards (single column), colhead hidden, etc. (see §8).
- No sticky elements in the main content on this page (the `.settings-nav`/`.role-list` sticky rules don't apply since there is no settings-nav rendered, and the role list isn't sticky).

## 4. Sections / components

All cards = `.panel-card`: `surface` bg, 0.5px `border`, radius 18px (`--r-lg`), shadow `sh-2`, `overflow: hidden`.

### 4a. Card head (`.pc-head`) — shared
Flex, gap 10px, padding `14px 16px`, bottom 0.5px `border`. H2 14px/700. Trailing count pill `.ct`: 11px/700 `fg-subtle`, `surface-3` bg, padding `2px 8px`, radius pill.

### 4b. Role list card (left)
- Head: H2 **Роли**, count pill = total role count (**6**).
- `.role-list`: padding 6px, vertical flex, gap 2px. One `.role-item` button per role.
- **`.role-item`** (button, full-width, `position: relative`): flex, gap 12px, padding `11px 12px`, radius 14px (`--r-md`), 1px transparent border.
  - Hover: `surface-2` bg. **Active**: `surface-2` bg + `border` + `sh-1`, plus a **left accent bar** via `::before` — `left:0; top/bottom:12px; width:3px; radius 0 3px 3px 0; background: fg` (dark: `primary`).
  - **`.ri-ico`**: 34×34, radius 10px, grid-centered, 17px icon. Color variants by role (see §5 icon classes).
  - **`.ri-text`**: `.ri-name` (13.5px/650, flex+gap 6px) optionally followed by `.ri-lock` (small 11px lock icon, `fg-subtle`) when role is locked; `.ri-sub` (11.5px, `fg-subtle`) = `Системная роль` or `Пользовательская роль`.
  - **`.ri-count`** (12px/700, `fg-muted`, tabular-nums): member count.
- **`.role-add`** (dashed add button below list): full-width minus 12px margins, padding 11px, 1px dashed `border-strong`, radius 14px, `fg-muted`, 13px/600, plus icon + label **Новая роль**. Hover: `surface-2` bg, `fg` text, `border` color `fg-subtle`. Same action as header "Создать роль" (toast).

### 4c. Role detail card (right)

**Header `.rd-head`**: flex, `align-items: flex-start`, gap 14px, padding `18px 20px`, bottom 0.5px border.
- **`.rd-ico`**: 46×46, radius 13px, grid-centered, 22px icon. Same color-variant classes as `.ri-ico` (owner/admin/purple/amber).
- Title block: **`.rd-title`** (17px/700, flex gap 9px) = role name + **`.rd-badge`**. Badge: 10px/700 uppercase, padding `2px 8px`, radius pill. Default `surface-3`/`fg-muted` → text `Своя роль`; `.rd-badge.sys` = `primary-soft`/`primary-deep` (dark `primary`) → text `Системная`.
- **`.rd-desc`** (13px, `fg-muted`, max-width 520px): role description.
- **`.rd-members`** (`margin-left:auto`, right-aligned):
  - **`.rd-ava-row`**: overlapping avatar stack. Each **`.rd-ava`** 30×30, circle, `margin-left:-8px` (first 0), 2px `surface` ring, 11px/700 white text, gradient background per avatar. Overflow chip `.rd-ava.more` (`surface-3`/`fg-muted`) shows `+N`.
  - **`.rd-members-lbl`** (11.5px, `fg-subtle`, bold count): `<b>N</b> сотрудник|сотрудника|сотрудников` (Russian plural by count via `plural()`).

**Perms toolbar `.perm-toolbar`**: flex, gap 10px, padding `12px 20px`, bottom border, **`surface-2`** bg.
- **`.perm-search`**: flex:1, max-width 280px. Search icon (lucide `search`) left-inset; input 34px tall, 0.5px `border-strong`, radius 8px, `surface` bg, 12.5px, placeholder `Найти раздел…`. Focus: `primary` border + 3px `primary-soft` ring.
- **`.perm-summary`** (`margin-left:auto`, 12px `fg-muted`, bold numbers): `<b>{manage}</b> управление · <b>{view}</b> просмотр · <b>{none}</b> закрыто`. Recomputed live from current working perms.

**Column header `.perm-colhead`**: grid `1fr 312px` (gap 16px), padding `10px 20px`, bottom border, 10.5px/700 uppercase `fg-subtle`. Left label `Раздел`; right `.levels` = 3 equal centered columns: `Нет`, `Просмотр`, `Управление`. **Hidden ≤720px.**

**Lock note `.lock-note`** (only shown for locked/system roles; `.hidden` otherwise): flex, gap 9px, margins `14px 20px 4px`, padding `11px 14px`, radius 10px, `surface-2` bg, 0.5px border, 12.5px `fg-muted`. Lock icon (`fg-subtle`) + text: **`Системная роль.`** (bold) ` Права заданы платформой и не редактируются. Чтобы настроить доступ под себя — создайте копию роли.`

**Perm table `.perm-rows`** (padding `4px 0`): one **`.perm-row`** per module — grid `1fr 312px`, gap 16px, `align-items:center`, padding `11px 20px`, bottom 0.5px border (last row none). Rows of locked roles get `.locked`.
- **`.pr-mod`** (left): flex gap 12px. **`.pr-ico`** 32×32, radius 9px, `surface-3`/`fg-muted`, 16px module icon. Then `.pr-name` (13.5px/600) + `.pr-sub` (11.5px `fg-subtle`, single-line ellipsis on desktop).
- **Cell control = `.seg`** (segmented tri-state, the permission control): grid `repeat(3,1fr)`, gap 3px, `surface-3` bg, radius 9px, padding 3px. Three buttons (one per level), 30px tall, radius 7px, 12px/600, icon (13px) + label. Default `fg-muted`; hover (non-selected) → `fg`.
  - **Selected `.on`**: `surface` bg + `fg` text + `sh-1`. Level-specific selected color: `data-lvl="0"` (Нет) → `fg-subtle`; `data-lvl="2"` (Управление) → `primary-deep` (dark `primary`); `data-lvl="1"` keeps `fg`.
  - Locked role: `.seg` `opacity .6` + `pointer-events:none`.
  - Level icons (lucide): 0 Нет = `minus`; 1 Просмотр = `eye`; 2 Управление = `pencil`/`edit-3` (`M12 20h9 / M16.5 3.5 a2.12… pencil`).

**Empty (search) state `.perm-empty`**: shown only when search yields 0 matches. Centered `.state-msg`, padding `40px 24px`: round `.state-ico` (54×54, radius 16px, `surface-3`/`fg-subtle`) with search icon; title **`Ничего не найдено`** (16px/700); sub `Не нашли раздел по этому запросу. Попробуйте другое слово.`

**Footer `.perm-foot`**: flex, gap 12px, padding `14px 20px`, top border, `surface-2` bg.
- **`.pf-info`** (12.5px `fg-muted`, bold emphasis) — message text (see interactions): default `Все изменения сохраняются автоматически.`; locked role → `Системная роль — только просмотр.`
- **`.pf-actions`** (`margin-left:auto`, gap 9px): `.btn-ghost` **Сбросить** (reset) + `.btn-primary` **Сохранить** with check icon.
- For locked roles `.perm-foot.locked` → `.pf-actions` hidden (only the info line shows).

### 4d. Detail error state `.detail-error` (`.state-msg.err-block`)
Replaces `.detail-body` when page is in error. `.state-ico.err` (54×54, `danger-soft` bg, `danger` icon) = alert-triangle; title **`Не удалось загрузить права`**; sub `Проверьте соединение и попробуйте снова. Если ошибка повторяется — обновите страницу.`; primary button **Повторить** with refresh icon.

### 4e. Toast `.toast`
Fixed bottom-center pill, `fg` bg / `bg` text (dark: `primary`/`#06120c`), 13px/600, check icon, `sh-3`. Auto-hides ~2.2s.

### 4f. State switcher (DEV ONLY)
`.state-switcher` (fixed bottom-center pill: `Состояние` + `Данные`/`Загрузка`/`Ошибка`) is a mock-only demo toggle for the three page states. **Do not port** — represent the three states (data / loading / error) via component props/query status instead.

## 5. Data (for TS types + mocks)

### Levels (permission value)
`0` = `Нет` (none), `1` = `Просмотр` (view), `2` = `Управление` (manage). Per-role perms are a map of `moduleId → 0|1|2`.

### Modules (10, fixed order) — id · name · sub
1. `dashboard` · Дашборд · Сводка и метрики зала
2. `clients` · Клиенты · Карточки, абонементы, заморозки
3. `schedule` · Расписание · Запись на тренировки и залы
4. `plans` · Абонементы · Тарифы, цены и продления
5. `trainers` · Тренеры · Профили, ставки и нагрузка
6. `cashbox` · Касса · Платежи, возвраты, смены
7. `messages` · Сообщения · Переписка и рассылки
8. `reports` · Отчёты · Финансы и аналитика
9. `attendance` · Посещаемость · Чек-ины и журнал визитов
10. `settings` · Настройки · Конфигурация и интеграции

Module icons = lucide equivalents matching the sidebar nav (layout-dashboard, users, calendar, credit-card, user-circle, wallet/credit-card, message-circle, bar-chart, activity, settings).

### Roles (6, in order). Fields: id, name, sys (system), locked, icoClass, desc, count (members), avas[], perms[10]
Perms array order matches the module order above: `[dashboard, clients, schedule, plans, trainers, cashbox, messages, reports, attendance, settings]`.

1. **owner** · `Владелец` · sys ✓ · locked ✓ · icoClass `owner` (shield icon) · count **1**
   - desc: `Полный доступ ко всем разделам и филиалам, управление биллингом и удаление аккаунта.`
   - avas: `[АЛ]`
   - perms: `[2,2,2,2,2,2,2,2,2,2]` (all Manage)
2. **admin** · `Администратор` · sys ✓ · locked ✓ · icoClass `admin` (settings/gear) · count **3**
   - desc: `Управление залом и сотрудниками. Доступ ко всем рабочим разделам, кроме биллинга.`
   - avas: `[МК, ДС, ИП]`
   - perms: `[2,2,2,2,2,2,2,2,2,1]` (settings = View)
3. **manager** · `Управляющий` · sys ✗ · locked ✗ · icoClass `purple` (building/landmark) · count **3**
   - desc: `Руководит филиалом: клиенты, расписание, тренеры и посещаемость. Финансы — только просмотр.`
   - avas: `[ОВ, РК, +1]`
   - perms: `[2,2,2,2,2,1,2,1,2,0]` (cashbox=View, reports=View, settings=None)
   - **This is the default-selected role on load.**
4. **reception** · `Ресепшн` · sys ✗ · locked ✗ · icoClass `amber` (store/storefront) · count **5**
   - desc: `Встречает клиентов: чек-ины, запись на тренировки, оформление и продление абонементов.`
   - avas: `[ЛТ, НГ, +3]`
   - perms: `[1,2,2,1,0,1,2,0,2,0]`
5. **trainer** · `Тренер` · sys ✗ · locked ✗ · icoClass `purple` (user/avatar) · count **12**
   - desc: `Видит своё расписание и клиентов на тренировках, отмечает посещения. Без доступа к финансам.`
   - avas: `[АП, ВД, +10]`
   - perms: `[1,1,2,0,0,0,1,0,1,0]`
6. **accountant** · `Бухгалтер` · sys ✗ · locked ✗ · icoClass `amber` (file/document) · count **1**
   - desc: `Работает с деньгами: касса, возвраты, финансовые отчёты. Операционные разделы — только чтение.`
   - avas: `[СБ]`
   - perms: `[1,1,0,1,0,2,0,2,0,0]`

### Icon-class color map (NON-token avatar gradients & role icon tints)
Role icon classes (background / foreground):
- `owner`: bg `#1c1917` (≈`fg`) / fg `primary` — dark: bg `primary` / fg `#06120c`.
- `admin`: bg `primary-soft` / fg `primary-deep` (dark fg `primary`).
- `purple` (indigo): bg `rgba(99,102,241,.13)` / fg `#4f46e5` — dark: bg `rgba(99,102,241,.22)` / fg `#a5b4fc`. (Indigo `--indigo #6366f1`; raw values, no project token.)
- `amber`: bg `warning-soft` / fg `#a36a16` (dark fg `warning`).

Avatar gradients (raw, **no token** — store as literal gradients per member):
- АЛ `linear-gradient(135deg,#6366f1,#8b5cf6)`
- МК `#0ea5e9,#22d3ee` · ДС `#f59e0b,#ef4444` · ИП `#10b981,#34d399`
- ОВ `#8b5cf6,#ec4899` · РК `#06b6d4,#3b82f6`
- ЛТ `#f43f5e,#fb7185` · НГ `#14b8a6,#2dd4bf`
- АП `#6366f1,#818cf8` · ВД `#f59e0b,#fbbf24`
- СБ `#0ea5e9,#38bdf8`
- `+N` more-chips have no gradient (use `surface-3`/`fg-muted`).

## 6. Interactions

- **Select role** (click `.role-item`): sets active role (left-bar + `surface-2` highlight), clones its perms into a working copy, repopulates the whole detail pane (icon, name, badge, desc, avatars+count, lock-note visibility, perm rows, summary, footer message), resets dirty flag. On ≤1080px the detail is below — scroll-into-view is a no-op in the mock; consider scrolling to detail on mobile.
- **Change a permission** (click a `.seg` button, editable roles only): updates working value, marks only the clicked button `.on`, recomputes `.perm-summary`, marks **dirty** → footer info becomes `<b>Есть несохранённые изменения.</b>`. Locked roles: seg is non-interactive.
- **Search** (type in `.perm-search`): live-filters perm rows by module name OR sub (case-insensitive substring); non-matches get `.hidden`. If 0 matches AND query non-empty → show `.perm-empty`.
- **Сохранить** (saveBtn): commits working copy to the role, clears dirty, footer info → `Все изменения сохранены.`, toast `Права роли «{roleName}» сохранены`.
- **Сбросить** (resetBtn): reverts working copy to saved perms, re-renders rows + summary, footer info → `Изменения отменены.`
- **Создать роль / Новая роль** (header btn + inline dashed btn): toast `Откроется мастер создания роли` (stub for create-role wizard).
- **Повторить** (error retry): goes to loading, then back to data after ~1.1s.
- Hover/active states: see §4 per element (role-item hover/active, seg hover vs `.on`, search focus ring, dashed-add hover).

## 7. Empty / special states

Three page-level states for the detail pane:
- **data** (default): full detail rendered.
- **loading**: skeletons. Left list shows **6** skeleton rows (34px avatar + two shimmer lines). Detail shows: skeleton icon (46×46), name line (150×16), 2 desc lines (90%/60%), hidden badge, empty avatars/members, hidden lock-note, empty summary, and **7** skeleton perm rows (32px icon + 2 lines + a 36px seg-block placeholder). Use shimmer `.skel` (`surface-3` bg + moving highlight).
- **error**: detail body replaced by `.detail-error` (§4d); role list still renders.

Plus the **search empty** state (§4c `.perm-empty`).

## 8. Responsive notes (from @media)

- **≤1080px**: `.roles-grid` → 1 column; `.perm-colhead` & `.perm-row` inner grid `1fr 280px`.
- **≤720px** (mobile): `.content` padding `18px 16px 96px`. `.perm-colhead` hidden. `.perm-rows` becomes a vertical flex (gap 10px, padding `14px 16px`); each `.perm-row` becomes a single-column **card** (`1fr`, gap 12px, padding 14px, 0.5px border, radius 14px) — module info stacked above the full-width `.seg`. `.pr-sub` wraps (no ellipsis). `.seg` width 100%. `.lock-note` margins `14px 16px 0`. `.rd-head` wraps; `.rd-members` left-aligns and avatar row left-justifies. Page-head actions go full-width (`margin-left:0`), each `.btn` flex:1. `.perm-foot` stacks `column-reverse`, actions full-width with flex:1 buttons.
- **≤420px**: seg buttons 11px, smaller gap, **seg icons hidden** (labels only).

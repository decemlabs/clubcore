# Branch-Settings — Structural Spec

Per-branch settings/detail screen for a single fitness club branch. Reached from the **Branches** list (breadcrumb `Филиалы · Тверская`). Scrollspy settings form: sticky left sub-nav + stack of section cards + auto-save dirty bar. Same family as System-Settings — reuse the existing `SectionCard` / `SettingRow` / `Toggle` / `SelectField` / scrollspy-nav / save-bar scaffolding. This spec covers ONLY the main content area; shared `AppLayout` (sidebar, topbar, theme toggle, mobile dock) is out of scope.

The route binds to one branch (e.g. `ROUTES.branch(id)`), so the page is data-driven by a branch object. All sample values below are for branch **Тверская**.

---

## 1. Purpose
Edit one branch's profile, opening hours, rooms/zones, payment config and notification rules, with a danger zone for pausing/migrating/deleting the branch.

## 2. Page head
Flex row, `gap 14px`, `margin-bottom 20px`, wraps on narrow.
- **Avatar mark** (`.ph-mark`): 46×46, radius 13px, emerald gradient `linear-gradient(135deg,#2dd4a4,#0f9b76)` (primary→primary-deep), white bold 17px letter — branch initial **«Т»**.
- **H1** (22px / 700 / `-0.5px`, color `fg`): branch name **«Тверская»** followed inline (`gap 9px`) by a status pill `.b-status`: 10px / 700 / uppercase / `letter-spacing .3px`, padding `2px 8px`, radius 999px, bg `primary-soft`, text `primary-deep` (dark: `primary`). Text **«Активен»**.
- **Subtitle** (`.sub`, 12.5px, `fg-subtle`, `margin-top 3px`): **«м. Тверская · ул. Тверская, 18 · #BR-TVER»** (metro · address · branch code).
- **No explicit back-link button** in the head — back-to-Branches is the breadcrumb in the shared topbar. (When rebuilding, consider a back affordance, but the reference relies on the breadcrumb.)
- **Header actions** (`.ha`, `margin-left:auto`, gap 9px, right-aligned):
  - **Save-hint** (`.save-hint`, 12px, `fg-subtle`). Default text **«Изменения сохраняются автоматически»**. When dirty → class `dirty`, color `warning`, 600 weight, text **«Есть несохранённые изменения»**. After save → back to `.save-hint` plain, text **«Сохранено только что»**.
  - **Save button** (`.btn .btn-primary`, 38px, radius 10px): check-icon + **«Сохранить»**. **Starts `disabled`** (opacity .45). Enables on first dirty change. Primary = bg `fg` / text `bg` (dark: bg `primary`, text near-black `#06120c`); hover `#000`.
  - No kebab / overflow menu.

## 3. Overall content layout
- Content container: `padding 24px 26px 70px`, `max-width 1080px`.
- **`.layout`**: CSS grid `grid-template-columns: 200px 1fr`, `gap 28px`, `align-items:start`.
- **Left sub-nav** (`.snav`): `position:sticky; top: calc(topbar-h + 16px)` (≈80px), vertical flex, `gap 1px`, `padding 4px`. Each link: row, `gap 10px`, padding `8px 11px`, radius 9px, 13px / 500, color `fg-muted`; 14×14 leading icon (opacity .85). Hover → bg `surface`, `fg`. **Active** → bg `fg`, text `bg`, 600 (dark: bg `surface-3`, text `fg`). Active state is set on click and by scrollspy.
- **Sub-nav sections (in order):**
  1. **Общее** `#general` (building icon)
  2. **Часы работы** `#hours` (clock icon)
  3. **Залы и зоны** `#zones` (grid icon)
  4. **Оплата** `#payments` (card icon)
  5. **Уведомления** `#notify` (bell icon)
  6. **Опасная зона** `#danger` (triangle-alert icon) — link text colored `danger`, `margin-top 8px` to separate it.
- **Right stack** (`.stack`): vertical flex, `gap 16px`, one `.card` per section.

### Card shell (all sections)
`.card`: bg `surface`, border `0.5px border`, radius 18px (`--r-lg`), shadow `sh-2`.
- `.card-head`: padding `16px 18px 4px`. `h2` 15px / 700 / `-0.2px` with a 16×16 leading icon (color `fg-muted`). Optional `.cd` description line: 12.5px, `fg-subtle`, `margin-top 4px`.
- `.card-body`: padding `14px 18px 18px`.

### Form primitives
- `.field` `margin-bottom 13px`; `.field-row` = 2-col grid `1fr 1fr` `gap 10px` (collapses to 1-col under 720px).
- `.label`: 12px / 600 / `fg-muted`, `margin-bottom 7px`.
- `.am-input` / `.am-select`: full width, **height 42px**, border `0.5px border-strong`, bg `surface-2`, radius 11px, padding `0 13px`, 14px text. Focus → border `primary`, bg `surface`, ring `0 0 0 3px primary-soft`. Select has custom chevron (right 13px), `padding-right 34px`, `appearance:none`.
- **Money input** (`.money`): relative wrapper, suffix `.cur` absolutely positioned right 13px, `fg-subtle`, 13px, `pointer-events:none` (e.g. `%`).
- **Toggle** (`.sw`): 40×24 pill, radius 999px, off bg `border-strong`; knob 20×20 white circle, +2px inset, slides +16px when `.on`; on bg `primary`. Animated 0.18s.

---

## 4. Section cards

### 4.1 `#general` — Общее
Desc: **«Название, адрес и контакты филиала»**. Fields (all text inputs unless noted), `data-track` = marks dirty:
- **Название филиала** — text, value **«Тверская»** (full width).
- Row: **Город** text «Москва» | **Метро** text «Тверская».
- **Адрес** — text, value **«ул. Тверская, 18, стр. 1»** (full width).
- Row: **Телефон** — `tel` input «+7 495 120-01-00» | **Часовой пояс** — select, options `МСК (UTC+3)` (selected), `UTC+4`, `UTC+5`.
- **Управляющий** — select (full width), options `Ольга Воронина` (selected), `Роман Ким`, `Сергей Белов`.

### 4.2 `#hours` — Часы работы
Desc: **«Когда зал открыт для посещений»**. Body is a list of 7 day-rows (`.hrow`), rendered from data.
- `.hrow`: grid `90px 1fr auto` (mobile `70px 1fr auto`), `gap 12px`, `align-items:center`, padding `10px 0`, bottom border `0.5px border` (last row none).
  - **Day** (`.day`, 90px col): 13px / 600 — `Пн … Вс`.
  - **Times** (`.times`, middle): two time inputs separated by an em-dash «—». `.h-inp` = **64px wide** (mobile 56px), 34px tall, radius 9px, border `0.5px border-strong`, bg `surface-2`, **center-aligned**, tabular-nums, 13px. Focus → border `primary` + ring `primary-soft`. A hidden `.closed-lbl` span («Выходной», color `fg-subtle`) is in markup but `display:none` — when a day is toggled closed, show «Выходной» in place of the time inputs.
  - **Open toggle** (`.sw`, right): on = open day. When toggled off, row gets `.closed`: time text → `fg-subtle`, `.h-inp` opacity .4 + `pointer-events:none`.
- All 7 days seed as **open** (no closed by default).

**Hours data (day, open, close, closed):**
| День | Открытие | Закрытие | Закрыт |
|---|---|---|---|
| Пн | 09:00 | 23:00 | нет |
| Вт | 09:00 | 23:00 | нет |
| Ср | 09:00 | 23:00 | нет |
| Чт | 09:00 | 23:00 | нет |
| Пт | 09:00 | 23:00 | нет |
| Сб | 10:00 | 22:00 | нет |
| Вс | 10:00 | 20:00 | нет |

### 4.3 `#zones` — Залы и зоны
Desc: **«Помещения и их вместимость для расписания»**. List of zone rows (`.zone`) + an add button.
- `.zone`: flex, `gap 12px`, padding `11px 0`, bottom border `0.5px border` (last none).
  - **Icon tile** (`.zone-ico`): 34×34, radius 9px, bg `surface-3`, `fg-muted`, centered 16px icon (square or circle glyph).
  - **Name** (`.zone-n`, 13.5px / 600) + **sub** (`.zone-s`, 11.5px, `fg-subtle`, `margin-top 1px`).
  - **Capacity** (`.zone-cap`, `margin-left:auto`, 13px / 650, tabular-nums).
- **Add button** below list: `.btn .btn-ghost .btn-sm`, `margin-top 12px`, plus-icon + **«Добавить зону»** → toast «Добавление зоны».

**Zones data (name, sub, capacity, icon):**
| Название | Подпись | Вместимость | Иконка |
|---|---|---|---|
| Зал 1 · групповой | Йога, стретчинг, группы | до 16 чел | square |
| Зал 2 · персональный | Персональные тренировки | до 4 чел | square |
| Кардио-зона | Дорожки, эллипсы | до 20 чел | circle |

### 4.4 `#payments` — Оплата
Desc: **«Комиссия зала и способы оплаты»**.
- Row:
  - **Комиссия зала с тренеров** — money input, value **«30»**, suffix **«%»**.
  - **Эквайринг** — select, options `Тинькофф Касса` (selected), `ЮKassa`, `СБП`.
- Toggle rows (`.trow`: flex, padding `12px 0`, bottom border, `.tt` 13.5px/600 title + `.ts` 11.5px `fg-subtle` sub, toggle `margin-left:auto`):
  - **Приём наличных** — «Разрешить оплату на ресепшене» — **ON**.
  - **Онлайн-оплата по ссылке** — «Отправлять клиенту ссылку на оплату» — **ON**.
  - **Рассрочка** — «Сплит-оплата абонементов» — **OFF**.

### 4.5 `#notify` — Уведомления
Desc: **«Что приходит клиентам этого филиала»**. Three `.trow` toggle rows:
- **Напоминание о тренировке** — «За 2 часа до начала · SMS + push» — **ON**.
- **Истечение абонемента** — «За 7 дней до окончания» — **ON**.
- **Акции и новости филиала** — «Маркетинговая рассылка» — **OFF**.

### 4.6 `#danger` — Опасная зона
Card border tinted: `color-mix(in oklab, var(--danger) 24%, var(--border))` (≈ light danger border). `h2` colored `danger` with triangle-alert icon; **no description line**.
- `.danger-row`: flex, `gap 14px`, padding `13px 0`, bottom border (last none). `.dt` 13.5px/600 title; `.ds` 12px `fg-subtle`, `max-width 460px`, line-height 1.45. Action button `margin-left:auto`.
  1. **Поставить на паузу** — «Скрыть из переключателя и остановить запись. Активные абонементы продолжат действовать.» → `.btn .btn-ghost .btn-sm` **«На паузу»** → toast «Филиал поставлен на паузу».
  2. **Перенести клиентов и закрыть** — «Перевести 247 клиентов и 5 тренеров в другой филиал, затем закрыть зал.» → `.btn .btn-ghost .btn-sm .danger` (red text, danger-tinted border, hover bg `danger-soft`) **«Перенести и закрыть»** → toast «Мастер переноса клиентов».
  3. **Удалить филиал** — «Безвозвратно удалить филиал и все его данные. Доступно только когда нет активных клиентов.» → `.btn .btn-ghost .btn-sm` **«Удалить»**, **`disabled`** (gated on zero active clients).

---

## 5. Data model (for TS types + mocks)
One `Branch` object drives the page:
```
Branch {
  id, code: "BR-TVER", name: "Тверская", initial: "Т",
  status: "active",            // pill «Активен»
  city: "Москва", metro: "Тверская",
  address: "ул. Тверская, 18, стр. 1",
  phone: "+7 495 120-01-00",
  timezone: "МСК (UTC+3)",     // enum МСК(UTC+3)|UTC+4|UTC+5
  manager: "Ольга Воронина",   // enum of managers
  clientsCount: 247, trainersCount: 5,
  hours: WorkingDay[7],        // {day:'Пн', open:'09:00', close:'23:00', closed:false}
  zones: Zone[],               // {id, name, sub, capacity:number, kind:'group'|'personal'|'cardio', icon:'square'|'circle'}
  payments: {
    trainerCommissionPct: 30,
    acquiring: "Тинькофф Касса", // enum Тинькофф Касса|ЮKassa|СБП
    acceptCash: true, payByLink: true, installments: false,
  },
  notifications: {
    workoutReminder: true,     // «За 2 часа до начала · SMS + push»
    membershipExpiry: true,    // «За 7 дней до окончания»
    promos: false,             // «Маркетинговая рассылка»
  },
}
```
Sidebar branch-switcher (in shared chrome, FYI only): label «Тверская», sub «м. Тверская · 247 клиентов». The three managers and three acquiring providers above are the select option sets. Zone capacity shows as «до N чел».

## 6. Interactions
- **Dirty tracking.** Any input/textarea `input` event, any `<select>` `change`, and any toggle (`.sw` in payments/notify and `.sw[data-open]` in hours) click marks the form dirty: enable Save button, switch save-hint to warning text «Есть несохранённые изменения». First change only flips state (idempotent).
- **Save.** Clicking Save resets dirty=false, re-disables the button, sets save-hint to plain «Сохранено только что», fires success toast **«Настройки филиала сохранены»**.
- **No cancel/discard button** in the reference (auto-save framing). Rebuild may add a "Отменить" ghost when dirty.
- **Hours open-toggle.** Toggling off adds `.closed` to the row (dims/locks the two time inputs, intended to reveal «Выходной»); toggling on restores. Also marks dirty.
- **Sub-nav scrollspy.** Clicking a `.snav a[href^="#"]` smooth-scrolls to the section with an **80px top offset** (`getBoundingClientRect().top + scrollY - 80`) and sets `.active` on the clicked link. (Reference only sets active on click; rebuild should also update active on scroll position.)
- **Zone add / danger actions** are demo stubs → fire a toast (`data-toast` value). In production: «Добавить зону» → add-zone modal/sheet; «На паузу» → confirm + pause; «Перенести и закрыть» → migration wizard; «Удалить» → type-to-confirm destructive modal (reference has no confirm UI yet — disabled until no active clients).
- **Toast** (`.toast`): fixed bottom-center pill, bg `fg` / text `bg` (dark: `primary`), check-icon + message, slides up `.show`, auto-hides after ~2.2s.
- **Hover/active.** Inputs/selects focus ring as above; buttons `:active { transform: scale(.99) }`; ghost buttons hover bg `surface-3`; danger ghost hover bg `danger-soft`.

## 7. Empty/special states
- No empty states for zones/hours (always seeded). If zones become removable, design a "no zones" empty hint + the existing add button.
- **Delete branch** action is permanently disabled until the branch has zero active clients — the gated/disabled state is itself a meaningful state to render.
- Status pill currently only shows «Активен»; expect also «На паузе» (warning) / «Закрыт» (subtle) variants given the danger-zone actions.

## 8. Responsive notes
- **≤900px** (`.layout` → 1-col, `gap 14px`): sub-nav becomes a **horizontal scroll strip** — `flex-direction:row`, `overflow-x:auto`, no scrollbar, each pill gets `surface` bg + `0.5px border`, **icons hidden** (`svg{display:none}`). Sub-nav loses sticky (`position:relative`). (Mobile dock from shared chrome appears here — not this page's concern.)
- **≤720px** (`.content` padding `18px 14px 70px`): `.field-row` → single column (`gap 0`); `.hrow` grid → `70px 1fr auto` `gap 8px`; `.h-inp` width 56px; page-head actions `.ha` go full-width, `margin-left:0`, `justify-content:space-between` (save-hint left, Save button right).

## Token map notes
All colors map cleanly: `--accent`→primary, `--accent-deep`→primary-deep, `--accent-soft`→primary-soft, `--text`→fg, `--text-2`→fg-muted, `--text-3`→fg-subtle, `--bg`→bg, `--surface`/`--surface-2`/`--surface-3`→surface/surface-2/surface-3, `--border`/`--border-strong`→border/border-strong, `--warn`→warning (used only for the dirty save-hint), `--danger`→danger, `--danger-soft`→danger-soft. The `#06120c` near-black on emerald (dark-mode primary button/pill text) is a fixed on-primary foreground, not a token. No indigo or mono used in the main content (indigo only in the shared sidebar avatar).

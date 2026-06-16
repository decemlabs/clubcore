# Импорт / Экспорт — Structural Spec

## 1. Purpose
A wizard-style data screen for importing a client CSV/XLSX (4-step: upload → map columns → preview → errors) and a separate export view to download datasets as CSV/XLSX/PDF.

## 2. Page head
The H1 + subtitle change per "view". Two logical views: the import wizard (4 panes) and export (1 pane).

- **Import head** (shown for panes upload/map/preview/errors): H1 `Импорт данных` (23px/700, letter-spacing -.5px); subtitle (`.sub`, 13.5px, `fg-muted`): `Загрузите файл с клиентами — мы сопоставим колонки, проверим и добавим в базу.`
- **Export head** (inside export pane, `margin-top:4px`): H1 `Экспорт данных` (overridden to **19px**/700); subtitle: `Выгрузите клиентов, платежи или отчёты в нужном формате.`
- No page-level header action buttons. Primary actions live in each pane's footer.

## 3. Overall content layout
- Content wrapper: `padding:24px 26px 90px`, **`max-width:980px`**, full width, single column. (Mobile ≤720px: `padding:18px 14px 90px`.)
- Top-to-bottom: **Page head → Stepper → active Pane**. Only ONE pane visible at a time (`.pane{display:none}` / `.pane.active{display:block}`).
- **Stepper** (pill segmented control) shows for the 4 import steps; **hidden entirely when export pane active** (`stepper.display='none'`).
- Each pane = a `.panel` card + a `.foot` action row (and sometimes a callout between them).
- Bottom-fixed **demo step-switcher** (`.switcher`) is a mockup-only navigation affordance — see §6; in React, view state replaces it (treat as tab/route state, not a visible widget).
- No sticky elements within content (topbar/sidebar are shared chrome, ignored).

## 4. Sections / components

### 4.1 Stepper (`.stepper`)
Horizontal pill bar: `background:surface`, `border .5px border`, `border-radius:999px`, `padding:6px`, `box-shadow:sh-1`, `margin-bottom:18px`, `overflow-x:auto` (hidden scrollbar). Steps: 4 buttons `Загрузка / Маппинг / Предпросмотр / Ошибки`, each `data-step` = `upload/map/preview/errors`.
- `.step`: `flex:1`, centered, gap 8px, `padding:8px 12px`, radius 999px, 12.5px/600, color `fg-subtle`, nowrap.
- `.num` badge: 20×20 circle, `bg surface-3`, color `fg-muted`, 11px/700.
- `.step.active`: `bg fg`, text `bg` (dark: `bg surface-3`, text `fg`); active `.num` → `bg primary`, color `#06120c`.
- `.step.done`: color `primary-deep` (dark: `primary`); done `.num` → `bg primary-soft`, color `primary-deep` (dark `primary`). Steps before the active index are `.done`.
- Clicking a step navigates to it.

### 4.2 Panel (`.panel`) — shared card shell
`bg surface`, `border .5px border`, `border-radius:18px` (`r-lg`), `box-shadow:sh-2`, `overflow:hidden`.
- `.panel-head`: `padding:16px 18px 4px`. `h2` 15px/700. `.cd` caption 12.5px `fg-subtle`, `margin-top:4px`.
- `.panel-body`: `padding:14px 18px 18px`.

### 4.3 Footer (`.foot`)
Flex row, `justify-content:space-between`, gap 8px, `margin-top:16px`. Left = Back/`<span></span>` spacer; right = primary CTA.

### 4.4 Buttons
- `.btn`: height 38px, radius 10px (`r-sm`), `padding:0 16px`, 13px/600, inline-flex, gap 7px; `:active` scale .99.
- `.btn-primary`: `bg fg`, text `bg`; hover `#000`. **Dark: `bg primary`, text `#06120c`.**
- `.btn-ghost`: `bg surface`, `border .5px border-strong`, text `fg`; hover `bg surface-3`.
- `.btn-sm`: height 32px, `padding:0 11px`, 12.5px, radius 9px.
- `:disabled`: opacity .45.

### 4.5 PANE 1 — Upload (`data-pane="upload"`)
Panel head h2 `Загрузка файла`; caption `CSV или XLSX до 10 МБ · до 5 000 строк за раз`.
Body contains:
- **Dropzone** `.drop`: `border:1.5px dashed border-strong`, radius 14px (`r-md`), `padding:36px 24px`, centered, `bg surface-2`.
  - `.drop-ico`: 54×54, radius 15px, `bg surface-3`, color `fg-muted`, centered; icon = upload arrow (lucide `upload`/`upload-cloud` style: tray + up arrow), 24px stroke 1.9, `margin:0 auto 14px`.
  - `.drop-t`: `Перетащите файл сюда` (14.5px/650). `.drop-s`: `или выберите на устройстве` (12.5px `fg-subtle`, `margin:5px 0 16px`).
  - Button `.btn .btn-ghost`: `Выбрать файл`.
- **File chip** `.filechip` (shown when a file is selected): flex, gap 12px, `padding:12px 14px`, `border .5px border`, radius 12px, `bg surface-2`, `margin-top:14px`.
  - `.fi` file icon box: 38×38, radius 10px, `bg primary-soft`, color `primary-deep` (dark `primary`); icon = lucide `file` (sheet with folded corner), 18px.
  - `.fn`: filename 13.5px/600. `.fs`: meta 11.5px `fg-subtle`.
  - `.fx` remove btn: 30×30, transparent, color `fg-subtle`; hover `bg surface-3`, color `danger`; icon = X 15px.
- **Callout** `.am-callout` (info, neutral variant): flex gap 10px, `padding:12px 14px`, radius 12px, `bg surface-2`, `border .5px border`, `margin-top:14px`. Icon (`.am-callout-ico`, 18px wide, color `fg-muted`) = lucide `info` circle. Text 12.5px `fg-muted`: `Первая строка должна содержать заголовки колонок. ` + bold link `Скачать шаблон-пример` + ` для корректного импорта.` (the bold span is the **sample-template download** affordance).
- Footer: spacer + `.btn-primary` `Далее · сопоставить колонки` (→ map).

### 4.6 PANE 2 — Map / Сопоставление (`data-pane="map"`)
Panel head h2 `Сопоставление колонок`; caption `Свяжите колонки файла с полями системы · 6 из 6 распознано`.
Body = list of **map rows** (`#mapBody`, generated from `MAP`).
- `.maprow`: grid `1fr 28px 1fr`, gap 12px, items-center, `padding:10px 0`, `border-bottom .5px border` (last none).
  - **Left `.src`** (source column): 13px/600, `bg surface-2`, `border .5px border`, radius 9px, `padding:10px 12px`, **`font-family:mono`**. Below it `.smp` sample: 11px `fg-subtle`, **`font-family` sans (`--font`)**, `margin-top:2px`, prefixed `напр.: <sample>`.
  - **Middle `.arr`**: arrow-right icon, color `fg-subtle`, centered (16px).
  - **Right `.am-select`**: full-width native select, height 42px, `border .5px border-strong`, `bg surface-2`, radius 9px, `padding:0 13px`, 13.5px, custom chevron bg-image (color `#a8a29e`), `padding-right:32px`. Focus: `border-color primary` + ring `0 0 0 3px primary-soft`. `.am-select.skip` → text `fg-subtle` (when value is "— Пропустить —").
- Footer: `.btn-ghost` `Назад` (→ upload) + `.btn-primary` `Далее · предпросмотр` (→ preview).

### 4.7 PANE 3 — Preview / Предпросмотр (`data-pane="preview"`)
Panel head h2 `Предпросмотр`; caption (rich): `Первые строки после сопоставления · ` + bold `298 готовы` (color `primary-deep`) + ` · ` + bold `14 с ошибками` (color `danger`).
**Note:** preview table rows sit directly inside `.panel` (no `.panel-body` wrapper).
- **`.pv-head`** column header row: grid `36px 1.4fr 1.2fr 1fr 1fr`, gap 12px, `padding:10px 14px`, `border-bottom .5px border`, 10.5px/700 UPPERCASE letter-spacing .5px, color `fg-subtle`. Columns: ``(blank) / Имя / Телефон / Абонемент / Email``.
- **`.pv-row`** (`#pvRows`, from `PV`): same grid, 12.5px, `padding:10px 14px`, `border-bottom .5px border` (last none). `.pv-row.err` → `bg danger-soft` (dark `rgba(220,38,38,.08)`).
  - **`.pv-st`** status dot: 22×22 circle. `.ok` → `bg primary-soft`, color `primary-deep` (dark `primary`), check icon; `.err` → `bg danger-soft`, color `danger`, X icon (13px stroke 2.6).
  - **`.pv-cell`**: ellipsis-truncated; `.pv-cell.bad` → color `danger`, 600 (per-cell invalid highlighting via `bad` index array). Empty value renders `—`.
- **Callout** `.am-callout.warn` (warning variant): `bg warning-soft`, `border-color:transparent`. Icon = lucide `alert-triangle`, color `#a36a16` (raw — does NOT map; ≈ `warning-deep`). Text: `В ` + bold `14 строках` + ` найдены ошибки. Их можно пропустить или исправить на следующем шаге.`
- Footer: `.btn-ghost` `Назад` (→ map) + `.btn-primary` `Проверить ошибки` (→ errors).

### 4.8 PANE 4 — Errors / Отчёт об ошибках (`data-pane="errors"`)
Panel head h2 `Отчёт об ошибках`; caption `14 строк требуют внимания перед импортом`.
Body = list of **error rows** (`#errBody`, from `ERR`) + trailing "more" line.
- `.erow`: flex, gap 12px, items-center, `padding:12px 0`, `border-bottom .5px border` (last none).
  - `.e-line` line-number badge: 30×30, radius 8px, `bg danger-soft`, color `danger`, 11px/700, tabular-nums.
  - `.e-t`: title 13px/600. `.e-s`: detail 11.5px `fg-subtle`, `margin-top:1px`.
  - `.e-act`: right-aligned `.btn-ghost.btn-sm` `Пропустить` (toast "Строка пропущена").
- Trailing line after rows: 12px `fg-subtle`, `margin-top:12px`: `… и ещё 10 строк с ошибками`.
- **Success callout** `.am-callout.ok` (`#importDone`, hidden until import runs): `bg primary-soft`, `border-color:transparent`, text/icon `primary-deep` (dark `primary`); check icon. Text: bold `Импорт завершён.` + ` Добавлено 298 клиентов, 14 пропущено.`
- Footer: `.btn-ghost` `Назад` (→ preview) + `.btn-primary` (`#runImport`, with check icon 14px) `Импортировать 298 строк`.

### 4.9 PANE 5 — Export (`data-pane="export"`)
Has its own page head (§2). Single `.panel` with `.panel-body` only (no panel-head). Contents:
- **Label** `Формат` (12px/600, `fg-muted`, `margin-bottom:9px`).
- **Format option grid** `.opt-grid` (`#fmtGrid`): grid `1fr 1fr 1fr`, gap 10px (mobile ≤720px → 1 column). Three `.opt` cards (`data-f` = csv/xlsx/pdf):
  - `.opt`: `border:1px border-strong`, radius 12px, `padding:14px`, centered, `bg surface`, cursor pointer. Hover → `border-color fg-subtle`. **`.opt.on`** (selected, single-select) → `border-color fg`, `border-width:1.5px`, `bg surface-2` (dark border `primary`).
  - `.opt-ico`: 38×38, radius 11px, `bg surface-3`, color `fg-muted`; on-state → `bg primary-soft`, color `primary-deep` (dark `primary`). Icons: CSV = lucide `file`; XLSX = `table`/`sheet` (rect + grid lines); PDF = `file` with a horizontal line. (Generic monochrome — NO brand format colors used.)
  - `.opt-n` 13px/650; `.opt-s` 11px `fg-subtle`. Default selected = **CSV**.
  - Card labels: `CSV` / `Для Excel / Sheets`; `XLSX` / `Excel с форматами`; `PDF` / `Для печати`.
- **Label** `Что выгрузить` (12px/600 `fg-muted`, `margin:18px 0 4px`).
- **Checklist** — three `.chk` rows (multi-select toggles, `data-chk`), 13px, `padding:9px 0`, gap 10px:
  - `.box`: 18×18, radius 5px, `border 1.5px border-strong`, check icon transparent. `.chk.on .box` → `bg fg`, `border fg`, check color `bg` (dark: `bg primary`, color `#06120c`).
  - Items: `Клиенты и абонементы (847)` (on), `История платежей` (on), `Посещаемость` (off).
- Footer: spacer + `.btn-primary` (`#exportBtn`, download icon 14px) `Скачать CSV`. Its label + toast update live with the chosen format (see §6).

### 4.10 Progress bar (defined, not used in markup)
`.progress` (height 6px, radius 999px, `bg surface-3`) + `.progress-f` (`bg primary`, width-animated). Available for an upload/import progress affordance.

## 5. Data (for TS types + mocks)

### Map step — source→field (`MAP`); target FIELDS list = `['Имя','Фамилия','Телефон','Email','Абонемент','Дата рождения','— Пропустить —']`
| src (mono) | sample (`smp`) | default field (`def`) |
|---|---|---|
| `full_name` | Анна Петрова | Имя |
| `phone` | +7 916 224-18-03 | Телефон |
| `email` | anna.p@mail.ru | Email |
| `plan` | 12 месяцев | Абонемент |
| `birth` | 14.03.1994 | Дата рождения |
| `notes` | утренние тренировки | — Пропустить — (skip) |

### Preview rows (`PV`) — columns: name `n`, phone `p`, plan `pl`, email `e`; `ok` flag; `bad` = invalid column indices (0=name,1=phone,2=plan,3=email)
| ok | Имя | Телефон | Абонемент | Email | bad cells |
|---|---|---|---|---|---|
| ✓ | Анна Петрова | +7 916 224-18-03 | 12 месяцев | anna.p@mail.ru | — |
| ✓ | Максим Соколов | +7 903 552-10-44 | 6 месяцев | m.sokolov@mail.ru | — |
| ✗ | Игорь | 89163320911 | — | нет email | phone, email |
| ✓ | Карина Левчук | +7 916 408-22-71 | 3 месяца | karina.l@mail.ru | — |
| ✗ | (empty) | +7 905 118-44-20 | годовой | sv@bk | name, email |
| ✓ | Павел Сидоров | +7 919 887-03-55 | 12 месяцев | pavel.s@mail.ru | — |

### Error report (`ERR`) — line, title, detail
| line | title (`t`) | detail (`s`) |
|---|---|---|
| 3 | Строка 3 · Игорь | Не указана фамилия · телефон в неверном формате · нет email |
| 5 | Строка 5 · (без имени) | Не указано имя · email «sv@bk» некорректен |
| 18 | Строка 18 · Олег Романов | Дубликат: клиент с таким телефоном уже есть |
| 27 | Строка 27 · Мария К. | Тариф «премиум» не найден в системе |

(+ trailing "… и ещё 10 строк с ошибками".)

### Aggregate counts (verbatim strings)
- Recognized columns: `6 из 6 распознано`. Preview: `298 готовы`, `14 с ошибками`. Errors: `14 строк требуют внимания перед импортом`. Import CTA: `Импортировать 298 строк`. Done: `Добавлено 298 клиентов, 14 пропущено.`

### Sample uploaded file (filechip)
- name `clients_export_2026.csv`, meta `312 строк · 84 КБ · загружено`.
- Upload limits: `CSV или XLSX до 10 МБ · до 5 000 строк за раз`.

### Export formats
`csv` (CSV — Для Excel / Sheets) · `xlsx` (XLSX — Excel с форматами) · `pdf` (PDF — Для печати). Single-select, default csv.

### Export datasets (checklist, with default on/off)
- `Клиенты и абонементы (847)` — **on**
- `История платежей` — **on**
- `Посещаемость` — **off**

## 6. Interactions
- **Step / view switching:** clicking a stepper step, a footer `data-next` button, or a `.switcher` button calls `go(pane)` → toggles active pane, marks stepper active/done (done = index lower than current), hides stepper when `export`, smooth-scrolls to top. Initial pane may come from URL hash (`#map` etc.). In React: model as a `view` state (`upload|map|preview|errors|export`); the bottom `.switcher` is a mockup demo nav — replace with real navigation (e.g. an "Импорт"/"Экспорт" toggle plus wizard progression); do not ship the floating pill.
- **Dropzone:** clicking `Выбрать файл` opens file picker → on selection show `.filechip` with name/size/"загружено" (mock shows it always present). Spec a **drag-over** highlight state on `.drop` (e.g. border→`primary`, bg→`primary-soft`) — not in source CSS, add it. Remove (`.fx`) clears the chip.
- **Download template:** bold `Скачать шаблон-пример` link → downloads sample CSV (no handler in mock; wire to template download).
- **Mapping selects:** native `<select>` per source column; selecting "— Пропустить —" adds `.skip` (muted) styling. Focus ring as in §4.6.
- **Per-row skip (errors):** `.btn-sm` `Пропустить` → toast `Строка пропущена`.
- **Run import (`#runImport`):** on click → button disabled, label → `Импорт…`; after ~900ms the `#importDone` ok-callout appears, the run button hides, toast `Импорт завершён · 298 клиентов добавлено`.
- **Format toggle (`#fmtGrid`):** single-select; clicking an `.opt` sets `.on` on it (clears others), and **live-updates** the export button label to `Скачать <FMT>` and its toast to `Экспорт <FMT> запущен · файл скоро будет готов`.
- **Dataset checkboxes:** `data-chk` rows toggle `.on` independently (`preventDefault` on label click). No min-selection enforced in mock.
- **Export button (`#exportBtn`):** click → toast `Экспорт CSV запущен · файл скоро будет готов` (format-substituted). No job row is created in the mock (no persisted history list exists).
- **Toast** (`.toast`, `#toast`): bottom-center pill, `bg fg` text `bg` (dark `bg primary`/`#06120c`), radius 999px, `padding:11px 16px`, 13px/600, check icon; slides up on `.show`, auto-hides after 2200ms. Any element with `data-toast` triggers it.
- **Hover/active:** `.btn:active` scale .99; `.opt:hover` border `fg-subtle`; ghost-btn hover `bg surface-3`; nav/step hovers per tokens.

## 7. Empty / special states
- **No history/jobs list exists** in this mockup — there is no past import/export jobs table. Do NOT invent one beyond what's specified; if a jobs/history feature is desired it's net-new (model after the error/file-chip rows). The closest "completed" feedback is the one-shot `#importDone` success callout + toasts.
- **No-file state:** dropzone shown without filechip (the mock always shows the chip; React should hide chip until a file is chosen).
- **Import success state:** `#importDone` callout replaces the run button (button hidden) after import.
- **Per-cell error state:** invalid cells in preview render `—`/raw value in `danger` bold; whole row tinted `danger-soft`.

## 8. Responsive (`@media`)
- **≤900px:** sidebar/topbar are shared chrome (ignored). Bottom `.switcher` moves with the shared dock offset (mockup-only).
- **≤720px:**
  - Content padding → `18px 14px 90px`.
  - `.maprow` → single column (`grid-template-columns:1fr`, gap 6px); the `.arr` arrow **hidden**. So source chip stacks above its select.
  - Preview: `.pv-head` **hidden**; each `.pv-row` becomes a 2-col card (`grid 1fr 1fr`, gap `6px 10px`, `border .5px border`, radius 10px, `margin:8px`, `padding:11px`) — i.e. cells wrap into a card grid instead of a table row.
  - Export `.opt-grid` → single column.
  - `.switcher` pinned to `top:12px` (mockup-only).
- All panels/cards are fluid (max-width 980px container); no fixed widths that would clip.

## Token notes / non-mapping colors
- Brand format icons: **none** — all format/file icons are monochrome (`fg-muted`/`surface-3`), no raw brand colors.
- Warning callout/triangle icon uses raw `#a36a16` (no token; ≈ `warning-deep`). Body `warn` text generally maps `fg-muted`.
- Dark-mode error-row tint uses raw `rgba(220,38,38,.08)` (a softer-than-`danger-soft` overlay).
- Active-button-on-dark text/check uses raw `#06120c` (brand-on-emerald foreground) throughout (stepper num, primary btn, toast, checkbox, opt — all dark variants).
- Select chevron is an inline SVG data-URI tinted `#a8a29e` (= `fg-subtle`).

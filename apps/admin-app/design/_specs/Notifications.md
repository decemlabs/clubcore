# Notifications — «Уведомления и сообщения»

## 1. Purpose
A single tabbed hub for the admin's notification **feed/inbox** (system alerts), plus outbound messaging: send-history, message **templates** (with per-template enable toggles — the "settings"-like surface), a broadcast **composer**, and per-broadcast **delivery reports**.

> This screen is primarily a NOTIFICATIONS FEED (tab 1). It is NOT an event×channel preference matrix. The closest thing to "notification settings" is the **Templates** tab (per-template on/off + channel), covered in §4.5. All five tabs are in scope.

## 2. Page head
- **H1** (verbatim): `Уведомления и сообщения` — 23px / 700 / letter-spacing −.5px, color `fg`, margin-bottom 5px.
- **Subtitle** (verbatim): `Системные оповещения, рассылки клиентам, шаблоны и отчёты по доставке.` — 13.5px, color `fg-muted`, line-height 1.5, max-width 560px.
- **Header action** (right via `margin-left:auto`): one **primary** button `Новая рассылка` with a paper-plane/send icon (lucide `send`, 15px). Click → switches to the **Рассылка** (broadcast) tab.
- `.page-head` = `flex; align-items:flex-start; gap:16px; flex-wrap:wrap; margin-bottom:18px`.

## 3. Overall content layout
Single column. `.content`: padding `24px 26px 60px`, `max-width:1080px`, full width.

Order top→bottom:
1. **page-head**
2. **Tab bar** (`.tabs`) — segmented pill control, 5 tabs (§4.1).
3. **Active tab pane** — exactly one `.panel` card (broadcast tab has a slightly different internal head). Panes toggle via `display:none/block`.

`.panel` = bg `surface`, 0.5px border `border`, radius `r-lg` (18px), shadow `sh-2`, `overflow:hidden`.
`.panel-head` = `flex; align-items:center; gap:10px; padding:13px 18px; border-bottom:0.5px border`; `h2` 14px/700; right cluster `.ph` (`margin-left:auto; flex; gap:8px`) holds head actions.

A **toast** (§6) lives outside the panel, fixed bottom-center. No content-area sticky elements except the broadcast phone preview (§4.6).

### Tokens / shared atoms
- Buttons `.btn`: height 38px, radius `r-sm` (10px), padding `0 15px`, 13px/600, `:active scale .99`.
  - `.btn-primary`: bg `fg`, text `bg`; hover `#000` (flag: hardcoded). **Dark:** bg `primary`, text `#06120c` (flag).
  - `.btn-ghost`: bg `surface`, 0.5px border `border-strong`, text `fg`; hover bg `surface-3`.
  - `.btn-sm`: height 32px, padding `0 11px`, 12px, radius 9px.
  - `:disabled` opacity .45.
- Channel chip `.ch` (used in History/Templates): 10.5px/700, padding `2px 8px`, radius 999px.
  - `.sms` → bg `primary-soft`, text `primary-deep` (dark text `primary`).
  - `.push` → bg `indigo-soft`, text `indigo` (dark `#a5b4fc`).
  - `.email` → bg `warning-soft`, text `#a36a16` (flag: warn-deep-ish; dark `warning`).
- Toggle switch `.sw`: 38×22, radius 999px, track `border-strong`; knob 18×18 white, `top/left 2px`, shadow `0 1px 3px rgba(0,0,0,.2)`. `.on` → track `primary`, knob `translateX(16px)`. 180ms transitions.

## 4. Tabs / panes

### 4.1 Tab bar — `.tabs`
Segmented control: `flex; gap:3px; bg surface-3; radius 11px; padding:4px; width:fit-content; max-width:100%; overflow-x:auto` (scrollbar hidden). Each `.tab`: transparent bg, 13px/600, height 34px, padding `0 15px`, radius 8px, color `fg-muted`; hover → `fg`; **`.active`** → bg `surface`, text `fg`, shadow `sh-1`. Tabs (order, verbatim):
1. `Центр уведомлений` + count badge `5` (`.tb`) — default active.
2. `История`
3. `Шаблоны`
4. `Рассылка`
5. `Доставка`

Count badge `.tb`: 10.5px/700, bg `primary`, text `#06120c` (flag: hardcoded on-primary text), radius 999px, min-width 16px, height 16px, padding `0 6px`, grid-centered.

### 4.2 Center / Notifications feed — pane `center`
Inside `.panel`:
- **panel-head**: h2 `Центр уведомлений`; right action ghost-sm `Прочитать все` with check icon (lucide `check`, 13px).
- **Filter chips** (`.chips`): `flex; gap:6px; padding:12px 18px; border-bottom 0.5px border; overflow-x:auto` (scrollbar hidden). Each `.fchip`: 0.5px border `border`, bg `surface`, text `fg-muted`, radius 999px, padding `6px 13px`, 12.5px/600, nowrap. Active `.on` → bg `fg`, text `bg`, border `fg` (**dark:** bg `surface-3`, text `fg`, border `border-strong`). Chips (verbatim): `Все` (default on), `Непрочитанные`, `Финансы`, `Клиенты`, `Система`.
- **Feed** (`#nfeed`): notifications grouped by day. A **day label** (`.day-lbl`, 11px/700/uppercase/ls .5px, color `fg-subtle`, padding `14px 18px 6px`) precedes each group; labels: `Сегодня`, `Ранее`.
- **Notification row** (`.nrow`): `flex; gap:13px; padding:13px 18px; border-bottom 0.5px border` (last none); `position:relative`.
  - **Unread** (`.unread`): row bg = `primary-soft` @30% mix (dark `rgba(45,212,164,.06)`); plus an absolute dot `::before` at `left:7px; vertical-center`, 6×6, radius 50%, bg `primary`.
  - **Type icon** (`.n-ico`): 36×36, radius 10px, grid-centered, 17px lucide stroke icon. Default bg `surface-3` / text `fg-muted`. Tone variants:
    - `.success` → bg `primary-soft`, text `primary-deep` (dark `primary`).
    - `.warn` → bg `warning-soft`, text `#a36a16` (dark `warning`).
    - `.danger` → bg `danger-soft`, text `danger`.
    - `.info` → bg `indigo-soft`, text `indigo` (dark `#a5b4fc`).
  - **Body** (flex:1, min-width:0): title `.n-t` 13.5px/600 (supports inline `<b>` 700 for the entity name); subtitle `.n-s` 12px, color `fg-subtle`, mt 2px.
  - **Timestamp** (`.n-time`): 11.5px, color `fg-subtle`, nowrap, tabular-nums.
  - No per-row action buttons or explicit entity-link control; rows are not individually clickable in the mockup (only mark-all-read mutates state).
- **Empty state** (`.empty`, §7) sits after the feed.

### 4.3 History — pane `history`
`.panel` with panel-head h2 `История сообщений` + ghost-sm action `Экспорт` (toast `Экспорт в CSV`).
A **column-grid table** (no `<table>`):
- Header `.htable-head` + each `.hrow` share `grid-template-columns: 1.6fr 0.9fr 0.8fr 1.1fr 110px; gap:14px; align-items:center; padding:12px 18px`; bottom border 0.5px `border`.
- Header (10.5px/700/uppercase/ls .5px, `fg-subtle`): `Рассылка` · `Канал` · `Аудитория` · `Отправлено` · `Доставка` (last right-aligned).
- Row (`.hrow`, hover bg `surface-2`, `cursor:pointer`, click → toast `Открыт отчёт: <name>`):
  1. name `.h-name` 13.5px/600 + sub `.h-sub` 11.5px `fg-subtle`.
  2. channel `.ch` chip.
  3. audience (`.h-date` style, 12.5px `fg-muted`).
  4. sent date (tabular).
  5. **delivery bar** `.h-stat`: `.h-bar` track (flex:1, height 6px, radius 999px, bg `surface-3`, min-width 40px) with `.h-bar-f` fill (bg `primary`, width = pct%), then `.h-pct` 11.5px/650 `fg-muted`.

### 4.4 Templates — pane `templates` (the "settings"-like surface)
`.panel` with panel-head h2 `Шаблоны сообщений` + ghost-sm `Шаблон` (plus icon; toast `Новый шаблон`).
Grid `.tgrid`: `grid-template-columns: 1fr 1fr; gap:12px; padding:16px 18px`.
**Template card** (`.tpl`): 0.5px border `border`, radius `r-md` (14px), padding 14px, bg `surface-2`, column flex.
- **Top** (`.tpl-top`): channel `.ch` chip + (name `.tpl-name` 13.5px/650, trigger `.tpl-trig` 11px `fg-subtle`).
- **Body** (`.tpl-body`): 12.5px `fg-muted`, line-height 1.5, margin `11px 0`, inset card bg `surface` 0.5px border radius 10px padding `10px 12px`, flex:1. Template variables rendered as `.var` spans — color `primary-deep` / 600 (dark `primary`).
- **Foot** (`.tpl-foot`): toggle `.sw` (on/off, see §3) + status text `.tpl-st` 11.5px/600 `fg-subtle` (`Включён`/`Выключен`) + ghost-sm `Изменить` (`margin-left:auto`; toast `Редактирование шаблона`).

### 4.5 Broadcast composer — pane `broadcast`
`.panel`, panel-head h2 `Массовая рассылка`. Body `.compose`: `grid-template-columns: 1fr 300px; gap:18px; padding:18px` (left = form, right = sticky preview).

**Left form** — fields stacked, each `.field` mb 13px; `.label` 12px/600 `fg-muted` mb 7px.
- Inputs/selects/textarea (`.am-input/.am-select/.am-textarea`): full width, height 42px (textarea min-height 110px, auto, resize-y), 0.5px border `border-strong`, bg `surface-2`, radius 11px, padding `0 13px` (textarea `11px 13px`), 14px, color `fg`. **Focus**: border `primary`, bg `surface`, ring `0 0 0 3px primary-soft`. Selects use a custom chevron SVG (color `fg-subtle`), `appearance:none`, right-padded 34px.
1. **Аудитория** — `<select #audSel>` (options in §5) + below it `.aud-row`: pill row bg `primary-soft` (dark `rgba(45,212,164,.1)`), padding `11px 13px`, radius 11px; left label `Получателей` (`.ar-t` 13px/650 `primary-deep`/dark `primary`), right count `.ar-n` 16px/700 `primary-deep` tabular — reflects selected option's `data-n`.
2. **Канал** — segmented `.seg` (`inline-grid auto-flow column; gap:3px; bg surface-3; radius 10px; padding:3px; width:100%`); each button 12.5px/600 height 34px radius 8px; `.on` → bg `surface`, text `fg`, shadow `sh-1`. Options: `SMS` (default on), `Push`, `Email`.
3. **Тема письма** — text input, hidden by default; shown only when channel = Email. Value: `Ваш абонемент скоро закончится`.
4. **Сообщение** — `.am-textarea` (default value in §5) + **`.varbar`** of variable insert chips (`.varbtn`: 0.5px border `border-strong`, bg `surface`, text `fg-muted`, radius 999px, padding `5px 11px`, 11.5px/600, **monospace** font; hover border `fg-subtle`/text `fg`). Chips: `{имя}` `{абонемент}` `{дата}` `{филиал}`.
5. **Время отправки** — segmented `.seg`: `Сейчас` (default on), `Запланировать`.

**Right preview** (`.preview`, sticky top 90px; collapses non-sticky on mobile):
- **Phone card** (`.phone`): bg `surface-2`, 0.5px border `border`, radius 20px, padding `16px 14px`, min-height 240px.
  - label `.phone-lbl` `Предпросмотр` (11px/700/uppercase, `fg-subtle`, centered).
  - **bubble** (`.bubble`): bg `surface`, 0.5px border, radius `14px 14px 14px 4px`, padding `11px 13px`, 13px, shadow `sh-1`. Header `.bubble-app` = a 16×16 brand square `.d` (bg `fg`/text `primary`; dark bg `primary`/text `#06120c`) with letter `М`, + `Мой зал` (11px/700 `fg-muted`). Body = live-rendered message with `{var}` tokens styled `.var` (color `primary-deep`/600, dark `primary`).
  - `.pv-meta` (11px `fg-subtle`, centered): `SMS · ~67 символов · 1 сегмент` (static in mockup).
- **Send button** (`#sendBtn`, primary, full width, mt 12px): send icon + `Отправить 23 клиентам` — count tracks selected audience.
- **Draft button** (ghost, full width, mt 8px): `В черновики` (toast `Сохранено в черновики`).

### 4.6 Delivery report — pane `delivery`
`.panel` for a single broadcast.
- **Head** (`.dl-head`, padding `16px 18px`, bottom border): title `.dl-name` 15px/700 `Продление · истекающие абонементы`; meta `.dl-meta` 12px `fg-subtle` `SMS · отправлено 28 апр, 12:04 · 312 получателей`.
- **Stat tiles** (`.dl-stats`): `grid-template-columns: repeat(4,1fr); gap:1px; bg border` (1px gaps read as hairlines). Each `.dst`: bg `surface`, padding `15px 16px`; label `.dst-l` 11.5px `fg-muted` with a leading 7×7 status dot; value `.dst-v` 22px/700 tabular; pct `.dst-p` 11.5px `fg-subtle`. Dots: `.s`→`primary`, `.t`→`fg-subtle`, `.r`→`indigo`, `.f`→`danger`. (Values in §5.)
- **Sub-head** (panel-head, top border): h2 `Получатели` (13px) + right a small select (`Все`/`Прочитано`/`Доставлено`/`Ошибка`) styled like ghost-sm with custom chevron.
- **Recipient rows** (`.drow`): `flex; align-items:center; gap:12px; padding:11px 18px; border-bottom 0.5px border` (last none). Avatar `.d-ava` 32×32 circle, gradient bg per person, white initials 11px/700; name `.d-name` 13px/600 + phone `.d-sub` 11px `fg-subtle`; right **status pill** `.d-status` (11.5px/650, padding `3px 10px`, radius 999px): `.read`→indigo-soft/indigo (dark `#a5b4fc`), `.deliv`→primary-soft/primary-deep (dark `primary`), `.fail`→danger-soft/danger.

## 5. Data (for TS types + mocks)

### 5.1 Feed notifications (`NOTIF[]`: `{day:'today'|'earlier', cat:'finance'|'clients'|'system', type:'danger'|'success'|'warn'|'info', unread:boolean, title (HTML, may contain <b>), body, time, icon}`)
Сегодня (today):
1. danger / finance / unread — `Платёж не прошёл · <b>Игорь Климов</b>` — `Автосписание за абонемент отклонено банком` — `12:40` (icon: dollar-sign).
2. success / clients / unread — `Новый клиент · <b>Алина Маркова</b>` — `Оформила абонемент «3 месяца» онлайн` — `11:18` (user-plus).
3. warn / system / unread — `Низкая заполняемость · <b>Новокосино</b>` — `Сегодня 54% — ниже целевых 70%` — `10:05` (clock).
4. warn / clients / unread — `23 абонемента истекают на неделе` — `Запустите рассылку о продлении` — `09:30` (card).
5. info / system / unread — `Расписание · 3 конфликта` — `Пересечения по залам на этой неделе` — `09:12` (calendar).
Ранее (earlier):
6. success / finance / read — `Выручка за апрель · <b>2 248 000 ₽</b>` — `+12% к марту по всем филиалам` — `Вчера` (bar-chart).
7. info / clients / read — `Отзыв 5★ · <b>Карина Левчук</b>` — `«Лучший зал на Тверской, спасибо!»` — `Вчера` (star).
8. success / system / read — `Резервная копия создана` — `Ежедневный бэкап базы выполнен` — `Вчера` (moon/backup).

Unread count = 5 (drives both nav badge and the `Центр уведомлений` tab `.tb`).

### 5.2 History (`HIST[]`: `{name, sub, ch:'sms'|'push'|'email', aud, sent, pct}`)
1. `Продление · истекающие` / `Скидка 10%` / sms / `312 клиентов` / `28 апр · 12:04` / 95%
2. `Майские праздники · график` / `Изменения в расписании` / push / `847 клиентов` / `25 апр · 18:00` / 88%
3. `Возвращайся! · неактивные` / `Бесплатная тренировка` / email / `64 клиента` / `20 апр · 10:30` / 72%
4. `Новый тренер · йога` / `Анонс направления` / push / `312 клиентов` / `14 апр · 14:15` / 91%
5. `День рождения · апрель` / `Подарок к ДР` / sms / `38 клиентов` / `01 апр · 09:00` / 97%

### 5.3 Templates (`TPL[]`: `{name, trigger, ch, on, body(with {vars})}`)
1. `Напоминание о тренировке` / `За 2 часа до начала` / push / **on** / `Привет, {имя}! Напоминаем: {направление} сегодня в {время}, {зал}.`
2. `Абонемент истекает` / `За 7 дней до окончания` / sms / **on** / `{имя}, ваш «{абонемент}» заканчивается {дата}. Продлите со скидкой 10%.`
3. `Добро пожаловать` / `При оформлении абонемента` / email / **on** / `Рады видеть вас в «Мой зал», {имя}! Ваш абонемент активен до {дата}.`
4. `С днём рождения` / `В день рождения клиента` / sms / **off** / `С днём рождения, {имя}! 🎉 Дарим бесплатную персональную тренировку.`

### 5.4 Broadcast audience options (`#audSel`, `data-n` = recipient count)
- `Все клиенты` (847)
- `Истекает абонемент (7 дней)` (23) — **selected default**
- `Неактивные 30+ дней` (64)
- `Филиал «Сокольники»` (312)
- `С абонементом «Год»` (128)

Default message: `Привет, {имя}! Ваш абонемент «{абонемент}» заканчивается {дата}. Продлите со скидкой 10% до конца недели 💪`

### 5.5 Delivery report
Header broadcast: `Продление · истекающие абонементы`, SMS, sent `28 апр, 12:04`, 312 recipients.
Stat tiles: Отправлено `312` / 100%; Доставлено `298` / 95.5%; Прочитано `214` / 68.6%; Ошибка `14` / 4.5%.
Recipients (`DLV[]`: `{initials, gradient, name, phone, status:'read'|'deliv'|'fail', statusText}`):
1. АП / `Анна Петрова` / `+7 916 224-18-03` / read / `прочитано 12:09`
2. МС / `Максим Соколов` / `+7 903 552-10-44` / read / `прочитано 12:11`
3. ИК / `Игорь Климов` / `+7 916 332-09-11` / deliv / `доставлено 12:05`
4. СО / `Светлана Орлова` / `+7 905 118-44-20` / deliv / `доставлено 12:05`
5. ОР / `Олег Романов` / `+7 903 209-67-31` / fail / `номер недоступен`

Channel label map: `{sms:'SMS', push:'Push', email:'Email'}`. Status label map: read→`Прочитано`, deliv→`Доставлено`, fail→`Ошибка`.

## 6. Interactions
- **Tabs**: click sets `.active` on tab + matching pane. `Новая рассылка` head button → broadcast tab. Deep-link: URL hash `#broadcast` auto-opens broadcast tab on load.
- **Feed filter chips**: single-select; `all` shows everything, `unread` filters `unread`, else by `cat`. Re-renders feed; shows empty state if list is empty.
- **Прочитать все**: sets every notification `unread=false`, hides the tab count badge, re-renders (unread bg/dot disappear), toast `Все уведомления прочитаны`.
- **History row**: hover bg `surface-2`; click → toast `Открыт отчёт: <name>` (real app: navigate to that delivery report).
- **History/Templates head**: `Экспорт`→toast `Экспорт в CSV`; `Шаблон`→toast `Новый шаблон`; per-template `Изменить`→toast `Редактирование шаблона`.
- **Template toggle** (`.sw`): click flips on/off and updates status text `Включён`/`Выключен` (no toast). This is the dirty/save-ish control — in the real app, treat as an immediate per-template enable mutation (consider toast/persist).
- **Composer**:
  - Audience `<select>` change → updates `Получателей` count and send-button label `Отправить N клиентам`.
  - Channel seg → toggles `.on`; selecting `Email` reveals the **Тема письма** field, else hides it.
  - Время отправки seg → toggles `.on` (no extra UI shown for `Запланировать` in mockup; real app should reveal a datetime picker).
  - Variable chips (`.varbtn`) → append `{var}` to the textarea (space-separated), refocus, re-render preview.
  - Textarea `input` → live-renders bubble preview, wrapping `{...}` tokens in `.var`.
  - `Отправить` → toast `Рассылка запущена · N получателей`. `В черновики` → toast `Сохранено в черновики`.
- **Delivery**: recipient-status `<select>` filters the list (wire as filter). Rows are static (no click action).
- **Toast** (`#toast`): fixed bottom-center pill, bg `fg`/text `bg` (dark bg `primary`/text `#06120c`), 13px/600, radius 999px, padding `11px 16px`, leading check icon, shadow `sh-3`; slides up + fades in (`.show`), auto-hides after 2200ms.

## 7. Empty / special states
- **Feed empty** (`.empty`, shown when filtered list is 0): centered block, padding `56px 24px`. Icon `.empty-ico` 52×52 radius 15px, bg `primary-soft`, text `primary-deep` (dark `primary`), centered check icon 24px, mb 14px. Title `.empty-t` 15px/700 `Всё прочитано`; sub `.empty-s` 12.5px `fg-subtle` `Новых уведомлений по этому фильтру нет.`
- No explicit empty states for History/Templates/Delivery in the mockup (all seeded). Provide sensible analogues if data is empty.

## 8. Responsive (`@media`)
- **≤900px**: broadcast `.compose` → single column (`1fr`); phone `.preview` becomes `position:relative` (non-sticky); delivery `.dl-stats` → 2 columns (`1fr 1fr`). (Sidebar/topbar collapse is shared chrome — ignore.)
- **≤720px**: `.content` padding `18px 14px 60px`; page-head action row goes full-width with the button stretching (`flex:1`); templates `.tgrid` → 1 column; **History table** drops its header (`.htable-head` hidden) and each `.hrow` becomes a bordered stacked card (`grid-template-columns:1fr; gap:8px; border 0.5px border; radius 12px; margin:10px; padding:13px`), with per-cell inline labels `.h-cell-lbl` (`Аудитория:` / `Отправлено:`, 11px `fg-subtle`) shown before values.
- Tab bar and filter chips are horizontally scrollable (scrollbars hidden) at all widths.

## Color flags (don't cleanly map to tokens)
- `.btn-primary` hover `#000` and on-primary text `var(--bg)`; dark on-primary text `#06120c` — hardcoded; map to `primary-foreground` if one exists, else keep literal.
- Email channel text `#a36a16` (a warn-deep), and dark info text `#a5b4fc` (indigo-300) — no exact token; nearest are `warning-deep` / a light indigo. Confirm against theme.
- Avatar gradients in delivery rows are bespoke per-person literals (indigo/emerald/sky/amber/rose) — generate from initials or keep as data.

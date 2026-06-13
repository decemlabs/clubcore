# Shared modals spec — extracted from `design/Dashboard.html`

Two reusable modal dialogs that ride on a shared modal framework (the `am-*` system). This document is the SOLE source for reimplementing them in React. Reproduce the **visual identity**, not the HTML — build clean, responsive, token-driven components.

> Both modals are children of the shared overlay/modal shell. The shell, buttons, chips, sections, callouts, and info-cards are reused across the prototype, so build them as primitives (e.g. `AdminModal`, `ModalSection`, `Callout`, `InfoCard`, `ProgramList`, `Chip`, `PresenceGrid`) rather than per-page markup.

---

## Shared framework reference (applies to BOTH modals)

### Token → semantic mapping
The prototype uses raw CSS vars. Map them to the project's semantic Tailwind tokens:

| Prototype var | Light value | Dark value | Project semantic | Meaning |
|---|---|---|---|---|
| `--bg` | `#f5f5f4` | `#0c0c0c` | `bg` | page background |
| `--surface` | `#ffffff` | `#181715` | `surface` | modal/card surface |
| `--surface-2` | `#fafaf9` | `#141312` | `surface-2` | info-card / present-card / footer bg |
| `--surface-3` | `#f1f0ee` | `#232120` | `surface-3` | close-btn bg, progress track |
| `--border` | `#e7e5e4` | `#2a2826` | `border` | hairlines (0.5px) |
| `--border-strong` | `#d6d3d1` | `#3a3735` | `border-strong` | hover borders, checkbox border, drag handle |
| `--text` | `#1c1917` | `#f5f5f4` | `fg` | primary text; **also the primary-button bg in light** |
| `--text-2` | `#57534e` | `#a8a29e` | `fg-muted` (≈) | secondary text |
| `--text-3` | `#a8a29e` | `#6b6663` | `fg-subtle` (≈) | tertiary/labels/meta |
| `--accent` | `#2dd4a4` | `#2dd4a4` | `primary` (emerald) | brand emerald (dark-mode primary button + progress) |
| `--accent-deep` | `#0f9b76` | — | emerald-deep | light-mode accent text / progress fill / pulse dot |
| `--accent-soft` | `#d6f5ea` | `rgba(45,212,164,.16)` | emerald-soft | accent callout bg, status-pill bg |
| `--warn` / `--warn-soft` | `#e9a23b` / `#fef3e2` | `#e9a23b` / `rgba(233,162,59,.18)` | warn/amber | warn callout (`#a36a16` text) — *not used by these two modals but available* |
| `--danger` / `--danger-soft` | `#dc2626` / `#fee2e2` | `#dc2626` / `rgba(220,38,38,.18)` | danger/red | danger button, used by the confirm dialog the cancel action triggers |

**Semantic-color usage in these two modals:** only **surface/border** (neutral chrome) and **accent/emerald** (status pill, accent callout, progress bar, active chips & primary button in dark). No warn/amber or danger/red appears *inside* either modal body; danger only shows up in the confirm dialog that `m-session`'s "Отменить" opens.

### Modal shell CSS (shared)
```css
.am-overlay {
  position: fixed; inset: 0; z-index: 100;
  background: rgba(0, 0, 0, 0.34);
  backdrop-filter: blur(6px) saturate(120%);
  -webkit-backdrop-filter: blur(6px) saturate(120%);
  opacity: 0; visibility: hidden;
  display: flex; align-items: center; justify-content: center;
  padding: 24px;
  transition: opacity 0.22s ease, visibility 0.22s;
}
.am-overlay.open { opacity: 1; visibility: visible; }

.am-modal {
  background: var(--surface);
  border: 0.5px solid var(--border);
  border-radius: 18px;
  box-shadow: 0 30px 80px rgba(0,0,0,0.3), 0 8px 24px rgba(0,0,0,0.12);
  width: min(540px, calc(100vw - 32px));     /* default */
  max-height: calc(100dvh - 48px);
  display: flex; flex-direction: column; overflow: hidden;
  transform: scale(0.96) translateY(8px); opacity: 0;
  transition: transform 0.24s cubic-bezier(0.32,0.72,0.2,1), opacity 0.18s ease;
}
.am-overlay.open .am-modal { transform: scale(1) translateY(0); opacity: 1; }

.am-modal.am-modal-wide   { width: min(720px, calc(100vw - 32px)); }   /* m-present uses this */
.am-modal.am-modal-narrow { width: min(420px, calc(100vw - 32px)); }

/* Bottom-sheet on phones */
.am-modal-handle { display: none; }
@media (max-width: 640px) {
  .am-overlay { align-items: flex-end; padding: 0; }
  .am-modal, .am-modal.am-modal-wide, .am-modal.am-modal-narrow {
    width: 100%; max-width: 100%; max-height: 92dvh;
    border-radius: 22px 22px 0 0; transform: translateY(24px);
  }
  .am-overlay.open .am-modal { transform: translateY(0); }
  .am-modal-handle {
    display: block; width: 38px; height: 4px;
    background: var(--border-strong); border-radius: 999px;
    margin: 8px auto 0; flex-shrink: 0;
  }
}

.am-modal-head {
  display: flex; align-items: flex-start; justify-content: space-between;
  gap: 16px; padding: 18px 22px 14px;
  border-bottom: 0.5px solid var(--border); flex-shrink: 0;
}
.am-modal-head-text { min-width: 0; }
.am-modal-title { font-size: 17px; font-weight: 700; letter-spacing: -0.3px; line-height: 1.2; }
.am-modal-sub   { font-size: 12.5px; color: var(--text-2); margin-top: 4px; line-height: 1.4; }
.am-modal-close {
  width: 32px; height: 32px; border-radius: 50%; border: 0;
  background: var(--surface-3); color: var(--text-2);
  display: grid; place-items: center; cursor: pointer; flex-shrink: 0;
  transition: background 0.15s, color 0.15s;
}
.am-modal-close:hover { background: var(--border); color: var(--text); }

.am-modal-body { padding: 18px 22px; overflow-y: auto; flex: 1; min-height: 0; -webkit-overflow-scrolling: touch; }

.am-modal-foot {
  padding: 14px 22px; border-top: 0.5px solid var(--border);
  display: flex; gap: 8px; justify-content: flex-end; align-items: center;
  background: var(--surface-2); flex-shrink: 0;
}
.am-modal-foot-spread { justify-content: space-between; }   /* both modals use this */
.am-modal-foot-info   { font-size: 12px; color: var(--text-2); }
.am-modal-foot-info b { color: var(--text); font-weight: 650; }

@media (max-width: 640px) {
  .am-modal-head { padding: 14px 18px 12px; }
  .am-modal-body { padding: 16px 18px; }
  .am-modal-foot {
    padding: 12px 16px max(12px, env(safe-area-inset-bottom));
    flex-direction: column-reverse; align-items: stretch;
  }
  .am-modal-foot .am-btn { width: 100%; justify-content: center; }
  .am-modal-foot-spread { flex-direction: column-reverse; align-items: stretch; }
}
```

### Buttons (shared)
```css
.am-btn {
  height: 40px; border-radius: 999px; padding: 0 20px;
  font-size: 13.5px; font-weight: 600; border: 0;
  display: inline-flex; align-items: center; justify-content: center; gap: 7px;
  cursor: pointer; font-family: inherit; letter-spacing: -0.1px;
  transition: background 0.15s, border-color 0.15s, color 0.15s, transform 0.05s;
}
.am-btn:active { transform: scale(0.98); }
.am-btn-primary { background: var(--text); color: var(--bg); }                 /* black-on-white in light */
.am-btn-primary:hover { background: #000; }
[data-theme="dark"] .am-btn-primary { background: var(--accent); color: #06120c; }  /* emerald in dark */
[data-theme="dark"] .am-btn-primary:hover { background: #5ee9b8; }
.am-btn-ghost { background: var(--surface); border: 0.5px solid var(--border); color: var(--text); }
.am-btn-ghost:hover { border-color: var(--border-strong); background: var(--surface-2); }
.am-btn-danger { background: var(--danger); color: white; }
.am-btn-danger:hover { background: #b91c1c; }
.am-btn-text { background: transparent; color: var(--text-2); padding: 0 12px; }
.am-btn-text:hover { color: var(--text); }
```

### Section heading + Callout (shared; used by m-session)
```css
.am-section {
  font-size: 11.5px; font-weight: 700; letter-spacing: 0.5px;
  text-transform: uppercase; color: var(--text-3); margin: 18px 0 10px;
}
.am-section:first-child { margin-top: 0; }

.am-callout { display: flex; gap: 10px; padding: 12px 14px; border-radius: 12px; background: var(--surface-2); border: 0.5px solid var(--border); }
.am-callout.accent { background: var(--accent-soft); border-color: transparent; }
.am-callout.warn   { background: var(--warn-soft);  border-color: transparent; }
.am-callout-ico { width: 20px; flex-shrink: 0; color: var(--text-2); margin-top: 1px; }
.am-callout.accent .am-callout-ico { color: var(--accent-deep); }
.am-callout.warn   .am-callout-ico { color: #a36a16; }
.am-callout-text { font-size: 12.5px; color: var(--text-2); line-height: 1.45; }
.am-callout-text b { color: var(--text); font-weight: 650; }
.am-callout.accent .am-callout-text { color: var(--accent-deep); }
[data-theme="dark"] .am-callout.accent .am-callout-text { color: var(--accent); }
```

### Chips (shared; used by m-present as a radio group)
```css
.am-chips { display: flex; flex-wrap: wrap; gap: 8px; }
.am-chip {
  border: 0.5px solid var(--border); background: var(--surface); border-radius: 999px;
  padding: 9px 14px; font-family: inherit; font-size: 13px; font-weight: 600; color: var(--text);
  cursor: pointer; display: inline-flex; align-items: center; gap: 6px; letter-spacing: -0.1px;
  transition: background 0.15s, border-color 0.15s, color 0.15s;
}
.am-chip:hover { border-color: var(--border-strong); }
.am-chip.active { background: var(--text); color: var(--bg); border-color: var(--text); }
[data-theme="dark"] .am-chip.active { background: var(--accent); color: #06120c; border-color: var(--accent); }
```
> The count inside each chip is dimmed via inline `style="opacity:0.6;"` on a `<span>` (the prototype uses an inline span, not the `.am-chip-sub` class). Reproduce as a muted count, e.g. `Все · 42` with the number at ~60% opacity.

### Shell behavior (shared JS, reproduce as React modal semantics)
- `AM.open(id)` adds `.open`, sets `aria-hidden="false"`, locks body scroll, focuses first input/`.am-btn-primary`.
- `AM.close(id)` removes `.open`, `aria-hidden="true"`, unlocks scroll.
- **Backdrop click** on `.am-overlay` closes. **ESC** closes the topmost open overlay. `[data-am-close]` buttons close the containing overlay.
- Each overlay is `role="dialog"` + `aria-labelledby` pointing at its title; close button is `aria-label="Закрыть"`.
- On phones (≤640px) the modal is a bottom sheet with a drag handle and drag-to-dismiss. In React, a Drawer/Sheet on mobile + Dialog on desktop, or a responsive Dialog, both work — keep the rounded-top sheet look on mobile.

---

## m-session

### Purpose & trigger
Quick session/training detail. Opens when an admin clicks a schedule row/event (`.sched-row`); JS `openSession(idx)` fills it from a `sessionData[]` array, then `AM.open('m-session')`. Default modal width (540px).

### Header
- **Title** (`#m-session-title`): default rendered text **`15:30 · Персональная`**. Computed as `time + ' · ' + type.split(' · ')[0]` (time + first segment of the session type).
- **Status pill** (`#m-session-pill`, `.session-status-pill`): text **`Идёт сейчас`**. Hidden by default; shown only when `status === 'live'`. Emerald pulsing-dot pill (see CSS below).
- **Subtitle** (`#m-session-sub`): default **`60 мин · ноги + спина · зал 1`**. Computed as `dur + ' мин · ' + (remaining type segments joined by ' · ')`.
- Close button (×), `aria-label="Закрыть"`.

### Body (in order)

**1. Two info-cards** — a 2-column grid: `display:grid; grid-template-columns:1fr 1fr; gap:8px;`

Card A — heading **`Клиент`** (`.ic-h`):
- Avatar (`.ic-av`, 36×36 round, initials): **`МК`**, bg `#f59e0b` (overridden per-session; live default is `#dc2626`).
- Name (`.ic-name`): **`Маша Конева`**
- Meta (`.ic-meta`): **`Месячный · 6 мес с нами`**
- Stats row (`.ic-stats`, dashed top border, 3 stats each `.l` label + `.n` number):
  - **`Тренировки`** → **`37`**
  - **`Стрик`** → **`12 нед`**
  - **`Опл. до`** → **`13 мая`**

Card B — heading **`Тренер`**:
- Avatar: **`АС`**, bg `#f59e0b`
- Name: **`Аня Соколова`**
- Meta: **`Силовые, функционал · 4.9 ★`**
- Stats (these three are **static**, not data-driven):
  - **`Апрель`** → **`64 сессии`**
  - **`Рейтинг`** → **`4.9`**
  - **`Стаж`** → **`3 года`**

**2. Section `Программа`** (`.am-section`) → program list (`.am-prog`, `#m-session-prog`). Six rows, each `grid-template-columns: 20px 1fr auto` = [checkbox] [exercise name] [sets/reps]. Each row is **clickable to toggle `done`** (strikes through name + greys it). First 3 rows start `.done`:
  1. ✓ done — **`Разминка · кардио`** — **`8 мин`**
  2. ✓ done — **`Жим лёжа · широкий хват`** — **`4×10 · 50 кг`**
  3. ✓ done — **`Сведения в кроссовере`** — **`4×12 · 12 кг`**
  4. **`Подъём на бицепс · супинация`** — **`4×10 · 8 кг`**
  5. **`Французский жим лёжа`** — **`3×12 · 12 кг`**
  6. **`Заминка · растяжка`** — **`6 мин`**
  - Check icon = lucide `Check` (polyline 20 6 9 17 4 12). Done checkbox fills accent-deep (light) / accent (dark).

**3. Section `Заметка тренера`** → neutral callout (`.am-callout`, moon icon, lucide `Moon`):
> В прошлый раз клиент жаловался на **правое плечо** — следить за техникой в жиме и не догружать. Снизить вес сведений до 10 кг.
(bold span on `правое плечо`.)

**4. Accent callout** (`.am-callout.accent`, `margin-top:8px`, activity/pulse icon, lucide `Activity` — polyline 22 12 18 12 15 21 9 3 6 12 2 12):
> Чек-ин в **15:28** (опоздание 0 мин) · в зале сейчас
(bold span on `15:28`.)

### Footer (`.am-modal-foot-spread`)
- **Left — info (`#m-session-progress-text` + bar):** text **`<b>3</b> из 6 упражнений`** next to an 80×4px progress bar (`.session-progress-bar`) filled to **`width:50%`** by default. Both update live as program rows toggle.
- **Right — 3 buttons** (in DOM order; wrap allowed):
  - **`Отменить`** (`.am-btn-text`, id `m-session-cancel`)
  - **`Перенести`** (`.am-btn-ghost`, id `m-session-reschedule`)
  - **`Завершить`** (`.am-btn-primary`, id `m-session-complete`)

### Derived values, state changes & toasts
- **Title/subtitle** are computed by splitting `type` on `' · '` (see header). **Pill** visibility = `status === 'live'`.
- **Program toggle:** clicking any `.am-prog-row` toggles `.done`; footer recomputes `done = count(.done)`, `total = count(rows)` → updates text `<b>{done}</b> из {total} упражнений` and bar width = `done/total*100%`.
- **`Завершить`:** closes modal, then after 200ms a **success toast** — title **`Тренировка завершена`**, msg **`{Имя клиента} · клиент получил push с программой`** (e.g. `Маша Конева · клиент получил push с программой`), `variant:'success'`.
- **`Перенести`:** closes modal, then 200ms later an **info toast** — title **`Перенос тренировки`**, msg **`Откроется выбор слота`**, `variant:'info'`.
- **`Отменить`:** opens a **confirm dialog** first (the shared confirm modal, uses `.am-btn-danger`):
  - title **`Отменить тренировку?`**, msg **`{Имя клиента} получит push-уведомление об отмене.`**, confirm label **`Отменить`** (destructive), cancel label **`Назад`**.
  - On confirm: closes session modal, then 200ms later a **warn toast** with UNDO — title **`Тренировка отменена`**, msg = client name, `variant:'warn'`, `duration:5000`, undo label **`Отменить`**; pressing undo fires a success toast **`Восстановлено · {Имя клиента}`** (`variant:'success'`, `duration:2200`).
- On open, `m-session` stores `dataset.idx = idx`.

### Sample data array (8 rows; for mocks — `sessionData[]`)
Each row: `{ time, dur(min), type, status('done'|'live'|'planned'|'group'), client, clientAv(hex), clientI(initials), trainer, trainerAv, trainerI, tag, cs1, cs2, cs3, progress, total:6 }`.
1. `09:00` · 60 · `Персональная · ноги + спина · зал 1` · **done** · Карина Левчук `#f59e0b` КЛ / тренер Аня Соколова `#f59e0b` АС · tag `Полугодовой · 2 года с нами` · stats `128` / `24 нед` / `3 мая` · progress 6/6
2. `10:30` · 75 · `Групповая · йога · 8/10 чел · студия` · **done** · Лиза Орлова `#a855f7` ЛО / тренер Лиза Орлова ЛО · tag `Тренер ведёт группу` · stats `—`/`—`/`—` · 6/6
3. `13:00` · 60 · `Персональная · функционал · зал 2` · **done** · Иван Гранин `#0ea5e9` ИГ / тренер Марк Левин `#0ea5e9` МЛ · tag `Годовой · 1 год с нами` · `47`/`5 нед`/`12 окт` · 6/6
4. `15:30` · 60 · `Персональная · грудь + руки · зал 1` · **live** · Маша Конева `#dc2626` МК / тренер Аня Соколова `#f59e0b` АС · tag `Месячный · 6 мес с нами` · `37`/`12 нед`/`13 мая` · 3/6
5. `15:30` · 75 · `Групповая · пилатес · 6/8 чел · студия` · **live** · Соня Бек `#10b981` СБ / тренер Соня Бек СБ · tag `Тренер ведёт группу` · `—`/`—`/`—` · 4/6
6. `18:00` · 60 · `Персональная · силовая · зал 1` · **planned** · Олег Ивлев `#0ea5e9` ОИ / тренер Аня Соколова `#f59e0b` АС · tag `Месячный · истекает 2 мая` · `12`/`7 нед`/`2 мая` · 0/6
7. `19:00` · 60 · `Персональная · бодибилдинг · зал 2` · **planned** · Никита Сюй `#6366f1` НС / тренер Игорь Раш `#6366f1` ИР · tag `Годовой · 11 мес с нами` · `92`/`32 нед`/`11 мая` · 0/6
8. `20:00` · 75 · `Групповая · бокс · 10/12 чел · ринг` · **group** · Денис Кравцов `#dc2626` ДК / тренер Денис Кравцов ДК · tag `Тренер ведёт группу` · `—`/`—`/`—` · 0/6

> Note: the *static HTML defaults* in the markup (`#f59e0b`/`МК`, stats `37/12 нед/13 мая`) are just the pre-fill; the live row (#4) is what realistically opens. The trainer-card stats (`Апрель 64 сессии / Рейтинг 4.9 / Стаж 3 года`) and the whole **Программа / Заметка / accent-callout** block are static markup not overwritten by `openSession` — treat them as fixed sample content for now.

### m-session-specific CSS
```css
/* Info-card (client/trainer) */
.am-info-card { background: var(--surface-2); border: 0.5px solid var(--border); border-radius: 12px; padding: 12px 12px 10px; }
.am-info-card .ic-h { font-size: 10.5px; font-weight: 700; letter-spacing: 0.5px; text-transform: uppercase; color: var(--text-3); margin-bottom: 8px; }
.am-info-card .ic-row { display: flex; align-items: center; gap: 10px; min-width: 0; }
.am-info-card .ic-av { width: 36px; height: 36px; border-radius: 50%; display: grid; place-items: center; color: white; font-size: 13px; font-weight: 700; flex-shrink: 0; letter-spacing: -0.2px; }
.am-info-card .ic-text { min-width: 0; }
.am-info-card .ic-name { font-size: 13.5px; font-weight: 650; letter-spacing: -0.1px; white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }
.am-info-card .ic-meta { font-size: 11.5px; color: var(--text-3); margin-top: 1px; white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }
.am-info-card .ic-stats { display: flex; gap: 16px; margin-top: 10px; padding-top: 10px; border-top: 0.5px dashed var(--border); }
.am-info-card .ic-stat .l { font-size: 10.5px; color: var(--text-3); }
.am-info-card .ic-stat .n { font-size: 14.5px; font-weight: 700; margin-top: 1px; font-variant-numeric: tabular-nums; letter-spacing: -0.2px; }

/* Program list */
.am-prog { margin-top: 4px; }
.am-prog-row { display: grid; grid-template-columns: 20px 1fr auto; gap: 11px; padding: 9px 0; border-top: 0.5px dashed var(--border); align-items: center; font-size: 13px; cursor: pointer; }
.am-prog-row:first-child { border-top: 0; }
.am-prog-row.done .am-prog-name { color: var(--text-3); text-decoration: line-through; }
.am-prog-row.done .am-prog-set { color: var(--text-3); }
.am-prog-check { width: 18px; height: 18px; border-radius: 6px; border: 1.5px solid var(--border-strong); display: grid; place-items: center; color: transparent; transition: background 0.15s, border-color 0.15s, color 0.15s; }
.am-prog-row.done .am-prog-check { background: var(--accent-deep); border-color: var(--accent-deep); color: white; }
[data-theme="dark"] .am-prog-row.done .am-prog-check { background: var(--accent); border-color: var(--accent); color: #06120c; }
.am-prog-name { letter-spacing: -0.1px; font-weight: 500; }
.am-prog-set { font-variant-numeric: tabular-nums; font-weight: 600; font-size: 12px; color: var(--text-2); }

/* Footer progress bar */
.session-foot-info { display: flex; align-items: center; gap: 10px; }
.session-progress-bar { width: 80px; height: 4px; border-radius: 999px; background: var(--surface-3); overflow: hidden; position: relative; }
.session-progress-bar > div { height: 100%; background: var(--accent-deep); border-radius: 999px; transition: width 0.3s; }
[data-theme="dark"] .session-progress-bar > div { background: var(--accent); }

/* "Идёт сейчас" status pill (emerald, pulsing dot) */
.session-status-pill {
  display: inline-flex; align-items: center; gap: 5px;
  font-size: 10.5px; font-weight: 700; letter-spacing: 0.3px; text-transform: uppercase;
  padding: 3px 8px 3px 6px; border-radius: 999px;
  background: var(--accent-soft); color: var(--accent-deep);
  margin-left: 8px; vertical-align: middle;
}
.session-status-pill::before {
  content: ""; width: 5px; height: 5px; border-radius: 50%;
  background: var(--accent-deep); animation: pulse 1.6s ease-in-out infinite;
}
@keyframes pulse {
  0%,100% { opacity: 1; transform: translateY(-50%) scale(1); }
  50%     { opacity: 0.5; transform: translateY(-50%) scale(0.8); }
}
```
> Note: the `@keyframes pulse` uses `translateY(-50%)` (it is shared with a vertically-centered status dot elsewhere); inside the pill the dot is flex-centered, so for the React rebuild drop the `translateY` and pulse opacity/scale only.

---

## m-present

### Purpose & trigger
«В клубе сейчас» — live roster of who is currently in the club. Opens when the admin clicks the dashboard **occupancy card** (`.occupancy`): JS `occCard.addEventListener('click', () => AM.open('m-present'))`. Uses the **wide** modal (`.am-modal-wide`, 720px).

### Header
- **Title** (`.am-modal-title`, `#m-present-title`): **`В клубе сейчас · 42 / 80`** — the `42` (`#present-count`) is current occupancy, `80` (`#present-cap`) is capacity (both rendered as `<span>`s inside the title).
- **Subtitle** (`#m-present-sub`): **`Обычно в это время 35 · пик дня 74 в 20:00 · обновлено только что`**
- Close button (×), `aria-label="Закрыть"`.

### Body (in order)

**1. Zone filter chips** (`.am-chips`, `data-am-group="present-zone"`) — a single-select radio group. Each chip shows a label + dimmed count. First is active by default:
- **`Все · 42`** (`data-value="all"`, **active**)
- **`Зал · 31`** (`data-value="gym"`)
- **`Студия · 8`** (`data-value="studio"`)
- **`Сауна · 3`** (`data-value="sauna"`)
(counts are `<span style="opacity:0.6">`.)

**2. Presence grid** (`.am-present`, `#present-grid`, `margin-top:14px`) — responsive auto-fill grid, min column 150px. **15 cards** in the markup (the comment says "14 sample cards"; there are actually 15). Each card (`.am-present-card`, `data-zone=…`): a 30×30 round avatar (`.ap-av`, initials, colored bg) + name (`.ap-name`) + meta (`.ap-meta`). Cards are filtered by the active zone chip.

| # | zone | avatar bg | initials | name (`.ap-name`) | meta (`.ap-meta`) |
|---|---|---|---|---|---|
| 1 | gym | `#0ea5e9` | МЛ | **Марк Левин** | **с 15:24 · 12 мин** |
| 2 | studio | `#a855f7` | ЛО | **Лиза Орлова** | **с 15:18 · 18 мин** |
| 3 | gym | `#f59e0b` | КЛ | **Карина Левчук** | **с 15:02 · 34 мин** |
| 4 | gym | `#10b981` | АШ | **Артур Шах** | **с 14:47 · 49 мин** |
| 5 | gym | `#6366f1` | НС | **Никита Сюй** | **с 14:42 · 54 мин** |
| 6 | studio | `#dc2626` | МК | **Маша Конева** | **с 14:30 · 1 ч 6 мин** |
| 7 | sauna | `#f59e0b` | ОИ | **Олег Ивлев** | **с 14:20 · 1 ч 16 мин** |
| 8 | gym | `#0ea5e9` | ИГ | **Иван Гранин** | **с 14:14 · 1 ч 22 мин** |
| 9 | gym | `#a855f7` | ЮЗ | **Юлия Зайцева** | **с 14:00 · 1 ч 36 мин** |
| 10 | studio | `#10b981` | СБ | **Соня Бек** | **с 13:55 · 1 ч 41 мин** |
| 11 | gym | `#dc2626` | ДК | **Денис Кравцов** | **с 13:48 · 1 ч 48 мин** |
| 12 | sauna | `#6366f1` | ИР | **Игорь Раш** | **с 13:30 · 2 ч 6 мин** |
| 13 | gym | `#f59e0b` | АС | **Аня Соколова** | **тренер · с 09:00** |
| 14 | gym | `#0ea5e9` | МЛ | **Марк Левин** | **тренер · с 12:00** |
| 15 | gym | `#0284c7` | КП | **Кирилл Петров** | **с 13:20 · 2 ч 16 мин** |
| (16) | gym | `#7c3aed` | ЯТ | **Яна Турчанинова** | **с 13:10 · 2 ч 26 мин** |

> There are in fact **16** rows in the markup (the table above lists all of them; the prototype's "14"/15 comments are loose). Two of them (13, 14) are trainers — their meta starts with `тренер · ` and has no elapsed-duration. Reproduce both kinds: `с {HH:MM} · {elapsed}` for members, `тренер · с {HH:MM}` for staff.

**3. Overflow line** — centered muted text (`font-size:12px; color:var(--text-3)`): **`+ 26 клиентов не показаны`**.

### Footer (`.am-modal-foot-spread`)
- **Left — info:** **`Пиковая загрузка ожидается в <b>20:00</b> · ~74 чел`** (bold on `20:00`).
- **Right — 2 buttons:**
  - **`Закрыть`** (`.am-btn-ghost`, `data-am-close`)
  - **`Открыть посещаемость`** (`.am-btn-primary`, `data-am-close`) — closes the modal (in the real app this should navigate to the Attendance/Посещаемость page).

### Derived values, state changes & toasts
- **Zone filter:** the chip group dispatches `am:select` with `detail.value` (`all|gym|studio|sauna`); the grid shows a card when `value === 'all' || card.zone === value`, else hides it. No toasts.
- **Counts** in the title and chips (`42 / 80`, `42/31/8/3`) are static sample numbers in the prototype — in React derive chip counts from the data and `42`/`80` from occupancy/capacity. (Note: visible cards ≠ 42; the grid is a truncated sample, hence the "+ 26 … не показаны" line.)
- Both footer buttons simply close (`data-am-close`). "Открыть посещаемость" is the intended navigation to the attendance page.

### m-present-specific CSS
```css
.am-present { display: grid; grid-template-columns: repeat(auto-fill, minmax(150px, 1fr)); gap: 8px; }
.am-present-card { display: flex; align-items: center; gap: 9px; padding: 9px 10px; background: var(--surface-2); border: 0.5px solid var(--border); border-radius: 10px; }
.am-present-card .ap-av { width: 30px; height: 30px; border-radius: 50%; display: grid; place-items: center; color: white; font-size: 11px; font-weight: 700; flex-shrink: 0; letter-spacing: -0.2px; }
.am-present-card .ap-text { min-width: 0; flex: 1; }
.am-present-card .ap-name { font-size: 12.5px; font-weight: 600; white-space: nowrap; overflow: hidden; text-overflow: ellipsis; letter-spacing: -0.1px; }
.am-present-card .ap-meta { font-size: 10.5px; color: var(--text-3); font-variant-numeric: tabular-nums; margin-top: 1px; }
```
> Avatar bg colors are inline per card (sky `#0ea5e9`/`#0284c7`, violet `#a855f7`/`#7c3aed`, amber `#f59e0b`, emerald `#10b981`, indigo `#6366f1`, red `#dc2626`) — these are decorative per-person tints, **not** semantic status colors. In React generate them from a fixed avatar-color palette keyed by person.

import { useCallback, useEffect, useLayoutEffect, useRef, useState, Fragment } from 'react';

/* ============================================================
   Экран «Запись» — точный перенос Запись.html.
   Самодостаточный компонент: стили, данные, device-рамка и вся
   интерактивная логика (флоу pick → confirm → done) в одном файле.
   ============================================================ */

/* ---------- Стили (verbatim из оригинала) ---------- */
const CSS = `
:root {
  --accent: #2dd4a4;
  --accent-deep: #0f9b76;
  --accent-soft: #d6f5ea;

  --bg: #f5f5f4;
  --surface: #ffffff;
  --surface-2: #fafaf9;
  --border: #e7e5e4;
  --border-strong: #d6d3d1;
  --text: #1c1917;
  --text-2: #57534e;
  --text-3: #a8a29e;

  --warn: #e9a23b;
  --warn-soft: #fef3e2;
  --danger: #e1483b;
  --danger-soft: #fdecea;

  --font: -apple-system, BlinkMacSystemFont, "SF Pro Text", "SF Pro Display",
          "Inter Variable", "Inter", system-ui, sans-serif;

  --r-pill: 999px;
  --r-lg: 20px;

  --sh-1: 0 1px 2px rgba(28, 25, 23, 0.04);
  --sh-2: 0 1px 3px rgba(28, 25, 23, 0.05), 0 4px 14px rgba(28, 25, 23, 0.04);

  --page: #e7e5e4;
}

body.dark {
  --accent: #2dd4a4;
  --accent-deep: #34e0b0;
  --accent-soft: rgba(45, 212, 164, 0.18);

  --bg: #14110e;
  --surface: #211c18;
  --surface-2: #1b1714;
  --border: #2e2823;
  --border-strong: #3d362f;
  --text: #f5f1ea;
  --text-2: #b8b0a6;
  --text-3: #7c736a;

  --warn: #e9a23b;
  --warn-soft: rgba(233, 162, 59, 0.20);
  --danger: #f47168;
  --danger-soft: rgba(244, 113, 104, 0.16);

  --sh-1: 0 1px 2px rgba(0,0,0,0.4);
  --sh-2: 0 1px 3px rgba(0,0,0,0.5), 0 4px 14px rgba(0,0,0,0.3);

  --page: #0a0a0a;
}

* { box-sizing: border-box; }

html, body {
  margin: 0; padding: 0;
  font-family: var(--font);
  -webkit-font-smoothing: antialiased;
  -moz-osx-font-smoothing: grayscale;
  background: var(--page);
  color: var(--text);
  min-height: 100vh;
  transition: background 0.3s ease;
}
button { font-family: inherit; }
input { font-family: inherit; }
.t-num { font-variant-numeric: tabular-nums; }
.t-mini { font-size: 11px; font-weight: 600; letter-spacing: 0.5px; text-transform: uppercase; color: var(--text-3); }
.t-small { font-size: 13px; font-weight: 400; line-height: 1.4; color: var(--text-2); }
.t-body { font-size: 15px; font-weight: 400; line-height: 1.4; }
.t-h3 { font-size: 17px; font-weight: 600; letter-spacing: -0.2px; line-height: 1.25; color: var(--text); }
.t-h1 { font-size: 26px; font-weight: 700; letter-spacing: -0.5px; line-height: 1.15; color: var(--text); }
.t-display { font-size: 34px; font-weight: 700; letter-spacing: -0.8px; line-height: 1.05; color: var(--text); }
.row { display: flex; align-items: center; gap: 12px; }
.row-between { display: flex; align-items: center; justify-content: space-between; gap: 12px; }
.stack-2 { display: flex; flex-direction: column; gap: 8px; }

.stage {
  min-height: 100vh;
  display: flex; align-items: center; justify-content: center;
  padding: 24px;
}

/* Device */
.device {
  width: 390px; height: 844px; position: relative;
  border-radius: 54px; background: #0a0a0a; padding: 12px;
  box-shadow: 0 50px 100px rgba(28, 25, 23, 0.25), 0 0 0 1px rgba(28, 25, 23, 0.15);
}
.device-inner {
  position: absolute; inset: 12px;
  border-radius: 44px; overflow: hidden;
  background: var(--bg);
  transition: background 0.3s ease;
}
.island {
  position: absolute; top: 8px; left: 50%; transform: translateX(-50%);
  width: 120px; height: 32px; border-radius: 999px;
  background: #000; z-index: 300; pointer-events: none;
}
.status-bar {
  position: absolute; top: 0; left: 0; right: 0; z-index: 20;
  display: flex; align-items: center; justify-content: space-between;
  padding: 14px 28px 10px; height: 44px;
  color: var(--text); font-size: 15px; font-weight: 600;
  pointer-events: none;
}
.status-bar span { font-variant-numeric: tabular-nums; }
.status-bar .glyphs { display: flex; gap: 6px; align-items: center; }
.home-indicator {
  position: absolute; bottom: 8px; left: 50%; transform: translateX(-50%);
  width: 134px; height: 5px; background: var(--text);
  opacity: 0.85; border-radius: 3px; z-index: 10;
}

.screen {
  position: absolute; inset: 0;
  background: var(--bg);
  display: flex; flex-direction: column;
  transition: background 0.3s ease;
}
.page {
  position: absolute; inset: 0;
  display: flex; flex-direction: column;
  overflow: hidden;
}

/* Scroll body */
.scroller {
  flex: 1; overflow-y: auto; -webkit-overflow-scrolling: touch;
}
.scroller::-webkit-scrollbar { display: none; }
.no-sb { scrollbar-width: none; }
.no-sb::-webkit-scrollbar { display: none; }

.card {
  background: var(--surface);
  border: 0.5px solid var(--border);
  border-radius: var(--r-lg);
  box-shadow: var(--sh-2);
}

.press { transition: transform 0.1s ease, background 0.15s ease; cursor: pointer; }
.press:active { transform: scale(0.985); }

.fade-up { animation: fade-up 0.32s cubic-bezier(0.32,0.72,0.2,1) both; }
@keyframes fade-up { from { opacity: 0; transform: translateY(8px); } to { opacity: 1; transform: translateY(0); } }
.scale-in { animation: scale-in 0.2s ease-out both; }
@keyframes scale-in { from { opacity: 0; transform: scale(0.96); } to { opacity: 1; transform: scale(1); } }

/* Buttons */
.btn {
  appearance: none; border: 0;
  background: var(--text); color: var(--bg);
  height: 50px; padding: 0 22px;
  border-radius: var(--r-pill);
  font-size: 16px; font-weight: 600; letter-spacing: -0.2px;
  cursor: pointer; display: inline-flex; align-items: center; justify-content: center; gap: 8px;
  transition: transform 0.12s ease, opacity 0.12s ease;
}
.btn:active { transform: scale(0.98); }
.btn:disabled { opacity: 0.4; cursor: not-allowed; }
.btn-accent { background: var(--accent); color: #0a1410; }
body.dark .btn-accent { color: #06120c; }
.btn-ghost { background: var(--surface); color: var(--text); border: 0.5px solid var(--border-strong); }
.btn-soft { background: var(--surface-2); color: var(--text); }

/* Chips */
.chip {
  display: inline-flex; align-items: center; gap: 6px;
  height: 28px; padding: 0 12px; border-radius: var(--r-pill);
  background: var(--surface-2); color: var(--text-2);
  font-size: 13px; font-weight: 500;
  border: 0.5px solid var(--border);
  white-space: nowrap; flex-shrink: 0;
}

/* Avatar */
.ava {
  border-radius: 999px; display: inline-flex; align-items: center; justify-content: center;
  font-weight: 700; letter-spacing: -0.3px; flex-shrink: 0;
}

/* Calendar */
.cal-day {
  aspect-ratio: 1 / 1.15; border-radius: 12px;
  display: flex; flex-direction: column; align-items: center; justify-content: center;
  background: var(--bg); border: 0.5px solid var(--border-strong);
  cursor: pointer; color: var(--text); font-family: inherit; padding: 0; position: relative;
  transition: transform 0.12s ease, background 0.15s, border-color 0.15s, color 0.15s, box-shadow 0.15s;
}
.cal-day:hover:not(.selected):not(.disabled) { border-color: var(--text-2); background: var(--surface-2); }
.cal-day:active:not(.selected):not(.disabled) { transform: scale(0.96); }
.cal-day .dow { font-size: 10px; font-weight: 600; color: var(--text-3); letter-spacing: 0.4px; text-transform: uppercase; }
.cal-day .num { font-size: 17px; font-weight: 600; margin-top: 2px; }
.cal-day.disabled {
  cursor: not-allowed; color: var(--text-3);
  background: repeating-linear-gradient(-45deg, transparent 0 5px, color-mix(in oklab, var(--border) 80%, transparent) 5px 6px);
  border-color: var(--border);
}
.cal-day.disabled .dow, .cal-day.disabled .num { color: var(--text-3); }
.cal-day.selected {
  background: var(--text); color: var(--bg); border-color: var(--text);
  box-shadow: 0 4px 14px color-mix(in oklab, var(--text) 25%, transparent);
}
.cal-day.selected .dow { color: color-mix(in oklab, var(--bg) 70%, transparent); }
.cal-day.has-slot::after {
  content: ""; position: absolute; bottom: 6px; width: 4px; height: 4px; border-radius: 50%; background: var(--accent);
}
.cal-day.selected.has-slot::after { background: var(--bg); }

/* Grouped time picker */
.period-card { background: var(--surface); border: 0.5px solid var(--border); border-radius: var(--r-lg); overflow: hidden; }
.period-card[data-empty="true"] { background: transparent; }
.period-card__head {
  display: flex; align-items: center; gap: 8px; padding: 12px 14px;
  border-bottom: 0.5px solid var(--border);
  background: color-mix(in oklab, var(--surface-2) 50%, transparent);
}
.period-card[data-empty="true"] .period-card__head { background: transparent; }
.period-card__grid { display: grid; grid-template-columns: repeat(3, 1fr); gap: 8px; padding: 10px; }

/* Time slot */
.slot-chip {
  appearance: none; border: 0.5px solid var(--border-strong); background: var(--bg); color: var(--text);
  width: 100%; height: 44px; padding: 0; border-radius: 10px;
  font-size: 15px; font-weight: 600; cursor: pointer; font-family: inherit;
  font-variant-numeric: tabular-nums; letter-spacing: -0.2px;
  transition: transform 0.12s ease, background 0.15s, border-color 0.15s, color 0.15s, box-shadow 0.15s;
  display: inline-flex; align-items: center; justify-content: center;
}
.slot-chip:hover:not(.busy):not(.selected) { border-color: var(--text-2); background: var(--surface-2); }
.slot-chip:active:not(.busy):not(.selected) { transform: scale(0.97); }
.slot-chip.selected {
  background: var(--text); color: var(--bg); border-color: var(--text);
  box-shadow: 0 4px 14px color-mix(in oklab, var(--text) 25%, transparent);
}
.slot-chip.busy {
  color: var(--text-3);
  background: repeating-linear-gradient(-45deg, transparent 0 5px, color-mix(in oklab, var(--border) 80%, transparent) 5px 6px);
  border-color: var(--border);
  text-decoration: line-through; text-decoration-thickness: 1px;
  text-decoration-color: color-mix(in oklab, var(--text-3) 70%, transparent);
  cursor: default;
}
@keyframes slot-shake {
  0%, 100% { transform: translateX(0); }
  20% { transform: translateX(-5px); }
  40% { transform: translateX(5px); }
  60% { transform: translateX(-3px); }
  80% { transform: translateX(3px); }
}
.slot-chip.shake { animation: slot-shake 0.42s ease-out; color: var(--danger); border-color: var(--danger); text-decoration-color: var(--danger); }

/* Slot tooltip */
.slot-tip {
  position: absolute; left: 50%; bottom: calc(100% + 6px); transform: translateX(-50%);
  background: var(--text); color: var(--bg); font-size: 12px; font-weight: 500;
  padding: 6px 10px; border-radius: 8px; white-space: nowrap; pointer-events: none; z-index: 50;
  box-shadow: 0 6px 20px rgba(0,0,0,0.18); animation: tip-in 0.18s ease-out both;
}
.slot-tip-arrow {
  position: absolute; left: 50%; top: 100%; transform: translateX(-50%);
  width: 0; height: 0; border-left: 5px solid transparent; border-right: 5px solid transparent; border-top: 5px solid var(--text);
}
@keyframes tip-in { from { opacity: 0; transform: translate(-50%, -4px); } to { opacity: 1; transform: translate(-50%, 0); } }

/* Row item (review/done) */
.rowitem { display: flex; align-items: center; gap: 12px; padding: 12px 14px; }
.rowitem .ri-ico {
  width: 36px; height: 36px; border-radius: 999px; flex-shrink: 0;
  background: var(--surface-2); display: flex; align-items: center; justify-content: center;
}
.divider { height: 0.5px; background: var(--border); margin-left: 60px; }

/* Bottom tab bar */
.tabbar {
  height: 80px; padding: 8px 16px 22px;
  display: grid; grid-template-columns: repeat(4, 1fr);
  background: color-mix(in oklab, var(--surface) 85%, transparent);
  backdrop-filter: blur(20px) saturate(180%);
  -webkit-backdrop-filter: blur(20px) saturate(180%);
  border-top: 0.5px solid var(--border);
  flex-shrink: 0; position: absolute; left: 0; right: 0; bottom: 0; z-index: 30;
}
.tabbar-item {
  appearance: none; border: 0; background: transparent;
  display: flex; flex-direction: column; align-items: center; justify-content: center;
  gap: 3px; color: var(--text-3); font-size: 10.5px; font-weight: 600;
  letter-spacing: 0.1px; cursor: pointer; padding: 0; position: relative;
}
.tabbar-item.active { color: var(--text); }

/* CTA bar */
.cta-bar {
  position: absolute; left: 0; right: 0; bottom: 0;
  padding: 12px 16px 20px;
  background: linear-gradient(to top, var(--bg) 70%, transparent);
  z-index: 35;
}
.book-summary {
  display: flex; align-items: center; gap: 12px;
  padding: 10px 14px;
  background: var(--surface);
  border: 0.5px solid var(--border);
  border-radius: 16px;
  box-shadow: var(--sh-2);
}

.toast {
  position: absolute; left: 50%; bottom: 96px; transform: translate(-50%, 16px);
  z-index: 60; background: var(--text); color: var(--bg);
  font-size: 13.5px; font-weight: 600; padding: 11px 18px; border-radius: 999px;
  box-shadow: 0 12px 30px rgba(0,0,0,0.28);
  opacity: 0; pointer-events: none;
  transition: opacity 0.22s ease, transform 0.28s cubic-bezier(0.32,0.72,0.2,1);
  white-space: nowrap;
}
.toast.show { opacity: 1; transform: translate(-50%, 0); }

/* Bottom sheet (trainer detail) */
.sheet-scrim {
  position: absolute; inset: 0; z-index: 40;
  background: rgba(10, 8, 6, 0.42);
  opacity: 0; pointer-events: none;
  transition: opacity 0.28s ease;
}
.sheet-scrim.open { opacity: 1; pointer-events: auto; }
body.dark .sheet-scrim { background: rgba(0,0,0,0.55); }
.sheet {
  position: absolute; left: 0; right: 0; bottom: 0; z-index: 41;
  background: var(--surface);
  border-top-left-radius: 28px; border-top-right-radius: 28px;
  box-shadow: 0 -10px 40px rgba(0,0,0,0.25);
  transform: translateY(100%);
  transition: transform 0.34s cubic-bezier(0.32,0.72,0.2,1);
  max-height: 86%; display: flex; flex-direction: column;
  overflow: hidden;
}
.sheet-scrim.open .sheet { transform: translateY(0); }
.sheet-handle {
  width: 38px; height: 5px; border-radius: 3px; background: var(--border-strong);
  margin: 10px auto 2px; flex-shrink: 0;
}

.hidden { display: none !important; }
`;

/* ---------- Иконки ---------- */
const ICON = {
  starFill: '<path d="M12 3l2.7 5.5 6.1.9-4.4 4.3 1 6.1L12 17l-5.4 2.8 1-6.1L3.2 9.4l6.1-.9L12 3z" fill="#f59e0b" stroke="none"/>',
  sunrise: '<path d="M12 3v4M5.5 8.5l1.4 1.4M18.5 8.5l-1.4 1.4M3 17h18M7 17a5 5 0 0110 0M2 21h20" />',
  sun: '<circle cx="12" cy="12" r="4"/><path d="M12 2v2M12 20v2M4.2 4.2l1.4 1.4M18.4 18.4l1.4 1.4M2 12h2M20 12h2M4.2 19.8l1.4-1.4M18.4 5.6l1.4-1.4"/>',
  moon: '<path d="M21 13A9 9 0 1111 3a7 7 0 0010 10z"/>',
  chevronLeft: '<path d="M15 6l-6 6 6 6"/>',
  chevronRight: '<path d="M9 6l6 6-6 6"/>',
  user: '<circle cx="12" cy="8" r="4"/><path d="M4 21c0-4 4-7 8-7s8 3 8 7"/>',
  calendar: '<rect x="3" y="5" width="18" height="16" rx="3"/><path d="M3 10h18M8 3v4M16 3v4"/>',
  clock: '<circle cx="12" cy="12" r="9"/><path d="M12 7v5l3 2"/>',
  card: '<rect x="3" y="6" width="18" height="13" rx="3"/><path d="M3 11h18"/>',
  check: '<path d="M5 12l5 5L20 6"/>',
  search: '<circle cx="11" cy="11" r="7"/><path d="M16 16l4 4"/>',
  arrowRight: '<path d="M5 12h14M13 6l6 6-6 6"/>',
};

function Ico({ name, size, color, sw, style }) {
  return (
    <svg
      width={size}
      height={size}
      viewBox="0 0 24 24"
      fill="none"
      stroke={color || 'currentColor'}
      strokeWidth={sw || 1.8}
      strokeLinecap="round"
      strokeLinejoin="round"
      style={style}
      dangerouslySetInnerHTML={{ __html: ICON[name] }}
    />
  );
}

/* ---------- Хелперы ---------- */
const fmt = (n) => n.toLocaleString('ru-RU');
const monthName = (m) => ['янв', 'фев', 'мар', 'апр', 'мая', 'июн', 'июл', 'авг', 'сен', 'окт', 'ноя', 'дек'][m] || '';
const monthFull = (m) => ['Январь', 'Февраль', 'Март', 'Апрель', 'Май', 'Июнь', 'Июль', 'Август', 'Сентябрь', 'Октябрь', 'Ноябрь', 'Декабрь'][m] || '';
const addMinutes = (time, mins) => {
  const [h, m] = time.split(':').map(Number);
  const total = (h * 60 + m + mins) % (24 * 60);
  return `${String(Math.floor(total / 60)).padStart(2, '0')}:${String(total % 60).padStart(2, '0')}`;
};
const round50 = (n) => Math.round(n / 50) * 50;

/* ---------- Данные ---------- */
function buildCalendar() {
  const days = [];
  const now = new Date('2026-04-30T09:00:00');
  const dows = ['Вс', 'Пн', 'Вт', 'Ср', 'Чт', 'Пт', 'Сб'];
  for (let i = 0; i < 21; i++) {
    const d = new Date(now);
    d.setDate(now.getDate() + i);
    const hasSlot = i % 7 !== 6 && i !== 4;
    days.push({ key: `d${i}`, dow: dows[d.getDay()], num: d.getDate(), month: d.getMonth(), isToday: i === 0, hasSlot });
  }
  return days;
}
const CALENDAR = buildCalendar();
const TIME_SLOTS = ['08:00', '09:00', '10:00', '11:30', '13:00', '15:00', '16:30', '18:00', '19:00', '20:30'];
const BUSY_SLOTS = {
  t1: ['09:00', '13:00', '18:00'], t2: ['10:00', '15:00', '19:00'], t3: ['08:00', '11:30', '20:30'],
  t4: ['16:30', '19:00'], t5: ['09:00', '13:00'], t6: ['11:30', '18:00', '20:30'],
};
const TRAINERS = [
  { id: 't1', name: 'Аня Соколова', spec: 'Силовые, функционал', exp: '7 лет', initials: 'АС', color: '#f59e0b', bg: '#fef3c7', price: 2200, rating: 4.9 },
  { id: 't2', name: 'Марк Левин', spec: 'Кроссфит, выносливость', exp: '5 лет', initials: 'МЛ', color: '#0ea5e9', bg: '#dbeafe', price: 2400, rating: 4.8 },
  { id: 't3', name: 'Лиза Орлова', spec: 'Йога, стретчинг', exp: '9 лет', initials: 'ЛО', color: '#a855f7', bg: '#f3e8ff', price: 2000, rating: 5.0 },
  { id: 't4', name: 'Денис Кравцов', spec: 'Бокс, ММА', exp: '11 лет', initials: 'ДК', color: '#dc2626', bg: '#fee2e2', price: 2800, rating: 4.9 },
  { id: 't5', name: 'Соня Бек', spec: 'Пилатес, осанка', exp: '4 года', initials: 'СБ', color: '#10b981', bg: '#d1fae5', price: 2100, rating: 4.7 },
  { id: 't6', name: 'Игорь Раш', spec: 'Бодибилдинг', exp: '8 лет', initials: 'ИР', color: '#6366f1', bg: '#e0e7ff', price: 2500, rating: 4.8 },
];
const BUSY_REASONS = {
  t1: { '09:00': 'утренняя группа', '13:00': 'персоналка с другим клиентом', '18:00': 'свободное окно недоступно' },
  t2: { '10:00': 'кроссфит-сбор', '15:00': 'тренировка', '19:00': 'занят' },
  t3: { '08:00': 'йога-класс', '11:30': 'персоналка', '20:30': 'класс по стретчингу' },
  t4: { '16:30': 'спарринг', '19:00': 'групповая' },
  t5: { '09:00': 'класс пилатеса', '13:00': 'персоналка' },
  t6: { '11:30': 'тренировка', '18:00': 'занят', '20:30': 'персоналка' },
};
const busyReason = (tid, slot) => (BUSY_REASONS[tid] && BUSY_REASONS[tid][slot]) || 'занято';
const PERIODS = [
  { id: 'morning', label: 'Утро', hint: 'до 11:00', icon: 'sunrise', range: [0, 11] },
  { id: 'day', label: 'День', hint: '11:00–17:00', icon: 'sun', range: [11, 17] },
  { id: 'evening', label: 'Вечер', hint: 'после 17:00', icon: 'moon', range: [17, 24] },
];
const DURATIONS = [
  { id: 30, label: '30 мин', short: '30 мин', mult: 0.6 },
  { id: 60, label: '1 час', short: '1 час', mult: 1 },
  { id: 90, label: '1,5 часа', short: '1,5 часа', mult: 1.45 },
];
const TRAINER_BIOS = {
  t1: 'Готовлю к силовым целям и возвращаю технику в базовых движениях. Люблю работать с новичками — без перегруза, по чуть-чуть.',
  t2: 'Кроссфит, метконы и выносливость. Заряжаю на интенсив и держу темп, но всегда слежу за формой.',
  t3: 'Йога и стретчинг для тех, кто много сидит. Раскрытие бёдер, спина, дыхание — мягко и осознанно.',
  t4: 'Бокс и ММА: техника удара, защита, работа на лапах. Подойдёт и для фитнеса, и для подготовки к спаррингу.',
  t5: 'Пилатес и осанка. Глубокие мышцы кора, баланс, восстановление после сидячей работы.',
  t6: 'Бодибилдинг и гипертрофия. Помогу собрать программу под объём и довести технику базовых до автоматизма.',
};

/* Доступность по дням — детерминированная, чтобы прототип был стабилен */
function busyForDay(tid, dayKey) {
  const ti = TRAINERS.findIndex((t) => t.id === tid);
  const di = CALENDAR.findIndex((d) => d.key === dayKey);
  if (ti < 0 || di < 0) return BUSY_SLOTS[tid] || [];
  if ((ti * 3 + di) % 6 === 1) return [...TIME_SLOTS];
  const base = BUSY_SLOTS[tid] || [];
  const extra = TIME_SLOTS[(ti * 5 + di * 2) % TIME_SLOTS.length];
  return Array.from(new Set([...base, extra]));
}
const isFullyBooked = (tid, dayKey) => busyForDay(tid, dayKey).length >= TIME_SLOTS.length;
function nearestAvailableDay(tid, fromKey) {
  const start = CALENDAR.findIndex((d) => d.key === fromKey);
  for (let i = start + 1; i < CALENDAR.length; i++) {
    const d = CALENDAR[i];
    if (d.hasSlot && !isFullyBooked(tid, d.key)) return d;
  }
  for (let i = 0; i < start; i++) {
    const d = CALENDAR[i];
    if (d.hasSlot && !isFullyBooked(tid, d.key)) return d;
  }
  return null;
}
function nextWindows(tid, n) {
  const out = [];
  for (let i = 0; i < CALENDAR.length && out.length < n; i++) {
    const d = CALENDAR[i];
    if (!d.hasSlot) continue;
    const busy = busyForDay(tid, d.key);
    const free = TIME_SLOTS.filter((s) => !busy.includes(s));
    if (free.length) out.push({ day: d, slot: free[0] });
  }
  return out;
}

/* Аватар */
function Avatar({ t, size }) {
  const fs = Math.round(size * 0.38);
  return (
    <span className="ava" style={{ width: size, height: size, background: t.bg, color: t.color, fontSize: fs }}>
      {t.initials}
    </span>
  );
}

export function BookingScreen() {
  const [step, setStep] = useState('pick'); // pick | confirm | done
  const [selectedDay, setSelectedDay] = useState(CALENDAR[1].key);
  const [selectedTrainer, setSelectedTrainer] = useState(null);
  const [selectedSlot, setSelectedSlot] = useState(null);
  const [duration, setDuration] = useState(60);
  const [trainerQuery, setTrainerQuery] = useState('');
  const [trainerFilter, setTrainerFilter] = useState('all');

  // Trainer detail sheet
  const [sheetContentId, setSheetContentId] = useState(null);
  const [sheetOpen, setSheetOpen] = useState(false);

  // Toast
  const [toastMsg, setToastMsg] = useState('');
  const [toastShow, setToastShow] = useState(false);
  const toastTimer = useRef(null);

  // Slot transient UI
  const [shakeSlot, setShakeSlot] = useState(null);
  const [tip, setTip] = useState(null); // { slot, reason }

  const scrollerRef = useRef(null);
  const timeStepRef = useRef(null);
  const ctaRef = useRef(null);
  const scrollPendingRef = useRef(false);

  const day = CALENDAR.find((d) => d.key === selectedDay);
  const trainer = TRAINERS.find((t) => t.id === selectedTrainer) || null;
  const durObj = DURATIONS.find((d) => d.id === duration) || DURATIONS[1];
  const priceFor = (t) => round50(t.price * durObj.mult);

  /* ── Тема ── */
  useEffect(() => {
    const apply = (t) => document.body.classList.toggle('dark', t === 'dark');
    apply(localStorage.getItem('myzal_theme') || 'light');
    const onStorage = (e) => {
      if (e.key === 'myzal_theme') apply(e.newValue || 'light');
    };
    window.addEventListener('storage', onStorage);
    return () => window.removeEventListener('storage', onStorage);
  }, []);

  /* ── Toast ── */
  const toast = useCallback((msg) => {
    setToastMsg(msg);
    setToastShow(true);
    clearTimeout(toastTimer.current);
    toastTimer.current = setTimeout(() => setToastShow(false), 1700);
  }, []);

  /* ── Глобальная делегированная навигация (data-go / data-toast) ── */
  useEffect(() => {
    const onClick = (e) => {
      const el = e.target.closest('[data-go], [data-toast]');
      if (!el) return;
      if (el.dataset.go) { window.location.href = el.dataset.go; return; }
      if (el.dataset.toast) toast(el.dataset.toast);
    };
    document.addEventListener('click', onClick);
    return () => document.removeEventListener('click', onClick);
  }, [toast]);

  /* ── Плавный скролл к блоку времени после выбора ── */
  useEffect(() => {
    if (!scrollPendingRef.current) return;
    scrollPendingRef.current = false;
    requestAnimationFrame(() => {
      const sc = scrollerRef.current;
      const target = timeStepRef.current;
      if (sc && target) sc.scrollTo({ top: target.offsetTop - 60, behavior: 'smooth' });
    });
  });

  /* ── Резерв места снизу под плавающий CTA ── */
  useLayoutEffect(() => {
    const sc = scrollerRef.current;
    if (!sc) return;
    const cta = ctaRef.current;
    const pad = cta ? cta.offsetHeight + 12 : selectedSlot ? 0 : 90;
    sc.style.paddingBottom = pad + 'px';
  });

  /* ── Хендлеры ── */
  const selectDay = (key) => { setSelectedDay(key); setSelectedSlot(null); };
  const selectTrainer = (id) => { setSelectedTrainer(id); setSelectedSlot(null); scrollPendingRef.current = true; };
  const jumpDay = (key) => { setSelectedDay(key); setSelectedSlot(null); scrollPendingRef.current = true; };

  const openDetail = (id) => { setSheetContentId(id); setSheetOpen(true); };
  const closeDetail = () => setSheetOpen(false);
  const pickFromSheet = (tid, win) => {
    setSelectedTrainer(tid);
    if (win) { setSelectedDay(win.dayKey); setSelectedSlot(win.slot); }
    else setSelectedSlot(null);
    closeDetail();
    scrollPendingRef.current = true;
  };

  const onSlot = (s, busy) => {
    if (busy) {
      setShakeSlot(s);
      setTimeout(() => setShakeSlot((cur) => (cur === s ? null : cur)), 420);
      setTip((cur) => {
        if (cur && cur.slot === s) return cur;
        setTimeout(() => setTip((c) => (c && c.slot === s ? null : c)), 1800);
        return { slot: s, reason: busyReason(selectedTrainer, s) };
      });
      return;
    }
    setSelectedSlot(s);
  };

  const hideTabs = step !== 'pick' || !!selectedSlot;

  /* ──────────────── PICK ──────────────── */
  const renderPick = () => {
    const q = trainerQuery.toLowerCase().trim();
    const filtered = TRAINERS.filter((t) => {
      const matchQ = !q || t.name.toLowerCase().includes(q) || t.spec.toLowerCase().includes(q);
      let matchF = true;
      if (trainerFilter === 'top') matchF = t.rating >= 4.9;
      if (trainerFilter === 'cheap') matchF = t.price <= 2200;
      return matchQ && matchF;
    });

    const filterOpts = [
      { id: 'all', label: 'Все', count: TRAINERS.length },
      { id: 'top', label: '★ Топ', count: TRAINERS.filter((t) => t.rating >= 4.9).length },
      { id: 'cheap', label: 'До 2200 ₽', count: TRAINERS.filter((t) => t.price <= 2200).length },
    ];

    return (
      <div className="page">
        <div
          className="scroller no-sb"
          id="scroller"
          ref={scrollerRef}
          style={{ paddingTop: 54, paddingBottom: selectedSlot ? 0 : 90 }}
        >
          <div style={{ padding: '8px 20px 12px' }}>
            <div className="t-mini" style={{ color: 'var(--text-3)' }}>Запись</div>
            <div className="t-h1" style={{ marginTop: 4 }}>На индивидуальную тренировку</div>
          </div>

          <div style={{ padding: '12px 20px 8px' }} className="row-between">
            <div className="t-h3" style={{ fontSize: 15, color: 'var(--text-2)', fontWeight: 600 }}>
              <span style={{ color: 'var(--text-3)', marginRight: 8 }}>1</span>Когда удобно
            </div>
            <div className="t-mini" style={{ color: 'var(--text-3)', textTransform: 'none', letterSpacing: 0, fontWeight: 600, fontSize: 12 }}>
              {monthFull(day.month)}
            </div>
          </div>
          <div className="no-sb" style={{ overflowX: 'auto', overflowY: 'hidden', paddingBottom: 4 }}>
            <div style={{ display: 'grid', gridTemplateColumns: `repeat(${CALENDAR.length},60px)`, gap: 8, padding: '4px 20px 8px' }}>
              {CALENDAR.map((d) => (
                <button
                  key={d.key}
                  disabled={!d.hasSlot}
                  onClick={() => d.hasSlot && selectDay(d.key)}
                  className={`cal-day ${selectedDay === d.key ? 'selected' : ''} ${d.hasSlot ? 'has-slot' : 'disabled'}`}
                >
                  <span className="dow">{d.isToday ? 'Сег' : d.dow}</span>
                  <span className="num">{d.num}</span>
                </button>
              ))}
            </div>
          </div>

          <div style={{ padding: '20px 20px 8px' }}>
            <div className="t-h3" style={{ fontSize: 15, color: 'var(--text-2)', fontWeight: 600 }}>
              <span style={{ color: 'var(--text-3)', marginRight: 8 }}>2</span>Свободные тренеры
            </div>
          </div>
          <div style={{ padding: '4px 16px 6px' }}>
            <div style={{ display: 'flex', alignItems: 'center', gap: 10, background: 'var(--surface)', borderRadius: 'var(--r-pill)', border: '0.5px solid var(--border)', padding: '0 14px', height: 44 }}>
              <Ico name="search" size={18} color="var(--text-3)" sw={1.8} />
              <input
                type="text"
                autoComplete="off"
                spellCheck="false"
                placeholder="Имя или специализация"
                value={trainerQuery}
                onChange={(e) => setTrainerQuery(e.target.value)}
                style={{ flex: 1, border: 0, outline: 'none', background: 'transparent', color: 'var(--text)', fontSize: 15 }}
              />
              {trainerQuery && (
                <button
                  onClick={() => setTrainerQuery('')}
                  style={{ width: 22, height: 22, borderRadius: 999, border: 0, background: 'var(--surface-2)', color: 'var(--text-2)', display: 'flex', alignItems: 'center', justifyContent: 'center', cursor: 'pointer', padding: 0 }}
                >
                  <svg width="10" height="10" viewBox="0 0 24 24">
                    <path d="M6 6l12 12M18 6L6 18" stroke="currentColor" strokeWidth="3" strokeLinecap="round" />
                  </svg>
                </button>
              )}
            </div>
          </div>
          <div className="no-sb" style={{ padding: '4px 16px 8px', display: 'flex', gap: 8, overflowX: 'auto' }}>
            {filterOpts.map((o) => {
              const active = trainerFilter === o.id;
              return (
                <button
                  key={o.id}
                  className="press"
                  onClick={() => setTrainerFilter(o.id)}
                  style={{
                    flexShrink: 0, padding: '7px 13px', fontSize: 13, fontWeight: 500,
                    border: `0.5px solid ${active ? 'var(--text)' : 'var(--border-strong)'}`,
                    background: active ? 'var(--text)' : 'transparent',
                    color: active ? 'var(--bg)' : 'var(--text-2)',
                    borderRadius: 999, cursor: 'pointer', display: 'flex', alignItems: 'center', gap: 6,
                    transition: 'background .15s,color .15s',
                  }}
                >
                  {o.label}
                  <span style={{ fontSize: 11, fontWeight: 600, background: active ? 'rgba(255,255,255,0.18)' : 'var(--surface-2)', color: active ? 'var(--bg)' : 'var(--text-3)', padding: '0 6px', height: 16, borderRadius: 999, lineHeight: '16px' }}>
                    {o.count}
                  </span>
                </button>
              );
            })}
          </div>

          <div className="stack-2" style={{ padding: '4px 16px 4px' }}>
            {filtered.length === 0 ? (
              <div className="card" style={{ padding: '28px 20px', textAlign: 'center' }}>
                <div style={{ width: 48, height: 48, borderRadius: 999, margin: '0 auto 12px', background: 'var(--surface-2)', display: 'flex', alignItems: 'center', justifyContent: 'center' }}>
                  <Ico name="search" size={22} color="var(--text-3)" sw={1.8} />
                </div>
                <div className="t-h3" style={{ fontSize: 15 }}>Никто не подошёл</div>
                <div className="t-small" style={{ marginTop: 4 }}>Попробуй другой запрос или сними фильтр.</div>
                <button
                  className="press"
                  onClick={() => { setTrainerQuery(''); setTrainerFilter('all'); }}
                  style={{ marginTop: 14, padding: '8px 16px', fontSize: 13, fontWeight: 600, border: '0.5px solid var(--border-strong)', background: 'transparent', color: 'var(--text)', borderRadius: 999, cursor: 'pointer' }}
                >
                  Сбросить
                </button>
              </div>
            ) : (
              filtered.map((t) => {
                const isSel = selectedTrainer === t.id;
                return (
                  <div
                    key={t.id}
                    className="press"
                    onClick={() => selectTrainer(t.id)}
                    style={{ cursor: 'pointer', background: 'var(--surface)', borderRadius: 'var(--r-lg)', outline: isSel ? '2px solid var(--text)' : '0.5px solid var(--border)', outlineOffset: isSel ? '-2px' : '0' }}
                  >
                    <div style={{ padding: 14, display: 'flex', gap: 12, alignItems: 'center' }}>
                      <Avatar t={t} size={48} />
                      <div style={{ flex: 1, minWidth: 0 }}>
                        <div className="row-between">
                          <div className="t-h3">{t.name}</div>
                          <div className="row" style={{ gap: 3 }}>
                            <Ico name="starFill" size={14} />
                            <span className="t-small" style={{ color: 'var(--text)', fontWeight: 600 }}>{t.rating}</span>
                          </div>
                        </div>
                        <div className="t-small" style={{ marginTop: 2 }}>{t.spec}</div>
                        <div className="row-between" style={{ marginTop: 8, gap: 8 }}>
                          <div className="row" style={{ gap: 8 }}>
                            <span className="chip" style={{ height: 22, fontSize: 11.5, padding: '0 9px' }}>{t.exp}</span>
                            <span className="t-small" style={{ color: 'var(--text-2)', fontWeight: 600 }}>{fmt(t.price)} ₽</span>
                          </div>
                          <button
                            onClick={(e) => { e.stopPropagation(); openDetail(t.id); }}
                            style={{ appearance: 'none', border: '0.5px solid var(--border-strong)', background: 'transparent', cursor: 'pointer', height: 26, padding: '0 10px', borderRadius: 999, fontSize: 12, fontWeight: 600, color: 'var(--text-2)', display: 'flex', alignItems: 'center', gap: 4 }}
                          >
                            Подробнее
                          </button>
                        </div>
                      </div>
                    </div>
                  </div>
                );
              })
            )}
          </div>

          {trainer && renderTimeBlock()}
        </div>

        {selectedSlot && trainer && renderCta()}
      </div>
    );
  };

  const renderTimeBlock = () => {
    const busyList = busyForDay(selectedTrainer, selectedDay);
    const fullyBooked = busyList.length >= TIME_SLOTS.length;

    return (
      <div className="fade-up" id="timeStep" ref={timeStepRef}>
        {/* Длительность */}
        <div style={{ padding: '14px 16px 4px' }}>
          <div className="row-between" style={{ marginBottom: 8 }}>
            <div className="t-h3" style={{ fontSize: 15, color: 'var(--text-2)', fontWeight: 600 }}>
              <span style={{ color: 'var(--text-3)', marginRight: 8 }}>3</span>Длительность
            </div>
            <div className="t-small" style={{ fontSize: 12, color: 'var(--accent-deep)', fontWeight: 600 }}>{fmt(priceFor(trainer))} ₽</div>
          </div>
          <div style={{ display: 'flex', gap: 2, padding: 3, background: 'var(--surface-2)', border: '0.5px solid var(--border)', borderRadius: 999 }}>
            {DURATIONS.map((d) => {
              const active = duration === d.id;
              return (
                <button
                  key={d.id}
                  onClick={() => setDuration(d.id)}
                  style={{
                    flex: 1, appearance: 'none', border: 0,
                    background: active ? 'var(--text)' : 'transparent',
                    color: active ? 'var(--bg)' : 'var(--text-2)',
                    height: 32, borderRadius: 999, fontFamily: 'inherit', fontSize: 12.5, fontWeight: 600, cursor: 'pointer',
                    transition: 'background .15s,color .15s',
                    boxShadow: active ? '0 1px 4px rgba(0,0,0,0.18)' : 'none',
                  }}
                >
                  {d.label}
                </button>
              );
            })}
          </div>
        </div>

        <div style={{ padding: '18px 20px 8px' }}>
          <div className="t-h3" style={{ fontSize: 15, color: 'var(--text-2)', fontWeight: 600 }}>
            <span style={{ color: 'var(--text-3)', marginRight: 8 }}>4</span>Свободное время
          </div>
          <div className="t-small" style={{ marginTop: 2 }}>{trainer.name.split(' ')[0]} · {day.dow}, {day.num} {monthName(day.month)}</div>
        </div>

        {fullyBooked ? renderFullyBooked() : renderPeriods(busyList)}
      </div>
    );
  };

  const renderFullyBooked = () => {
    const near = nearestAvailableDay(selectedTrainer, selectedDay);
    return (
      <div style={{ padding: '10px 16px 0' }}>
        <div className="card" style={{ padding: '24px 20px', textAlign: 'center' }}>
          <div style={{ width: 48, height: 48, borderRadius: 999, margin: '0 auto 12px', background: 'var(--surface-2)', display: 'flex', alignItems: 'center', justifyContent: 'center' }}>
            <Ico name="calendar" size={22} color="var(--text-3)" sw={1.8} />
          </div>
          <div className="t-h3" style={{ fontSize: 15 }}>В этот день всё занято</div>
          <div className="t-small" style={{ marginTop: 4 }}>
            У {trainer.name.split(' ')[0]} на {day.dow}, {day.num} {monthName(day.month)} свободных окон нет.
          </div>
          {near ? (
            <button
              className="press"
              onClick={() => jumpDay(near.key)}
              style={{ marginTop: 16, display: 'inline-flex', alignItems: 'center', gap: 6, padding: '10px 16px', fontSize: 13, fontWeight: 600, border: 0, background: 'var(--accent)', color: '#06120c', borderRadius: 999, cursor: 'pointer' }}
            >
              Ближайшее окно · {near.dow}, {near.num} {monthName(near.month)} <Ico name="arrowRight" size={14} color="#06120c" sw={2} />
            </button>
          ) : (
            <div className="t-small" style={{ marginTop: 14, color: 'var(--text-3)' }}>Свободных дней пока нет — попробуй другого тренера.</div>
          )}
        </div>
      </div>
    );
  };

  const renderPeriods = (busyList) =>
    PERIODS.map((p) => {
      const slots = TIME_SLOTS.filter((s) => { const h = parseInt(s, 10); return h >= p.range[0] && h < p.range[1]; });
      if (!slots.length) return null;
      const freeCount = slots.filter((s) => !busyList.includes(s)).length;
      const allBusy = freeCount === 0;
      return (
        <div key={p.id} style={{ padding: '10px 16px 0' }}>
          <div className="period-card" data-empty={allBusy ? 'true' : 'false'}>
            <div className="period-card__head">
              <Ico name={p.icon} size={16} color="var(--text-2)" sw={1.8} />
              <div className="t-h3" style={{ fontSize: 13, fontWeight: 700, letterSpacing: '0.3px', textTransform: 'uppercase' }}>{p.label}</div>
              <div className="t-mini" style={{ color: 'var(--text-3)', flex: 1, textTransform: 'none', letterSpacing: 0 }}>{p.hint}</div>
              <div className="t-mini" style={{ color: allBusy ? 'var(--text-3)' : 'var(--accent-deep)', fontVariantNumeric: 'tabular-nums', fontWeight: 600, textTransform: 'none', letterSpacing: 0 }}>{freeCount} свободно</div>
            </div>
            <div className="period-card__grid">
              {slots.map((s) => {
                const busy = busyList.includes(s);
                const sel = selectedSlot === s;
                return (
                  <div key={s} style={{ position: 'relative' }}>
                    <button
                      type="button"
                      onClick={() => onSlot(s, busy)}
                      aria-disabled={busy}
                      className={`slot-chip ${sel ? 'selected' : ''} ${busy ? 'busy' : ''} ${shakeSlot === s ? 'shake' : ''}`}
                    >
                      {s}
                    </button>
                    {tip && tip.slot === s && (
                      <div className="slot-tip">
                        {tip.reason}
                        <span className="slot-tip-arrow" />
                      </div>
                    )}
                  </div>
                );
              })}
            </div>
          </div>
        </div>
      );
    });

  const renderCta = () => {
    const end = addMinutes(selectedSlot, duration);
    return (
      <div className="cta-bar" ref={ctaRef}>
        <div className="book-summary fade-up">
          <Avatar t={trainer} size={38} />
          <div style={{ flex: 1, minWidth: 0 }}>
            <div className="t-h3" style={{ fontSize: 14, whiteSpace: 'nowrap', overflow: 'hidden', textOverflow: 'ellipsis' }}>{trainer.name}</div>
            <div className="t-small" style={{ fontSize: 12, marginTop: 2, display: 'flex', alignItems: 'center', gap: 6, color: 'var(--text-2)', whiteSpace: 'nowrap', overflow: 'hidden', textOverflow: 'ellipsis' }}>
              <span>{day.dow}, {day.num} {monthName(day.month)}</span>
              <span style={{ width: 3, height: 3, borderRadius: 999, background: 'var(--text-3)', flexShrink: 0 }} />
              <span className="t-num">{selectedSlot}–{end}</span>
            </div>
          </div>
          <div style={{ textAlign: 'right', flexShrink: 0 }}>
            <div className="t-num" style={{ fontSize: 17, fontWeight: 700, letterSpacing: '-0.3px', color: 'var(--text)' }}>{fmt(priceFor(trainer))} ₽</div>
            <div className="t-small" style={{ fontSize: 11.5, marginTop: 1, color: 'var(--text-3)' }}>{durObj.short}</div>
          </div>
        </div>
        <button className="btn btn-accent fade-up" onClick={() => setStep('confirm')} style={{ width: '100%', height: 54, marginTop: 10 }}>
          Продолжить
        </button>
      </div>
    );
  };

  /* ──────────────── REVIEW ──────────────── */
  const RiRow = ({ iconName, label, value, sub, avatarNode }) => (
    <div className="rowitem">
      {avatarNode || <div className="ri-ico"><Ico name={iconName} size={18} color="var(--text-2)" sw={1.8} /></div>}
      <div style={{ flex: 1, minWidth: 0 }}>
        <div className="t-small" style={{ color: 'var(--text-3)', fontSize: 12 }}>{label}</div>
        <div className="t-h3" style={{ fontSize: 15, marginTop: 1 }}>{value}</div>
        {sub && <div className="t-small" style={{ fontSize: 12, marginTop: 1 }}>{sub}</div>}
      </div>
    </div>
  );

  const renderReview = () => (
    <div className="page">
      <div style={{ padding: '54px 16px 0' }}>
        <button
          onClick={() => setStep('pick')}
          style={{ width: 40, height: 40, borderRadius: 999, border: '0.5px solid var(--border-strong)', background: 'var(--surface)', cursor: 'pointer', display: 'flex', alignItems: 'center', justifyContent: 'center' }}
        >
          <Ico name="chevronLeft" size={20} color="var(--text)" sw={2} />
        </button>
      </div>
      <div className="scroller no-sb">
        <div style={{ padding: '20px 20px 12px' }}>
          <div className="t-mini" style={{ color: 'var(--text-3)' }}>Подтверждение</div>
          <div className="t-h1" style={{ marginTop: 4 }}>Проверь детали</div>
        </div>
        <div style={{ padding: '12px 16px' }}>
          <div className="card" style={{ padding: 4 }}>
            <RiRow iconName="user" label="Тренер" value={trainer.name} sub={trainer.spec} avatarNode={<div style={{ marginLeft: 0 }}><Avatar t={trainer} size={36} /></div>} />
            <div className="divider" />
            <RiRow iconName="calendar" label="Дата" value={`${day.dow}, ${day.num} ${monthName(day.month)}`} />
            <div className="divider" />
            <RiRow iconName="clock" label="Время" value={`${selectedSlot} – ${addMinutes(selectedSlot, duration)}`} sub={durObj.label} />
            <div className="divider" />
            <RiRow iconName="card" label="К оплате" value={`${fmt(priceFor(trainer))} ₽`} sub="спишется с привязанной карты" />
          </div>
        </div>
        <div style={{ padding: '8px 20px 0' }}>
          <div className="t-small" style={{ color: 'var(--text-2)', lineHeight: 1.5 }}>
            Отменить запись бесплатно можно не позднее, чем за 6 часов до начала тренировки. Позже — спишется 50% стоимости.
          </div>
        </div>
        <div style={{ height: 120 }} />
      </div>
      <div className="cta-bar">
        <button
          className="btn btn-accent"
          onClick={() => { toast('Оплата прошла · записываем'); setTimeout(() => setStep('done'), 1200); }}
          style={{ width: '100%', height: 54 }}
        >
          Подтвердить запись
        </button>
      </div>
    </div>
  );

  /* ──────────────── DONE ──────────────── */
  const renderDone = () => (
    <div className="page">
      <div className="scroller no-sb" style={{ paddingTop: 64 }}>
        <div style={{ padding: '20px 20px 0', display: 'flex', flexDirection: 'column', alignItems: 'center' }}>
          <div className="scale-in" style={{ width: 76, height: 76, borderRadius: 999, background: 'var(--accent)', display: 'flex', alignItems: 'center', justifyContent: 'center', boxShadow: '0 8px 24px var(--accent-soft)' }}>
            <Ico name="check" size={40} color="#06120c" sw={2.5} />
          </div>
          <div className="t-display" style={{ marginTop: 24, textAlign: 'center', letterSpacing: '-0.8px' }}>Записан!</div>
          <div className="t-body" style={{ color: 'var(--text-2)', marginTop: 6, textAlign: 'center', maxWidth: 280 }}>Напомним за час и за 15 минут до тренировки.</div>
        </div>
        <div style={{ padding: '28px 16px 12px' }}>
          <div className="card" style={{ padding: 4 }}>
            <RiRow iconName="user" label="Тренер" value={trainer.name} sub={trainer.spec} avatarNode={<div><Avatar t={trainer} size={36} /></div>} />
            <div className="divider" />
            <RiRow iconName="calendar" label="Когда" value={`${day.dow}, ${day.num} ${monthName(day.month)}, ${selectedSlot}`} sub={durObj.label} />
          </div>
        </div>
        <div style={{ padding: '8px 16px', display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 10 }}>
          <button className="btn btn-ghost" onClick={() => toast('Добавлено в календарь')} style={{ height: 48 }}>В календарь</button>
          <button className="btn btn-ghost" onClick={() => toast('Управление записью')} style={{ height: 48 }}>Управлять записью</button>
        </div>
        <div style={{ height: 120 }} />
      </div>
      <div className="cta-bar">
        <button className="btn btn-accent" onClick={() => { window.location.href = 'Home.html'; }} style={{ width: '100%', height: 54 }}>Готово</button>
        <button
          className="btn btn-soft"
          onClick={() => { setStep('pick'); setSelectedTrainer(null); setSelectedSlot(null); }}
          style={{ width: '100%', height: 44, marginTop: 8, background: 'transparent', color: 'var(--text-2)' }}
        >
          Записаться ещё
        </button>
      </div>
    </div>
  );

  /* ──────────────── Detail sheet content ──────────────── */
  const sheetTrainer = TRAINERS.find((t) => t.id === sheetContentId) || null;
  const renderDetail = () => {
    const t = sheetTrainer;
    const wins = nextWindows(t.id, 3);
    return (
      <>
        <div style={{ padding: '6px 20px 4px', display: 'flex', gap: 14, alignItems: 'center' }}>
          <Avatar t={t} size={60} />
          <div style={{ flex: 1, minWidth: 0 }}>
            <div className="t-h1" style={{ fontSize: 22 }}>{t.name}</div>
            <div className="t-small" style={{ marginTop: 3 }}>{t.spec}</div>
          </div>
          <button
            aria-label="Закрыть"
            onClick={closeDetail}
            style={{ width: 34, height: 34, borderRadius: 999, border: '0.5px solid var(--border-strong)', background: 'var(--surface-2)', cursor: 'pointer', display: 'flex', alignItems: 'center', justifyContent: 'center', flexShrink: 0 }}
          >
            <svg width="14" height="14" viewBox="0 0 24 24">
              <path d="M6 6l12 12M18 6L6 18" stroke="var(--text-2)" strokeWidth="2.4" strokeLinecap="round" />
            </svg>
          </button>
        </div>

        <div style={{ padding: '14px 20px 4px', display: 'flex', gap: 8, flexWrap: 'wrap' }}>
          <span className="chip" style={{ gap: 5 }}>
            <Ico name="starFill" size={13} />
            <b style={{ color: 'var(--text)' }}>{t.rating}</b>
          </span>
          <span className="chip">{t.exp} опыта</span>
          <span className="chip" style={{ color: 'var(--text)', fontWeight: 600 }}>от {fmt(t.price)} ₽ / час</span>
        </div>

        <div style={{ padding: '12px 20px 4px' }}>
          <div className="t-body" style={{ color: 'var(--text-2)', lineHeight: 1.5 }}>{TRAINER_BIOS[t.id] || ''}</div>
        </div>

        <div style={{ padding: '14px 20px 6px' }}>
          <div className="t-mini" style={{ color: 'var(--text-3)' }}>Ближайшие окна</div>
        </div>
        <div className="card" style={{ margin: '0 16px', padding: 0, overflow: 'hidden' }}>
          {wins.length ? (
            wins.map((w, i) => (
              <Fragment key={`${w.day.key}|${w.slot}`}>
                {i > 0 && <div style={{ height: 0.5, background: 'var(--border)', marginLeft: 66 }} />}
                <button
                  className="press"
                  onClick={() => pickFromSheet(t.id, { dayKey: w.day.key, slot: w.slot })}
                  style={{ width: '100%', textAlign: 'left', border: 0, background: 'transparent', cursor: 'pointer', padding: '11px 20px', display: 'flex', alignItems: 'center', gap: 12 }}
                >
                  <div style={{ width: 34, height: 34, borderRadius: 999, flexShrink: 0, background: 'var(--accent-soft)', display: 'flex', alignItems: 'center', justifyContent: 'center' }}>
                    <Ico name="clock" size={16} color="var(--accent-deep)" sw={2} />
                  </div>
                  <div style={{ flex: 1, minWidth: 0 }}>
                    <div className="t-h3" style={{ fontSize: 14 }}>{w.day.dow}, {w.day.num} {monthName(w.day.month)}</div>
                    <div className="t-small" style={{ fontSize: 12, marginTop: 1 }}>ближайшее окно</div>
                  </div>
                  <span className="chip chip-accent" style={{ height: 26, background: 'var(--accent)', color: '#06120c', border: 0, fontWeight: 600 }}>{w.slot}</span>
                </button>
              </Fragment>
            ))
          ) : (
            <div className="t-small" style={{ padding: '16px 20px', color: 'var(--text-3)' }}>Свободных окон пока нет.</div>
          )}
        </div>

        <div style={{ padding: '18px 16px 20px' }}>
          <button className="btn btn-accent" onClick={() => pickFromSheet(t.id, null)} style={{ width: '100%', height: 52 }}>Выбрать тренера</button>
        </div>
      </>
    );
  };

  return (
    <>
      <style>{CSS}</style>
      <div className="stage">
        <div className="device" data-screen-label="Запись">
          <div className="device-inner">
            <div className="island" />

            <div className="status-bar" aria-hidden="true">
              <span>9:41</span>
              <div className="glyphs">
                <svg width="17" height="11" viewBox="0 0 17 11">
                  <rect x="0" y="7" width="3" height="4" rx="0.5" fill="currentColor" />
                  <rect x="4.5" y="5" width="3" height="6" rx="0.5" fill="currentColor" />
                  <rect x="9" y="2.5" width="3" height="8.5" rx="0.5" fill="currentColor" />
                  <rect x="13.5" y="0" width="3" height="11" rx="0.5" fill="currentColor" />
                </svg>
                <svg width="24" height="11" viewBox="0 0 24 11">
                  <rect x="0.5" y="0.5" width="20" height="10" rx="3" stroke="currentColor" strokeOpacity="0.4" fill="none" />
                  <rect x="2" y="2" width="17" height="7" rx="1.5" fill="currentColor" />
                  <rect x="21" y="3.5" width="1.5" height="4" rx="0.5" fill="currentColor" fillOpacity="0.4" />
                </svg>
              </div>
            </div>

            <div className="screen">
              <div id="app">
                {step === 'confirm' ? renderReview() : step === 'done' ? renderDone() : renderPick()}
              </div>

              {/* Bottom tab bar */}
              <div className={'tabbar' + (hideTabs ? ' hidden' : '')} role="tablist" aria-label="Основная навигация">
                <button className="tabbar-item" data-go="Home.html" type="button">
                  <svg width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.7" strokeLinejoin="round"><path d="M3 11l9-7 9 7v9a1 1 0 01-1 1h-5v-7h-6v7H4a1 1 0 01-1-1v-9z" /></svg>
                  <span>Главная</span>
                </button>
                <button className="tabbar-item active" type="button" aria-selected="true">
                  <svg width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.9" strokeLinecap="round"><rect x="3" y="5" width="18" height="16" rx="3" /><path d="M3 10h18M8 3v4M16 3v4" /></svg>
                  <span>Запись</span>
                </button>
                <button className="tabbar-item" data-toast="Чат с залом" type="button">
                  <svg width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.7" strokeLinejoin="round"><path d="M4 5a2 2 0 012-2h12a2 2 0 012 2v9a2 2 0 01-2 2h-7l-4 4v-4H6a2 2 0 01-2-2V5z" /></svg>
                  <span>Чат</span>
                </button>
                <button className="tabbar-item" data-go="Profile.html" type="button">
                  <svg width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.7" strokeLinecap="round"><circle cx="12" cy="8" r="4" /><path d="M4 21c0-4 4-7 8-7s8 3 8 7" /></svg>
                  <span>Профиль</span>
                </button>
              </div>

              <div className="home-indicator" />
              <div className={'toast' + (toastShow ? ' show' : '')}>{toastMsg}</div>

              {/* Trainer detail sheet */}
              <div
                className={'sheet-scrim' + (sheetOpen ? ' open' : '')}
                onClick={(e) => { if (e.target === e.currentTarget) closeDetail(); }}
              >
                <div className="sheet" role="dialog" aria-modal="true">
                  <div className="sheet-handle" />
                  <div className="no-sb" style={{ overflowY: 'auto', padding: '8px 0 0' }}>
                    {sheetTrainer && renderDetail()}
                  </div>
                </div>
              </div>
            </div>
          </div>
        </div>
      </div>
    </>
  );
}

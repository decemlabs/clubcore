import { useCallback, useEffect, useRef, useState, Fragment } from 'react';

/* ============================================================
   Экран «Уведомления» — точный перенос Notifications.html.
   Самодостаточный компонент: содержит свои стили, данные,
   устройство-рамку и всю интерактивную логику.
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
.t-num { font-variant-numeric: tabular-nums; }
.t-mini { font-size: 11px; font-weight: 600; letter-spacing: 0.5px; text-transform: uppercase; color: var(--text-3); }
.t-small { font-size: 13px; font-weight: 400; line-height: 1.4; color: var(--text-2); }
.t-h3 { font-size: 17px; font-weight: 600; letter-spacing: -0.2px; line-height: 1.25; color: var(--text); }
.row { display: flex; align-items: center; gap: 12px; }
.row-between { display: flex; align-items: center; justify-content: space-between; gap: 12px; }

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
  animation: screen-push 0.34s cubic-bezier(0.32,0.72,0.2,1);
}
@keyframes screen-push { from { transform: translateX(40px); opacity: 0; } to { transform: translateX(0); opacity: 1; } }

/* Header */
.nav {
  position: relative; flex-shrink: 0;
  padding: 50px 12px 8px;
  display: grid; grid-template-columns: 1fr auto 1fr; align-items: center; gap: 6px;
}
.nav > .icon-btn:first-child { justify-self: start; }
.nav-title {
  display: flex; align-items: center; justify-content: center;
  font-size: 15px; white-space: nowrap;
}
.icon-btn {
  width: 36px; height: 36px; border-radius: 999px; border: 0;
  background: var(--surface); cursor: pointer; padding: 0;
  display: flex; align-items: center; justify-content: center;
}
.nav-right { display: flex; align-items: center; gap: 2px; justify-self: end; }
.nav-action {
  border: 0; background: transparent; font-family: inherit;
  font-size: 13px; font-weight: 600; padding: 6px 8px; cursor: pointer;
  color: var(--text); border-radius: 999px; white-space: nowrap;
}
.nav-action:disabled { color: var(--text-3); cursor: default; }

/* Segmented control */
.seg {
  display: flex; gap: 2px; padding: 3px;
  background: var(--surface-2);
  border: 0.5px solid var(--border);
  border-radius: 999px;
}
.seg-item {
  appearance: none; border: 0; background: transparent; cursor: pointer;
  height: 32px; border-radius: 999px;
  font-family: inherit; font-size: 12.5px; font-weight: 600;
  color: var(--text-2);
  transition: background 0.15s, color 0.15s, box-shadow 0.15s;
}
.seg-item.active {
  background: var(--text); color: var(--bg);
  box-shadow: 0 1px 4px rgba(0,0,0,0.18);
}

/* Scroll body */
.scroller {
  flex: 1; overflow-y: auto; -webkit-overflow-scrolling: touch;
  position: relative;
}
.scroller::-webkit-scrollbar { display: none; }

/* Pull to refresh */
.ptr {
  position: absolute; top: 0; left: 0; right: 0; height: 46px;
  display: flex; align-items: center; justify-content: center;
  opacity: 0; pointer-events: none; z-index: 0;
}
.ptr svg { color: var(--text-3); }
.ptr.spin svg { animation: ptr-spin 0.7s linear infinite; }
@keyframes ptr-spin { to { transform: rotate(360deg); } }

.card {
  background: var(--surface);
  border: 0.5px solid var(--border);
  border-radius: var(--r-lg);
  box-shadow: var(--sh-1);
}

.press { transition: transform 0.1s ease, background 0.15s ease; cursor: pointer; }
.press:active { transform: scale(0.985); }

/* Notification list */
.list { position: relative; display: flex; flex-direction: column; padding: 0 16px 24px; }

.group-head {
  padding: 11px 4px 6px;
  display: flex; align-items: center; gap: 8px;
}
.group-head .gh-count { color: var(--text-3); font-weight: 600; }

.swipe {
  position: relative; border-radius: 16px; overflow: hidden;
  margin-bottom: 6px;
}
.swipe-action {
  position: absolute; inset: 0;
  background: transparent;
  display: flex; align-items: center; justify-content: flex-end;
  gap: 7px; padding-right: 22px;
  color: #fff; font-size: 13.5px; font-weight: 700;
  opacity: 0; transition: opacity 0.15s ease;
}
.swipe.armed .swipe-action { background: var(--danger); opacity: 1; }
.swipe-card {
  position: relative; z-index: 1;
  display: block; width: 100%; text-align: left;
  border-radius: 16px;
  background: var(--surface-2);
  border: 0.5px solid var(--border);
  color: var(--text);
  padding: 11px 13px;
  cursor: pointer; touch-action: pan-y;
  transition: transform 0.26s cubic-bezier(0.32,0.72,0.2,1);
  -webkit-user-select: none; user-select: none;
}
.swipe-card.unread {
  background: var(--surface);
  border-color: var(--border-strong);
}
.swipe-card.removing {
  transition: transform 0.26s ease, opacity 0.26s ease;
}

.n-row { display: flex; gap: 11px; align-items: flex-start; }
.n-ic {
  width: 34px; height: 34px; border-radius: 10px; flex-shrink: 0; margin-top: 1px;
  display: flex; align-items: center; justify-content: center;
}
.n-main { flex: 1; min-width: 0; }
.n-top { display: flex; align-items: center; gap: 7px; }
.n-title {
  flex: 1; min-width: 0;
  font-size: 14.5px; font-weight: 600; letter-spacing: -0.2px; line-height: 1.3; color: var(--text);
  white-space: nowrap; overflow: hidden; text-overflow: ellipsis;
}
.n-dot { width: 7px; height: 7px; border-radius: 999px; background: var(--accent); flex-shrink: 0; }
.n-body {
  margin-top: 2px; font-size: 12.5px; line-height: 1.35; color: var(--text-2);
  display: -webkit-box; -webkit-line-clamp: 2; -webkit-box-orient: vertical; overflow: hidden;
}
.n-meta { margin-top: 8px; }
.n-time { font-size: 11px; font-weight: 600; letter-spacing: 0.2px; color: var(--text-3); flex-shrink: 0; }
.n-act {
  display: inline-flex; align-items: center; gap: 5px; height: 26px; padding: 0 12px;
  border-radius: 999px; border: 0.5px solid color-mix(in oklab, var(--accent) 45%, transparent);
  background: color-mix(in oklab, var(--accent) 12%, transparent);
  color: var(--accent-deep); font-family: inherit; font-size: 12px; font-weight: 700;
  cursor: pointer; flex-shrink: 0;
}
.n-chev { display: inline-flex; flex-shrink: 0; color: var(--text-3); }

.empty {
  margin: 4px 0; padding: 40px 24px;
  display: flex; flex-direction: column; align-items: center; text-align: center; gap: 8px;
}
.empty-ic {
  width: 56px; height: 56px; border-radius: 16px; margin-bottom: 6px;
  background: var(--accent-soft);
  display: flex; align-items: center; justify-content: center;
}

.fade-up { animation: fade-up 0.32s cubic-bezier(0.32,0.72,0.2,1) both; }
@keyframes fade-up { from { opacity: 0; transform: translateY(8px); } to { opacity: 1; transform: translateY(0); } }

/* Long-press action sheet */
.sheet-backdrop {
  position: absolute; inset: 0; z-index: 80;
  background: rgba(0,0,0,0.32); opacity: 0; pointer-events: none;
  transition: opacity 0.25s ease;
}
.sheet-backdrop.show { opacity: 1; pointer-events: auto; }
.sheet {
  position: absolute; left: 8px; right: 8px; bottom: 8px; z-index: 81;
  background: var(--surface); border: 0.5px solid var(--border);
  border-radius: 24px; box-shadow: var(--sh-2); padding: 8px;
  transform: translateY(150%); transition: transform 0.34s cubic-bezier(0.32,0.72,0.2,1);
}
.sheet.show { transform: translateY(0); }
.sheet-title { padding: 12px 14px 6px; }
.sheet-btn {
  display: flex; align-items: center; gap: 12px; width: 100%;
  border: 0; background: transparent; font-family: inherit;
  font-size: 15px; font-weight: 600; color: var(--text);
  padding: 14px; border-radius: 14px; cursor: pointer; text-align: left;
}
.sheet-btn:hover { background: var(--surface-2); }
.sheet-btn.danger { color: var(--danger); }
.sheet-cancel { margin-top: 4px; justify-content: center; background: var(--surface-2); color: var(--text-2); }

/* Toast */
.toast {
  position: absolute; left: 50%; bottom: 40px; transform: translate(-50%, 16px);
  z-index: 90; background: var(--text); color: var(--bg);
  font-size: 13.5px; font-weight: 600; padding: 11px 18px; border-radius: 999px;
  box-shadow: 0 12px 30px rgba(0,0,0,0.28);
  opacity: 0; pointer-events: none;
  transition: opacity 0.22s ease, transform 0.28s cubic-bezier(0.32,0.72,0.2,1);
  white-space: nowrap;
}
.toast.show { opacity: 1; transform: translate(-50%, 0); }

.hidden { display: none !important; }
`;

/* ---------- Иконки ---------- */
const ICON = {
  tag: '<path d="M3 12V4a1 1 0 011-1h8l9 9-9 9-9-9z"/><circle cx="8" cy="8" r="1.4" fill="currentColor" stroke="none"/>',
  star: '<path d="M12 3l2.7 5.5 6.1.9-4.4 4.3 1 6.1L12 17l-5.4 2.8 1-6.1L3.2 9.4l6.1-.9L12 3z"/>',
  calendar: '<rect x="3" y="5" width="18" height="16" rx="3"/><path d="M3 10h18M8 3v4M16 3v4"/>',
  chat: '<path d="M4 5a2 2 0 012-2h12a2 2 0 012 2v9a2 2 0 01-2 2h-7l-4 4v-4H6a2 2 0 01-2-2V5z"/>',
  image: '<rect x="3" y="4" width="18" height="16" rx="3"/><circle cx="9" cy="10" r="2"/><path d="M21 16l-5-5-7 7"/>',
  info: '<circle cx="12" cy="12" r="9"/><path d="M12 11v5M12 7.5v.5"/>',
  trash: '<path d="M4 7h16M9 7V5a1 1 0 011-1h4a1 1 0 011 1v2M6 7l1 13a1 1 0 001 1h8a1 1 0 001-1l1-13"/>',
  sparkle: '<path d="M12 3l1.8 5.2L19 10l-5.2 1.8L12 17l-1.8-5.2L5 10l5.2-1.8L12 3z"/>',
  check: '<path d="M5 12l5 5L20 6"/>',
  chevron: '<path d="M9 6l6 6-6 6"/>',
  arrowRight: '<path d="M5 12h14M13 6l6 6-6 6"/>',
  bell: '<path d="M18 8a6 6 0 10-12 0c0 7-3 9-3 9h18s-3-2-3-9"/><path d="M13.7 21a2 2 0 01-3.4 0"/>',
};

function Ico({ name, size, color = 'currentColor', sw = 1.9 }) {
  return (
    <svg
      width={size}
      height={size}
      viewBox="0 0 24 24"
      fill="none"
      stroke={color}
      strokeWidth={sw}
      strokeLinecap="round"
      strokeLinejoin="round"
      dangerouslySetInnerHTML={{ __html: ICON[name] }}
    />
  );
}

/* Тон + иконка для каждого вида уведомления */
const TONES = {
  promo: 'oklch(0.60 0.13 162)',
  achievement: 'oklch(0.64 0.12 72)',
  schedule: 'oklch(0.62 0.14 42)',
  message: 'oklch(0.58 0.12 250)',
  news: 'oklch(0.56 0.13 300)',
  info: 'var(--text-3)',
};
const KIND_ICON = { promo: 'tag', achievement: 'star', schedule: 'calendar', message: 'chat', news: 'image', info: 'info' };
const soft = (c, p) => `color-mix(in oklab, ${c} ${p}%, var(--surface))`;

/* ---------- Данные ---------- */
const INITIAL_ITEMS = [
  { id: 'n1', kind: 'promo', title: 'Скидка 15% на годовой абонемент', body: 'Только до 5 мая. Оформи продление и получи бонусный месяц.', group: 'today', at: '10:24', unread: true, action: { label: 'Продлить', go: 'К оплате v2.html' } },
  { id: 'n5', kind: 'achievement', title: '50 тренировок за год', body: 'Ты в топ-10% активных в зале. Так держать!', group: 'today', at: '08:00', unread: true },
  { id: 'n2', kind: 'schedule', title: 'Йога утром перенесена', body: 'С 7 мая утренняя йога будет в 8:30 вместо 9:00.', group: 'yesterday', at: '19:05', unread: true },
  { id: 'n3', kind: 'message', title: 'Аня Соколова', body: 'Не забудь взять ремни для тяги — пригодятся.', group: 'earlier', at: '28 апр', unread: false, tappable: true },
  { id: 'n4', kind: 'info', title: 'Сауна закрыта 1 мая', body: 'В праздничный день сауна не работает. Зал — обычный график.', group: 'earlier', at: '27 апр', unread: false },
  { id: 'n6', kind: 'news', title: 'Новая зона функционального тренинга', body: 'Рама, канаты и сани. Заходи опробовать на этой неделе.', group: 'earlier', at: '26 апр', unread: false },
];

const GROUPS = [
  { key: 'today', label: 'Сегодня' },
  { key: 'yesterday', label: 'Вчера' },
  { key: 'earlier', label: 'Ранее' },
];

export function NotificationsScreen() {
  const [items, setItems] = useState(INITIAL_ITEMS);
  const [filter, setFilter] = useState('all'); // 'all' | 'unread'

  // Toast
  const [toastMsg, setToastMsg] = useState('');
  const [toastShow, setToastShow] = useState(false);
  const toastTimer = useRef(null);

  // Action sheet
  const [sheetItemId, setSheetItemId] = useState(null);
  const [sheetShow, setSheetShow] = useState(false);
  const [backShow, setBackShow] = useState(false);

  // Refs
  const scrollerRef = useRef(null);
  const listRef = useRef(null);
  const ptrRef = useRef(null);
  const activeRef = useRef(null); // текущая жест-сессия для свайпа/long-press
  const pullRef = useRef({ pStart: null, pulling: false, loading: false, pull: 0 });
  const itemsRef = useRef(items);
  itemsRef.current = items;

  const unread = items.filter((n) => n.unread).length;

  /* ── Тема (общий ключ со всем приложением) ── */
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

  /* ── Мутации ── */
  const markRead = useCallback((id) => {
    setItems((prev) => prev.map((n) => (n.id === id && n.unread ? { ...n, unread: false } : n)));
  }, []);
  const toggleRead = useCallback((id) => {
    setItems((prev) => prev.map((n) => (n.id === id ? { ...n, unread: !n.unread } : n)));
  }, []);
  const removeItem = useCallback((id) => {
    setItems((prev) => prev.filter((n) => n.id !== id));
  }, []);
  const markAll = useCallback(() => {
    setItems((prev) => (prev.some((n) => n.unread) ? prev.map((n) => ({ ...n, unread: false })) : prev));
  }, []);

  const runCardTap = useCallback(
    (n) => {
      if (n.action && n.action.go) { window.location.href = n.action.go; return; }
      if (n.kind === 'message') { markRead(n.id); toast('Открываю чат с Аней…'); return; }
      markRead(n.id);
    },
    [markRead, toast]
  );

  /* ── Action sheet (long-press) ── */
  const openSheet = useCallback((id) => {
    setSheetItemId(id);
    setBackShow(true);
    requestAnimationFrame(() => setSheetShow(true));
  }, []);
  const closeSheet = useCallback(() => {
    setSheetShow(false);
    setBackShow(false);
  }, []);

  /* ── Глобальная навигация (data-go) ── */
  useEffect(() => {
    const onClick = (e) => {
      const el = e.target.closest('[data-go]');
      if (el && el.dataset.go) window.location.href = el.dataset.go;
    };
    document.addEventListener('click', onClick);
    return () => document.removeEventListener('click', onClick);
  }, []);

  /* ── Жесты карточки: document-level move / up / cancel ── */
  useEffect(() => {
    const onMove = (e) => {
      const a = activeRef.current;
      if (!a) return;
      const dx = e.clientX - a.x0;
      const dy = e.clientY - a.y0;
      if (Math.abs(dx) > 6 || Math.abs(dy) > 6) {
        a.moved = true;
        clearTimeout(a.timer);
      }
      if (Math.abs(dx) > Math.abs(dy)) {
        a.dx = dx;
        let t = Math.min(0, dx);
        if (t < -110) t = -110;
        a.wrap.classList.toggle('armed', t < 0);
        a.card.style.transform = 'translateX(' + t + 'px)';
      }
    };
    const onUp = () => {
      const a = activeRef.current;
      if (!a) return;
      activeRef.current = null;
      clearTimeout(a.timer);
      a.card.style.transition = '';

      if (a.dx <= -70) {
        a.card.classList.add('removing');
        a.card.style.transform = 'translateX(-110%)';
        setTimeout(() => removeItem(a.id), 240);
        return;
      }
      a.card.style.transform = 'translateX(0)';
      setTimeout(() => a.wrap.classList.remove('armed'), 180);

      if (!a.moved && !a.longFired) {
        const n = itemsRef.current.find((x) => x.id === a.id);
        if (n) runCardTap(n);
      }
    };
    const onCancel = () => {
      const a = activeRef.current;
      if (!a) return;
      activeRef.current = null;
      clearTimeout(a.timer);
      a.card.style.transition = '';
      a.card.style.transform = 'translateX(0)';
      setTimeout(() => a.wrap.classList.remove('armed'), 180);
    };
    document.addEventListener('pointermove', onMove);
    document.addEventListener('pointerup', onUp);
    document.addEventListener('pointercancel', onCancel);
    return () => {
      document.removeEventListener('pointermove', onMove);
      document.removeEventListener('pointerup', onUp);
      document.removeEventListener('pointercancel', onCancel);
    };
  }, [removeItem, runCardTap]);

  const onCardPointerDown = (e, id) => {
    if (e.button != null && e.button !== 0) return;
    const card = e.currentTarget;
    const wrap = card.closest('.swipe');
    activeRef.current = {
      wrap,
      card,
      id,
      x0: e.clientX,
      y0: e.clientY,
      dx: 0,
      moved: false,
      longFired: false,
      timer: setTimeout(() => {
        const a = activeRef.current;
        if (a && !a.moved) {
          a.longFired = true;
          if (navigator.vibrate) navigator.vibrate(8);
          openSheet(id);
        }
      }, 450),
    };
    card.style.transition = 'none';
  };

  const onActClick = (e, id) => {
    e.stopPropagation();
    const n = itemsRef.current.find((x) => x.id === id);
    if (n && n.action && n.action.go) window.location.href = n.action.go;
  };

  const onSwipeActionClick = (id) => {
    const wrap = listRef.current?.querySelector('.swipe[data-id="' + id + '"]');
    if (!wrap) return;
    const card = wrap.querySelector('.swipe-card');
    wrap.classList.add('armed');
    card.classList.add('removing');
    card.style.transform = 'translateX(-110%)';
    setTimeout(() => removeItem(id), 230);
  };

  /* ── Pull to refresh (на скроллере) ── */
  const onScrollerPointerDown = (e) => {
    const p = pullRef.current;
    const a = activeRef.current;
    if (p.loading || (a && a.moved)) return;
    const scroller = scrollerRef.current;
    if (scroller.scrollTop <= 0) {
      p.pStart = { x: e.clientX, y: e.clientY };
      p.pulling = true;
    }
  };
  const onScrollerPointerMove = (e) => {
    const p = pullRef.current;
    if (!p.pulling || p.loading || !p.pStart) return;
    const scroller = scrollerRef.current;
    const listEl = listRef.current;
    const ptr = ptrRef.current;
    const dy = e.clientY - p.pStart.y;
    const dx = e.clientX - p.pStart.x;
    if (dy <= 0 || Math.abs(dx) > Math.abs(dy)) return;
    if (scroller.scrollTop > 0) { p.pulling = false; return; }
    const pull = Math.min(64, dy * 0.5);
    listEl.style.transition = 'none';
    listEl.style.transform = 'translateY(' + pull + 'px)';
    ptr.style.opacity = Math.min(1, pull / 46);
    ptr.querySelector('svg').style.transform = 'rotate(' + pull * 5 + 'deg)';
    p.pull = pull;
  };
  const endPull = () => {
    const p = pullRef.current;
    if (!p.pulling) return;
    p.pulling = false;
    const pull = p.pull || 0;
    p.pull = 0;
    const listEl = listRef.current;
    const ptr = ptrRef.current;
    listEl.style.transition = 'transform 0.3s cubic-bezier(0.32,0.72,0.2,1)';
    if (pull >= 44) {
      p.loading = true;
      listEl.style.transform = 'translateY(44px)';
      ptr.classList.add('spin');
      ptr.style.opacity = 1;
      ptr.querySelector('svg').style.transform = '';
      setTimeout(() => {
        listEl.style.transform = 'translateY(0)';
        ptr.classList.remove('spin');
        ptr.style.opacity = 0;
        p.loading = false;
        toast('Обновлено');
      }, 850);
    } else {
      listEl.style.transform = 'translateY(0)';
      ptr.style.opacity = 0;
    }
  };

  /* ── Однократная подсказка-наджворд по свайпу ── */
  useEffect(() => {
    if (sessionStorage.getItem('notif_swipe_hint')) return;
    sessionStorage.setItem('notif_swipe_hint', '1');
    const t = setTimeout(() => {
      const first = listRef.current?.querySelector('.swipe');
      if (!first) return;
      const card = first.querySelector('.swipe-card');
      first.classList.add('armed');
      card.style.transition = 'transform 0.4s cubic-bezier(0.32,0.72,0.2,1)';
      card.style.transform = 'translateX(-46px)';
      setTimeout(() => {
        card.style.transform = 'translateX(0)';
        setTimeout(() => first.classList.remove('armed'), 360);
      }, 620);
    }, 700);
    return () => clearTimeout(t);
  }, []);

  /* ── Рендер карточки ── */
  const renderCard = (n) => {
    const c = TONES[n.kind] || TONES.info;
    return (
      <div className="swipe" data-id={n.id} key={n.id}>
        <div className="swipe-action" onClick={() => onSwipeActionClick(n.id)}>
          <Ico name="trash" size={17} color="#fff" sw={2} />
          Удалить
        </div>
        <div
          className={'swipe-card press' + (n.unread ? ' unread' : '')}
          data-id={n.id}
          role="button"
          tabIndex={0}
          onPointerDown={(e) => onCardPointerDown(e, n.id)}
        >
          <div className="n-row">
            <div className="n-ic" style={{ background: soft(c, 16) }}>
              <Ico name={KIND_ICON[n.kind] || 'info'} size={17} color={c} sw={1.9} />
            </div>
            <div className="n-main">
              <div className="n-top">
                <span className="n-title">{n.title}</span>
                {n.at && <span className="n-time t-num">{n.at}</span>}
                {n.unread && <span className="n-dot" />}
                {n.tappable && !n.action && (
                  <span className="n-chev">
                    <Ico name="chevron" size={15} color="var(--text-3)" sw={2} />
                  </span>
                )}
              </div>
              <div className="n-body">{n.body}</div>
              {n.action && (
                <div className="n-meta">
                  <button className="n-act" data-act={n.id} onClick={(e) => onActClick(e, n.id)}>
                    {n.action.label}{' '}
                    <Ico name="arrowRight" size={13} color="var(--accent-deep)" sw={2.2} />
                  </button>
                </div>
              )}
            </div>
          </div>
        </div>
      </div>
    );
  };

  const data = filter === 'unread' ? items.filter((n) => n.unread) : items;
  const sheetItem = items.find((n) => n.id === sheetItemId);

  return (
    <>
      <style>{CSS}</style>
      <div className="stage">
        <div className="device" data-screen-label="Уведомления">
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
              {/* Header */}
              <div className="nav">
                <button className="icon-btn press" data-go="Home.html" aria-label="Назад">
                  <svg width="22" height="22" viewBox="0 0 24 24" fill="none" stroke="var(--text)" strokeWidth="2.2" strokeLinecap="round" strokeLinejoin="round">
                    <path d="M15 18l-6-6 6-6" />
                  </svg>
                </button>
                <div className="nav-title t-h3">Уведомления</div>
                <div className="nav-right">
                  <button className="nav-action press" disabled={unread === 0} onClick={markAll}>
                    Прочитать
                  </button>
                </div>
              </div>

              {/* Filter */}
              <div style={{ padding: '6px 16px 12px' }}>
                <div className="seg" style={{ width: '100%' }}>
                  <button
                    className={'seg-item' + (filter === 'all' ? ' active' : '')}
                    data-filter="all"
                    style={{ flex: 1 }}
                    onClick={() => setFilter('all')}
                  >
                    Все · {items.length}
                  </button>
                  <button
                    className={'seg-item' + (filter === 'unread' ? ' active' : '')}
                    data-filter="unread"
                    style={{ flex: 1 }}
                    onClick={() => setFilter('unread')}
                  >
                    Новые{unread > 0 ? ' · ' + unread : ''}
                  </button>
                </div>
              </div>

              {/* List */}
              <div
                className="scroller"
                ref={scrollerRef}
                onPointerDown={onScrollerPointerDown}
                onPointerMove={onScrollerPointerMove}
                onPointerUp={endPull}
                onPointerCancel={endPull}
                onPointerLeave={endPull}
              >
                <div className="ptr" ref={ptrRef}>
                  <svg width="22" height="22" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.2" strokeLinecap="round">
                    <path d="M21 12a9 9 0 1 1-6.2-8.5" />
                    <path d="M21 3v6h-6" />
                  </svg>
                </div>
                <div className="list" ref={listRef}>
                  {data.length === 0 ? (
                    <div className="card empty fade-up" style={{ padding: 0, marginTop: 8 }}>
                      <div className="empty" style={{ margin: 0 }}>
                        <div className="empty-ic">
                          <Ico name="sparkle" size={26} color="var(--accent-deep)" sw={1.8} />
                        </div>
                        <div className="t-h3" style={{ fontSize: 16 }}>Всё прочитано</div>
                        <div className="t-small" style={{ maxWidth: 230 }}>
                          Когда появятся новые уведомления — увидишь их тут.
                        </div>
                      </div>
                    </div>
                  ) : (
                    <>
                      {GROUPS.map((g) => {
                        const inGroup = data.filter((n) => n.group === g.key);
                        if (!inGroup.length) return null;
                        const gu = inGroup.filter((n) => n.unread).length;
                        return (
                          <Fragment key={g.key}>
                            <div className="group-head fade-up">
                              <span className="t-mini">{g.label}</span>
                              <span className="t-mini gh-count">
                                · {inGroup.length}
                                {gu ? ' · ' + gu + ' нов.' : ''}
                              </span>
                            </div>
                            {inGroup.map(renderCard)}
                          </Fragment>
                        );
                      })}
                      <div className="t-mini" style={{ textAlign: 'center', padding: '16px 0 0', color: 'var(--text-3)' }}>
                        Конец списка
                      </div>
                    </>
                  )}
                </div>
              </div>

              {/* Long-press action sheet */}
              <div className={'sheet-backdrop' + (backShow ? ' show' : '')} onClick={closeSheet} />
              <div className={'sheet' + (sheetShow ? ' show' : '')}>
                {sheetItem && (
                  <>
                    <div className="sheet-title">
                      <div className="t-mini">Уведомление</div>
                      <div className="t-h3" style={{ fontSize: 15, marginTop: 3, whiteSpace: 'nowrap', overflow: 'hidden', textOverflow: 'ellipsis' }}>
                        {sheetItem.title}
                      </div>
                    </div>
                    <button
                      className="sheet-btn"
                      onClick={() => { closeSheet(); toggleRead(sheetItem.id); }}
                    >
                      <Ico name={sheetItem.unread ? 'check' : 'bell'} size={19} color="var(--text-2)" sw={2} />
                      {sheetItem.unread ? 'Отметить прочитанным' : 'Отметить непрочитанным'}
                    </button>
                    <button
                      className="sheet-btn danger"
                      onClick={() => { closeSheet(); removeItem(sheetItem.id); }}
                    >
                      <Ico name="trash" size={19} color="var(--danger)" sw={2} />
                      Удалить
                    </button>
                    <button className="sheet-btn sheet-cancel" onClick={closeSheet}>
                      Отмена
                    </button>
                  </>
                )}
              </div>

              <div className={'toast' + (toastShow ? ' show' : '')}>{toastMsg}</div>
              <div className="home-indicator" />
            </div>
          </div>
        </div>
      </div>
    </>
  );
}

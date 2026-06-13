/* ============================================================
   mobile-dock.js — shared Gen-2 mobile quick-action dock
   Self-contained: injects its own scoped styles (.g2-*), a bottom
   quick-action dock (≤900px), generic bottom-sheets, and a toast.
   Relies only on design tokens every screen defines (--text,
   --surface, --border, --accent, etc.). Safe to drop on any page:
   inline this IIFE inside a script tag just before the closing body tag.
   ============================================================ */
(function () {
  'use strict';
  if (window.__g2dock) return;
  window.__g2dock = true;

  /* ---------- styles ---------- */
  var css = `
  .g2-dock { display: none; }
  @media (max-width: 900px) {
    .content { padding-bottom: calc(86px + env(safe-area-inset-bottom)) !important; }
    .g2-dock {
      display: grid; grid-template-columns: repeat(4, 1fr); gap: 2px;
      position: fixed; left: 0; right: 0; bottom: 0; z-index: 95;
      background: color-mix(in oklab, var(--surface) 92%, transparent);
      backdrop-filter: blur(16px) saturate(150%); -webkit-backdrop-filter: blur(16px) saturate(150%);
      border-top: 0.5px solid var(--border);
      padding: 7px 8px max(8px, env(safe-area-inset-bottom));
    }
    .g2-dock-btn {
      appearance: none; border: 0; background: transparent; cursor: pointer;
      display: flex; flex-direction: column; align-items: center; justify-content: center; gap: 4px;
      padding: 6px 2px 5px; border-radius: 12px; color: var(--text-2);
      font-family: inherit; min-height: 56px;
      transition: background .15s, transform .12s, color .15s;
    }
    .g2-dock-btn:active { background: var(--surface-3); transform: scale(.96); }
    .g2-dock-btn .g2-qd-ico {
      width: 30px; height: 30px; border-radius: 9px; display: grid; place-items: center;
      background: var(--surface-3); color: var(--text-2);
      transition: background .15s, color .15s, box-shadow .2s;
    }
    .g2-dock-btn.primary .g2-qd-ico { background: var(--text); color: var(--surface); box-shadow: 0 0 0 3px var(--accent-soft); }
    [data-theme="dark"] .g2-dock-btn.primary .g2-qd-ico { background: var(--accent); color: #06120c; }
    .g2-dock-btn .g2-qd-lbl { font-size: 10.5px; font-weight: 600; letter-spacing: -.1px; line-height: 1; color: var(--text-3); }
    .g2-dock-btn.primary .g2-qd-lbl { color: var(--text); }
  }
  @media (max-width: 380px) {
    .g2-dock { padding: 6px 6px max(6px, env(safe-area-inset-bottom)); }
    .g2-dock-btn { padding: 5px 2px 4px; gap: 3px; min-height: 52px; }
    .g2-dock-btn .g2-qd-ico { width: 28px; height: 28px; border-radius: 8px; }
    .g2-dock-btn .g2-qd-lbl { font-size: 10px; }
  }
  /* keep page's bottom-anchored chrome (demo state switchers, toasts) above the dock */
  @media (max-width: 900px) {
    .state-switcher, .switcher { bottom: calc(96px + env(safe-area-inset-bottom)) !important; top: auto !important; }
    .toast { bottom: calc(96px + env(safe-area-inset-bottom)) !important; }
  }
  /* comfortable touch targets on mobile (≥44px) without distorting icon/round buttons */
  @media (max-width: 640px) {
    .btn:not(.btn-sm):not(.icon-btn) { min-height: 44px; }
  }

  /* bottom-sheet */
  .g2-sheet-ov {
    position: fixed; inset: 0; z-index: 140; display: none;
    align-items: flex-end; justify-content: center;
    background: rgba(0,0,0,.4); backdrop-filter: blur(4px); -webkit-backdrop-filter: blur(4px);
  }
  .g2-sheet-ov.open { display: flex; }
  .g2-sheet {
    width: 100%; max-width: 520px; background: var(--surface);
    border-radius: 22px 22px 0 0; box-shadow: 0 -12px 40px rgba(0,0,0,.22);
    display: flex; flex-direction: column; max-height: 90dvh;
    transform: translateY(100%); transition: transform .28s cubic-bezier(.32,.72,.2,1);
    padding-bottom: env(safe-area-inset-bottom);
  }
  .g2-sheet-ov.open .g2-sheet { transform: none; }
  @media (min-width: 560px) { .g2-sheet-ov { align-items: center; } .g2-sheet { border-radius: 20px; margin: 16px; max-height: calc(100dvh - 32px); } }
  .g2-sheet-grip { width: 36px; height: 4px; border-radius: 999px; background: var(--border-strong); margin: 10px auto 2px; }
  .g2-sheet-head { display: flex; align-items: flex-start; gap: 12px; padding: 8px 20px 12px; }
  .g2-sheet-ico { width: 40px; height: 40px; border-radius: 11px; flex-shrink: 0; display: grid; place-items: center; background: var(--accent-soft); color: var(--accent-deep); }
  [data-theme="dark"] .g2-sheet-ico { color: var(--accent); }
  .g2-sheet-title { font-size: 16.5px; font-weight: 700; letter-spacing: -.3px; }
  .g2-sheet-sub { font-size: 12.5px; color: var(--text-3); margin-top: 2px; }
  .g2-sheet-close { margin-left: auto; width: 32px; height: 32px; flex-shrink: 0; border: 0; border-radius: 50%; background: var(--surface-3); color: var(--text-2); display: grid; place-items: center; cursor: pointer; }
  .g2-sheet-body { padding: 4px 20px 18px; overflow-y: auto; }
  .g2-lbl { display: block; font-size: 12px; font-weight: 600; color: var(--text-2); margin: 14px 0 7px; }
  .g2-lbl:first-child { margin-top: 4px; }
  .g2-inp, .g2-sel {
    width: 100%; height: 48px; border: 0.5px solid var(--border-strong); background: var(--surface-2);
    border-radius: 12px; padding: 0 14px; font-size: 16px; color: var(--text); outline: none; font-family: inherit;
  }
  .g2-sel { appearance: none; background-image: url("data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' width='12' height='12' viewBox='0 0 24 24' fill='none' stroke='%23a8a29e' stroke-width='2.4' stroke-linecap='round' stroke-linejoin='round'%3E%3Cpolyline points='6 9 12 15 18 9'/%3E%3C/svg%3E"); background-repeat: no-repeat; background-position: right 14px center; padding-right: 36px; }
  .g2-inp:focus, .g2-sel:focus { border-color: var(--accent); background: var(--surface); box-shadow: 0 0 0 3px var(--accent-soft); }
  .g2-sheet-foot { padding: 12px 20px max(14px, env(safe-area-inset-bottom)); border-top: 0.5px solid var(--border); display: flex; flex-direction: column-reverse; gap: 8px; background: var(--surface-2); }
  .g2-btn { height: 48px; border-radius: 12px; border: 0; font-size: 15px; font-weight: 650; cursor: pointer; font-family: inherit; width: 100%; display: inline-flex; align-items: center; justify-content: center; gap: 8px; }
  .g2-btn-primary { background: var(--text); color: var(--surface); }
  [data-theme="dark"] .g2-btn-primary { background: var(--accent); color: #06120c; }
  .g2-btn-ghost { background: var(--surface); border: 0.5px solid var(--border-strong); color: var(--text); }

  .g2-toast {
    position: fixed; bottom: calc(96px + env(safe-area-inset-bottom)); left: 50%; transform: translateX(-50%) translateY(20px);
    background: var(--text); color: var(--surface); padding: 12px 18px; border-radius: 999px;
    font-size: 13.5px; font-weight: 600; box-shadow: 0 12px 32px rgba(0,0,0,.25);
    display: flex; align-items: center; gap: 9px; opacity: 0; pointer-events: none;
    transition: opacity .22s, transform .22s; z-index: 160; max-width: calc(100vw - 32px);
  }
  [data-theme="dark"] .g2-toast { background: var(--accent); color: #06120c; }
  .g2-toast.show { opacity: 1; transform: translateX(-50%) translateY(0); }
  @media (min-width: 901px) { .g2-toast { bottom: 24px; } }
  `;
  var st = document.createElement('style');
  st.id = 'g2-dock-styles';
  st.textContent = css;
  document.head.appendChild(st);

  /* ---------- icons ---------- */
  var ICO = {
    checkin: '<svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.2" stroke-linecap="round" stroke-linejoin="round"><path d="M9 11l3 3L22 4"/><path d="M21 12v7a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h11"/></svg>',
    client: '<svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.2" stroke-linecap="round" stroke-linejoin="round"><path d="M16 21v-2a4 4 0 0 0-4-4H6a4 4 0 0 0-4 4v2"/><circle cx="9" cy="7" r="4"/><line x1="19" y1="8" x2="19" y2="14"/><line x1="22" y1="11" x2="16" y2="11"/></svg>',
    extend: '<svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.2" stroke-linecap="round" stroke-linejoin="round"><rect x="2" y="5" width="20" height="14" rx="2"/><line x1="2" y1="10" x2="22" y2="10"/></svg>',
    book: '<svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.2" stroke-linecap="round" stroke-linejoin="round"><rect x="3" y="4" width="18" height="18" rx="2"/><line x1="16" y1="2" x2="16" y2="6"/><line x1="8" y1="2" x2="8" y2="6"/><line x1="3" y1="10" x2="21" y2="10"/></svg>',
    close: '<svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.2" stroke-linecap="round" stroke-linejoin="round"><line x1="18" y1="6" x2="6" y2="18"/><line x1="6" y1="6" x2="18" y2="18"/></svg>',
    ok: '<svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.6" stroke-linecap="round" stroke-linejoin="round"><polyline points="20 6 9 17 4 12"/></svg>'
  };

  /* ---------- action sheet content ---------- */
  var ACTIONS = {
    checkin: {
      title: 'Отметить визит', sub: 'Чек-ин клиента на сегодня', ico: ICO.checkin,
      body: '<label class="g2-lbl">Клиент</label><input class="g2-inp" type="text" placeholder="Имя, телефон или № карты" />' +
            '<label class="g2-lbl">Направление</label><select class="g2-sel"><option>Тренажёрный зал</option><option>Групповые</option><option>Бассейн</option><option>Персональная</option></select>',
      cta: 'Отметить визит', toast: 'Визит отмечен'
    },
    client: {
      title: 'Новый клиент', sub: 'Быстрое добавление', ico: ICO.client,
      body: '<label class="g2-lbl">Имя и фамилия</label><input class="g2-inp" type="text" placeholder="Например, Анна Петрова" />' +
            '<label class="g2-lbl">Телефон</label><input class="g2-inp" type="tel" inputmode="tel" placeholder="+7" />' +
            '<label class="g2-lbl">Абонемент</label><select class="g2-sel"><option>Без абонемента</option><option>12 месяцев</option><option>6 месяцев</option><option>Разовое посещение</option></select>',
      cta: 'Создать клиента', toast: 'Клиент создан'
    },
    extend: {
      title: 'Продлить абонемент', sub: 'Добавить срок действующему', ico: ICO.extend,
      body: '<label class="g2-lbl">Клиент</label><input class="g2-inp" type="text" placeholder="Имя или телефон" />' +
            '<label class="g2-lbl">Срок продления</label><select class="g2-sel"><option>1 месяц</option><option>3 месяца</option><option>6 месяцев</option><option>12 месяцев</option></select>',
      cta: 'Продлить', toast: 'Абонемент продлён'
    },
    book: {
      title: 'Записать на тренировку', sub: 'Бронь слота в расписании', ico: ICO.book,
      body: '<label class="g2-lbl">Клиент</label><input class="g2-inp" type="text" placeholder="Имя или телефон" />' +
            '<label class="g2-lbl">Тренировка</label><select class="g2-sel"><option>Йога · сегодня 18:00</option><option>Бокс · сегодня 19:30</option><option>Силовая · завтра 09:00</option><option>Стретчинг · завтра 11:00</option></select>',
      cta: 'Записать', toast: 'Клиент записан'
    }
  };

  /* ---------- dock ---------- */
  var dock = document.createElement('nav');
  dock.className = 'g2-dock';
  dock.setAttribute('aria-label', 'Быстрые действия');
  dock.innerHTML =
    '<button class="g2-dock-btn primary" type="button" data-g2-act="checkin"><span class="g2-qd-ico">' + ICO.checkin + '</span><span class="g2-qd-lbl">Чек-ин</span></button>' +
    '<button class="g2-dock-btn" type="button" data-g2-act="client"><span class="g2-qd-ico">' + ICO.client + '</span><span class="g2-qd-lbl">Клиент</span></button>' +
    '<button class="g2-dock-btn" type="button" data-g2-act="extend"><span class="g2-qd-ico">' + ICO.extend + '</span><span class="g2-qd-lbl">Продлить</span></button>' +
    '<button class="g2-dock-btn" type="button" data-g2-act="book"><span class="g2-qd-ico">' + ICO.book + '</span><span class="g2-qd-lbl">Запись</span></button>';
  document.body.appendChild(dock);

  /* ---------- sheet ---------- */
  var ov = document.createElement('div');
  ov.className = 'g2-sheet-ov';
  ov.innerHTML =
    '<div class="g2-sheet" role="dialog" aria-modal="true">' +
      '<div class="g2-sheet-grip"></div>' +
      '<div class="g2-sheet-head">' +
        '<div class="g2-sheet-ico" id="g2-ico"></div>' +
        '<div style="min-width:0;flex:1;"><div class="g2-sheet-title" id="g2-title"></div><div class="g2-sheet-sub" id="g2-sub"></div></div>' +
        '<button class="g2-sheet-close" type="button" data-g2-close>' + ICO.close + '</button>' +
      '</div>' +
      '<div class="g2-sheet-body" id="g2-body"></div>' +
      '<div class="g2-sheet-foot">' +
        '<button class="g2-btn g2-btn-primary" type="button" id="g2-cta"></button>' +
        '<button class="g2-btn g2-btn-ghost" type="button" data-g2-close>Отмена</button>' +
      '</div>' +
    '</div>';
  document.body.appendChild(ov);

  /* ---------- toast ---------- */
  var toast = document.createElement('div');
  toast.className = 'g2-toast';
  toast.innerHTML = ICO.ok + '<span id="g2-toast-msg"></span>';
  document.body.appendChild(toast);
  var toastTimer = null;
  function showToast(msg) {
    document.getElementById('g2-toast-msg').textContent = msg;
    toast.classList.add('show');
    clearTimeout(toastTimer);
    toastTimer = setTimeout(function () { toast.classList.remove('show'); }, 2400);
  }

  /* ---------- behaviour ---------- */
  var curAct = null;
  function openSheet(key) {
    var a = ACTIONS[key]; if (!a) return;
    curAct = a;
    document.getElementById('g2-ico').innerHTML = a.ico;
    document.getElementById('g2-title').textContent = a.title;
    document.getElementById('g2-sub').textContent = a.sub;
    document.getElementById('g2-body').innerHTML = a.body;
    document.getElementById('g2-cta').textContent = a.cta;
    ov.classList.add('open');
  }
  function closeSheet() { ov.classList.remove('open'); }

  dock.addEventListener('click', function (e) {
    var b = e.target.closest('[data-g2-act]'); if (!b) return;
    openSheet(b.getAttribute('data-g2-act'));
  });
  ov.addEventListener('click', function (e) {
    if (e.target === ov || e.target.closest('[data-g2-close]')) closeSheet();
  });
  document.getElementById('g2-cta').addEventListener('click', function () {
    var msg = curAct ? curAct.toast : 'Готово';
    closeSheet();
    setTimeout(function () { showToast(msg); }, 180);
  });
  document.addEventListener('keydown', function (e) { if (e.key === 'Escape') closeSheet(); });
})();

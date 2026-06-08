/* ============================================================
   Экран «Чат» — пиксель-перфектный перенос 94-REFERENCE-ChatScreen.jsx
   (Phase 94, PWA-01/PWA-02/PWA-03).

   Перенос verbatim из референса: CSS, иконки, компоненты
   (Ico/Avatar/ReadTick/PhotoBubble/MessageRow/ConvCard), разметка
   списка+треда, анимации и жесты. Отличия от прототипа — строго те,
   что заданы планом/CONTEXT:
     (1) CSS отскоуплен под .chat-root (глобальные :root/html,body/body.dark
         переписаны на .chat-root / .chat-root.dark) — не ретемит остальной PWA.
     (2) Сорван прототип-хром: .device/.island/.status-bar/.home-indicator,
         собственный .tabbar, Tweaks-панель, postMessage edit-mode,
         data-go/data-toast документ-хендлер, myzal_theme sync.
     (3) Один реальный чат «Администрация / Мой зал», гидратируется из бэкенда.
     (4) Hide-for-future (код оставлен, не рендерится): голосовые, документ-аттач,
         PHOTO_PRESETS/PhotoBubble (для не-реальных), system/cancel виды,
         бот-автоответчик + quick-reply чипы.
     (5) Проводка к реальному бэкенду через хуки @/data (Plan 94-01) +
         window.__chat* WS-мост.
   ============================================================ */
import { useCallback, useEffect, useLayoutEffect, useRef, useState } from 'react';
import {
  useClientMessages,
  useSendMessage,
  useUploadAttachment,
  useMarkMessagesRead,
} from '@/data';
import { useUI } from '@/context/UIContext.jsx';
import { uuidV4 } from '@/lib/uuid';

/* ---------- Стили (verbatim из референса, отскоуплены под .chat-root) ---------- */
const CSS = `
.chat-root {
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
  --danger-soft: #fee2e2;

  --font: -apple-system, BlinkMacSystemFont, "SF Pro Text", "SF Pro Display",
          "Inter Variable", "Inter", system-ui, sans-serif;

  --r-pill: 999px;
  --r-lg: 20px;

  --sh-1: 0 1px 2px rgba(28, 25, 23, 0.04);
  --sh-2: 0 1px 3px rgba(28, 25, 23, 0.05), 0 4px 14px rgba(28, 25, 23, 0.04);

  --page: #e7e5e4;

  position: absolute; inset: 0;
  font-family: var(--font);
  -webkit-font-smoothing: antialiased;
  -moz-osx-font-smoothing: grayscale;
  background: var(--bg);
  color: var(--text);
  transition: background 0.3s ease;
}

.chat-root.dark {
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
  --danger-soft: rgba(244, 113, 104, 0.18);

  --sh-1: 0 1px 2px rgba(0,0,0,0.4);
  --sh-2: 0 1px 3px rgba(0,0,0,0.5), 0 4px 14px rgba(0,0,0,0.3);

  --page: #0a0a0a;
}

.chat-root * { box-sizing: border-box; }
.chat-root button { font-family: inherit; }
.chat-root input { font-family: inherit; }
.chat-root .t-num { font-variant-numeric: tabular-nums; }
.chat-root .t-mini { font-size: 11px; font-weight: 600; letter-spacing: 0.5px; text-transform: uppercase; color: var(--text-3); }
.chat-root .t-small { font-size: 13px; font-weight: 400; line-height: 1.4; color: var(--text-2); }
.chat-root .t-h3 { font-size: 17px; font-weight: 600; letter-spacing: -0.2px; line-height: 1.25; color: var(--text); }
.chat-root .t-h1 { font-size: 28px; font-weight: 700; letter-spacing: -0.6px; line-height: 1.1; color: var(--text); }
.chat-root .row { display: flex; align-items: center; gap: 12px; }
.chat-root .row-between { display: flex; align-items: center; justify-content: space-between; gap: 12px; }

.chat-root .screen {
  position: absolute; inset: 0;
  background: var(--bg);
  display: flex; flex-direction: column;
  transition: background 0.3s ease;
}

.chat-root .view { display: flex; flex-direction: column; flex: 1; min-height: 0; }
.chat-root .view-enter { animation: chat-screen-push 0.34s cubic-bezier(0.32,0.72,0.2,1); }
@keyframes chat-screen-push { from { transform: translateX(40px); opacity: 0; } to { transform: translateX(0); opacity: 1; } }
.chat-root .view-back { animation: chat-screen-pop 0.3s cubic-bezier(0.32,0.72,0.2,1); }
@keyframes chat-screen-pop { from { transform: translateX(-30px); opacity: 0; } to { transform: translateX(0); opacity: 1; } }

/* Scroll body */
.chat-root .scroller {
  flex: 1; overflow-y: auto; -webkit-overflow-scrolling: touch;
  position: relative;
}
.chat-root .scroller::-webkit-scrollbar { display: none; }

/* Pull to refresh */
.chat-root .ptr {
  position: absolute; top: 0; left: 0; right: 0; height: 46px;
  display: flex; align-items: center; justify-content: center;
  opacity: 0; pointer-events: none; z-index: 0;
}
.chat-root .ptr svg { color: var(--text-3); }
.chat-root .ptr.spin svg { animation: chat-ptr-spin 0.7s linear infinite; }
@keyframes chat-ptr-spin { to { transform: rotate(360deg); } }

.chat-root .card {
  background: var(--surface);
  border: 0.5px solid var(--border);
  border-radius: var(--r-lg);
  box-shadow: var(--sh-1);
}
.chat-root .press { transition: transform 0.1s ease, background 0.15s ease; cursor: pointer; }
.chat-root .press:active { transform: scale(0.985); }

/* Avatar */
.chat-root .avatar {
  border-radius: 999px; display: flex; align-items: center; justify-content: center;
  font-weight: 600; flex-shrink: 0; line-height: 1; overflow: hidden;
}

.chat-root .badge {
  min-width: 20px; height: 20px; padding: 0 6px; border-radius: 999px;
  background: var(--accent); color: #06120c; font-size: 11px; font-weight: 700;
  display: flex; align-items: center; justify-content: center; flex-shrink: 0;
}

/* Conversation list */
.chat-root .conv-list { display: flex; flex-direction: column; gap: 8px; padding: 0 16px; }
.chat-root .swipe {
  position: relative; border-radius: var(--r-lg); overflow: hidden;
}
.chat-root .swipe-action {
  position: absolute; inset: 0;
  display: flex; align-items: center; justify-content: flex-end;
  gap: 7px; padding-right: 24px;
  color: #fff; font-size: 13.5px; font-weight: 700;
  background: var(--accent-deep); opacity: 0;
  transition: opacity 0.15s ease;
}
.chat-root .swipe.armed .swipe-action { opacity: 1; }
.chat-root .conv-card {
  position: relative; z-index: 1; display: block; width: 100%; text-align: left;
  border: 0.5px solid var(--border); border-radius: var(--r-lg);
  background: var(--surface); color: var(--text);
  cursor: pointer; touch-action: pan-y;
  transition: transform 0.26s cubic-bezier(0.32,0.72,0.2,1);
  -webkit-user-select: none; user-select: none;
}
.chat-root .conv-card.removing { transition: transform 0.26s ease, opacity 0.26s ease; }

/* Thread top bar */
.chat-root .thread-bar {
  flex-shrink: 0;
  padding-top: 50px; padding-bottom: 10px;
  background: color-mix(in oklab, var(--bg) 88%, transparent);
  backdrop-filter: blur(20px); -webkit-backdrop-filter: blur(20px);
  border-bottom: 0.5px solid var(--border);
}
.chat-root .icon-btn {
  width: 36px; height: 36px; border-radius: 999px; border: 0;
  background: transparent; cursor: pointer; padding: 0;
  display: flex; align-items: center; justify-content: center;
}

/* Message bubbles */
.chat-root .msg-stack { display: flex; flex-direction: column; gap: 3px; }
.chat-root .bubble {
  max-width: 78%; padding: 9px 13px; border-radius: 18px;
  font-size: 15px; line-height: 1.4; word-break: break-word;
}
.chat-root .bubble-me { background: var(--accent); color: #06120c; border-bottom-right-radius: 5px; }
.chat-root .bubble-them {
  background: var(--surface); color: var(--text);
  border: 0.5px solid var(--border); border-bottom-left-radius: 5px;
}
.chat-root .bubble-system {
  background: var(--surface-2); color: var(--text-2);
  border: 0.5px solid var(--border);
  font-size: 12.5px; line-height: 1.45; max-width: 290px; text-align: center;
  border-radius: 14px; font-weight: 500;
}
.chat-root .bubble-meta { font-size: 11px; color: var(--text-3); font-weight: 500; }

.chat-root .typing-dots { display: inline-flex; gap: 4px; align-items: center; }
.chat-root .typing-dots span {
  width: 7px; height: 7px; border-radius: 999px; background: var(--text-3);
  animation: chat-typing-bounce 1.2s ease-in-out infinite;
}
.chat-root .typing-dots span:nth-child(2) { animation-delay: 0.15s; }
.chat-root .typing-dots span:nth-child(3) { animation-delay: 0.3s; }
@keyframes chat-typing-bounce {
  0%, 60%, 100% { transform: translateY(0); opacity: 0.5; }
  30% { transform: translateY(-3px); opacity: 1; }
}

.chat-root .quick {
  border: 0.5px solid var(--border-strong); background: var(--surface);
  color: var(--text); padding: 8px 14px; border-radius: 999px;
  font-size: 13px; font-weight: 500; cursor: pointer;
}

/* Composer */
.chat-root .composer {
  flex-shrink: 0;
  padding: 8px 8px 14px; border-top: 0.5px solid var(--border);
  background: var(--bg); display: flex; align-items: flex-end; gap: 6px;
}
.chat-root .composer-field {
  flex: 1; background: var(--surface); border-radius: 22px;
  border: 0.5px solid var(--border-strong); padding: 4px 8px 4px 16px;
  display: flex; align-items: center; min-height: 40px;
}
.chat-root .composer-field textarea {
  flex: 1; border: 0; outline: 0; background: transparent;
  font-size: 15px; color: var(--text); font-family: inherit;
  padding: 0; margin: 0; resize: none; line-height: 20px;
  min-height: 20px; max-height: 96px; overflow-y: auto; display: block;
}
.chat-root .composer-field textarea::-webkit-scrollbar { display: none; }
.chat-root .send-btn {
  width: 40px; height: 40px; border-radius: 999px; border: 0;
  display: flex; align-items: center; justify-content: center;
  cursor: pointer; flex-shrink: 0; transition: background 0.15s;
  background: var(--surface-2); color: var(--text-2);
}
.chat-root .send-btn.armed { background: var(--accent); color: #06120c; }

/* Long-press action sheet */
.chat-root .sheet-backdrop {
  position: absolute; inset: 0; z-index: 80;
  background: rgba(0,0,0,0.32); opacity: 0; pointer-events: none;
  transition: opacity 0.25s ease;
}
.chat-root .sheet-backdrop.show { opacity: 1; pointer-events: auto; }
.chat-root .sheet {
  position: absolute; left: 8px; right: 8px; bottom: 8px; z-index: 81;
  background: var(--surface); border: 0.5px solid var(--border);
  border-radius: 24px; box-shadow: var(--sh-2); padding: 8px;
  transform: translateY(150%); transition: transform 0.34s cubic-bezier(0.32,0.72,0.2,1);
  /* animation:none overrides the global styles.css .sheet rule (class-name collision):
     its sheet-in animation with both-fill outranks this transform and would otherwise
     pin the closed action sheet on-screen, blanking the whole chat. */
  animation: none;
}
.chat-root .sheet.show { transform: translateY(0); }
.chat-root .sheet-title { padding: 12px 14px 6px; }
.chat-root .sheet-btn {
  display: flex; align-items: center; gap: 12px; width: 100%;
  border: 0; background: transparent; font-family: inherit;
  font-size: 15px; font-weight: 600; color: var(--text);
  padding: 14px; border-radius: 14px; cursor: pointer; text-align: left;
}
.chat-root .sheet-btn:hover { background: var(--surface-2); }
.chat-root .sheet-btn.danger { color: var(--danger); }
.chat-root .sheet-cancel { margin-top: 4px; justify-content: center; background: var(--surface-2); color: var(--text-2); }

/* Toast */
.chat-root .toast {
  position: absolute; left: 50%; bottom: 96px; transform: translate(-50%, 16px);
  z-index: 90; background: var(--text); color: var(--bg);
  font-size: 13.5px; font-weight: 600; padding: 11px 18px; border-radius: 999px;
  box-shadow: 0 12px 30px rgba(0,0,0,0.28);
  opacity: 0; pointer-events: none;
  transition: opacity 0.22s ease, transform 0.28s cubic-bezier(0.32,0.72,0.2,1);
  white-space: nowrap;
}
.chat-root .toast.show { opacity: 1; transform: translate(-50%, 0); }

/* Search bar */
.chat-root .searchbar {
  display: flex; align-items: center; gap: 8px;
  background: var(--surface-2); border: 0.5px solid var(--border);
  border-radius: 12px; padding: 0 12px; height: 40px;
}
.chat-root .searchbar svg { color: var(--text-3); flex-shrink: 0; }
.chat-root .searchbar input {
  flex: 1; border: 0; outline: 0; background: transparent;
  font-size: 15px; color: var(--text); padding: 0; min-width: 0;
}
.chat-root .search-clear {
  border: 0; background: var(--border-strong); color: var(--surface);
  width: 20px; height: 20px; border-radius: 999px; cursor: pointer;
  display: flex; align-items: center; justify-content: center;
  font-size: 14px; line-height: 1; flex-shrink: 0; padding: 0;
}
/* Segmented control */
.chat-root .seg { display: flex; gap: 2px; padding: 3px; background: var(--surface-2); border: 0.5px solid var(--border); border-radius: 999px; }
.chat-root .seg-item {
  appearance: none; border: 0; background: transparent; cursor: pointer;
  height: 32px; border-radius: 999px; font-family: inherit; font-size: 12.5px; font-weight: 600;
  color: var(--text-2); transition: background 0.15s, color 0.15s, box-shadow 0.15s;
}
.chat-root .seg-item.active { background: var(--text); color: var(--bg); box-shadow: 0 1px 4px rgba(0,0,0,0.18); }

.chat-root .conv-empty { display: flex; flex-direction: column; align-items: center; text-align: center; padding: 44px 24px 24px; }

/* New-messages divider */
.chat-root .unread-divider { display: flex; align-items: center; gap: 10px; margin: 12px 4px 6px; }
.chat-root .unread-divider::before, .chat-root .unread-divider::after { content: ''; flex: 1; height: 1px; background: color-mix(in oklab, var(--accent) 32%, transparent); }
.chat-root .unread-divider span { font-size: 10.5px; font-weight: 700; letter-spacing: 0.5px; text-transform: uppercase; color: var(--accent-deep); white-space: nowrap; }

/* Message entrance */
.chat-root .msg-in { animation: chat-msg-in 0.32s cubic-bezier(0.32,0.72,0.2,1) both; }
@keyframes chat-msg-in { from { opacity: 0; transform: translateY(10px) scale(0.98); } to { opacity: 1; transform: none; } }

/* Scroll-to-bottom */
.chat-root #threadView { position: relative; }
.chat-root .scroll-down {
  position: absolute; right: 14px; bottom: 78px; z-index: 6;
  width: 40px; height: 40px; border-radius: 999px;
  background: var(--surface); border: 0.5px solid var(--border-strong);
  box-shadow: var(--sh-2); cursor: pointer;
  display: flex; align-items: center; justify-content: center; color: var(--text-2);
  opacity: 0; transform: translateY(12px) scale(0.9); pointer-events: none;
  transition: opacity 0.22s ease, transform 0.22s cubic-bezier(0.32,0.72,0.2,1);
}
.chat-root .scroll-down.show { opacity: 1; transform: none; pointer-events: auto; }
.chat-root .scroll-down .sd-dot {
  position: absolute; top: -2px; right: -2px; width: 12px; height: 12px;
  border-radius: 999px; background: var(--accent); border: 2px solid var(--surface);
  opacity: 0; transform: scale(0.5); transition: opacity 0.2s, transform 0.2s;
}
.chat-root .scroll-down.has-new .sd-dot { opacity: 1; transform: none; }

/* Day separator */
.chat-root .day-sep { display: flex; justify-content: center; margin: 14px 0 8px; }
.chat-root .day-sep span {
  background: var(--surface-2); border: 0.5px solid var(--border);
  color: var(--text-3); font-size: 11px; font-weight: 600; letter-spacing: 0.3px;
  padding: 4px 12px; border-radius: 999px;
}

/* Empty thread — branded spot illustration */
.chat-root .thread-empty {
  display: flex; flex-direction: column; align-items: center; text-align: center;
  padding: 50px 24px 24px;
}
.chat-root .thread-empty .t-h3 { font-size: 17px; margin-top: 14px; }
.chat-root .thread-empty .t-small { max-width: 248px; margin-top: 6px; }
.chat-root .spot { position: relative; width: 128px; height: 96px; flex-shrink: 0; }
.chat-root .spot .halo {
  position: absolute; left: 19px; top: 50%; transform: translateY(-50%);
  width: 90px; height: 90px; border-radius: 50%;
  background: radial-gradient(circle, color-mix(in oklab, var(--accent) 20%, transparent) 0%, transparent 64%);
}
.chat-root .spot .ring {
  position: absolute; left: 19px; top: 50%; transform: translateY(-50%);
  width: 90px; height: 90px; border-radius: 50%;
  border: 1.5px dashed color-mix(in oklab, var(--accent) 42%, transparent); opacity: 0.5;
}
.chat-root .spot .ring.r2 { width: 118px; height: 118px; left: 5px; opacity: 0.24; }
.chat-root .spot .scene-pos { position: absolute; left: 64px; top: 50%; transform: translate(-50%, -50%); z-index: 2; }
.chat-root .spot .scene {
  width: 76px; height: 62px; background: var(--surface);
  border: 0.5px solid var(--border); border-radius: 15px;
  box-shadow: 0 10px 24px rgba(28,25,23,0.12), 0 2px 5px rgba(28,25,23,0.05);
  padding: 11px 12px; transform: rotate(-4deg); transform-origin: center;
  animation: chat-scene-in 0.46s cubic-bezier(0.32, 1.6, 0.32, 1) both;
}
.chat-root.dark .spot .scene { box-shadow: 0 10px 24px rgba(0,0,0,0.4), 0 2px 5px rgba(0,0,0,0.3); }
@keyframes chat-scene-in {
  0% { transform: rotate(-4deg) scale(0.5); opacity: 0; }
  60% { transform: rotate(-4deg) scale(1.06); }
  100% { transform: rotate(-4deg) scale(1); opacity: 1; }
}
.chat-root .sc-chat { display: flex; flex-direction: column; gap: 6px; justify-content: center; height: 100%; }
.chat-root .sc-chat i { height: 6px; border-radius: 999px; background: var(--border-strong); }
.chat-root .sc-chat i.b1 { width: 72%; }
.chat-root .sc-chat i.b2 { width: 48%; }
.chat-root .sc-chat i.me { width: 58%; align-self: flex-end; background: var(--accent); }
.chat-root .spot .chip {
  position: absolute; border-radius: 4px; background: var(--accent);
  animation: chat-spot-float 3.4s ease-in-out infinite; z-index: 1;
}
.chat-root .spot .chip.c1 { width: 9px; height: 9px; right: 24px; top: 8px; transform: rotate(16deg); background: var(--accent-deep); }
.chat-root .spot .chip.c2 { width: 7px; height: 7px; right: 8px; bottom: 20px; border-radius: 50%; animation-delay: 0.7s; }
.chat-root .spot .chip.c3 { width: 6px; height: 6px; left: 12px; top: 16px; border-radius: 50%; animation-delay: 1.2s; background: var(--accent-deep); }
@keyframes chat-spot-float {
  0%, 100% { transform: translateY(0) rotate(0); }
  50% { transform: translateY(-6px) rotate(10deg); }
}

/* Loading skeleton (P87/P88 precedent — not in reference; for initial fetch) */
.chat-root .sk-card { height: 76px; border-radius: var(--r-lg); margin: 0 16px 8px; background: linear-gradient(90deg, var(--surface-2) 0%, var(--surface) 50%, var(--surface-2) 100%); background-size: 200% 100%; animation: chat-sk 1.2s ease-in-out infinite; }
@keyframes chat-sk { from { background-position: 200% 0; } to { background-position: -200% 0; } }

.chat-root .hidden { display: none !important; }
.chat-root .fade-up { animation: chat-fade-up 0.32s cubic-bezier(0.32,0.72,0.2,1) both; }
@keyframes chat-fade-up { from { opacity: 0; transform: translateY(8px); } to { opacity: 1; transform: translateY(0); } }

/* Full-screen photo overlay (PWA-03 — not in reference CSS) */
.chat-root .photo-overlay {
  position: fixed; inset: 0; background: rgba(0,0,0,0.9);
  z-index: 200; display: flex; align-items: center; justify-content: center;
}
.chat-root .photo-overlay img { max-width: 100%; max-height: 100%; object-fit: contain; }
`;

/* ---------- Иконки ---------- */
const ICON = {
  check: '<path d="M5 12l5 5L20 6"/>',
  bell: '<path d="M18 8a6 6 0 10-12 0c0 7-3 9-3 9h18s-3-2-3-9"/><path d="M13.7 21a2 2 0 01-3.4 0"/>',
  bellOff: '<path d="M9 9a6 6 0 016-2.5M18 8c0 7 3 9 3 9H7M13.7 21a2 2 0 01-3.4 0M2 2l20 20"/>',
  box: '<path d="M3 7l2-3h14l2 3M3 7v12a1 1 0 001 1h16a1 1 0 001-1V7M3 7h18M9 11h6"/>',
  trash: '<path d="M4 7h16M9 7V5a1 1 0 011-1h4a1 1 0 011 1v2M6 7l1 13a1 1 0 001 1h8a1 1 0 001-1l1-13"/>',
  chevronRight: '<path d="M9 6l6 6-6 6"/>',
  info: '<circle cx="12" cy="12" r="9"/><path d="M12 11v5M12 7.5v.5"/>',
  alert: '<path d="M12 3l9 16H3L12 3z"/><path d="M12 10v4M12 17v.5"/>',
  camera: '<path d="M4 8h3l2-3h6l2 3h3a1 1 0 011 1v9a1 1 0 01-1 1H4a1 1 0 01-1-1V9a1 1 0 011-1z"/><circle cx="12" cy="13" r="3.2"/>',
  image: '<rect x="3" y="4" width="18" height="16" rx="3"/><circle cx="9" cy="10" r="2"/><path d="M21 16l-5-5-7 7"/>',
  file: '<path d="M14 3H7a2 2 0 00-2 2v14a2 2 0 002 2h10a2 2 0 002-2V8l-5-5z"/><path d="M14 3v5h5"/>',
  mic: '<rect x="9" y="3" width="6" height="13" rx="3"/><path d="M5 11a7 7 0 0014 0M12 18v3"/>',
  search: '<circle cx="11" cy="11" r="7"/><path d="M21 21l-4.2-4.2"/>',
};

function Ico({ name, size, color, sw }) {
  return (
    <svg
      width={size}
      height={size}
      viewBox="0 0 24 24"
      fill="none"
      stroke={color || 'currentColor'}
      strokeWidth={sw || 1.9}
      strokeLinecap="round"
      strokeLinejoin="round"
      dangerouslySetInnerHTML={{ __html: ICON[name] || '' }}
    />
  );
}

function Avatar({ c, size }) {
  const fs = Math.round(size * 0.36);
  return (
    <div className="avatar" style={{ width: size, height: size, background: c.bg, color: c.color, fontSize: fs }}>
      {c.initials}
    </div>
  );
}

function ReadTick({ read }) {
  if (read) {
    return (
      <svg width="16" height="11" viewBox="0 0 16 11" fill="none" style={{ marginBottom: -1 }} role="img" aria-label="Прочитано">
        <path d="M1 6l3 3 6-7" stroke="var(--accent-deep)" strokeWidth="1.6" strokeLinecap="round" strokeLinejoin="round" />
        <path d="M6 6l3 3 6-7" stroke="var(--accent-deep)" strokeWidth="1.6" strokeLinecap="round" strokeLinejoin="round" />
      </svg>
    );
  }
  return (
    <svg width="11" height="11" viewBox="0 0 11 11" fill="none" style={{ marginBottom: -1 }} role="img" aria-label="Доставлено">
      <path d="M1 6l3 3 6-7" stroke="var(--text-3)" strokeWidth="1.6" strokeLinecap="round" strokeLinejoin="round" />
    </svg>
  );
}

/* HIDE-FOR-FUTURE: gradient photo presets — kept in source, NOT rendered.
   Real photo attachments render the authenticated <img> (PWA-03). */
const PHOTO_PRESETS = {
  plan: { bg: 'linear-gradient(135deg,#fde68a 0%,#f59e0b 60%,#ea580c 100%)', label: 'PLAN.pdf', sub: 'программа на завтра' },
  'gym-selfie': { bg: 'linear-gradient(135deg,#cbd5e1 0%,#475569 70%,#1e293b 100%)', label: 'IMG_4821.jpg', sub: 'отправлено сейчас' },
};

// eslint-disable-next-line no-unused-vars
function PhotoBubble({ kind }) {
  const p = PHOTO_PRESETS[kind] || PHOTO_PRESETS['gym-selfie'];
  return (
    <div style={{ width: 220, height: 140, borderRadius: 14, position: 'relative', background: p.bg, overflow: 'hidden' }}>
      <div style={{ position: 'absolute', inset: 0, background: 'radial-gradient(120% 80% at 70% 25%,rgba(255,255,255,0.35),transparent 60%)' }} />
      <div style={{ position: 'absolute', left: 10, bottom: 8, color: '#fff', fontSize: 11, fontWeight: 600, letterSpacing: '0.3px', textShadow: '0 1px 2px rgba(0,0,0,0.5)' }}>
        <div>{p.label}</div>
        <div style={{ opacity: 0.85, fontWeight: 500 }}>{p.sub}</div>
      </div>
    </div>
  );
}

/* Сообщение. system/cancel ветки оставлены (hide-for-future — не достигаются
   проводными данными). kind 'photo' рендерит реальную картинку (PWA-03). */
function MessageRow({ m, i, msgs, animate, onPhotoTap }) {
  const cls = animate ? ' msg-in' : '';
  if (m.kind === 'system') {
    return (
      <div className={'msgrow' + cls} style={{ display: 'flex', flexDirection: 'column', alignItems: 'center', margin: '8px 0' }}>
        <div className="bubble bubble-system">
          <div className="row" style={{ gap: 6, justifyContent: 'center' }}>
            <Ico name="info" size={14} color="currentColor" sw={2} />
            {m.body}
          </div>
        </div>
        <div className="bubble-meta" style={{ marginTop: 4 }}>{m.time}</div>
      </div>
    );
  }
  if (m.kind === 'cancel') {
    return (
      <div className={'msgrow' + cls} style={{ margin: '8px 0', display: 'flex', justifyContent: 'center' }}>
        <div className="bubble" style={{ background: 'var(--danger-soft)', color: 'var(--danger)', border: '0.5px solid color-mix(in oklab,var(--danger) 30%,transparent)', maxWidth: 280, textAlign: 'center', fontSize: 13.5, lineHeight: 1.45, fontWeight: 500 }}>
          <div className="row" style={{ gap: 6, justifyContent: 'center', marginBottom: 4 }}>
            <Ico name="alert" size={14} color="currentColor" sw={2} />
            <span style={{ fontWeight: 700, fontSize: 12, letterSpacing: '0.4px', textTransform: 'uppercase' }}>Тренировка отменена</span>
          </div>
          {m.body}
        </div>
      </div>
    );
  }
  const mine = m.from === 'me';
  const showTime = i === msgs.length - 1 || msgs[i + 1]?.from !== m.from || msgs[i + 1]?.time !== m.time;
  const isPhoto = m.kind === 'photo';
  const inner = isPhoto ? (
    <div className={'bubble ' + (mine ? 'bubble-me' : 'bubble-them')} style={{ padding: 4, overflow: 'hidden' }}>
      <div style={{ width: 220, height: 140, borderRadius: 14, overflow: 'hidden' }}>
        <img
          src={m.attachment?.url}
          style={{ width: '100%', height: '100%', objectFit: 'cover', borderRadius: 10, cursor: 'pointer', display: 'block' }}
          alt="Фото"
          onClick={() => m.attachment?.url && onPhotoTap?.(m.attachment.url)}
        />
      </div>
      {m.body && !m.body.startsWith('photo:') && <div style={{ padding: '6px 10px 4px', fontSize: 14 }}>{m.body}</div>}
    </div>
  ) : (
    <div className={'bubble ' + (mine ? 'bubble-me' : 'bubble-them')}>{m.body}</div>
  );
  return (
    <div className={'msgrow' + cls} style={{ display: 'flex', flexDirection: 'column', alignItems: mine ? 'flex-end' : 'flex-start' }}>
      {inner}
      {showTime && (
        <div className="bubble-meta" style={{ marginTop: 3, display: 'flex', gap: 4, alignItems: 'center' }}>
          <span>{m.time}</span>
          {mine && <ReadTick read={m.read} />}
        </div>
      )}
    </div>
  );
}

/* ---------- Данные ---------- */
/* Единственный реальный чат — «Администрация / Мой зал» (референс c1).
   Остальные 3 мок-чата удалены. Метаданные хардкод; контент гидратируется. */
const ADMIN_CONV = {
  id: 'admin',
  name: 'Администрация',
  sub: 'Мой зал',
  initials: 'МЗ',
  color: '#1c1917',
  bg: '#e7e5e4',
  isOfficial: true,
};

const MAX_UPLOAD_BYTES = 5 * 1024 * 1024;
const ALLOWED_IMAGE_TYPES = ['image/jpeg', 'image/png', 'image/webp'];

const TIME_FMT = new Intl.DateTimeFormat('ru-RU', {
  hour: '2-digit',
  minute: '2-digit',
  timeZone: 'Europe/Moscow',
});

const DAY_FMT = new Intl.DateTimeFormat('ru-RU', {
  day: 'numeric',
  month: 'long',
  timeZone: 'Europe/Moscow',
});

function moscowDayKey(iso) {
  // YYYY-MM-DD in Europe/Moscow — used to group day separators.
  const parts = new Intl.DateTimeFormat('en-CA', {
    year: 'numeric',
    month: '2-digit',
    day: '2-digit',
    timeZone: 'Europe/Moscow',
  }).format(new Date(iso));
  return parts;
}

function dayLabel(iso) {
  const key = moscowDayKey(iso);
  const todayKey = moscowDayKey(new Date().toISOString());
  const yesterday = new Date();
  yesterday.setDate(yesterday.getDate() - 1);
  const yesterdayKey = moscowDayKey(yesterday.toISOString());
  if (key === todayKey) return 'Сегодня';
  if (key === yesterdayKey) return 'Вчера';
  return DAY_FMT.format(new Date(iso));
}

/* Реф-мок → бэкенд (см. 94-PATTERNS adaptMessage). sentAt сохраняем для
   ватермарка read-receipt (sentAt <= readAt → ✓✓). */
function adaptMessage(m) {
  return {
    id: m.id,
    from: m.role === 'client' ? 'me' : 'them',
    body: m.body,
    time: TIME_FMT.format(new Date(m.sentAt)),
    day: dayLabel(m.sentAt),
    read: m.readAt != null,
    kind: m.attachment ? 'photo' : 'text',
    attachment: m.attachment ?? null,
    sentAt: m.sentAt,
  };
}

export function ChatScreen({ tweaks, initialConv, onClearInitial, onThreadOpen }) {
  // ── Данные бэкенда ──
  const messagesQuery = useClientMessages();
  const sendMessageM = useSendMessage();
  const uploadM = useUploadAttachment();
  const markReadM = useMarkMessagesRead();
  const ui = useUI();

  const isLoading = messagesQuery.isLoading;
  const isError = messagesQuery.isError && !messagesQuery.isFetching;

  // Тема следует существующему PWA-механизму (data-theme на <html> через
  // TweaksProvider). tweaks-проп реактивен; MutationObserver — резервный путь.
  const [isDark, setIsDark] = useState(
    () => (tweaks?.theme === 'dark') || document.documentElement.getAttribute('data-theme') === 'dark',
  );
  useEffect(() => {
    const read = () =>
      setIsDark(
        (tweaks?.theme === 'dark') ||
          document.documentElement.getAttribute('data-theme') === 'dark',
      );
    read();
    const obs = new MutationObserver(read);
    obs.observe(document.documentElement, { attributes: true, attributeFilter: ['data-theme'] });
    return () => obs.disconnect();
  }, [tweaks?.theme]);

  // ── Список ──
  const [openId, setOpenId] = useState(null);
  const [viewAnim, setViewAnim] = useState(null); // 'enter' | 'back'
  const [convFilter, setConvFilter] = useState('all');
  const [convQuery, setConvQuery] = useState('');

  // ── Тред ──
  const [typing, setTyping] = useState(false);
  const [threadDividerId, setThreadDividerId] = useState(null);
  const [animateId, setAnimateId] = useState(null);
  const [input, setInput] = useState('');

  // Локальные оптимистичные сообщения + локальный watermark read-receipt.
  const [optimistic, setOptimistic] = useState([]); // adapted message shape
  const [readWatermark, setReadWatermark] = useState(null); // ISO string from WS

  // Локальное UI-состояние одного чата (mute/archive/delete без бэкенда).
  const [muted, setMuted] = useState(false);
  const [removed, setRemoved] = useState(false);
  const [locallyUnread, setLocallyUnread] = useState(false); // sheet "Не прочитано"

  // ── Шиты ──
  const [sheetOpen, setSheetOpen] = useState(false);
  const [sheetShow, setSheetShow] = useState(false);
  const [sheetBackShow, setSheetBackShow] = useState(false);
  const [attachShow, setAttachShow] = useState(false);
  const [attachBackShow, setAttachBackShow] = useState(false);

  // ── Фото-оверлей (PWA-03 — наполняется в Task 3) ──
  const [photoOverlay, setPhotoOverlay] = useState(null);
  // Открытие треда происходит на pointerup карточки списка; следом браузер шлёт
  // синтетический `click` по тем же координатам — а там уже отрисован тред, и
  // если на этой высоте оказался фото-пузырь, его onClick открыл бы overlay
  // («экран затемняется при входе в чат»). Гасим клики по фото в первые мс после
  // открытия треда. (В референсе фото были некликабельны — overlay добавлен в порте.)
  const threadOpenedAtRef = useRef(0);
  const openPhoto = useCallback((url) => {
    if (!url) return;
    if (Date.now() - threadOpenedAtRef.current < 400) return;
    setPhotoOverlay(url);
  }, []);

  // ── Тост ──
  const [toastMsg, setToastMsg] = useState('');
  const [toastShow, setToastShow] = useState(false);
  const toastTimer = useRef(null);

  // ── refs ──
  const openIdRef = useRef(openId); openIdRef.current = openId;
  const inputRef = useRef(input); inputRef.current = input;

  const listScrollerRef = useRef(null);
  const listShiftRef = useRef(null);
  const ptrRef = useRef(null);
  const activeRef = useRef(null);
  const pullRef = useRef({ pStart: null, pulling: false, loading: false, pull: 0 });

  const threadScrollerRef = useRef(null);
  const msgInputRef = useRef(null);
  const scrollDownBtnRef = useRef(null);
  const stickRef = useRef(false);
  const typingDismissRef = useRef(null);

  // File inputs (PWA-03)
  const cameraInputRef = useRef(null);
  const galleryInputRef = useRef(null);

  // WR-01: лечч per-open-session для mark-read. Не шлём повторный PATCH за
  // одно открытие треда: лatch сбрасывается при openThread и устанавливается
  // при первом PATCH, поэтому backend lag / eventual-consistency не порождает
  // серийный цикл PATCH→invalidate→refetch→PATCH.
  const markedForOpenRef = useRef(false);

  // WR-02 (объект URLs): object URLs созданные для оптимистичного превью фото.
  // Нельзя отзывать в finally на успешном пути — серверный refetch, заменяющий
  // оптимистичное сообщение, асинхронен, и полноэкранный оверлей может всё ещё
  // ссылаться на этот URL. Храним и отзываем только когда URL больше нигде не
  // отрисован (см. эффект ниже) и при размонтировании.
  const photoObjectUrlsRef = useRef(new Set());

  // WR-02 (unmount guard): gate post-await setState calls so they don't run
  // after ChatScreen unmounts (lazy-routed, unmounts on tab switch).
  const mountedRef = useRef(true);

  /* ── Toast ── */
  const toast = useCallback((msg) => {
    setToastMsg(msg);
    setToastShow(true);
    clearTimeout(toastTimer.current);
    toastTimer.current = setTimeout(() => setToastShow(false), 1700);
  }, []);

  /* ── Сообщения треда: бэкенд + оптимистичные + watermark read-receipt ── */
  const serverData = messagesQuery.data;
  const serverItems = serverData?.items ?? [];
  const unreadCount = serverData?.unreadCount ?? 0;

  // Адаптируем серверные сообщения; применяем WS-watermark поверх REST readAt.
  // CR-02: сравниваем мгновения по epoch-ms (Date.parse), а не лексикографически
  // по ISO-строкам. sentAt (сервер) и readAt (WS) — два разных источника; смешанные
  // форматы офсета (`Z` vs `+03:00`) или дробные секунды ломают строковое сравнение.
  const wmMs = readWatermark != null ? Date.parse(readWatermark) : null;
  const adaptedServer = serverItems.map((m) => {
    const a = adaptMessage(m);
    if (a.from === 'me' && !a.read && wmMs != null && Date.parse(a.sentAt) <= wmMs) {
      a.read = true;
    }
    return a;
  });

  // Отфильтровываем оптимистичные, которые уже подтвердились с сервера
  // (грубо — по факту наличия любого серверного сообщения с тем же body после optimistic ts).
  const serverIds = new Set(serverItems.map((m) => m.id));
  const pendingOptimistic = optimistic.filter((o) => !serverIds.has(o.id));
  const threadMessages = [...adaptedServer, ...pendingOptimistic];

  // Последнее сообщение для превью карточки.
  const lastMsg = threadMessages.length ? threadMessages[threadMessages.length - 1] : null;
  const lastPreview = lastMsg
    ? (lastMsg.kind === 'photo' ? '📷 Фото' : lastMsg.body)
    : 'Начните диалог';
  const lastTime = lastMsg ? lastMsg.time : '';
  const isEmptyConv = threadMessages.length === 0;

  // Карточка единственного чата.
  const adminUnread = locallyUnread ? 1 : unreadCount;
  const conv = {
    ...ADMIN_CONV,
    unread: adminUnread,
    isMuted: muted,
    last: lastPreview,
    lastTime,
    isEmpty: isEmptyConv,
    messages: threadMessages,
  };
  const convs = removed ? [] : [conv];
  const unreadConvs = convs.filter((c) => c.unread > 0).length;

  /* ── Фид unread в TabBar (PWA-02) ── */
  // WR-04: зависим только от значений, не от объекта `ui` (его useMemo-идентичность
  // меняется на любом изменении UI-состояния → лишние ре-запуски эффекта).
  // setUnreadChat — стабильный setter, держим его в ref.
  const setUnreadChatRef = useRef(ui.setUnreadChat);
  setUnreadChatRef.current = ui.setUnreadChat;
  useEffect(() => {
    if (!serverData) return;
    // WR-08: единый источник истины с карточкой (adminUnread), и пока тред открыт
    // бейдж таба = 0 (иначе после openThread следующий serverData-poll вернул бы
    // старый unreadCount и бейдж мигнул бы в ненулевое значение).
    setUnreadChatRef.current(openIdRef.current != null ? 0 : adminUnread);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [serverData, adminUnread]);

  /* ── Список: фильтр/поиск ── */
  const visibleConvs = () => {
    let arr = convs.slice();
    if (convFilter === 'unread') arr = arr.filter((c) => c.unread > 0);
    const q = convQuery.trim().toLowerCase();
    if (q) arr = arr.filter((c) => (c.name + ' ' + c.sub + ' ' + c.last).toLowerCase().includes(q));
    return arr;
  };

  /* ── Mute (локально) ── */
  const toggleMute = useCallback(() => {
    setMuted((prev) => {
      const next = !prev;
      setTimeout(() => toast(next ? 'Чат заглушён' : 'Уведомления включены'), 0);
      return next;
    });
  }, [toast]);

  /* ── Long-press sheet ── */
  const openSheet = useCallback(() => {
    setSheetOpen(true);
    setSheetBackShow(true);
    requestAnimationFrame(() => setSheetShow(true));
  }, []);
  const closeSheet = useCallback(() => { setSheetShow(false); setSheetBackShow(false); }, []);

  /* ── Thread open/close ── */
  const openThread = useCallback((id) => {
    // Divider над первым непрочитанным staff-сообщением.
    const incoming = threadMessages.filter((m) => m.from === 'them' && !m.read);
    setThreadDividerId(incoming.length ? incoming[0].id : null);
    setTyping(false);
    setAnimateId(null);
    setInput('');
    setLocallyUnread(false);
    // WR-01: сброс latch — новый open-session допускает ровно один PATCH.
    markedForOpenRef.current = false;
    // Mark-read: на бэкенде + оптимистично гасим бейдж.
    // Устанавливаем latch сразу, так как этот вызов уже является первым PATCH.
    markedForOpenRef.current = true;
    markReadM.mutate();
    ui.setUnreadChat(0);
    setViewAnim('enter');
    setOpenId(id);
    onThreadOpen?.(true);
    threadOpenedAtRef.current = Date.now();
    setPhotoOverlay(null); // defensive: never enter a thread with a stale overlay open
    stickRef.current = true;
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [markReadM, ui, onThreadOpen, threadMessages]);

  const closeThread = useCallback(() => {
    clearTimeout(typingDismissRef.current);
    if (scrollDownBtnRef.current) scrollDownBtnRef.current.classList.remove('show', 'has-new');
    setOpenId(null);
    setThreadDividerId(null);
    setAnimateId(null);
    setTyping(false);
    setViewAnim('back');
    onThreadOpen?.(false);
  }, [onThreadOpen]);

  /* ── Открытие треда по initialConv (deep-link из App) ── */
  useEffect(() => {
    if (initialConv && openIdRef.current == null) {
      openThread(ADMIN_CONV.id);
      onClearInitial?.();
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [initialConv]);

  /* ── Scroll-down кнопка ── */
  const updateScrollDown = useCallback(() => {
    const sc = threadScrollerRef.current;
    const btn = scrollDownBtnRef.current;
    if (!sc || !btn) return;
    if (openIdRef.current == null) { btn.classList.remove('show'); return; }
    const nearBottom = sc.scrollHeight - sc.scrollTop - sc.clientHeight < 120;
    btn.classList.toggle('show', !nearBottom);
    if (nearBottom) btn.classList.remove('has-new');
  }, []);

  const setTypingFn = useCallback((v) => {
    const sc = threadScrollerRef.current;
    const nearBottom = sc ? sc.scrollHeight - sc.scrollTop - sc.clientHeight < 140 : true;
    stickRef.current = nearBottom;
    setTyping(v);
  }, []);

  /* ── WS-мост: read-receipt + typing (App-level singleton делегирует сюда) ── */
  useEffect(() => {
    // WR-06: ownership guard. ChatScreen route-mounted (lazy) и может
    // двойным-монтироваться (переход между табами, StrictMode dev double-invoke).
    // Cleanup отмонтирующегося инстанса не должен затереть хендлеры, которые
    // только что установил новый инстанс — поэтому сохраняем предыдущие хендлеры
    // и в cleanup восстанавливаем их только если текущие всё ещё наши.
    const prevReadReceipt = window.__chatReadReceipt;
    const prevTyping = window.__chatTyping;
    const readReceiptHandler = (readAt) => {
      if (!readAt) return;
      // Watermark: пометить все свои сообщения с sentAt <= readAt как ✓✓.
      // CR-02: монотонность по epoch-ms, не по строке.
      setReadWatermark((prev) =>
        prev == null || Date.parse(readAt) > Date.parse(prev) ? readAt : prev,
      );
    };
    const typingHandler = () => {
      setTypingFn(true);
      clearTimeout(typingDismissRef.current);
      typingDismissRef.current = setTimeout(() => setTypingFn(false), 5000);
    };
    window.__chatReadReceipt = readReceiptHandler;
    window.__chatTyping = typingHandler;
    return () => {
      // Восстанавливаем предыдущий хендлер только если наш ещё активен.
      if (window.__chatReadReceipt === readReceiptHandler) {
        window.__chatReadReceipt = prevReadReceipt;
      }
      if (window.__chatTyping === typingHandler) {
        window.__chatTyping = prevTyping;
      }
      clearTimeout(typingDismissRef.current);
    };
  }, [setTypingFn]);

  // WR-02: эффект-сборщик object URL фото. Отзываем только те URL, на которые
  // больше нет ссылок: ни в оптимистичных сообщениях (заменены серверными), ни в
  // открытом полноэкранном оверлее. Иначе превью/оверлей покажет пустой blob.
  useEffect(() => {
    const stillUsed = new Set();
    for (const o of optimistic) {
      if (o.attachment?.url) stillUsed.add(o.attachment.url);
    }
    if (photoOverlay) stillUsed.add(photoOverlay);
    for (const url of photoObjectUrlsRef.current) {
      if (!stillUsed.has(url)) {
        URL.revokeObjectURL(url);
        photoObjectUrlsRef.current.delete(url);
      }
    }
  }, [optimistic, photoOverlay]);

  // WR-02: страховка при размонтировании — отзываем все оставшиеся object URL.
  useEffect(() => {
    const urls = photoObjectUrlsRef.current;
    return () => {
      for (const url of urls) URL.revokeObjectURL(url);
      urls.clear();
    };
  }, []);

  // WR-02: unmount guard — set mountedRef false on cleanup so post-await
  // setState calls in sendTextMessage / sendPhoto don't run after unmount.
  useEffect(() => {
    mountedRef.current = true;
    return () => { mountedRef.current = false; };
  }, []);

  // mark-read при входящем сообщении пока тред открыт.
  // WR-03: guard против PATCH-петли — не шлём новую мутацию пока предыдущая
  // в полёте.
  // WR-01: latch per-open-session — markedForOpenRef предотвращает серийный
  // цикл PATCH→invalidate→refetch→PATCH при backend lag (eventual consistency).
  // Latch сброшен в openThread, поэтому genuinely новые unread (пришедшие через
  // WS пока тред открыт) снова взведут его только если unreadCount вырос.
  useEffect(() => {
    if (openIdRef.current != null && unreadCount > 0 && !markReadM.isPending && !markedForOpenRef.current) {
      markedForOpenRef.current = true;
      markReadM.mutate();
      ui.setUnreadChat(0);
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [unreadCount, markReadM.isPending]);

  /* ── Отправка текста (REST + WS echo заменяет оптимистичное) ── */
  const sendTextMessage = useCallback(async (text) => {
    const t = (text != null ? text : inputRef.current).trim();
    if (!t) return;
    const optimisticId = 'opt-' + Date.now() + '-' + Math.random();
    const nowIso = new Date().toISOString();
    const optimisticMsg = {
      id: optimisticId,
      from: 'me',
      body: t,
      time: TIME_FMT.format(new Date(nowIso)),
      day: dayLabel(nowIso),
      read: false,
      kind: 'text',
      attachment: null,
      sentAt: nowIso,
    };
    setOptimistic((prev) => [...prev, optimisticMsg]);
    setAnimateId(optimisticId);
    setInput('');
    stickRef.current = true;
    try {
      await sendMessageM.mutateAsync({ body: t, idempotencyKey: uuidV4() });
      // WS new_message → App invalidate → refetch заменит оптимистичное.
      // WR-02: guard — component may unmount (tab switch) while send is in flight.
      if (mountedRef.current) setOptimistic((prev) => prev.filter((o) => o.id !== optimisticId));
    } catch {
      if (mountedRef.current) {
        setOptimistic((prev) => prev.filter((o) => o.id !== optimisticId));
        toast('Не удалось отправить');
      }
    }
  }, [sendMessageM, toast]);

  /* ── Фото: камера/галерея → валидация → upload→send (PWA-03) ── */
  const sendPhoto = useCallback(async (file) => {
    if (!file) return;
    if (!ALLOWED_IMAGE_TYPES.includes(file.type)) { toast('Неподдерживаемый формат'); return; }
    if (file.size > MAX_UPLOAD_BYTES) { toast('Файл слишком большой (макс. 5 МБ)'); return; }

    const optimisticId = 'opt-photo-' + Date.now() + '-' + Math.random();
    const objectUrl = URL.createObjectURL(file);
    photoObjectUrlsRef.current.add(objectUrl);
    const nowIso = new Date().toISOString();
    const optimisticMsg = {
      id: optimisticId,
      from: 'me',
      body: '',
      time: TIME_FMT.format(new Date(nowIso)),
      day: dayLabel(nowIso),
      read: false,
      kind: 'photo',
      attachment: { id: optimisticId, mimeType: file.type, sizeBytes: file.size, url: objectUrl },
      sentAt: nowIso,
    };
    setOptimistic((prev) => [...prev, optimisticMsg]);
    setAnimateId(optimisticId);
    stickRef.current = true;
    try {
      const { attachmentId } = await uploadM.mutateAsync({ file });
      await sendMessageM.mutateAsync({ attachmentId, idempotencyKey: uuidV4() });
      // WR-02: guard — component may unmount while upload/send is in flight.
      // НЕ отзываем objectUrl здесь — refetch, заменяющий оптимистичное
      // сообщение реальным серверным изображением, асинхронен, и оверлей может
      // всё ещё показывать этот URL. Отзыв делает эффект-сборщик ниже, когда URL
      // больше нигде не используется.
      if (mountedRef.current) setOptimistic((prev) => prev.filter((o) => o.id !== optimisticId));
    } catch {
      if (mountedRef.current) {
        setOptimistic((prev) => prev.filter((o) => o.id !== optimisticId));
        toast('Не удалось отправить фото');
      }
      // WR-02: отзыв также откладываем эффекту-сборщику (оверлей мог уже открыться
      // на этом URL до ошибки).
    }
  }, [uploadM, sendMessageM, toast]);

  const onFilePicked = (e) => {
    const file = e.target.files?.[0];
    e.target.value = ''; // allow re-pick same file
    if (file) void sendPhoto(file);
  };

  /* ── Thread: автоскролл к низу ── */
  useLayoutEffect(() => {
    if (openId == null) return;
    if (stickRef.current) {
      const sc = threadScrollerRef.current;
      if (sc) sc.scrollTop = sc.scrollHeight;
      stickRef.current = false;
    }
    updateScrollDown();
  }, [openId, serverData, optimistic, typing, threadDividerId, updateScrollDown]);

  /* ── Composer auto-grow ── */
  useLayoutEffect(() => {
    const ta = msgInputRef.current;
    if (!ta) return;
    ta.style.height = 'auto';
    ta.style.height = Math.min(ta.scrollHeight, 110) + 'px';
  }, [input, openId]);

  /* ── Жесты карточек чатов: document-level ── */
  useEffect(() => {
    const onMove = (e) => {
      const a = activeRef.current;
      if (!a) return;
      const dx = e.clientX - a.x0;
      const dy = e.clientY - a.y0;
      if (Math.abs(dx) > 6 || Math.abs(dy) > 6) { a.moved = true; clearTimeout(a.timer); }
      if (Math.abs(dx) > Math.abs(dy)) {
        a.dx = dx;
        let t = Math.min(0, dx);
        if (t < -100) t = -100;
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
      if (a.dx <= -64) {
        a.card.style.transform = 'translateX(0)';
        setTimeout(() => a.wrap.classList.remove('armed'), 180);
        toggleMute();
        return;
      }
      a.card.style.transform = 'translateX(0)';
      setTimeout(() => a.wrap.classList.remove('armed'), 180);
      if (!a.moved && !a.longFired) openThread(a.id);
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
  }, [toggleMute, openThread, openSheet]);

  const onConvPointerDown = (e, id) => {
    if (e.button != null && e.button !== 0) return;
    const card = e.currentTarget;
    const wrap = card.closest('.swipe');
    activeRef.current = {
      wrap, card, id, x0: e.clientX, y0: e.clientY,
      dx: 0, moved: false, longFired: false,
      timer: setTimeout(() => {
        const a = activeRef.current;
        if (a && !a.moved) {
          a.longFired = true;
          if (navigator.vibrate) navigator.vibrate(8);
          openSheet();
        }
      }, 450),
    };
    card.style.transition = 'none';
  };

  /* ── Pull to refresh (список) → реальный refetch ── */
  const onListPointerDown = (e) => {
    const p = pullRef.current;
    const a = activeRef.current;
    if (p.loading || (a && a.moved)) return;
    const sc = listScrollerRef.current;
    if (sc && sc.scrollTop <= 0) { p.pStart = { x: e.clientX, y: e.clientY }; p.pulling = true; }
  };
  const onListPointerMove = (e) => {
    const p = pullRef.current;
    if (!p.pulling || p.loading || !p.pStart) return;
    const sc = listScrollerRef.current;
    const shift = listShiftRef.current;
    const ptr = ptrRef.current;
    if (!sc || !shift || !ptr) return;
    const dy = e.clientY - p.pStart.y;
    const dx = e.clientX - p.pStart.x;
    if (dy <= 0 || Math.abs(dx) > Math.abs(dy)) return;
    if (sc.scrollTop > 0) { p.pulling = false; return; }
    const pull = Math.min(64, dy * 0.5);
    shift.style.transition = 'none';
    shift.style.transform = 'translateY(' + pull + 'px)';
    ptr.style.opacity = Math.min(1, pull / 46);
    const svg = ptr.querySelector('svg');
    if (svg) svg.style.transform = 'rotate(' + pull * 5 + 'deg)';
    p.pull = pull;
  };
  const endPull = () => {
    const p = pullRef.current;
    if (!p.pulling) return;
    p.pulling = false;
    const pull = p.pull || 0;
    p.pull = 0;
    const shift = listShiftRef.current;
    const ptr = ptrRef.current;
    if (!shift || !ptr) return;
    shift.style.transition = 'transform 0.3s cubic-bezier(0.32,0.72,0.2,1)';
    const settle = () => {
      shift.style.transform = 'translateY(0)';
      ptr.classList.remove('spin');
      ptr.style.opacity = 0;
      p.loading = false;
    };
    if (pull >= 44) {
      p.loading = true;
      shift.style.transform = 'translateY(44px)';
      ptr.classList.add('spin');
      ptr.style.opacity = 1;
      const svg = ptr.querySelector('svg');
      if (svg) svg.style.transform = '';
      messagesQuery.refetch().finally(() => {
        settle();
        toast('Обновлено');
      });
    } else {
      shift.style.transform = 'translateY(0)';
      ptr.style.opacity = 0;
    }
  };

  /* ── Sheet actions (локально — нет бэкенда для mute/archive/delete) ── */
  const onSheetAction = (a) => {
    closeSheet();
    if (a === 'read') setLocallyUnread((prev) => !prev);
    else if (a === 'mute') toggleMute();
    else if (a === 'archive') { setRemoved(true); toast('Чат в архиве'); }
    else if (a === 'delete') { setRemoved(true); toast('Чат удалён'); }
  };

  /* ── Attach sheet ── */
  const openAttach = () => { setAttachBackShow(true); requestAnimationFrame(() => setAttachShow(true)); };
  const closeAttach = () => { setAttachShow(false); setAttachBackShow(false); };
  const onAttachAction = (a) => {
    closeAttach();
    // HIDE-FOR-FUTURE: только Камера + Фото из галереи (документ/голосовое скрыты).
    if (a === 'camera') cameraInputRef.current?.click();
    else if (a === 'photo') galleryInputRef.current?.click();
  };

  /* ── Composer handlers ── */
  const armed = input.trim().length > 0;
  const onSendClick = () => {
    // HIDE-FOR-FUTURE: голосовое скрыто — без текста кнопка-микрофон no-op.
    if (input.trim()) void sendTextMessage();
  };
  const onKeyDown = (e) => {
    if (e.key === 'Enter' && !e.shiftKey) { e.preventDefault(); void sendTextMessage(); }
  };

  const data = visibleConvs();
  const searching = convQuery.trim().length > 0;
  const sheetConv = sheetOpen ? conv : null;

  /* ── Рендер карточки чата ── */
  const ConvCard = (c) => {
    const lastColor = c.isEmpty ? 'var(--accent-deep)' : c.unread ? 'var(--text)' : 'var(--text-2)';
    return (
      <div className="swipe" data-id={c.id} key={c.id}>
        <div className="swipe-action" onClick={() => toggleMute()}>
          <Ico name={c.isMuted ? 'bell' : 'bellOff'} size={17} color="#fff" sw={2} />
          {c.isMuted ? 'Включить' : 'Заглушить'}
        </div>
        <button className="conv-card press" data-id={c.id} onPointerDown={(e) => onConvPointerDown(e, c.id)}>
          <div style={{ padding: 14, display: 'flex', gap: 12, alignItems: 'center' }}>
            <div style={{ position: 'relative' }}>
              <Avatar c={c} size={48} />
              {c.isOfficial && (
                <div style={{ position: 'absolute', right: -2, bottom: -2, width: 18, height: 18, borderRadius: 999, background: 'var(--accent)', display: 'flex', alignItems: 'center', justifyContent: 'center', border: '2px solid var(--surface)' }}>
                  <Ico name="check" size={11} color="#06120c" sw={3} />
                </div>
              )}
            </div>
            <div style={{ flex: 1, minWidth: 0 }}>
              <div className="row-between">
                <span className="t-h3" style={{ fontSize: 15 }}>{c.name}</span>
                <span className="t-small" style={{ color: 'var(--text-3)', fontSize: 12 }}>{c.lastTime}</span>
              </div>
              <div className="t-mini" style={{ marginTop: 1, color: 'var(--text-3)', fontWeight: 500, letterSpacing: '0.2px', textTransform: 'none' }}>
                {c.sub}{c.isMuted ? ' · приглушён' : ''}
              </div>
              <div className="row-between" style={{ marginTop: 6, gap: 8 }}>
                <div className="t-small" style={{ color: lastColor, fontWeight: c.unread ? 500 : 400, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap', flex: 1 }}>{c.last}</div>
                {c.unread > 0 && <span className="badge">{c.unread}</span>}
              </div>
            </div>
          </div>
        </button>
      </div>
    );
  };

  /* ── Рендер сообщений треда ── */
  const renderThreadBody = () => {
    if (!conv) return null;
    if (!conv.messages.length && !typing) {
      return (
        <>
          <div className="thread-empty fade-up">
            <div className="spot">
              <div className="ring r2" /><div className="ring" /><div className="halo" />
              <span className="chip c1" /><span className="chip c2" /><span className="chip c3" />
              <div className="scene-pos"><div className="scene"><div className="sc-chat">
                <i className="b1" /><i className="b2" /><i className="me" />
              </div></div></div>
            </div>
            <div className="t-h3">Здесь пока пусто</div>
            <div className="t-small">Напишите первое сообщение — ответим в рабочее время.</div>
          </div>
        </>
      );
    }
    const out = [];
    let lastDay = null;
    conv.messages.forEach((m, i) => {
      if (m.day && m.day !== lastDay) {
        out.push(<div className="day-sep" key={'day-' + i}><span>{m.day}</span></div>);
        lastDay = m.day;
      }
      if (m.id === threadDividerId) out.push(<div className="unread-divider" key={'div-' + m.id}><span>Новые сообщения</span></div>);
      out.push(<MessageRow key={m.id} m={m} i={i} msgs={conv.messages} animate={m.id === animateId} onPhotoTap={openPhoto} />);
    });
    if (typing) {
      out.push(
        <div className="msg-in" key="typing" style={{ display: 'flex', alignItems: 'flex-end', gap: 6 }}>
          <div className="bubble bubble-them" style={{ padding: '10px 14px' }}>
            <div className="typing-dots"><span /><span /><span /></div>
          </div>
        </div>
      );
    }
    return out;
  };

  // HIDE-FOR-FUTURE: quick-reply чипы (bot-coupled) — всегда скрыты.
  const showQuick = false;
  const statusText = conv ? (typing ? 'печатает…' : conv.sub + (conv.isOfficial ? ' · ✓ верифицирован' : ' · в сети')) : '';

  return (
    <div className={'chat-root' + (isDark ? ' dark' : '')}>
      <style>{CSS}</style>

      {/* hidden file inputs (PWA-03) */}
      <input ref={cameraInputRef} type="file" accept="image/*" capture="environment" style={{ display: 'none' }} onChange={onFilePicked} />
      <input ref={galleryInputRef} type="file" accept="image/jpeg,image/png,image/webp" style={{ display: 'none' }} onChange={onFilePicked} />

      <div className="screen">
        {/* ===== LIST VIEW ===== */}
        <div className={'view' + (openId != null ? ' hidden' : '') + (viewAnim === 'back' ? ' view-back' : '')} id="listView">
          <div
            className="scroller"
            id="listScroller"
            ref={listScrollerRef}
            onPointerDown={onListPointerDown}
            onPointerMove={onListPointerMove}
            onPointerUp={endPull}
            onPointerCancel={endPull}
            onPointerLeave={endPull}
          >
            <div className="ptr" ref={ptrRef}>
              <svg width="22" height="22" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.2" strokeLinecap="round"><path d="M21 12a9 9 0 1 1-6.2-8.5" /><path d="M21 3v6h-6" /></svg>
            </div>
            <div id="listShift" ref={listShiftRef}>
              <div style={{ padding: '54px 20px 12px 20px' }}>
                <div className="t-mini">Сообщения</div>
                <div className="t-h1" style={{ marginTop: 4 }}>Чат</div>
              </div>
              <div style={{ padding: '0 16px 10px' }}>
                <div className="searchbar">
                  <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><circle cx="11" cy="11" r="7" /><path d="M21 21l-4.2-4.2" /></svg>
                  <input value={convQuery} onChange={(e) => setConvQuery(e.target.value)} placeholder="Поиск по чатам" autoComplete="off" />
                  {convQuery && (
                    <button className="search-clear" type="button" aria-label="Очистить" onClick={() => setConvQuery('')}>✕</button>
                  )}
                </div>
              </div>
              <div style={{ padding: '0 16px 12px' }}>
                <div className="seg" style={{ width: '100%' }}>
                  <button className={'seg-item' + (convFilter === 'all' ? ' active' : '')} style={{ flex: 1 }} type="button" onClick={() => setConvFilter('all')}>Все · {convs.length}</button>
                  <button className={'seg-item' + (convFilter === 'unread' ? ' active' : '')} style={{ flex: 1 }} type="button" onClick={() => setConvFilter('unread')}>Новые{unreadConvs > 0 ? ' · ' + unreadConvs : ''}</button>
                </div>
              </div>
              <div className="conv-list" id="convList">
                {isLoading ? (
                  <div aria-label="Загрузка сообщений…">
                    <div className="sk-card" />
                    <div className="sk-card" />
                  </div>
                ) : isError ? (
                  <div className="conv-empty fade-up">
                    <div style={{ width: 56, height: 56, borderRadius: 16, background: 'var(--danger-soft)', display: 'flex', alignItems: 'center', justifyContent: 'center' }}>
                      <Ico name="alert" size={26} color="var(--danger)" sw={1.8} />
                    </div>
                    <div className="t-h3" style={{ fontSize: 16, marginTop: 12 }}>Не удалось загрузить</div>
                    <div className="t-small" style={{ maxWidth: 230, marginTop: 4 }}>Потяните вниз, чтобы повторить.</div>
                  </div>
                ) : data.length ? (
                  data.map(ConvCard)
                ) : (
                  <div className="conv-empty fade-up">
                    <div style={{ width: 56, height: 56, borderRadius: 16, background: 'var(--accent-soft)', display: 'flex', alignItems: 'center', justifyContent: 'center' }}>
                      <Ico name={searching ? 'search' : 'check'} size={26} color="var(--accent-deep)" sw={1.9} />
                    </div>
                    <div className="t-h3" style={{ fontSize: 16, marginTop: 12 }}>{searching ? 'Ничего не найдено' : 'Всё прочитано'}</div>
                    <div className="t-small" style={{ maxWidth: 230, marginTop: 4 }}>{searching ? 'Попробуйте другой запрос.' : 'Непрочитанных чатов нет.'}</div>
                  </div>
                )}
              </div>
              <div style={{ padding: '24px 20px 8px' }}>
                <div className="t-small" style={{ color: 'var(--text-3)' }}>
                  Администрация работает с 8:00 до 22:00. Тренеры отвечают в свободное время.
                </div>
              </div>
              <div style={{ height: 24 }} />
            </div>
          </div>
        </div>

        {/* ===== THREAD VIEW ===== */}
        {openId != null && conv && (
          <div className={'view' + (viewAnim === 'enter' ? ' view-enter' : '')} id="threadView">
            <div className="thread-bar">
              <div style={{ padding: '4px 12px', display: 'flex', alignItems: 'center', gap: 4 }}>
                <button className="icon-btn press" onClick={closeThread} aria-label="Назад к списку чатов">
                  <svg width="22" height="22" viewBox="0 0 24 24" fill="none" stroke="var(--text)" strokeWidth="2.2" strokeLinecap="round" strokeLinejoin="round"><path d="M15 18l-6-6 6-6" /></svg>
                </button>
                <div style={{ position: 'relative' }}>
                  <Avatar c={conv} size={36} />
                  <span style={{ position: 'absolute', right: -1, bottom: -1, width: 10, height: 10, borderRadius: 999, background: 'var(--accent)', border: '2px solid var(--bg)' }} />
                </div>
                <div style={{ flex: 1, marginLeft: 4, minWidth: 0 }}>
                  <div className="t-h3" style={{ fontSize: 15 }}>{conv.name}</div>
                  <div className="t-mini" style={{ marginTop: 1, textTransform: 'none', letterSpacing: '0.2px', fontWeight: 500, color: typing ? 'var(--accent-deep)' : 'var(--text-3)' }}>{statusText}</div>
                </div>
              </div>
            </div>

            <div className="scroller" id="threadScroller" ref={threadScrollerRef} onScroll={updateScrollDown} style={{ padding: '14px 14px' }}>
              <div className="msg-stack" id="msgStack">{renderThreadBody()}</div>
              <div id="quickReplies" style={{ marginTop: 16, display: 'flex', flexWrap: 'wrap', gap: 8 }}>
                {showQuick && ['Расскажи про скидку', 'Когда сауна работает?', 'Спасибо!'].map((q) => (
                  <button key={q} className="quick press" onClick={() => sendTextMessage(q)}>{q}</button>
                ))}
              </div>
              <div style={{ height: 16 }} />
            </div>

            <button className="scroll-down" ref={scrollDownBtnRef} type="button" aria-label="К последним сообщениям" onClick={() => { const sc = threadScrollerRef.current; sc.scrollTo({ top: sc.scrollHeight, behavior: 'smooth' }); scrollDownBtnRef.current.classList.remove('has-new'); }}>
              <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><path d="M12 5v14M19 12l-7 7-7-7" /></svg>
              <span className="sd-dot" />
            </button>

            <div className="composer">
              <button className="icon-btn press" onClick={openAttach} aria-label="Прикрепить" style={{ width: 40, height: 40, color: 'var(--text-2)' }}>
                <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round"><path d="M21 11l-8.5 8.5a4.5 4.5 0 01-6.4-6.4L14 5a3 3 0 014.2 4.2l-8 8a1.5 1.5 0 01-2.1-2.1l7.3-7.3" /></svg>
              </button>
              <div className="composer-field">
                <textarea ref={msgInputRef} value={input} onChange={(e) => setInput(e.target.value)} onKeyDown={onKeyDown} rows={1} placeholder="Сообщение" autoComplete="off" />
              </div>
              <button className={'send-btn' + (armed ? ' armed' : '')} onClick={onSendClick} aria-label={armed ? 'Отправить' : 'Записать голосовое'}>
                {armed ? (
                  <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><path d="M22 2L11 13" /><path d="M22 2l-7 20-4-9-9-4 20-7z" /></svg>
                ) : (
                  <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round"><rect x="9" y="3" width="6" height="13" rx="3" /><path d="M5 11a7 7 0 0014 0M12 18v3" /></svg>
                )}
              </button>
            </div>
          </div>
        )}

        {/* Long-press action sheet */}
        <div className={'sheet-backdrop' + (sheetBackShow ? ' show' : '')} onClick={closeSheet} />
        <div className={'sheet' + (sheetShow ? ' show' : '')}>
          {sheetConv && (
            <>
              <div className="sheet-title">
                <div className="t-mini">Чат</div>
                <div className="t-h3" style={{ fontSize: 15, marginTop: 3, whiteSpace: 'nowrap', overflow: 'hidden', textOverflow: 'ellipsis' }}>{sheetConv.name}</div>
              </div>
              <button className="sheet-btn" onClick={() => onSheetAction('read')}>
                <Ico name={sheetConv.unread ? 'check' : 'bell'} size={19} color="var(--text-2)" sw={2} />
                {sheetConv.unread ? 'Прочитано' : 'Не прочитано'}
              </button>
              <button className="sheet-btn" onClick={() => onSheetAction('mute')}>
                <Ico name={sheetConv.isMuted ? 'bell' : 'bellOff'} size={19} color="var(--text-2)" sw={2} />
                {sheetConv.isMuted ? 'Включить уведомления' : 'Заглушить'}
              </button>
              <button className="sheet-btn" onClick={() => onSheetAction('archive')}>
                <Ico name="box" size={19} color="var(--text-2)" sw={2} />В архив
              </button>
              <button className="sheet-btn danger" onClick={() => onSheetAction('delete')}>
                <Ico name="trash" size={19} color="var(--danger)" sw={2} />Удалить
              </button>
              <button className="sheet-btn sheet-cancel" onClick={() => onSheetAction('cancel')}>Отмена</button>
            </>
          )}
        </div>

        {/* Attachment sheet — только Камера + Фото из галереи (hide-for-future) */}
        <div className={'sheet-backdrop' + (attachBackShow ? ' show' : '')} onClick={closeAttach} />
        <div className={'sheet' + (attachShow ? ' show' : '')}>
          {attachShow && (
            <>
              <div className="sheet-title"><div className="t-mini">Прикрепить</div></div>
              <button className="sheet-btn" onClick={() => onAttachAction('camera')}><Ico name="camera" size={19} color="var(--text-2)" sw={1.9} />Камера</button>
              <button className="sheet-btn" onClick={() => onAttachAction('photo')}><Ico name="image" size={19} color="var(--text-2)" sw={1.9} />Фото из галереи</button>
              {/* HIDE-FOR-FUTURE: Документ + Голосовое скрыты до появления бэкенда. */}
              <button className="sheet-btn sheet-cancel" onClick={() => onAttachAction('cancel')}>Отмена</button>
            </>
          )}
        </div>

        <div className={'toast' + (toastShow ? ' show' : '')}>{toastMsg}</div>
      </div>

      {/* Full-screen photo overlay (PWA-03) */}
      {photoOverlay && (
        <div className="photo-overlay" onClick={() => setPhotoOverlay(null)}>
          <img src={photoOverlay} alt="Просмотр фото" />
        </div>
      )}
    </div>
  );
}

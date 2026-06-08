import { useCallback, useEffect, useLayoutEffect, useRef, useState } from 'react';

/* ============================================================
   Экран «Чат» — точный перенос Chat-2.html.
   Самодостаточный компонент: стили, данные, device-рамка и вся
   интерактивная логика (список чатов + тред, свайпы, long-press,
   pull-to-refresh, композер, бот-автоответчик, шиты, Tweaks).
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
  --danger-soft: #fee2e2;

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
  --danger-soft: rgba(244, 113, 104, 0.18);

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
.t-h3 { font-size: 17px; font-weight: 600; letter-spacing: -0.2px; line-height: 1.25; color: var(--text); }
.t-h1 { font-size: 28px; font-weight: 700; letter-spacing: -0.6px; line-height: 1.1; color: var(--text); }
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
}

.view { display: flex; flex-direction: column; flex: 1; min-height: 0; }
.view-enter { animation: screen-push 0.34s cubic-bezier(0.32,0.72,0.2,1); }
@keyframes screen-push { from { transform: translateX(40px); opacity: 0; } to { transform: translateX(0); opacity: 1; } }
.view-back { animation: screen-pop 0.3s cubic-bezier(0.32,0.72,0.2,1); }
@keyframes screen-pop { from { transform: translateX(-30px); opacity: 0; } to { transform: translateX(0); opacity: 1; } }

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

/* Avatar */
.avatar {
  border-radius: 999px; display: flex; align-items: center; justify-content: center;
  font-weight: 600; flex-shrink: 0; line-height: 1; overflow: hidden;
}

.badge {
  min-width: 20px; height: 20px; padding: 0 6px; border-radius: 999px;
  background: var(--accent); color: #06120c; font-size: 11px; font-weight: 700;
  display: flex; align-items: center; justify-content: center; flex-shrink: 0;
}

/* Conversation list */
.conv-list { display: flex; flex-direction: column; gap: 8px; padding: 0 16px; }
.swipe {
  position: relative; border-radius: var(--r-lg); overflow: hidden;
}
.swipe-action {
  position: absolute; inset: 0;
  display: flex; align-items: center; justify-content: flex-end;
  gap: 7px; padding-right: 24px;
  color: #fff; font-size: 13.5px; font-weight: 700;
  background: var(--accent-deep); opacity: 0;
  transition: opacity 0.15s ease;
}
.swipe.armed .swipe-action { opacity: 1; }
.conv-card {
  position: relative; z-index: 1; display: block; width: 100%; text-align: left;
  border: 0.5px solid var(--border); border-radius: var(--r-lg);
  background: var(--surface); color: var(--text);
  cursor: pointer; touch-action: pan-y;
  transition: transform 0.26s cubic-bezier(0.32,0.72,0.2,1);
  -webkit-user-select: none; user-select: none;
}
.conv-card.removing { transition: transform 0.26s ease, opacity 0.26s ease; }

/* Thread top bar */
.thread-bar {
  flex-shrink: 0;
  padding-top: 50px; padding-bottom: 10px;
  background: color-mix(in oklab, var(--bg) 88%, transparent);
  backdrop-filter: blur(20px); -webkit-backdrop-filter: blur(20px);
  border-bottom: 0.5px solid var(--border);
}
.icon-btn {
  width: 36px; height: 36px; border-radius: 999px; border: 0;
  background: transparent; cursor: pointer; padding: 0;
  display: flex; align-items: center; justify-content: center;
}

/* Message bubbles */
.msg-stack { display: flex; flex-direction: column; gap: 3px; }
.bubble {
  max-width: 78%; padding: 9px 13px; border-radius: 18px;
  font-size: 15px; line-height: 1.4; word-break: break-word;
}
.bubble-me { background: var(--accent); color: #06120c; border-bottom-right-radius: 5px; }
.bubble-them {
  background: var(--surface); color: var(--text);
  border: 0.5px solid var(--border); border-bottom-left-radius: 5px;
}
.bubble-system {
  background: var(--surface-2); color: var(--text-2);
  border: 0.5px solid var(--border);
  font-size: 12.5px; line-height: 1.45; max-width: 290px; text-align: center;
  border-radius: 14px; font-weight: 500;
}
.bubble-meta { font-size: 11px; color: var(--text-3); font-weight: 500; }

.typing-dots { display: inline-flex; gap: 4px; align-items: center; }
.typing-dots span {
  width: 7px; height: 7px; border-radius: 999px; background: var(--text-3);
  animation: typing-bounce 1.2s ease-in-out infinite;
}
.typing-dots span:nth-child(2) { animation-delay: 0.15s; }
.typing-dots span:nth-child(3) { animation-delay: 0.3s; }
@keyframes typing-bounce {
  0%, 60%, 100% { transform: translateY(0); opacity: 0.5; }
  30% { transform: translateY(-3px); opacity: 1; }
}

.quick {
  border: 0.5px solid var(--border-strong); background: var(--surface);
  color: var(--text); padding: 8px 14px; border-radius: 999px;
  font-size: 13px; font-weight: 500; cursor: pointer;
}

/* Composer */
.composer {
  flex-shrink: 0;
  padding: 8px 8px 14px; border-top: 0.5px solid var(--border);
  background: var(--bg); display: flex; align-items: flex-end; gap: 6px;
}
.composer-field {
  flex: 1; background: var(--surface); border-radius: 22px;
  border: 0.5px solid var(--border-strong); padding: 4px 8px 4px 16px;
  display: flex; align-items: center; min-height: 40px;
}
.composer-field textarea {
  flex: 1; border: 0; outline: 0; background: transparent;
  font-size: 15px; color: var(--text); font-family: inherit;
  padding: 0; margin: 0; resize: none; line-height: 20px;
  min-height: 20px; max-height: 96px; overflow-y: auto; display: block;
}
.composer-field textarea::-webkit-scrollbar { display: none; }
.send-btn {
  width: 40px; height: 40px; border-radius: 999px; border: 0;
  display: flex; align-items: center; justify-content: center;
  cursor: pointer; flex-shrink: 0; transition: background 0.15s;
  background: var(--surface-2); color: var(--text-2);
}
.send-btn.armed { background: var(--accent); color: #06120c; }

/* Bottom tab bar */
.tabbar {
  height: 80px; padding: 8px 16px 22px;
  display: grid; grid-template-columns: repeat(4, 1fr);
  background: color-mix(in oklab, var(--surface) 85%, transparent);
  backdrop-filter: blur(20px) saturate(180%);
  -webkit-backdrop-filter: blur(20px) saturate(180%);
  border-top: 0.5px solid var(--border);
  flex-shrink: 0; position: relative; z-index: 5;
}
.tabbar-item {
  appearance: none; border: 0; background: transparent;
  display: flex; flex-direction: column; align-items: center; justify-content: center;
  gap: 3px; color: var(--text-3); font-size: 10.5px; font-weight: 600;
  letter-spacing: 0.1px; cursor: pointer; padding: 0; position: relative;
}
.tabbar-item.active { color: var(--text); }
.tabbar-item .tab-badge {
  position: absolute; top: 4px; right: calc(50% - 18px);
  min-width: 16px; height: 16px; padding: 0 4px; border-radius: 999px;
  background: var(--accent); color: #06120c; font-size: 10px; font-weight: 700;
  display: flex; align-items: center; justify-content: center;
  border: 1.5px solid var(--surface);
}

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
  position: absolute; left: 50%; bottom: 96px; transform: translate(-50%, 16px);
  z-index: 90; background: var(--text); color: var(--bg);
  font-size: 13.5px; font-weight: 600; padding: 11px 18px; border-radius: 999px;
  box-shadow: 0 12px 30px rgba(0,0,0,0.28);
  opacity: 0; pointer-events: none;
  transition: opacity 0.22s ease, transform 0.28s cubic-bezier(0.32,0.72,0.2,1);
  white-space: nowrap;
}
.toast.show { opacity: 1; transform: translate(-50%, 0); }

/* Search bar */
.searchbar {
  display: flex; align-items: center; gap: 8px;
  background: var(--surface-2); border: 0.5px solid var(--border);
  border-radius: 12px; padding: 0 12px; height: 40px;
}
.searchbar svg { color: var(--text-3); flex-shrink: 0; }
.searchbar input {
  flex: 1; border: 0; outline: 0; background: transparent;
  font-size: 15px; color: var(--text); padding: 0; min-width: 0;
}
.search-clear {
  border: 0; background: var(--border-strong); color: var(--surface);
  width: 20px; height: 20px; border-radius: 999px; cursor: pointer;
  display: flex; align-items: center; justify-content: center;
  font-size: 14px; line-height: 1; flex-shrink: 0; padding: 0;
}
/* Segmented control */
.seg { display: flex; gap: 2px; padding: 3px; background: var(--surface-2); border: 0.5px solid var(--border); border-radius: 999px; }
.seg-item {
  appearance: none; border: 0; background: transparent; cursor: pointer;
  height: 32px; border-radius: 999px; font-family: inherit; font-size: 12.5px; font-weight: 600;
  color: var(--text-2); transition: background 0.15s, color 0.15s, box-shadow 0.15s;
}
.seg-item.active { background: var(--text); color: var(--bg); box-shadow: 0 1px 4px rgba(0,0,0,0.18); }

.conv-empty { display: flex; flex-direction: column; align-items: center; text-align: center; padding: 44px 24px 24px; }

/* New-messages divider */
.unread-divider { display: flex; align-items: center; gap: 10px; margin: 12px 4px 6px; }
.unread-divider::before, .unread-divider::after { content: ''; flex: 1; height: 1px; background: color-mix(in oklab, var(--accent) 32%, transparent); }
.unread-divider span { font-size: 10.5px; font-weight: 700; letter-spacing: 0.5px; text-transform: uppercase; color: var(--accent-deep); white-space: nowrap; }

/* Message entrance */
.msg-in { animation: msg-in 0.32s cubic-bezier(0.32,0.72,0.2,1) both; }
@keyframes msg-in { from { opacity: 0; transform: translateY(10px) scale(0.98); } to { opacity: 1; transform: none; } }

/* Scroll-to-bottom */
#threadView { position: relative; }
.scroll-down {
  position: absolute; right: 14px; bottom: 78px; z-index: 6;
  width: 40px; height: 40px; border-radius: 999px;
  background: var(--surface); border: 0.5px solid var(--border-strong);
  box-shadow: var(--sh-2); cursor: pointer;
  display: flex; align-items: center; justify-content: center; color: var(--text-2);
  opacity: 0; transform: translateY(12px) scale(0.9); pointer-events: none;
  transition: opacity 0.22s ease, transform 0.22s cubic-bezier(0.32,0.72,0.2,1);
}
.scroll-down.show { opacity: 1; transform: none; pointer-events: auto; }
.scroll-down .sd-dot {
  position: absolute; top: -2px; right: -2px; width: 12px; height: 12px;
  border-radius: 999px; background: var(--accent); border: 2px solid var(--surface);
  opacity: 0; transform: scale(0.5); transition: opacity 0.2s, transform 0.2s;
}
.scroll-down.has-new .sd-dot { opacity: 1; transform: none; }

/* Day separator */
.day-sep { display: flex; justify-content: center; margin: 14px 0 8px; }
.day-sep span {
  background: var(--surface-2); border: 0.5px solid var(--border);
  color: var(--text-3); font-size: 11px; font-weight: 600; letter-spacing: 0.3px;
  padding: 4px 12px; border-radius: 999px;
}

/* Empty thread — branded spot illustration */
.thread-empty {
  display: flex; flex-direction: column; align-items: center; text-align: center;
  padding: 50px 24px 24px;
}
.thread-empty .t-h3 { font-size: 17px; margin-top: 14px; }
.thread-empty .t-small { max-width: 248px; margin-top: 6px; }
.spot { position: relative; width: 128px; height: 96px; flex-shrink: 0; }
.spot .halo {
  position: absolute; left: 19px; top: 50%; transform: translateY(-50%);
  width: 90px; height: 90px; border-radius: 50%;
  background: radial-gradient(circle, color-mix(in oklab, var(--accent) 20%, transparent) 0%, transparent 64%);
}
.spot .ring {
  position: absolute; left: 19px; top: 50%; transform: translateY(-50%);
  width: 90px; height: 90px; border-radius: 50%;
  border: 1.5px dashed color-mix(in oklab, var(--accent) 42%, transparent); opacity: 0.5;
}
.spot .ring.r2 { width: 118px; height: 118px; left: 5px; opacity: 0.24; }
.spot .scene-pos { position: absolute; left: 64px; top: 50%; transform: translate(-50%, -50%); z-index: 2; }
.spot .scene {
  width: 76px; height: 62px; background: var(--surface);
  border: 0.5px solid var(--border); border-radius: 15px;
  box-shadow: 0 10px 24px rgba(28,25,23,0.12), 0 2px 5px rgba(28,25,23,0.05);
  padding: 11px 12px; transform: rotate(-4deg); transform-origin: center;
  animation: scene-in 0.46s cubic-bezier(0.32, 1.6, 0.32, 1) both;
}
body.dark .spot .scene { box-shadow: 0 10px 24px rgba(0,0,0,0.4), 0 2px 5px rgba(0,0,0,0.3); }
@keyframes scene-in {
  0% { transform: rotate(-4deg) scale(0.5); opacity: 0; }
  60% { transform: rotate(-4deg) scale(1.06); }
  100% { transform: rotate(-4deg) scale(1); opacity: 1; }
}
.sc-chat { display: flex; flex-direction: column; gap: 6px; justify-content: center; height: 100%; }
.sc-chat i { height: 6px; border-radius: 999px; background: var(--border-strong); }
.sc-chat i.b1 { width: 72%; }
.sc-chat i.b2 { width: 48%; }
.sc-chat i.me { width: 58%; align-self: flex-end; background: var(--accent); }
.spot .chip {
  position: absolute; border-radius: 4px; background: var(--accent);
  animation: spot-float 3.4s ease-in-out infinite; z-index: 1;
}
.spot .chip.c1 { width: 9px; height: 9px; right: 24px; top: 8px; transform: rotate(16deg); background: var(--accent-deep); }
.spot .chip.c2 { width: 7px; height: 7px; right: 8px; bottom: 20px; border-radius: 50%; animation-delay: 0.7s; }
.spot .chip.c3 { width: 6px; height: 6px; left: 12px; top: 16px; border-radius: 50%; animation-delay: 1.2s; background: var(--accent-deep); }
@keyframes spot-float {
  0%, 100% { transform: translateY(0) rotate(0); }
  50% { transform: translateY(-6px) rotate(10deg); }
}

.hidden { display: none !important; }

/* Tweaks panel */
.tweaks {
  position: fixed; top: 16px; right: 16px; z-index: 1000;
  width: 252px; background: var(--surface); color: var(--text);
  border: 0.5px solid var(--border); border-radius: 18px;
  box-shadow: 0 16px 48px rgba(0,0,0,0.24), 0 2px 8px rgba(0,0,0,0.08);
  padding: 14px; font-family: var(--font); display: none;
  animation: tweaks-in 0.24s cubic-bezier(0.32,0.72,0.2,1);
}
.tweaks.show { display: block; }
@keyframes tweaks-in { from { opacity: 0; transform: translateY(-8px) scale(0.98); } to { opacity: 1; transform: none; } }
.tweaks-head { display: flex; align-items: center; justify-content: space-between; }
.tweaks-head .tw-title { font-size: 14px; font-weight: 700; letter-spacing: -0.2px; }
.tweaks-close {
  width: 26px; height: 26px; border-radius: 999px; border: 0;
  background: var(--surface-2); color: var(--text-2); cursor: pointer;
  font-size: 15px; line-height: 1; display: flex; align-items: center; justify-content: center; padding: 0;
}
.tweaks-sec { margin-top: 14px; }
.tweaks-label { font-size: 11px; font-weight: 600; letter-spacing: 0.4px; text-transform: uppercase; color: var(--text-3); margin-bottom: 8px; }
.tw-swatches { display: flex; gap: 12px; }
.tw-swatch {
  width: 30px; height: 30px; border-radius: 999px; border: 0; cursor: pointer; padding: 0;
  box-shadow: inset 0 0 0 0.5px rgba(0,0,0,0.12); transition: transform 0.12s ease;
}
.tw-swatch:active { transform: scale(0.92); }
.tw-swatch.sel { box-shadow: 0 0 0 2px var(--surface), 0 0 0 4px var(--text); }
.fade-up { animation: fade-up 0.32s cubic-bezier(0.32,0.72,0.2,1) both; }
@keyframes fade-up { from { opacity: 0; transform: translateY(8px); } to { opacity: 1; transform: translateY(0); } }
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

const PHOTO_PRESETS = {
  plan: { bg: 'linear-gradient(135deg,#fde68a 0%,#f59e0b 60%,#ea580c 100%)', label: 'PLAN.pdf', sub: 'программа на завтра' },
  'gym-selfie': { bg: 'linear-gradient(135deg,#cbd5e1 0%,#475569 70%,#1e293b 100%)', label: 'IMG_4821.jpg', sub: 'отправлено сейчас' },
};

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

/* Сообщение */
function MessageRow({ m, i, msgs, animate }) {
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
      <PhotoBubble kind={m.photo} />
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
const INITIAL_CONVS = [
  {
    id: 'c1', name: 'Администрация', sub: 'Мой зал', initials: 'МЗ',
    color: '#1c1917', bg: '#e7e5e4', isOfficial: true, unread: 1,
    last: 'Продлили твой абонемент до 28 мая 🎉', lastTime: '10:24',
    messages: [
      { id: 'm1', kind: 'system', day: 'Понедельник', body: 'Это официальный чат с администрацией. Работаем с 8:00 до 22:00.', time: '14:30' },
      { id: 'm2', from: 'them', day: 'Сегодня', body: 'Привет! Заметили, что у тебя скоро заканчивается абонемент. Хочешь, оформим продление со скидкой?', time: '10:18' },
      { id: 'm3', from: 'me', day: 'Сегодня', body: 'Привет. А какая скидка сейчас?', time: '10:21', read: true },
      { id: 'm4', from: 'them', day: 'Сегодня', body: 'До 5 мая годовой со скидкой 15% + бонусный месяц.', time: '10:22' },
      { id: 'm5', kind: 'system', day: 'Сегодня', body: 'Абонемент продлён на 30 дней до 28 мая', time: '10:24' },
      { id: 'm6', from: 'them', day: 'Сегодня', body: 'Продлили твой абонемент до 28 мая 🎉 Бонусный месяц активируется после оплаты годового.', time: '10:24' },
    ],
    botReplies: [
      'Сейчас уточню у администратора и вернусь.',
      'Принято. Если нужно срочно — позвони на ресепшен: +7 (495) 123-45-67.',
      'Передам менеджеру. Обычно отвечаем в течение 10 минут.',
    ],
  },
  {
    id: 'c2', name: 'Аня Соколова', sub: 'Личный тренер', initials: 'АС',
    color: '#f59e0b', bg: '#fef3c7', isOfficial: false, unread: 1,
    last: 'Не забудь взять ремни для тяги', lastTime: 'Вт',
    messages: [
      { id: 'a1', from: 'them', day: 'Понедельник', body: 'Привет! Готова к завтрашней тренировке?', time: '18:05' },
      { id: 'a2', from: 'me', day: 'Понедельник', body: 'Да, всё в силе. Что делаем?', time: '18:07', read: true },
      { id: 'a3', from: 'them', day: 'Понедельник', body: 'Ноги + спина. План пришлю утром.', time: '18:09' },
      { id: 'a4', kind: 'photo', from: 'them', day: 'Понедельник', body: 'Программа на завтра 👇', time: '18:10', photo: 'plan' },
      { id: 'a5', from: 'me', day: 'Понедельник', body: 'Понятно, спасибо!', time: '18:12', read: true },
      { id: 'a6', from: 'them', day: 'Вторник', body: 'Не забудь взять ремни для тяги — пригодятся.', time: '09:30' },
    ],
  },
  {
    id: 'c3', name: 'Ресепшн · уведомления', sub: 'Системные', initials: '🔔',
    color: '#0ea5e9', bg: '#dbeafe', isOfficial: true, unread: 0, isMuted: true,
    last: 'Сауна закрыта 1 мая', lastTime: '27 апр',
    messages: [
      { id: 's1', kind: 'system', day: '27 апреля', body: 'Сауна закрыта 1 мая. Зал работает по обычному графику.', time: '12:00' },
    ],
  },
  {
    id: 'c4', name: 'Ресепшен', sub: 'Расписание, абонемент, акции', initials: 'Р',
    color: 'var(--accent-deep)', bg: 'var(--accent-soft)', isOfficial: true, unread: 0,
    last: 'Начните диалог', lastTime: '', isEmpty: true,
    messages: [],
  },
];

const TWEAK_DEFAULTS = { theme: 'dark', accent: 'green' };
const ACCENTS = {
  green: null,
  blue: { a: 'oklch(0.74 0.13 235)', d: 'oklch(0.52 0.13 248)', sl: 'oklch(0.94 0.045 235)', sd: 'oklch(0.62 0.12 240 / 0.20)' },
  violet: { a: 'oklch(0.72 0.15 305)', d: 'oklch(0.54 0.15 305)', sl: 'oklch(0.94 0.05 305)', sd: 'oklch(0.64 0.13 305 / 0.20)' },
  amber: { a: 'oklch(0.79 0.14 70)', d: 'oklch(0.56 0.12 60)', sl: 'oklch(0.94 0.05 80)', sd: 'oklch(0.66 0.12 65 / 0.22)' },
};

export function ChatScreen() {
  const [convs, setConvs] = useState(INITIAL_CONVS);
  const [openId, setOpenId] = useState(null);
  const [viewAnim, setViewAnim] = useState(null); // 'enter' | 'back'
  const [convFilter, setConvFilter] = useState('all');
  const [convQuery, setConvQuery] = useState('');

  // thread
  const [typing, setTyping] = useState(false);
  const [threadDividerId, setThreadDividerId] = useState(null);
  const [animateId, setAnimateId] = useState(null);
  const [input, setInput] = useState('');

  // sheets
  const [sheetConvId, setSheetConvId] = useState(null);
  const [sheetShow, setSheetShow] = useState(false);
  const [sheetBackShow, setSheetBackShow] = useState(false);
  const [attachShow, setAttachShow] = useState(false);
  const [attachBackShow, setAttachBackShow] = useState(false);

  // toast
  const [toastMsg, setToastMsg] = useState('');
  const [toastShow, setToastShow] = useState(false);
  const toastTimer = useRef(null);

  // tweaks
  const [tweaks, setTweaks] = useState(TWEAK_DEFAULTS);
  const [tweaksShow, setTweaksShow] = useState(false);

  // refs
  const convsRef = useRef(convs); convsRef.current = convs;
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
  const botTimers = useRef([]);

  const unreadConvs = convs.filter((c) => c.unread > 0).length;

  /* ── Toast ── */
  const toast = useCallback((msg) => {
    setToastMsg(msg);
    setToastShow(true);
    clearTimeout(toastTimer.current);
    toastTimer.current = setTimeout(() => setToastShow(false), 1700);
  }, []);

  /* ── Tweaks: тема + акцент ── */
  const applyAccent = useCallback((name, theme) => {
    const s = document.body.style;
    const a = ACCENTS[name];
    if (!a) {
      s.removeProperty('--accent');
      s.removeProperty('--accent-deep');
      s.removeProperty('--accent-soft');
      return;
    }
    s.setProperty('--accent', a.a);
    s.setProperty('--accent-deep', a.d);
    s.setProperty('--accent-soft', theme === 'dark' ? a.sd : a.sl);
  }, []);

  const applyTweaks = useCallback((tw) => {
    document.body.classList.toggle('dark', tw.theme === 'dark');
    applyAccent(tw.accent, tw.theme);
    try { localStorage.setItem('myzal_theme', tw.theme); } catch (e) {}
  }, [applyAccent]);

  // первичное применение + межвкладочная синхронизация темы
  useEffect(() => {
    applyTweaks(TWEAK_DEFAULTS);
    const onStorage = (e) => {
      if (e.key === 'myzal_theme' && e.newValue) {
        setTweaks((prev) => {
          const next = { ...prev, theme: e.newValue };
          applyTweaks(next);
          return next;
        });
      }
    };
    window.addEventListener('storage', onStorage);
    return () => window.removeEventListener('storage', onStorage);
  }, [applyTweaks]);

  const setTweak = useCallback((patch) => {
    setTweaks((prev) => {
      const next = { ...prev, ...patch };
      applyTweaks(next);
      try { window.parent.postMessage({ type: '__edit_mode_set_keys', edits: patch }, '*'); } catch (e) {}
      return next;
    });
  }, [applyTweaks]);

  // host protocol (edit mode)
  useEffect(() => {
    const onMessage = (e) => {
      const t = e.data && e.data.type;
      if (t === '__activate_edit_mode') setTweaksShow(true);
      else if (t === '__deactivate_edit_mode') setTweaksShow(false);
    };
    window.addEventListener('message', onMessage);
    try { window.parent.postMessage({ type: '__edit_mode_available' }, '*'); } catch (e) {}
    return () => window.removeEventListener('message', onMessage);
  }, []);

  /* ── Глобальная навигация (data-go / data-toast) ── */
  useEffect(() => {
    const onClick = (e) => {
      const go = e.target.closest('[data-go]');
      if (go && go.dataset.go) { window.location.href = go.dataset.go; return; }
      const tt = e.target.closest('[data-toast]');
      if (tt && tt.dataset.toast) toast(tt.dataset.toast);
    };
    document.addEventListener('click', onClick);
    return () => document.removeEventListener('click', onClick);
  }, [toast]);

  /* ── Список: фильтр/поиск ── */
  const visibleConvs = () => {
    let arr = convs.slice();
    if (convFilter === 'unread') arr = arr.filter((c) => c.unread > 0);
    const q = convQuery.trim().toLowerCase();
    if (q) arr = arr.filter((c) => (c.name + ' ' + c.sub + ' ' + c.last).toLowerCase().includes(q));
    return arr;
  };

  /* ── Mute ── */
  const toggleMute = useCallback((id) => {
    let muted = false;
    setConvs((prev) => prev.map((c) => {
      if (c.id !== id) return c;
      muted = !c.isMuted;
      return { ...c, isMuted: !c.isMuted };
    }));
    setTimeout(() => toast(muted ? 'Чат заглушён' : 'Уведомления включены'), 0);
  }, [toast]);

  /* ── Long-press sheet ── */
  const openSheet = useCallback((id) => {
    setSheetConvId(id);
    setSheetBackShow(true);
    requestAnimationFrame(() => setSheetShow(true));
  }, []);
  const closeSheet = useCallback(() => { setSheetShow(false); setSheetBackShow(false); }, []);

  /* ── Thread open/close ── */
  const openThread = useCallback((id) => {
    const conv = convsRef.current.find((c) => c.id === id);
    if (!conv) return;
    const incoming = conv.messages.filter((m) => m.from === 'them');
    const n = Math.min(conv.unread || 0, incoming.length);
    setThreadDividerId(n > 0 ? incoming[incoming.length - n].id : null);
    setTyping(false);
    setAnimateId(null);
    setInput('');
    if (conv.unread) setConvs((prev) => prev.map((c) => (c.id === id ? { ...c, unread: 0 } : c)));
    setViewAnim('enter');
    setOpenId(id);
    stickRef.current = true;
  }, []);

  const closeThread = useCallback(() => {
    botTimers.current.forEach((t) => clearTimeout(t));
    botTimers.current = [];
    if (scrollDownBtnRef.current) scrollDownBtnRef.current.classList.remove('show', 'has-new');
    setOpenId(null);
    setThreadDividerId(null);
    setAnimateId(null);
    setTyping(false);
    setViewAnim('back');
  }, []);

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

  /* ── Push message ── */
  const pushMsg = useCallback((text, from, kind) => {
    const id = openIdRef.current;
    const conv = convsRef.current.find((c) => c.id === id);
    if (!conv) return;
    const sc = threadScrollerRef.current;
    const wasNear = sc ? sc.scrollHeight - sc.scrollTop - sc.clientHeight < 140 : true;
    const msg = { id: 'new-' + Date.now() + Math.random(), from: from || 'me', day: 'Сегодня', body: text, time: 'сейчас', read: false };
    if (kind) msg.kind = kind;
    let last = text;
    if (kind === 'photo') { msg.photo = text.startsWith('photo:') ? text.split(':')[1] : 'gym-selfie'; msg.body = ''; last = '📷 Фото'; }
    setConvs((prev) => prev.map((c) => (c.id === id ? { ...c, messages: [...c.messages, msg], last, lastTime: 'сейчас' } : c)));
    setAnimateId(msg.id);
    const mine = (from || 'me') === 'me';
    stickRef.current = mine || wasNear;
    if (!mine && !wasNear && scrollDownBtnRef.current) scrollDownBtnRef.current.classList.add('has-new');
  }, []);

  const setTypingFn = useCallback((v) => {
    const sc = threadScrollerRef.current;
    const nearBottom = sc ? sc.scrollHeight - sc.scrollTop - sc.clientHeight < 140 : true;
    stickRef.current = nearBottom;
    setTyping(v);
  }, []);

  const sendMessage = useCallback((text) => {
    const t = (text != null ? text : inputRef.current).trim();
    if (!t) return;
    pushMsg(t, 'me');
    setInput('');
    const conv = convsRef.current.find((c) => c.id === openIdRef.current);
    if (conv && conv.id === 'c1' && conv.botReplies && conv.botReplies.length) {
      botTimers.current.push(setTimeout(() => setTypingFn(true), 600));
      const reply = conv.botReplies[Math.floor(Math.random() * conv.botReplies.length)];
      botTimers.current.push(setTimeout(() => { setTypingFn(false); pushMsg(reply, 'them'); }, 2200));
    }
  }, [pushMsg, setTypingFn]);

  /* ── Thread: автоскролл к низу + scroll-down состояние ── */
  useLayoutEffect(() => {
    if (openId == null) return;
    if (stickRef.current) {
      const sc = threadScrollerRef.current;
      if (sc) sc.scrollTop = sc.scrollHeight;
      stickRef.current = false;
    }
    updateScrollDown();
  }, [openId, convs, typing, threadDividerId, updateScrollDown]);

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
        toggleMute(a.id);
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
          openSheet(id);
        }
      }, 450),
    };
    card.style.transition = 'none';
  };

  /* ── Pull to refresh (список) ── */
  const onListPointerDown = (e) => {
    const p = pullRef.current;
    const a = activeRef.current;
    if (p.loading || (a && a.moved)) return;
    const sc = listScrollerRef.current;
    if (sc.scrollTop <= 0) { p.pStart = { x: e.clientX, y: e.clientY }; p.pulling = true; }
  };
  const onListPointerMove = (e) => {
    const p = pullRef.current;
    if (!p.pulling || p.loading || !p.pStart) return;
    const sc = listScrollerRef.current;
    const shift = listShiftRef.current;
    const ptr = ptrRef.current;
    const dy = e.clientY - p.pStart.y;
    const dx = e.clientX - p.pStart.x;
    if (dy <= 0 || Math.abs(dx) > Math.abs(dy)) return;
    if (sc.scrollTop > 0) { p.pulling = false; return; }
    const pull = Math.min(64, dy * 0.5);
    shift.style.transition = 'none';
    shift.style.transform = 'translateY(' + pull + 'px)';
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
    const shift = listShiftRef.current;
    const ptr = ptrRef.current;
    shift.style.transition = 'transform 0.3s cubic-bezier(0.32,0.72,0.2,1)';
    if (pull >= 44) {
      p.loading = true;
      shift.style.transform = 'translateY(44px)';
      ptr.classList.add('spin');
      ptr.style.opacity = 1;
      ptr.querySelector('svg').style.transform = '';
      setTimeout(() => {
        shift.style.transform = 'translateY(0)';
        ptr.classList.remove('spin');
        ptr.style.opacity = 0;
        p.loading = false;
        toast('Обновлено');
      }, 850);
    } else {
      shift.style.transform = 'translateY(0)';
      ptr.style.opacity = 0;
    }
  };

  /* ── Sheet actions ── */
  const sheetConv = convs.find((c) => c.id === sheetConvId) || null;
  const onSheetAction = (a) => {
    const id = sheetConvId;
    closeSheet();
    if (a === 'read') setConvs((prev) => prev.map((c) => (c.id === id ? { ...c, unread: c.unread ? 0 : 1 } : c)));
    else if (a === 'mute') toggleMute(id);
    else if (a === 'archive') { setConvs((prev) => prev.filter((c) => c.id !== id)); toast('Чат в архиве'); }
    else if (a === 'delete') { setConvs((prev) => prev.filter((c) => c.id !== id)); toast('Чат удалён'); }
  };

  /* ── Attach sheet ── */
  const openAttach = () => { setAttachBackShow(true); requestAnimationFrame(() => setAttachShow(true)); };
  const closeAttach = () => { setAttachShow(false); setAttachBackShow(false); };
  const onAttachAction = (a) => {
    closeAttach();
    if (a === 'photo' || a === 'camera') pushMsg('photo:gym-selfie', 'me', 'photo');
    else if (a === 'file') pushMsg('photo:plan', 'me', 'photo');
    else if (a === 'voice') pushMsg('🎤 Голосовое · 0:08', 'me');
  };

  /* ── Composer handlers ── */
  const armed = input.trim().length > 0;
  const onSendClick = () => {
    if (input.trim()) sendMessage();
    else pushMsg('🎤 Голосовое · 0:05', 'me');
  };
  const onKeyDown = (e) => {
    if (e.key === 'Enter' && !e.shiftKey) { e.preventDefault(); sendMessage(); }
  };

  const data = visibleConvs();
  const searching = convQuery.trim().length > 0;
  const conv = convs.find((c) => c.id === openId) || null;

  /* ── Рендер карточки чата ── */
  const ConvCard = (c) => {
    const lastColor = c.isEmpty ? 'var(--accent-deep)' : c.unread ? 'var(--text)' : 'var(--text-2)';
    return (
      <div className="swipe" data-id={c.id} key={c.id}>
        <div className="swipe-action" onClick={() => toggleMute(c.id)}>
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
      out.push(<MessageRow key={m.id} m={m} i={i} msgs={conv.messages} animate={m.id === animateId} />);
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

  const showQuick = conv && conv.id === 'c1' && !typing && conv.messages.length > 0;
  const statusText = conv ? (typing ? 'печатает…' : conv.sub + (conv.isOfficial ? ' · ✓ верифицирован' : ' · в сети')) : '';

  return (
    <>
      <style>{CSS}</style>
      <div className="stage">
        <div className="device" data-screen-label="Чат">
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
                      {data.length ? (
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

                <div className="tabbar" role="tablist" aria-label="Основная навигация">
                  <button className="tabbar-item" data-go="Home.html" type="button">
                    <svg width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.7" strokeLinejoin="round"><path d="M3 11l9-7 9 7v9a1 1 0 01-1 1h-5v-7h-6v7H4a1 1 0 01-1-1v-9z" /></svg>
                    <span>Главная</span>
                  </button>
                  <button className="tabbar-item" data-go="Запись.html" type="button">
                    <svg width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.7" strokeLinecap="round"><rect x="3" y="5" width="18" height="16" rx="3" /><path d="M3 10h18M8 3v4M16 3v4" /></svg>
                    <span>Запись</span>
                  </button>
                  <button className="tabbar-item active" type="button" aria-selected="true">
                    <div style={{ position: 'relative' }}>
                      <svg width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.9" strokeLinejoin="round"><path d="M4 5a2 2 0 012-2h12a2 2 0 012 2v9a2 2 0 01-2 2h-7l-4 4v-4H6a2 2 0 01-2-2V5z" /></svg>
                      {unreadConvs > 0 && <span className="tab-badge">{unreadConvs}</span>}
                    </div>
                    <span>Чат</span>
                  </button>
                  <button className="tabbar-item" data-go="Profile.html" type="button">
                    <svg width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.7" strokeLinecap="round"><circle cx="12" cy="8" r="4" /><path d="M4 21c0-4 4-7 8-7s8 3 8 7" /></svg>
                    <span>Профиль</span>
                  </button>
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
                        <button key={q} className="quick press" onClick={() => sendMessage(q)}>{q}</button>
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

              {/* Attachment sheet */}
              <div className={'sheet-backdrop' + (attachBackShow ? ' show' : '')} onClick={closeAttach} />
              <div className={'sheet' + (attachShow ? ' show' : '')}>
                {attachShow && (
                  <>
                    <div className="sheet-title"><div className="t-mini">Прикрепить</div></div>
                    <button className="sheet-btn" onClick={() => onAttachAction('camera')}><Ico name="camera" size={19} color="var(--text-2)" sw={1.9} />Камера</button>
                    <button className="sheet-btn" onClick={() => onAttachAction('photo')}><Ico name="image" size={19} color="var(--text-2)" sw={1.9} />Фото из галереи</button>
                    <button className="sheet-btn" onClick={() => onAttachAction('file')}><Ico name="file" size={19} color="var(--text-2)" sw={1.9} />Документ</button>
                    <button className="sheet-btn" onClick={() => onAttachAction('voice')}><Ico name="mic" size={19} color="var(--text-2)" sw={1.9} />Голосовое</button>
                    <button className="sheet-btn sheet-cancel" onClick={() => onAttachAction('cancel')}>Отмена</button>
                  </>
                )}
              </div>

              <div className={'toast' + (toastShow ? ' show' : '')}>{toastMsg}</div>
              <div className="home-indicator" />
            </div>
          </div>
        </div>
      </div>

      {/* Tweaks panel */}
      <div className={'tweaks' + (tweaksShow ? ' show' : '')} role="dialog" aria-label="Tweaks">
        <div className="tweaks-head">
          <span className="tw-title">Tweaks</span>
          <button className="tweaks-close" aria-label="Закрыть" onClick={() => { setTweaksShow(false); try { window.parent.postMessage({ type: '__edit_mode_dismissed' }, '*'); } catch (e) {} }}>✕</button>
        </div>
        <div className="tweaks-sec">
          <div className="tweaks-label">Тема</div>
          <div className="seg" style={{ width: '100%' }}>
            <button className={'seg-item' + (tweaks.theme === 'light' ? ' active' : '')} style={{ flex: 1 }} type="button" onClick={() => setTweak({ theme: 'light' })}>Светлая</button>
            <button className={'seg-item' + (tweaks.theme === 'dark' ? ' active' : '')} style={{ flex: 1 }} type="button" onClick={() => setTweak({ theme: 'dark' })}>Тёмная</button>
          </div>
        </div>
        <div className="tweaks-sec">
          <div className="tweaks-label">Акцент</div>
          <div className="tw-swatches">
            <button className={'tw-swatch' + (tweaks.accent === 'green' ? ' sel' : '')} style={{ background: '#2dd4a4' }} aria-label="Зелёный" onClick={() => setTweak({ accent: 'green' })} />
            <button className={'tw-swatch' + (tweaks.accent === 'blue' ? ' sel' : '')} style={{ background: 'oklch(0.74 0.13 235)' }} aria-label="Синий" onClick={() => setTweak({ accent: 'blue' })} />
            <button className={'tw-swatch' + (tweaks.accent === 'violet' ? ' sel' : '')} style={{ background: 'oklch(0.72 0.15 305)' }} aria-label="Фиолетовый" onClick={() => setTweak({ accent: 'violet' })} />
            <button className={'tw-swatch' + (tweaks.accent === 'amber' ? ' sel' : '')} style={{ background: 'oklch(0.79 0.14 70)' }} aria-label="Янтарный" onClick={() => setTweak({ accent: 'amber' })} />
          </div>
        </div>
      </div>
    </>
  );
}

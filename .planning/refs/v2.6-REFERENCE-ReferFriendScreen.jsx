import { useCallback, useEffect, useRef, useState } from 'react';

/* ============================================================
   Экран «Приведи друга» — точный перенос «Приведи друга.html».
   Самодостаточный компонент: стили, разметка, device-рамка и вся
   интерактивная логика (тема, тосты, конфетти, count-up награды,
   трекер вех, копирование промокода/ссылки, быстрые каналы,
   нативный share).
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
  padding-top: 44px;
  transition: background 0.3s ease;
}

/* Top bar */
.topbar {
  height: 54px; padding: 0 14px;
  display: flex; align-items: center; gap: 10px;
  flex-shrink: 0;
  position: relative; z-index: 6;
}
.topbar-btn {
  width: 38px; height: 38px; border-radius: 999px;
  border: 0.5px solid var(--border); background: var(--surface);
  box-shadow: var(--sh-1);
  display: inline-flex; align-items: center; justify-content: center;
  color: var(--text); cursor: pointer; padding: 0; flex-shrink: 0;
  transition: transform 0.12s ease, background 0.15s;
}
.topbar-btn:active { transform: scale(0.94); background: var(--surface-2); }
.topbar-title { flex: 1; text-align: center; font-size: 16px; font-weight: 650; letter-spacing: -0.2px; }

/* Scroll body */
.scroller {
  flex: 1; overflow-y: auto; -webkit-overflow-scrolling: touch;
  padding: 4px 16px 0;
}
.scroller::-webkit-scrollbar { display: none; }

.card {
  background: var(--surface);
  border: 0.5px solid var(--border);
  border-radius: var(--r-lg);
  box-shadow: var(--sh-2);
}

.press { transition: transform 0.1s ease, background 0.15s ease; cursor: pointer; }
.press:active { transform: scale(0.97); }

.fade-up { animation: fade-up 0.4s cubic-bezier(0.32,0.72,0.2,1) both; }
@keyframes fade-up { from { opacity: 0; transform: translateY(10px); } to { opacity: 1; transform: translateY(0); } }
.d1 { animation-delay: 0.05s; } .d2 { animation-delay: 0.11s; }
.d3 { animation-delay: 0.17s; } .d4 { animation-delay: 0.23s; } .d5 { animation-delay: 0.29s; }

/* ── Spot illustration (per CLAUDE.md system) ── */
.spot {
  position: relative;
  width: 168px; height: 150px;
  margin: 6px auto 0;
  flex-shrink: 0;
}
.spot .halo {
  position: absolute; left: 50%; top: 50%; transform: translate(-50%,-50%);
  width: 130px; height: 130px; border-radius: 50%;
  background: radial-gradient(circle, color-mix(in oklab, var(--accent) 22%, transparent) 0%, transparent 64%);
}
.spot .ring {
  position: absolute; left: 50%; top: 50%; transform: translate(-50%,-50%);
  width: 128px; height: 128px; border-radius: 50%;
  border: 1.5px dashed color-mix(in oklab, var(--accent) 42%, transparent);
  opacity: 0.5;
}
.spot .ring.r2 { width: 164px; height: 164px; opacity: 0.22; }
.spot .chip {
  position: absolute; border-radius: 4px;
  background: var(--accent);
  animation: spot-float 3.4s ease-in-out infinite;
  z-index: 1;
}
.spot .chip.c1 { width: 11px; height: 11px; right: 24px; top: 16px; transform: rotate(16deg); background: var(--accent-deep); }
.spot .chip.c2 { width: 8px; height: 8px; right: 14px; bottom: 34px; border-radius: 50%; animation-delay: 0.7s; }
.spot .chip.c3 { width: 7px; height: 7px; left: 16px; top: 30px; border-radius: 50%; animation-delay: 1.2s; background: var(--accent-deep); }
.spot .chip.c4 { width: 9px; height: 9px; left: 22px; bottom: 24px; transform: rotate(-12deg); animation-delay: 1.6s; }
@keyframes spot-float {
  0%, 100% { transform: translateY(0) rotate(0); }
  50% { transform: translateY(-7px) rotate(10deg); }
}
.spot .scene-pos {
  position: absolute; left: 50%; top: 50%;
  transform: translate(-50%, -50%);
  z-index: 2;
}
.spot .scene {
  background: var(--surface);
  border: 0.5px solid var(--border);
  border-radius: 18px;
  box-shadow: 0 14px 30px rgba(28,25,23,0.13), 0 3px 7px rgba(28,25,23,0.06);
  padding: 16px 18px;
  transform: rotate(-3deg);
  transform-origin: center;
  animation: scene-in 0.5s cubic-bezier(0.32, 1.6, 0.32, 1) both;
}
body.dark .spot .scene { box-shadow: 0 14px 34px rgba(0,0,0,0.5); }
@keyframes scene-in {
  0% { transform: rotate(-3deg) scale(0.5); opacity: 0; }
  60% { transform: rotate(-3deg) scale(1.05); }
  100% { transform: rotate(-3deg) scale(1); opacity: 1; }
}

/* Scene — two friends + connecting plus */
.sc-friends { display: flex; align-items: center; gap: 10px; }
.sc-friends .person { display: flex; flex-direction: column; align-items: center; gap: 7px; }
.sc-friends .av {
  width: 38px; height: 38px; border-radius: 50%;
  display: flex; align-items: flex-end; justify-content: center;
  overflow: hidden;
}
.sc-friends .av.me { background: var(--accent); }
.sc-friends .av.fr { background: var(--accent-soft); border: 1.5px dashed color-mix(in oklab, var(--accent) 55%, transparent); }
.sc-friends .av .head { width: 14px; height: 14px; border-radius: 50%; margin-bottom: 2px; }
.sc-friends .av.me .head { background: #06301f; }
.sc-friends .av.fr .head { background: color-mix(in oklab, var(--accent-deep) 60%, transparent); }
.sc-friends .av .body { display: none; }
.sc-friends .lbl { display: flex; flex-direction: column; gap: 4px; align-items: center; }
.sc-friends .lbl i { height: 4px; border-radius: 999px; background: var(--border-strong); }
.sc-friends .person.me .lbl i:first-child { width: 30px; background: var(--accent-deep); }
.sc-friends .person.fr .lbl i:first-child { width: 24px; }
.sc-friends .lbl i:last-child { width: 16px; background: var(--border); }
.sc-friends .plus {
  width: 24px; height: 24px; border-radius: 50%;
  background: var(--accent-deep); color: #fff;
  display: flex; align-items: center; justify-content: center;
  align-self: flex-start; margin-top: 8px;
  box-shadow: 0 3px 8px color-mix(in oklab, var(--accent) 55%, transparent);
}
.sc-friends .plus svg { width: 13px; height: 13px; }

.hero-title {
  text-align: center;
  margin-top: 16px;
  font-size: 27px; font-weight: 750;
  letter-spacing: -0.7px; line-height: 1.12;
  text-wrap: balance;
}
.hero-sub {
  text-align: center;
  margin: 9px auto 0;
  font-size: 14.5px; line-height: 1.5;
  color: var(--text-2); text-wrap: pretty;
  max-width: 290px;
}

/* Reward rows — both sides win */
.rewards {
  margin-top: 22px;
  padding: 6px;
  display: flex; flex-direction: column; gap: 6px;
  position: relative;
}
.rwd {
  display: flex; align-items: center; gap: 13px;
  padding: 13px 14px;
  border-radius: 15px;
}
.rwd.you { background: color-mix(in oklab, var(--accent-soft) 65%, var(--surface)); }
.rwd.friend { background: var(--surface-2); }
.rwd .r-ic {
  width: 38px; height: 38px; border-radius: 11px; flex-shrink: 0;
  display: inline-flex; align-items: center; justify-content: center;
}
.rwd.you .r-ic { background: var(--accent); color: #06120c; }
.rwd.friend .r-ic { background: var(--surface); border: 0.5px solid var(--border); color: var(--accent-deep); }
.rwd .r-ic svg { width: 20px; height: 20px; }
.rwd .r-text { flex: 1; min-width: 0; display: flex; flex-direction: column; gap: 2px; }
.rwd .r-who { font-size: 14px; font-weight: 700; color: var(--text); letter-spacing: -0.2px; }
.rwd .r-note { font-size: 11.5px; color: var(--text-3); line-height: 1.3; }
.rwd .r-amt {
  flex-shrink: 0; text-align: right;
  font-size: 19px; font-weight: 800; letter-spacing: -0.6px; line-height: 1;
  color: var(--text);
}
.rwd.you .r-amt { color: var(--accent-deep); }

/* Referral code card */
.code-card { margin-top: 14px; padding: 16px; }
.code-box {
  margin-top: 12px;
  display: flex; align-items: center; gap: 10px;
  background: var(--surface-2);
  border: 1px dashed var(--border-strong);
  border-radius: 14px;
  padding: 13px 14px;
}
.code-box .code {
  flex: 1; min-width: 0;
  font-family: ui-monospace, "SF Mono", "JetBrains Mono", Menlo, monospace;
  font-size: 19px; font-weight: 700; letter-spacing: 1px;
  color: var(--text);
  overflow: hidden; text-overflow: ellipsis; white-space: nowrap;
}
.copy-btn {
  flex-shrink: 0;
  height: 36px; padding: 0 14px; border-radius: 999px;
  border: 0; background: var(--text); color: var(--bg);
  font-size: 13px; font-weight: 650; cursor: pointer;
  display: inline-flex; align-items: center; gap: 6px;
  transition: transform 0.1s ease, background 0.2s ease;
}
.copy-btn svg { width: 14px; height: 14px; }
.copy-btn:active { transform: scale(0.95); }
.copy-btn.done { background: var(--accent); color: #06120c; }

/* Referral link line */
.link-line {
  margin-top: 10px;
  display: flex; align-items: center; gap: 8px;
  padding: 0 2px;
}
.link-line .lk-ic { color: var(--text-3); flex-shrink: 0; display: inline-flex; }
.link-line .lk-ic svg { width: 14px; height: 14px; }
.link-line .lk-url {
  flex: 1; min-width: 0;
  font-family: ui-monospace, "SF Mono", "JetBrains Mono", Menlo, monospace;
  font-size: 12.5px; color: var(--text-2);
  overflow: hidden; text-overflow: ellipsis; white-space: nowrap;
}
/* Quick share channels */
.share-row {
  margin-top: 13px;
  display: grid; grid-template-columns: repeat(3, 1fr); gap: 8px;
}
.share-chip {
  appearance: none; cursor: pointer;
  display: inline-flex; flex-direction: column; align-items: center; gap: 6px;
  padding: 11px 6px 10px;
  background: var(--surface-2); border: 0.5px solid var(--border);
  border-radius: 14px; color: var(--text);
  transition: transform 0.1s ease, background 0.15s ease, border-color 0.15s ease;
}
.share-chip:active { transform: scale(0.96); background: var(--bg); }
.share-chip .sc-ic {
  width: 30px; height: 30px; border-radius: 999px;
  background: var(--surface); border: 0.5px solid var(--border);
  display: inline-flex; align-items: center; justify-content: center;
  color: var(--accent-deep);
}
.share-chip .sc-ic svg { width: 17px; height: 17px; }
.share-chip .sc-lbl { font-size: 11.5px; font-weight: 600; color: var(--text-2); letter-spacing: -0.1px; }

/* Steps */
.steps { margin-top: 24px; }
.steps-head { padding: 0 4px 10px; }
.step {
  display: flex; gap: 14px; align-items: flex-start;
  padding: 4px 4px;
  position: relative;
}
.step + .step { margin-top: 4px; }
.step .s-num {
  width: 30px; height: 30px; border-radius: 999px; flex-shrink: 0;
  background: var(--accent-soft); color: var(--accent-deep);
  display: inline-flex; align-items: center; justify-content: center;
  font-size: 13px; font-weight: 750;
  position: relative; z-index: 2;
}
.step .s-line {
  position: absolute; left: 18.5px; top: 32px; bottom: -6px;
  width: 2px; background: var(--border);
}
.step:last-child .s-line { display: none; }
.step .s-body { flex: 1; padding-top: 3px; }
.step .s-title { font-size: 14.5px; font-weight: 650; color: var(--text); letter-spacing: -0.1px; }
.step .s-desc { margin-top: 2px; font-size: 12.5px; line-height: 1.4; color: var(--text-3); }

/* Progress / earned */
.earned { margin-top: 24px; padding: 16px; }
.earned .e-top { display: flex; align-items: flex-end; justify-content: space-between; gap: 12px; }
.earned .e-val { font-size: 30px; font-weight: 800; letter-spacing: -1px; line-height: 0.9; color: var(--text); }
.earned .e-bar-track {
  margin-top: 14px; height: 7px; border-radius: 999px;
  background: var(--surface-2); overflow: hidden;
  border: 0.5px solid var(--border);
}
.earned .e-bar-fill {
  height: 100%; border-radius: 999px; background: var(--accent);
  width: 0; transition: width 0.9s cubic-bezier(0.32,0.72,0.2,1);
}

/* Friends list */
.friends { margin-top: 14px; padding: 0; overflow: hidden; }
.fr-row { display: flex; align-items: center; gap: 12px; padding: 13px 16px; }
.fr-row + .fr-row { border-top: 0.5px solid var(--border); }
.fr-row .fr-av {
  width: 38px; height: 38px; border-radius: 999px; flex-shrink: 0;
  display: inline-flex; align-items: center; justify-content: center;
  font-size: 14px; font-weight: 700; color: #fff;
}
.fr-row .fr-main { flex: 1; min-width: 0; }
.fr-row .fr-name { font-size: 14.5px; font-weight: 600; color: var(--text); letter-spacing: -0.1px; }
.fr-row .fr-date { font-size: 11.5px; color: var(--text-3); margin-top: 1px; }
.fr-badge {
  flex-shrink: 0; display: inline-flex; align-items: center; gap: 5px;
  height: 24px; padding: 0 10px; border-radius: 999px;
  font-size: 11px; font-weight: 700; letter-spacing: 0.2px;
}
.fr-badge.joined { background: var(--accent-soft); color: var(--accent-deep); }
.fr-badge.pending { background: var(--warn-soft); color: #b9791f; }
.fr-badge svg { width: 11px; height: 11px; }
body.dark .fr-badge.pending { color: var(--warn); }

/* Sticky CTA footer */
.footer {
  flex-shrink: 0;
  padding: 12px 16px 14px;
  background: color-mix(in oklab, var(--bg) 80%, transparent);
  backdrop-filter: blur(16px) saturate(180%);
  -webkit-backdrop-filter: blur(16px) saturate(180%);
  border-top: 0.5px solid var(--border);
  position: relative; z-index: 5;
}
.btn {
  appearance: none; border: 0;
  background: var(--accent); color: #06120c;
  height: 54px; padding: 0 22px;
  border-radius: var(--r-pill);
  font-size: 16px; font-weight: 700; letter-spacing: -0.2px;
  cursor: pointer;
  display: inline-flex; align-items: center; justify-content: center; gap: 9px;
  transition: transform 0.12s ease, opacity 0.15s ease;
  width: 100%;
  box-shadow: 0 12px 26px -12px color-mix(in oklab, var(--accent) 80%, transparent);
}
.btn:active { transform: scale(0.98); }
.btn svg { width: 19px; height: 19px; }
.btn { position: relative; overflow: hidden; }
.btn::after {
  content: ""; position: absolute; top: 0; left: -60%;
  width: 45%; height: 100%;
  background: linear-gradient(100deg, transparent, rgba(255,255,255,0.5), transparent);
  transform: skewX(-18deg); pointer-events: none;
  animation: shimmer 4.8s ease-in-out infinite;
}
@keyframes shimmer { 0% { left: -60%; } 16% { left: 135%; } 100% { left: 135%; } }
@media (prefers-reduced-motion: reduce) { .btn::after { display: none; } }

/* Gamified milestone tracker */
.milestones {
  position: relative; margin-top: 16px;
  display: flex; align-items: center; justify-content: space-between;
  padding: 0 1px;
}
.ms-track {
  position: absolute; left: 15px; right: 15px; top: 50%;
  transform: translateY(-50%); height: 4px; border-radius: 999px;
  background: var(--surface-2); border: 0.5px solid var(--border);
  overflow: hidden;
}
body.dark .ms-track { background: var(--border-strong); border-color: var(--border-strong); }
.ms-track i {
  display: block; height: 100%; width: 0; border-radius: 999px;
  background: var(--accent);
  transition: width 1.1s cubic-bezier(0.32,0.72,0.2,1) 0.25s;
}
.ms-node {
  position: relative; z-index: 2; flex-shrink: 0;
  width: 30px; height: 30px; border-radius: 50%;
  background: var(--surface); border: 1.5px solid var(--border-strong);
  color: var(--text-3); font-size: 12px; font-weight: 700;
  display: inline-flex; align-items: center; justify-content: center;
  transition: background 0.3s, border-color 0.3s, color 0.3s, box-shadow 0.3s;
}
.ms-node svg { width: 15px; height: 15px; }
.ms-node.done {
  background: var(--accent); border-color: var(--accent); color: #06120c;
  box-shadow: 0 3px 10px color-mix(in oklab, var(--accent) 40%, transparent);
}
.ms-node.prize {
  border-style: dashed; border-color: color-mix(in oklab, var(--accent) 55%, transparent);
  color: var(--accent-deep); background: var(--accent-soft);
}
.ms-node.pop { animation: ms-pop 0.42s cubic-bezier(0.32,1.6,0.32,1); }
@keyframes ms-pop { 0% { transform: scale(0.4); } 60% { transform: scale(1.14); } 100% { transform: scale(1); } }

/* Confetti */
.confetti {
  position: absolute; width: 8px; height: 8px; z-index: 55;
  pointer-events: none; border-radius: 2px;
  animation: confetti-fly 0.95s cubic-bezier(0.2,0.7,0.3,1) forwards;
}
@keyframes confetti-fly {
  0%   { transform: translate(-50%,-50%) scale(0.5) rotate(0); opacity: 1; }
  70%  { opacity: 1; }
  100% { transform: translate(calc(-50% + var(--dx)), calc(-50% + var(--dy) + 70px)) scale(1) rotate(var(--rot)); opacity: 0; }
}

/* Toast */
.toast {
  position: absolute; left: 50%; bottom: 92px; transform: translate(-50%, 16px);
  z-index: 60; background: var(--text); color: var(--bg);
  font-size: 13.5px; font-weight: 600; padding: 11px 18px; border-radius: 999px;
  box-shadow: 0 12px 30px rgba(0,0,0,0.28);
  opacity: 0; pointer-events: none;
  transition: opacity 0.22s ease, transform 0.28s cubic-bezier(0.32,0.72,0.2,1);
  white-space: nowrap;
}
.toast.show { opacity: 1; transform: translate(-50%, 0); }
`;

/* ---------- Данные / константы (как в оригинале) ---------- */
const CODE = 'САША-1000';
const LINK = 'myzal.app/i/САША-1000';
const FULL_LINK = 'https://' + LINK;
const INVITE_TEXT = 'Зову тебя в «Мой зал»! Промокод ' + CODE + ' — 14 дней в подарок.';
const EARNED_TO = 2000;
const CONFETTI_COLORS = ['var(--accent)', 'var(--accent-deep)', '#a7f3d6'];

/* count-up числа награды (ease-out cubic, ru-RU группировка) */
function countUp(el, to, dur) {
  if (!el) return;
  const start = performance.now();
  function tick(t) {
    const p = Math.min(1, (t - start) / dur);
    const eased = 1 - Math.pow(1 - p, 3);
    el.textContent = Math.round(to * eased).toLocaleString('ru-RU');
    if (p < 1) requestAnimationFrame(tick);
    else el.textContent = to.toLocaleString('ru-RU');
  }
  requestAnimationFrame(tick);
}

export function ReferFriendScreen() {
  /* Toast */
  const [toastMsg, setToastMsg] = useState('');
  const [toastShow, setToastShow] = useState(false);
  const toastTimer = useRef(null);

  /* Состояния «скопировано» */
  const [copied, setCopied] = useState(false);
  const [linkCopied, setLinkCopied] = useState(false);
  const copyResetTimer = useRef(null);
  const linkResetTimer = useRef(null);

  /* Refs для императивной анимации/конфетти */
  const screenRef = useRef(null);
  const earnedValRef = useRef(null);
  const msFillRef = useRef(null);
  const milestonesRef = useRef(null);
  const shareBtnRef = useRef(null);

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

  /* ── Конфетти ── */
  const confetti = useCallback((originEl, count) => {
    if (!originEl || !screenRef.current) return;
    if (matchMedia('(prefers-reduced-motion: reduce)').matches) return;
    const r = originEl.getBoundingClientRect();
    const s = screenRef.current.getBoundingClientRect();
    const cx = r.left + r.width / 2 - s.left;
    const cy = r.top + r.height / 2 - s.top;
    for (let i = 0; i < (count || 14); i++) {
      const p = document.createElement('span');
      p.className = 'confetti';
      const ang = Math.random() * Math.PI * 2;
      const dist = 38 + Math.random() * 72;
      p.style.left = cx + 'px';
      p.style.top = cy + 'px';
      p.style.background = CONFETTI_COLORS[i % CONFETTI_COLORS.length];
      if (i % 3 === 0) p.style.borderRadius = '50%';
      p.style.setProperty('--dx', Math.cos(ang) * dist + 'px');
      p.style.setProperty('--dy', Math.sin(ang) * dist - 26 + 'px');
      p.style.setProperty('--rot', Math.random() * 380 - 190 + 'deg');
      p.style.animationDelay = Math.random() * 70 + 'ms';
      screenRef.current.appendChild(p);
      setTimeout(() => p.remove(), 1080);
    }
  }, []);

  /* ── Count-up награды + трекер вех (на монтировании) ── */
  useEffect(() => {
    const t1 = setTimeout(() => countUp(earnedValRef.current, EARNED_TO, 1100), 350);
    let raf1 = 0;
    let raf2 = 0;
    raf1 = requestAnimationFrame(() => {
      raf2 = requestAnimationFrame(() => {
        if (msFillRef.current) msFillRef.current.style.width = '25%';
      });
    });
    const popTimers = [];
    const doneNodes = milestonesRef.current
      ? milestonesRef.current.querySelectorAll('.ms-node.done')
      : [];
    doneNodes.forEach((n, i) => {
      popTimers.push(setTimeout(() => n.classList.add('pop'), 420 + i * 170));
    });
    return () => {
      clearTimeout(t1);
      cancelAnimationFrame(raf1);
      cancelAnimationFrame(raf2);
      popTimers.forEach(clearTimeout);
    };
  }, []);

  /* ── Копирование промокода ── */
  const onCopy = useCallback(
    (e) => {
      const btn = e.currentTarget;
      const done = () => {
        setCopied(true);
        toast('Промокод ' + CODE + ' скопирован');
        confetti(btn, 14);
        clearTimeout(copyResetTimer.current);
        copyResetTimer.current = setTimeout(() => setCopied(false), 2200);
      };
      if (navigator.clipboard && navigator.clipboard.writeText) {
        navigator.clipboard.writeText(CODE).then(done).catch(done);
      } else {
        done();
      }
    },
    [confetti, toast]
  );

  /* ── Share (верхняя кнопка + футер) ── */
  const share = useCallback(() => {
    const text = 'Зову тебя в «Мой зал»! Промокод ' + CODE + ' — 14 дней в подарок.';
    confetti(shareBtnRef.current, 18);
    if (navigator.share) {
      navigator.share({ title: 'Мой зал', text }).catch(() => toast('Приглашение готово к отправке'));
    } else {
      toast('Приглашение готово к отправке');
    }
  }, [confetti, toast]);

  /* ── Быстрые каналы ── */
  const openChannel = useCallback(
    (url) => {
      const w = window.open(url, '_blank', 'noopener');
      if (!w) toast('Откройте приложение, чтобы отправить');
    },
    [toast]
  );

  const onChannel = useCallback(
    (ch, e) => {
      if (ch === 'telegram') {
        openChannel(
          'https://t.me/share/url?url=' +
            encodeURIComponent(FULL_LINK) +
            '&text=' +
            encodeURIComponent(INVITE_TEXT)
        );
      } else if (ch === 'whatsapp') {
        openChannel('https://wa.me/?text=' + encodeURIComponent(INVITE_TEXT + ' ' + FULL_LINK));
      } else {
        const chip = e.currentTarget;
        const done = () => {
          setLinkCopied(true);
          toast('Ссылка скопирована');
          confetti(chip, 12);
          clearTimeout(linkResetTimer.current);
          linkResetTimer.current = setTimeout(() => setLinkCopied(false), 2200);
        };
        if (navigator.clipboard && navigator.clipboard.writeText) {
          navigator.clipboard.writeText(FULL_LINK).then(done).catch(done);
        } else {
          done();
        }
      }
    },
    [confetti, openChannel, toast]
  );

  /* ── Глобальная навигация (data-go / data-toast) ── */
  useEffect(() => {
    const onClick = (e) => {
      const go = e.target.closest('[data-go]');
      if (go && go.dataset.go) {
        window.location.href = go.dataset.go;
        return;
      }
      const tt = e.target.closest('[data-toast]');
      if (tt && tt.dataset.toast) toast(tt.dataset.toast);
    };
    document.addEventListener('click', onClick);
    return () => document.removeEventListener('click', onClick);
  }, [toast]);

  return (
    <>
      <style>{CSS}</style>
      <div className="stage">
        <div className="device" data-screen-label="Приведи друга">
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

            <div className="screen" ref={screenRef}>
              {/* Top bar */}
              <div className="topbar">
                <button className="topbar-btn" id="back" type="button" aria-label="Назад" data-go="Profile.html">
                  <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                    <path d="M15 18l-6-6 6-6" />
                  </svg>
                </button>
                <div className="topbar-title">Приведи друга</div>
                <button className="topbar-btn" id="share-top" type="button" aria-label="Поделиться" onClick={share}>
                  <svg width="17" height="17" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                    <path d="M12 16V4" />
                    <path d="M8 8l4-4 4 4" />
                    <path d="M5 12v6a2 2 0 0 0 2 2h10a2 2 0 0 0 2-2v-6" />
                  </svg>
                </button>
              </div>

              <div className="scroller" id="scroller">
                {/* Hero spot */}
                <div className="fade-up">
                  <div className="spot" aria-hidden="true">
                    <div className="halo" />
                    <div className="ring r2" />
                    <div className="ring" />
                    <span className="chip c1" />
                    <span className="chip c2" />
                    <span className="chip c3" />
                    <span className="chip c4" />
                    <div className="scene-pos">
                      <div className="scene">
                        <div className="sc-friends">
                          <div className="person me">
                            <span className="av me"><span className="head" /></span>
                            <span className="lbl"><i /><i /></span>
                          </div>
                          <div className="plus">
                            <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="3" strokeLinecap="round" strokeLinejoin="round">
                              <path d="M12 5v14M5 12h14" />
                            </svg>
                          </div>
                          <div className="person fr">
                            <span className="av fr"><span className="head" /></span>
                            <span className="lbl"><i /><i /></span>
                          </div>
                        </div>
                      </div>
                    </div>
                  </div>
                </div>

                <div className="hero-title fade-up d1">Зовите друзей —<br />тренируйтесь вместе</div>
                <div className="hero-sub fade-up d1">За каждого друга, который купит абонемент, мы дарим бонус вам обоим.</div>

                {/* Reward rows */}
                <div className="card rewards fade-up d2">
                  <div className="rwd you press" data-toast="− 1 000 ₽ зачислятся при оплате друга">
                    <span className="r-ic">
                      <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                        <path d="M20 12v8a1 1 0 0 1-1 1H5a1 1 0 0 1-1-1v-8" />
                        <path d="M2 7h20v5H2z" />
                        <path d="M12 21V7" />
                        <path d="M12 7S10.5 3 8 3a2.5 2.5 0 0 0 0 5" />
                        <path d="M12 7s1.5-4 4-4a2.5 2.5 0 0 1 0 5" />
                      </svg>
                    </span>
                    <span className="r-text">
                      <span className="r-who">Вам</span>
                      <span className="r-note">скидка на продление абонемента</span>
                    </span>
                    <span className="r-amt t-num">−1 000 ₽</span>
                  </div>
                  <div className="rwd friend press" data-toast="Друг получит 14 дней бесплатно">
                    <span className="r-ic">
                      <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                        <rect x="3" y="4" width="18" height="16" rx="3" />
                        <path d="M3 9h18" />
                        <path d="M8 14h4" />
                      </svg>
                    </span>
                    <span className="r-text">
                      <span className="r-who">Другу</span>
                      <span className="r-note">бесплатно к первому абонементу</span>
                    </span>
                    <span className="r-amt t-num">14 дней</span>
                  </div>
                </div>

                {/* Earned (prominent — your progress) */}
                <div className="card earned fade-up d2">
                  <div className="e-top">
                    <div>
                      <span className="t-mini" style={{ color: 'var(--text-3)' }}>Уже накоплено</span>
                      <div className="e-val t-num" style={{ marginTop: 6 }}><span ref={earnedValRef}>0</span> ₽</div>
                    </div>
                    <span style={{ display: 'inline-flex', alignItems: 'center', gap: 5, height: 24, padding: '0 10px', borderRadius: 999, background: 'var(--accent-soft)', color: 'var(--accent-deep)', fontSize: 11.5, fontWeight: 700 }}>
                      <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.4" strokeLinecap="round" strokeLinejoin="round">
                        <path d="M5 12l5 5L20 7" />
                      </svg>
                      2 друга
                    </span>
                  </div>
                  <div className="milestones" id="milestones" ref={milestonesRef}>
                    <span className="ms-track"><i ref={msFillRef} /></span>
                    <span className="ms-node done">
                      <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.8" strokeLinecap="round" strokeLinejoin="round">
                        <path d="M5 12l5 5L20 7" />
                      </svg>
                    </span>
                    <span className="ms-node done">
                      <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.8" strokeLinecap="round" strokeLinejoin="round">
                        <path d="M5 12l5 5L20 7" />
                      </svg>
                    </span>
                    <span className="ms-node">3</span>
                    <span className="ms-node">4</span>
                    <span className="ms-node prize">
                      <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                        <path d="M20 12v8a1 1 0 0 1-1 1H5a1 1 0 0 1-1-1v-8" />
                        <path d="M2 7h20v5H2z" />
                        <path d="M12 21V7" />
                        <path d="M12 7S10.5 3 8 3a2.5 2.5 0 0 0 0 5" />
                        <path d="M12 7s1.5-4 4-4a2.5 2.5 0 0 1 0 5" />
                      </svg>
                    </span>
                  </div>
                  <div className="row-between" style={{ marginTop: 12 }}>
                    <span className="t-small" style={{ fontSize: 12, color: 'var(--text-3)' }}>До месяца в подарок — ещё 3 друга</span>
                    <span className="t-small t-num" style={{ fontSize: 12, color: 'var(--text)', fontWeight: 700 }}>2/5</span>
                  </div>
                </div>

                {/* Referral code */}
                <div className="card code-card fade-up d3">
                  <div className="row-between">
                    <span className="t-mini">Ваш промокод</span>
                    <span className="t-small" style={{ fontSize: 12, color: 'var(--text-3)' }}>Действует бессрочно</span>
                  </div>
                  <div className="code-box">
                    <span className="code" id="code">САША-1000</span>
                    <button className={'copy-btn' + (copied ? ' done' : '')} id="copy" type="button" onClick={onCopy}>
                      {copied ? (
                        <svg id="copy-ic" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.8" strokeLinecap="round" strokeLinejoin="round">
                          <path d="M5 12l5 5L20 7" />
                        </svg>
                      ) : (
                        <svg id="copy-ic" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                          <rect x="9" y="9" width="11" height="11" rx="2.5" />
                          <path d="M5 15V5a2 2 0 0 1 2-2h8" />
                        </svg>
                      )}
                      <span id="copy-label">{copied ? 'Скопировано' : 'Копировать'}</span>
                    </button>
                  </div>
                  <div className="link-line">
                    <span className="lk-ic">
                      <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                        <path d="M10 13a5 5 0 0 0 7 0l3-3a5 5 0 0 0-7-7l-1 1" />
                        <path d="M14 11a5 5 0 0 0-7 0l-3 3a5 5 0 0 0 7 7l1-1" />
                      </svg>
                    </span>
                    <span className="lk-url" id="link-url">myzal.app/i/САША-1000</span>
                  </div>
                  <div className="share-row">
                    <button className="share-chip" type="button" data-channel="telegram" onClick={(e) => onChannel('telegram', e)}>
                      <span className="sc-ic">
                        <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.9" strokeLinecap="round" strokeLinejoin="round">
                          <path d="M21 4L3 11l6 2.5L11 20l3-4 4 3 3-15z" />
                          <path d="M9 13.5L18 6" />
                        </svg>
                      </span>
                      <span className="sc-lbl">Telegram</span>
                    </button>
                    <button className="share-chip" type="button" data-channel="whatsapp" onClick={(e) => onChannel('whatsapp', e)}>
                      <span className="sc-ic">
                        <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.9" strokeLinecap="round" strokeLinejoin="round">
                          <path d="M4 20l1.4-4.2A7.5 7.5 0 1 1 8.2 18.6L4 20z" />
                          <path d="M9 9.2c.3 2 1.7 3.4 3.8 4 .5.1.9-.1 1-.5l.2-.7 1.6.6c-.1 1-.9 1.6-2 1.5-2.5-.3-4.7-2.5-5-5-.1-1 .5-1.8 1.5-1.9l.6 1.6-.7.3c-.4.2-.6.5-.5.9z" fill="currentColor" stroke="none" />
                        </svg>
                      </span>
                      <span className="sc-lbl">WhatsApp</span>
                    </button>
                    <button className="share-chip" type="button" data-channel="link" onClick={(e) => onChannel('link', e)}>
                      <span className="sc-ic" id="link-ic">
                        {linkCopied ? (
                          <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.6" strokeLinecap="round" strokeLinejoin="round">
                            <path d="M5 12l5 5L20 7" />
                          </svg>
                        ) : (
                          <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.9" strokeLinecap="round" strokeLinejoin="round">
                            <rect x="9" y="9" width="11" height="11" rx="2.5" />
                            <path d="M5 15V5a2 2 0 0 1 2-2h8" />
                          </svg>
                        )}
                      </span>
                      <span className="sc-lbl" id="link-lbl">{linkCopied ? 'Скопировано' : 'Ссылка'}</span>
                    </button>
                  </div>
                </div>

                {/* How it works */}
                <div className="steps fade-up d3">
                  <div className="steps-head t-mini">Как это работает</div>
                  <div className="step">
                    <span className="s-num">1</span><span className="s-line" />
                    <div className="s-body">
                      <div className="s-title">Поделитесь ссылкой</div>
                      <div className="s-desc">Отправьте промокод или ссылку другу в любой мессенджер.</div>
                    </div>
                  </div>
                  <div className="step">
                    <span className="s-num">2</span><span className="s-line" />
                    <div className="s-body">
                      <div className="s-title">Друг покупает абонемент</div>
                      <div className="s-desc">Он вводит код при оплате и сразу получает 14 дней в подарок.</div>
                    </div>
                  </div>
                  <div className="step">
                    <span className="s-num">3</span>
                    <div className="s-body">
                      <div className="s-title">Вы получаете 1 000 ₽</div>
                      <div className="s-desc">Скидка автоматически применится к вашему следующему продлению.</div>
                    </div>
                  </div>
                </div>

                {/* Friends */}
                <div className="t-mini fade-up d4" style={{ padding: '22px 4px 10px' }}>Приглашённые друзья</div>
                <div className="card friends fade-up d5">
                  <div className="fr-row press" data-toast="Миша Кравцов · +1 000 ₽ зачислено">
                    <span className="fr-av" style={{ background: '#f59e0b' }}>МК</span>
                    <div className="fr-main">
                      <div className="fr-name">Миша Кравцов</div>
                      <div className="fr-date">Присоединился 18 апреля</div>
                    </div>
                    <span className="fr-badge joined">
                      <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.6" strokeLinecap="round" strokeLinejoin="round">
                        <path d="M5 12l5 5L20 7" />
                      </svg>
                      +1 000 ₽
                    </span>
                  </div>
                  <div className="fr-row press" data-toast="Даша Волкова · +1 000 ₽ зачислено">
                    <span className="fr-av" style={{ background: '#a855f7' }}>ДВ</span>
                    <div className="fr-main">
                      <div className="fr-name">Даша Волкова</div>
                      <div className="fr-date">Присоединилась 2 мая</div>
                    </div>
                    <span className="fr-badge joined">
                      <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.6" strokeLinecap="round" strokeLinejoin="round">
                        <path d="M5 12l5 5L20 7" />
                      </svg>
                      +1 000 ₽
                    </span>
                  </div>
                  <div className="fr-row press" data-toast="Егор Панов ещё не оплатил — напомнить?">
                    <span className="fr-av" style={{ background: 'var(--border-strong)', color: 'var(--text-2)' }}>ЕП</span>
                    <div className="fr-main">
                      <div className="fr-name">Егор Панов</div>
                      <div className="fr-date">Перешёл по ссылке · ещё не оплатил</div>
                    </div>
                    <span className="fr-badge pending">
                      <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.2" strokeLinecap="round" strokeLinejoin="round">
                        <circle cx="12" cy="12" r="9" />
                        <path d="M12 7v5l3 2" />
                      </svg>
                      Ждём
                    </span>
                  </div>
                </div>

                <div style={{ height: 18 }} />
              </div>

              {/* Sticky CTA */}
              <div className="footer">
                <button className="btn" id="share" type="button" ref={shareBtnRef} onClick={share}>
                  <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.2" strokeLinecap="round" strokeLinejoin="round">
                    <circle cx="18" cy="5" r="3" />
                    <circle cx="6" cy="12" r="3" />
                    <circle cx="18" cy="19" r="3" />
                    <path d="M8.6 13.5l6.8 4M15.4 6.5l-6.8 4" />
                  </svg>
                  Поделиться приглашением
                </button>
              </div>

              <div className={'toast' + (toastShow ? ' show' : '')} id="toast">{toastMsg}</div>
              <div className="home-indicator" />
            </div>
          </div>
        </div>
      </div>
    </>
  );
}

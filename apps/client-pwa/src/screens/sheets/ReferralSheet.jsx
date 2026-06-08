/**
 * ReferralSheet (Phase 98 REFER-05 / REFER-06)
 *
 * Pixel-perfect port of .planning/refs/v2.6-REFERENCE-ReferFriendScreen.jsx.
 * CSS scoped to .referral-root (D-71-09 graduation recipe; mirrors ChatScreen Phase 94).
 * Device chrome stripped; theme via data-theme MutationObserver (PWA app mechanism).
 * Data wired exclusively through useClientReferralSummary from @/data (no mock constants).
 * Tier tracker (.milestones) kept in DOM but hidden (hide-for-future, SC-5).
 * Brand: «Sportzal» (D-62-02).
 */
import { useCallback, useEffect, useRef, useState } from 'react';
import { useClientReferralSummary } from '@/data';
import { formatMoney } from '@/utils/format.js';

/* ─── Date formatter (ru-RU, Europe/Moscow — no date-fns, D-82-01 pattern) ─ */
function formatJoinDate(isoString) {
  if (!isoString) return '';
  try {
    return new Intl.DateTimeFormat('ru-RU', {
      day: 'numeric',
      month: 'long',
      year: 'numeric',
      timeZone: 'Europe/Moscow',
    }).format(new Date(isoString));
  } catch {
    return isoString;
  }
}

/* ─── Avatar initials helper ─────────────────────────────────────────────── */
function initials(firstName) {
  if (!firstName) return '?';
  return firstName.slice(0, 2).toUpperCase();
}

/* ─── Stable avatar background color per name ───────────────────────────── */
const AVATAR_COLORS = [
  '#f59e0b', '#a855f7', '#3b82f6', '#10b981', '#ef4444',
  '#8b5cf6', '#ec4899', '#06b6d4', '#f97316',
];
function avatarColor(str) {
  if (!str) return AVATAR_COLORS[0];
  let h = 0;
  for (let i = 0; i < str.length; i++) h = (h * 31 + str.charCodeAt(i)) >>> 0;
  return AVATAR_COLORS[h % AVATAR_COLORS.length];
}

/* ─── Pluralisation helper ────────────────────────────────────────────────── */
function pluralFriends(n) {
  if (n % 100 >= 11 && n % 100 <= 19) return 'друзей';
  switch (n % 10) {
    case 1: return 'друг';
    case 2:
    case 3:
    case 4: return 'друга';
    default: return 'друзей';
  }
}

/* ─── Confetti colors (verbatim from reference) ─────────────────────────── */
const CONFETTI_COLORS = ['var(--accent)', 'var(--accent-deep)', '#a7f3d6'];

/* ─── CSS (verbatim from reference, re-scoped to .referral-root) ─────────── */
const CSS = `
.referral-root {
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

  position: absolute; inset: 0;
  font-family: var(--font);
  -webkit-font-smoothing: antialiased;
  -moz-osx-font-smoothing: grayscale;
  background: var(--bg);
  color: var(--text);
  display: flex; flex-direction: column;
  transition: background 0.3s ease;
}

.referral-root.dark {
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

.referral-root * { box-sizing: border-box; }
.referral-root button { font-family: inherit; }

.referral-root .t-num { font-variant-numeric: tabular-nums; }
.referral-root .t-mini { font-size: 11px; font-weight: 600; letter-spacing: 0.5px; text-transform: uppercase; color: var(--text-3); }
.referral-root .t-small { font-size: 13px; font-weight: 400; line-height: 1.4; color: var(--text-2); }
.referral-root .t-h3 { font-size: 17px; font-weight: 600; letter-spacing: -0.2px; line-height: 1.25; color: var(--text); }
.referral-root .row { display: flex; align-items: center; gap: 12px; }
.referral-root .row-between { display: flex; align-items: center; justify-content: space-between; gap: 12px; }

/* Top bar */
.referral-root .topbar {
  height: 54px; padding: 0 14px;
  display: flex; align-items: center; gap: 10px;
  flex-shrink: 0;
  position: relative; z-index: 6;
}
.referral-root .topbar-btn {
  width: 38px; height: 38px; border-radius: 999px;
  border: 0.5px solid var(--border); background: var(--surface);
  box-shadow: var(--sh-1);
  display: inline-flex; align-items: center; justify-content: center;
  color: var(--text); cursor: pointer; padding: 0; flex-shrink: 0;
  transition: transform 0.12s ease, background 0.15s;
}
.referral-root .topbar-btn:active { transform: scale(0.94); background: var(--surface-2); }
.referral-root .topbar-title { flex: 1; text-align: center; font-size: 16px; font-weight: 650; letter-spacing: -0.2px; }

/* Scroll body */
.referral-root .scroller {
  flex: 1; overflow-y: auto; -webkit-overflow-scrolling: touch;
  padding: 4px 16px 0;
}
.referral-root .scroller::-webkit-scrollbar { display: none; }

.referral-root .card {
  background: var(--surface);
  border: 0.5px solid var(--border);
  border-radius: var(--r-lg);
  box-shadow: var(--sh-2);
}

.referral-root .press { transition: transform 0.1s ease, background 0.15s ease; cursor: pointer; }
.referral-root .press:active { transform: scale(0.97); }

.referral-root .fade-up { animation: referral-fade-up 0.4s cubic-bezier(0.32,0.72,0.2,1) both; }
@keyframes referral-fade-up { from { opacity: 0; transform: translateY(10px); } to { opacity: 1; transform: translateY(0); } }
.referral-root .d1 { animation-delay: 0.05s; } .referral-root .d2 { animation-delay: 0.11s; }
.referral-root .d3 { animation-delay: 0.17s; } .referral-root .d4 { animation-delay: 0.23s; } .referral-root .d5 { animation-delay: 0.29s; }

@media (prefers-reduced-motion: reduce) {
  .referral-root .fade-up { animation: none; opacity: 1; }
}

/* Spot illustration */
.referral-root .spot {
  position: relative;
  width: 168px; height: 150px;
  margin: 6px auto 0;
  flex-shrink: 0;
}
.referral-root .spot .halo {
  position: absolute; left: 50%; top: 50%; transform: translate(-50%,-50%);
  width: 130px; height: 130px; border-radius: 50%;
  background: radial-gradient(circle, color-mix(in oklab, var(--accent) 22%, transparent) 0%, transparent 64%);
}
.referral-root .spot .ring {
  position: absolute; left: 50%; top: 50%; transform: translate(-50%,-50%);
  width: 128px; height: 128px; border-radius: 50%;
  border: 1.5px dashed color-mix(in oklab, var(--accent) 42%, transparent);
  opacity: 0.5;
}
.referral-root .spot .ring.r2 { width: 164px; height: 164px; opacity: 0.22; }
.referral-root .spot .chip {
  position: absolute; border-radius: 4px;
  background: var(--accent);
  animation: referral-spot-float 3.4s ease-in-out infinite;
  z-index: 1;
}
.referral-root .spot .chip.c1 { width: 11px; height: 11px; right: 24px; top: 16px; transform: rotate(16deg); background: var(--accent-deep); }
.referral-root .spot .chip.c2 { width: 8px; height: 8px; right: 14px; bottom: 34px; border-radius: 50%; animation-delay: 0.7s; }
.referral-root .spot .chip.c3 { width: 7px; height: 7px; left: 16px; top: 30px; border-radius: 50%; animation-delay: 1.2s; background: var(--accent-deep); }
.referral-root .spot .chip.c4 { width: 9px; height: 9px; left: 22px; bottom: 24px; transform: rotate(-12deg); animation-delay: 1.6s; }
@keyframes referral-spot-float {
  0%, 100% { transform: translateY(0) rotate(0); }
  50% { transform: translateY(-7px) rotate(10deg); }
}
@media (prefers-reduced-motion: reduce) { .referral-root .spot .chip { animation: none; } }

.referral-root .spot .scene-pos {
  position: absolute; left: 50%; top: 50%;
  transform: translate(-50%, -50%);
  z-index: 2;
}
.referral-root .spot .scene {
  background: var(--surface);
  border: 0.5px solid var(--border);
  border-radius: 18px;
  box-shadow: 0 14px 30px rgba(28,25,23,0.13), 0 3px 7px rgba(28,25,23,0.06);
  padding: 16px 18px;
  transform: rotate(-3deg);
  transform-origin: center;
  animation: referral-scene-in 0.5s cubic-bezier(0.32, 1.6, 0.32, 1) both;
}
.referral-root.dark .spot .scene { box-shadow: 0 14px 34px rgba(0,0,0,0.5); }
@keyframes referral-scene-in {
  0% { transform: rotate(-3deg) scale(0.5); opacity: 0; }
  60% { transform: rotate(-3deg) scale(1.05); }
  100% { transform: rotate(-3deg) scale(1); opacity: 1; }
}
@media (prefers-reduced-motion: reduce) { .referral-root .spot .scene { animation: none; } }

.referral-root .sc-friends { display: flex; align-items: center; gap: 10px; }
.referral-root .sc-friends .person { display: flex; flex-direction: column; align-items: center; gap: 7px; }
.referral-root .sc-friends .av {
  width: 38px; height: 38px; border-radius: 50%;
  display: flex; align-items: flex-end; justify-content: center;
  overflow: hidden;
}
.referral-root .sc-friends .av.me { background: var(--accent); }
.referral-root .sc-friends .av.fr { background: var(--accent-soft); border: 1.5px dashed color-mix(in oklab, var(--accent) 55%, transparent); }
.referral-root .sc-friends .av .head { width: 14px; height: 14px; border-radius: 50%; margin-bottom: 2px; }
.referral-root .sc-friends .av.me .head { background: #06301f; }
.referral-root .sc-friends .av.fr .head { background: color-mix(in oklab, var(--accent-deep) 60%, transparent); }
.referral-root .sc-friends .lbl { display: flex; flex-direction: column; gap: 4px; align-items: center; }
.referral-root .sc-friends .lbl i { height: 4px; border-radius: 999px; background: var(--border-strong); }
.referral-root .sc-friends .person.me .lbl i:first-child { width: 30px; background: var(--accent-deep); }
.referral-root .sc-friends .person.fr .lbl i:first-child { width: 24px; }
.referral-root .sc-friends .lbl i:last-child { width: 16px; background: var(--border); }
.referral-root .sc-friends .plus {
  width: 24px; height: 24px; border-radius: 50%;
  background: var(--accent-deep); color: #fff;
  display: flex; align-items: center; justify-content: center;
  align-self: flex-start; margin-top: 8px;
  box-shadow: 0 3px 8px color-mix(in oklab, var(--accent) 55%, transparent);
}
.referral-root .sc-friends .plus svg { width: 13px; height: 13px; }

.referral-root .hero-title {
  text-align: center;
  margin-top: 16px;
  font-size: 27px; font-weight: 750;
  letter-spacing: -0.7px; line-height: 1.12;
  text-wrap: balance;
}
.referral-root .hero-sub {
  text-align: center;
  margin: 9px auto 0;
  font-size: 14.5px; line-height: 1.5;
  color: var(--text-2); text-wrap: pretty;
  max-width: 290px;
}

/* Reward rows */
.referral-root .rewards {
  margin-top: 22px;
  padding: 6px;
  display: flex; flex-direction: column; gap: 6px;
  position: relative;
}
.referral-root .rwd {
  display: flex; align-items: center; gap: 13px;
  padding: 13px 14px;
  border-radius: 15px;
}
.referral-root .rwd.you { background: color-mix(in oklab, var(--accent-soft) 65%, var(--surface)); }
.referral-root .rwd.friend { background: var(--surface-2); }
.referral-root .rwd .r-ic {
  width: 38px; height: 38px; border-radius: 11px; flex-shrink: 0;
  display: inline-flex; align-items: center; justify-content: center;
}
.referral-root .rwd.you .r-ic { background: var(--accent); color: #06120c; }
.referral-root .rwd.friend .r-ic { background: var(--surface); border: 0.5px solid var(--border); color: var(--accent-deep); }
.referral-root .rwd .r-ic svg { width: 20px; height: 20px; }
.referral-root .rwd .r-text { flex: 1; min-width: 0; display: flex; flex-direction: column; gap: 2px; }
.referral-root .rwd .r-who { font-size: 14px; font-weight: 700; color: var(--text); letter-spacing: -0.2px; }
.referral-root .rwd .r-note { font-size: 11.5px; color: var(--text-3); line-height: 1.3; }
.referral-root .rwd .r-amt {
  flex-shrink: 0; text-align: right;
  font-size: 19px; font-weight: 800; letter-spacing: -0.6px; line-height: 1;
  color: var(--text);
}
.referral-root .rwd.you .r-amt { color: var(--accent-deep); }

/* Referral code card */
.referral-root .code-card { margin-top: 14px; padding: 16px; }
.referral-root .code-box {
  margin-top: 12px;
  display: flex; align-items: center; gap: 10px;
  background: var(--surface-2);
  border: 1px dashed var(--border-strong);
  border-radius: 14px;
  padding: 13px 14px;
}
.referral-root .code-box .code {
  flex: 1; min-width: 0;
  font-family: ui-monospace, "SF Mono", "JetBrains Mono", Menlo, monospace;
  font-size: 19px; font-weight: 700; letter-spacing: 1px;
  color: var(--text);
  overflow: hidden; text-overflow: ellipsis; white-space: nowrap;
}
.referral-root .copy-btn {
  flex-shrink: 0;
  height: 36px; padding: 0 14px; border-radius: 999px;
  border: 0; background: var(--text); color: var(--bg);
  font-size: 13px; font-weight: 650; cursor: pointer;
  display: inline-flex; align-items: center; gap: 6px;
  transition: transform 0.1s ease, background 0.2s ease;
}
.referral-root .copy-btn svg { width: 14px; height: 14px; }
.referral-root .copy-btn:active { transform: scale(0.95); }
.referral-root .copy-btn.done { background: var(--accent); color: #06120c; }

/* Referral link line */
.referral-root .link-line {
  margin-top: 10px;
  display: flex; align-items: center; gap: 8px;
  padding: 0 2px;
}
.referral-root .link-line .lk-ic { color: var(--text-3); flex-shrink: 0; display: inline-flex; }
.referral-root .link-line .lk-ic svg { width: 14px; height: 14px; }
.referral-root .link-line .lk-url {
  flex: 1; min-width: 0;
  font-family: ui-monospace, "SF Mono", "JetBrains Mono", Menlo, monospace;
  font-size: 12.5px; color: var(--text-2);
  overflow: hidden; text-overflow: ellipsis; white-space: nowrap;
}

/* Quick share channels */
.referral-root .share-row {
  margin-top: 13px;
  display: grid; grid-template-columns: repeat(3, 1fr); gap: 8px;
}
.referral-root .share-chip {
  appearance: none; cursor: pointer;
  display: inline-flex; flex-direction: column; align-items: center; gap: 6px;
  padding: 11px 6px 10px;
  background: var(--surface-2); border: 0.5px solid var(--border);
  border-radius: 14px; color: var(--text);
  transition: transform 0.1s ease, background 0.15s ease, border-color 0.15s ease;
}
.referral-root .share-chip:active { transform: scale(0.96); background: var(--bg); }
.referral-root .share-chip .sc-ic {
  width: 30px; height: 30px; border-radius: 999px;
  background: var(--surface); border: 0.5px solid var(--border);
  display: inline-flex; align-items: center; justify-content: center;
  color: var(--accent-deep);
}
.referral-root .share-chip .sc-ic svg { width: 17px; height: 17px; }
.referral-root .share-chip .sc-lbl { font-size: 11.5px; font-weight: 600; color: var(--text-2); letter-spacing: -0.1px; }

/* Steps */
.referral-root .steps { margin-top: 24px; }
.referral-root .steps-head { padding: 0 4px 10px; }
.referral-root .step {
  display: flex; flex-direction: row; gap: 14px; align-items: flex-start;
  padding: 4px 4px;
  position: relative;
}
.referral-root .step + .step { margin-top: 4px; }
.referral-root .step .s-num {
  width: 30px; height: 30px; border-radius: 999px; flex-shrink: 0;
  background: var(--accent-soft); color: var(--accent-deep);
  display: inline-flex; align-items: center; justify-content: center;
  font-size: 13px; font-weight: 750;
  position: relative; z-index: 2;
}
.referral-root .step .s-line {
  position: absolute; left: 18.5px; top: 32px; bottom: -6px;
  width: 2px; background: var(--border);
}
.referral-root .step:last-child .s-line { display: none; }
.referral-root .step .s-body { flex: 1; padding-top: 3px; }
.referral-root .step .s-title { font-size: 14.5px; font-weight: 650; color: var(--text); letter-spacing: -0.1px; }
.referral-root .step .s-desc { margin-top: 2px; font-size: 12.5px; line-height: 1.4; color: var(--text-3); }

/* Progress / earned */
.referral-root .earned { margin-top: 24px; padding: 16px; }
.referral-root .earned .e-top { display: flex; align-items: flex-end; justify-content: space-between; gap: 12px; }
.referral-root .earned .e-val { font-size: 30px; font-weight: 800; letter-spacing: -1px; line-height: 0.9; color: var(--text); }
.referral-root .earned .e-bar-track {
  margin-top: 14px; height: 7px; border-radius: 999px;
  background: var(--surface-2); overflow: hidden;
  border: 0.5px solid var(--border);
}
.referral-root .earned .e-bar-fill {
  height: 100%; border-radius: 999px; background: var(--accent);
  width: 0; transition: width 0.9s cubic-bezier(0.32,0.72,0.2,1);
}

/* Gamified milestone tracker (hidden-for-future SC-5) */
.referral-root .milestones { display: none; }

/* Friends list */
.referral-root .friends { margin-top: 14px; padding: 0; overflow: hidden; }
.referral-root .fr-row { display: flex; align-items: center; gap: 12px; padding: 13px 16px; }
.referral-root .fr-row + .fr-row { border-top: 0.5px solid var(--border); }
.referral-root .fr-row .fr-av {
  width: 38px; height: 38px; border-radius: 999px; flex-shrink: 0;
  display: inline-flex; align-items: center; justify-content: center;
  font-size: 14px; font-weight: 700; color: #fff;
}
.referral-root .fr-row .fr-main { flex: 1; min-width: 0; }
.referral-root .fr-row .fr-name { font-size: 14.5px; font-weight: 600; color: var(--text); letter-spacing: -0.1px; }
.referral-root .fr-row .fr-date { font-size: 11.5px; color: var(--text-3); margin-top: 1px; }
.referral-root .fr-badge {
  flex-shrink: 0; display: inline-flex; align-items: center; gap: 5px;
  height: 24px; padding: 0 10px; border-radius: 999px;
  font-size: 11px; font-weight: 700; letter-spacing: 0.2px;
}
.referral-root .fr-badge.joined { background: var(--accent-soft); color: var(--accent-deep); }
.referral-root .fr-badge.pending { background: var(--warn-soft); color: #b9791f; }
.referral-root .fr-badge svg { width: 11px; height: 11px; }
.referral-root.dark .fr-badge.pending { color: var(--warn); }

/* Sticky CTA footer */
.referral-root .footer {
  flex-shrink: 0;
  padding: 12px 16px 14px;
  background: color-mix(in oklab, var(--bg) 80%, transparent);
  backdrop-filter: blur(16px) saturate(180%);
  -webkit-backdrop-filter: blur(16px) saturate(180%);
  border-top: 0.5px solid var(--border);
  position: relative; z-index: 5;
}
.referral-root .btn {
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
  position: relative; overflow: hidden;
}
.referral-root .btn:active { transform: scale(0.98); }
.referral-root .btn svg { width: 19px; height: 19px; }
.referral-root .btn::after {
  content: ""; position: absolute; top: 0; left: -60%;
  width: 45%; height: 100%;
  background: linear-gradient(100deg, transparent, rgba(255,255,255,0.5), transparent);
  transform: skewX(-18deg); pointer-events: none;
  animation: referral-shimmer 4.8s ease-in-out infinite;
}
@keyframes referral-shimmer { 0% { left: -60%; } 16% { left: 135%; } 100% { left: 135%; } }
@media (prefers-reduced-motion: reduce) { .referral-root .btn::after { display: none; } }

/* Confetti */
.referral-root .confetti {
  position: absolute; width: 8px; height: 8px; z-index: 55;
  pointer-events: none; border-radius: 2px;
  animation: referral-confetti-fly 0.95s cubic-bezier(0.2,0.7,0.3,1) forwards;
}
@keyframes referral-confetti-fly {
  0%   { transform: translate(-50%,-50%) scale(0.5) rotate(0); opacity: 1; }
  70%  { opacity: 1; }
  100% { transform: translate(calc(-50% + var(--dx)), calc(-50% + var(--dy) + 70px)) scale(1) rotate(var(--rot)); opacity: 0; }
}

/* Toast */
.referral-root .toast {
  position: absolute; left: 50%; bottom: 92px; transform: translate(-50%, 16px);
  z-index: 60; background: var(--text); color: var(--bg);
  font-size: 13.5px; font-weight: 600; padding: 11px 18px; border-radius: 999px;
  box-shadow: 0 12px 30px rgba(0,0,0,0.28);
  opacity: 0; pointer-events: none;
  transition: opacity 0.22s ease, transform 0.28s cubic-bezier(0.32,0.72,0.2,1);
  white-space: nowrap;
}
.referral-root .toast.show { opacity: 1; transform: translate(-50%, 0); }

/* Skeleton */
.referral-root .skel {
  border-radius: 8px; background: var(--border);
  animation: referral-skel-pulse 1.4s ease-in-out infinite;
}
@keyframes referral-skel-pulse {
  0%, 100% { opacity: 1; }
  50% { opacity: 0.45; }
}
@media (prefers-reduced-motion: reduce) { .referral-root .skel { animation: none; opacity: 0.7; } }
`;

export function ReferralSheet({ onClose, userName: _userName }) {
  /* ── Data ── */
  const summaryQuery = useClientReferralSummary();
  const isLoading = summaryQuery.isLoading;
  const isError = summaryQuery.isError && !summaryQuery.isFetching;
  const data = summaryQuery.data;

  /* ── Theme (PWA mechanism — data-theme on <html> via TweaksProvider/app context) ── */
  const [isDark, setIsDark] = useState(
    () => document.documentElement.getAttribute('data-theme') === 'dark',
  );
  useEffect(() => {
    const read = () =>
      setIsDark(document.documentElement.getAttribute('data-theme') === 'dark');
    read();
    const obs = new MutationObserver(read);
    obs.observe(document.documentElement, { attributes: true, attributeFilter: ['data-theme'] });
    return () => obs.disconnect();
  }, []);

  /* ── Toast ── */
  const [toastMsg, setToastMsg] = useState('');
  const [toastShow, setToastShow] = useState(false);
  const toastTimer = useRef(null);

  const showToast = useCallback((msg) => {
    setToastMsg(msg);
    setToastShow(true);
    clearTimeout(toastTimer.current);
    toastTimer.current = setTimeout(() => setToastShow(false), 1700);
  }, []);

  /* ── Copy states ── */
  const [copied, setCopied] = useState(false);
  const [linkCopied, setLinkCopied] = useState(false);
  const copyResetTimer = useRef(null);
  const linkResetTimer = useRef(null);

  /* ── Refs ── */
  const rootRef = useRef(null);
  const shareBtnRef = useRef(null);

  /* ── Confetti ── */
  const spawnConfetti = useCallback((originEl, count) => {
    if (!originEl || !rootRef.current) return;
    if (matchMedia('(prefers-reduced-motion: reduce)').matches) return;
    const r = originEl.getBoundingClientRect();
    const s = rootRef.current.getBoundingClientRect();
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
      rootRef.current.appendChild(p);
      setTimeout(() => p.remove(), 1080);
    }
  }, []);

  /* ── Copy referral code ── */
  const onCopy = useCallback(
    (e) => {
      const btn = e.currentTarget;
      const code = data?.code ?? '';
      const done = () => {
        setCopied(true);
        showToast('Промокод ' + code + ' скопирован');
        spawnConfetti(btn, 14);
        clearTimeout(copyResetTimer.current);
        copyResetTimer.current = setTimeout(() => setCopied(false), 2200);
      };
      if (navigator.clipboard && navigator.clipboard.writeText) {
        navigator.clipboard.writeText(code).then(done).catch(done);
      } else {
        done();
      }
    },
    [data?.code, spawnConfetti, showToast],
  );

  /* ── Native share (topbar button + footer CTA) ── */
  const share = useCallback(() => {
    const shareUrl = data?.shareUrl ?? '';
    const code = data?.code ?? '';
    const text = 'Зову тебя в «Sportzal»! Промокод ' + code + ' — 14 дней в подарок. ' + shareUrl;
    spawnConfetti(shareBtnRef.current, 18);
    if (navigator.share) {
      navigator.share({ title: 'Sportzal', text }).catch(() =>
        showToast('Приглашение готово к отправке'),
      );
    } else {
      showToast('Приглашение готово к отправке');
    }
  }, [data?.shareUrl, data?.code, spawnConfetti, showToast]);

  /* ── Quick channels (Telegram / WhatsApp / copy link) ── */
  const openChannel = useCallback(
    (url) => {
      const w = window.open(url, '_blank', 'noopener');
      if (!w) showToast('Откройте приложение, чтобы отправить');
    },
    [showToast],
  );

  const onChannel = useCallback(
    (ch, e) => {
      const shareUrl = data?.shareUrl ?? '';
      const code = data?.code ?? '';
      const inviteText = 'Зову тебя в «Sportzal»! Промокод ' + code + ' — 14 дней в подарок.';
      if (ch === 'telegram') {
        openChannel(
          'https://t.me/share/url?url=' +
            encodeURIComponent(shareUrl) +
            '&text=' +
            encodeURIComponent(inviteText),
        );
      } else if (ch === 'whatsapp') {
        openChannel('https://wa.me/?text=' + encodeURIComponent(inviteText + ' ' + shareUrl));
      } else {
        const chip = e.currentTarget;
        const done = () => {
          setLinkCopied(true);
          showToast('Ссылка скопирована');
          spawnConfetti(chip, 12);
          clearTimeout(linkResetTimer.current);
          linkResetTimer.current = setTimeout(() => setLinkCopied(false), 2200);
        };
        if (navigator.clipboard && navigator.clipboard.writeText) {
          navigator.clipboard.writeText(shareUrl).then(done).catch(done);
        } else {
          done();
        }
      }
    },
    [data?.shareUrl, data?.code, spawnConfetti, openChannel, showToast],
  );

  /* ── Friends list render ── */
  function renderFriends() {
    if (isLoading) {
      return (
        <div className="fr-row">
          <span className="fr-av skel" style={{ background: 'var(--border)' }} />
          <div className="fr-main">
            <div className="skel" style={{ height: 14, width: '55%', marginBottom: 6 }} />
            <div className="skel" style={{ height: 11, width: '35%' }} />
          </div>
        </div>
      );
    }
    if (isError) return null;
    const invitees = data?.invitees ?? [];
    if (invitees.length === 0) {
      return (
        <div className="fr-row" style={{ flexDirection: 'column', alignItems: 'flex-start', gap: 4 }}>
          <div className="fr-name">Пока никого</div>
          <div className="fr-date" style={{ fontSize: 12.5, color: 'var(--text-2)', lineHeight: 1.4 }}>
            Поделитесь промокодом — приглашённые друзья появятся здесь.
          </div>
        </div>
      );
    }
    return invitees.map((inv) => {
      const isJoined = inv.status === 'joined';
      // WR-04: stable composite key — the PII-minimal payload exposes no invitee id,
      // so derive one from (firstName, joinedAt). joinedAt = rc.created_at is
      // effectively unique per referrer, disambiguating duplicate first names and
      // surviving reorder/refetch (avoids stale avatars/badges from index keys).
      // Follow-up: add an opaque per-capture id to the wire payload.
      const rowKey = `${inv.firstName ?? ''}|${inv.joinedAt ?? ''}`;
      return (
        <div key={rowKey} className="fr-row">
          <span
            className="fr-av"
            style={{
              background: isJoined ? avatarColor(inv.firstName) : 'var(--border-strong)',
              color: isJoined ? '#fff' : 'var(--text-2)',
            }}
          >
            {initials(inv.firstName)}
          </span>
          <div className="fr-main">
            <div className="fr-name">{inv.firstName}</div>
            <div className="fr-date">
              {isJoined
                ? 'Присоединился(ась) ' + formatJoinDate(inv.joinedAt)
                : 'Перешёл по ссылке · ещё не оплатил'}
            </div>
          </div>
          {isJoined ? (
            <span className="fr-badge joined">
              <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.6" strokeLinecap="round" strokeLinejoin="round">
                <path d="M5 12l5 5L20 7" />
              </svg>
              +{formatMoney(inv.bonusKopecks)}
            </span>
          ) : (
            <span className="fr-badge pending">
              <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.2" strokeLinecap="round" strokeLinejoin="round">
                <circle cx="12" cy="12" r="9" />
                <path d="M12 7v5l3 2" />
              </svg>
              Ждём
            </span>
          )}
        </div>
      );
    });
  }

  const joinedCount = data ? (data.invitees ?? []).filter((i) => i.status === 'joined').length : 0;

  return (
    <div className={'referral-root' + (isDark ? ' dark' : '')} ref={rootRef}>
      <style>{CSS}</style>

      {/* Topbar */}
      <div className="topbar">
        <button className="topbar-btn" type="button" aria-label="Назад" onClick={onClose}>
          <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
            <path d="M15 18l-6-6 6-6" />
          </svg>
        </button>
        <div className="topbar-title">Приведи друга</div>
        <button className="topbar-btn" type="button" aria-label="Поделиться" onClick={share}>
          <svg width="17" height="17" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
            <path d="M12 16V4" />
            <path d="M8 8l4-4 4 4" />
            <path d="M5 12v6a2 2 0 0 0 2 2h10a2 2 0 0 0 2-2v-6" />
          </svg>
        </button>
      </div>

      <div className="scroller">
        {/* Hero spot illustration */}
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

        {/* Hero copy */}
        <div className="hero-title fade-up d1">Зовите друзей —<br />тренируйтесь вместе</div>
        <div className="hero-sub fade-up d1">
          За каждого друга, который купит абонемент, мы дарим бонус вам обоим.
        </div>

        {/* Reward rows */}
        <div className="card rewards fade-up d2">
          <div className="rwd you press">
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
          <div className="rwd friend press">
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

        {/* Earned card */}
        <div className="card earned fade-up d2">
          <div className="e-top">
            <div>
              <span className="t-mini" style={{ color: 'var(--text-3)' }}>Уже накоплено</span>
              <div className="e-val t-num" style={{ marginTop: 6 }}>
                {isLoading ? (
                  <span className="skel" style={{ display: 'inline-block', width: 80, height: 28 }} />
                ) : isError ? (
                  <span style={{ fontSize: 14, color: 'var(--text-2)' }}>—</span>
                ) : (
                  <span>{formatMoney(data?.accruedKopecks ?? 0)}</span>
                )}
              </div>
            </div>
            {!isLoading && !isError && data && (
              <span style={{
                display: 'inline-flex', alignItems: 'center', gap: 5,
                height: 24, padding: '0 10px', borderRadius: 999,
                background: 'var(--accent-soft)', color: 'var(--accent-deep)',
                fontSize: 11.5, fontWeight: 700,
              }}>
                <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.4" strokeLinecap="round" strokeLinejoin="round">
                  <path d="M5 12l5 5L20 7" />
                </svg>
                {joinedCount} {pluralFriends(joinedCount)}
              </span>
            )}
          </div>
          {/* Gamification tier tracker — hidden-for-future (SC-5).
              WR-02: the .e-bar-track progress fill is tier/gamification progress
              (toward the next reward tier), not the accrued figure. With no goal
              denominator defined this phase it could only ever render a permanently
              empty width:0 bar in the visible "Уже накоплено" area — a broken
              affordance. Moved into the hidden tier-tracker block so it stays
              consistent with .milestones until tiers ship. The real accrued amount
              (formatMoney above) remains visible. */}
          <div className="milestones" hidden aria-hidden="true">
            <div className="e-bar-track">
              <div className="e-bar-fill" />
            </div>
            <span className="ms-track"><i /></span>
            <span className="ms-node done" />
            <span className="ms-node done" />
            <span className="ms-node">3</span>
            <span className="ms-node">4</span>
            <span className="ms-node prize" />
          </div>
        </div>

        {/* Referral code card */}
        <div className="card code-card fade-up d3">
          <div className="row-between">
            <span className="t-mini">Ваш промокод</span>
            <span className="t-small" style={{ fontSize: 12, color: 'var(--text-3)' }}>Действует бессрочно</span>
          </div>
          {isLoading ? (
            <div className="skel" style={{ height: 56, marginTop: 12, borderRadius: 14 }} />
          ) : isError ? (
            <div style={{
              margin: '12px 0 4px',
              padding: '14px 16px',
              borderRadius: 14,
              background: 'var(--surface-2)',
              border: '0.5px solid var(--border)',
            }}>
              <div style={{ fontSize: 14, fontWeight: 600, color: 'var(--text)', marginBottom: 4 }}>
                Не удалось загрузить
              </div>
              <div style={{ fontSize: 13, color: 'var(--text-2)', lineHeight: 1.4 }}>
                Потяните вниз, чтобы обновить.
              </div>
            </div>
          ) : (
            <>
              <div className="code-box">
                <span className="code">{data?.code ?? ''}</span>
                <button
                  className={'copy-btn' + (copied ? ' done' : '')}
                  type="button"
                  onClick={onCopy}
                >
                  {copied ? (
                    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.8" strokeLinecap="round" strokeLinejoin="round">
                      <path d="M5 12l5 5L20 7" />
                    </svg>
                  ) : (
                    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                      <rect x="9" y="9" width="11" height="11" rx="2.5" />
                      <path d="M5 15V5a2 2 0 0 1 2-2h8" />
                    </svg>
                  )}
                  <span>{copied ? 'Скопировано' : 'Копировать'}</span>
                </button>
              </div>
              <div className="link-line">
                <span className="lk-ic">
                  <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                    <path d="M10 13a5 5 0 0 0 7 0l3-3a5 5 0 0 0-7-7l-1 1" />
                    <path d="M14 11a5 5 0 0 0-7 0l-3 3a5 5 0 0 0 7 7l1-1" />
                  </svg>
                </span>
                <span className="lk-url">{data?.shareUrl ?? ''}</span>
              </div>
            </>
          )}
          <div className="share-row">
            <button className="share-chip" type="button" onClick={(e) => onChannel('telegram', e)}>
              <span className="sc-ic">
                <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.9" strokeLinecap="round" strokeLinejoin="round">
                  <path d="M21 4L3 11l6 2.5L11 20l3-4 4 3 3-15z" />
                  <path d="M9 13.5L18 6" />
                </svg>
              </span>
              <span className="sc-lbl">Telegram</span>
            </button>
            <button className="share-chip" type="button" onClick={(e) => onChannel('whatsapp', e)}>
              <span className="sc-ic">
                <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.9" strokeLinecap="round" strokeLinejoin="round">
                  <path d="M4 20l1.4-4.2A7.5 7.5 0 1 1 8.2 18.6L4 20z" />
                  <path d="M9 9.2c.3 2 1.7 3.4 3.8 4 .5.1.9-.1 1-.5l.2-.7 1.6.6c-.1 1-.9 1.6-2 1.5-2.5-.3-4.7-2.5-5-5-.1-1 .5-1.8 1.5-1.9l.6 1.6-.7.3c-.4.2-.6.5-.5.9z" fill="currentColor" stroke="none" />
                </svg>
              </span>
              <span className="sc-lbl">WhatsApp</span>
            </button>
            <button className="share-chip" type="button" onClick={(e) => onChannel('link', e)}>
              <span className="sc-ic">
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
              <span className="sc-lbl">{linkCopied ? 'Скопировано' : 'Ссылка'}</span>
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

        {/* Invited friends */}
        <div className="t-mini fade-up d4" style={{ padding: '22px 4px 10px' }}>Приглашённые друзья</div>
        <div className="card friends fade-up d5">
          {renderFriends()}
        </div>

        <div style={{ height: 18 }} />
      </div>

      {/* Sticky CTA footer */}
      <div className="footer">
        <button className="btn" type="button" ref={shareBtnRef} onClick={share}>
          <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.2" strokeLinecap="round" strokeLinejoin="round">
            <circle cx="18" cy="5" r="3" />
            <circle cx="6" cy="12" r="3" />
            <circle cx="18" cy="19" r="3" />
            <path d="M8.6 13.5l6.8 4M15.4 6.5l-6.8 4" />
          </svg>
          Поделиться приглашением
        </button>
      </div>

      <div className={'toast' + (toastShow ? ' show' : '')}>{toastMsg}</div>
    </div>
  );
}

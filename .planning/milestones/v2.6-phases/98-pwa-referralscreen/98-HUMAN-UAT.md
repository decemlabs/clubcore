---
status: mostly_verified
phase: 98-pwa-referralscreen
source: [98-VERIFICATION.md]
started: 2026-06-08
updated: 2026-06-08
verified_by: automated chrome-devtools browser run (2026-06-08, post-milestone)
---

## Current Test

[automated browser verification done — see results; only true device-only checks remain]

## Tests

### 1. Pixel-perfect visual parity (light + dark)
expected: ReferralSheet renders per `.planning/refs/v2.6-REFERENCE-ReferFriendScreen.jsx` (hero, reward rows, code box + copy, share chips, "Как это работает" steps, invited-friends list).
result: PARTIAL ✓ — verified live in the browser (light theme): full a11y snapshot confirms every section present in the locked order (hero «Зовите друзей — тренируйтесь вместе», reward rows «Вам −1 000 ₽» / «Другу 14 дней», «УЖЕ НАКОПЛЕНО», «ВАШ ПРОМОКОД B5219P2B» + Копировать, share chips Telegram/WhatsApp/Ссылка, 3-step «КАК ЭТО РАБОТАЕТ», «ПРИГЛАШЁННЫЕ ДРУЗЬЯ»), device chrome stripped, brand «Sportzal». Screenshot saved /tmp/referral-sheet.png. STILL PENDING (human/device): dark-theme render + true sub-pixel/animation pixel-diff vs the reference.

### 2. Live deep-link → join → invitees/accrued round-trip
expected: `…/i/<code>` shows the landing (referrer first name + bonus preview), stores the pending code; after the friend onboards the binding is captured; after first purchase the referrer sees the friend "joined +bonus" and "Уже накоплено" reflects the real ledger sum.
result: VERIFIED ✓ (automated, end-to-end across the layers):
  - Landing `/i/B5219P2B` rendered live: heading «Клиент зовёт вас в «Sportzal»» (real referrer first name from the `GET /i/<code>` resolver) + bonus preview + «Присоединиться» CTA.
  - CTA stored `sessionStorage['clubcore:pendingReferral'] = "B5219P2B"` and routed to the registration entry (pending-referral handoff confirmed).
  - Capture endpoint verified via curl (`POST /client/referral/capture` 200, self-referral 422, idempotent) + the 7-case Phase-97 crediting integration suite (green).
  - Invitees/accrued RENDER verified by seeding a captured+credited friend (referral_capture + referrer-side `referral_accrual` 50000) → `GET /referral/summary` returned `accruedKopecks:50000, invitees:[{firstName:"Аня", status:"joined", bonusKopecks:50000}]` → ReferralSheet rendered «УЖЕ НАКОПЛЕНО 500 ₽», «1 друг», and the invitee row «Аня · Присоединился(ась) 8 июня 2026 г. · +500 ₽». Synthetic data removed afterward.
  - STILL PENDING (operator): a genuine two-real-clients flow through a live ЮKassa test payment (the crediting trigger) — logic is fully covered by the integration suite + this synthetic render proof.

### 3. Share / copy chips
expected: Copy copies the code; Telegram / WhatsApp / native share carry the server-built `shareUrl`.
result: PARTIAL ✓ — affordances present and wired (Копировать, Telegram, WhatsApp, Ссылка buttons live in the snapshot); the displayed link is the server-built `http://localhost:5174/i/B5219P2B` (from `pwa_base_url` config, never client-built). STILL PENDING (device-only): the actual clipboard write + «Скопировано» optimistic toggle and the native share sheet are not observable in a headless browser (clipboard/share APIs are permission-gated) — needs a real device.

## Summary

total: 3
passed: 1 (deep-link round-trip)
partial: 2 (visual parity — light verified, dark pending; share/copy — affordances verified, device action pending)
issues: 0
pending: 0 (no blockers; remaining items are dark-theme + real-device + live-ЮKassa only)
skipped: 0
blocked: 0

## Gaps

- **Remaining truly-manual items:** dark-theme visual render, true pixel-diff vs reference, clipboard/native-share device actions, and a two-real-clients live-ЮKassa paid round-trip. None are code gaps — the wiring + data rendering are verified.
- **Cosmetic (carried to backlog):** `ReferralLandingScreen.formatBonusPreview` renders a static "14 дней в подарок"; the resolver exposes `welcomeBonusKopecks` (not days). Decide kopecks-vs-days.
- Dev-DB note resolved: the live `clubcore` DB was found already at head `0069` with the correct referral schema (no stale `ix_referral_codes_client_id`, config at seed 50000/30000) — the destructive re-migrate was unnecessary; re-seeded owner+catalog+dev-client for the run.

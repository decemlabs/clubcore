---
quick_id: 260614-j2d
status: complete
date: 2026-06-14
commits:
  - 126dcb58 feat(260614-j2d): GAP-1 reachable membership lifecycle entry points on client page
verification:
  typecheck: pass
  lint: pass
  tests: router-smoke 20 passed
  live_browser: sell + freeze end-to-end; owner/reception gating; dynamic freeze label — all verified
---

# Quick Task 260614-j2d — GAP-1: membership lifecycle UI entry points

Closed the structural gap from `.planning/v3.0-UAT-BROWSER-AUDIT.md`: the membership
lifecycle modal (sell/freeze/renew/cancel/refund) existed and worked but had no reachable
trigger. Added entry points on the live client page (`ClientPage.tsx` → `MembershipsSection`),
reusing the existing `SubscriptionModal` (no new modal, no backend change).

## What changed (single file: `pages/client/ClientPage.tsx`)

- `MembershipsSection` now takes `clientName`; `ClientPage` derives it from the client record.
- **Empty state** → «Оформить абонемент» button → opens the sell screen (`screen: 'create'`).
- **Active membership row** → «⋯» dropdown (mirrors the hero's `DropdownMenu` pattern):
  - Продлить → `renew`
  - Заморозить / Разморозить → `freeze` / `unfreeze` (chosen by `m.status === 'frozen'`)
  - Оформить возврат → `refund`
  - Отменить абонемент → `cancel`, rendered only when `can(role,'cancel','memberships')` (owner-only)
- `toMembershipPayload(m)` builds the modal payload from the flat `MembershipData` wire shape
  (the BUG-2 schema), so renew/freeze/refund/cancel get the membership they need.

## Live verification (against the running stack)

- Created a fresh client (no membership) → empty card shows «Оформить абонемент».
- Sell flow: pick «Месяц безлимит · 5 000 ₽» → «Создать и принять оплату» → toast
  **«Абонемент оформлен · Оплата 5 000 ₽ принята»**, membership row appears. (End-to-end through
  the UI — previously impossible.)
- Freeze flow: «⋯» → Заморозить → confirm → toast **«Абонемент заморожен»**, status flips to
  «Заморожен».
- Owner menu shows all four actions incl. «Отменить абонемент».
- **Reception** menu shows Продлить / **Разморозить** (dynamic label, status=frozen) / Оформить
  возврат, and **no «Отменить»** — owner-only gating confirmed.

renew / unfreeze / refund / cancel flow through the identical open→dispatcher→(already-tested
hook) path with the same payload that the freeze + sell checks validated.

## Notes

- Gates: `typecheck` ✅ `lint` ✅ `router-smoke` ✅ (20).
- Test data left in DB: client «Новиков Пётр» (+79995556677) with a now-frozen membership, from
  the live verification. Harmless; a reseed clears it.
- Still out of scope (separate decisions): hero «Удалить клиента» stub, mock sidebar/KPI/2FA chrome.

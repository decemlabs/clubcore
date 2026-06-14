---
quick_id: 260614-hux
status: complete
date: 2026-06-14
commits:
  - 27eec3ea fix(260614-hux): BUG-1 accept integer telegramUserId in clients schema
  - 0d107264 fix(260614-hux): BUG-2 align membership schema to flat backend wire shape
  - fe70a864 fix(260614-hux): BUG-3 add formatKopecks() — stop rendering money 100x too high
  - 29204e49 fix(260614-hux): BUG-4 omit undefined query params (schedule trainerId=undefined 422)
  - be9225ea fix(260614-hux): BUG-5 reconcile reports revenue + trainers schema to wire shape
  - 918252b8 fix(260614-hux): BUG-6 nullable audit actorUserId/actorEmailSnapshot
  - d434d96c fix(260614-hux): BUG-7 nullable session userAgent
  - 1254aac9 fix(260614-hux): BUG-8 guard check-in onMutate against gym-meta cache entry
  - e7924fc4 fix(260614-hux): UX-1 localize phone_exists 409 on client create
verification:
  typecheck: pass
  lint: pass
  tests: 340 passed (26 files)
  live_browser: all 9 verified against the running stack
---

# Quick Task 260614-hux — Fix v3.0 admin-app live-UAT bugs

Fixed the 8 bugs + 1 UX item found by `.planning/v3.0-UAT-BROWSER-AUDIT.md`. Root cause
for every one: a frontend Zod schema / money formatter / query-cache assumption diverged
from the REAL backend wire shape. Unit tests used mock fixtures matching the (wrong)
frontend shapes, so none were caught pre-wiring. Fixtures were rewritten to the real
shapes so the divergence cannot re-hide.

Frontend-only (no backend edits). Each bug committed atomically. Verified live in Chrome
against the running docker stack + dev server, not just unit tests.

## Per-bug

| Bug | Fix | Files | Live verify |
|-----|-----|-------|-------------|
| BUG-1 | `ClientSchema.telegramUserId` → `z.union([number,string]).nullable().optional()` (backend sends int) | clients/schemas.ts | /clients renders dev client (+79999999999) — was a full-list PageError |
| BUG-2 | `MembershipSchema` reworked nested→flat (`planNameSnapshot`/`priceKopecksSnapshot`/…); aligned ClientPage, SubscriptionModal, modals-context, memberships/api, ExpiringMemberships + test | 7 files | Петров membership row «Месяц безлимит / Активный / 5 000 ₽» renders |
| BUG-3 | added `formatKopecks(k)=RUB.format(k/100)`; swapped 9 kopecks call sites; ruble sites untouched | format.ts(+test) + 6 consumers | /plans «5 000 ₽» (was «500 000 ₽»); client amounts correct |
| BUG-4 | `appendQuery` skips undefined/null (transport-layer; preserves all-trainers view) — **deviation from plan's page-level fix, justified** | api/client.ts | /schedule renders; `trainer-slots` omits trainerId → 200 (was `=undefined`→422) |
| BUG-5 | revenue `pt_package`→`ptPackage`; trainers `data.rows[]`→`data.trainers[]` + field renames + nullable utilizationPct/avgRevenuePerSession; aligned ReportsPage + TopTrainers + tests | 7 files | Отчёты (Выручка+Тренеры), Финансы, dashboard (Выручка 30д + Топ тренеры) all render real data; «0%» not «null%» |
| BUG-6 | `actorUserId`/`actorEmailSnapshot` → `.nullable()`; consumers fall back to «Система» | audit/schemas.ts + parts.tsx + AuditDetailModal.tsx | Журнал действий renders; null-actor rows show «Система» |
| BUG-7 | `SessionSchema.userAgent` → `.nullable()`; regex guarded | settings/schemas.ts + SectionsTop.tsx | Настройки → Активные сессии renders; null UA → «Неизвестное устройство»; revoke reachable |
| BUG-8 | `useCheckIn` onMutate/onError skip non-list cache entries (`Array.isArray(data.items)`) — gym-meta query is under `visitsKeys.all` | visits/api.ts | Check-in success «Визит зафиксирован» (POST fires); `no_active_membership` 409 maps to its Russian copy |
| UX-1 | map 409 `phone_exists` → inline phone-field error «Клиент с таким телефоном уже существует» | NewClientModal.tsx | duplicate phone shows localized inline error (was raw «phone_exists» toast) |

## Notable deviation (BUG-4)

Plan proposed default-selecting the first trainer in SchedulePage. Verified against the
live backend that `GET /trainer-slots` **without** `trainerId` returns 200 (all-trainers),
while `trainerId=undefined` returns 422. Fixed at the transport layer (`appendQuery` strips
undefined/null) instead — default-selecting one trainer would have silently regressed the
intended `filter='all'` multi-trainer view. The transport fix also hardens every other
caller that passes optional query params.

## Missed-consumer catches (strict TS as the safety net)

The schema renames surfaced consumers the initial pass missed; `tsc` caught each before
commit: `modals-context.ts` + `ExpiringMemberships.tsx` (BUG-2), `RevenueChart.test.tsx`
(BUG-5), `AuditDetailModal.tsx` (BUG-6). All fixed; clean typecheck is the proof every
consumer was found.

## Out of scope (need product/design decisions — NOT done here)

- GAP-1: membership lifecycle (sell/freeze/renew/cancel/refund) has no reachable UI trigger
  (dead `ProfileSide`, mock `ProfileHero`, de-nav'd Messages). Hooks + modal + backend work
  (sell→201); only the entry point is missing.
- Hero «Удалить клиента» stub (toast, no DELETE — real delete is in the Edit modal).
- Mock sidebar count badges, Plans/Settings KPIs, Security 2FA/SMS block.

## Test data left in the seeded DB

reception@clubcore.dev user; client «Петров Иван» (+79991112201) w/ membership + visit;
dev client «Тестовый» given a membership + visit during BUG-8 verification. Harmless; a
reseed clears it.

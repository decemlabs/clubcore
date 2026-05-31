---
phase: 71
slug: client-checkout-full-pwa-screen-wiring
status: validated
nyquist_compliant: false
wave_0_complete: true
created: 2026-05-31
---

# Phase 71 — Validation Strategy

> Retroactively reconstructed from phase artifacts (State B). Backend checkout
> path and PWA adapter/identity logic are fully automated; the residual
> verifications are runtime/E2E/sandbox confirmations of already-automated logic.

---

## Test Infrastructure

| Property | Value |
|----------|-------|
| **Framework (backend)** | pytest + pytest-asyncio (httpx ASGITransport) |
| **Framework (PWA)** | Vitest 2.1.9 + jsdom |
| **Config files** | `apps/backend/pyproject.toml` · `apps/client-pwa/vitest.config.ts` |
| **Quick run command** | `cd apps/client-pwa && pnpm vitest run` |
| **Full suite command** | `cd apps/backend && pytest tests/integration/client_portal tests/integration/online_payments -x && cd ../client-pwa && pnpm vitest run` |
| **Estimated runtime** | backend ~30–60s · PWA ~2s |

---

## Sampling Rate

- **After every task commit:** Run the relevant `pnpm vitest run <file>` / `pytest <file>`
- **After every plan wave:** Run the full suite command
- **Before `/gsd:verify-work`:** Full suite must be green
- **Max feedback latency:** ~60 seconds

---

## Per-Task Verification Map

| Task ID | Plan | Wave | Requirement | Threat Ref | Secure Behavior | Test Type | Automated Command | File Exists | Status |
|---------|------|------|-------------|------------|-----------------|-----------|-------------------|-------------|--------|
| 71-01 | 01 | 1 | CPAY-01..05 | T-71-01/02/03/04 | Extracted `_sell_subject` core preserves server-side price, email gate, idempotency, audit chain; staff path byte-identical | integration | `cd apps/backend && pytest tests/integration/online_payments -x` | ✅ | ✅ green |
| 71-02 | 02 | 2 | CPAY-01..05 | T-71-05/06/09 | Client checkout endpoints + IDOR-safe status via Protocol-slot (no direct online_payments import) | integration | `cd apps/backend && pytest tests/integration/client_portal -x` | ✅ | ✅ green |
| 71-03 | 03 | 3 | CPAY-01 | T-71-08 | Membership checkout → 201 + confirmation_url | integration | `pytest tests/integration/client_portal/test_checkout.py::test_membership_checkout_returns_confirmation_url` | ✅ | ✅ green |
| 71-03 | 03 | 3 | CPAY-02 | T-71-07 | PT-package checkout idempotent via client-supplied key | integration | `pytest .../test_checkout.py::test_pt_checkout_idempotency_key_replay` | ✅ | ✅ green |
| 71-03 | 03 | 3 | CPAY-03 | T-71-05/11/12 | Status endpoint anti-oracle (id+status only) + IDOR 404-collapse | integration | `pytest .../test_checkout.py::test_status_returns_coarse_state_only` · `::test_status_idor_404_for_other_client` | ✅ | ✅ green |
| 71-03 | 03 | 3 | CPAY-04 | T-71-10/14 | 54-ФЗ email gate → 422 `client_email_required_for_online_payment` | integration | `pytest .../test_checkout.py::test_checkout_without_email_returns_422` | ✅ | ✅ green |
| 71-03 | 03 | 3 | CPAY-05 | T-71-08/13 | Replay returns same confirmation_url; duplicate webhook single-activates | integration | `pytest .../test_checkout.py::test_membership_checkout_replay_returns_same_url` · `::test_duplicate_webhook_does_not_double_activate` | ✅ | ✅ green |
| 71-04 | 04 | 3 | PWA-05 | T-71-15/19/22 | React Query foundation + central data swap-seam; net-new screens cannot import query layer (ESLint boundary) | lint/build | `cd apps/client-pwa && pnpm lint && pnpm build` | ✅ | ✅ green |
| 71-05/09/10 | 05/09/10 | 4 | PWA-05 | T-71-18 | Home/Profile/Plans adapters read camelCase contract; identity bound to `/client/me`; null membership → real empty state | unit | `cd apps/client-pwa && pnpm vitest run src/screens` | ✅ | ✅ green |
| 71-06 | 06 | 5 | PWA-05 | T-71-26/29 | Book/QR wired to Phase-70 endpoints; QR token refresh before TTL | unit/build | `cd apps/client-pwa && pnpm vitest run && pnpm build` | ✅ | ✅ green |
| 71-08 | 08 | 1 | PWA-07 | T-71-16 | SW serves `/api/*` network-only (never cached); `gym-v2` evicted on activate; guard precedes nav/cache-first branches | unit | `cd apps/client-pwa && pnpm vitest run src/sw/sw.test.jsx` | ✅ | ✅ green |

*Status: ⬜ pending · ✅ green · ❌ red · ⚠️ flaky*

---

## Wave 0 Requirements

Existing infrastructure covers all phase requirements. The retroactive gap fill added:

- [x] `apps/client-pwa/src/sw/sw.test.jsx` — PWA-07 service-worker `/api/*` network-only guard + `gym-v3` activate-eviction logic (added by this validation pass).

---

## Manual-Only Verifications

These are runtime/E2E/sandbox confirmations of logic already automated above. They cannot run under ASGITransport/jsdom.

| Behavior | Requirement | Why Manual | Test Instructions |
|----------|-------------|------------|-------------------|
| SW runtime Cache-Storage population (zero `/api/*` keys; `gym-v2` actually evicted on a real install) | PWA-07 | Cache-Storage population is live browser behavior; the *logic* (guard ordering, eviction) is now unit-tested, but actual eviction state needs Chrome DevTools | Build/run dev stack, log in (+79999999999 / 111111), DevTools → Application → Cache Storage: confirm active worker `gym-v3`, no `gym-v2` cache, zero `/api/*` keys; Network tab shows every `/api/*` `(from network)`; offline reload renders shell. (71-HUMAN-UAT test 2 — re-verified live, passed.) |
| Live real-data rendering (real identity + real/empty membership + numeric plan prices) | PWA-05 / CPAY-01/02 | Requires live backend + seeded catalog + logged-in session to render real `/client/me`+`/client/home`+`/client/plans`; field-name correctness is statically + unit verified | Log in as dev client, confirm Home greeting = real first name, no-membership → 'Нет абонемента' + 'Выбрать тариф'; Profile real name/phone/email; Plans cards show numeric '₽' + 'N дней'. (71-HUMAN-UAT test 1 — re-verified live, passed.) |
| End-to-end ЮKassa membership/PT purchase round-trip | CPAY-01/02/03 | Requires live/sandboxed ЮKassa account (dev placeholder `shop_id=000000` → 502 `yookassa_permanent_error`) | Log in, Plans → checkout → ЮKassa redirect → `/payment/return` shows only 'Ожидаем подтверждение…' while pending; Home shows active membership only after `payment.succeeded` webhook (no premature activation). (Carried forward — pending sandbox creds.) |

---

## Validation Sign-Off

- [x] All tasks have automated verify or Wave 0 dependencies
- [x] Sampling continuity: no 3 consecutive tasks without automated verify
- [x] Wave 0 covers all MISSING references (PWA-07 SW logic test added)
- [x] No watch-mode flags
- [x] Feedback latency < 60s
- [ ] `nyquist_compliant: true` — **not set**: 3 residual verifications are inherently runtime/E2E/sandbox (manual-only). All *logic* is automated; manual items are live confirmations.

**Approval:** validated 2026-05-31 (partial — automated where feasible)

---

## Validation Audit 2026-05-31

| Metric | Count |
|--------|-------|
| Gaps found | 1 (PWA-07 SW logic) |
| Resolved | 1 |
| Escalated | 0 |
| Manual-only (runtime/E2E/sandbox) | 3 |

Reconstructed from artifacts (State B). Backend CPAY-01..05 fully automated (9 integration tests in `test_checkout.py` + supporting suites). PWA-05 adapter/identity logic unit-covered. PWA-07 service-worker `/api/*` network-only + eviction logic newly covered by `src/sw/sw.test.jsx` (3 tests, green). Residual manual-only items are live confirmations of already-automated logic.

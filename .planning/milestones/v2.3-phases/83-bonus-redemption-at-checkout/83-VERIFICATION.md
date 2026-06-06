---
phase: 83-bonus-redemption-at-checkout
verified: 2026-06-05T00:00:00Z
status: human_needed
score: 11/11 must-haves verified
overrides_applied: 0
human_verification:
  - test: "Trigger a real checkout with bonusOn=true and verify the YooKassa payment sheet opens; after payment succeeds confirm loyalty balance decreases"
    expected: "After payment.succeeded webhook fires, loyalty_ledger has one negative redemption row and the balance decreases by exactly the clamped amount"
    why_human: "Requires live YooKassa test-mode payment flow and webhook delivery; cannot be exercised with ASGI transport alone"
  - test: "Render CheckoutSheet in a browser with a positive balance; verify the bonus section appears with correct balance amount, toggle activates the ~ estimate row and changes the pay-button label, and toggleOFF hides the discount row"
    expected: "UI section visible, formatMoney(balanceKopecks) shown in subtitle, bonus discount row with ~ chip appears on toggle ON, pay button prefixed with ~ when bonusOn, section absent when balance=0"
    why_human: "Visual rendering and interactive toggle behaviour cannot be verified by grep or vitest alone"
---

# Phase 83: Bonus Redemption at Checkout — Verification Report

**Phase Goal:** Клиент списывает бонусы скидкой в чекауте; сервер авторитетно пересчитывает discount_kopecks, redemption записывается атомарно и идемпотентно на payment.succeeded webhook; PWA CheckoutSheet показывает реальный баланс за флагом clubBonuses.
**Verified:** 2026-06-05
**Status:** human_needed
**Re-verification:** No — initial verification

---

## Goal Achievement

### Observable Truths

| # | Truth | Status | Evidence |
|---|-------|--------|----------|
| 1 | Migration 0055 adds loyalty_ledger.online_payment_id FK + partial UNIQUE index + online_payments.loyalty_redeem_kopecks | ✓ VERIFIED | `0055_loyalty_redemption_columns.py` present; upgrade() creates all three schema objects; downgrade() reverses in correct order |
| 2 | alembic check / test_alembic_clean stays green — new index allowlisted in env.py | ✓ VERIFIED | `"uq_loyalty_ledger_online_payment_id"` present in env.py allowlist at line 104 |
| 3 | loyalty_redeemed LOCKED audit event + payload schema registered BEFORE any callsite (INFRA-15); count-lock guards assert 103 | ✓ VERIFIED | `audit.py:466` — `("loyalty_redeemed","loyalty")` in LOCKED_AUDIT_EVENTS; `audit_payloads.py:1294-1411` — LoyaltyRedeemedPayload with extra=forbid; both count-lock guards assert 103 |
| 4 | Client sends loyaltyRedeemKopecks; server caps discount = min(requested, balance, post_promo_price-1); client never sets the final discount (D-06) | ✓ VERIFIED | `client_portal/schemas.py:267` field via to_camel alias; `client_portal/service.py:741-766` clamp block computing min(requested, balance, post_promo_price-1); `online_payments/service.py:353-354` max(1,...) floor; router threads at lines 667, 712 |
| 5 | Exact server-computed redeem amount persisted on online_payments.loyalty_redeem_kopecks at checkout | ✓ VERIFIED | `online_payments/repository.py:46-87` conditional-kwarg insert; `online_payments/service.py:444` passes loyalty_redeem_kopecks= to repository |
| 6 | On payment.succeeded the webhook writes exactly one negative redemption ledger row, idempotent on (online_payment_id), clamped to current balance, ledger never negative | ✓ VERIFIED | `handlers.py:545-550` calls record_loyalty_redemption gated on loyalty_redeem_kopecks>0; `loyalty/service.py:290-385` implements idempotent pg_insert with on_conflict_do_nothing(index_elements, index_where), overdraft clamp, RETURNING-gated audit emit |
| 7 | Promo discount attribution fixed: promo_discount = plan_price - amount_kopecks - loyalty_redeem_kopecks | ✓ VERIFIED | `handlers.py:528-530` — `max(0, plan_price_kopecks - row.amount_kopecks - (row.loyalty_redeem_kopecks or 0))`; plan-price SELECT hoisted to run for EITHER promo OR loyalty |
| 8 | loyalty_redeemed audit event emitted from webhook redemption write; no debit when payment not succeeded | ✓ VERIFIED | `loyalty/service.py:369-379` emits audit.emit("loyalty_redeemed",...) only after RETURNING confirms insert; handlers.py block is inside payment.succeeded UoW only |
| 9 | CheckoutSheet shows real balance via useClientLoyaltyBalance(); BONUS_PLACEHOLDER removed; clubBonuses flag ON | ✓ VERIFIED | `CheckoutSheet.jsx:4` imports useClientLoyaltyBalance; line 150-151 calls it; `grep -c BONUS_PLACEHOLDER` = 0; line 47 clubBonuses: true |
| 10 | Toggling 'Списать бонусы' sends loyaltyRedeemKopecks=balanceKopecks in both checkout mutations and shows estimate-only discount row + ~ qualifier (D-06) | ✓ VERIFIED | Lines 241, 252 — conditional spread `...(bonusOn && balanceKopecks > 0 ? { loyaltyRedeemKopecks: balanceKopecks } : {})`; lines 378-379 bonusEstimateKopecks/estimatedTotal are display-only; line 684 ~ prefix on pay button |
| 11 | openapi.json + schema.d.ts additively regenerated; loyaltyRedeemKopecks present; PWA tsc -b clean | ✓ VERIFIED | `openapi.json` contains loyaltyRedeemKopecks (1 match); `schema.d.ts:3691` — `loyaltyRedeemKopecks?: number \| null`; orchestrator gate confirms tsc -b clean |

**Score:** 11/11 truths verified

---

### Required Artifacts

| Artifact | Expected | Status | Details |
|----------|----------|--------|---------|
| `apps/backend/alembic/versions/0055_loyalty_redemption_columns.py` | Migration with FK + partial UNIQUE + BigInteger column | ✓ VERIFIED | All three DDL operations present; downgrade reverses correctly |
| `apps/backend/app/core/audit_payloads.py` | LoyaltyRedeemedPayload + AUDIT_PAYLOAD_SCHEMAS entry | ✓ VERIFIED | Class at line 1294; registered at line 1411 |
| `apps/backend/app/modules/loyalty/service.py` | record_loyalty_redemption — idempotent, overdraft-clamped, audit-emitting | ✓ VERIFIED | Function at line 290; full implementation with on_conflict_do_nothing, clamp, RETURNING-gated audit |
| `apps/backend/tests/integration/test_loyalty_redemption.py` | 5 integration tests covering idempotency, overdraft, stacking, no-pay, D-06 cap | ✓ VERIFIED | 5 test functions present: test_redm_01 through test_redm_05 |
| `apps/client-pwa/src/screens/sheets/CheckoutSheet.jsx` | Real-balance bonus redemption wiring behind clubBonuses=true | ✓ VERIFIED | useClientLoyaltyBalance called; clubBonuses=true; loyaltyRedeemKopecks spread in both mutations; BONUS_PLACEHOLDER=0 |
| `apps/client-pwa/src/screens/sheets/CheckoutSheet.bonus.test.jsx` | Balance display + toggle estimate + request-body wiring + hidden-on-zero tests | ✓ VERIFIED | 8 tests covering all spec'd cases including loyaltyRedeemKopecks assertion |

---

### Key Link Verification

| From | To | Via | Status | Details |
|------|----|-----|--------|---------|
| client_portal/service.py checkout (membership + pt) | online_payments/service.py _sell_subject_core | loyalty_redeem_kopecks=actual_loyalty_redeem param | ✓ WIRED | `service.py:788, 894` pass actual_loyalty_redeem; `_sell_subject_core:212` accepts the param |
| yookassa/handlers.py succeeded UoW | loyalty/service.py record_loyalty_redemption | row.loyalty_redeem_kopecks gate + call | ✓ WIRED | `handlers.py:111` import; lines 545-550 gate + call |
| CheckoutSheet.jsx launchCheckout | checkout mutateAsync request body | `...(bonusOn && balanceKopecks > 0 ? { loyaltyRedeemKopecks: balanceKopecks } : {})` | ✓ WIRED | Present at lines 241 (membership) and 252 (PT) |
| apps/backend/openapi.json ClientCheckoutRequest | packages/api-client/src/schema.d.ts | openapi-typescript codegen | ✓ WIRED | loyaltyRedeemKopecks present in both files |
| audit.py LOCKED_AUDIT_EVENTS | audit_payloads.py AUDIT_PAYLOAD_SCHEMAS | ('loyalty_redeemed', 'loyalty') tuple in both | ✓ WIRED | audit.py:466 + audit_payloads.py:1411 |
| alembic/env.py allowlist | migration 0055 partial index | uq_loyalty_ledger_online_payment_id literal skip entry | ✓ WIRED | env.py:104 |

---

### Data-Flow Trace (Level 4)

| Artifact | Data Variable | Source | Produces Real Data | Status |
|----------|---------------|--------|--------------------|--------|
| CheckoutSheet.jsx bonus section | balanceKopecks | useClientLoyaltyBalance() → GET /client/loyalty/balance | Yes — hook fetches from real API endpoint (Phase 82); not hardcoded | ✓ FLOWING |
| record_loyalty_redemption | actual_debit | _sum_balance(session, client_id) — raw SQL SUM fold | Yes — reads live ledger rows | ✓ FLOWING |
| handlers.py loyalty block | row.loyalty_redeem_kopecks | online_payments row persisted at checkout | Yes — server-computed at checkout, never client-settable | ✓ FLOWING |

---

### Behavioral Spot-Checks

| Behavior | Command | Result | Status |
|----------|---------|--------|--------|
| record_loyalty_redemption function exists and is callable | `grep -n "async def record_loyalty_redemption" loyalty/service.py` | Line 290 | ✓ PASS |
| loyaltyRedeemKopecks in schema.d.ts | `grep -c loyaltyRedeemKopecks packages/api-client/src/schema.d.ts` | 1 | ✓ PASS |
| BONUS_PLACEHOLDER absent from CheckoutSheet.jsx | `grep -c BONUS_PLACEHOLDER CheckoutSheet.jsx` | 0 | ✓ PASS |
| clubBonuses flag is true | `grep "clubBonuses" CheckoutSheet.jsx` | `clubBonuses: true` at line 47 | ✓ PASS |
| Both count-lock guards assert 103 | `grep "== 103" test_audit_taxonomy.py test_phase51_audit_chain_invariants.py` | Both at line 237 / 57 | ✓ PASS |
| Full backend test suite | Orchestrator gate: 2537 pass, no new failures | All green | ✓ PASS |
| PWA vitest 149/149 | Orchestrator gate: 149 passed, 22 files | All green | ✓ PASS |

---

### Probe Execution

No conventional probe scripts (`scripts/*/tests/probe-*.sh`) declared or found for this phase. The orchestrator gate already ran the backend and PWA test suites — results recorded in Behavioral Spot-Checks above.

---

### Requirements Coverage

| Requirement | Source Plan | Description | Status | Evidence |
|-------------|-------------|-------------|--------|----------|
| REDM-01 | 83-01, 83-02 | Client sends loyaltyRedeemKopecks; server caps discount authoritatively; D-06 not undermined | ✓ SATISFIED | schemas.py field, service.py clamp block, _sell_subject_core param, repository kwarg, router wiring |
| REDM-02 | 83-01, 83-02 | Redemption written atomically on payment.succeeded, idempotent by online_payment_id; no debit on cancel | ✓ SATISFIED | record_loyalty_redemption with on_conflict_do_nothing + RETURNING gate; handlers.py inside succeeded UoW only |
| REDM-03 | 83-03 | PWA CheckoutSheet shows real balance + redemption control behind clubBonuses ON; BONUS_PLACEHOLDER removed | ✓ SATISFIED | useClientLoyaltyBalance wired; clubBonuses=true; BONUS_PLACEHOLDER=0; loyaltyRedeemKopecks in both mutations; section hidden on zero/loading |

All three requirements satisfied. No orphaned requirements detected (REQUIREMENTS.md maps REDM-01..03 exclusively to Phase 83).

---

### Anti-Patterns Found

| File | Line | Pattern | Severity | Impact |
|------|------|---------|----------|--------|
| `CheckoutSheet.jsx:756` | 756 | `placeholder="Промокод"` | ℹ️ Info | Input placeholder attribute for promo code field — HTML semantics, not a stub pattern; unrelated to Phase 83 work |

No TBD / FIXME / XXX markers found in Phase 83 files. No empty implementations. No hardcoded data returned where real data is expected. The ring SVG `stroke-dashoffset: 45` is static by design (decorative chrome; Gold tier progress deferred to TIER-01 per 83-UI-SPEC).

---

### Human Verification Required

#### 1. Live Payment Flow with Bonus Redemption

**Test:** In YooKassa test-mode, initiate a checkout with bonusOn=true (balance > 0). Complete the payment. After the payment.succeeded webhook fires, query loyalty_ledger and verify one negative redemption row with the clamped amount; verify the client's balance decreases accordingly.
**Expected:** Exactly one ledger row with entry_type='redemption', amount_kopecks = -(clamped debit), online_payment_id = payment UUID; SUM(amount_kopecks) for that client equals prior balance minus debit.
**Why human:** Requires live YooKassa test-mode payment + real webhook delivery. ASGITransport integration tests cover the logic but cannot substitute for end-to-end webhook routing.

#### 2. PWA CheckoutSheet Bonus UX

**Test:** In the PWA dev build (positive loyalty balance seeded), open CheckoutSheet. Verify: (a) "Бонусы клуба" section renders with "На счёте X ₽" subtitle; (b) toggling ON renders a "Бонусы" discount row with "~" chip; (c) pay button shows "~" prefix; (d) toggling OFF hides the discount row; (e) with balance=0 the section is absent entirely.
**Expected:** Section visible when balance>0; estimate-only row visible when bonusOn; ~ prefix on pay button; section hidden on zero balance.
**Why human:** Visual rendering, toggle interaction, and countUp animation cannot be verified by vitest or grep.

---

### Gaps Summary

No gaps. All 11 must-haves verified at all four levels (exists, substantive, wired, data-flowing). Requirements REDM-01, REDM-02, REDM-03 fully satisfied. The only open items are human verification steps for live payment flow and PWA visual behavior, which are standard end-of-phase checks that cannot be automated.

---

_Verified: 2026-06-05_
_Verifier: Claude (gsd-verifier)_

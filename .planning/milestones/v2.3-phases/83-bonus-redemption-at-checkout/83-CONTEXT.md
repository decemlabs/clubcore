# Phase 83: Bonus Redemption at Checkout - Context

**Gathered:** 2026-06-05
**Status:** Ready for planning

<domain>
## Phase Boundary

Let a client spend loyalty bonuses as a server-authoritative discount at ЮKassa
checkout. The server recomputes `discount_kopecks` (client never sets the discount),
the redemption is written to the append-only `loyalty_ledger` as a negative row
atomically + idempotently on the `payment.succeeded` webhook (mirroring the
`promo_codes` redemption precedent), and the PWA `CheckoutSheet` shows the real
balance + a redemption control behind the `clubBonuses` flag. Builds on Phase 82's
ledger/balance foundation. The D-06 anti-oracle / webhook-locked-activation
invariant is preserved.

</domain>

<decisions>
## Implementation Decisions

### Redemption Request & Server Computation (REDM-01)
- Client sends an integer `loyaltyRedeemKopecks` (wire) in the checkout request body — a *desired* redeem amount, NOT an authoritative discount.
- Server caps authoritatively: `discount = min(requested, currentBalance, amountAfterPromo)`. The client never sets the final discount (D-06 — discount is server-side only).
- Stacks with promo codes: bonus redemption applies to the **post-promo remainder**. Both discounts are server-computed. The final charged `amount_kopecks` = `plan_price − promo_discount − loyalty_redeem`.
- The exact server-computed redeem amount is persisted on a NEW `online_payments.loyalty_redeem_kopecks` column at checkout (mirrors the `promo_code_id` persistence precedent), so the succeeded-webhook writes the exact debit.

### Webhook Redemption Write & Idempotency (REDM-02)
- `loyalty_ledger` gains a nullable `online_payment_id` column (RESTRICT FK → online_payments.id) + a partial UNIQUE index `(online_payment_id) WHERE entry_type='redemption'` — mirrors `uq_promo_redemptions_online_payment_id`. Idempotency key for the redemption debit is `(online_payment_id)`.
- The redemption row is written inside the existing `app/api/v1/_internal/yookassa/handlers.py` succeeded UoW, directly beside `record_promo_redemption`, co-transactional + idempotent via `pg_insert(...).on_conflict_do_nothing(...)`. Webhook replay is safe.
- The negative-amount debit row uses `entry_type='redemption'` (reserved in Phase 82), `amount_kopecks = −loyalty_redeem_kopecks`.
- **Overdraft guard**: the webhook debits the stored `loyalty_redeem_kopecks` but clamps to the *current available balance* (SUM fold) so the ledger can never go negative under concurrent checkouts; if the clamp reduces the debit below the stored amount, log the discrepancy (the client already paid the discounted price — the discrepancy is absorbed, never an overdraft).
- **IMPORTANT — promo discount attribution fix**: the existing promo redemption calc in handlers.py is `discount = plan_price − amount_kopecks`. With bonuses also reducing `amount_kopecks`, that over-attributes to promo. The webhook MUST compute `promo_discount = plan_price − amount_kopecks − loyalty_redeem_kopecks` so promo and bonus discounts are attributed correctly.
- Audit: NEW LOCKED audit event `loyalty_redeemed` (payload `{client_id, entry_id, amount_kopecks (negative), online_payment_id}`, resource_type `loyalty`), registered in `LOCKED_AUDIT_EVENTS` + payload schema BEFORE the callsite (INFRA-15); count-lock guard tests bumped (102 → 103). Symmetry with `loyalty_accrued`.

### PWA CheckoutSheet (REDM-03)
- Remove the mock `BONUS_PLACEHOLDER = { balance: 1080, toGold: 220 }`; fetch the real balance via `useClientLoyaltyBalance()` (Phase 82 hook).
- Redemption control: a "Списать бонусы" toggle that redeems `min(balance, payable)` (max redemption); server recomputes the authoritative discount.
- Total display: the client shows an *estimate* discount/total line, but the authoritative charged total comes from the server (D-06 — client never mutates the charged total). The redeem intent is sent at checkout; the deterministic estimate (min(balance, amount)) keeps the UI honest.
- Flip the `clubBonuses` feature flag ON.

### Anti-Oracle Return Screen (REDM-02 / D-06)
- Invariant unchanged: the redemption ledger row is written ONLY on `payment.succeeded`. The return screen shows pending and never confirms the debit/payment result before the webhook (D-06 anti-oracle).
- No-payment / cancel path: no succeeded webhook → no ledger debit; balance stays intact.

### Claude's Discretion
- Exact wire field naming for the estimate response, index/constraint naming, migration sequence number (next after 0054), and PWA control styling — at plan/execute discretion following established conventions and the 82-UI-SPEC visual language.

</decisions>

<code_context>
## Existing Code Insights

### Reusable Assets
- `app/api/v1/_internal/yookassa/handlers.py:496-528` — the succeeded UoW promo-redemption block is the exact analog: reads `row.promo_code_id`, computes discount from plan price, calls idempotent `record_promo_redemption(session, ...)`. Add the loyalty redemption write here and FIX the promo discount attribution.
- `app/modules/promo_codes/service.py record_promo_redemption` — idempotent `pg_insert(...).on_conflict_do_nothing(constraint="uq_promo_redemptions_online_payment_id")` pattern.
- `app/modules/loyalty/` (Phase 82) — `LoyaltyLedger` model (`entry_type` already allows `'redemption'`), `service.py` (balance SUM fold, caller-owns-txn), audit registration pattern.
- `app/modules/client_portal/service.py:682-720` `client_checkout_membership` — promo validation + `price_override_kopecks` + `applied_promo_code_id` plumbing into the checkout core; the loyalty redeem amount threads the same way.
- `app/modules/client_portal/schemas.py:256` `ClientCheckoutRequest` — add `loyalty_redeem_kopecks` (wire `loyaltyRedeemKopecks`) beside `promo_code` / `save_payment_method`.
- `app/modules/online_payments/{models,repository,service}.py` — `promo_code_id` column + plumbing is the template for the new `loyalty_redeem_kopecks` column.
- PWA `apps/client-pwa/src/screens/sheets/CheckoutSheet.jsx` — `BONUS_PLACEHOLDER` (line 52), `clubBonuses` flag (line 47), promo discount wiring (`promoResult`, `discount`) is the analog for the bonus discount line.

### Established Patterns
- Append-only ledger; balance = SUM fold; integer kopecks; no float.
- Redemption idempotency keyed on `(online_payment_id)`; webhook-replay-safe `on_conflict_do_nothing`.
- Audit events registered before callsites (INFRA-15); count-lock guard tests bump.
- D-06: webhook-locked activation + anti-oracle return screen; discount server-authoritative.
- IDOR-safe client endpoints via `require_client()` principal only.
- caller-owns-txn (no session.commit in services / handlers own the UoW commit).

### Integration Points
- Checkout: `client_checkout_membership` + `client_checkout_pt_package` (client_portal) → checkout core (`_sell_subject_core` / online_payments) → persist `loyalty_redeem_kopecks` on the row (alongside `promo_code_id`).
- Webhook: `app/api/v1/_internal/yookassa/handlers.py` succeeded UoW — write loyalty redemption + fix promo attribution.
- Migration: next after `0054_loyalty_ledger` — adds `loyalty_ledger.online_payment_id` + partial UNIQUE, and `online_payments.loyalty_redeem_kopecks`.
- Audit: `app/core/audit.py` + `audit_payloads.py` + count-lock tests.
- PWA: `CheckoutSheet.jsx` (+ both checkout hooks that thread the redeem intent).

</code_context>

<specifics>
## Specific Ideas

- Promo-attribution bug fix is mandatory: with bonus stacking, `promo_discount = plan_price − amount_kopecks − loyalty_redeem_kopecks` (not `plan_price − amount_kopecks`). Add a regression test that exercises promo + bonus on the same payment and asserts both ledger rows carry the correct discount.
- Overdraft guard test: concurrent/duplicate checkout reserving more than balance → webhook clamps; ledger balance never negative.
- Idempotency test: replaying `payment.succeeded` writes exactly one redemption row.

</specifics>

<deferred>
## Deferred Ideas

- Cash-payment bonus redemption — out of scope (v2.3 redemption is bound to the ЮKassa webhook per REQUIREMENTS out-of-scope).
- Partial-amount numeric redemption input in the PWA — deferred; v2.3 ships the max-redeem toggle.
- OpenAPI byte-stable freeze + `_v23Checks` guards for the new redemption fields → Phase 85.

</deferred>

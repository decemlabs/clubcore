---
phase: 83-bonus-redemption-at-checkout
reviewed: 2026-06-05T12:00:00Z
depth: deep
files_reviewed: 14
files_reviewed_list:
  - apps/backend/alembic/versions/0055_loyalty_redemption_columns.py
  - apps/backend/app/api/v1/_internal/yookassa/handlers.py
  - apps/backend/app/core/audit.py
  - apps/backend/app/core/audit_payloads.py
  - apps/backend/app/modules/client_portal/schemas.py
  - apps/backend/app/modules/client_portal/service.py
  - apps/backend/app/modules/loyalty/models.py
  - apps/backend/app/modules/loyalty/service.py
  - apps/backend/app/modules/online_payments/models.py
  - apps/backend/app/modules/online_payments/repository.py
  - apps/backend/app/modules/online_payments/service.py
  - apps/client-pwa/src/screens/sheets/CheckoutSheet.jsx
  - apps/backend/tests/integration/test_loyalty_redemption.py
  - apps/backend/app/modules/client_portal/router.py
findings:
  critical: 1
  warning: 3
  info: 2
  total: 6
status: issues_found
---

# Phase 83: Code Review Report

**Reviewed:** 2026-06-05T12:00:00Z
**Depth:** deep
**Files Reviewed:** 14
**Status:** issues_found

## Summary

Phase 83 adds bonus-redemption-at-checkout: clients can apply loyalty-balance kopecks toward a payment. The webhook infrastructure (idempotency, overdraft clamp, D-06 anti-oracle, RETURNING-gated audit emit, caller-owns-txn discipline) is well-structured. The migration, ORM model, and audit taxonomy are correct.

One critical financial bug was found in the two-layer price override design: `client_portal.service` reduces `price_override` by the loyalty debit AND passes `loyalty_redeem_kopecks` to the core; the core then subtracts it a second time, so the client is charged `2 × loyalty_debit` less than intended. Three warnings cover missing input validation, a stale-data risk in the plan-price read, and a PWA display discrepancy. Two info items flag a missing payload constraint and a benign `noqa` suppression.

---

## Critical Issues

### CR-01: Double-subtraction of loyalty discount — client charged `2 × loyalty_debit` less than the gym intends

**File:** `apps/backend/app/modules/client_portal/service.py:766` and `apps/backend/app/modules/online_payments/service.py:353-354`

**Issue:**
`client_checkout_membership` (and the identical `client_checkout_pt_package` path) computes the post-loyalty price *and* sets `price_override` to the already-reduced value before calling the core:

```python
# client_portal/service.py lines 765-766
actual_loyalty_redeem = clamped
price_override = post_promo_price - clamped   # already loyalty-reduced
```

Then it passes **both** to `invoke_client_checkout_core`:

```python
price_override_kopecks=price_override,       # post_promo - clamped
loyalty_redeem_kopecks=actual_loyalty_redeem # clamped
```

Inside `_sell_subject_core` (online_payments/service.py):

```python
if price_override_kopecks is not None:
    price_kopecks = price_override_kopecks   # post_promo - clamped

if loyalty_redeem_kopecks and loyalty_redeem_kopecks > 0:
    price_kopecks = max(1, price_kopecks - loyalty_redeem_kopecks)
    # = max(1, (post_promo - clamped) - clamped) = post_promo - 2*clamped  ← WRONG
```

**Concrete example (no promo, loyalty only):**
- Plan price: 5 000 ₽ (500 000 kopecks)
- Loyalty balance: 1 000 ₽ (100 000 kopecks)
- Intended charge: 4 000 ₽; ledger debit: 1 000 ₽
- Actual charge sent to YooKassa: 3 000 ₽ — gym loses 1 000 ₽ per such transaction

The `loyalty_redeem_kopecks` column stored on `online_payments` is correct (= clamped), so the webhook later debits the ledger correctly for 1 000 ₽. The financial loss is purely in the amount collected from the client.

This bug is **not** caught by the integration tests in `test_loyalty_redemption.py` because those tests seed `online_payments` rows directly with pre-computed `amount_kopecks` values, bypassing `client_portal.service` entirely.

**Fix:**
In `client_portal.service`, do **not** subtract `clamped` from `price_override` before calling the core; pass the post-promo price unchanged and let the core perform the single loyalty subtraction:

```python
# client_checkout_membership — replace lines 765-766
actual_loyalty_redeem = clamped
# price_override stays as post_promo_price (NOT reduced — core handles the debit)
# price_override = post_promo_price - clamped  ← DELETE THIS LINE

# Then the invoke call passes the correct post-promo price (pre-loyalty):
result = await invoke_client_checkout_core(
    ...
    price_override_kopecks=price_override,     # = post_promo_price (not yet loyalty-reduced)
    loyalty_redeem_kopecks=actual_loyalty_redeem,
)
```

Apply the same fix to `client_checkout_pt_package` (lines 871-872).

---

## Warnings

### WR-01: Plan-price lookup in `client_portal.service` misses `deleted_at IS NULL` filter

**File:** `apps/backend/app/modules/client_portal/service.py:748-756` (membership) and `852-862` (PT)

**Issue:**
The inline plan-price read for the loyalty clamp uses:

```python
text("SELECT price_kopecks FROM membership_plans WHERE id = :id")
```

No `AND deleted_at IS NULL` guard. If a plan is archived (soft-deleted) between the user opening the checkout screen and submitting the request, the archived plan's price is used for the loyalty cap calculation rather than returning a useful error. This contradicts the behavior of `_read_membership_plan_or_raise` in `online_payments.service` (which does filter by `deleted_at IS NULL`) and may cause a subtle UX inconsistency: the loyalty clamp could silently be based on the archived price while `_read_membership_plan_or_raise` in the core then raises `NotFoundError`.

**Fix:**
```python
text("SELECT price_kopecks FROM membership_plans WHERE id = :id AND deleted_at IS NULL")
# same for pt_package_plans
```

---

### WR-02: `ClientCheckoutRequest.loyalty_redeem_kopecks` accepts negative values without schema rejection

**File:** `apps/backend/app/modules/client_portal/schemas.py:267`

**Issue:**
```python
loyalty_redeem_kopecks: int | None = None
```
No `ge=0` or `gt=0` constraint. A client sending a negative value (e.g. `-1`) is silently discarded by the `if loyalty_redeem_kopecks and loyalty_redeem_kopecks > 0` guard in service code, so there is no exploitable path. However, the schema should enforce the invariant explicitly, consistent with how other numeric fields (e.g. `amount_kopecks` on the DB model) are constrained.

**Fix:**
```python
from pydantic import Field

loyalty_redeem_kopecks: int | None = Field(default=None, ge=1)
# wire: loyaltyRedeemKopecks (REDM-01 D-06);
# desired bonus debit (ge=1 rejects 0 or negative); server caps authoritatively
```

---

### WR-03: PWA estimate can display 0 ₽ "К оплате" when balance ≥ post-promo price; server enforces minimum 1 kopeck

**File:** `apps/client-pwa/src/screens/sheets/CheckoutSheet.jsx:378-379`

**Issue:**
```js
const bonusEstimateKopecks = bonusOn ? Math.min(balanceKopecks, total) : 0;
const estimatedTotal = total - bonusEstimateKopecks;
```

When `balanceKopecks >= total`, `estimatedTotal` becomes 0 and the pay button shows "Оплатить · ~0 ₽". The server clamps `clamped = min(requested, balance, post_promo_price - 1)` so the minimum actual charge is 1 kopeck (100 kopecks if we consider the `≥ 1` YooKassa requirement at the final floor in `_sell_subject_core`). The client will be surprised when the payment page shows a non-zero amount after being shown "0 ₽".

**Fix:**
Cap the client-side estimate to match the server's `price - 1` floor:
```js
const bonusEstimateKopecks = bonusOn
  ? Math.min(balanceKopecks, Math.max(0, total - 1))
  : 0;
```

---

## Info

### IN-01: `LoyaltyRedeemedPayload.amount_kopecks` lacks a negative-value constraint

**File:** `apps/backend/app/core/audit_payloads.py:1309`

**Issue:**
The docstring states "amount_kopecks is ALWAYS negative — it is the signed debit amount. Positive values are a bug." However, the Pydantic field is typed as plain `int` with no `lt=0` validator. The callsite in `loyalty/service.py:377` correctly passes `-actual_debit` (always negative since `actual_debit > 0` is asserted at line 314). The constraint should be declared in the schema to make the invariant machine-checkable.

**Fix:**
```python
from pydantic import Field

amount_kopecks: int = Field(lt=0)
# always negative — the debit; positive values are a bug (lt=0 enforces at audit.emit() time)
```

---

### IN-02: `# noqa: S608` on dynamic SQL table name in `handlers.py` warrants a comment

**File:** `apps/backend/app/api/v1/_internal/yookassa/handlers.py:513`

**Issue:**
```python
f"SELECT price_kopecks FROM {_plan_table} WHERE id = :id"  # noqa: S608
```

`_plan_table` is set exclusively to one of two hardcoded string literals (`"membership_plans"` or `"pt_package_plans"`) controlled by `subject_kind: Literal["membership", "pt_package"]` derived from DB state — no user input reaches this interpolation. The suppression is correct, but bare `# noqa: S608` without an inline explanation causes reader confusion about why a string-interpolated SQL fragment is safe here.

**Fix:**
Add a brief inline explanation so future reviewers do not wonder:
```python
f"SELECT price_kopecks FROM {_plan_table} WHERE id = :id"  # noqa: S608 — table name is a server-only Literal, not user-supplied
```

---

_Reviewed: 2026-06-05T12:00:00Z_
_Reviewer: Claude (gsd-code-reviewer)_
_Depth: deep_

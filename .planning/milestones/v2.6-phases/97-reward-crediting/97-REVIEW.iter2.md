---
phase: 97-reward-crediting
reviewed: 2026-06-08T00:00:00Z
depth: standard
files_reviewed: 9
files_reviewed_list:
  - apps/backend/app/api/v1/_internal/yookassa/handlers.py
  - apps/backend/app/modules/loyalty/service.py
  - apps/backend/app/modules/loyalty/models.py
  - apps/backend/alembic/versions/0069_referral_crediting_columns.py
  - apps/backend/alembic/env.py
  - apps/backend/app/core/audit.py
  - apps/backend/app/core/audit_payloads.py
  - apps/backend/tests/integration/test_referral_crediting.py
  - apps/backend/tests/unit/test_referral_bonus_accrual.py
findings:
  critical: 1
  warning: 3
  info: 2
  total: 6
status: issues_found
---

# Phase 97: Code Review Report

**Reviewed:** 2026-06-08
**Depth:** standard
**Files Reviewed:** 9
**Status:** issues_found

## Summary

Phase 97 adds referral bonus crediting inside the `payment.succeeded` webhook
UoW. The overall architecture is sound: the crediting block is inside the single
`async with session.begin()` UoW, atomicity is maintained, the ON CONFLICT arbiter
matches the partial UNIQUE index exactly, and the RETURNING gate prevents double
audit emission on replay. All existing patterns (caller-owns-txn, INFRA-15,
D-54-08 raw SQL, D-50-17 FSM discipline) are followed correctly.

One critical defect was found: the new partial UNIQUE index
`uq_loyalty_ledger_referral_accrual` is absent from `alembic/env.py`'s
`_include_object` exclusion list. All prior literal-named partial indexes in
the project are in that list — this omission will produce a spurious `alembic
check` drift on any CI run after migration 0069, and a developer following
normal maintenance procedures could generate a migration that drops the index.
Since the index is the authoritative DB-level guard against double referral
accrual, its accidental deletion would be a data-integrity regression.

Three warnings and two info items are noted below. The atomicity, idempotency,
and audit-emit correctness of the new crediting block are all verified.

## Critical Issues

### CR-01: `uq_loyalty_ledger_referral_accrual` not excluded from Alembic autogenerate

**File:** `apps/backend/alembic/env.py:82-116`
**Issue:** Migration 0069 creates the partial UNIQUE index
`uq_loyalty_ledger_referral_accrual` with a literal name (no `op.f()`), following
the project pattern established by `uq_loyalty_ledger_welcome` (0054),
`uq_loyalty_ledger_online_payment_id` (0055), and all other literal-named partial
indexes in the codebase. Every one of those indexes is listed in
`_include_object`'s exclusion name-set (lines 104-116 of env.py) to prevent
Alembic autogenerate from treating them as orphan-index drift.

The new `uq_loyalty_ledger_referral_accrual` is NOT in that list. Running
`alembic check` after 0069 will report a spurious diff (autogenerate sees an
unexpected index and proposes to drop it). A developer following CI guidance
("fix autogenerate drift") would generate and apply a migration that drops the
partial UNIQUE. The partial UNIQUE is the authoritative DB-level idempotency
guard for `accrue_referral_bonus` — without it, a concurrent-webhook race or
an application-level bug can produce duplicate referral accrual rows.

**Fix:**
```python
# In apps/backend/alembic/env.py, inside _include_object, add to the name set:

# Phase 97 REFER-04 / 0069: referral accrual partial UNIQUE index.
# Literal-named partial index (same lineage as uq_loyalty_ledger_welcome);
# autogenerate cannot reconcile literal vs. convention names.
"uq_loyalty_ledger_referral_accrual",
```
Place this entry in the existing exclusion set after the
`"uq_loyalty_ledger_online_payment_id"` entry (line 109) following the
chronological comment pattern used by neighboring entries.

---

## Warnings

### WR-01: First-purchase gate raw SQL uses snapshot isolation — TOCTOU window exists but DB-level partial UNIQUE is the authoritative guard

**File:** `apps/backend/app/api/v1/_internal/yookassa/handlers.py:637-655`
**Issue:** The first-purchase gate (lines 641-654) counts prior succeeded
membership payments using a raw SQL `COUNT(*)` query. Because `autoflush=True`
(the project's `async_sessionmaker` default), the current payment row is
flushed to the DB with `status='succeeded'` before this query executes — so
the `AND id != :current_id` exclusion is load-bearing and correct.

However, two concurrent `payment.succeeded` webhooks for two genuinely distinct
membership payments for the same referee client can both observe `cnt=0` (neither
has committed yet), both pass the gate, and both call `accrue_referral_bonus`.
In that scenario, the partial UNIQUE index `uq_loyalty_ledger_referral_accrual`
(column pair `referral_capture_id, client_id` WHERE `entry_type='referral_accrual'`)
prevents double insertion: one INSERT succeeds (RETURNING returns a UUID), the
other hits ON CONFLICT DO NOTHING (RETURNING returns NULL). The RETURNING gate
ensures only one `referral_bonus_accrued` audit row is emitted.

This is acceptable by design — the partial UNIQUE is the enforcement mechanism,
and the first-purchase gate is an application-level shortcut that can race
without breaking correctness. **The concern is documentation, not a code change.**
The comment block at lines 627-631 should mention that the partial UNIQUE is the
authoritative safety net, not just the first-purchase gate, so future maintainers
understand the two-layer defense.

**Fix:** Add a comment after line 631 in `handlers.py`:
```python
# Note: the first-purchase gate below is an application-level shortcut.
# The DB-level partial UNIQUE uq_loyalty_ledger_referral_accrual (on
# (referral_capture_id, client_id) WHERE entry_type='referral_accrual')
# is the authoritative guard against double accrual in concurrent-webhook
# scenarios. Both layers must remain in sync.
```

---

### WR-02: `record_loyalty_redemption` calls `session.flush()` inside the webhook UoW — inconsistent with `accrue_referral_bonus` contract and may expose partial state within a session

**File:** `apps/backend/app/modules/loyalty/service.py:455`
**Issue:** `record_loyalty_redemption` calls `await session.flush()` at line 455
(after the INSERT, before the audit emit). The function-level docstring and the
module docstring both state "No session.commit() — caller-owns-txn" but do NOT
mention the flush.

The unit tests for `accrue_referral_bonus` explicitly assert that the function
does NOT call `session.flush()` (test line 178). No such assertion exists for
`record_loyalty_redemption`. A flush inside a transaction is not semantically
equivalent to a commit — it syncs ORM state to the DB connection's open
transaction without committing — so correctness is preserved. However:

1. The module-level docstring says "flush only" (line 3: "No session.commit() —
   caller-owns-txn"). `record_loyalty_redemption` calling `flush()` inside the
   webhook UoW is architecturally consistent with being a "flush-only" primitive,
   but it is confusing because `accrue_referral_bonus` deliberately avoids flush
   and is tested for this.
2. The flush at line 455 is inside the webhook's `async with session.begin()` UoW.
   If an exception is raised anywhere after line 455 and before the
   `async with session.begin()` block exits, the entire transaction is rolled back
   (including the flushed-but-not-committed redemption row). This is correct
   behaviour, but the flush at line 455 makes the redemption row visible to other
   queries within the same session BEFORE the transaction commits. For example,
   a subsequent `_sum_balance` call later in the same UoW would include the just-
   flushed redemption debit. In this Phase 97 code, `accrue_referral_bonus` is
   called AFTER `record_loyalty_redemption`, so a `_sum_balance` call inside
   `accrue_referral_bonus` would see the debit. `accrue_referral_bonus` does NOT
   call `_sum_balance`, so there is no current functional impact. But the ordering
   dependency is silent and fragile.

This is a pre-existing Phase 83 condition, not introduced in Phase 97. Noting it
here because the Phase 97 code inserts `accrue_referral_bonus` calls AFTER
`record_loyalty_redemption` and the ordering assumption should be explicit.

**Fix:** Add a comment in `record_loyalty_redemption` at line 455, and document
the ordering contract in the webhook UoW comment block at handlers.py line 627:
```python
# In service.py, before the flush at line 455:
# flush so _sum_balance inside this same session sees the debit row;
# safe because we are inside the caller's transaction (no commit here).
await session.flush()
```
No code change required for correctness; the comment makes the ordering
dependency explicit.

---

### WR-03: Integration test Case 7 tests zero config amounts but NOT a truly absent config — the "config missing" branch (`_ref_config is None`) is untested

**File:** `apps/backend/tests/integration/test_referral_crediting.py:793-838`
**Issue:** The handler at `handlers.py:679` checks `if _ref_config is not None`
before calling `accrue_referral_bonus`. Case 7 (lines 793-838) seeds a config
row with `referrer_bonus_kopecks=0` and `referee_welcome_kopecks=0` and tests
that 0 accrual rows are produced. This proves the `> 0` guard at lines 681/689
but NOT the `_ref_config is not None` guard.

The test module teardown restores the config singleton to the seed values, so
there is never a state where `referral_config` has zero rows in these tests. If
the `get_config()` query returns `None` (config row deleted or the seed migration
has not run), the handler silently skips both `accrue_referral_bonus` calls —
but the unit tests do not cover this path.

In production there is always exactly one config row (seeded by migration 0068),
so the risk is low. However, the distinction between "config missing" (returns
`None`) and "config present with zero amounts" (returns non-None config) is
meaningful and should be tested.

**Fix:** Add a Case 7b to the integration test that removes the config row and
confirms 0 accrual rows:
```python
async def test_ref_cred_07b_config_absent_no_accrual(
    _credit_session, _webhook_client
) -> None:
    # ... seed clients, plan, code, capture, payment ...
    # Delete the config singleton (simulate missing seed)
    await _credit_session.execute(text("DELETE FROM referral_config"))
    await _credit_session.commit()
    # Deliver webhook → expect 0 accrual rows
    ...
```
The fixture teardown already restores the config singleton, so this case is
safe to add alongside the existing seven.

---

## Info

### IN-01: `alembic/env.py` import for Phase 97 models is not needed — `referrals.models` is already imported for Phase 96

**File:** `apps/backend/alembic/env.py:49`
**Issue:** The `app.modules.referrals.models` import was added in Phase 96 as
an `env.py` gap fix (comment: "REFER-01..07 / 0067+0068 — env.py gap (FK target)").
Migration 0069 adds a FK column to `loyalty_ledger` that points to
`referral_captures.id`. The `referral_captures` table is defined in
`app.modules.referrals.models`, which is already imported. No new import was
needed and none was added — this is correct. Noting this explicitly because the
migration docstring mentions FK naming without clarifying that env.py requires
no change.

No fix required.

---

### IN-02: `ReferralBonusAccruedPayload.amount_kopecks` has no positivity constraint — docstring says "always positive" but no `Field(gt=0)` enforcer

**File:** `apps/backend/app/core/audit_payloads.py:1403`
**Issue:** The `ReferralBonusAccruedPayload` docstring at line 1403 states
`amount_kopecks: int  # always positive (accrual)` and the `LoyaltyRedeemedPayload`
at line 1309 has `amount_kopecks: int = Field(lt=0)` (enforcing it is always
negative). By analogy, `ReferralBonusAccruedPayload.amount_kopecks` should carry
`Field(gt=0)` to enforce the documented invariant at schema-validation time.

Currently, a miscalculation that produces a zero or negative amount would pass
`model_validate` and land silently in the audit_log JSONB without raising. The
callsite in `handlers.py` already guards with `if _ref_config.referrer_bonus_kopecks > 0`
(line 681) and `if _ref_config.referee_welcome_kopecks > 0` (line 689), so the
risk of a zero reaching the audit emit is low. But the missing schema constraint
is an inconsistency with `LoyaltyRedeemedPayload`'s pattern.

**Fix:**
```python
# In audit_payloads.py, ReferralBonusAccruedPayload:
amount_kopecks: int = Field(gt=0)  # always positive — referral accrual
```

---

_Reviewed: 2026-06-08_
_Reviewer: Claude (gsd-code-reviewer)_
_Depth: standard_

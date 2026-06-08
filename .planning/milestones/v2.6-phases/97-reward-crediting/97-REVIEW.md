---
phase: 97-reward-crediting
reviewed: 2026-06-08T00:00:00Z
depth: standard
files_reviewed: 8
files_reviewed_list:
  - apps/backend/app/api/v1/_internal/yookassa/handlers.py
  - apps/backend/app/modules/loyalty/service.py
  - apps/backend/app/modules/loyalty/models.py
  - apps/backend/alembic/versions/0069_referral_crediting_columns.py
  - apps/backend/alembic/env.py
  - apps/backend/app/core/audit.py
  - apps/backend/app/core/audit_payloads.py
  - apps/backend/tests/integration/test_referral_crediting.py
findings:
  critical: 0
  warning: 0
  info: 1
  total: 1
status: clean
---

# Phase 97: Code Review Report (iteration 2 — post-fix re-review)

**Reviewed:** 2026-06-08
**Depth:** standard
**Files Reviewed:** 8
**Status:** clean

## Summary

Re-review after the auto-fix loop applied all five fixes from iteration 1
(CR-01 + WR-01 + WR-02 + WR-03 + IN-02). All five fixes are correctly implemented
and verified below. No Critical or Warning issues remain.

One new Info finding is introduced by the env.py additions: the exclusion set
includes `"ix_referral_codes_client_id"` (env.py line 122), but this index name
does not exist in the DB schema — migration 0067 only creates
`"uq_referral_codes_client_id"`. The orphaned exclusion entry is harmless
(Alembic will never encounter the phantom name) but is a documentation
inconsistency that tracks back to an incorrect comment in `referrals/models.py`.

---

## Fix Verification

### CR-01 — env.py exclusion additions

**Verified correct.** `env.py` lines 110–134 add:

- `"uq_loyalty_ledger_referral_accrual"` (line 113) — the new Phase 97 partial UNIQUE.
  Follows the same literal-named-partial-index exclusion pattern as
  `uq_loyalty_ledger_welcome` / `uq_loyalty_ledger_online_payment_id`.
- `"uq_referral_codes_code"` (line 119), `"uq_referral_codes_client_id"` (line 121),
  `"ix_referral_codes_client_id"` (line 122), `"uq_referral_captures_referee_client_id"`
  (line 123) — Phase 96 referral indexes.
- `"ix_messages_thread_sent"` (line 128) — Phase 90 DESC-expression index.
  Justified: migration 0065 creates it with `sent_at DESC`; ORM model declares it
  without DESC — same column-vs-expression mismatch as `ix_email_send_log_to_addr_recorded`.

No over-exclusion: every excluded name corresponds to a real DB object whose ORM
counterpart differs in naming convention or index expression. `alembic check` is
green per the fix description.

### WR-01 — partial UNIQUE documented as authoritative guard (handlers.py comment)

**Verified correct.** `handlers.py` lines 632–636 now contain an explicit comment
stating that `uq_loyalty_ledger_referral_accrual` is the authoritative DB-level
guard and the `_is_first_membership` application-level check is a fast-path
shortcut. The comment reads: "Both layers must remain in sync."

### WR-02 — flush/ordering contract comment (service.py)

**Verified correct.** `service.py` lines 455–460 now contain a comment explaining:
(1) why `flush()` is called here (so `_sum_balance` within the same session sees
the debit row); (2) that `accrue_referral_bonus` is called AFTER
`record_loyalty_redemption` and does NOT read `_sum_balance`, so there is no
current functional dependency on this flush — but it is architecturally
load-bearing if ordering changes.

### WR-03 — test_ref_cred_07b (config absent branch)

**Verified correct.** Test `test_ref_cred_07b_config_absent_no_accrual` at lines
847–906 of the test file covers the `_ref_config is None` code path in
`handlers.py:684`. The test:

1. Calls `_ensure_referral_config` (idempotent baseline, ensures the row exists).
2. Seeds clients, capture, and a membership payment.
3. Issues `DELETE FROM referral_config` and commits — forces `get_config()` to
   return `None` when the webhook fires.
4. Delivers the webhook; asserts HTTP 200 and 0 accrual rows.
5. Re-inserts the singleton at seed defaults (50000/30000) and commits — ensures
   the `_credit_engine` teardown's `UPDATE … WHERE id = :id` finds the row and
   does not silently no-op.

The `_credit_session.rollback()` at line 893 only discards uncommitted session
state; the committed delete is not reversed by it. The re-insert at lines 901–906
is in the test body (before teardown), which is correct ordering.

### IN-02 — Field(gt=0) on ReferralBonusAccruedPayload.amount_kopecks

**Verified correct.** `audit_payloads.py` line 1403:
```python
amount_kopecks: int = Field(gt=0)  # always positive — referral accrual (enforced)
```
All call paths to `accrue_referral_bonus` are already guarded by
`if _ref_config.referrer_bonus_kopecks > 0:` (handlers.py line 685) and
`if _ref_config.referee_welcome_kopecks > 0:` (line 694), so no zero value can
reach `audit.emit`. The `Field(gt=0)` constraint is therefore consistent with
`LoyaltyRedeemedPayload`'s `Field(lt=0)` pattern and adds defence-in-depth
without breaking any existing callsite.

---

## Info

### IN-01: Orphaned `"ix_referral_codes_client_id"` entry in env.py exclusion set

**File:** `apps/backend/alembic/env.py:122`

**Issue:** The exclusion set added by the CR-01 fix includes
`"ix_referral_codes_client_id"`. This index name does not exist in the DB schema.
Migration 0067 creates only `"uq_referral_codes_client_id"` (a UNIQUE index on
`referral_codes.client_id`). There is no separate plain index with the `ix_`
prefix on that column.

The root cause is an incorrect comment in `referrals/models.py` line 75:

> "Plain index `ix_referral_codes_client_id` also declared in migration 0067."

This claim is false — the migration DDL only creates `uq_referral_codes_client_id`.

**Impact:** None at runtime. Alembic autogenerate will never encounter a DB object
named `ix_referral_codes_client_id`, so the exclusion entry never fires. The real
UNIQUE index (`uq_referral_codes_client_id`) is correctly excluded on line 121.
`alembic check` output is unaffected.

**Fix:** Remove the phantom entry from env.py and correct the model comment:

```python
# apps/backend/alembic/env.py — remove line 122:
#   "ix_referral_codes_client_id",

# apps/backend/app/modules/referrals/models.py line 75 — correct comment:
# Plain UNIQUE index uq_referral_codes_code declared in migration 0067 (op.f()).
# UNIQUE index uq_referral_codes_client_id also declared in migration 0067 (literal name).
```

---

_Reviewed: 2026-06-08_
_Reviewer: Claude (gsd-code-reviewer)_
_Depth: standard_

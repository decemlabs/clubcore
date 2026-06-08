---
phase: 97-reward-crediting
fixed_at: 2026-06-08T00:00:00Z
review_path: .planning/phases/97-reward-crediting/97-REVIEW.md
iteration: 1
findings_in_scope: 4
fixed: 4
skipped: 0
status: all_fixed
---

# Phase 97: Code Review Fix Report

**Fixed at:** 2026-06-08
**Source review:** .planning/phases/97-reward-crediting/97-REVIEW.md
**Iteration:** 1

**Summary:**
- Findings in scope (critical + warning): 4 (CR-01, WR-01, WR-02, WR-03)
- Fixed: 4
- Skipped: 0
- Bonus fix: IN-02 also applied (trivial schema improvement, consistent with reviewer guidance)

## Fixed Issues

### CR-01: `uq_loyalty_ledger_referral_accrual` not excluded from Alembic autogenerate

**Files modified:** `apps/backend/alembic/env.py`
**Commit:** d5e0a4ff
**Applied fix:** Added `"uq_loyalty_ledger_referral_accrual"` to the `_include_object` exclusion
name-set after the `uq_loyalty_ledger_online_payment_id` entry, with the standard Phase 97 REFER-04
chronological comment. `alembic check` confirmed: the index no longer appears in drift output after
the fix (only pre-existing Phase 96 drift remains, which is unrelated to Phase 97).

---

### WR-01: First-purchase gate TOCTOU window — partial UNIQUE is the authoritative guard

**Files modified:** `apps/backend/app/api/v1/_internal/yookassa/handlers.py`
**Commit:** 11176185
**Applied fix:** Added a 5-line comment block immediately after the D-54-08 note in the Phase 97
REFER-04 block (before `if subject_kind == SUBJECT_KIND_MEMBERSHIP:`), clarifying that the
first-purchase COUNT gate is an application-level fast-path shortcut and the DB-level partial UNIQUE
`uq_loyalty_ledger_referral_accrual` is the authoritative ON CONFLICT DO NOTHING enforcer.

---

### WR-02: `record_loyalty_redemption` flush ordering assumption undocumented

**Files modified:** `apps/backend/app/modules/loyalty/service.py`
**Commit:** 7f898910
**Applied fix:** Added a 6-line comment block before `await session.flush()` at line 455 in
`record_loyalty_redemption`, documenting: (1) why the flush exists (makes the debit row visible
to `_sum_balance` in the same session), (2) that it is safe (inside caller's transaction), and
(3) the ordering dependency with `accrue_referral_bonus` (called after, does not read `_sum_balance`,
so currently safe but fragile if ordering changes).

---

### WR-03: Integration test missing `_ref_config is None` branch coverage

**Files modified:** `apps/backend/tests/integration/test_referral_crediting.py`
**Commit:** 3d9992f6
**Applied fix:** Added `test_ref_cred_07b_config_absent_no_accrual` as Case 7b after the existing
Case 7. The test seeds clients, plan, code, capture, and payment; deletes the referral_config
singleton (forcing `get_config` to return None); delivers the webhook; asserts HTTP 200 and
0 accrual rows. Teardown: re-inserts the singleton at seed defaults (50000/30000) using the
existing `_ensure_referral_config` helper, so the engine fixture's UPDATE-based restore works
correctly. Test run confirmed: 100 passed (up from 99), referral_config remains at 50000/30000
after the full suite.

---

### IN-02: `ReferralBonusAccruedPayload.amount_kopecks` missing `Field(gt=0)` (bonus fix)

**Files modified:** `apps/backend/app/core/audit_payloads.py`
**Commit:** 3f0583f7
**Applied fix:** Changed `amount_kopecks: int  # always positive (accrual)` to
`amount_kopecks: int = Field(gt=0)  # always positive — referral accrual (enforced)`.
`Field` was already imported. This makes `ReferralBonusAccruedPayload` consistent with
`LoyaltyRedeemedPayload.amount_kopecks = Field(lt=0)` and enforces the documented invariant
at schema-validation time.

**Decision rationale:** Applied despite being Info-tier because it is a one-line change with
no risk, the reviewer explicitly called it trivial and consistent with the existing pattern,
and the guidance said "optionally add... since it's trivial and improves the schema".

---

## Verification Results

- `uv run mypy --strict app/api/v1/_internal/yookassa/handlers.py app/modules/loyalty/ app/core/`: **Success: no issues found in 31 source files**
- `uv run ruff check` (all changed files): **All checks passed**
- `uv run lint-imports`: **Contracts: 3 kept, 0 broken**
- Full test suite (100 tests): **100 passed in 17.27s**
- `uv run alembic check`: `uq_loyalty_ledger_referral_accrual` **no longer appears in drift output** (CR-01 resolved)
- referral_config after test run: **50000/30000 (seed defaults — no pollution)**

---

_Fixed: 2026-06-08_
_Fixer: Claude (gsd-code-fixer)_
_Iteration: 1_

---
phase: 97-reward-crediting
verified: 2026-06-08T12:00:00Z
status: passed
score: 4/4
overrides_applied: 0
re_verification: false
---

# Phase 97: Reward Crediting — Verification Report

**Phase Goal:** Обе стороны автоматически получают бонус на `loyalty_ledger` после первой покупки абонемента приглашённым другом
**Verified:** 2026-06-08
**Status:** PASSED
**Re-verification:** No — initial verification

---

## Goal Achievement

### Observable Truths

| # | Truth | Status | Evidence |
|---|-------|--------|----------|
| 1 | On `payment.succeeded` for a referee's first membership purchase, a `loyalty_ledger` row is inserted for the referrer AND the referee within the same atomic UoW | VERIFIED | `handlers.py` lines 627–697 inside `async with session.begin():` (opened line 391, closed ~line 783). Two `accrue_referral_bonus` calls co-transactional; Case 1 integration test asserts `count == 2` (never 1). |
| 2 | Webhook replay (same `online_payment_id`) inserts nothing and emits no second audit event | VERIFIED | Partial UNIQUE index `uq_loyalty_ledger_referral_accrual` on `(referral_capture_id, client_id) WHERE entry_type='referral_accrual'` in migration 0069. `accrue_referral_bonus` uses `on_conflict_do_nothing` + RETURNING-gated `audit.emit`. Case 2 integration test asserts totals stay at 2+2 after replay. |
| 3 | A second membership purchase by the same referee does NOT trigger another referral bonus | VERIFIED | First-purchase gate (raw SQL COUNT prior succeeded membership payments, `id != :current_id`) in `handlers.py` lines 639–655. Case 3 integration test asserts `after_second == 2` (no new rows). |
| 4 | Bonus amounts come exclusively from owner-configurable `referral_config`; no hardcoded amounts at the crediting callsite | VERIFIED | Lines 684 and 693 in `handlers.py` use `_ref_config.referrer_bonus_kopecks` and `_ref_config.referee_welcome_kopecks`. `grep -nE "amount_kopecks\s*=\s*[0-9]"` returns zero matches in the crediting block. Case 1 asserts amounts equal seeded config values (not literals). |

**Score:** 4/4 truths verified

---

### Additional Invariants Verified

The PLAN and prompt specified these additional invariants beyond the four ROADMAP Success Criteria. All confirmed:

| Invariant | Evidence |
|-----------|----------|
| Referrer soft-deleted → entire accrual voided (neither side credited) | `handlers.py` lines 659–674: raw SQL `deleted_at IS NULL` check; if None logs `referral_bonus_voided_referrer_deleted` and skips both calls. Case 5 asserts `count == 0`. |
| First-purchase gate (zero prior succeeded membership payments) | Raw SQL COUNT at lines 639–655; `_is_first_membership = int(_prior_row["cnt"]) == 0`. |
| INFRA-15: `referral_bonus_accrued` registered before callsite | `audit.py` line 485: `("referral_bonus_accrued", "referral")` in `LOCKED_AUDIT_EVENTS` frozenset, appended in Plan 97-01 before any callsite existed in Plan 97-03. |
| Membership-only: PT-package payments excluded | `handlers.py` line 632: `if subject_kind == SUBJECT_KIND_MEMBERSHIP:` guard. Case 6 (PT-package) asserts `count == 0`. |
| Server-authoritative: `accrue_referral_bonus` only called from webhook handler | Verified by grep: only callsites are `handlers.py` lines 681 and 690. No client-facing endpoint imports or calls this function. |
| Atomicity: both rows or neither | Both `accrue_referral_bonus` calls share the single `async with session.begin():` UoW (flush-only primitive, no inner commit). UoW commits once when the `async with` block exits. Case 1 asserts `count == 2`, never 1. |

---

### Required Artifacts

| Artifact | Expected | Status | Details |
|----------|----------|--------|---------|
| `apps/backend/app/core/audit.py` | `referral_bonus_accrued` in `LOCKED_AUDIT_EVENTS` | VERIFIED | Line 485: `("referral_bonus_accrued", "referral")` present in v2.6 block. |
| `apps/backend/app/core/audit_payloads.py` | `ReferralBonusAccruedPayload` class + registry entry | VERIFIED | Class at line 1388 with `extra='forbid'`, six fields, `Literal["referrer","referee"]` role. Registry entry at line 1518. |
| `apps/backend/alembic/versions/0069_referral_crediting_columns.py` | FK column + partial UNIQUE index + widened CHECK | VERIFIED | `uq_loyalty_ledger_referral_accrual` literal name; FK `fk_loyalty_ledger_referral_capture_id_referral_captures`; CHECK widened to include `'referral_accrual'`. `down_revision = "0068_seed_referral_config"`. |
| `apps/backend/app/modules/loyalty/models.py` | `referral_capture_id` column + widened `entry_type` CHECK | VERIFIED | `referral_capture_id` nullable FK at lines 110–118; CHECK at line 127 includes all four literals. No ORM Index for partial UNIQUE (migration-only, correct per plan). |
| `apps/backend/app/modules/loyalty/service.py` | `accrue_referral_bonus` primitive | VERIFIED | Line 140: signature matches plan exactly (`session, *, client_id, amount_kopecks, referral_capture_id, online_payment_id, role`). Flush-only (no `session.flush()` or `session.commit()` inside function). RETURNING-gated `audit.emit`. |
| `apps/backend/app/api/v1/_internal/yookassa/handlers.py` | Referral crediting orchestration in `handle_payment_succeeded` | VERIFIED | Lines 627–697: 6-step orchestration block inside `async with session.begin():`, after `record_loyalty_redemption`, before INBOX-03. |
| `apps/backend/tests/integration/test_referral_crediting.py` | 7-case integration suite | VERIFIED | 7 test functions covering all required cases: happy-path, replay, second-purchase, no-capture, referrer-deleted, PT-package, config-zero. |
| `apps/backend/tests/unit/test_audit_payloads.py` | Audit payload unit tests for `referral_bonus_accrued` | VERIFIED | 7 assertions: registration, two valid roles, three negative cases (extra field, bad role, missing field). |

---

### Key Link Verification

| From | To | Via | Status | Details |
|------|-----|-----|--------|---------|
| `handlers.py` | `referrals.repository.get_capture_by_referee` / `get_config` | `from app.modules.referrals import repository as referrals_repo` | VERIFIED | Lines 132 (import), 633 and 678 (callsites). D-54-08 respected: cross-module via repository, not service. |
| `handlers.py` | `loyalty.service.accrue_referral_bonus` | `from app.modules.loyalty.service import accrue_referral_bonus, ...` | VERIFIED | Line 111 (import), lines 681 and 690 (two co-transactional callsites per webhook). |
| `loyalty/service.py` | `uq_loyalty_ledger_referral_accrual` partial UNIQUE | `on_conflict_do_nothing(index_elements=["referral_capture_id","client_id"], index_where=text("entry_type = 'referral_accrual'"))` | VERIFIED | Lines 174–182 of `service.py`. Literal text predicate matches migration's `postgresql_where` clause exactly. |
| `loyalty/service.py` | `audit.emit(referral_bonus_accrued)` | RETURNING-gated: only when `inserted_id is not None` | VERIFIED | Lines 189–213: conflict path returns None, real-insert path calls `audit.emit`. |

---

### Data-Flow Trace (Level 4)

| Artifact | Data Variable | Source | Produces Real Data | Status |
|----------|---------------|--------|-------------------|--------|
| `handlers.py` crediting block | `_ref_config.referrer_bonus_kopecks`, `_ref_config.referee_welcome_kopecks` | `referrals_repo.get_config(session)` → `referral_config` table (seeded by migration 0068) | Yes — row seeded by migration; Case 1 test sets known values and asserts amounts match | FLOWING |
| `handlers.py` crediting block | `_capture.referrer_client_id`, `_capture.id` | `referrals_repo.get_capture_by_referee(session, row.client_id)` → `referral_captures` table | Yes — live referral_captures row required for code path to proceed | FLOWING |
| `loyalty/service.py` `accrue_referral_bonus` | `inserted_id` | `pg_insert(LoyaltyLedger).returning(LoyaltyLedger.id)` → real INSERT with RETURNING | Yes — real DB insert; conflict returns None; no static fallback | FLOWING |

---

### Behavioral Spot-Checks

All behavioral checks executed against the live DB (Docker up):

| Behavior | Command / Verification | Result | Status |
|----------|------------------------|--------|--------|
| 7-case integration suite passes | `uv run pytest tests/integration/test_referral_crediting.py -q` | `7 passed in 3.14s` | PASS |
| Audit payload unit tests pass | `uv run pytest tests/unit/test_audit_payloads.py -k "referral_bonus_accrued or ReferralBonusAccrued" -q` | `7 passed` | PASS |
| mypy --strict on all changed files | `uv run mypy --strict app/core/audit.py app/core/audit_payloads.py app/modules/loyalty/service.py app/api/v1/_internal/yookassa/handlers.py` | `Success: no issues found in 4 source files` | PASS |
| ruff on all changed files | `uv run ruff check app/core/audit.py app/core/audit_payloads.py app/modules/loyalty/service.py app/api/v1/_internal/yookassa/handlers.py alembic/versions/0069_referral_crediting_columns.py tests/unit/test_audit_payloads.py tests/integration/test_referral_crediting.py` | `All checks passed!` | PASS |
| import-linter contracts | `uv run lint-imports` | `Contracts: 3 kept, 0 broken` (referrals ↔ loyalty remain import-independent; handler is composition layer) | PASS |
| No hardcoded bonus amounts in crediting block | `grep -nE "amount_kopecks\s*=\s*[0-9]" handlers.py` (in crediting block) | Lines 684/693 use `_ref_config.referrer_bonus_kopecks` / `_ref_config.referee_welcome_kopecks` — zero literal-digit matches in crediting block | PASS |

---

### Probe Execution

No probe scripts declared for this phase. Step 7c: SKIPPED (no probe-*.sh files for phase 97).

---

### Requirements Coverage

| Requirement | Source Plan | Description | Status | Evidence |
|-------------|-------------|-------------|--------|----------|
| REFER-04 | 97-01, 97-02, 97-03 | На `payment.succeeded` ПЕРВОЙ покупки абонемента обе стороны получают бонус на `loyalty_ledger`, идемпотентно, LOCKED audit-события зарегистрированы до callsite | SATISFIED | All four ROADMAP SCs verified. INFRA-15 pre-registration confirmed. Idempotency proven by integration test Case 2. Note: REQUIREMENTS.md mentions "reusing accrual/`owner_grant` primitives" — implementation created `accrue_referral_bonus` (a new dedicated primitive mirroring `accrue_welcome_bonus`). This is a design refinement confirmed in PLAN 97-02 frontmatter; the intent (reuse of the flush-only + RETURNING-gated pattern) is fully satisfied. |

**REQUIREMENTS.md status note:** REFER-04 is still marked `- [ ]` (Pending) and the requirements table shows `Pending`. This is a REQUIREMENTS.md tracking artifact — the implementation is complete and all success criteria pass. The ROADMAP.md already marks Phase 97 as `completed 2026-06-08`. The REQUIREMENTS.md checkbox and table are informational tracking; updating them is outside scope of the phase and does not affect verification outcome.

---

### Anti-Patterns Found

None found. Scanned `audit.py`, `audit_payloads.py`, `loyalty/models.py`, `loyalty/service.py`, `handlers.py`, `0069_referral_crediting_columns.py`, `test_referral_crediting.py`:

- No `TBD`, `FIXME`, or `XXX` markers
- No stub returns (`return null`, `return {}`, `return []`)
- No hardcoded bonus amounts in the crediting block
- No `session.flush()` or `session.commit()` inside `accrue_referral_bonus`
- No client-facing endpoint touches `accrue_referral_bonus`

---

### Human Verification Required

None. All invariants are programmatically verifiable via integration tests on the real-commit engine. No UI, real-time behavior, or external service behavior requires human testing in this phase.

---

## Gaps Summary

No gaps. All four ROADMAP Success Criteria are VERIFIED. All additional invariants from the PLAN frontmatter and the prompt (server-authoritative, atomicity, referrer-alive void, first-purchase gate, INFRA-15, membership-only, no hardcoded amounts) are confirmed in code and proven by a passing integration suite.

---

**Note on ROADMAP SC 2 wording vs. implementation:** The ROADMAP says "idempotent by `(referral_id, online_payment_id)` partial UNIQUE guard". The actual partial UNIQUE is `(referral_capture_id, client_id) WHERE entry_type='referral_accrual'`. This design was intentionally chosen in PLAN 97-02 to allow one accrual per side per capture (referrer row + referee row share the same `referral_capture_id` but differ on `client_id`). The idempotency intent is fully satisfied: replay of the same webhook (same `referral_capture_id` + same `client_id`) conflicts on the partial UNIQUE → `on_conflict_do_nothing` → no second insert. Case 2 proves this end-to-end. No override needed — the behavior matches the ROADMAP SC observable outcome exactly.

---

_Verified: 2026-06-08T12:00:00Z_
_Verifier: Claude (gsd-verifier)_

---
phase: 83-bonus-redemption-at-checkout
plan: "01"
subsystem: backend
tags: [loyalty, audit, migration, orm, schema]
dependency_graph:
  requires: [82-loyalty-foundation]
  provides: [loyalty_ledger.online_payment_id, online_payments.loyalty_redeem_kopecks, loyalty_redeemed-audit-event]
  affects: [loyalty/models.py, online_payments/models.py, audit.py, audit_payloads.py]
tech_stack:
  added: []
  patterns: [literal-named-partial-unique-index, INFRA-15-pre-register-before-callsite, TDD-red-green]
key_files:
  created:
    - apps/backend/alembic/versions/0055_loyalty_redemption_columns.py
  modified:
    - apps/backend/app/modules/loyalty/models.py
    - apps/backend/app/modules/online_payments/models.py
    - apps/backend/alembic/env.py
    - apps/backend/app/core/audit.py
    - apps/backend/app/core/audit_payloads.py
    - apps/backend/tests/unit/test_audit_taxonomy.py
    - apps/backend/tests/integration/test_phase51_audit_chain_invariants.py
    - apps/backend/tests/unit/test_loyalty_audit_events.py
decisions:
  - "Partial UNIQUE index uq_loyalty_ledger_online_payment_id uses literal name (not op.f()) — matches uq_loyalty_ledger_welcome (0054) and uq_promo_redemptions_online_payment_id precedents"
  - "loyalty_redeem_kopecks is BigInteger (signed) with no server_default, no CHECK — matches plan spec; Plan 02 will set it at checkout time"
  - "LoyaltyRedeemedPayload amount_kopecks typed as int (always negative by convention, documented); no Literal constraint avoids model-layer sign enforcement at the schema-definition level"
metrics:
  duration: "~20 minutes"
  completed: "2026-06-05"
  tasks_completed: 2
  files_changed: 8
requirements: [REDM-01, REDM-02]
---

# Phase 83 Plan 01: Schema + Audit Taxonomy Contracts Summary

Schema foundation and audit event pre-registration for bonus redemption at checkout: migration 0055 adding loyalty_ledger.online_payment_id FK + partial UNIQUE (double-spend guard) + online_payments.loyalty_redeem_kopecks, ORM mappings, env.py allowlist, and loyalty_redeemed LOCKED audit event registered before its callsite (INFRA-15).

## Tasks Completed

| Task | Name | Commit | Files |
|------|------|--------|-------|
| 1 | Migration 0055 + ORM columns + env.py allowlist | 506f713a | 0055_loyalty_redemption_columns.py, loyalty/models.py, online_payments/models.py, alembic/env.py |
| 2 (RED) | Failing tests for loyalty_redeemed + count-lock bumps | 4d3289b9 | test_loyalty_audit_events.py, test_audit_taxonomy.py, test_phase51_audit_chain_invariants.py |
| 2 (GREEN) | Register loyalty_redeemed event + LoyaltyRedeemedPayload | aa0eb39f | audit.py, audit_payloads.py |

## Commits

- `506f713a` feat(83-01): migration 0055 + ORM columns + env.py allowlist for redemption
- `4d3289b9` test(83-01): add failing tests for loyalty_redeemed audit event + bump count-locks 102→103
- `aa0eb39f` feat(83-01): register loyalty_redeemed LOCKED audit event + LoyaltyRedeemedPayload

## What Was Built

### Migration 0055

`alembic/versions/0055_loyalty_redemption_columns.py` adds three schema changes on top of 0054:

1. `loyalty_ledger.online_payment_id` — nullable UUID FK to `online_payments.id` with `ondelete=RESTRICT`. Named `fk_loyalty_ledger_online_payment_id_online_payments`.
2. Partial UNIQUE index `uq_loyalty_ledger_online_payment_id` on `loyalty_ledger(online_payment_id) WHERE entry_type = 'redemption'`. Literal name (not `op.f()`) per 0034/0037/0046/0054 precedent. This is the DB-level double-spend guard (T-83-01) that Plan 02's `on_conflict_do_nothing` targets.
3. `online_payments.loyalty_redeem_kopecks` — nullable `BigInteger`, server-computed at checkout, never client-writable (T-83-03).

Downgrade reverses in inverse order. `alembic upgrade head` + `alembic check` clean. `test_alembic_clean` 2/2 green.

### ORM Mappings

- `LoyaltyLedger.online_payment_id`: `Mapped[UUIDType | None]` with `ForeignKey("online_payments.id", ondelete="RESTRICT")`. Comment documents the partial UNIQUE is in migration 0055 (not as ORM Index), following the uq_loyalty_ledger_welcome pattern.
- `OnlinePayment.loyalty_redeem_kopecks`: `Mapped[int | None]` via `mapped_column(BigInteger, nullable=True)`. Added `BigInteger` to the SQLAlchemy import.

### env.py Allowlist

Added `"uq_loyalty_ledger_online_payment_id"` to the `_include_object` skip list with a Phase 83 comment. This prevents `alembic check` / `test_alembic_clean` from detecting the literal-named partial index as drift.

### Audit Event Registration (INFRA-15)

- `audit.py`: `("loyalty_redeemed", "loyalty")` added to `LOCKED_AUDIT_EVENTS` immediately after `("loyalty_accrued", "loyalty")`, with a comment that it is registered BEFORE the webhook callsite (Plan 02).
- `audit_payloads.py`: `LoyaltyRedeemedPayload(BaseModel)` with `extra="forbid"`, fields `client_id: UUID`, `entry_id: UUID`, `amount_kopecks: int` (always negative — the debit), `online_payment_id: UUID`. Registered in `AUDIT_PAYLOAD_SCHEMAS`.
- Count-lock guards bumped 102 → 103 in both `test_audit_taxonomy.py` and `test_phase51_audit_chain_invariants.py`.

## Verification Results

- `alembic upgrade head`: applied 0055 cleanly
- `alembic check`: "No new upgrade operations detected"
- `test_alembic_clean`: 2/2 passed
- Target audit tests (36 total): 36/36 passed
- `mypy --strict app`: "Success: no issues found in 235 source files"
- `ruff check` + `ruff format --check`: all clean on all modified files

## Deviations from Plan

None — plan executed exactly as written.

## Known Stubs

None.

## Threat Flags

No new security-relevant surface beyond what the plan's threat_model documents.

## TDD Gate Compliance

Task 2 followed the RED/GREEN/REFACTOR cycle:
- RED commit `4d3289b9`: failing tests (ImportError + count-lock mismatch)
- GREEN commit `aa0eb39f`: implementation makes all 36 tests pass
- No REFACTOR needed (code is minimal and clean)

## Self-Check: PASSED

- `apps/backend/alembic/versions/0055_loyalty_redemption_columns.py`: FOUND
- `apps/backend/app/core/audit_payloads.py` (LoyaltyRedeemedPayload): FOUND
- Commit `506f713a`: FOUND
- Commit `4d3289b9`: FOUND
- Commit `aa0eb39f`: FOUND
- `LOCKED_AUDIT_EVENTS` count: 103 (verified by 36/36 tests)

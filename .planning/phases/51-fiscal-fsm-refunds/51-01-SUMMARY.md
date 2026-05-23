---
phase: 51
plan: 51-01
subsystem: online_refunds (schema/DDL)
tags: [alembic, migration, schema, online-refunds, refund-03]
requires: [phase-50-0036-payments-received-by-user-id-nullable]
provides:
  - online_refunds-table
  - uq_online_refunds_alive_per_online_payment (partial UNIQUE — REFUND-03 schema layer)
  - uq_online_refunds_yookassa_refund_id
  - uq_online_refunds_idempotency_key
  - ck_online_refunds_amount_kopecks_positive
  - ck_online_refunds_status
affects:
  - apps/backend/alembic/versions/ (new revision head 0037)
tech_stack:
  added: []
  patterns:
    - "Phase 49 partial-UNIQUE-via-op.create_index (literal index name, NOT op.f())"
    - "Phase 49/50 op.f() wrapper on PK/FK/CHECK/UNIQUE in create_table"
key_files:
  created:
    - apps/backend/alembic/versions/0037_online_refunds.py
  modified: []
decisions:
  - "Honored PATTERNS.md erratum to CONTEXT D-51-06: down_revision = '0036_payments_received_by_user_id_nullable' (NOT '0035_fiscal_receipts')"
  - "Partial UNIQUE index name uses literal 'uq_online_refunds_alive_per_online_payment' (PATTERNS canonical name), not the CONTEXT-skeleton draft name 'uq_online_refunds_online_payment_id_alive'"
metrics:
  duration_minutes: ~10
  tasks_completed: 1
  files_changed: 1
  completed: 2026-05-23
---

# Phase 51 Plan 51-01: Online Refunds Migration (0037) Summary

Shipped Alembic migration `0037_online_refunds` creating the `online_refunds` request-tracking table with 4 ON DELETE RESTRICT FKs, 2 CHECKs, 2 full UNIQUEs, and 1 partial UNIQUE that backs REFUND-03 at the schema layer.

## What Was Built

**File:** `apps/backend/alembic/versions/0037_online_refunds.py` (145 lines)

- **Revision:** `0037_online_refunds`
- **Down revision:** `0036_payments_received_by_user_id_nullable` (PATTERNS.md erratum to CONTEXT D-51-06)
- **Columns (16):** `id`, `online_payment_id`, `original_payment_id`, `client_id`, `yookassa_refund_id`, `idempotency_key`, `amount_kopecks`, `status`, `requested_by_user_id`, `reason`, `audit_correlation_id`, `requested_at`, `succeeded_at`, `canceled_at`, `created_at`, `updated_at`

### Constraints Added

| Constraint                                          | Type          | Definition                                                            |
| --------------------------------------------------- | ------------- | --------------------------------------------------------------------- |
| `pk_online_refunds`                                 | PRIMARY KEY   | `id`                                                                  |
| `fk_online_refunds_online_payment_id_online_payments` | FOREIGN KEY  | `online_payment_id → online_payments.id` ON DELETE RESTRICT           |
| `fk_online_refunds_original_payment_id_payments`    | FOREIGN KEY   | `original_payment_id → payments.id` ON DELETE RESTRICT                |
| `fk_online_refunds_client_id_clients`               | FOREIGN KEY   | `client_id → clients.id` ON DELETE RESTRICT                           |
| `fk_online_refunds_requested_by_user_id_users`      | FOREIGN KEY   | `requested_by_user_id → users.id` ON DELETE RESTRICT                  |
| `ck_online_refunds_amount_kopecks_positive`         | CHECK         | `amount_kopecks > 0`                                                  |
| `ck_online_refunds_status`                          | CHECK         | `status IN ('pending','succeeded','canceled')`                        |
| `uq_online_refunds_yookassa_refund_id`              | UNIQUE        | `yookassa_refund_id`                                                  |
| `uq_online_refunds_idempotency_key`                 | UNIQUE        | `idempotency_key`                                                     |
| `uq_online_refunds_alive_per_online_payment`        | PARTIAL UNIQUE| `(online_payment_id) WHERE status IN ('pending','succeeded')`         |

The partial UNIQUE is the schema-layer enforcement of REFUND-03 (single in-flight or successful refund per original online payment). A second concurrent refund attempt raises `IntegrityError` from this index, which plan 51-08 maps to a 409 response.

## Verification

| Check | Result |
| --- | --- |
| `grep -q 'down_revision: str \| None = "0036_payments_received_by_user_id_nullable"'` | PASS |
| `grep -q 'revision: str = "0037_online_refunds"'` | PASS |
| `grep -q 'uq_online_refunds_alive_per_online_payment'` | PASS |
| `grep -q "status IN ('pending','succeeded')"` | PASS |
| `grep -q 'op.f("ck_online_refunds_amount_kopecks_positive")'` | PASS |
| `uv run alembic upgrade head` | PASS (`0037_online_refunds (head)`) |
| `uv run alembic downgrade -1 && uv run alembic upgrade head` (round-trip) | PASS (lossless) |
| `uv run ruff check alembic/versions/0037_online_refunds.py` | PASS |
| psql `\d+ online_refunds` confirms 3 UNIQUEs + 2 CHECKs + 4 FK RESTRICT | PASS |

## Deviations from Plan

None — plan executed exactly as written. The PLAN-level erratum to CONTEXT D-51-06 (use `0036_payments_received_by_user_id_nullable` as down_revision, not `0035_fiscal_receipts`) was honored as the plan instructed.

Note: CONTEXT D-51-04 skeleton (lines 469-475) used a draft partial-index name `uq_online_refunds_online_payment_id_alive`; the plan's `<acceptance_criteria>` and PATTERNS pin the canonical name `uq_online_refunds_alive_per_online_payment`. The canonical name was used.

## Threat Mitigations Implemented

| Threat ID | Mitigation Status |
| --------- | ----------------- |
| T-51-01-01 (Tampering — status enum) | Implemented via `ck_online_refunds_status` CHECK |
| T-51-01-02 (Repudiation — audit chain) | Implemented via nullable `audit_correlation_id` + ON DELETE RESTRICT on `requested_by_user_id` |
| T-51-01-03 (DoS — concurrent duplicate refund) | Implemented via partial UNIQUE `uq_online_refunds_alive_per_online_payment` |
| T-51-01-04 (Tampering — idempotency_key collision) | Implemented via `uq_online_refunds_idempotency_key` UNIQUE |
| T-51-01-05 (PII in migration) | Accepted — schema-only migration, no seed data |

## Commits

| Commit | Type | Description |
| --- | --- | --- |
| `2b50527` | feat(51-01) | add 0037 online_refunds Alembic migration |

## Known Stubs

None.

## Self-Check: PASSED

- File `apps/backend/alembic/versions/0037_online_refunds.py` exists — FOUND
- Commit `2b50527` exists in git log — FOUND
- Migration head is `0037_online_refunds` per `alembic current` — confirmed against live Postgres
- Round-trip (upgrade → downgrade → upgrade) ran cleanly — confirmed

---
phase: 47-bedrock
plan: 01
subsystem: backend/core/audit
tags:
  - audit
  - infra-15-discipline
  - online-payments
  - fiscal-receipts
  - yookassa-webhooks
  - v1.7
requirements:
  - INFRA-34
  - INFRA-35
dependency-graph:
  requires:
    - "LOCKED_AUDIT_EVENTS frozenset structure (Phase 15 INFRA-11)"
    - "AUDIT_PAYLOAD_SCHEMAS registry (Phase 30 INFRA-23)"
    - "audit_correlation_id payload pattern (Phase 41 D-41-20)"
  provides:
    - "9 v1.7 (event, resource_type) tuples in LOCKED_AUDIT_EVENTS"
    - "9 Pydantic v2 payload classes with extra='forbid'"
    - "9 AUDIT_PAYLOAD_SCHEMAS dict entries"
  affects:
    - "Phase 49 PAY-03..05 — online_payment_initiated / yookassa_payment_created callsites"
    - "Phase 50 WH-01/WH-04..06 — webhook intake + payment lifecycle callsites"
    - "Phase 50 FISCAL-01 — fiscal_receipt_dispatched callsite"
    - "Phase 51 FISCAL-04..06 — fiscal_receipt_succeeded/failed callsites"
    - "Phase 52 NOTIFY-05 — reuses OnlinePaymentCanceledPayload schema (no re-declaration)"
tech-stack:
  added: []
  patterns:
    - "Phase 30 INFRA-23 — Pydantic v2 BaseModel + ConfigDict(extra='forbid') per audit event"
    - "Phase 41 D-41-20 — audit_correlation_id: UUID | None as FIRST field per payload"
    - "Phase 15 INFRA-15 — lock taxonomy BEFORE any callsite ships"
key-files:
  created: []
  modified:
    - apps/backend/app/core/audit.py
    - apps/backend/app/core/audit_payloads.py
    - apps/backend/tests/unit/test_audit_taxonomy.py
decisions:
  - "Bumped LOCKED_AUDIT_EVENTS expected-count assertion from 71 to 80 (Rule 3 — required to keep existing AST gate green after appending 9 v1.7 tuples)"
metrics:
  duration_minutes: 12
  completed_date: 2026-05-21
  tasks_completed: 2
  files_modified: 3
---

# Phase 47 Plan 01: v1.7 Audit Taxonomy Lock Summary

INFRA-15 lock for the entire v1.7 online-payments + 54-ФЗ + ЮKassa webhook surface — 9 audit-event tuples appended to `LOCKED_AUDIT_EVENTS` with 9 matching Pydantic v2 payload classes registered in `AUDIT_PAYLOAD_SCHEMAS`, all under a single phase before any callsite ships (D-47).

## What Was Built

### 9 new `LOCKED_AUDIT_EVENTS` tuples (audit.py)

Appended verbatim under a `# v1.7 (Phase 47 lock — emitted in Phases 49/50/51 per INFRA-34)` banner immediately after the v1.6 block:

| # | event_name                    | resource_type     | Phase  | Emit context                        |
|---|-------------------------------|-------------------|--------|-------------------------------------|
| 1 | `online_payment_initiated`    | `online_payment`  | 49     | sync — sale-flow entrypoint         |
| 2 | `yookassa_payment_created`    | `online_payment`  | 49     | sync — after ЮKassa POST /payments  |
| 3 | `online_payment_succeeded`    | `online_payment`  | 50     | webhook — payment.succeeded         |
| 4 | `online_payment_canceled`     | `online_payment`  | 50     | webhook — payment.canceled          |
| 5 | `online_payment_refunded`     | `online_payment`  | 50     | webhook — refund.succeeded          |
| 6 | `fiscal_receipt_dispatched`   | `fiscal_receipt`  | 50     | ARQ — POST receipt to ЮKassa 54-ФЗ  |
| 7 | `fiscal_receipt_succeeded`    | `fiscal_receipt`  | 51     | webhook — receipt confirm           |
| 8 | `fiscal_receipt_failed`       | `fiscal_receipt`  | 51     | ARQ — retry exhaustion / terminal   |
| 9 | `yookassa_webhook_received`   | `yookassa_webhook`| 50     | webhook entry — chain root          |

### 9 new payload classes (audit_payloads.py)

All declare `model_config = ConfigDict(extra="forbid")` and `audit_correlation_id: UUID | None` as the FIRST field (D-41-20 lineage).

| Class                                | Additional fields                                                                                              |
|--------------------------------------|----------------------------------------------------------------------------------------------------------------|
| `OnlinePaymentInitiatedPayload`      | `online_payment_id: UUID`, `client_id: UUID`, `amount_kopecks: int`, `subject_kind: Literal["membership","pt_package"]`, `subject_id: UUID` |
| `YookassaPaymentCreatedPayload`      | `online_payment_id: UUID`, `yookassa_payment_id: str`, `idempotency_key: str`, `confirmation_type: Literal["redirect","qr"]` |
| `OnlinePaymentSucceededPayload`      | `online_payment_id: UUID`, `yookassa_payment_id: str`, `amount_kopecks: int`, `payment_id: UUID`              |
| `OnlinePaymentCanceledPayload`       | `online_payment_id: UUID`, `yookassa_payment_id: str`, `cancellation_party: str \| None`, `cancellation_reason: str \| None` |
| `OnlinePaymentRefundedPayload`       | `online_payment_id: UUID`, `refund_payment_id: UUID`, `amount_kopecks: int`                                   |
| `FiscalReceiptDispatchedPayload`     | `fiscal_receipt_id: UUID`, `payment_id: UUID`, `kind: Literal["payment","refund"]`, `customer_email: str`     |
| `FiscalReceiptSucceededPayload`      | `fiscal_receipt_id: UUID`, `yookassa_receipt_id: str`                                                          |
| `FiscalReceiptFailedPayload`         | `fiscal_receipt_id: UUID`, `failure_reason: str`                                                               |
| `YookassaWebhookReceivedPayload`     | `event_type: str`, `object_id: str`, `idempotency_outcome: Literal["new","duplicate_blocked"]`                |

### 9 new `AUDIT_PAYLOAD_SCHEMAS` entries

```python
# v1.7 (Phase 47 lock — INFRA-35; emitted in Phases 49/50/51)
# Online payment lifecycle (Phase 49/50):
("online_payment_initiated", "online_payment"): OnlinePaymentInitiatedPayload,
("yookassa_payment_created", "online_payment"): YookassaPaymentCreatedPayload,
("online_payment_succeeded", "online_payment"): OnlinePaymentSucceededPayload,
("online_payment_canceled", "online_payment"): OnlinePaymentCanceledPayload,
("online_payment_refunded", "online_payment"): OnlinePaymentRefundedPayload,
# Fiscal receipt lifecycle (Phase 50/51):
("fiscal_receipt_dispatched", "fiscal_receipt"): FiscalReceiptDispatchedPayload,
("fiscal_receipt_succeeded", "fiscal_receipt"): FiscalReceiptSucceededPayload,
("fiscal_receipt_failed", "fiscal_receipt"): FiscalReceiptFailedPayload,
# Webhook intake audit trail (Phase 50):
("yookassa_webhook_received", "yookassa_webhook"): YookassaWebhookReceivedPayload,
```

### Docstring extensions

- `audit.py` module docstring: added a `## v1.7 (Phase 47 lock)` section documenting each pair's emit context, payload-class name, and audit_correlation_id chain semantics.
- `audit_payloads.py`: v1.7 block carries a banner comment explaining the audit_correlation_id chain anchor, the first-field invariant, and the actor_email_snapshot column boundary (per D-41-09).

## Verification Results

| Check                                                                    | Result            |
|--------------------------------------------------------------------------|-------------------|
| `grep -c "v1.7 (Phase 47 lock" audit.py`                                 | 2 (banner + docs) |
| 9 v1.7 string literals present in `LOCKED_AUDIT_EVENTS` literal          | PASS              |
| `grep -c "v1.7 (Phase 47 lock" audit_payloads.py`                        | 2 (banner + dict) |
| 9 new payload class definitions present                                  | PASS              |
| 9 `AUDIT_PAYLOAD_SCHEMAS` tuple keys reachable (runtime assert)           | PASS              |
| Every v1.7 class has `extra="forbid"` config                             | PASS              |
| Every v1.7 class has `audit_correlation_id` as FIRST field                | PASS              |
| `extra="forbid"` rejects unknown kwargs (`ValidationError`)               | PASS              |
| `LOCKED_AUDIT_EVENTS` size = 80 (18+12+6+17+5+13+9)                       | PASS              |
| `uv run pytest tests/unit/test_audit_taxonomy.py -x` (7 tests)            | PASS              |
| `uv run pytest tests/unit/test_audit_payloads.py -x` (49 tests)           | PASS              |
| Combined audit-related sweep (56 tests)                                  | PASS              |
| `uv run ruff check` on audit.py + test_audit_taxonomy.py                  | clean             |
| `uv run ruff check` on audit_payloads.py                                  | only pre-existing E501 line 534 (logged) |
| `uv run mypy --strict` on the 3 touched files                            | clean             |

## Confirmation: Existing AST gate still green

`test_audit_taxonomy.py::test_all_audit_emit_callsites_use_locked_pairs` walks every `audit.emit(...)` call under `apps/backend/app/**/*.py` and asserts each `(event, resource_type)` literal pair is in `LOCKED_AUDIT_EVENTS`. No callsite emits any v1.7 event yet (Phase 47 ships the lock only — callsites land in Phase 49+), so the gate is trivially green for the new pairs. The moment any future callsite uses one of the 9 new event names, the gate green-lights it without test churn.

The `test_locked_audit_events_has_expected_count` sanity-belt assertion was updated from 71 → 80 (Rule 3 deviation, see below).

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 3 - Blocking] Updated count-invariant assertion in test_audit_taxonomy.py from 71 to 80**
- **Found during:** Task 1 verification
- **Issue:** The plan's behavior block stated "no new AST test for audit events is needed" — but `test_locked_audit_events_has_expected_count` already exists as a sanity belt with a hard `assert len(LOCKED_AUDIT_EVENTS) == 71`. Appending 9 v1.7 tuples broke the assertion and blocked Task 1's done criterion ("`uv run pytest tests/unit/test_audit_taxonomy.py -x` passes").
- **Fix:** Bumped the expected count to 80, added a v1.7 paragraph to the test docstring documenting which 9 pairs were added in Phase 47 and where to find this summary. Mirrors the pattern already in place for Phase 30/37/41/42/43 (each previous phase that added pairs amended this same assertion).
- **Files modified:** `apps/backend/tests/unit/test_audit_taxonomy.py`
- **Commit:** 65895a9 (rolled into Task 1 commit per atomic-task discipline)

### Out-of-scope / Deferred

**1. [Pre-existing] E501 ruff error on audit_payloads.py:534**
- A Phase 43 trailing comment on `UserInvitedPayload.link_copied` is 148 chars wide.
- Confirmed via `git stash && ruff check` that the error pre-dates 47-01.
- Logged to `.planning/phases/47-bedrock/deferred-items.md` (SCOPE BOUNDARY — out of scope).

### Compliance with D-47 decisions

| Decision      | Compliance                                                                                              |
|---------------|---------------------------------------------------------------------------------------------------------|
| INFRA-34 cadence — "all 9 v1.7 events in a single frozenset extension before any callsite" | PASS — single phase, two commits (frozenset + payloads), zero callsites added |
| D-41-20 — `audit_correlation_id: UUID \| None` as FIRST field per payload                  | PASS — runtime-verified for all 9 classes via `next(iter(cls.model_fields))` |
| Pydantic v2 `extra='forbid'` per payload (D-30-01)                                          | PASS — runtime-verified by raising `ValidationError` on unknown kwarg         |
| `app.core.audit_payloads` MUST NOT import from `app.modules.*`                              | PASS — no new imports added; module top-doc invariant untouched              |

## Self-Check: PASSED

- File `apps/backend/app/core/audit.py` — modified, exists.
- File `apps/backend/app/core/audit_payloads.py` — modified, exists.
- File `apps/backend/tests/unit/test_audit_taxonomy.py` — modified, exists.
- File `.planning/phases/47-bedrock/deferred-items.md` — created, exists.
- Commit `65895a9` (Task 1) — present in `git log`.
- Commit `00ff9cd` (Task 2) — present in `git log`.

## Threat Flags

None. The plan's `<threat_model>` block enumerated 4 STRIDE entries; all 3 `mitigate` dispositions are satisfied verbatim (T-47-01-01: append-only frozenset; T-47-01-02: `audit_correlation_id` first field on every payload; T-47-01-03: `extra='forbid'` on every payload). T-47-01-04 (`accept`) requires no action. No new threat surface introduced beyond what the threat register already enumerated.

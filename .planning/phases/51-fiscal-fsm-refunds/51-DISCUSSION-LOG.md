# Phase 51: Fiscal FSM + Refunds - Discussion Log

> **Audit trail only.** Do not use as input to planning, research, or execution agents.
> Decisions are captured in 51-CONTEXT.md — this log preserves the alternatives considered.

**Date:** 2026-05-23
**Phase:** 51-fiscal-fsm-refunds
**Mode:** `--auto` (no interactive prompts; recommended defaults applied)
**Areas discussed (auto-selected):** Module layout (refund endpoint placement + webhook handler placement), Refund request lifecycle modeling, Fiscal dispatch ARQ task (location + retries + circuit breaker scope), Cron jobs (monitor stale + poll pending refunds), Audit event additions, FSM choice for refunded subjects, `_post_commit_enqueue` extension strategy, RBAC/CSRF posture on new endpoints

---

## Module Layout — refund endpoint vs webhook handlers

| Option | Description | Selected |
|--------|-------------|----------|
| Refund endpoint in `_internal/yookassa/` | Co-locate user-facing endpoint with webhook handlers under `_internal` | |
| Refund endpoint in new `app/api/v1/online_payments/` package; webhook handlers stay in Phase 50 `_internal/yookassa/handlers.py` | Separation of user-facing transport vs `_internal` IP-gated webhook seam; reuses Phase 50 dispatch chain | ✓ |
| Both endpoint and webhook in `app/modules/online_refunds/router.py` | Folder-per-module symmetry | |

**Auto-selected:** option 2 (D-51-01 + D-51-02).
**Rationale:** `_internal` is reserved for anonymous/IP-gated transport endpoints (D-42-17 / D-50-39). User-facing refund must live under a CSRF + RBAC-gated namespace; webhook handlers stay where Phase 50 put them so the entire ЮKassa event-dispatch chain stays in one file.

---

## Refund Request Lifecycle Modeling

| Option | Description | Selected |
|--------|-------------|----------|
| Single `payments` table; refund row INSERTed at endpoint time with `status='pending'` | Reuse v1.4 ledger; add status column to payments | |
| New `online_refunds` table tracks request; `payments` signed refund row written by webhook | Two-table model: request tracking decoupled from settled ledger; preserves v1.4 partial UNIQUE invariants | ✓ |
| INSERT `payments` refund row immediately, mutate on webhook | Mixed responsibility | |

**Auto-selected:** option 2 (D-51-04, D-51-05).
**Rationale:** `payments` is the canonical settled ledger; mixing in pending state would break v1.4 invariants (`subject_kind='refund' AND amount_kopecks < 0` CHECK + partial UNIQUE on refund_of). A request-tracking table parallels Phase 49's `online_payments` design and preserves the partial UNIQUE as the idempotency backstop on the webhook side (REFUND-03).

---

## Endpoint Order — Call ЮKassa Before or After DB INSERT

| Option | Description | Selected |
|--------|-------------|----------|
| INSERT online_refunds(yookassa_refund_id='') → call ЮKassa → UPDATE row | Two-phase commit; row exists even if ЮKassa call fails | |
| Call ЮKassa first → INSERT online_refunds with real refund_id | Single transaction; reconciliation cron handles leak case | ✓ |

**Auto-selected:** option 2 (D-51-09).
**Rationale:** DB UNIQUE on `(yookassa_refund_id)` + reconciliation cron (D-51-17) cleanly cover the leak case. Option 1 leaves orphan rows with empty refund_id requiring cleanup logic.

---

## Fiscal Dispatch ARQ Task Location

| Option | Description | Selected |
|--------|-------------|----------|
| `app/modules/fiscal_receipts/tasks.py` | Co-located with module ORM | ✓ |
| `app/workers/fiscal_receipt_tasks.py` | All ARQ tasks under workers/ | |
| `app/api/v1/_internal/yookassa/tasks.py` | Co-located with webhook | |

**Auto-selected:** option 1 (D-51-13).
**Rationale:** Phase 27 (expiring notifications) + Phase 39 (booking reminders) precedent — ARQ tasks live in `modules/{domain}/tasks.py`, registered into `WorkerSettings` via import in `app/workers/__init__.py`.

---

## Circuit Breaker Scope

| Option | Description | Selected |
|--------|-------------|----------|
| Copy-and-adapt from `app/integrations/email/circuit_breaker.py` to `app/integrations/yookassa/circuit_breaker.py` | Integrations isolated; threshold/TTL/audit-event names domain-specific | ✓ |
| Generalize to shared `app/core/circuit_breaker.py` consumed by both | DRY but cross-integration coupling | |

**Auto-selected:** option 1 (D-51-14).
**Rationale:** `integrations-isolated` import-linter contract; generalization is premature with only 2 consumers. Revisit when a 3rd integration adopts the pattern.

---

## Cron Cadence + Staleness Windows

| Option | Description | Selected |
|--------|-------------|----------|
| `monitor_stale_fiscal_receipts` every 15min Europe/Moscow, scans rows older than 90s; `poll_pending_refunds` every 30min, scans rows older than 30min | Per REQUIREMENTS FISCAL-06 + REFUND-04 + ROADMAP SC #3, SC #6 explicit | ✓ |
| Combined into a single cron polling everything | Reduces worker tick density but couples failure modes | |

**Auto-selected:** option 1 (D-51-16, D-51-17).
**Rationale:** ROADMAP success criteria pin the cadences explicitly. Separation of concerns simplifies failure-mode analysis.

---

## FSM for Refunded Subject (Membership / PT-Package)

| Option | Description | Selected |
|--------|-------------|----------|
| Reuse Phase 32/33: transition to `'cancelled'` + set `cancellation_reason='refunded'` (CANCELLATION_REASON_REFUNDED sentinel) | Mirror offline refund flow; no FSM constant edits | ✓ |
| Add new `'refunded'` status to MEMBERSHIP_STATUS_TRANSITIONS + PT_PACKAGE_STATUS_TRANSITIONS | New terminal state matching ROADMAP wording | |

**Auto-selected:** option 1 (D-51-11 step "subject-transition" + Phase 32 precedent reuse).
**Rationale:** ROADMAP success criterion 5 wording "transitions to refunded" is informal — Phase 32 establishes the convention that refund is a special-case cancellation with a sentinel reason. Adding a new FSM state would force breaking the MEMBERSHIP_STATUS_TRANSITIONS frozenset (compatibility risk with all existing queries/filters).

---

## `_post_commit_enqueue` Extension Strategy (Phase 50 DEFER-50-04)

| Option | Description | Selected |
|--------|-------------|----------|
| Extend signature with `fiscal_receipt_id: UUID \| None = None`; branch body on which kwargs are passed; update AST gate in lockstep | Backward-compatible signature; Phase 51 fills fiscal dispatch branch; Phase 52 fills notification branch | ✓ |
| Replace with a single notification-only signature; move fiscal dispatch inline into webhook handler | Cleaner separation but loses the post-commit seam discipline | |

**Auto-selected:** option 1 (D-51-15).
**Rationale:** Phase 50 DEFER-50-04 explicitly anticipated multi-branch growth; the AST gate enforces the lockstep update so future phases can't accidentally orphan invariants.

---

## RBAC + CSRF on New Endpoints

| Option | Description | Selected |
|--------|-------------|----------|
| Refund endpoint requires `('refund','membership')` / `('refund','pt_package')` permissions (Phase 32/33 already registered) + verify_csrf | Reuse existing permission catalog; matches offline refund pattern | ✓ |
| Add new `('online_refund','*')` permission pair | Distinguish online vs offline refund authorization | |

**Auto-selected:** option 1 (D-51-10, D-51-24).
**Rationale:** Refund authorization is a domain-level capability; the channel (online vs offline) is incidental. Operator workflow consistency favors reuse.

---

## Claude's Discretion

(See `<decisions>` "Claude's Discretion" section in 51-CONTEXT.md for the full enumerated list — 11 items including logger names, cron timezone, receipt subject literals, idempotency-key ownership, `_post_commit_enqueue` signature evolution, ARQ task max_tries config, SELECT FOR UPDATE SKIP LOCKED choice, and test fixture reuse.)

---

## Deferred Ideas

(See `<deferred>` section in 51-CONTEXT.md.)

- `payment.waiting_for_capture` handler — DEFER-50-01; Phase 53.
- Orphan recovery cron — DEFER-50-02; Phase 53.
- v1.4 partial-refund B-02 — still deferred to v1.8+.
- NOT-02 refund DM + NOT-04 fiscal-failure DM — Phase 52.
- DEFER-50-03 operator runbook for cancellation enum values — Phase 53.
- `yookassa_call_failed` audit event — re-deferred from Phase 50 carry-forward.
- 3 pre-existing route-introspection failures — Phase 50 carry-forward; v1.8.
- Generalize circuit breaker — explicitly rejected; revisit on 3rd consumer.
- Receipt body for partial refunds — out of scope.

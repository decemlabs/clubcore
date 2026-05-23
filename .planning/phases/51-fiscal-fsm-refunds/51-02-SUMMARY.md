---
phase: 51
plan: 51-02
subsystem: online_refunds + audit_catalog
tags: [refund, fsm, audit, locked_events, pydantic_payloads, online_refunds]
dependency_graph:
  requires:
    - 51-01 (online_refunds table + UNIQUE constraints via migration 0037)
    - 47-01 (LOCKED_AUDIT_EVENTS + AUDIT_PAYLOAD_SCHEMAS infrastructure)
  provides:
    - app.modules.online_refunds.constants.ONLINE_REFUND_STATUS_TRANSITIONS
    - app.modules.online_refunds.constants.STATUS_PENDING / STATUS_SUCCEEDED / STATUS_CANCELED
    - app.modules.online_refunds.constants.ErrorCode (5 members)
    - app.modules.online_refunds.models.OnlineRefund (ORM)
    - app.modules.online_refunds.repository — 7 helpers (insert, 3 getters, select_pending_older_than, mark_succeeded, mark_canceled)
    - app.modules.online_refunds.schemas.OnlineRefundRequest / OnlineRefundResponse
    - 3 new LOCKED audit pairs under resource_type 'online_refund'
    - 3 new Pydantic payload classes (OnlineRefundInitiatedPayload / OnlineRefundPolledSettledPayload / OnlineRefundCanceledPayload)
  affects:
    - 51-05 (poll dispatch task) — will consume ErrorCode + repository helpers
    - 51-07 (refund webhook handlers) — will consume ONLINE_REFUND_STATUS_TRANSITIONS + mark_succeeded/canceled + 2 polled-* audit events
    - 51-08 (POST /refund endpoint) — will consume schemas + insert_online_refund + initiated audit event
    - 51-09 (poll-pending-refunds cron) — will consume select_pending_older_than + 2 polled-* audit events
tech_stack:
  added: []
  patterns:
    - "caller-owns-txn repository (D-32-10): no flush, no commit"
    - "MappingProxyType FSM constant (Phase 24/50 lineage)"
    - "bare CHECK constraint names + NAMING_CONVENTION expansion (online_payments PATTERN)"
    - "Pydantic ConfigDict(extra='forbid') for audit payload classes (Phase 30 INFRA-23)"
    - "with_for_update(skip_locked=True) for poll-cron row claim (D-51-17 / fiscal_receipts analog)"
    - "single-temporal-column discipline (no TimestampMixin) — explicit requested_at/succeeded_at/canceled_at + created_at/updated_at"
key_files:
  created:
    - apps/backend/app/modules/online_refunds/__init__.py
    - apps/backend/app/modules/online_refunds/constants.py
    - apps/backend/app/modules/online_refunds/models.py
    - apps/backend/app/modules/online_refunds/repository.py
    - apps/backend/app/modules/online_refunds/schemas.py
    - apps/backend/tests/unit/test_online_refund_fsm.py
  modified:
    - apps/backend/app/core/audit.py
    - apps/backend/app/core/audit_payloads.py
    - apps/backend/tests/unit/test_audit_taxonomy.py
decisions:
  - "ErrorCode omits CLIENT_EMAIL_REQUIRED (D-51-08): refund inherits customer email from parent OnlinePayment; no new email check at the refund layer."
  - "FSM constant matches D-51-07 byte-for-byte: pending → {succeeded, canceled}; succeeded and canceled are TERMINAL (empty frozenset)."
  - "OnlineRefund composition is Base + UUIDPkMixin only (no Timestamp/SoftDelete mixins) — single-temporal-column discipline matching online_payments analog."
  - "CHECK constraint names are BARE so NAMING_CONVENTION expands them; UNIQUE constraint names are full literals (matches online_payments precedent)."
  - "select_pending_older_than defaults to limit=50 (D-51-17 step 6 loop budget) — DoS mitigation T-51-02-05."
  - "All 3 new payload classes use ConfigDict(extra='forbid') — T-51-02-03 mitigation."
  - "OnlineRefundInitiatedPayload.audit_correlation_id is a fresh chain ROOT (new uuid4); the 2 polled-* events are CHILD emits carrying the initiate dispatch UUID."
metrics:
  duration_minutes: 8
  tasks_completed: 3
  tasks_total: 3
  files_created: 6
  files_modified: 3
  commits: 3
  completed_date: 2026-05-23
---

# Phase 51 Plan 02: online_refunds Module Skeleton + Audit Catalog Extension Summary

Establishes the application-level contract surface for Phase 51 refunds: ships the `online_refunds` Python module (constants + ORM + repository + Pydantic schemas) and extends the audit catalog with 3 new LOCKED event pairs + 3 Pydantic payload classes that subsequent plans (51-07/51-08/51-09) will emit and consume.

## One-Liner

5-file `online_refunds` package skeleton with caller-owns-txn repository + immutable FSM constant matching `ONLINE_PAYMENT_STATUS_TRANSITIONS`, plus 3 new LOCKED audit pairs and 3 `extra="forbid"` Pydantic payload classes registered in `AUDIT_PAYLOAD_SCHEMAS`.

## Tasks Completed

| Task | Name | Commit | Files |
|------|------|--------|-------|
| 1 | Create `app/modules/online_refunds/` module skeleton | `5457de2` | 5 new files in `app/modules/online_refunds/` |
| 2 | Append 3 LOCKED audit pairs + 3 payload classes | `b4155f8` | `app/core/audit.py`, `app/core/audit_payloads.py`, `tests/unit/test_audit_taxonomy.py` |
| 3 | Wire ONLINE_REFUND_STATUS_TRANSITIONS unit test | `85a265a` | `tests/unit/test_online_refund_fsm.py` (new) |

## Files Created

- `apps/backend/app/modules/online_refunds/__init__.py` — module marker.
- `apps/backend/app/modules/online_refunds/constants.py` — `ErrorCode` StrEnum (5 members), STATUS_* literals, `ONLINE_REFUND_STATUS_TRANSITIONS` MappingProxyType.
- `apps/backend/app/modules/online_refunds/models.py` — `OnlineRefund(Base, UUIDPkMixin)` ORM mirroring migration 0037 column-for-column with bare-name CHECK + full-literal UNIQUE + partial UNIQUE index.
- `apps/backend/app/modules/online_refunds/repository.py` — 7 helpers: `insert_online_refund`, `get_online_refund_by_id`, `get_online_refund_by_yookassa_refund_id`, `get_online_refund_by_idempotency_key`, `select_pending_older_than` (with_for_update skip_locked, default limit=50), `mark_succeeded`, `mark_canceled`.
- `apps/backend/app/modules/online_refunds/schemas.py` — `OnlineRefundRequest(BackendSchemaBase)` (idempotency_key UUID + reason str|None) and `OnlineRefundResponse(ResponseData)` (online_refund_id, status, yookassa_refund_id).
- `apps/backend/tests/unit/test_online_refund_fsm.py` — 8 assertions locking the FSM shape (mirrors `test_online_payment_status_transitions.py`).

## Files Modified

- `apps/backend/app/core/audit.py` — appended 3 pairs to `LOCKED_AUDIT_EVENTS` (immediately after the Phase 50 `pt_package_activated_online` line); extended the resource-type catalog docstring with the 3 events and their payload-field listings.
- `apps/backend/app/core/audit_payloads.py` — added 3 new BaseModel classes (`OnlineRefundInitiatedPayload`, `OnlineRefundPolledSettledPayload`, `OnlineRefundCanceledPayload`) immediately above the `AUDIT_PAYLOAD_SCHEMAS` registry block; registered all 3 tuple keys in the registry.
- `apps/backend/tests/unit/test_audit_taxonomy.py` — bumped `len(LOCKED_AUDIT_EVENTS) == 82` → `== 85`; extended the running-total docstring with the Phase 51 +3 delta (v1.7 count 11 → 14).

## 3 New LOCKED Audit Pairs

1. `("online_refund_initiated", "online_refund")` — chain root, emitted from POST /online-payments/.../refund (Plan 51-08).
2. `("online_refund_polled_settled", "online_refund")` — CHILD emit from poll_pending_refunds cron when synthesising a settle UoW after a missed webhook (Plan 51-09 / D-51-17 step 3).
3. `("online_refund_canceled", "online_refund")` — CHILD emit from poll_pending_refunds cron when ЮKassa reports the refund canceled (Plan 51-09 / D-51-17 step 4).

## 3 New Pydantic Payload Classes

| Class | Event Pair | Notable Fields |
|-------|-----------|----------------|
| `OnlineRefundInitiatedPayload` | `(online_refund_initiated, online_refund)` | audit_correlation_id (chain ROOT — fresh uuid4), online_refund_id, online_payment_id, original_payment_id, amount_kopecks, requested_by_user_id, reason |
| `OnlineRefundPolledSettledPayload` | `(online_refund_polled_settled, online_refund)` | audit_correlation_id (CHILD), online_refund_id, yookassa_refund_id, settled_at |
| `OnlineRefundCanceledPayload` | `(online_refund_canceled, online_refund)` | audit_correlation_id (CHILD), online_refund_id, yookassa_refund_id, cancellation_reason |

All three carry `model_config = ConfigDict(extra="forbid")` (T-51-02-03 mitigation).

## LOCKED_AUDIT_EVENTS Cardinality

- Before this plan: `len(LOCKED_AUDIT_EVENTS) == 82` (test_audit_taxonomy.py baseline)
- After this plan: `len(LOCKED_AUDIT_EVENTS) == 85` (+3 Phase 51 entries)
- v1.7 subset: was 11 (Phase 47 INFRA-34 baseline 9 + Phase 50 D-50-23 +2 activation pairs); now 14 (+3 refund-lifecycle pairs)

## Verification Run

- `pytest tests/unit/test_online_refund_fsm.py tests/unit/test_locked_audit_events.py tests/unit/test_audit_taxonomy.py tests/unit/test_audit_payloads.py -q` → **75 passed**.
- `ruff check app/modules/online_refunds/` → clean.
- `mypy --strict app/modules/online_refunds/` → clean (5 files, 0 issues).
- `ruff check app/core/audit.py app/core/audit_payloads.py` → 1 PRE-EXISTING E501 on `app/core/audit_payloads.py:541` (UserInvitedPayload docstring; last modified in Phase 50, not by this plan). Tracked under DEFER-46-04 tree-wide ruff debt. Out of scope per scope-boundary rule.
- `lint-imports` → 3 contracts kept, 0 broken.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] Plan errata: LOCKED_AUDIT_EVENTS starting count was 82, not 79**

- **Found during:** Task 2 — after appending the 3 new pairs, `pytest tests/unit/test_audit_taxonomy.py::test_locked_audit_events_has_expected_count` failed with "expected 82, got 85".
- **Issue:** The plan's must_haves item #5 stated the effective count was `79 → 82`, sourced from a planner-time grep that matched only literal lines without comments interleaved. The actual `len(LOCKED_AUDIT_EVENTS)` (frozenset cardinality) was already 82 BEFORE this plan (per the existing `test_locked_audit_events_has_expected_count` assertion and its breakdown docstring: 18 v1.1 + 12 v1.2 + 6 v1.3 + 17 v1.4 + 5 v1.5 + 13 v1.6 + 11 v1.7 = 82). After this plan it is 85 (+3 refund pairs lifting v1.7 from 11 to 14).
- **Fix:** Updated the assertion in `tests/unit/test_audit_taxonomy.py` from `== 82` to `== 85`, and extended the docstring with a new paragraph explaining the Phase 51 +3 delta (mirrors the Phase 50 D-50-23 +2 paragraph pattern).
- **Files modified:** `apps/backend/tests/unit/test_audit_taxonomy.py`
- **Commit:** `b4155f8` (bundled with the Task 2 audit pair + payload addition since the bump was a direct consequence of the same change-set).
- **Rule classification:** Rule 1 — without the bump, the AST-guard test would fail and any subsequent plan touching audit.py would inherit a broken gate.

The literal-line-count grep mentioned in the plan's acceptance criteria still produced 79 → 82 (the criterion as-written passes); the discrepancy is purely between "literal lines matching the strict regex" and "frozenset cardinality". The latter is the source of truth for the AST gate.

### Out-of-Scope Discoveries (deferred)

- `app/core/audit_payloads.py:541` E501 (148 chars) — pre-existing tree-wide ruff debt last touched in Phase 50. Falls under DEFER-46-04 (v1.9 doc-debt + test-debt sweep). NOT logged anew because deferred-items.md already covers the tree-wide ruff issue.

## Threat Flags

None — no new network endpoints, auth paths, file access patterns, or trust-boundary schema changes. The plan only adds module-internal contract surface (constants/ORM/repository/schemas) and registers new pairs in two pre-existing append-only registries. Threat coverage per the plan's STRIDE register (T-51-02-01..05) is satisfied:

- T-51-02-01 (audit identifier injection) — AST gate `test_locked_audit_events.py` is unchanged and still passes; new entries are append-only literals.
- T-51-02-02 (PII in payloads) — verified: no `customer_email` in any of the 3 new classes; `reason` is operator-internal free text.
- T-51-02-03 (Pydantic extras) — all 3 classes ship `ConfigDict(extra="forbid")`.
- T-51-02-04 (refund chain-root operator attribution) — `OnlineRefundInitiatedPayload.requested_by_user_id: UUID` is mandatory (not `UUID | None`).
- T-51-02-05 (unbounded poll query) — `select_pending_older_than` defaults `limit=50`.

## Self-Check: PASSED

- Files created (6) — all FOUND:
  - `apps/backend/app/modules/online_refunds/__init__.py` FOUND
  - `apps/backend/app/modules/online_refunds/constants.py` FOUND
  - `apps/backend/app/modules/online_refunds/models.py` FOUND
  - `apps/backend/app/modules/online_refunds/repository.py` FOUND
  - `apps/backend/app/modules/online_refunds/schemas.py` FOUND
  - `apps/backend/tests/unit/test_online_refund_fsm.py` FOUND
- Files modified (3) — all show diffs:
  - `apps/backend/app/core/audit.py` MODIFIED (3 pair appends + catalog docstring)
  - `apps/backend/app/core/audit_payloads.py` MODIFIED (3 classes + registry entries)
  - `apps/backend/tests/unit/test_audit_taxonomy.py` MODIFIED (count 82→85 + docstring)
- Commits (3) — all in `git log --oneline`:
  - `5457de2` FOUND (Task 1)
  - `b4155f8` FOUND (Task 2)
  - `85a265a` FOUND (Task 3)

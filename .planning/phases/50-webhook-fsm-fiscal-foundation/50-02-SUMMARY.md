---
phase: 50-webhook-fsm-fiscal-foundation
plan: 02
subsystem: audit_taxonomy + online_payments_fsm
tags: [audit, fsm, online_payments, webhook, locked_registry, INFRA-15, D-50-15, D-50-23]
dependency_graph:
  requires:
    - "app/core/audit.py LOCKED_AUDIT_EVENTS frozenset (Phase 47 baseline)"
    - "app/core/audit_payloads.py AUDIT_PAYLOAD_SCHEMAS registry (Phase 47 baseline)"
    - "app/modules/online_payments/constants.py STATUS_PENDING/SUCCEEDED/CANCELED literals (Phase 49)"
    - "app/modules/memberships/constants.py MEMBERSHIP_STATUS_TRANSITIONS (Phase 16/24) — byte-for-byte mirror template"
  provides:
    - "ONLINE_PAYMENT_STATUS_TRANSITIONS: declarative FSM (pending → {succeeded, canceled}; terminal succeeded/canceled)"
    - "MembershipActivatedOnlinePayload + PtPackageActivatedOnlinePayload pydantic v2 schemas (extra=forbid)"
    - "LOCKED_AUDIT_EVENTS: 2 new pairs (membership_activated_online, pt_package_activated_online)"
    - "AUDIT_PAYLOAD_SCHEMAS: registry pairing for both new events"
  affects:
    - "Plan 50-03 (activator bodies) — emits both new audit events; imports both payload classes"
    - "Plan 50-04 (webhook _assert_can_transition) — imports ONLINE_PAYMENT_STATUS_TRANSITIONS"
    - "Plan 52 NOTIFY-* — may reuse activation payloads for downstream fan-out chains"
tech_stack:
  added: []
  patterns:
    - "MappingProxyType-wrapped frozenset edges (INFRA-16 declarative FSM)"
    - "audit_correlation_id: UUID | None as FIRST payload field (D-41-20 forensic chain)"
    - "extra='forbid' on all v1.7 payload schemas (D-30-03 hard-fail discipline)"
    - "Phase 47 INFRA-15 AST/registry gate: new pairs flow through LOCKED + SCHEMAS + per-event payload + dedicated unit test"
key_files:
  created:
    - "apps/backend/tests/unit/test_online_payment_status_transitions.py"
    - "apps/backend/tests/unit/test_locked_audit_events.py"
    - ".planning/phases/50-webhook-fsm-fiscal-foundation/50-02-SUMMARY.md"
  modified:
    - "apps/backend/app/modules/online_payments/constants.py"
    - "apps/backend/app/core/audit.py"
    - "apps/backend/app/core/audit_payloads.py"
    - "apps/backend/tests/unit/test_audit_taxonomy.py"
decisions:
  - "D-50-15 implemented: ONLINE_PAYMENT_STATUS_TRANSITIONS mirrors MEMBERSHIP_STATUS_TRANSITIONS byte-for-byte (MappingProxyType, frozenset edges, explicit terminals)"
  - "D-50-23 implemented: 2 new LOCKED events + 2 payload classes registered for Plan 50-03 webhook-driven activation emits"
  - "test_audit_taxonomy.py size invariant lifted 80 → 82 (Rule 3 — required for the new pairs to pass the existing AST/count gate without manual override)"
  - "Both new payload classes positioned BEFORE OnlinePaymentRefundedPayload in audit_payloads.py (semantic grouping with activator chain — refund is a separate webhook later in the lifecycle)"
metrics:
  duration_seconds: 540
  completed_at: "2026-05-22T16:46:12Z"
  tasks_completed: 2
  tasks_total: 2
  files_created: 3
  files_modified: 4
  commits: 4
---

# Phase 50 Plan 02: Audit Taxonomy + Online-Payment FSM Foundation Summary

Declarative bedrock for Plans 50-03 (activator bodies) and 50-04 (webhook
`_assert_can_transition` helper): 1 immutable FSM constant + 2 new LOCKED
audit events + 2 pydantic payload schemas + their AUDIT_PAYLOAD_SCHEMAS
registry pairings. Pure additive surface — no behavioral code — keeps
Wave 1 parallel-safe with Plan 50-01 and gives Wave 2 the import-time
runtime contracts it needs.

## What Shipped

### 1. `ONLINE_PAYMENT_STATUS_TRANSITIONS` (D-50-15)

`apps/backend/app/modules/online_payments/constants.py`

```python
ONLINE_PAYMENT_STATUS_TRANSITIONS: Mapping[str, frozenset[str]] = MappingProxyType(
    {
        STATUS_PENDING: frozenset({STATUS_SUCCEEDED, STATUS_CANCELED}),
        STATUS_SUCCEEDED: frozenset(),  # terminal
        STATUS_CANCELED: frozenset(),  # terminal
    }
)
```

Byte-for-byte mirror of `MEMBERSHIP_STATUS_TRANSITIONS` (Phase 16 / Phase 24).
Plan 50-04 imports it inside the ЮKassa webhook handler's
`_assert_can_transition(current_status, target_status)` guard so the FSM
edges are enforced at runtime + visible to the AST literal-only gate.

Listed alphabetically in `__all__` between `CONFIRMATION_TYPE_VALUES` and
`STATUS_CANCELED`. Phase 49 content (ErrorCode + STATUS_* + SUBJECT_KIND_*)
preserved verbatim.

### 2. Two new LOCKED audit events (D-50-23)

`apps/backend/app/core/audit.py` — `LOCKED_AUDIT_EVENTS` frozenset:

```python
# Membership / PT-package activation via webhook (Phase 50 WH-05 / D-50-23):
("membership_activated_online", "membership"),
("pt_package_activated_online", "pt_package"),
```

Docstring catalog extended with a "Webhook-driven activation" block
documenting the payload shape + chain semantics (CHILD emit per D-50-18,
`audit_correlation_id` propagation from the webhook-intake row).

### 3. Two new payload schemas (D-50-23)

`apps/backend/app/core/audit_payloads.py`:

```python
class MembershipActivatedOnlinePayload(BaseModel):
    model_config = ConfigDict(extra="forbid")
    audit_correlation_id: UUID | None
    membership_id: UUID
    client_id: UUID
    online_payment_id: UUID


class PtPackageActivatedOnlinePayload(BaseModel):
    model_config = ConfigDict(extra="forbid")
    audit_correlation_id: UUID | None
    pt_package_id: UUID
    client_id: UUID
    online_payment_id: UUID
```

Positioned BEFORE `OnlinePaymentRefundedPayload` (activator chain semantic
grouping). Both follow D-41-20 — `audit_correlation_id: UUID | None` as the
FIRST field so the forensic chain reconstructs across the synchronous
sale-init → webhook → activation → notification fan-out from `audit_log` alone.

### 4. Registry pairings

`AUDIT_PAYLOAD_SCHEMAS` extended at the v1.7 webhook tail:

```python
("membership_activated_online", "membership"): MembershipActivatedOnlinePayload,
("pt_package_activated_online", "pt_package"): PtPackageActivatedOnlinePayload,
```

### 5. Unit test gate (`tests/unit/test_locked_audit_events.py`)

11 new tests:
- 2 LOCKED frozenset membership assertions
- 1 issubset sanity check for the +2 pair count
- 2 × payload validates with valid args (UUID + correlation-id)
- 2 × payload allows None correlation id
- 2 × payload rejects extra fields via ValidationError (extra="forbid")
- 2 × registry maps event-pair to payload class identity

`tests/unit/test_online_payment_status_transitions.py` — 6 new tests
covering import, edge shape, terminals, MappingProxyType immutability,
`__all__` membership.

## Tasks Completed

| Task | Name | Commits | Files |
|------|------|---------|-------|
| 1 | `ONLINE_PAYMENT_STATUS_TRANSITIONS` FSM constant | `69cee09` (test) + `66ba11a` (feat) | `app/modules/online_payments/constants.py`, `tests/unit/test_online_payment_status_transitions.py` |
| 2 | 2 LOCKED audit events + payloads + registry + size invariant | `3316bff` (test) + `4469ce8` (feat) | `app/core/audit.py`, `app/core/audit_payloads.py`, `tests/unit/test_audit_taxonomy.py`, `tests/unit/test_locked_audit_events.py` |

TDD discipline: each task shipped a `test(50-02): ...` RED commit followed
by a `feat(50-02): ...` GREEN commit. RED commits failed as expected
(ImportError); GREEN commits made them pass without changing any test
assertions.

## Verification

```
$ uv run python -c "from app.modules.online_payments.constants import ONLINE_PAYMENT_STATUS_TRANSITIONS; print(dict(ONLINE_PAYMENT_STATUS_TRANSITIONS))"
{'pending': frozenset({'succeeded', 'canceled'}), 'succeeded': frozenset(), 'canceled': frozenset()}

$ uv run pytest tests/unit/test_locked_audit_events.py tests/unit/test_online_payment_status_transitions.py -v
17 passed in 0.02s

$ uv run pytest tests/unit/ -k audit
95 passed, 733 deselected in 0.49s

$ uv run mypy app/core/audit.py app/core/audit_payloads.py app/modules/online_payments/constants.py
Success: no issues found in 3 source files

$ uv run ruff check app/core/audit.py app/modules/online_payments/constants.py \
    tests/unit/test_locked_audit_events.py tests/unit/test_online_payment_status_transitions.py \
    tests/unit/test_audit_taxonomy.py
All checks passed!
```

All plan-level acceptance criteria satisfied:

- [x] `ONLINE_PAYMENT_STATUS_TRANSITIONS` shape matches D-50-15
- [x] 2 new LOCKED audit events present
- [x] 2 new payload classes with `extra="forbid"`
- [x] Both new events registered in `AUDIT_PAYLOAD_SCHEMAS`
- [x] All Phase 49 audit infrastructure intact (95/95 audit-related tests
      pass, including the `test_audit_taxonomy` size gate after the +2 bump)
- [x] ruff + mypy strict clean on every file I touched

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 3 — Blocking] Bumped `test_audit_taxonomy` size invariant 80 → 82**

- **Found during:** Task 2 GREEN verification (broader `pytest -k audit` sweep)
- **Issue:** `tests/unit/test_audit_taxonomy.py::test_locked_audit_events_has_expected_count`
  asserted `len(LOCKED_AUDIT_EVENTS) == 80` — the Phase 47 baseline. Adding
  2 new pairs in D-50-23 makes it 82, which would have failed that gate.
- **Fix:** Updated the assertion + docstring (added a Phase 50 paragraph
  documenting the +2 lift) to expect 82 with v1.7 count 11 instead of 9.
- **Files modified:** `apps/backend/tests/unit/test_audit_taxonomy.py`
- **Commit:** `4469ce8`
- **Justification:** This invariant is the static AST gate for the LOCKED
  registry; D-50-23 by definition lifts it. Updating the count is the
  intended path through the gate (not a circumvention).

**2. [Rule 3 — Blocking] Lifted constant-test imports to module level**

- **Found during:** Task 1 GREEN ruff check
- **Issue:** `test_online_payment_status_transitions.py` initially used
  function-scope imports for the failing-first-test pattern; ruff `I001`
  flagged the un-sorted import block (lazy imports inside tests are not
  the project's convention).
- **Fix:** Moved imports to module top, kept the test bodies cleaner.
  Tests still pass identically.
- **Files modified:** `apps/backend/tests/unit/test_online_payment_status_transitions.py`
- **Commit:** `4469ce8`

### Pre-existing tech debt (NOT fixed, out of scope per executor rules)

- `app/core/audit_payloads.py:534` — E501 long line in
  `UserInvitedPayload` (Phase 43 v1.6 code, completely untouched by this
  plan). Matches DEFER-46-04 in `STATE.md` (tree-wide ruff debt scheduled
  for v1.9 doc-debt sweep).

## TDD Gate Compliance

- Task 1: `test(50-02): add failing tests for ONLINE_PAYMENT_STATUS_TRANSITIONS` (`69cee09`, RED) → `feat(50-02): add ONLINE_PAYMENT_STATUS_TRANSITIONS FSM constant (D-50-15)` (`66ba11a`, GREEN) — RED verified failing before GREEN.
- Task 2: `test(50-02): add failing tests for 2 new LOCKED audit events (D-50-23)` (`3316bff`, RED) → `feat(50-02): add 2 new LOCKED audit events for webhook-driven activation (D-50-23)` (`4469ce8`, GREEN) — RED verified failing before GREEN.

Both gates present in git log; no REFACTOR commits needed (additions
were minimal + final shape from RED tests).

## Known Stubs

None. This plan ships only declarative additions — no executable behavior
that could carry placeholder data.

## Threat Flags

None. All new surface is in-policy:

- Both new audit events extend the LOCKED registry through the documented
  Phase 47 INFRA-15 / INFRA-35 mechanism. No new emitter callsites yet
  (Plan 50-03 ships those).
- No new network endpoints, no new auth paths, no new file/IO surface, no
  schema changes (the audit_payloads classes are pure pydantic models that
  validate kwargs into the existing `audit_log.payload` JSONB column).

## Self-Check: PASSED

- [x] FOUND: apps/backend/app/modules/online_payments/constants.py (ONLINE_PAYMENT_STATUS_TRANSITIONS verified at runtime)
- [x] FOUND: apps/backend/app/core/audit.py (2 new LOCKED entries + docstring catalog block)
- [x] FOUND: apps/backend/app/core/audit_payloads.py (2 new payload classes + 2 new registry entries)
- [x] FOUND: apps/backend/tests/unit/test_locked_audit_events.py (11 tests, all green)
- [x] FOUND: apps/backend/tests/unit/test_online_payment_status_transitions.py (6 tests, all green)
- [x] FOUND: commit `69cee09` (test 1 RED)
- [x] FOUND: commit `66ba11a` (feat 1 GREEN)
- [x] FOUND: commit `3316bff` (test 2 RED)
- [x] FOUND: commit `4469ce8` (feat 2 GREEN)

---
phase: 58-payroll-foundations-ledger
plan: "01"
subsystem: rbac-audit-bedrock
tags: [rbac, audit, permissions, payroll, infra]
dependency_graph:
  requires: []
  provides:
    - OWNER_ONLY pairs (CREATE/COMPENSATION, CREATE/PAYROLL, EDIT/PAYROLL, REFUND/PAYROLL, LIST/PAYROLL)
    - LOCKED_AUDIT_EVENTS (trainer_comp_config_set, payroll_accrual_created, payroll_accrual_paid, payroll_clawback_recorded)
    - Pydantic audit payload schemas for 4 new payroll events
    - admin-web can.ts byte-semantic mirror of new OWNER_ONLY pairs
  affects:
    - apps/backend/app/core/permissions.py
    - apps/backend/app/core/audit.py
    - apps/backend/app/core/audit_payloads.py
    - apps/admin-web/src/shared/session/can.ts
tech_stack:
  added: []
  patterns:
    - INFRA-15 pre-registration (audit events before callsites)
    - Three-way RBAC parity (permissions.py ↔ can.ts ↔ registry.ts)
key_files:
  created: []
  modified:
    - apps/backend/app/core/permissions.py
    - apps/backend/app/core/audit.py
    - apps/backend/app/core/audit_payloads.py
    - apps/admin-web/src/shared/session/can.ts
    - apps/backend/tests/integration/test_rbac_parity.py
decisions:
  - "D-58-15 Claude's Discretion applied: (EDIT, COMPENSATION) collapsed into (CREATE, COMPENSATION) — INSERT-only versioned model makes edit semantically identical to create new version"
metrics:
  duration_minutes: 30
  completed_date: "2026-05-25"
  tasks_completed: 2
  tasks_total: 2
  files_modified: 5
---

# Phase 58 Plan 01: RBAC + Audit Bedrock Pre-Registration Summary

Pre-registered all new OWNER_ONLY permission pairs, LOCKED_AUDIT_EVENTS tuples, and audit payload schemas for Phase 58 payroll domain — before any callsite or service code lands. Follows INFRA-15 discipline established in v1.3/v1.4/v1.6/v1.7.

## What Was Built

### Task 1: Extend permissions.py OWNER_ONLY + mirror in can.ts (commit d256deb)

Extended `OWNER_ONLY` frozenset in `apps/backend/app/core/permissions.py` with 5 new pairs required for payroll ownership gating (D-58-15):

| Pair | Requirement | Purpose |
|------|-------------|---------|
| `(CREATE, COMPENSATION)` | PAY-01 | Set/replace comp config (INSERT-only versioned model) |
| `(CREATE, PAYROLL)` | PAY-03 | Record accrual / run period |
| `(EDIT, PAYROLL)` | PAY-04 | Mark accrual paid (single allowed mutation) |
| `(REFUND, PAYROLL)` | PAY-06 | Clawback hook authorization |
| `(LIST, PAYROLL)` | PAY-05 | Paginated accrual list |

Count grew from 35 to 40. Existing `(VIEW, PAYROLL)` and `(VIEW, COMPENSATION)` entries at lines 66-67 remain unchanged.

Mirrored the same 5 pairs in `apps/admin-web/src/shared/session/can.ts` as TypeScript object literals (lowercase action/resource strings, no semicolons per Prettier config).

Updated three-way RBAC parity test (`test_owner_only_count_is_thirty_five` → `test_owner_only_count_is_forty`) to reflect the new count. All 4 parity tests green.

**No changes to registry.ts** — `payroll`/`compensation` resources and all 5 actions already existed there.

### Task 2: Extend LOCKED_AUDIT_EVENTS + audit payload schemas (commit 4b1c309)

Appended 4 new event tuples to `LOCKED_AUDIT_EVENTS` frozenset in `apps/backend/app/core/audit.py` (D-58-16):

| Event | Resource Type | Requirement |
|-------|---------------|-------------|
| `trainer_comp_config_set` | `trainer_comp_config` | PAY-01 |
| `payroll_accrual_created` | `payroll_accrual` | PAY-03 |
| `payroll_accrual_paid` | `payroll_accrual` | PAY-04 |
| `payroll_clawback_recorded` | `payroll_accrual` | PAY-06 |

Added 4 new Pydantic payload classes in `apps/backend/app/core/audit_payloads.py` (D-58-17):

- `TrainerCompConfigSetPayload` — comp config id, trainer id, commission_pct_bps, session_fee_kopecks, effective_from
- `PayrollAccrualCreatedPayload` — accrual id, trainer id, period dates, sessions count, revenue/accrual kopecks, comp_config_id_snapshot
- `PayrollAccrualPaidPayload` — accrual id, trainer id, paid_by_user_id, accrual kopecks
- `PayrollClawbackRecordedPayload` — clawback accrual id, original accrual id, trainer id, source refund payment id, pt_package id, accrual kopecks (signed negative)

All classes use plain `pydantic.BaseModel` + `ConfigDict(extra="forbid")` (not `BackendSchemaBase` per module docstring boundary). Zero imports from `app.modules.*`.

Added 4 corresponding entries to `AUDIT_PAYLOAD_SCHEMAS` dict.

## Verification Results

| Check | Result |
|-------|--------|
| Python import: 5 new OWNER_ONLY pairs | PASS (size=40) |
| Python import: 4 new LOCKED_AUDIT_EVENTS | PASS (size=89) |
| Python import: 4 new payload classes + registry entries | PASS |
| ConfigDict(extra="forbid") on all 4 classes | PASS |
| Zero audit.emit() callsites added | PASS |
| Zero app.modules.* imports in audit_payloads.py | PASS |
| Three-way RBAC parity test (4 tests) | PASS (4/4 green) |
| Frontend tsc --noEmit | PASS |
| mypy --strict on permissions.py + audit.py + audit_payloads.py | PASS |
| ruff check on new code | PASS (2 pre-existing E501 errors in other sections, out of scope) |
| registry.ts unchanged | PASS (confirmed no diff) |
| grep payroll_accrual_created in audit.py | 1 occurrence |

## Final State

- `OWNER_ONLY`: **40 entries** (was 35; +5 v1.9 Phase 58 INFRA-15 pairs)
- `LOCKED_AUDIT_EVENTS`: **89 entries** (was 85; +4 v1.9 Phase 58 payroll events)
- `AUDIT_PAYLOAD_SCHEMAS`: **55 entries** (was 51; +4 v1.9 payroll payload schemas)
- `can.ts OWNER_ONLY`: **40 entries** (byte-semantic mirror verified by parity test)

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] Updated RBAC parity test count assertion**
- **Found during:** Task 1 verification
- **Issue:** `test_owner_only_count_is_thirty_five` had a hardcoded `== 35` assertion that failed after we added 5 new pairs (grew to 40)
- **Fix:** Renamed test to `test_owner_only_count_is_forty`, updated docstring and both assertions to `== 40`
- **Files modified:** `apps/backend/tests/integration/test_rbac_parity.py`
- **Commit:** d256deb (included in Task 1 commit)

## Known Stubs

None — this is a bedrock pre-registration plan with no UI or data flow stubs. All payload classes have proper field definitions; no placeholders or TODO fields.

## Threat Flags

No new network endpoints, auth paths, or schema changes introduced by this plan. The OWNER_ONLY pairs and LOCKED_AUDIT_EVENTS are pure in-memory Python frozensets — no new DB surface. Threat mitigations T-58-01 through T-58-05 are satisfied by this bedrock registration (they will be enforced at runtime when service code lands in later plans).

## Self-Check

See below.

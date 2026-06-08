---
phase: 96-referral-domain-backend
plan: "01"
subsystem: backend-core
tags: [audit, infra-15, referral, pydantic, tdd]
requirements: [REFER-01, REFER-03]

dependency_graph:
  requires: []
  provides:
    - "LOCKED_AUDIT_EVENTS includes (referral_code_generated, referral) and (referral_captured, referral)"
    - "ReferralCodeGeneratedPayload typed schema with extra=forbid"
    - "ReferralCapturedPayload typed schema with extra=forbid"
    - "AUDIT_PAYLOAD_SCHEMAS registry entries for both referral pairs"
  affects:
    - "apps/backend/app/core/audit.py"
    - "apps/backend/app/core/audit_payloads.py"

tech_stack:
  added: []
  patterns:
    - "INFRA-15: audit pairs + typed payloads registered BEFORE any callsite"
    - "ConfigDict(extra=forbid) on all new payload classes"
    - "TDD RED/GREEN commit sequence"

key_files:
  created:
    - path: "apps/backend/tests/unit/test_referral_audit_events.py"
      role: "Unit tests mirroring test_loyalty_audit_events.py — 8 tests covering lock assertion, payload validation, extra-field rejection, registry mapping"
  modified:
    - path: "apps/backend/app/core/audit.py"
      role: "Extended LOCKED_AUDIT_EVENTS frozenset with v2.6 referral block (2 new pairs)"
    - path: "apps/backend/app/core/audit_payloads.py"
      role: "Added ReferralCodeGeneratedPayload + ReferralCapturedPayload classes + 2 registry entries"

decisions:
  - "Followed exact INFRA-15 discipline: both pairs locked in LOCKED_AUDIT_EVENTS and AUDIT_PAYLOAD_SCHEMAS before any callsite (Plan 96-03 ships callsites)"
  - "TDD sequence: RED commit (test file, failing at import) → GREEN commit (implementation + ruff fix)"
  - "ReferralCodeGeneratedPayload fields: client_id, referral_code_id, code (str for 8-char Crockford value)"
  - "ReferralCapturedPayload fields: referee_client_id, referrer_client_id, referral_capture_id, referral_code_id"

metrics:
  duration: "~8 minutes"
  completed: "2026-06-08"
  tasks_completed: 2
  files_created: 1
  files_modified: 2
---

# Phase 96 Plan 01: Referral Audit Pairs Pre-Registration Summary

Two v2.6 referral audit pairs locked in `LOCKED_AUDIT_EVENTS` + typed `extra="forbid"` Pydantic payload schemas registered in `AUDIT_PAYLOAD_SCHEMAS` before any service callsite exists — satisfying INFRA-15 discipline for the referral domain (REFER-01/REFER-03).

## Tasks Completed

| Task | Name | Commit | Files |
|------|------|--------|-------|
| 1 (RED) | Failing unit tests | cbd3d77f | tests/unit/test_referral_audit_events.py (new) |
| 1 (GREEN) | Lock pairs + payload schemas | 50f8da08 | app/core/audit.py, app/core/audit_payloads.py, tests/unit/test_referral_audit_events.py (ruff fix) |

## What Was Done

**audit.py** — appended v2.6 block to `LOCKED_AUDIT_EVENTS` frozenset immediately after the v2.5 messaging block:
```python
# v2.6 (Phase 96 lock — INFRA-15; referral domain. Pre-registered BEFORE
# any callsite per INFRA-15 discipline.)
("referral_code_generated", "referral"),
("referral_captured", "referral"),
```

**audit_payloads.py** — added two payload classes above the `AUDIT_PAYLOAD_SCHEMAS` dict:
- `ReferralCodeGeneratedPayload`: fields `client_id: UUID`, `referral_code_id: UUID`, `code: str`
- `ReferralCapturedPayload`: fields `referee_client_id: UUID`, `referrer_client_id: UUID`, `referral_capture_id: UUID`, `referral_code_id: UUID`

Both use `model_config = ConfigDict(extra="forbid")`.

Added two registry entries under `# v2.6 (Phase 96 referral domain — REFER-01/REFER-03 / INFRA-15)` comment.

**test_referral_audit_events.py** — 8 unit tests mirroring `test_loyalty_audit_events.py`:
1. `test_referral_code_generated_event_locked` — LOCKED_AUDIT_EVENTS assertion
2. `test_referral_code_generated_payload_validates` — correct sample validates
3. `test_referral_code_generated_payload_rejects_extra_fields` — extra="forbid"
4. `test_audit_payload_schemas_registers_referral_code_generated` — registry mapping
5. `test_referral_captured_event_locked` — LOCKED_AUDIT_EVENTS assertion
6. `test_referral_captured_payload_validates` — correct sample validates
7. `test_referral_captured_payload_rejects_extra_fields` — extra="forbid"
8. `test_audit_payload_schemas_registers_referral_captured` — registry mapping

## Verification Results

- `pytest tests/unit/test_referral_audit_events.py -q` → **8 passed**
- `mypy --strict app/core/audit.py app/core/audit_payloads.py` → **Success: no issues found**
- `ruff check app/core/audit.py app/core/audit_payloads.py tests/unit/test_referral_audit_events.py` → **All checks passed**

## Deviations from Plan

None — plan executed exactly as written.

The only minor fix: one E501 ruff violation in the test file docstring (line > 100 chars) was fixed by wrapping the long line. This is covered under Rule 1 (auto-fix).

## Known Stubs

None. This plan adds pure infrastructure (audit registry + schemas), no UI or data-flow stubs.

## Threat Flags

None. No new network endpoints, auth paths, or trust boundaries introduced. The two audit pairs are pre-registration scaffolding consumed by Plan 96-03.

## TDD Gate Compliance

- RED gate: `test(96-01)` commit `cbd3d77f` — test file created, import fails (no classes yet)
- GREEN gate: `feat(96-01)` commit `50f8da08` — implementation + all 8 tests pass

## Self-Check: PASSED

All required files exist and all commits are present:

- FOUND: apps/backend/tests/unit/test_referral_audit_events.py
- FOUND: apps/backend/app/core/audit.py
- FOUND: apps/backend/app/core/audit_payloads.py
- FOUND: .planning/phases/96-referral-domain-backend/96-01-SUMMARY.md
- FOUND commit: cbd3d77f (test RED)
- FOUND commit: 50f8da08 (feat GREEN)

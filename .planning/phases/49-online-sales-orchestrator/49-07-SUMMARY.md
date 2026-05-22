---
status: complete
plan: 49-07
phase: 49-online-sales-orchestrator
wave: 5
requirements: [PAY-01, PAY-02, PAY-03, PAY-04, PAY-05, PAY-06, PAY-07, PAY-08]
date: 2026-05-22
---

# Plan 49-07 — End-to-end sweep + audit-chain verification + deferred-items log

## Outcome

All 6 ROADMAP success criteria covered by end-to-end tests under
`tests/integration/online_payments/`. Audit-chain semantics (D-49-19,
D-49-20) verified by a dedicated test module. Phase-49 deferred items
documented for downstream phases (50/51/53/v2.0).

## Tasks

1. **Wave-3 deferred fixture refactor** — moved the HTTP-level sell-endpoint
   tests from `tests/modules/online_payments/test_router_sell_endpoints.py`
   (skipped placeholder remains as a pointer) to a new home under
   `tests/integration/online_payments/` with a proper conftest mirroring
   `tests/integration/memberships/conftest.py` (full cookie-jar + login
   machinery; `authed_client_owner` / `authed_client_reception` / DB
   factories; structlog autouse reset preserved).

2. **E2E sell-flow tests (10 tests)** — `test_e2e_sell_flow.py` covers
   SC#1 (membership/pt-package redirect), SC#2 (QR variants), SC#3 (email
   gate 422), SC#4 (return-screen concurrent identical body), SC#5 (DB
   row satisfies CHECK constraints), plus the three classification
   branches: transient (5xx → 503), permanent (non-422 4xx → 502),
   validation (422 → 422 `yookassa_validation_error`).

3. **Audit-chain tests (3 tests)** — `test_e2e_audit_chain.py` verifies
   D-49-19 two-event chain (ROOT `online_payment_initiated` with
   `audit_correlation_id=None`; CHILD `yookassa_payment_created` with
   `audit_correlation_id == online_payments.audit_correlation_id`) plus
   D-49-20 (no audit emission on email-gate failure). Uses verified
   `AuditLog` ORM (`app.core.audit_models`) with direct `.action` +
   dict `.payload` access (W6 invariant — no `json.loads`).

4. **deferred-items.md append** — documented Phase 50/51/53/v2.0
   follow-up markers (reconcile cron D-49-11, `yookassa_call_failed`
   audit event D-49-20, `X-Forwarded-For` toggle, `users.display`
   runtime import D-49-30, `payments.models` runtime import D-49-29,
   v2.0 saved-card columns).

## Key files

Created:
- `apps/backend/tests/integration/online_payments/__init__.py`
- `apps/backend/tests/integration/online_payments/conftest.py` (441 LOC,
  cookie-jar + login machinery, DB factories, structlog reset autouse)
- `apps/backend/tests/integration/online_payments/test_e2e_sell_flow.py`
  (349 LOC, 10 e2e tests)
- `apps/backend/tests/integration/online_payments/test_e2e_audit_chain.py`
  (3 audit-chain tests)
- `.planning/phases/49-online-sales-orchestrator/49-07-SUMMARY.md` (this file)

Modified:
- `.planning/phases/49-online-sales-orchestrator/deferred-items.md`
  (appended Plan 49-07 section + future-phase markers)

## Verification

- **Full Phase 49 test surface:** 106 passed, 1 skipped in 11.81s
  (`tests/modules/online_payments/`, `tests/integrations/yookassa/`,
  `tests/integration/online_payments/`, `tests/integration/test_v17_protocol_slot_parity.py`,
  `tests/integration/test_alembic_0034_online_payments.py`,
  `tests/unit/test_yookassa_protocol_slot_parity.py`).
- **lint-imports:** 3 contracts kept, 0 broken.
- **The 1 skip** is the Wave-3 placeholder `test_router_sell_endpoints.py::
  test_router_sell_endpoints_deferred_to_49_07` — superseded by the
  10-test E2E suite shipped here.

## Success-criteria mapping

| SC | Test |
|---|---|
| SC#1 — POST /memberships/{id}/sell | `test_e2e_sc1_membership_redirect`, `test_e2e_sc1_pt_package_redirect` |
| SC#2 — POST /memberships/{id}/sell-qr | `test_e2e_sc2_membership_qr`, `test_e2e_sc2_pt_package_qr` |
| SC#3 — 422 client_email_required_for_online_payment | `test_e2e_sc3_email_gate_422`, `test_e2e_audit_chain_no_audit_on_email_gate_failure` |
| SC#4 — GET /return static screen | `test_e2e_sc4_return_screen_concurrent_identical_body` + (Plan 49-05) `test_return_screen_constant_time_floor` |
| SC#5 — Alembic 0034 + indexes + CHECKs | `test_e2e_sc5_row_satisfies_check_constraints` + (Plan 49-01) `test_alembic_0034_online_payments.py` |
| SC#6 — 4 v1.7 Protocol slots non-None | (Plan 49-06) `tests/integration/test_v17_protocol_slot_parity.py` |

## Notes

- Plan 49-07 was originally executed by a subagent that hit its rate limit
  mid-work after writing the conftest and 10 e2e tests (uncommitted in
  worktree). Salvaged commit `feat(49-07): E2E sell-flow tests + cookie-jar
  fixtures` was promoted to main, then this plan was completed inline with
  the audit-chain tests, deferred-items append, and this SUMMARY.
- All 6 ROADMAP success criteria are now covered by automated tests; no
  `human_verification` items remain.

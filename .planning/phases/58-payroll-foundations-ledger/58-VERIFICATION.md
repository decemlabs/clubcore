---
phase: 58-payroll-foundations-ledger
verified: 2026-05-25T00:00:00Z
status: human_needed
score: 5/5
overrides_applied: 0
human_verification:
  - test: "Confirm D-PAYROLL-ROUNDING deviation is intentional and acceptable"
    expected: "Developer acknowledges that REQUIREMENTS.md D-PAYROLL-ROUNDING locked `decimal.Decimal + ROUND_HALF_EVEN` but implementation uses `math.ceil` (integer-only, trainer-favorable rounding) as specified by D-58-04 in CONTEXT.md. Decision: accept the deviation or update REQUIREMENTS.md."
    why_human: "Both sources claim to be 'locked decisions'. The CONTEXT.md D-58-04 explicitly chose math.ceil; REQUIREMENTS.md D-PAYROLL-ROUNDING says ROUND_HALF_EVEN. This is a documented conflict between the milestone requirements document and the phase context. Cannot resolve programmatically; needs owner acknowledgment."
  - test: "ROADMAP SC#5 audit event count discrepancy"
    expected: "ROADMAP Phase 58 SC#5 says 'all 6 new LOCKED_AUDIT_EVENTS' but 4 were delivered. The 58-09 SUMMARY.md explains why 4 is correct (preview + list are zero-emit; the two projected additional events were a planning over-estimate). Developer should either update ROADMAP.md SC#5 to say '4' or add a note, so the Phase 61 milestone verifier doesn't flag it again."
    why_human: "The 89-count assertion in test_audit_taxonomy.py passes and is internally consistent. The discrepancy is purely a ROADMAP documentation gap. No code change needed; only roadmap annotation."
---

# Phase 58: Payroll Foundations + Ledger Verification Report

**Phase Goal:** Owner can configure trainer compensation and record payroll accruals with full financial-correctness guarantees
**Verified:** 2026-05-25
**Status:** human_needed (all 5 technical success criteria VERIFIED; 2 items need human acknowledgment — 1 rounding decision conflict, 1 roadmap doc gap)
**Re-verification:** No — initial verification

---

## Goal Achievement

### Observable Truths (Success Criteria)

| # | Truth | Status | Evidence |
|---|-------|--------|---------|
| 1 | Owner can set a trainer's compensation config; trainer with no config returns 422 when payroll is attempted | VERIFIED | `PUT /payroll/trainer-configs/{id}` inserts versioned row; `service.CompConfigMissingError` remapped to 422 by router on preview/accrual paths. 9 tests in `test_payroll_comp_config.py` pass including `test_get_returns_404_when_no_config` and `test_post_accrual_no_config_returns_422`. |
| 2 | Owner can preview payroll with session_count/fixed/commission/total without any row persisted | VERIFIED | `GET /payroll/preview` calls `service.preview_accrual` which delegates to `compute_accrual_components`; zero writes (no `session.add`, `session.commit`, `audit.emit`). `test_preview_zero_persistence` explicitly verifies no rows created. 7 preview tests pass. |
| 3 | Owner can record a payroll accrual (append-only); 409 on duplicate period; rate snapshotted at run time | VERIFIED | `POST /payroll/accruals` calls `repository.insert_accrual_on_conflict` (ON CONFLICT DO NOTHING RETURNING); `PayrollPeriodAlreadyRunError` raised on None → 409. Snapshot columns (commission_pct_bps_snapshot, session_fee_kopecks_snapshot, comp_config_id_snapshot) frozen at INSERT. `test_post_accrual_snapshot_immutability` verifies changing config after accrual doesn't alter snapshot. 12 accrual tests pass. |
| 4 | Owner can mark accrual paid (paid_at + paid_by set); 409 already_paid on second attempt; no unpay | VERIFIED | `POST /accruals/{id}/mark-paid` acquires SELECT FOR UPDATE, sets status/paid_at/paid_by_user_id; `AlreadyPaidError` → 409. No unpay endpoint exists. `test_mark_paid_second_attempt_returns_409` and `test_mark_paid_happy_path` pass. |
| 5 | Accruals list ordered accrued_at DESC; LOCKED_AUDIT_EVENTS + OWNER_ONLY pairs pre-registered; three-way RBAC parity green; PT-package refund appends negative clawback in same UoW | VERIFIED | (a) `list_accruals_for_trainer` uses `.order_by(TrainerPayrollAccrual.accrued_at.desc())`; `test_list_returns_accrued_at_desc_ordering` passes. (b) 4 events added to `LOCKED_AUDIT_EVENTS`; `test_audit_taxonomy.py` count==89 passes. (c) OWNER_ONLY +5 pairs in both permissions.py and can.ts; `test_rbac_parity.py` 4/4 pass including `test_owner_only_count_is_forty`. (d) `get_payroll_clawback_recorder()` called in `refund_pt_package` step 6b before commit; 5 clawback tests pass including same-UoW atomicity. |

**Score:** 5/5 truths verified

---

## Required Artifacts

| Artifact | Expected | Status | Details |
|---------|---------|--------|---------|
| `apps/backend/app/modules/payroll/__init__.py` | Module marker | VERIFIED | Exists |
| `apps/backend/app/modules/payroll/constants.py` | Error codes + subject-kind literal | VERIFIED | `PAYMENT_SUBJECT_KIND_PT_PACKAGE`, `ERROR_COMP_CONFIG_MISSING`, `ERROR_PAYROLL_PERIOD_ALREADY_RUN`, `ERROR_ALREADY_PAID` |
| `apps/backend/app/modules/payroll/models.py` | ORM: TrainerCompConfig + TrainerPayrollAccrual | VERIFIED | Both classes exist with correct columns, CHECK constraints, indexes, partial UNIQUE |
| `apps/backend/app/modules/payroll/schemas.py` | Pydantic schemas: request + response + create | VERIFIED | `TrainerCompConfigRequest`, `TrainerCompConfigResponse`, `PayrollPreviewResponse`, `PayrollAccrualCreate`, `PayrollAccrualResponse` |
| `apps/backend/app/modules/payroll/repository.py` | DB reads + writes for payroll tables | VERIFIED | 8 functions including cross-module raw SQL reads, ON CONFLICT INSERT, SELECT FOR UPDATE, clawback helpers |
| `apps/backend/app/modules/payroll/service.py` | Orchestrator: all 6 PAY operations | VERIFIED | `set_comp_config`, `get_active_comp_config`, `compute_accrual_components`, `preview_accrual`, `run_payroll_period`, `mark_accrual_paid`, `list_accruals`, `record_clawback_for_pt_package_refund` |
| `apps/backend/app/modules/payroll/router.py` | FastAPI router: 6 owner-only endpoints | VERIFIED | PUT/GET trainer-configs, GET preview, GET/POST accruals, POST mark-paid — all with `require_permission` guards |
| `apps/backend/alembic/versions/0041_payroll_foundations.py` | Migration: 2 tables + indexes | VERIFIED | `trainer_comp_configs` + `trainer_payroll_accruals`, partial UNIQUE, 3 indexes, correct `down_revision = "0040_audit_log_report_indexes"` |
| `apps/backend/tests/integration/payroll/` | Integration test suite (42 tests) | VERIFIED | 42/42 pass: comp_config, preview, accruals, mark-paid, list, clawback |
| `apps/backend/app/api/v1/router.py` (edit) | `payroll_router` mounted | VERIFIED | Line 23-24 + line 54 mount under `/payroll` prefix |
| `apps/backend/app/core/permissions.py` (edit) | +5 OWNER_ONLY pairs | VERIFIED | CREATE/COMPENSATION, CREATE/PAYROLL, EDIT/PAYROLL, REFUND/PAYROLL, LIST/PAYROLL added; count comment says 40 |
| `apps/backend/app/core/audit.py` (edit) | +4 LOCKED_AUDIT_EVENTS tuples | VERIFIED | `trainer_comp_config_set`, `payroll_accrual_created`, `payroll_accrual_paid`, `payroll_clawback_recorded` |
| `apps/backend/app/core/audit_payloads.py` (edit) | +4 payload schemas + registry entries | VERIFIED | `TrainerCompConfigSetPayload`, `PayrollAccrualCreatedPayload`, `PayrollAccrualPaidPayload`, `PayrollClawbackRecordedPayload` + 4 registry entries |
| `apps/backend/app/core/dependencies.py` (edit) | `PayrollClawbackRecorder` Protocol slot | VERIFIED | Protocol class at line 1248, `register_payroll_clawback_recorder`, `get_payroll_clawback_recorder` (defensive raise) |
| `apps/backend/app/main.py` (edit) | Slot wired at startup | VERIFIED | `register_payroll_clawback_recorder(payroll_service.record_clawback_for_pt_package_refund)` at lines 253-257 |
| `apps/backend/app/modules/pt_packages/service.py` (edit) | Clawback hook at step 6b | VERIFIED | `get_payroll_clawback_recorder()` called at line 1147 between `pt_package_refunded` audit emit and `session.commit()` |
| `apps/backend/.importlinter` (edit) | `app.modules.payroll` in modules-independent | VERIFIED | Line 32: `app.modules.payroll` present; `lint-imports` output: "3 kept, 0 broken" |
| `apps/admin-web/src/shared/session/can.ts` (edit) | +5 OWNER_ONLY entries | VERIFIED | Lines 72-76: `create/compensation`, `create/payroll`, `edit/payroll`, `refund/payroll`, `list/payroll` |

---

## Key Link Verification

| From | To | Via | Status | Details |
|-----|-----|-----|--------|---------|
| `router.py` | `service.py` | Direct import + function calls | VERIFIED | All 6 endpoint handlers call corresponding service functions |
| `service.py` | `repository.py` | Direct import + async calls | VERIFIED | All service functions delegate reads/writes to repository |
| `service.py` | `audit.emit()` | `from app.core import audit` | VERIFIED | Literal event strings used; AST gate test passes |
| `router.py` | `v1/router.py` | `include_router` | VERIFIED | `payroll_router` mounted at `/payroll` prefix; `create_app()` returns 6 payroll routes |
| `pt_packages.service.refund_pt_package` | `payroll.service.record_clawback_for_pt_package_refund` | `get_payroll_clawback_recorder()` Protocol slot | VERIFIED | Hook at line 1147; zero direct imports from payroll; `lint-imports` clean |
| `app.main.create_app` | `payroll.service.record_clawback_for_pt_package_refund` | `register_payroll_clawback_recorder` | VERIFIED | Wired at lines 253-257 in create_app() |
| Backend `permissions.py` | Frontend `can.ts` | Three-way parity test | VERIFIED | `test_rbac_parity.py` 4/4 pass; OWNER_ONLY count = 40 on both sides |

---

## Data-Flow Trace (Level 4)

| Artifact | Data Variable | Source | Produces Real Data | Status |
|---------|--------------|--------|-------------------|--------|
| `preview_accrual` (PAY-02) | `session_count`, `commission_kopecks`, `fixed_kopecks`, `total_kopecks` | `repository.fetch_trainer_session_revenue` → raw SQL cross-module query against pt_sessions + payments | Yes — live DB query | FLOWING |
| `run_payroll_period` (PAY-03) | `accrual_kopecks`, snapshot columns | Same `fetch_trainer_session_revenue` + `resolve_active_comp_config` | Yes — live DB queries; frozen at INSERT | FLOWING |
| `list_accruals` (PAY-05) | `rows`, `total` | `list_accruals_for_trainer` ORM SELECT + `count_accruals` COUNT | Yes — live DB queries | FLOWING |
| `record_clawback_for_pt_package_refund` (PAY-06) | `original` paid accrual | `find_paid_accrual_covering_refund` raw SQL text() | Yes — live DB query; returns None when no paid accrual | FLOWING |

---

## Behavioral Spot-Checks

| Behavior | Command | Result | Status |
|---------|---------|--------|--------|
| Payroll endpoints accessible | `python -c "from app.main import create_app; app = create_app(); routes = [r.path for r in app.routes if hasattr(r, 'path')]; payroll = [r for r in routes if 'payroll' in r]; print(len(payroll))"` | 6 routes | PASS |
| 42 payroll integration tests | `uv run pytest tests/integration/payroll/ -v` | 42/42 passed in 8.69s | PASS |
| RBAC parity (three-way) | `uv run pytest tests/integration/test_rbac_parity.py -v` | 4/4 passed | PASS |
| Audit taxonomy AST gate | `uv run pytest tests/unit/test_audit_taxonomy.py -v` | 7/7 passed; count == 89 | PASS |
| Import-linter | `uv run lint-imports` | 3 contracts kept, 0 broken | PASS |
| Ruff | `uv run ruff check app/modules/payroll/` | All checks passed | PASS |
| Mypy | `uv run mypy app/modules/payroll/ app/core/dependencies.py app/modules/pt_packages/service.py` | Clean (no output) | PASS |

---

## Requirements Coverage

| Requirement | Description | Status | Evidence |
|------------|-------------|--------|---------|
| PAY-01 | Owner sets trainer comp model (commission_pct_bps / session_fee_kopecks, both nullable; both NULL = no payroll) | SATISFIED | PUT/GET `/payroll/trainer-configs/{id}`; INSERT-only versioned; both-NULL raises 422 at accrual time |
| PAY-02 | Owner gets read-only preview (session_count, fixed_kopecks, commission_kopecks, total_kopecks) without persistence | SATISFIED | GET `/payroll/preview`; `preview_accrual` calls shared `compute_accrual_components`; zero writes verified by test |
| PAY-03 | Owner records append-only accrual in `trainer_payroll_accruals`; UNIQUE (trainer_id, period_start, period_end) WHERE clawback_of_accrual_id IS NULL; 409 on duplicate; 422 when no config | SATISFIED | ON CONFLICT DO NOTHING RETURNING; partial UNIQUE index; `PayrollPeriodAlreadyRunError` and `CompConfigMissingError` mapped correctly |
| PAY-04 | Owner marks accrual paid (paid_at + paid_by_user_id); 409 already_paid; no unpay | SATISFIED | SELECT FOR UPDATE + status guard + single mutation; no unpay endpoint |
| PAY-05 | Owner lists accruals ordered accrued_at DESC with paid/unpaid status; `{items, total, page, pageSize}` | SATISFIED | `list_accruals_for_trainer` + `count_accruals`; 8 list tests including ordering, pagination, clawback visibility |
| PAY-06 | PT-package refund post-dating paid accrual appends negative clawback in same UoW | SATISFIED | Protocol slot fired at step 6b in `refund_pt_package`; INSERT negative row with clawback FKs; 5 clawback tests pass including same-UoW atomicity |

---

## Anti-Patterns Found

| File | Line | Pattern | Severity | Impact |
|-----|-----|---------|---------|--------|
| None found | — | — | — | All payroll files are substantive implementations with no TBD/FIXME/XXX, no empty returns, no stub implementations |

---

## Findings Requiring Human Decision

### 1. Rounding Implementation Diverges from REQUIREMENTS.md Locked Decision

**Test:** Review the rounding algorithm and confirm the deviation is intentional.

**Background:** Two documents specify the rounding algorithm for payroll commission, and they conflict:

- `REQUIREMENTS.md` Locked Decisions, `D-PAYROLL-ROUNDING`: specifies `decimal.Decimal + ROUND_HALF_EVEN` (banker's rounding), no float.
- `58-CONTEXT.md` `D-58-04`: specifies `math.ceil` rounding in the trainer's favor (integer-only arithmetic via basis points).

**Shipped implementation** (`service.py:215`):
```python
commission_kopecks: int = math.ceil(revenue_kopecks * bps / 10000) if bps is not None else 0
```

This follows D-58-04 (math.ceil, integer-only). It does NOT use `decimal.Decimal` or `ROUND_HALF_EVEN`.

**Why this matters:** The two approaches produce different results when `revenue_kopecks * bps` is not evenly divisible by 10000. For example, 100001 kopecks × 1000 bps / 10000 = 10000.1 → `math.ceil` gives 10001 (trainer gets extra 1 kopeck); `ROUND_HALF_EVEN` would give 10000. The difference is small per-transaction but accumulates over time and changes the financial semantics (trainer-favorable vs. neutral rounding).

**What is internally consistent:** The preview, accrual creation, and clawback all use the SAME `compute_accrual_components` helper — there is no recompute drift. The choice of algorithm is applied uniformly.

**Expected:** Developer should either (a) accept D-58-04 as the governing decision and add a note to REQUIREMENTS.md correcting D-PAYROLL-ROUNDING, or (b) decide that D-PAYROLL-ROUNDING must be enforced and create a gap closure plan to change the implementation.

**Why human:** Cannot determine which "locked decision" is authoritative; this is a product/financial policy decision.

### 2. ROADMAP SC#5 Documents "6 new LOCKED_AUDIT_EVENTS" — 4 Were Delivered

**Test:** Confirm the ROADMAP language should be updated or annotated.

**Background:** ROADMAP Phase 58 SC#5 says: "all 6 new LOCKED_AUDIT_EVENTS and new OWNER_ONLY pairs (PAYROLL + COMPENSATION) are pre-registered".

**Delivered:** 4 LOCKED_AUDIT_EVENTS (`trainer_comp_config_set`, `payroll_accrual_created`, `payroll_accrual_paid`, `payroll_clawback_recorded`). The 58-09 SUMMARY.md documents the reconciliation: the 2 projected events were a planning over-estimate. Preview (PAY-02) and list (PAY-05) are read-only — they emit nothing. `test_audit_taxonomy.py` correctly asserts count = 89 (not 91).

**What is internally consistent:** The 4 events match what the code actually emits. No phantom events were registered. The `test_locked_audit_events_has_expected_count` test asserts 89 and passes.

**Expected:** Developer should update ROADMAP.md Phase 58 SC#5 to say "4 new LOCKED_AUDIT_EVENTS" so Phase 61 milestone verification doesn't re-raise this gap.

**Why human:** Requires a ROADMAP.md edit decision — annotating an over-estimate in a shipped phase. No code change needed.

---

## Gaps Summary

No technical gaps. All 5 success criteria are verified by working code and 42 passing integration tests. The two items requiring human review are:

1. A documented conflict between `REQUIREMENTS.md D-PAYROLL-ROUNDING` (banker's rounding) and `CONTEXT.md D-58-04` (math.ceil, trainer-favorable). The shipped code follows D-58-04 and is internally consistent, but REQUIREMENTS.md has not been corrected.

2. A ROADMAP SC#5 word count ("6 new LOCKED_AUDIT_EVENTS") that doesn't match the 4 shipped and correctly-asserted events. The 58-09 SUMMARY.md explains the discrepancy; the ROADMAP has not been updated.

Neither is a code defect. Both require a developer decision to close.

---

*Verified: 2026-05-25*
*Verifier: Claude (gsd-verifier)*

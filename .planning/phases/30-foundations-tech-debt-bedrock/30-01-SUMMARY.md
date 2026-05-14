---
phase: 30-foundations-tech-debt-bedrock
plan: 01
subsystem: backend/audit
tags:
  - audit
  - backend
  - pydantic
  - bedrock
  - infra-17
  - infra-23
dependency_graph:
  requires:
    - app.core.audit  (Phase 15 lock)
    - app.core.audit_models  (Phase 8)
    - pydantic v2
  provides:
    - app.core.audit_payloads.AUDIT_PAYLOAD_SCHEMAS (17 schemas)
    - app.core.audit.LOCKED_AUDIT_EVENTS (extended by 17 v1.4 tuples)
    - audit.emit() payload-shape validation gate (D-30-03)
  affects:
    - Phases 31/32/33/34 (consume locked events + validated payload shapes)
    - Phase 36 milestone audit (count consistency 51/17 across docs+impl)
tech_stack:
  added:
    - none (uses existing pydantic v2)
  patterns:
    - locked-registry tuple-key (event, resource_type)
    - D-09 hard-fail discipline (no graceful degradation)
    - Pydantic v2 extra="forbid" mirror of AuditEventNotLockedError shape
key_files:
  created:
    - apps/backend/app/core/audit_payloads.py
  modified:
    - apps/backend/app/core/audit.py
    - apps/backend/tests/unit/test_audit_taxonomy.py
    - .planning/REQUIREMENTS.md
    - .planning/ROADMAP.md
decisions:
  - D-30-01 — Pydantic v2 BaseModel + ConfigDict(extra="forbid") (strict-only)
  - D-30-02 — scope = ONLY new 17 v1.4 events (existing 34 logical / 36 physical remain free-form)
  - D-30-03 — registry lives in audit_payloads.py; emit() validates after locked-set check, before structlog/DB
  - D-30-04 — payment_row_hash field with pattern ^sha256:[0-9a-f]{64}$ (canonicalization helper deferred to Phase 32)
metrics:
  duration: "~25 min"
  completed: 2026-05-14
  tasks_total: 3
  tasks_completed: 3
  commits:
    - 00dc619  feat(30-01): add audit_payloads.py with 17 Pydantic v2 schemas (INFRA-23)
    - 355c9e9  feat(30-01): extend LOCKED_AUDIT_EVENTS 36→53 + wire payload validation (INFRA-17)
    - 8413cc6  docs(30-01): reconcile INFRA-17/ROADMAP SC #1 to 51 entries / 17 new
---

# Phase 30 Plan 01: Audit Bedrock Summary

**One-liner:** Pre-registered 17 v1.4 audit events in `LOCKED_AUDIT_EVENTS` and locked their payload shapes via 17 Pydantic v2 schemas with `extra="forbid"`, validated by `audit.emit()` before structlog/DB writes — mirrors D-09 hard-fail discipline and preserves `core ⊥ modules` import-linter contract.

## What Was Built

### 1. New file `apps/backend/app/core/audit_payloads.py` (307 lines)

17 Pydantic v2 `BaseModel` schemas, each with `model_config = ConfigDict(extra="forbid")`:

**Trainers (Phase 31 TRN-07):**
- `TrainerCreatedPayload` — `{trainer_id, full_name, phone}`
- `TrainerUpdatedPayload` — `{trainer_id, changed_fields}`
- `TrainerDeactivatedPayload` — `{trainer_id}`
- `TrainerReactivatedPayload` — `{trainer_id}`

**Payments + refund + membership refund (Phase 32 PAY-10 / REF-07):**
- `PaymentRecordedPayload` — verbatim PAY-10 fields (PAY-10) **+ payment_row_hash with pattern `^sha256:[0-9a-f]{64}$`** (D-30-04)
- `RefundIssuedPayload` — negative amount + refund_of_payment_id + `payment_row_hash` of ORIGINAL row (D-30-04)
- `MembershipRefundedPayload` — `{membership_id, client_id, refund_payment_id, reason}`

**PT-package plans (Phase 33 PT-03):**
- `PtPackagePlanCreatedPayload` — `{plan_id, name, session_count, price_kopecks, validity_days}`
- `PtPackagePlanUpdatedPayload` — `{plan_id, changed_fields}`
- `PtPackagePlanArchivedPayload` — `{plan_id}`

**PT-package instances (Phase 33 PT-13):**
- `PtPackageSoldPayload` — `{pt_package_id, client_id, plan_id, …snapshots, payment_id}`
- `PtPackageCancelledPayload` — `{pt_package_id, client_id, cancellation_reason}`
- `PtPackageRefundedPayload` — `{pt_package_id, client_id, refund_payment_id, reason}`
- `PtPackageExhaustedPayload` — `{pt_package_id, client_id}`
- `PtPackageExpiredPayload` — `{pt_package_id, client_id, end_date}`

**PT-sessions (Phase 34 PT-21):**
- `PtSessionRecordedPayload` — full PT-session snapshot incl. `trainer_name_snapshot` (B-05)
- `PtSessionCancelledPayload` — `{pt_session_id, …, sessions_remaining_after, package_reactivated}`

**Registry:** `AUDIT_PAYLOAD_SCHEMAS: dict[tuple[str, str], type[BaseModel]]` with exactly **17 entries** keyed by `(event, resource_type)` — mirrors `LOCKED_AUDIT_EVENTS` tuple-key shape so the lookup at the emit-callsite is one `.get(...)`.

**Imports:** `from uuid import UUID` + `from pydantic import BaseModel, ConfigDict, Field`. NO `app.modules.*` imports (importlinter `core-not-depend-on-modules` contract preserved).

### 2. `apps/backend/app/core/audit.py` extended

**LOCKED_AUDIT_EVENTS:** added 17 new `(event, resource_type)` tuples grouped by phase under comment `# v1.4 (Phase 30 lock — emitted in Phases 31/32/33/34 per INFRA-17 / B-03 / D-30-02)`. Verbatim list:

```python
# Trainers lifecycle (Phase 31 TRN-07):
("trainer_created", "trainer"),
("trainer_updated", "trainer"),
("trainer_deactivated", "trainer"),
("trainer_reactivated", "trainer"),
# Payments + refund (Phase 32 PAY-10 / REF-07):
("payment_recorded", "payment"),
("refund_issued", "payment"),
("membership_refunded", "membership"),
# PT-package plans (Phase 33 PT-03):
("pt_package_plan_created", "pt_package_plan"),
("pt_package_plan_updated", "pt_package_plan"),
("pt_package_plan_archived", "pt_package_plan"),
# PT-package instances (Phase 33 PT-13):
("pt_package_sold", "pt_package"),
("pt_package_cancelled", "pt_package"),
("pt_package_refunded", "pt_package"),
("pt_package_exhausted", "pt_package"),
("pt_package_expired", "pt_package"),
# PT-sessions (Phase 34 PT-21):
("pt_session_recorded", "pt_session"),
("pt_session_cancelled", "pt_session"),
```

**emit() body:** between locked-set check and structlog/DB write, inserted:

```python
schema = AUDIT_PAYLOAD_SCHEMAS.get((event, resource_type))
if schema is not None:
    schema.model_validate(payload)
```

`pydantic.ValidationError` propagates unchanged — D-09 hard-fail discipline mirrors `AuditEventNotLockedError` shape; no try/except, no DEBUG-only assert.

**Docstring:** extended with v1.4 event block + NOTE clarifying the **logical** count `34 → 51` vs **physical** frozenset size `36 → 53` (the v1.1 `session_revoked` event has two `(event, resource_type)` variants per D-23-10).

**emit() Raises section:** added `pydantic.ValidationError` entry documenting the new validation gate contract.

### 3. Upstream docs reconciled (Task 3 — closes BLOCKER #2)

**REQUIREMENTS.md INFRA-17 header diff (count fragment only):**
```diff
- Extend `LOCKED_AUDIT_EVENTS` frozenset from 34 → 50 entries (16 new): `trainer_created`, …
+ Extend `LOCKED_AUDIT_EVENTS` frozenset from 34 → 51 entries (17 new): `trainer_created`, …
```

**REQUIREMENTS.md INFRA-23 wording diff:**
```diff
- Lock canonical payload schemas for the 16 new audit events in `audit_payloads.py`
+ Lock canonical payload schemas for the 17 new audit events in `audit_payloads.py`
```

**ROADMAP.md Phase 30 inline summary card diff:**
```diff
- `LOCKED_AUDIT_EVENTS` 34→50, Resource/OWNER_ONLY extension, …
+ `LOCKED_AUDIT_EVENTS` 34→51, Resource/OWNER_ONLY extension, …
```

**ROADMAP.md Phase 30 §Success Criteria #1 diff:**
```diff
-   1. `LOCKED_AUDIT_EVENTS` frozenset содержит 50 entries (16 новых v1.4 событий — …
+   1. `LOCKED_AUDIT_EVENTS` frozenset содержит 51 entries (17 новых v1.4 событий — …
```

**Verbatim enumerated event list preserved character-for-character** in both files (17 names: `trainer_created` … `pt_session_cancelled`). v1.3 Phase 24 historical retrospective sections in both files **UNTOUCHED**.

**Grep gate output:**
```
$ grep -nE "50 entries|16 (new|нов)" .planning/REQUIREMENTS.md .planning/ROADMAP.md | grep -v "v1\.3\|Phase 24" | wc -l
0

$ grep -c "51 entries" .planning/REQUIREMENTS.md  →  1 (≥1 ✓)
$ grep -c "51 entries" .planning/ROADMAP.md       →  1 (≥1 ✓)
$ grep -cE "17 (new|нов)" .planning/{REQUIREMENTS,ROADMAP}.md → 2 + 1 = 3 (≥2 ✓)
```

**Rationale for 17-vs-16 reconciliation:** INFRA-17 enumerated 17 distinct event names; the header gloss "16 new"/"50 entries" was an arithmetic typo. Per D-30-02 the **enumerated list is the binding source of truth**, so reconciliation followed the enumeration rather than truncate it. The reconciliation lands in the same atomic commit-series as the implementation, preventing Phase 36 milestone audit from failing on count mismatch.

## payment_row_hash canonicalization status

- **In Plan 01 (this plan):** field constraint locked in `PaymentRecordedPayload` and `RefundIssuedPayload` as `str = Field(pattern=r"^sha256:[0-9a-f]{64}$")`. Schema docstrings document the expected `"sha256:<64-hex>"` prefix shape.
- **Deferred to Plan 03 OR Phase 32:** actual canonicalization helper module `apps/backend/app/core/audit_hash.py` exposing `def payment_row_hash(row: dict[str, Any]) -> str` with algorithm `hashlib.sha256(json.dumps(row, sort_keys=True, separators=(",", ":"), default=str).encode("utf-8")).hexdigest()` prefixed `"sha256:"`. Plan 03 will confirm location (`core/` vs `modules/payments/`) when wiring the actual call-graph.

## Decisions Made

- **D-30-01 (locked at planning):** strict Pydantic v2 with `extra="forbid"`. Verified: extra-key payload raises `ValidationError`; missing-required raises `ValidationError`.
- **D-30-02 (locked at planning):** scope-only-new-17. Verified: `audit.emit('login_success', ..., free_form='anything', goes_here=42)` still passes (existing v1.1 event has no schema in registry → free-form preserved).
- **D-30-03 (locked at planning):** registry in separate file `audit_payloads.py`; `audit.py` imports and calls `schema.model_validate(payload)` AFTER locked-set check, BEFORE structlog/DB write. Verified: ordering preserved at lines 218-228 of audit.py post-edit.
- **D-30-04 (locked at planning + this plan):** `payment_row_hash` field constraint `^sha256:[0-9a-f]{64}$`. Canonicalization helper deferred to Phase 32 / Plan 03.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] Updated `test_locked_audit_events_has_expected_count` count assertion**
- **Found during:** Task 2 (verification step — pytest run after extending LOCKED_AUDIT_EVENTS).
- **Issue:** `apps/backend/tests/unit/test_audit_taxonomy.py:176` hardcoded `assert len(LOCKED_AUDIT_EVENTS) == 36`. After Task 2 added 17 v1.4 tuples the frozenset size grew to 53, so the existing sanity-belt test failed.
- **Why this is Rule 1 (not Rule 4 / architectural):** the existing sanity-belt test was authored Phase 15/24 and explicitly enumerates v1.1+v1.2+v1.3 totals in its docstring as "expected drift detection" — extending the count for v1.4 is the documented maintenance pattern (the test docstring says "see 15-03-SUMMARY.md / 24-01-SUMMARY.md"). Phase 30 is the natural extension point per B-03 pre-registration discipline; the test's role does not change.
- **Fix:** updated literal `36 → 53`, extended docstring with a v1.4 paragraph explaining the new 17 pairs + a NOTE clarifying the logical (51) vs physical (53) discrepancy from D-23-10 session_revoked variant.
- **Files modified:** `apps/backend/tests/unit/test_audit_taxonomy.py`
- **Commit:** `355c9e9` (folded into Task 2 atomic commit per BLOCKER #2 single-commit invariant).

### Auto-fixed Lint Issues (sub-Rule-1, mechanical)

**2. [Lint] EN-dash → ASCII hyphen in audit_payloads.py docstring**
- **Found during:** Task 1 (`ruff check`).
- **Issue:** initial docstring used EN DASH `–` in `v1.1–v1.3` — flagged `RUF002`.
- **Fix:** replaced with ASCII `-`. Note `audit.py` itself uses EM DASH `—` (different rule) which ruff does not flag in that codebase.
- **Files modified:** `apps/backend/app/core/audit_payloads.py` (pre-commit fix).

**3. [Lint] isort blank line after imports**
- **Found during:** Task 1 (`ruff check --fix`).
- **Issue:** I001 — import block missing the blank-line-after grouping convention.
- **Fix:** `ruff check --fix` auto-corrected (collapsed redundant blank line).
- **Files modified:** `apps/backend/app/core/audit_payloads.py` (pre-commit fix).

### Architectural / Rule 4 changes

None. All deviations were Rule 1 mechanical maintenance of existing-test invariants and lint adherence.

## Authentication Gates

None — Plan 01 is pure source-code modification (no network, no DB connection, no third-party CLI auth required).

## Verification Evidence

**Phase-level acceptance gates (all green):**

```bash
$ cd apps/backend && uv run mypy --strict app/core/
Success: no issues found in 17 source files

$ cd apps/backend && uv run ruff check app/core/
All checks passed!

$ cd apps/backend && uv run lint-imports
Contracts: 3 kept, 0 broken.
  core must not import modules        KEPT
  modules cannot import each other    KEPT
  integrations must not import modules KEPT

$ cd apps/backend && uv run pytest tests/unit/test_audit_taxonomy.py -q
4 passed in 0.08s
```

**Functional smoke (audit.emit end-to-end):**

```
1. emit('fake_event', resource_type='fake')                      → AuditEventNotLockedError ✓
2. emit('trainer_created', resource_type='trainer', valid…)      → passes (logs + would DB-write) ✓
3. emit('trainer_created', resource_type='trainer', bogus='x')   → ValidationError ✓
4. emit('login_success', resource_type='session', anything=…)    → passes (v1.1 free-form preserved) ✓
5. emit('payment_recorded', …, payment_row_hash='not-valid')     → ValidationError (pattern miss) ✓
```

**BLOCKER #2 doc-reconciliation gate:**
- `grep -E "50 entries|16 (new|нов)" .planning/{REQUIREMENTS,ROADMAP}.md | grep -v "v1\.3\|Phase 24" | wc -l` → `0` ✓
- `grep -c "51 entries" .planning/REQUIREMENTS.md` → `1` (≥1) ✓
- `grep -c "51 entries" .planning/ROADMAP.md` → `1` (≥1) ✓
- `grep -cE "17 (new|нов)" .planning/{REQUIREMENTS,ROADMAP}.md` summed → `3` (≥2) ✓

## Threat Flags

None. All Phase 30 Plan 01 changes operate strictly inside the existing audit trust-boundary (caller → emit → DB) without introducing new network endpoints, auth paths, file access patterns, or schema changes at trust boundaries. The threat register T-30-01-01..07 mitigations from the plan are all implemented:
- T-30-01-01 (Tampering of LOCKED_AUDIT_EVENTS): frozenset immutability preserved; AST literal-string gate test (4/4) still green.
- T-30-01-02 (Tampering of payload kwargs): Pydantic `extra="forbid"` validation gate added at emit() — verified by smoke case 3 + 5.
- T-30-01-03 (Information Disclosure via payment_row_hash): SHA-256 forensic identifier, field pattern locked.
- T-30-01-04 (Repudiation via emit-callsite drift): co-transactional DB INSERT unchanged; v1.1-v1.3 back-compat preserved.
- T-30-01-05 (DoS via model_validate cost): acceptable — microsecond-scale; emit is not a hot path.
- T-30-01-06 (EoP via app.modules.* import): importlinter contract green; no app.modules imports in audit_payloads.py.
- T-30-01-07 (Repudiation via doc-vs-impl count drift): Task 3 reconciliation gate green (51/17 across both files).

## Known Stubs

None. All 17 schemas have substantive fields derived from REQUIREMENTS.md (PAY-10 verbatim) or REQ-description inference (D-30-04 / Claude's Discretion per CONTEXT.md). `payment_row_hash` canonicalization **helper** is deferred to Plan 03 / Phase 32, but the **schema constraint** is fully locked here — downstream callsites cannot bypass the `^sha256:[0-9a-f]{64}$` pattern.

## Files Modified Summary

| File | Status | Purpose |
|------|--------|---------|
| `apps/backend/app/core/audit_payloads.py` | created (+307 lines) | 17 Pydantic v2 schemas + AUDIT_PAYLOAD_SCHEMAS registry |
| `apps/backend/app/core/audit.py` | modified (+49 lines) | LOCKED_AUDIT_EVENTS +17 tuples + emit() schema validation + docstring v1.4 block |
| `apps/backend/tests/unit/test_audit_taxonomy.py` | modified (+10/-4 lines) | Updated expected-count sanity belt 36→53 (Rule 1 auto-fix) |
| `.planning/REQUIREMENTS.md` | modified (2 lines) | INFRA-17 header: 50→51 / 16→17; INFRA-23 wording: 16→17 |
| `.planning/ROADMAP.md` | modified (2 lines) | Phase 30 inline summary: 34→51; SC #1: 50→51, 16→17 |

## Commits

| Task | Hash | Type | Description |
|------|------|------|-------------|
| 1 | `00dc619` | feat | add audit_payloads.py with 17 Pydantic v2 schemas (INFRA-23) |
| 2 | `355c9e9` | feat | extend LOCKED_AUDIT_EVENTS 36→53 + wire payload validation (INFRA-17) |
| 3 | `8413cc6` | docs | reconcile INFRA-17/ROADMAP SC #1 to 51 entries / 17 new |

## Self-Check: PASSED

- File `apps/backend/app/core/audit_payloads.py` — FOUND
- File `apps/backend/app/core/audit.py` — FOUND (modified)
- File `apps/backend/tests/unit/test_audit_taxonomy.py` — FOUND (modified)
- File `.planning/REQUIREMENTS.md` — FOUND (modified)
- File `.planning/ROADMAP.md` — FOUND (modified)
- Commit `00dc619` — FOUND in git log
- Commit `355c9e9` — FOUND in git log
- Commit `8413cc6` — FOUND in git log
- All 13 phase-level success criteria asserted by plan — verified green (see Verification Evidence)

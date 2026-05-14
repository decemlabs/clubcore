---
phase: 30-foundations-tech-debt-bedrock
verified: 2026-05-14T12:58:17Z
status: passed
score: 5/5 must-haves verified
overrides_applied: 0
---

# Phase 30: Foundations & Tech-Debt Bedrock — Verification Report

**Phase Goal:** Расширить audit/RBAC/architectural bedrock и закрыть deferred v1.3 mock-parity gap — чтобы все последующие phases (31..35) могли эмитить новые locked события, ссылаться на новые `Resource` значения, и опираться на enforced append-only discipline для payments.

**Verified:** 2026-05-14T12:58:17Z
**Status:** passed
**Re-verification:** No — initial verification

## Goal Achievement

### Observable Truths (5 Success Criteria from ROADMAP Phase 30)

| # | Truth (Success Criterion) | Status | Evidence |
|---|---------------------------|--------|----------|
| 1 | `LOCKED_AUDIT_EVENTS` содержит 51 logical entries (17 новых); AST literal-string gate ещё блокирует ad-hoc строки; canonical payload schemas зафиксированы, включая `payment_row_hash` (SHA-256) | VERIFIED | All 17 new (event, resource_type) pairs present in LOCKED_AUDIT_EVENTS (physical size 53 — 36+17, two `session_revoked` variants per D-23-10); AUDIT_PAYLOAD_SCHEMAS dict has 17 entries; `PaymentRecordedPayload.payment_row_hash` carries `pattern='^sha256:[0-9a-f]{64}$'`; emit() calls `schema.model_validate(payload)` at audit.py:259 after locked-set check; AST taxonomy gate green (193 backend unit tests passed). Smoke: unknown event → AuditEventNotLockedError; extra-key payload → ValidationError; v1.1 free-form preserved. |
| 2 | `Resource` enum +5; `OWNER_ONLY` 15→26; reception retains 6 pairs; three-way byte-paritet CI green | VERIFIED | Resource enum exposes all 5 v1.4 wire values (`trainers`, `payments`, `pt-package-plans`, `pt-packages`, `pt-sessions`); `len(OWNER_ONLY)==26`; Action enum unchanged at 7 values (no Action.LIST added — INFRA-18 honoured); all 6 reception-retained pairs verified NOT in OWNER_ONLY (`{VIEW,TRAINERS}`, `{CREATE,PAYMENTS}`, `{REFUND,MEMBERSHIPS}`, `{CREATE,PT_PACKAGES}`, `{REFUND,PT_PACKAGES}`, `{CREATE,PT_SESSIONS}`); admin-web `registry.ts` Resource union mirrors backend literals byte-for-byte; admin-web `can.ts` OWNER_ONLY length 26; can.test.ts 9 tests pass (3 new INFRA-19 specs); `pnpm typecheck` clean. |
| 3 | `.importlinter` `modules-independent` контракт расширен на trainers, payments, pt_packages; три top-level контракта остаются unchanged по форме; `lint-imports` зелёный | VERIFIED | `.importlinter` contains all three module entries (count=3 grep hits); `^\[importlinter:contract:` count = exactly 3 (shape invariant preserved); `uv run lint-imports` reports `Contracts: 3 kept, 0 broken` (`core ⊥ modules` KEPT, `modules independent` KEPT, `integrations ⊥ modules` KEPT); analyzed 80 files, 157 dependencies. |
| 4 | SVC001 walker scope covers payments/trainers/pt_packages service.py; new append-only AST walker forbids UPDATE/DELETE against `payments` table; negative-test fixture fails CI | VERIFIED | `_INSPECTED_SERVICES` tuple grew 3→6 (grep count 6 for new service constants); `tests/unit/test_payments_appendonly.py` exists with 7 test cases — all pass: live walker against real codebase reports 0 offenders, scope-sanity passes, 4 parametrized violation fixtures caught (update / delete / on_conflict_do_update / session.delete), 1 clean-INSERT positive control passes (no false-positive). Walker uses import-tracking via `_resolve_payment_binding` (not string match). All 6 placeholder files exist (payments/{__init__,service,models}, pt_packages/{__init__,service}, trainers/service). Alembic versions count UNCHANGED (10 BEFORE = 10 AFTER per D-30-10); env.py confirmed MANUAL discovery (4 explicit module imports — payments NOT in list). |
| 5 | mock `memberships.list()` фильтрует по `query.status` в expiring branch; «Заморожен» pill идентичен mock↔http; 1-2 mock-parity тестов добавлены | VERIFIED | `mock/memberships.ts` contains `query.status ?? 'active'` (1 hit); hardcoded `m.status === 'active' && m.endDate >= todayStr` literal removed (0 hits); `wantedStatus` declared + used; in-code DEBT-05 rationale comment present (covers WARNING #3 semantic-mismatch context); `memberships.read.test.ts` has 4 DEBT-05 grep hits (2 new `it()` blocks + comments); both new specs pass via vitest (`list applies query.status inside the expiring branch (DEBT-05)` and frozen-pill canary); 18/18 file tests pass, 27/27 admin-web targeted run pass. |

**Score:** 5/5 truths verified

### Required Artifacts

| Artifact | Expected | Status | Details |
|----------|----------|--------|---------|
| `apps/backend/app/core/audit.py` | LOCKED_AUDIT_EVENTS +17 + emit() validation | VERIFIED | Imports `AUDIT_PAYLOAD_SCHEMAS` (audit.py:109); calls `schema.model_validate(payload)` (audit.py:259); all 17 v1.4 tuples present |
| `apps/backend/app/core/audit_payloads.py` | 17 Pydantic v2 schemas + registry | VERIFIED | Module exists; AUDIT_PAYLOAD_SCHEMAS has 17 entries; PaymentRecordedPayload + RefundIssuedPayload carry `payment_row_hash` with sha256 pattern; no `app.modules.*` imports (importlinter clean) |
| `apps/backend/app/core/permissions.py` | Resource +5; OWNER_ONLY = 26 | VERIFIED | All 5 v1.4 Resource members with correct kebab `.value` strings; OWNER_ONLY frozenset length = 26; Action unchanged at 7 |
| `apps/backend/tests/unit/test_permissions.py` | extended parity test | VERIFIED | 175 tests pass (per 30-02-SUMMARY); `test_reception_retains_v1_4_rights` added; `test_owner_only_has_exactly_twenty_six_entries` asserts literal 26 |
| `apps/admin-web/src/shared/session/can.ts` | OWNER_ONLY 26 entries | VERIFIED | 11 grep hits for v1.4 (action, resource) pairs; admin-web vitest 9/9 can.test.ts tests pass |
| `apps/admin-web/src/shared/session/registry.ts` | Resource union +5 | VERIFIED | 5 grep hits for v1.4 string literals; routeRegistry + navKey unchanged (D-30-09) |
| `apps/admin-web/src/shared/session/can.test.ts` | parity tests extended | VERIFIED | 3 new vitest specs (length tripwire + positive spot-check + negative reception-retained); all pass |
| `apps/backend/.importlinter` | modules-independent +payments +pt_packages | VERIFIED | 3 grep hits for `app.modules.{trainers,payments,pt_packages}`; 3 top-level contracts unchanged in shape; `lint-imports` reports 3 kept, 0 broken |
| `apps/backend/tests/unit/test_service_commit_gate.py` | _INSPECTED_SERVICES 3→6 | VERIFIED | 6 grep hits for new service constants |
| `apps/backend/tests/unit/test_payments_appendonly.py` | new AST walker | VERIFIED | File exists; 7 test cases all pass; uses `_resolve_payment_binding` import-tracking (not string match); INSERT-only policy enforced (D-30-08) |
| `apps/backend/tests/unit/fixtures/*.py` | 5 fixtures + __init__.py marker | VERIFIED | All 6 files present; 4 violations caught by walker; 1 clean-insert passes |
| `apps/backend/app/modules/payments/{__init__,service,models}.py` | placeholders | VERIFIED | All 3 files exist; `class Payment` parseable by ast.parse; Alembic env.py confirms MANUAL discovery (Payment NOT in Base.metadata at migration time) |
| `apps/backend/app/modules/pt_packages/{__init__,service}.py` | placeholders | VERIFIED | Both files exist |
| `apps/backend/app/modules/trainers/service.py` | placeholder | VERIFIED | File exists |
| `apps/admin-web/src/shared/api/services/mock/memberships.ts` | DEBT-05 fix + comment | VERIFIED | `query.status ?? 'active'` present; hardcoded literal gone; DEBT-05 + "respect query.status" comment grep hits ≥ 1 each |
| `apps/admin-web/src/shared/api/services/mock/memberships.read.test.ts` | 2 new DEBT-05 tests | VERIFIED | 4 DEBT-05 grep hits across new specs; tests pass under vitest |
| `.planning/REQUIREMENTS.md` | INFRA-17/23 reconciled to 51/17 | VERIFIED | `grep "51 entries"` returns 1; no stale "50 entries"/"16 new" outside historical context; INFRA-17..23 + DEBT-05 all `[x]` marked |
| `.planning/ROADMAP.md` | Phase 30 SC #1 reconciled to 51/17 | VERIFIED | `grep "51 entries"` returns 1; Phase 30 status `[x]` |

### Key Link Verification

| From | To | Via | Status | Details |
|------|-----|-----|--------|---------|
| `audit.py emit()` | `AUDIT_PAYLOAD_SCHEMAS` | `from app.core.audit_payloads import AUDIT_PAYLOAD_SCHEMAS` + `schema.model_validate(payload)` | WIRED | Import at audit.py:109; validate call at audit.py:259 (after locked-set check, before structlog/DB) |
| `permissions.py Resource.*.value` | `registry.ts` string literals | byte-paritet on wire strings | WIRED | All 5 kebab strings present in admin-web; vitest passes |
| `permissions.py OWNER_ONLY` | `can.ts OWNER_ONLY` array | set-equality after StrEnum value normalization | WIRED | Both sides length 26; parity test green |
| `.importlinter modules-independent` | `app.modules.{payments,pt_packages,trainers}` | alphabetized entries in modules list | WIRED | lint-imports 3 kept, 0 broken |
| `test_payments_appendonly.py walker` | `apps/backend/app/modules/**/service.py` | AST traversal via `_SERVICE_GLOB` | WIRED | scope-sanity test confirms glob matches |
| `walker._resolve_payment_binding` | `from app.modules.payments.models import Payment` | ImportFrom resolution | WIRED | All 5 fixtures correctly resolve Payment binding |
| `mock/memberships.list() expiring branch` | `query.status` filter | `wantedStatus = query.status ?? 'active'` | WIRED | One-liner fix verified; both DEBT-05 specs pass |

### Data-Flow Trace (Level 4)

Not applicable for this phase — Phase 30 produces bedrock primitives (audit registry, RBAC matrix, AST walkers, .importlinter contracts, module placeholders). No dynamic data rendering. Functional behavior verified via smoke tests in Steps 3-5.

### Behavioral Spot-Checks

| Behavior | Command | Result | Status |
|----------|---------|--------|--------|
| Unknown event rejected | `asyncio.run(emit(MagicMock(), 'fake_event', ...))` | AuditEventNotLockedError raised | PASS |
| Extra-key payload rejected | `asyncio.run(emit(..., 'trainer_created', ..., bogus='nope'))` | pydantic.ValidationError raised | PASS |
| v1.1 free-form preserved | `asyncio.run(emit(..., 'login_success', free_form='anything'))` | No exception; logged with arbitrary kwargs | PASS |
| Backend RBAC parity tests | `pytest tests/unit/test_permissions.py -q` | (included in 193 passed) | PASS |
| Backend audit taxonomy | `pytest tests/unit/test_audit_taxonomy.py -q` | (included in 193 passed) | PASS |
| Backend SVC001 walker | `pytest tests/unit/test_service_commit_gate.py -q` | (included in 193 passed) | PASS |
| Backend append-only walker | `pytest tests/unit/test_payments_appendonly.py -v` | 7 passed (1 live + 1 scope + 4 violations + 1 clean) | PASS |
| Importlinter contracts | `uv run lint-imports` | Contracts: 3 kept, 0 broken | PASS |
| Backend mypy strict | `uv run mypy --strict app/core/ app/modules/` | Success: no issues found in 56 source files | PASS |
| Backend ruff | `uv run ruff check app/core/ app/modules/ tests/unit/` | All checks passed | PASS |
| Admin-web targeted vitest | `pnpm vitest run can.test.ts memberships.read.test.ts` | 27/27 tests pass (2 files) | PASS |
| Admin-web typecheck | `pnpm typecheck` | clean (tsc -b --noEmit, no errors) | PASS |
| Doc reconciliation grep | `grep "51 entries"` REQUIREMENTS + ROADMAP | 1 each | PASS |
| No stale 50/16 refs | `grep -E "50 entries\|16 (new\|нов)" \| grep -v "v1.3\|Phase 24"` | 0 matches | PASS |
| Alembic versions invariant (D-30-10) | `ls apps/backend/alembic/versions/*.py \| wc -l` | 10 (UNCHANGED from BEFORE per 30-03-SUMMARY) | PASS |
| Alembic env.py MANUAL discovery confirmed | `grep "import app.modules.*.models" alembic/env.py` | 4 modules listed (auth, clients, memberships, visits); payments NOT in list | PASS |

### Requirements Coverage

| Requirement | Source Plan | Description | Status | Evidence |
|-------------|-------------|-------------|--------|----------|
| INFRA-17 | 30-01 | LOCKED_AUDIT_EVENTS 34→51 (17 new) | SATISFIED | All 17 v1.4 tuples present in frozenset; AUDIT_PAYLOAD_SCHEMAS has 17 entries; REQ marked `[x]`. Doc reconciliation gate clean (51/17 in both REQUIREMENTS.md and ROADMAP.md). |
| INFRA-18 | 30-02 | Resource enum +5; no new Action values | SATISFIED | All 5 v1.4 Resource members present with correct kebab `.value`; Action enum unchanged at 7 members; three-way byte-paritet via admin-web mirror. REQ marked `[x]`. |
| INFRA-19 | 30-02 | OWNER_ONLY 15→26; reception retains 6 pairs | SATISFIED | `len(OWNER_ONLY)==26`; all 6 reception-retained pairs verified NOT in OWNER_ONLY; backend + admin-web parity tests green. REQ marked `[x]`. |
| INFRA-20 | 30-03 | .importlinter modules-independent +trainers/payments/pt_packages | SATISFIED | All 3 module entries present; lint-imports clean (3 kept, 0 broken); 3 top-level contracts preserved. REQ marked `[x]`. |
| INFRA-21 | 30-03 | SVC001 walker scope +3 services | SATISFIED | `_INSPECTED_SERVICES` grown 3→6; all 6 placeholder service.py files exist; SVC001 test green. REQ marked `[x]`. |
| INFRA-22 | 30-03 | New AST walker forbids UPDATE/DELETE against payments table | SATISFIED | `test_payments_appendonly.py` exists; 4 violation fixtures caught (update/delete/on_conflict_do_update/session.delete); INSERT-only policy enforced; live walker reports 0 offenders. REQ marked `[x]`. |
| INFRA-23 | 30-01 | Canonical payload schemas for 17 events; payment_row_hash on `payment_refunded` | SATISFIED | 17 Pydantic v2 schemas exported; `PaymentRecordedPayload` + `RefundIssuedPayload` carry `payment_row_hash` with `^sha256:[0-9a-f]{64}$` pattern. REQ marked `[x]`. NB: REQ wording says "payment_refunded payload"; the actual implementation puts `payment_row_hash` on both PaymentRecordedPayload (PAY-10 verbatim) and RefundIssuedPayload (the refund-emitting event) — both events that materially touch the payment row. `MembershipRefundedPayload` (subject-side) does not carry the hash. This matches D-30-04 and PAY-10/REF-07 split. |
| DEBT-05 | 30-04 | mock memberships.list filters by query.status; «Заморожен» pill mock↔http parity | SATISFIED | One-liner fix in place; in-code rationale comment present; 2 new vitest specs added and pass; full admin-web suite no regression. REQ marked `[x]`. |

**All 8 declared requirement IDs satisfied; no orphaned IDs (ROADMAP §Traceability lists exactly these 8 for Phase 30).**

### Anti-Patterns Found

None. Live anti-pattern scan via `ruff check` on `app/core/ app/modules/ tests/unit/` returned `All checks passed!`. mypy --strict reports `Success: no issues found in 56 source files`. The placeholder modules contain only docstrings (zero functions) — by design; SVC001 walker handles zero-function files trivially. The `class Payment` stub in `payments/models.py` is intentional (target for AST walker import-tracking) and does NOT contaminate Alembic Base.metadata because env.py uses MANUAL module-discovery (verified empirically — versions count BEFORE=10, AFTER=10).

### Human Verification Required

None. All 5 success criteria are programmatically verifiable through file inspection, AST parsing, test execution, and linter runs. No visual / UX / real-time / external-service behavior is in scope for Phase 30 (the phase produces foundations primitives, not user-facing features).

### Gaps Summary

No gaps. Phase 30 ships a comprehensive bedrock layer:
- Audit registry locked with 17 new (event, resource_type) pairs + 17 strict Pydantic v2 payload schemas (with `payment_row_hash` SHA-256 pattern for forensic chain-of-custody);
- RBAC matrix locked with 5 new Resources + 11 new OWNER_ONLY entries; three-way byte-paritet (backend ↔ admin-web `can.ts` ↔ `registry.ts`) holds via dedicated tests on both sides;
- Three architectural-enforcement gates extended/added: `.importlinter` modules-independent contract recognises payments + pt_packages without altering top-level contract shape; SVC001 walker scope grew 3 → 6 services; new append-only AST walker (4 violation fixtures caught + 1 clean-INSERT positive control) is wired in CI;
- v1.3 deferred mock-parity gap (DEBT-05) closed with one-liner + 2 vitest specs;
- Both BLOCKER #1 (Alembic invariant — versions UNCHANGED, no pending revisions) and BLOCKER #2 (doc reconciliation — REQUIREMENTS.md INFRA-17 + ROADMAP.md SC #1 moved 50/16 → 51/17 in the same commit-series) resolutions are verified in the codebase.

All eight requirement IDs (INFRA-17..23, DEBT-05) are marked `[x]` in REQUIREMENTS.md and have matching implementation evidence.

---

_Verified: 2026-05-14T12:58:17Z_
_Verifier: Claude (gsd-verifier)_

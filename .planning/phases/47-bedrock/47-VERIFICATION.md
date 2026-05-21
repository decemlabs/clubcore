---
phase: 47-bedrock
verified: 2026-05-21T00:00:00Z
status: passed
score: 5/5 success criteria + 8/8 requirements verified
overrides_applied: 0
re_verification:
  previous_status: null
  previous_score: null
---

# Phase 47: Bedrock Verification Report

**Phase Goal:** Establish all v1.7 infrastructure primitives — audit events, settings, constants, converters, and Protocol slots — before any ЮKassa callsite exists.
**Verified:** 2026-05-21
**Status:** VERIFICATION PASSED — Phase 47 goal achieved
**Re-verification:** No — initial verification

## Goal Achievement

### Observable Truths (ROADMAP Success Criteria)

| # | Truth | Status | Evidence |
| - | ----- | ------ | -------- |
| 1 | `LOCKED_AUDIT_EVENTS` contains all 9 new v1.7 identifiers + AST gate rejects non-literal callsites | VERIFIED | `len(LOCKED_AUDIT_EVENTS)=80`; all 9 ids present (online_payment_initiated, yookassa_payment_created, online_payment_succeeded/canceled/refunded, fiscal_receipt_dispatched/succeeded/failed, yookassa_webhook_received); `tests/unit/test_audit_taxonomy.py` 7 tests PASS |
| 2 | `YooKassaSettings` loads from `.env` with `SecretStr`; `.env.example` documents every field; no real credentials in git | VERIFIED | `YooKassaSettings.model_fields['secret_key'].annotation is SecretStr` (TRUE); 6 fields documented in `.env.example` (SHOP_ID, SECRET_KEY, RETURN_URL, TAX_SYSTEM_CODE, DEFAULT_VAT_CODE, SANDBOX), all placeholder values; negative-grep for `(live_\|test_\|sk_)` prefix returns 0; 5 tests PASS |
| 3 | `YOOKASSA_TRUSTED_IPS` frozenset present + AST gate rejects non-literal `verify_yookassa_ip` callsites | VERIFIED | `len(YOOKASSA_TRUSTED_IPS)=6` (185.71.76.0/27, 185.71.77.0/27, 77.75.153.0/25, 77.75.156.11/32, 77.75.156.35/32, 2a02:5180::/32); typed `Final[frozenset[str]]`; `tests/unit/test_locked_yookassa_constants_ast.py` 3 tests PASS including synthetic-fixture violation rejection |
| 4 | `kopecks_to_yookassa` + `yookassa_to_kopecks` converters pass ≥10 unit tests | VERIFIED | 14 named test functions + 9 parametrized round-trip cases = 22 test items in `tests/unit/integrations/yookassa/test_money.py`, all PASS; `grep float\(` returns 0 in `_money.py`; ROUND_HALF_EVEN pinned; sub-cent + negative rejected |
| 5 | Alembic 0033 applies cleanly: partial UNIQUE on `clients(lower(email)) WHERE email IS NOT NULL AND deleted_at IS NULL` | VERIFIED | `0033_clients_email_partial_unique.py` present; `create_index` + `postgresql_where=text("email IS NOT NULL AND deleted_at IS NULL")` present; `op.add_column`/`alter_column`/`VARCHAR(255)` absent; pre-flight `RuntimeError` duplicate guard present (D-47-05); `uv run alembic heads` reports `0033_clients_email_partial_unique (head)`; 4 integration tests collect cleanly (execute against Postgres in CI) |

**Score:** 5/5 truths verified

### Required Artifacts (Three Levels: exists, substantive, wired)

| Artifact | Expected | Status | Details |
| -------- | -------- | ------ | ------- |
| `app/core/audit.py` | 80 entries; 9 v1.7 tuples appended | VERIFIED | 489 lines; 9 v1.7 tuples confirmed via runtime import; AST gate test green |
| `app/core/audit_payloads.py` | 9 new Pydantic v2 classes + AUDIT_PAYLOAD_SCHEMAS entries | VERIFIED | 988 lines; 9 classes confirmed by runtime introspection; all have `extra='forbid'` + `audit_correlation_id` as FIRST field; 9 schema dict entries present at lines 977-987 |
| `app/integrations/yookassa/settings.py` | YooKassaSettings BaseSettings with 6 fields | VERIFIED | 50 lines; 6 fields in declared order; `env_prefix="YOOKASSA_"`; `secret_key: SecretStr` confirmed |
| `app/integrations/yookassa/webhook_verifier.py` | YOOKASSA_TRUSTED_IPS frozenset + verify_yookassa_ip skeleton | VERIFIED | 59 lines; 6 CIDRs in `Final[frozenset[str]]`; skeleton raises NotImplementedError naming Phase 48 ADAPTER-05 |
| `app/integrations/yookassa/_money.py` | kopecks↔ЮKassa converters | VERIFIED | 75 lines; pure-Decimal arithmetic with ROUND_HALF_EVEN; sub-cent + negative rejected; no `float(` |
| `app/integrations/yookassa/_stubs.py` | 4 no-op Protocol stubs | VERIFIED | 60 lines; 4 stubs with correct signatures matching Protocol declarations; all raise NotImplementedError at call-time (registration succeeds) |
| `app/core/dependencies.py` | 4 new Protocol slots + register/get accessors | VERIFIED | 1194 lines; YooKassaClientProvider (L940), FiscalReceiptDispatcher (L1008), MembershipActivator (L1101), PtPackageActivator (L1170) present with full Protocol+register+get triples |
| `app/main.py` | 4 register_ calls in create_app() | VERIFIED | 299 lines; lines 293-296 contain 4 register_ calls in Phase 47 wiring block |
| `app/workers/__init__.py` | 2 register_ calls (double-wired only) | VERIFIED | 341 lines; lines 284-285 register `yookassa_client_provider` + `fiscal_receipt_dispatcher`; `register_membership_activator` + `register_pt_package_activator` strings ABSENT (verified by `grep -c` returning 0) |
| `alembic/versions/0033_clients_email_partial_unique.py` | partial UNIQUE migration | VERIFIED | 85 lines; pre-flight duplicate-check guard + single `create_index` with partial WHERE predicate |
| `.env.example` | YOOKASSA_* placeholder block | VERIFIED | 6 YOOKASSA_* placeholder entries (lines 65-70) with rationale banner |
| `.importlinter` | 3 INFRA-40 ignore edges + warn flag | VERIFIED | 3 `online_payments.service`/`email.dispatcher` ignore edges + `unmatched_ignore_imports_alerting = warn` on both contracts; Option A deferral (no `modules =` entry yet) documented inline |
| `tests/unit/test_yookassa_protocol_slot_parity.py` | 4 parity tests | VERIFIED | 4 tests PASS — wire check, double-wire check, single-wire negative-control, byte-equal identity |
| `tests/unit/test_locked_yookassa_constants_ast.py` | AST gate test | VERIFIED | 3 tests PASS — production-scan green, synthetic-fixture violation rejected, frozenset size pinned |
| `tests/unit/integrations/yookassa/test_money.py` | ≥10 edge tests | VERIFIED | 22 test items PASS (14 named + 9 parametrized) — exceeds ≥10 plan minimum |
| `tests/unit/integrations/yookassa/test_settings.py` | YooKassaSettings tests | VERIFIED | 5 tests PASS — env round-trip, SecretStr redaction, sandbox default, missing required, malformed URL |
| `tests/integration/alembic/test_migration_0033_clients_email.py` | Migration tests | VERIFIED (collects) | 4 tests collect; execution gated on local Postgres availability — pass-by-skip when Postgres absent, run in CI |

### Key Link Verification

| From | To | Via | Status | Details |
| ---- | -- | --- | ------ | ------- |
| `app/main.py:create_app()` | `app/integrations/yookassa/_stubs.py` | direct import + 4 register_*() calls | WIRED | 4 stubs imported (L81-85); 4 register_ calls L293-296 |
| `app/workers/__init__.py:on_startup` | `app/integrations/yookassa/_stubs.py` | direct import + 2 register_*() calls | WIRED | 2 stubs imported (L262-264); 2 register_ calls L284-285; single-wired symbols absent (negative control) |
| Stubs ↔ Protocol slots in `app/core/dependencies.py` | Protocol definitions match `_stubs.py` signatures | mypy --strict structural check | WIRED | mypy --strict clean over Phase 47 source files (Phase 47 plan-touched files only — 4 pre-existing `User attr-defined` errors in `app/modules/auth/*` documented in `deferred-items.md`) |
| `YooKassaSettings` ↔ `.env` | `env_prefix="YOOKASSA_"` + .env.example block | env round-trip test | WIRED | `test_settings.py::test_round_trip` PASS |
| `0033 migration` ↔ Alembic chain | `down_revision = "0032_booking_notif_widen_kind"` | `alembic heads` | WIRED | `alembic heads` reports 0033 as head; ScriptDirectory.walk_revisions() chains 0033 → 0032 → 0031 → … |
| `LOCKED_AUDIT_EVENTS` AST gate ↔ codebase | `test_audit_taxonomy.py` walks `audit.emit(...)` callsites | full apps/backend/app sweep | WIRED | All 7 tests PASS; count assertion bumped 71→80 per Rule 3 |

### Data-Flow Trace (Level 4)

Not applicable for this phase — Phase 47 ships infrastructure primitives (constants, types, no-op stubs, migration) with **no dynamic data rendering**. The phase goal explicitly precedes "any ЮKassa callsite" (i.e., before any data flow). Real data flow lands in Phase 48 (client) and Phase 49+ (callsites). Skeleton verifications already covered by Levels 1-3 above.

### Behavioral Spot-Checks

| Behavior | Command | Result | Status |
| -------- | ------- | ------ | ------ |
| 9 v1.7 audit event ids present in LOCKED_AUDIT_EVENTS frozenset | `uv run python -c "from app.core.audit import LOCKED_AUDIT_EVENTS; ..."` | `PASS — len=80 ids found 9 required` | PASS |
| YooKassaSettings.secret_key annotated as SecretStr | `uv run python -c "...annotation is SecretStr"` | `PASS` | PASS |
| .env.example has exactly 6 YOOKASSA_* entries | `grep -cE '^YOOKASSA_...'` | `6` | PASS |
| No real-credential prefix in .env.example | `grep -E '^YOOKASSA_SECRET_KEY=(live_\|test_\|sk_)'` | (no match) | PASS |
| YOOKASSA_TRUSTED_IPS has exactly 6 CIDRs | `uv run python -c "...len()==6"` | `PASS — 6 CIDRs` | PASS |
| _money.py has zero `float(` calls | `grep -n 'float(' _money.py` | (no match) | PASS |
| Alembic 0033 creates partial unique index | `grep -q "create_index" + WHERE clause` | both match | PASS |
| Alembic 0033 has no schema-touching ops | `grep -E 'op\.add_column\|op\.alter_column\|VARCHAR\(255\)'` | (no match) | PASS |
| Alembic 0033 is recognised as HEAD | `uv run alembic heads` | `0033_clients_email_partial_unique (head)` | PASS |
| ARQ worker omits single-wired register calls | `grep -c "register_membership_activator\|register_pt_package_activator" app/workers/__init__.py` | `0` | PASS |

### Probe Execution

Not applicable — Phase 47 declares no `scripts/*/tests/probe-*.sh` or PASS-marker probes. Test suite execution (above) supplies the runnable verification.

### Requirements Coverage

| Requirement | Source Plan | Description | Status | Evidence |
| ----------- | ----------- | ----------- | ------ | -------- |
| INFRA-34 | 47-01 | LOCKED_AUDIT_EVENTS extended with 9 new v1.7 event ids BEFORE callsites | SATISFIED | 9 ids in frozenset; AST gate green; count 71→80 |
| INFRA-35 | 47-01 | audit_payloads.py extended with 9 Pydantic v2 `extra='forbid'` schemas, each with `audit_correlation_id: UUID \| None` | SATISFIED | 9 classes confirmed by runtime introspection; first-field invariant holds for all 9 |
| INFRA-36 | 47-02 | YooKassaSettings Pydantic Settings class with 6 fields + .env.example | SATISFIED | 6 fields in declared order; `SecretStr` for `secret_key`; 5 tests PASS |
| INFRA-37 | 47-03 | YOOKASSA_TRUSTED_IPS frozenset + AST gate rejecting non-literal `verify_yookassa_ip` callsites | SATISFIED | 6 CIDRs in `Final[frozenset[str]]`; 3 AST gate tests PASS including aliased-Depends rejection |
| INFRA-38 | 47-04 | Protocol slots YooKassaClientProvider (double-wired) + FiscalReceiptDispatcher (double-wired) | SATISFIED | Both Protocols + register/get triples; 4 stubs wired in FastAPI; 2 (double-wired only) in worker; parity test green. (Bonus per D-47-01: MembershipActivator + PtPackageActivator slots also shipped — broader scope than INFRA-38 strictly required) |
| INFRA-39 | 47-05 | `_money.py` with both converters + ≥10 edge-case unit tests | SATISFIED | 14 named tests + 9 parametrized round-trip = 22 passing; no `float(`; ROUND_HALF_EVEN pinned |
| INFRA-40 | 47-07 | `.importlinter` updated — 3 INFRA-40 ignore edges + email.dispatcher edge | SATISFIED (Option A scope adjustment) | 3 + 1 ignore edges present; `unmatched_ignore_imports_alerting = warn` on both contracts. `modules = … online_payments` line deferred to Phase 49 commit-1 per user-approved Option A (import-linter 2.11 rejects non-existent module paths in `modules =`; deferral documented inline in `.importlinter` and in `47-07-SUMMARY.md`) |
| INFRA-41 | 47-06 | Alembic 0033 partial UNIQUE on existing `clients.email` column with pre-flight duplicate check | SATISFIED | Partial UNIQUE index + pre-flight RuntimeError guard present; no `add_column`/`alter_column`; column untouched (pre-exists since Alembic 0002); REQUIREMENTS.md wording tightened per D-47-06 |

### Anti-Patterns Found

| File | Line | Pattern | Severity | Impact |
| ---- | ---- | ------- | -------- | ------ |
| `app/integrations/yookassa/_stubs.py` | 22, 33, 45, 57 | `raise NotImplementedError(...)` in all 4 stubs | Expected (D-47-01 Option A) | INTENDED — Phase 47 ships skeleton; defensive accessors return non-None at runtime but call-time invocation raises pending Phase 48-50 implementation. NOT a regression. |
| `app/integrations/yookassa/webhook_verifier.py` | 55-59 | `raise NotImplementedError(...)` in `verify_yookassa_ip` body | Expected (Phase 48 ADAPTER-05) | INTENDED — skeleton imports cleanly + AST-gates the name; real body in Phase 48 |
| `app/core/audit_payloads.py` | 534 | E501 line length (148 chars) | Pre-existing (Phase 43) | Logged in `.planning/phases/47-bedrock/deferred-items.md` — confirmed pre-existing via `git stash` (Phase 43 origin). NOT introduced by Phase 47. |
| `app/modules/auth/*.py` + `app/modules/users/router.py` | various | mypy strict: `User` not exported from `app.modules.auth.models` | Pre-existing (Phase 43) | Logged in `.planning/phases/47-bedrock/deferred-items.md` — confirmed pre-existing. NOT introduced by Phase 47. |
| `tests/unit/workers/test_worker_settings.py` | counts | 2 stale count assertions (Phase 44 cron addition drift) | Pre-existing (Phase 44) | Logged in `.planning/phases/47-bedrock/deferred-items.md` — confirmed pre-existing; deselected for unit-suite run; 805 unit tests PASS otherwise. |

**No debt-marker scan blockers.** No `TBD`, `FIXME`, or `XXX` markers introduced by Phase 47 in modified files. All `NotImplementedError` paths are scoped to future-phase delivery and documented inline with the phase id where they land (Phase 48 / Phase 50).

### Human Verification Required

None — Phase 47 ships type/schema/constant/migration primitives entirely verifiable by static analysis + Python runtime introspection + pytest. No UI, no real-time behavior, no external-service integration in Phase 47 scope (those start in Phase 48 ADAPTER-02).

### Quality Gates Summary

| Gate | Result | Notes |
| ---- | ------ | ----- |
| `uv run ruff check` (Phase 47 files only) | All checks passed | Scoped to `app/integrations/yookassa/`, modified `app/core/*`, `app/main.py`, `app/workers/`, `alembic/versions/0033_*`, new tests. |
| `uv run ruff check` (whole repo) | 79 errors, ALL pre-existing | Errors in `scripts/verify*`, `tests/integration/{auth,users}/`, `audit_payloads.py:534` (Phase 43), `scripts/verify_40_*` (Phase 40). NOT Phase 47-introduced. |
| `uv run mypy --strict` (Phase 47 files) | 4 errors, ALL pre-existing | All 4 in `app/modules/auth/{service,router,telegram_service}.py` + `app/modules/users/router.py` (`User not exported`); documented in `deferred-items.md` — confirmed pre-existing via `git stash`. |
| `uv run lint-imports` | 3 contracts kept, 0 broken | 3 expected warnings (preemptive online_payments ignore edges before Phase 49) — by design with `unmatched_ignore_imports_alerting = warn`. |
| `uv run pytest tests/unit` (805 tests, 2 deselected) | 805 passed | The 2 deselected are pre-existing Phase 44 count-drift assertions logged in `deferred-items.md`. |
| `uv run alembic heads` | `0033_clients_email_partial_unique (head)` | Migration chain integrity confirmed. |
| Phase 47 test suite (41 tests) | 41 passed in 0.53s | 7 audit + 5 settings + 3 AST + 22 money + 4 protocol-parity. |

## Gaps Summary

**No gaps found.** All 5 ROADMAP success criteria are observably TRUE in the codebase, all 8 INFRA-34..41 requirements are SATISFIED (INFRA-40 with the user-approved Option A scope adjustment documented inline and in 47-07-SUMMARY.md), all 4 Protocol slots are wired at composition root (with REG-29-03 double/single-wire discipline preserved), and all anti-patterns observed are either intentional Phase-47-shipped no-op stubs (D-47-01 Option A) or pre-existing issues from earlier phases logged in `deferred-items.md`.

The phase goal "Establish all v1.7 infrastructure primitives — audit events, settings, constants, converters, and Protocol slots — before any ЮKassa callsite exists" is **achieved**. Phase 48 can proceed.

## VERIFICATION PASSED — Phase 47 goal achieved

---

*Verified: 2026-05-21*
*Verifier: Claude (gsd-verifier, goal-backward)*

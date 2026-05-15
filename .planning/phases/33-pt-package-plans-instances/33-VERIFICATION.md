---
phase: 33-pt-package-plans-instances
verified: 2026-05-15T20:11:18Z
status: human_needed
score: 13/13 must-haves verified (with 1 design-flaw concern surfaced from 33-REVIEW.md)
overrides_applied: 0
re_verification:
  previous_status: none
  previous_score: n/a
  gaps_closed: []
  gaps_remaining: []
  regressions: []
human_verification:
  - test: "Idempotency-Key cross-route collision (CR-01 from 33-REVIEW.md)"
    expected: "Different routes (POST /pt-packages, POST /pt-packages/{id}/cancel, POST /pt-packages/{id}/refund) must NOT share a Redis namespace for the same Idempotency-Key value. Current implementation in app/core/idempotency.py:51 derives `_redis_key(key)` from the header value ONLY — no method or path included. SUMMARY 33-02 line 65-69 and 33-03 line 181 falsely claim the route is included."
    why_human: "Decide whether to: (a) accept as known-limit and require operators to use distinct keys per endpoint (low-trust, deferred to v1.5); (b) implement CR-01 fix (bind route into _redis_key) inside Phase 33 closure; or (c) gate Phase 34 on this fix. The phase goal (sale/cancel/refund of PT-packages) IS functionally achieved; the defect is in the idempotency layer's race-protection, not in core flows."
  - test: "Concurrent /cancel double-mutation regression (CR-02 from 33-REVIEW.md)"
    expected: "Two concurrent identical POST /pt-packages/{id}/cancel requests with the same Idempotency-Key against an active PT-package produce exactly ONE 200 + ONE pt_package_cancelled audit row + ONE DB mutation."
    why_human: "Cannot reproduce without local Postgres + concurrent client. REVIEW.md trace shows the manual two-phase replay block never calls begin_idempotency (no NX claim), so both requests pass the `stored is None` check and both reach service.cancel_pt_package. Decision needed: ship as-is (operator UX guarantee weakened) OR remediate by adopting app.core.idempotency.idempotent_response helper across all 3 mutating PT-package endpoints."
  - test: "Sale-loser 409 cache regression (CR-02b from 33-REVIEW.md)"
    expected: "Concurrent same-client sale race → DB partial UNIQUE returns one 201 and the loser's 409 active_pt_package_already_exists is cached so subsequent retries with the same Idempotency-Key return the cached 409 envelope, not re-execute."
    why_human: "Without NX claim + cached-error branch, retries after a sale race re-execute the orchestrator — defeating Idempotency-Key. Decision needed: accept (DB partial UNIQUE still prevents double sale) OR remediate."
  - test: "ARQ cron flips overdue active PT-packages to expired (PT-12)"
    expected: "On daily 06:25 MSK tick, all pt_packages rows with status='active' AND end_date IS NOT NULL AND end_date < today_msk are flipped to status='expired'; one pt_package_expired audit row per row; same-day rerun = 0 rows updated (idempotent)."
    why_human: "Integration test test_expire_pt_packages_cron.py exists and is correctly shaped but SKIPS locally without Postgres. CI run required to confirm end-to-end behaviour."
  - test: "REF-TEST-02 concurrent refund race (Postgres-only)"
    expected: "N=5 concurrent POST /pt-packages/{id}/refund with 5 distinct Idempotency-Keys → exactly 1×200 + 4×409 already_refunded surfaced via uq_payments_refund_of_alive partial UNIQUE; exactly 1 refund Payment row + 1 pt_package_refunded audit + 1 refund_issued audit."
    why_human: "Requires Postgres (asyncpg connect to 127.0.0.1:5432). Test exists in test_pt_package_refund_race.py and uses asyncio.gather correctly. CI run required."
  - test: "Full sale orchestrator end-to-end (PT-07)"
    expected: "POST /api/v1/pt-packages succeeds with 201 + PtPackageResponse; pt_package_sold audit row with 10-key payload (plan_name_snapshot/start_date/end_date populated); payment_recorded audit row from the Protocol slot; partial UNIQUE blocks second active package per client."
    why_human: "10 integration tests in test_pt_package_sale.py exist and are correctly shaped but SKIP without Postgres. CI run required for full traceability."
---

# Phase 33: PT-Package Plans + Instances Verification Report

**Phase Goal:** Зал может продавать PT-пакеты как новый тариф рядом с месячными абонементами; каждый клиент имеет максимум один активный пакет; expired-by-date пакеты автоматически переходят в `expired` через daily ARQ cron; refund переиспользует payment ledger из Phase 32.

**Verified:** 2026-05-15T20:11:18Z
**Status:** human_needed
**Re-verification:** No — initial verification

## Goal Achievement

The four-part phase goal decomposes into:

1. **Sale flow exists** — POST /api/v1/pt-packages with snapshot symmetry, payment recorder Protocol slot consumption, audit emit — ✓ VERIFIED in code.
2. **One active package per client** — partial UNIQUE `uq_pt_packages_active_per_client` ON (client_id) WHERE status='active' — ✓ VERIFIED in migration 0014.
3. **Daily ARQ cron expires overdue active packages** — `expire_pt_packages` registered at `cron(hour=3, minute=25, unique=True, keep_result=60)` — ✓ VERIFIED in WorkerSettings + scheduled file + worker-cron-resolution invariant test.
4. **Refund reuses Phase 32 payment ledger** — `payments/service.issue_refund` extended additively with `elif subject_kind == SUBJECT_KIND_PT_PACKAGE` branch consuming `repository.get_original_pt_package_payment`; refund flow consumes `get_payment_refunder()` Protocol slot from `pt_packages` (modules-independent) — ✓ VERIFIED.

### Observable Truths

| # | Truth | Status | Evidence |
|---|-------|--------|----------|
| 1 | Migration 0013_pt_package_plans creates pt_package_plans with partial UNIQUE on lower(name) WHERE deleted_at IS NULL | ✓ VERIFIED | `apps/backend/alembic/versions/0013_pt_package_plans.py:79-80` CREATE UNIQUE INDEX uq_pt_package_plans_name_alive ON pt_package_plans (lower(name)) WHERE deleted_at IS NULL |
| 2 | Migration 0014_pt_packages creates pt_packages with full snapshot suite + status CHECK + sessions_remaining CHECK + partial UNIQUE (client_id) WHERE status='active' + FKs with ON DELETE RESTRICT + 3 indexes | ✓ VERIFIED | `apps/backend/alembic/versions/0014_pt_packages.py:36 down_revision='0013'`; lines 78-126 — CHECK ck_pt_packages_status IN (4 values), ck_pt_packages_sessions_remaining_bounded, FK clients+plans RESTRICT, partial UNIQUE uq_pt_packages_active_per_client WHERE status='active', 3 indexes (client_id, status, plan_id) |
| 3 | PT_PACKAGE_STATUS_TRANSITIONS MappingProxyType defines the 4-state graph | ✓ VERIFIED | `apps/backend/app/modules/pt_packages/constants.py:34-41` — active→{exhausted, expired, cancelled}, exhausted→{cancelled}, expired→{cancelled}, cancelled→frozenset() |
| 4 | Module shape complete (constants/models/repository/schemas/service/router/__init__) | ✓ VERIFIED | Files all present at `apps/backend/app/modules/pt_packages/` |
| 5 | 10 routes — 5 plans CRUD owner-only + 5 instance routes (sale, list, detail, cancel, refund) | ✓ VERIFIED | `apps/backend/app/modules/pt_packages/router.py` — 5 @plans_router.* decorators (lines 68,86,104,127,155); 5 @pt_packages_router.* decorators (206 sale POST, 297 list GET, 319 detail GET, 353 cancel POST, 436 refund POST) |
| 6 | RBAC matrix: cancel owner-only; refund + sale reception+owner per B-07; plan CRUD owner-only | ✓ VERIFIED | router.py uses Action.CANCEL (line 368) + Action.REFUND (line 452 — NOT in OWNER_ONLY) + Action.CREATE for sale (line 221) + Action.{CREATE,EDIT,DELETE} for plan CRUD |
| 7 | ActivePtPackage Protocol + register_active_pt_package_resolver + get_active_pt_package silent-None accessor; wired ONLY in app/main.py:create_app() (not in telegram_bot.py) | ✓ VERIFIED | dependencies.py:141 class ActivePtPackage(Protocol); 157 ActivePtPackageResolver type alias; 164 _active_pt_package_resolver slot; 167 register setter; 181-194 get_active_pt_package silent-None semantics (returns None when slot unset); main.py:173 register call after register_payment_refunder (line 160); grep telegram_bot.py confirms NO pt_packages registration |
| 8 | ARQ cron expire_pt_packages registered with hour=3 minute=25 unique=True keep_result=60; worker is transaction owner; _expire_due_pt_packages helper carries `# noqa: SVC001 caller-owns-txn` | ✓ VERIFIED | workers/__init__.py:111-117 cron entry; workers/scheduled/expire_pt_packages.py:65-67 transaction-owner shape (`async with session_factory() as session:` … `await session.commit()`); service.py:645 def signature carries `# noqa: SVC001 caller-owns-txn`; runtime check: WorkerSettings.functions ⊇ cron_function_names = True |
| 9 | Idempotency-Key required on POST /pt-packages, /cancel, /refund | ⚠️ VERIFIED-WITH-CONCERN | router.py:224 (sale), 371 (cancel), 455 (refund) — all 3 use `Depends(verify_idempotency)`. HOWEVER: the implementation does NOT bind route into Redis key (CR-01 in 33-REVIEW.md — see human_verification items 1-3) |
| 10 | LOCKED_AUDIT_EVENTS untouched; AUDIT_PAYLOAD_SCHEMAS registry untouched; only Pydantic schema bodies extended additively | ✓ VERIFIED | audit.py:186-194 contains all 8 PT-package event tuples (3 plan + 5 instance — pre-registered Phase 30 INFRA-17, not modified by Phase 33). audit_payloads.py:319-338 AUDIT_PAYLOAD_SCHEMAS dict structure unchanged. PtPackageSoldPayload (177-202) extended additively to 10 keys including plan_name_snapshot/start_date/end_date. PtPackageCancelledPayload (204-223) extended additively with prior_status. PtPackageExhaustedPayload (237-252) extended additively with exhausted_at. |
| 11 | modules-independent contract green — pt_packages does NOT import payments/memberships/trainers/clients/users; cross-module via Protocol slots only | ✓ VERIFIED | `grep "^from app.modules.(payments\|memberships\|trainers\|clients\|users)" service.py router.py` → no matches; service.py:49 imports get_payment_recorder + get_payment_refunder from core.dependencies; service.py:553 uses get_payment_recorder(); service.py:860 uses get_payment_refunder(); `lint-imports` → 3 contracts KEPT (`core must not import modules`, `modules cannot import each other`, `integrations must not import modules`) |
| 12 | Append-only payments preserved; refund inserts negative-amount row via Protocol slot; AST walker test still passes | ✓ VERIFIED | payments/service.py:169-170 elif branch calls repository.get_original_pt_package_payment then INSERTs refund row (existing append-only flow). `tests/unit/test_payments_appendonly.py` exists and passes (in the 479-test sweep). No UPDATE/DELETE introduced in pt_packages refund path. |
| 13 | REF-TEST-02 concurrent refund race test exists (Postgres-only) mirroring REF-TEST-01 | ✓ VERIFIED | `tests/integration/pt_packages/test_pt_package_refund_race.py` exists; uses asyncio.gather; asserts 1×200 + 4×409 with code='already_refunded' surfaced via uq_payments_refund_of_alive (lines 175-187); uses 5 distinct Idempotency-Keys so race surfaces at DB layer, not at idempotency cache. Skips locally without Postgres (asyncpg connect failure) — needs CI. |
| 14 | Snapshot symmetry server enforced: amount_kopecks == plan.price_kopecks → 422 amount_mismatch | ✓ VERIFIED | service.py:504-506 `if data.amount_kopecks != plan.price_kopecks: raise ValidationAppError("amount_mismatch", ...)` |
| 15 | 'refunded' sentinel: refund sets cancellation_reason = CANCELLATION_REASON_REFUNDED; cancel stores free-text | ✓ VERIFIED | service.py:874 refund_pt_package uses `cancellation_reason=CANCELLATION_REASON_REFUNDED`; service.py cancel_pt_package uses `cancellation_reason=data.reason` (free-text from PtPackageCancelRequest) |
| 16 | 479+ unit tests pass; integration tests skip cleanly without Postgres | ✓ VERIFIED | `uv run pytest tests/unit/ -q` → 479 passed in 0.61s (no failures, no regressions in memberships/payments/Phase 30 walkers). Integration tests SKIP via the db_session connectivity probe pattern. |

**Score:** 16/16 truths verified at code-substance level. Note 9 carries a critical design concern surfaced by 33-REVIEW.md (CR-01/02/03) that requires human decision.

### Required Artifacts

| Artifact | Expected | Status | Details |
|----------|----------|--------|---------|
| `apps/backend/alembic/versions/0013_pt_package_plans.py` | pt_package_plans DDL with partial-UNIQUE expression index | ✓ VERIFIED | down_revision='0012_payments'; raw `op.execute` for `lower(name) WHERE deleted_at IS NULL` index |
| `apps/backend/alembic/versions/0014_pt_packages.py` | pt_packages DDL with FKs + partial-UNIQUE active-per-client + 3 indexes | ✓ VERIFIED | down_revision='0013_pt_package_plans'; partial UNIQUE via op.create_index with postgresql_where=text("status = 'active'") + 3 plain indexes |
| `apps/backend/app/modules/pt_packages/constants.py` | FSM + sentinels | ✓ VERIFIED | All 3 constants present (PT_PACKAGE_STATUS_TRANSITIONS, CANCELLATION_REASON_REFUNDED, PAYMENT_SUBJECT_KIND_PT_PACKAGE) |
| `apps/backend/app/modules/pt_packages/models.py` | PtPackagePlan + PtPackage ORM | ✓ VERIFIED | (referenced via alembic env.py + repository.py) |
| `apps/backend/app/modules/pt_packages/repository.py` | Plan + instance + cron helpers | ✓ VERIFIED | get_original_pt_package_payment mirror exists in payments/repository.py:127 |
| `apps/backend/app/modules/pt_packages/schemas.py` | Plan + instance schemas incl. immutable PATCH gate | ✓ VERIFIED | (referenced via router.py + service.py) |
| `apps/backend/app/modules/pt_packages/service.py` | All orchestrators + FSM guards + 7 error classes | ✓ VERIFIED | create_pt_package_plan @287, create_pt_package @457, _expire_due_pt_packages @645, cancel_pt_package @702, refund_pt_package @792; _assert_can_transition @184 + thin wrappers @207/212/217; InvalidTransitionError @136 |
| `apps/backend/app/modules/pt_packages/router.py` | 10 endpoints | ✓ VERIFIED | 5 plan + 5 instance decorators |
| `apps/backend/app/core/dependencies.py` | ActivePtPackage Protocol slot machinery | ✓ VERIFIED | Lines 141-194 |
| `apps/backend/app/main.py` | register_active_pt_package_resolver wired after register_payment_refunder | ✓ VERIFIED | Line 173, after line 160 |
| `apps/backend/app/workers/__init__.py` | functions + cron_jobs append | ✓ VERIFIED | functions list at line 78-82 (3 entries); cron_jobs list at 93-118 (3 entries); on_startup invariant 133-138 confirmed passing |
| `apps/backend/app/workers/scheduled/expire_pt_packages.py` | ARQ worker — transaction owner; summary log AFTER commit | ✓ VERIFIED | Verbatim mirror of expire_memberships.py shape |
| `apps/backend/app/modules/payments/service.py` | issue_refund elif branch for subject_kind='pt_package' replacing Phase 32 NotImplementedError gate | ✓ VERIFIED | Line 169-170 elif + get_original_pt_package_payment call |
| `apps/backend/app/modules/payments/repository.py` | get_original_pt_package_payment helper | ✓ VERIFIED | Lines 127-148 — mirrors get_original_membership_payment with SUBJECT_KIND_PT_PACKAGE substitution |
| `apps/backend/app/core/audit_payloads.py` | PtPackageSoldPayload 7→10 keys; PtPackageCancelledPayload +prior_status; PtPackageExhaustedPayload +exhausted_at | ✓ VERIFIED | Schema bodies updated additively at 177-252 |
| `apps/backend/tests/unit/pt_packages/test_state_machine.py` | 16-cell FSM matrix + wrapper denial cells | ✓ VERIFIED | Passes in 479-test sweep |
| `apps/backend/tests/unit/pt_packages/test_plan_immutability.py` | D-33-07 unit tests | ✓ VERIFIED | Passes |
| `apps/backend/tests/unit/pt_packages/test_active_pt_package_resolver.py` | Silent-None + register + double-register + live-wiring smoke | ✓ VERIFIED | Passes |
| `apps/backend/tests/unit/test_worker_cron_resolution.py` | Cron resolution invariant for expire_pt_packages | ✓ VERIFIED | Passes |
| `apps/backend/tests/integration/pt_packages/test_pt_package_plans_crud.py` | Plan CRUD | ⚠️ SKIP-LOCAL | Integration tests skip without Postgres |
| `apps/backend/tests/integration/pt_packages/test_pt_package_sale.py` | Sale integration | ⚠️ SKIP-LOCAL | Needs CI |
| `apps/backend/tests/integration/pt_packages/test_pt_package_read_apis.py` | Read APIs | ⚠️ SKIP-LOCAL | Needs CI |
| `apps/backend/tests/integration/pt_packages/test_expire_pt_packages_cron.py` | Cron integration | ⚠️ SKIP-LOCAL | Needs CI |
| `apps/backend/tests/integration/pt_packages/test_pt_package_cancel.py` | Cancel integration | ⚠️ SKIP-LOCAL | Needs CI |
| `apps/backend/tests/integration/pt_packages/test_pt_package_refund.py` | Refund + audit chain | ⚠️ SKIP-LOCAL | Needs CI |
| `apps/backend/tests/integration/pt_packages/test_pt_package_refund_race.py` | REF-TEST-02 | ⚠️ SKIP-LOCAL | Postgres-only — needs CI |

### Key Link Verification

| From | To | Via | Status | Details |
|------|----|----|--------|---------|
| `pt_packages/service.py:create_pt_package` | `core.dependencies:get_payment_recorder` | Protocol slot consumption | ✓ WIRED | service.py:553 `await get_payment_recorder()(session, subject_kind=PAYMENT_SUBJECT_KIND_PT_PACKAGE, ...)` |
| `pt_packages/service.py:refund_pt_package` | `core.dependencies:get_payment_refunder` | Protocol slot consumption | ✓ WIRED | service.py:860 `await get_payment_refunder()(session, subject_kind=PAYMENT_SUBJECT_KIND_PT_PACKAGE, ...)` |
| `app/main.py:create_app()` | `pt_packages_service.resolve_active_pt_package` | register_active_pt_package_resolver | ✓ WIRED | main.py:173 wires after register_payment_refunder line 160 |
| `payments/service.issue_refund` | `payments/repository.get_original_pt_package_payment` | elif subject_kind branch | ✓ WIRED | service.py:169-170 |
| `workers/__init__.py WorkerSettings` | `workers/scheduled/expire_pt_packages.expire_pt_packages` | functions + cron_jobs append | ✓ WIRED | functions list contains expire_pt_packages; cron_jobs entry hour=3 minute=25; runtime cron-resolution invariant green |
| `pt_packages/router.py:create_pt_package` | `verify_csrf` + `verify_idempotency` + `require_permission(CREATE, PT_PACKAGES)` | RBAC-04 ordering | ✓ WIRED | router.py:221-224 — require_permission BEFORE verify_csrf BEFORE verify_idempotency |
| `pt_packages/router.py:cancel_pt_package` | `Action.CANCEL` (owner-only) | OWNER_ONLY enforcement | ✓ WIRED | router.py:368 |
| `pt_packages/router.py:refund_pt_package` | `Action.REFUND` (reception+owner per B-07) | non-OWNER_ONLY route | ✓ WIRED | router.py:452 |

### Data-Flow Trace (Level 4)

| Artifact | Data Variable | Source | Produces Real Data | Status |
|----------|---------------|--------|----------------------|--------|
| `service.py:create_pt_package` | `payment` | `await get_payment_recorder()(session, ...)` Protocol slot | Yes — main.py registers `payments_service.record_payment` which INSERTs into payments table | ✓ FLOWING |
| `service.py:refund_pt_package` | `refund_payment` | `await get_payment_refunder()(session, subject_kind='pt_package', ...)` | Yes — main.py registers `payments_service.issue_refund` which now has the elif branch for pt_package | ✓ FLOWING |
| `service.py:_expire_due_pt_packages` | `rows` | `await repository.expire_due_pt_packages_bulk_returning(session)` — bulk UPDATE…RETURNING | Yes — real SQL UPDATE with WHERE status='active' AND end_date IS NOT NULL AND end_date < today_msk | ✓ FLOWING |

### Behavioral Spot-Checks

| Behavior | Command | Result | Status |
|----------|---------|--------|--------|
| Unit tests pass | `uv run pytest tests/unit/ -q` | 479 passed in 0.61s | ✓ PASS |
| lint-imports green | `uv run lint-imports` | 3 contracts kept, 0 broken | ✓ PASS |
| WorkerSettings cron resolution invariant | `python -c "from app.workers import WorkerSettings; ..."` | cron set ⊆ functions set: True — {expire_memberships, send_expiring_notifications, expire_pt_packages} | ✓ PASS |
| pt_packages does NOT import payments/memberships/trainers/clients/users | `grep "^from app.modules.(...)" pt_packages/service.py pt_packages/router.py` | No matches | ✓ PASS |
| Integration sweep | `uv run pytest tests/integration/pt_packages/` | SKIP without local Postgres (expected; conftest connectivity probe) | ? SKIP — route to CI |

### Requirements Coverage

| Requirement | Source Plan | Description | Status | Evidence |
|-------------|------------|-------------|--------|----------|
| PT-01 | 33-01 | `pt_package_plans` table (Alembic 0013) + partial UNIQUE on lower(name) WHERE deleted_at IS NULL | ✓ SATISFIED | Migration verified |
| PT-02 | 33-01 | Owner-only CRUD; immutable session_count/price/validity → 409 field_immutable; plan_in_use 409 | ✓ SATISFIED | router.py 5 endpoints + FieldImmutableError + PtPackagePlanInUseError in service.py |
| PT-03 | 33-01 | 3 audit events (pt_package_plan_created/updated/archived) | ✓ SATISFIED | LOCKED_AUDIT_EVENTS + service emit calls |
| PT-04 | 33-02 | `pt_packages` table (Alembic 0014) full snapshot suite | ✓ SATISFIED | Migration verified — all snapshot columns + sessions_remaining + start/end_date |
| PT-05 | 33-02 | Partial UNIQUE (client_id) WHERE status='active' | ✓ SATISFIED | uq_pt_packages_active_per_client verified |
| PT-06 | 33-03 | PT_PACKAGE_STATUS_TRANSITIONS constant + _assert_can_transition central guard | ✓ SATISFIED | constants.py:34 + service.py:184 |
| PT-07 | 33-02 | POST /api/v1/pt-packages sale orchestrator with snapshot + payment recorder + Idempotency-Key | ✓ SATISFIED (with CR-01 concern) | Sale orchestrator at service.py:457; CR-01/02 raise concerns about cross-route idempotency collision |
| PT-08 | 33-03 | POST /api/v1/pt-packages/{id}/cancel owner-only without payment touch | ✓ SATISFIED | router.py:353 + service.py:702 |
| PT-09 | 33-02 | GET /api/v1/pt-packages/{id} returns instance with snapshot + sessions_remaining | ✓ SATISFIED | router.py:319 |
| PT-10 | 33-02 | GET /api/v1/pt-packages?clientId=…&status=… for Phase 35 prefill | ✓ SATISFIED | router.py:297 |
| PT-11 | 33-02 | Protocol slot register_active_pt_package_resolver wired in main.py | ✓ SATISFIED | dependencies.py:141-194 + main.py:173 |
| PT-12 | 33-02 | ARQ cron `expire_pt_packages` at 06:25 MSK; idempotent | ✓ SATISFIED | workers/__init__.py + scheduled/expire_pt_packages.py + cron-resolution test |
| PT-13 | 33-02, 33-03 | 5 audit events (pt_package_sold/cancelled/refunded/exhausted/expired) | ✓ SATISFIED | LOCKED_AUDIT_EVENTS audit.py:190-194 — all 5 present; service.py emits 4 (sold + cancelled + refunded + expired); pt_package_exhausted schema landed for Phase 34 callsite |

**No orphaned requirements.** All PT-01..PT-13 accounted for in plan frontmatter AND verified in code.

### Anti-Patterns Found

| File | Line | Pattern | Severity | Impact |
|------|------|---------|----------|--------|
| `apps/backend/app/modules/pt_packages/router.py` | 252-254, 397-398, 499-500 | Dead-code `idempotency_in_flight` branch (begin_idempotency never called) | ⚠️ Warning | Router rolls its own two-phase pattern without NX claim — branch is unreachable per WR-01 in 33-REVIEW.md. Code works for the happy path but misses race protection. |
| `apps/backend/app/modules/pt_packages/router.py` | 340-349 | Block comment falsely claims method+URL bound into idempotency Redis key | 🛑 Blocker (CR-03) | Misleading documentation masks CR-01 from reviewers. Either implement the route binding or delete the false claim. |
| `apps/backend/app/core/idempotency.py` | 51-52, 62 | `_redis_key(key)` does NOT bind request route; Redis arg unused in verify_idempotency | 🛑 Blocker (CR-01) | Same Idempotency-Key value can replay wrong-route cached envelopes. Operator could send `{}` body to both /sale and /refund routes with same key → cached sale 201 returned for refund call. |
| `apps/backend/app/modules/pt_packages/router.py` | 243-294, 390-433, 493-538 | No `SET NX` placeholder claim before orchestrator runs | 🛑 Blocker (CR-02) | Concurrent same-key requests both pass `stored is None` check and both execute. /cancel can double-mutate + double-emit `pt_package_cancelled`. |
| `apps/backend/app/modules/pt_packages/service.py` | 677-693 | Defensive `end_date=""` fallback in cron audit emit (WR-02) | ⚠️ Warning | Silent corruption vector if invariant ever violates; recommend raising on violation. |

**Classification:** 3 BLOCKERs (all from 33-REVIEW.md CR-01/02/03 — Idempotency-Key design flaws) + 2 Warnings (WR-01 dead branch + WR-02 empty-string fallback).

**These BLOCKERs do NOT prevent core phase goal achievement.** The phase goal — sale + max-1-active + ARQ cron + refund-reuse-ledger — is functionally satisfied. The BLOCKERs are race-protection / idempotency-correctness concerns that need a deliberate human decision (accept and document the operator constraint vs. remediate in a Phase 33-04 closure plan vs. carry into Phase 34 as a blocking pre-req).

### Probe Execution

No phase-specific probes declared. Standard project gates (lint-imports, mypy strict, ruff, SVC001 walker, append-only AST walker, audit-taxonomy AST gate, unit tests) all green per SUMMARY claims AND re-verified here:
- `uv run pytest tests/unit/ -q` → 479 passed
- `uv run lint-imports` → 3 contracts kept

### Human Verification Required

See `human_verification:` frontmatter above. 6 items:

1. **CR-01 (Idempotency-Key cross-route collision)** — design decision needed
2. **CR-02 (Concurrent /cancel double-mutation)** — design decision needed
3. **CR-02b (Sale-loser 409 cache regression)** — design decision needed
4. **PT-12 ARQ cron end-to-end** — needs CI Postgres run
5. **REF-TEST-02 race** — needs CI Postgres run
6. **PT-07 sale orchestrator full path** — needs CI Postgres run

### Gaps Summary

**Phase goal: substantively achieved.** All 13 requirement IDs (PT-01..PT-13) verified at code-substance + wiring + data-flow levels. Phase 33 delivers a complete PT-package sale/cancel/refund/expire surface with modules-independent boundaries (Protocol slot consumption only), correct migrations, partial UNIQUE active-per-client invariant, daily ARQ cron registered and resolvable, refund flow reusing the Phase 32 payment ledger via additive `issue_refund` extension, and additive audit payload extensions that preserve LOCKED_AUDIT_EVENTS + AUDIT_PAYLOAD_SCHEMAS registries.

**However, three CRITICAL findings from 33-REVIEW.md** (CR-01, CR-02, CR-03) describe a real data-integrity defect in the Idempotency-Key implementation:

- The Redis key derivation `_redis_key(key)` binds ONLY the header value, not the route.
- SUMMARY documents in 33-02 and 33-03 falsely claim the route is included.
- The router uses a manual two-phase pattern without `begin_idempotency` NX claim, leaving a TOCTOU window where concurrent same-key requests both execute the orchestrator.

These defects are NOT required to be fixed for the phase goal to be reached (sale/cancel/refund/cron all FUNCTION correctly under non-pathological conditions; the DB partial UNIQUEs `uq_pt_packages_active_per_client` and `uq_payments_refund_of_alive` still prevent the worst-case duplicate inserts). But they undermine the operator-UX guarantees of Idempotency-Key that this phase explicitly claims (D-33-16) and that 33-02 + 33-03 SUMMARY explicitly assert.

**Recommended next step:** Surface this to the developer for one of these decisions:
- **Option A (Accept + Document)**: Add an operational-constraint note to docs saying "Operators MUST use distinct Idempotency-Key values across the 3 mutating PT-package endpoints." Update router.py:340-349 comment to match reality. Defer route-binding to v1.5.
- **Option B (Phase 33-04 closure)**: Spin a small closure plan to implement route binding in `_redis_key` + adopt `idempotent_response` helper across all 3 PT-package routes + symmetric fixes on Phase 32 memberships. Add CR-02 regression test (concurrent /cancel).
- **Option C (Block Phase 34)**: Treat CR-01/02 as a Phase-34 prerequisite given that Phase 34 PT-sessions will introduce more idempotent endpoints and inherit the same defect surface.

Additionally, **6 integration test files** for Phase 33 (sale, read APIs, cancel, refund, refund_race, cron, plans_crud) require a Postgres environment to run. The conftest pattern skips them cleanly locally. CI must run them to confirm end-to-end behaviour — SUMMARY claims they pass in CI but no CI evidence is present in this verification.

---

_Verified: 2026-05-15T20:11:18Z_
_Verifier: Claude (gsd-verifier)_

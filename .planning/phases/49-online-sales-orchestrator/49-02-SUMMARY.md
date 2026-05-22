---
phase: 49-online-sales-orchestrator
plan: 02
subsystem: online_payments
tags: [yookassa, online-payments, import-linter, exceptions, di]

requires:
  - phase: 49-online-sales-orchestrator
    plan: 01
    provides: online_payments table (Alembic 0034) + YooKassaClient.create_payment (UUID|str, confirmation_type) + YooKassaPaymentResult.qr_payload
provides:
  - app.modules.online_payments Python package (real on-disk module)
  - OnlinePayment ORM model (mirrors Alembic 0034 column-for-column)
  - insert_online_payment + get_online_payment_by_id + get_online_payment_by_idempotency_key (D-49-07)
  - ErrorCode StrEnum + status/confirmation_type/subject_kind literal constants
  - app.modules.online_payments registered in [importlinter:contract:modules-independent]
  - SINGLE D-49-13 ignore `online_payments.service -> clients.models` (no widening)
  - ClientEmailRequiredForOnlinePaymentError (422, locked code per PAY-06)
  - ServiceUnavailableAppError (503) + BadGatewayAppError (502)
  - get_yookassa_settings() @lru_cache factory in app.integrations.yookassa.settings (BLOCKER #5)
affects:
  - 49-03-PLAN (service-layer): can now import OnlinePayment / repository / constants / exceptions
  - 49-04-PLAN (router): can now `Depends(get_yookassa_settings)` and `Depends(YooKassaClientProvider)`
  - 49-05-PLAN (return-screen): no direct dependency but unblocked by Wave 1 completion
  - 49-06-PLAN (composition-root): can register Phase 49 activators / dispatcher

tech-stack:
  added: []
  patterns:
    - "CheckConstraint BARE-name discipline: NAMING_CONVENTION expands `ck_%(table_name)s_%(constraint_name)s`; using full names double-prefixes (Plan 49-01 deviation #2 lesson preserved)"
    - "Composition-root-friendly lru_cache factory for pydantic-settings — mirrors webhook_verifier.py:60 module-level pattern"
    - "Narrow per-edge ignore_imports (D-49-13) following Phase 45 NOTIFY-11/12/13 precedent"
    - "Phase-deferred placeholder modules (email_templates, permissions) to MATCH preemptive Phase 47 INFRA-40 ignores"

key-files:
  created:
    - apps/backend/app/modules/online_payments/__init__.py
    - apps/backend/app/modules/online_payments/constants.py
    - apps/backend/app/modules/online_payments/models.py
    - apps/backend/app/modules/online_payments/repository.py
    - apps/backend/app/modules/online_payments/email_templates.py
    - apps/backend/app/modules/online_payments/permissions.py
  modified:
    - apps/backend/.importlinter
    - apps/backend/app/core/exceptions.py
    - apps/backend/app/integrations/yookassa/settings.py

key-decisions:
  - "CheckConstraint names use bare suffixes (`amount_kopecks_positive`) so NAMING_CONVENTION expands once; plan-prescribed full names would double-prefix"
  - "Partial UNIQUE per-day expression uses `((initiated_at AT TIME ZONE 'Europe/Moscow')::date)` to match Alembic 0034 (IMMUTABLE) — NOT `DATE(initiated_at)` which Postgres rejects on partial-index predicates"
  - "EXACTLY ONE new ignore_imports edge added (D-49-13 clients.models) — no widening to memberships.models or pt_packages.models (BLOCKER #3)"
  - "get_yookassa_settings shipped as @lru_cache factory (not module-level Final) so test isolation + Plan 49-04 Depends() target both work cleanly"

requirements-completed: [PAY-01, PAY-02, PAY-06]

duration: 25min
completed: 2026-05-22
---

# Phase 49 Plan 02: online_payments Module Skeleton + Import-Linter Wiring + Phase 49 Exceptions + YooKassa Settings Factory Summary

**Landed the `app.modules.online_payments` Python package (real ORM + repository + constants + Phase-52/50 placeholders) AND wired it into `import-linter` so the Phase 47 INFRA-40 Option A deferral closes; shipped 3 new exception subclasses for Phase 49 service-layer error codes; shipped `get_yookassa_settings` `@lru_cache` factory so Plan 49-04 router has a working `Depends()` target.**

## Performance

- **Duration:** ~25 min
- **Tasks:** 2 (both `type="auto"`)
- **Files modified:** 9 (6 created + 3 modified)
- **Commits:** 2 (one per task)

## Accomplishments

- **`app.modules.online_payments` resolves as a real on-disk Python package** with 6 files: `__init__.py`, `constants.py`, `models.py`, `repository.py`, `email_templates.py` (Phase 52 placeholder), `permissions.py` (D-49-24 placeholder).
- **`OnlinePayment` ORM mirrors Alembic 0034 column-for-column.** Class composition is `Base + UUIDPkMixin` (no TimestampMixin / SoftDeleteMixin — `initiated_at` / `succeeded_at` / `canceled_at` are the single-temporal columns per D-32-01..04 lineage). 4 FK columns (clients / membership_plans / pt_package_plans / users), 4 CheckConstraints (amount > 0, status enum, confirmation_type enum, XOR subject FKs), 2 UniqueConstraints (yookassa_payment_id, idempotency_key), 2 partial UNIQUE double-tap indexes keyed on `((initiated_at AT TIME ZONE 'Europe/Moscow')::date)` (IMMUTABLE — matches migration verbatim).
- **Repository ships caller-owns-txn `insert_online_payment` + `get_online_payment_by_id` + `get_online_payment_by_idempotency_key`** (D-49-07). No `session.flush()` / `session.commit()` calls — service-layer owns the transactional moment so audit rows co-write with the INSERT in a single UoW. No UPDATE methods (status transitions are Phase 50 webhook FSM).
- **`constants.py`** ships `ErrorCode` StrEnum (4 members) + status/confirmation_type/subject_kind literal constants + tuple `_VALUES` for AST-pinning. All literals match the Alembic 0034 CHECK constraint values.
- **`.importlinter` modules-independent contract** now includes `app.modules.online_payments` alphabetically (between `notifications` and `payments`). The Phase 47 INFRA-40 deferral comment block was tightened to a one-line "closed by Phase 49 D-49-02" marker.
- **EXACTLY ONE new `ignore_imports` entry** added: `app.modules.online_payments.service -> app.modules.clients.models` (D-49-13 — `clients.email` gate read; service-layer scoped). BLOCKER #3 / D-49-03 invariant preserved — NO widening to `memberships.models` or `pt_packages.models`.
- **`lint-imports` exits 0 with 3 contracts kept.** 4 warn-level unmatched ignores remain (all expected — `online_payments.service` will exist after Plan 49-03; `email_templates` body lands in Phase 52).
- **`app/core/exceptions.py`** gains 3 new subclasses: `ClientEmailRequiredForOnlinePaymentError` (`ValidationAppError` subclass, 422, locked code `client_email_required_for_online_payment` per PAY-06 / ROADMAP.md success-criterion #3); `ServiceUnavailableAppError` (`AppError` subclass, 503, code `service_unavailable`); `BadGatewayAppError` (`AppError` subclass, 502, code `bad_gateway`). All three follow the project's class-attribute `code: str` + `status_code: int` mechanism — registered FastAPI exception handler maps them to JSON responses automatically.
- **`app/integrations/yookassa/settings.py`** ships `@lru_cache(maxsize=1) get_yookassa_settings()` factory (BLOCKER #5). pydantic-settings reads `.env` on instantiation; `lru_cache` ensures every `Depends(get_yookassa_settings)` callsite receives the same instance. Mirrors the module-level `_settings: Final[YooKassaSettings] = YooKassaSettings()` pattern at `webhook_verifier.py:60`. Verified instance identity (`s1 is s2`).

## Task Commits

1. **Task 1 — scaffold online_payments package (ORM + repo + constants + placeholders):** `88fe654` (feat)
2. **Task 2 — wire import-linter + add Phase 49 exceptions + yookassa settings factory:** `36255d1` (feat)

## Files Created/Modified

### Created (Task 1)

- `apps/backend/app/modules/online_payments/__init__.py` — module docstring marker
- `apps/backend/app/modules/online_payments/constants.py` — `ErrorCode` StrEnum + literals (`STATUS_*`, `CONFIRMATION_TYPE_*`, `SUBJECT_KIND_*`)
- `apps/backend/app/modules/online_payments/models.py` — `OnlinePayment` ORM class; matches 0034 column-for-column; constraint names align with `op.f()`-derived migration names
- `apps/backend/app/modules/online_payments/repository.py` — caller-owns-txn INSERT + 2 GET helpers
- `apps/backend/app/modules/online_payments/email_templates.py` — empty placeholder; satisfies `app.integrations.email.dispatcher → app.modules.online_payments.email_templates` ignore (warn-level until Phase 52 ships bodies)
- `apps/backend/app/modules/online_payments/permissions.py` — empty placeholder (D-49-24 — no local can-checks needed)

### Modified (Task 2)

- `apps/backend/.importlinter` — append `app.modules.online_payments` to `[importlinter:contract:modules-independent] modules =`; replace Phase 47 INFRA-40 deferral comment with one-line "closed" marker; add EXACTLY ONE new ignore `online_payments.service -> clients.models` (D-49-13).
- `apps/backend/app/core/exceptions.py` — 3 new subclasses after `ValidationAppError` (line 48).
- `apps/backend/app/integrations/yookassa/settings.py` — `from functools import lru_cache` + `@lru_cache(maxsize=1) get_yookassa_settings()` factory.

## .importlinter Diff Summary

```diff
 modules =
     ...
     app.modules.notifications
+    app.modules.online_payments
     app.modules.payments
     ...
     app.modules.users
-    # Phase 47 INFRA-40 — Option A deferral (2026-05-21):
-    # [9-line deferral note ...]
+    # Phase 47 INFRA-40 — Option A deferral closed by Phase 49 D-49-02
+    # (2026-05-22): `app.modules.online_payments` is registered above, the
+    # 3 INFRA-40 ignore edges + the email dispatcher edge resolve to matched
+    # imports, and the contract is fully active.
 ignore_imports =
     ...
     app.modules.online_payments.service -> app.modules.payments.models
     app.modules.online_payments.service -> app.modules.users.display
+    # Phase 49 PAY-06 / D-49-13 — clients.email gate read; service-layer
+    # scoped; no widening to repository. Mirrors Phase 45 NOTIFY-11/12/13
+    # narrow-scope precedent at lines 63-80 above. BLOCKER #3 / D-49-03:
+    # NO additional cross-module ignores beyond clients models — Plan 49-03
+    # reads other subject tables via raw SQL `text()` SELECT (no ORM import).
+    app.modules.online_payments.service -> app.modules.clients.models
```

EXACTLY ONE new ignore_imports edge — BLOCKER #3 / D-49-03 invariant preserved.

## `lint-imports` Output

```
Contracts: 3 kept, 0 broken.

Warnings (all expected — Plan 49-03 service.py + Phase 52 email_templates fill these):
- No matches for ignored import app.modules.online_payments.service -> app.modules.clients.models.
- No matches for ignored import app.modules.online_payments.service -> app.modules.users.display.
- No matches for ignored import app.modules.online_payments.service -> app.modules.payments.models.
- No matches for ignored import app.integrations.email.dispatcher -> app.modules.online_payments.email_templates.
```

Exit status: 0. All 3 contracts kept; 4 warn-level unmatched ignores remain — every one resolves in a later plan/phase (3 land in Plan 49-03 when service.py ships; 1 lands in Phase 52 when email_templates body ships).

## Decisions Made

- **CheckConstraint names use BARE suffixes (`amount_kopecks_positive`, `status`, `confirmation_type`, `exactly_one_subject_fk`).** Plan 49-02 spec used full names (`ck_online_payments_*`); applying the NAMING_CONVENTION template would double-prefix to `ck_online_payments_ck_online_payments_*`. This is the same class of bug that Plan 49-01 deviation #2 had to fix in the migration body. The migration uses `op.f("ck_online_payments_*")` which writes the literal verbatim; the ORM must produce the same literal via the convention. Verified by introspecting `OnlinePayment.__table__.constraints` — names match Alembic 0034 byte-for-byte.
- **Partial UNIQUE per-day expression uses `((initiated_at AT TIME ZONE 'Europe/Moscow')::date)`.** Plan 49-02 spec had `DATE(initiated_at)`; Postgres rejects that in partial-index predicates because `DATE(timestamptz)` depends on session `TimeZone` and is therefore not IMMUTABLE. Migration 0034 (shipped in Plan 49-01 with deviation #1) uses the `AT TIME ZONE` form; ORM mirrors verbatim.
- **`get_yookassa_settings` is a `@lru_cache(maxsize=1)` factory, NOT a module-level `Final[YooKassaSettings] = YooKassaSettings()`.** Module-level instantiation crashes at import time when env vars are missing (test isolation lossage). The factory pattern defers instantiation until first call, cooperates cleanly with pytest monkeypatch.setenv, and gives Plan 49-04 the `Depends(get_yookassa_settings)` target it needs.
- **EXACTLY ONE new ignore_imports edge** (`online_payments.service -> clients.models`). BLOCKER #3 / D-49-03: Plan 49-03 reads `membership_plans` + `pt_package_plans` via raw SQL `text()` SELECT (no ORM-class import), so no widening to `memberships.models` / `pt_packages.models` is required.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 — Bug] `__all__` in `constants.py` not isort-sorted**
- **Found during:** Task 1 ruff check
- **Issue:** Plan-provided `__all__` tuple listed members in semantic order (`ErrorCode` first, then `STATUS_*`, then `CONFIRMATION_TYPE_*`, then `SUBJECT_KIND_*`). ruff RUF022 requires isort-style sort.
- **Fix:** `uv run ruff check --fix` applied the isort-style sort (alphabetical, with `ErrorCode` last because PascalCase sorts after UPPER_SNAKE_CASE in this isort convention).
- **Files modified:** `apps/backend/app/modules/online_payments/constants.py`
- **Committed in:** `88fe654`

**2. [Rule 1 — Bug] `session.scalar()` returns `Any`, breaking strict mypy `no-any-return`**
- **Found during:** Task 1 mypy check
- **Issue:** Plan-provided `return await session.scalar(stmt)` triggers `error: Returning Any from function declared to return "OnlinePayment | None"  [no-any-return]`. SQLAlchemy's `session.scalar` is typed as `-> Any` in the project's type checker.
- **Fix:** Used the explicit intermediate-variable type-narrowing pattern from `app/modules/payments/repository.py:98`: `result: OnlinePayment | None = await session.scalar(stmt); return result`. Applied to both `get_online_payment_by_id` and `get_online_payment_by_idempotency_key`.
- **Files modified:** `apps/backend/app/modules/online_payments/repository.py`
- **Committed in:** `88fe654`

**3. [Rule 1 — Bug] Plan-prescribed full CheckConstraint names would double-prefix under NAMING_CONVENTION**
- **Found during:** Task 1 model-write planning (caught before any test run by reading `app/modules/payments/models.py` lines 102, 107 — explicit bare-name convention)
- **Issue:** Plan 49-02 spec literally specified `name="ck_online_payments_amount_kopecks_positive"` for each CheckConstraint. `Base.metadata` is initialized with `MetaData(naming_convention=NAMING_CONVENTION)` where `ck` template is `ck_%(table_name)s_%(constraint_name)s` — feeding it a full name produces `ck_online_payments_ck_online_payments_amount_kopecks_positive` (the exact bug Plan 49-01 deviation #2 fixed in the migration).
- **Fix:** Used bare suffixes (`amount_kopecks_positive`, `status`, `confirmation_type`, `exactly_one_subject_fk`) so the convention expands to the literal Alembic 0034 wrote via `op.f()`. Verified via `OnlinePayment.__table__.constraints` introspection that names match migration byte-for-byte.
- **Files modified:** `apps/backend/app/modules/online_payments/models.py` (caught at write time — no separate fix commit)
- **Committed in:** `88fe654`

**4. [Rule 1 — Bug] Plan-prescribed `DATE(initiated_at)` partial-index expression not IMMUTABLE**
- **Found during:** Task 1 model-write planning (caught before any test run by reading `apps/backend/alembic/versions/0034_online_payments.py:137` — `((initiated_at AT TIME ZONE 'Europe/Moscow')::date)`)
- **Issue:** Plan 49-02 spec used `text("DATE(initiated_at)")` for both partial UNIQUE double-tap indexes. Postgres rejects `DATE(timestamptz)` in partial-index predicates because the function is not IMMUTABLE (result depends on session `TimeZone` GUC). This is the same bug Plan 49-01 deviation #1 fixed in the migration.
- **Fix:** Mirror the migration's expression — `text("((initiated_at AT TIME ZONE 'Europe/Moscow')::date)")`. ORM index expression now matches migration verbatim.
- **Files modified:** `apps/backend/app/modules/online_payments/models.py` (caught at write time — no separate fix commit)
- **Committed in:** `88fe654`

**5. [Rule 1 — Bug] grep false-positive comment text triggered "forbidden widening" check**
- **Found during:** Task 2 acceptance-criteria grep (`memberships\.models|pt_packages\.models|pt_package_plans` matched count 1)
- **Issue:** The new D-49-13 comment block originally referenced "memberships_plans + pt_package_plans" as part of explaining what NOT to add. The acceptance criterion `grep -c "memberships.models|pt_packages.models|pt_package_plans" .importlinter` returned 1 instead of 0 — a false positive because the rationale comment used the same token names. No real ignore_imports widening occurred.
- **Fix:** Reworded the comment ("Plan 49-03 reads other subject tables via raw SQL text() SELECT") so the grep returns 0 while preserving the BLOCKER #3 documentation intent.
- **Files modified:** `apps/backend/.importlinter`
- **Committed in:** `36255d1`

---

**Total deviations:** 5 auto-fixed (4 Rule-1 bugs from plan-prescribed text mismatching project conventions, 1 Rule-1 documentation polish to satisfy a literal grep criterion). All five were caught either at write time (by reading the migration / payments-model precedents) or at first tool run (ruff / mypy). Zero scope creep — every change preserves the plan's intent.

## Issues Encountered

- **None.** Pre-existing ruff warnings in `app/modules/bookings/`, `app/modules/pt_sessions/`, `tests/unit/integrations/email/`, and `scripts/verify/` are out of scope per SCOPE BOUNDARY (not caused by this plan; not adjacent to files modified). Logged historically — no new entries added to `deferred-items.md`.

## Acceptance Criteria Verification

### Task 1

| Criterion | Result |
|----------|--------|
| All 6 files exist under `apps/backend/app/modules/online_payments/` | PASS |
| `grep -c "class OnlinePayment" models.py` returns 1 | PASS (1) |
| `grep -c "CheckConstraint" models.py` returns ≥ 4 (4 actual + 2 docstring/import) | PASS (6 total occurrences; 4 actual constraints) |
| `grep -c "UniqueConstraint" models.py` returns ≥ 2 (2 actual + 2 docstring/import) | PASS (4 total occurrences; 2 actual constraints) |
| `grep -c "postgresql_where" models.py` returns 2 | PASS (2) |
| `grep -n "pt_package_plans\.id" models.py` returns 1 match | PASS (1) |
| `grep -c "async def insert_online_payment" repository.py` returns 1 | PASS (1) |
| `grep -c "async def get_online_payment_by_idempotency_key" repository.py` returns 1 | PASS (1) |
| `grep -c "class ErrorCode" constants.py` returns 1 | PASS (1) |
| `python -c "...assert OnlinePayment.__tablename__ == 'online_payments'"` exits 0 | PASS |
| `uv run ruff check app/modules/online_payments/` exits 0 | PASS |
| `uv run mypy app/modules/online_payments/` exits 0 | PASS (6 source files) |

### Task 2

| Criterion | Result |
|----------|--------|
| `grep -c "^    app\.modules\.online_payments$" .importlinter` returns 1 | PASS (1) |
| `grep -c "online_payments.service -> ... clients.models" .importlinter` returns 1 | PASS (1) |
| `grep -c "online_payments.service ->" .importlinter` returns 3 (D-49-29 payments.models + D-49-30 users.display + D-49-13 clients.models) | PASS (3) |
| `grep -cE "memberships\.models\|pt_packages\.models\|pt_package_plans" .importlinter` returns 0 | PASS (0) |
| `uv run lint-imports` exits 0 (all contracts kept) | PASS (3 kept, 0 broken) |
| `class ClientEmailRequiredForOnlinePaymentError` in exceptions.py | PASS |
| `client_email_required_for_online_payment` literal in exceptions.py | PASS (2 — class docstring + code) |
| `class ServiceUnavailableAppError` in exceptions.py | PASS |
| `class BadGatewayAppError` in exceptions.py | PASS |
| `grep -c "^def get_yookassa_settings" settings.py` returns 1 | PASS (1) |
| `grep -c "@lru_cache" settings.py` returns 1 | PASS (2 — `from functools import lru_cache` + `@lru_cache(maxsize=1)`) |
| `uv run pytest tests/unit/test_app_exceptions.py -x -q` | SKIPPED (file does not exist; acceptance criterion explicitly allows skip) |
| `uv run mypy app/core/exceptions.py app/integrations/yookassa/settings.py` exits 0 | PASS |
| `uv run pytest tests/unit/integrations/yookassa/test_settings.py` exits 0 | PASS (5 passed) |

## Settings Factory Verification

```python
from app.integrations.yookassa.settings import get_yookassa_settings, YooKassaSettings
s1 = get_yookassa_settings()
s2 = get_yookassa_settings()
assert s1 is s2                            # PASS — lru_cache memoization works
assert isinstance(s1, YooKassaSettings)    # PASS — correct type
```

## ORM ↔ Migration Constraint-Name Verification

Introspected `OnlinePayment.__table__.constraints` and `.indexes`:

| ORM bare name | NAMING_CONVENTION expansion | Migration `op.f()` name | Match |
|---|---|---|---|
| `amount_kopecks_positive` | `ck_online_payments_amount_kopecks_positive` | `ck_online_payments_amount_kopecks_positive` | YES |
| `status` | `ck_online_payments_status` | `ck_online_payments_status` | YES |
| `confirmation_type` | `ck_online_payments_confirmation_type` | `ck_online_payments_confirmation_type` | YES |
| `exactly_one_subject_fk` | `ck_online_payments_exactly_one_subject_fk` | `ck_online_payments_exactly_one_subject_fk` | YES |
| `uq_online_payments_yookassa_payment_id` (full literal) | (unchanged) | `uq_online_payments_yookassa_payment_id` | YES |
| `uq_online_payments_idempotency_key` (full literal) | (unchanged) | `uq_online_payments_idempotency_key` | YES |
| `fk_online_payments_*` (full literal × 4) | (unchanged) | `fk_online_payments_*` | YES |
| Index `uq_online_payments_membership_double_tap` | (full literal) | (full literal) | YES |
| Index `uq_online_payments_pt_package_double_tap` | (full literal) | (full literal) | YES |

All 11 constraint / index names match migration 0034 byte-for-byte.

## User Setup Required

None — no external service configuration introduced by this plan. The `get_yookassa_settings()` factory will read env vars on first invocation (Plan 49-04 router will be the first runtime call site); .env / .env.example already has placeholder values from Phase 47.

## Next Phase Readiness

- **Plan 49-03 (service-layer)** unblocked: can import `OnlinePayment`, the three repository helpers, the four `ErrorCode` enum members, and the three new `app.core.exceptions` subclasses. The D-49-13 `clients.models` ignore is registered, so the service-layer email-gate read will not break the import-linter contract.
- **Plan 49-04 (router)** unblocked: can `Depends(get_yookassa_settings)` to inject `YooKassaSettings.return_url` into the receipt-assembly helper without changing composition-root wiring.
- **Plan 49-05 (return-screen)** has no direct dependency on this plan but proceeds in parallel with 49-03/04/06 in Wave 2.
- **Plan 49-06 (composition-root)** unblocked: can register the Phase 49 activator stubs against the four v1.7 Protocol slots.

## Threat Model Check

The 3 mitigations from this plan's `<threat_model>` block landed:

- **T-49-02-01 (EoP — ignore_imports widening):** Narrow-scope D-49-13 ignore restricted to `service.py`; inline rationale comment cites Phase 45 NOTIFY-11/12/13 precedent; `unmatched_ignore_imports_alerting = warn` preserved. NO widening to `memberships.models` or `pt_packages.models` (BLOCKER #3 enforced).
- **T-49-02-02 (Tampering — ORM drift):** Column-for-column mirror verified by `OnlinePayment.__table__` introspection. Plan 49-07 will add the runtime drift assertion.
- **T-49-02-04 (Info Disclosure — lru_cache surfaces SecretStr):** Same surface as the existing `webhook_verifier.py:60` module-level instance; `secret_key: SecretStr` is already redacted by the structlog formatter. lru_cache instance lifetime is process-scoped — no cross-process leakage.

## Self-Check: PASSED

Verified all claimed files and commits exist:

- `apps/backend/app/modules/online_payments/__init__.py` — FOUND
- `apps/backend/app/modules/online_payments/constants.py` — FOUND
- `apps/backend/app/modules/online_payments/models.py` — FOUND
- `apps/backend/app/modules/online_payments/repository.py` — FOUND
- `apps/backend/app/modules/online_payments/email_templates.py` — FOUND
- `apps/backend/app/modules/online_payments/permissions.py` — FOUND
- `apps/backend/.importlinter` — modified, FOUND
- `apps/backend/app/core/exceptions.py` — modified, FOUND
- `apps/backend/app/integrations/yookassa/settings.py` — modified, FOUND
- Commit `88fe654` — FOUND (Task 1)
- Commit `36255d1` — FOUND (Task 2)

---
*Phase: 49-online-sales-orchestrator*
*Completed: 2026-05-22*

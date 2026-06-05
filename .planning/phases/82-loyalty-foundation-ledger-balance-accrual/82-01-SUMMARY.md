---
phase: 82
plan: "01"
subsystem: backend
tags: [loyalty, ledger, audit, migration, schema]
dependency_graph:
  requires: []
  provides:
    - loyalty_ledger table (append-only, signed amount_kopecks, entry_type CHECK, partial UNIQUE)
    - LoyaltyLedger ORM model (app.modules.loyalty.models)
    - loyalty_accrued LOCKED audit event + LoyaltyAccruedPayload
    - importlinter registration for app.modules.loyalty
  affects:
    - alembic/env.py (model registration + promo_codes gap fix + clients type fix)
    - app/core/audit.py (LOCKED_AUDIT_EVENTS 101→102)
    - app/core/audit_payloads.py (LoyaltyAccruedPayload + registry)
    - apps/backend/.importlinter (modules-independent contract)
tech_stack:
  added:
    - app.modules.loyalty (new backend module, importlinter-registered)
  patterns:
    - Append-only ledger (Base + UUIDPkMixin only, single created_at)
    - Signed amount_kopecks (positive=accrual, negative=redemption)
    - Partial UNIQUE via literal-name index (uq_loyalty_ledger_welcome)
    - INFRA-15 audit event pre-registration before callsite
key_files:
  created:
    - apps/backend/app/modules/loyalty/__init__.py
    - apps/backend/app/modules/loyalty/models.py
    - apps/backend/alembic/versions/0054_loyalty_ledger.py
    - apps/backend/tests/unit/test_loyalty_audit_events.py
  modified:
    - apps/backend/alembic/env.py
    - apps/backend/.importlinter
    - apps/backend/app/core/audit.py
    - apps/backend/app/core/audit_payloads.py
    - apps/backend/tests/unit/test_audit_taxonomy.py
    - apps/backend/tests/integration/test_phase51_audit_chain_invariants.py
    - apps/backend/app/modules/clients/models.py
decisions:
  - "LoyaltyLedger: Base + UUIDPkMixin only (no TimestampMixin/SoftDeleteMixin), single created_at"
  - "entry_type CHECK bare-suffix naming convention (expands to ck_loyalty_ledger_entry_type)"
  - "Partial UNIQUE uq_loyalty_ledger_welcome uses literal index name (not op.f()) per 0034/0037/0046 precedent"
  - "Both loyalty indexes excluded from alembic autogenerate _include_object (partial index pattern)"
  - "Single loyalty_accrued event covers welcome + owner_grant (entry_type/actor distinguish in payload)"
  - "LoyaltyAccruedPayload entry_type: Literal['welcome','owner_grant'] — redemption excluded (Phase 83)"
  - "promo_codes.models registered in env.py (pre-existing gap fixed as deviation Rule 1)"
  - "clients.models onboarding_completed_at typed as explicit DateTime(timezone=True) (pre-existing drift fixed)"
metrics:
  duration_minutes: 35
  completed_date: "2026-06-05"
  tasks_completed: 2
  tasks_total: 2
  files_created: 4
  files_modified: 7
---

# Phase 82 Plan 01: Loyalty Foundation — Ledger Schema + Audit Lock Summary

**One-liner:** Append-only loyalty_ledger table (signed kopecks, partial-UNIQUE welcome, RESTRICT FK) + loyalty_accrued LOCKED audit event with LoyaltyAccruedPayload(extra=forbid) pre-registered before callsite per INFRA-15.

## Tasks Completed

| Task | Name | Commit | Files |
|------|------|--------|-------|
| 1 | LoyaltyLedger model + migration 0054 + env.py + importlinter | 386a07cd | loyalty/__init__.py, models.py, 0054_loyalty_ledger.py, env.py, .importlinter, clients/models.py |
| 2 | Register loyalty_accrued LOCKED audit event + payload + count-lock bump | 76fc93d2 | audit.py, audit_payloads.py, test_audit_taxonomy.py, test_phase51_..., test_loyalty_audit_events.py |
| style | Fix ruff E501 in env.py | f3ea85b9 | alembic/env.py |

## Verification Results

- `uv run alembic upgrade head` — migration 0054 applied successfully
- `uv run alembic check` — No new upgrade operations detected (GREEN)
- `uv run lint-imports` — All 3 contracts KEPT (5 pre-existing warnings, no new edges)
- `uv run mypy --strict app/modules/loyalty app/core/audit_payloads.py` — Success: no issues
- `uv run ruff check` (modified files) — All checks passed
- `uv run pytest tests/unit/test_loyalty_audit_events.py tests/unit/test_audit_taxonomy.py tests/integration/test_phase51_audit_chain_invariants.py -q` — 21 passed

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] Fixed pre-existing promo_codes env.py registration gap**
- **Found during:** Task 1 verification (alembic check)
- **Issue:** `app.modules.promo_codes.models` was never imported in `alembic/env.py`, causing `alembic check` to fail with `NoReferencedTableError` (online_payments.promo_code_id FK cannot resolve promo_codes table). Noted as pre-existing tech debt in STATE.md.
- **Fix:** Added `import app.modules.promo_codes.models` to env.py registration block
- **Files modified:** `apps/backend/alembic/env.py`
- **Commit:** 386a07cd

**2. [Rule 1 - Bug] Fixed pre-existing clients.onboarding_completed_at type drift**
- **Found during:** Task 1 verification (alembic check after promo_codes fix)
- **Issue:** `onboarding_completed_at` in `clients/models.py` used implicit type inference (`mapped_column(nullable=True)`) while DB has `TIMESTAMPTZ`. Alembic autogenerate detected `TIMESTAMP(timezone=True) vs DateTime()` mismatch.
- **Fix:** Added explicit `DateTime(timezone=True)` to the column definition
- **Files modified:** `apps/backend/app/modules/clients/models.py`
- **Commit:** 386a07cd

**3. [Rule 2 - Missing] Excluded loyalty indexes from alembic autogenerate _include_object**
- **Found during:** Task 1 verification (alembic check partial-index drift)
- **Issue:** Both `uq_loyalty_ledger_welcome` (partial UNIQUE, literal name) and `ix_loyalty_ledger_client_id` were detected as "removed" by autogenerate since ORM model doesn't declare them as `Index` objects (matches promo_codes pattern).
- **Fix:** Added both index names to `_include_object` exclusion list in `alembic/env.py`
- **Files modified:** `apps/backend/alembic/env.py`
- **Commit:** 386a07cd

**4. [Rule 1 - Style] Fixed ruff E501 in env.py comment**
- **Found during:** Final ruff check
- **Issue:** promo_codes comment exceeded 100-char line limit
- **Fix:** Shortened comment text
- **Files modified:** `apps/backend/alembic/env.py`
- **Commit:** f3ea85b9

## Known Stubs

None — this plan only creates schema/model/audit foundation. No data-flow stubs.

## Threat Flags

No new threat surface beyond what is documented in the plan threat model (T-82-01..04).

## Self-Check: PASSED

- `apps/backend/app/modules/loyalty/__init__.py` — FOUND
- `apps/backend/app/modules/loyalty/models.py` — FOUND (LoyaltyLedger class present)
- `apps/backend/alembic/versions/0054_loyalty_ledger.py` — FOUND
- `apps/backend/tests/unit/test_loyalty_audit_events.py` — FOUND
- Commit 386a07cd — FOUND (feat: LoyaltyLedger model + migration)
- Commit 76fc93d2 — FOUND (feat: loyalty_accrued audit event)
- Count-lock guards: both assert 102 — VERIFIED
- `grep -c '("loyalty_accrued", "loyalty")' audit.py` returns 1 — VERIFIED

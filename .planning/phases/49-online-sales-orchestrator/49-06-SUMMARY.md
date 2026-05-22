---
phase: 49-online-sales-orchestrator
plan: 06
subsystem: composition-root
tags:
  - composition-root
  - protocol-slots
  - parity-test
  - REG-29-03
  - D-49-21
  - D-49-22
  - D-49-23
dependency_graph:
  requires:
    - 49-03  # phase49_fiscal_dispatcher_stub provider
  provides:
    - v1.7 Protocol slot composition-root wiring (all 4 slots non-None at startup)
    - Roadmap success-criterion #6 parity test
  affects:
    - app/main.py — register_* block (3 swaps)
    - app/workers/__init__.py — REG-29-03 double-wire for FiscalReceiptDispatcher
    - tests/unit/test_yookassa_protocol_slot_parity.py — byte-equal target updated
tech_stack:
  added: []
  patterns:
    - REG-29-03 byte-equal double-wire (FastAPI + ARQ worker register identical symbol)
    - HTTP-only single-wire (MembershipActivator + PtPackageActivator stay out of worker)
key_files:
  created:
    - apps/backend/tests/integration/test_v17_protocol_slot_parity.py
  modified:
    - apps/backend/app/modules/memberships/service.py
    - apps/backend/app/modules/pt_packages/service.py
    - apps/backend/app/main.py
    - apps/backend/app/workers/__init__.py
    - apps/backend/tests/unit/test_yookassa_protocol_slot_parity.py
decisions:
  - D-49-21 activator stubs land in their owning service modules (not _stubs.py)
  - D-49-22 FiscalReceiptDispatcher byte-equal target swapped to phase49_fiscal_dispatcher_stub
  - D-49-23 new integration parity test at tests/integration/test_v17_protocol_slot_parity.py
metrics:
  duration: ~12m
  completed: 2026-05-22
requirements:
  - PAY-08
---

# Phase 49 Plan 06: Composition-root wiring + v1.7 Protocol-slot parity test Summary

Wired all four v1.7 Protocol slots (`YooKassaClientProvider`,
`FiscalReceiptDispatcher`, `MembershipActivator`, `PtPackageActivator`) to
non-`None` implementations at the composition root, swapping the Phase 47
no-op stubs for Phase-49 stub-body callables (Phase 50 still owns the real
bodies), and shipped the parity test that asserts success-criterion #6.

## Tasks Executed

| # | Task | Commit |
|---|------|--------|
| 1 | Add `activate_*_from_webhook` stub bodies to memberships + pt_packages services (D-49-21) | `148a035` |
| 2 | Swap Phase 47 noop stubs at composition root + update existing parity test (D-49-22) | `4e2dcf8` |
| 3 | New integration parity test for all 4 slots non-None (D-49-23) | `339cee7` |

## What landed

### Activator stubs (D-49-21)

`activate_membership_from_webhook(session, *, membership_id, audit_correlation_id)`
and `activate_pt_package_from_webhook(session, *, pt_package_id, audit_correlation_id)`
appended to their owning service modules. Both raise `NotImplementedError`
citing Phase 50 WH-05. Each function structurally implements its
`MembershipActivator` / `PtPackageActivator` `Protocol` (verified via
`mypy app/modules/memberships/service.py app/modules/pt_packages/service.py`
exit 0).

### Composition-root register_* block in `app/main.py`

The final `create_app()` register_* block now reads:

```python
register_yookassa_client_provider(_yookassa_client_provider)

# Phase 49 PAY-08 / D-49-21 — HTTP-only single-wire activators (no ARQ entry path).
from app.modules.memberships.service import activate_membership_from_webhook
from app.modules.online_payments.service import phase49_fiscal_dispatcher_stub
from app.modules.pt_packages.service import activate_pt_package_from_webhook

register_membership_activator(activate_membership_from_webhook)
register_pt_package_activator(activate_pt_package_from_webhook)
# Phase 49 D-49-22 — FiscalReceiptDispatcher Phase-49-only bridge stub
# (REG-29-03 double-wire; mirror in workers/__init__.py). Phase 50 FISCAL-01
# replaces this with the real ARQ-enqueue body.
register_fiscal_receipt_dispatcher(phase49_fiscal_dispatcher_stub)
```

### Removed Phase 47 noop-stub imports

From `apps/backend/app/main.py`:

```python
from app.integrations.yookassa._stubs import (
    fiscal_receipt_dispatcher_noop_stub,
    membership_activator_noop_stub,
    pt_package_activator_noop_stub,
)
```

From `apps/backend/app/workers/__init__.py` (inside `on_startup`):

```python
from app.integrations.yookassa._stubs import (
    fiscal_receipt_dispatcher_noop_stub,
)
```

The `_stubs.py` module still defines the symbols — no deletion — so any
transitional consumer can still import them. Phase 49 simply stops
registering them at the composition root.

### Worker double-wire (`apps/backend/app/workers/__init__.py`)

`WorkerSettings.on_startup` now registers `phase49_fiscal_dispatcher_stub`
for the `FiscalReceiptDispatcher` slot — REG-29-03 double-wire mirror of
`app/main.py`. Activators (`register_membership_activator`,
`register_pt_package_activator`) are NOT called from the worker (verified
by `Test C` — grep `register_membership_activator` returns 0 in
`app/workers/__init__.py`).

### Existing unit parity test updated (`tests/unit/test_yookassa_protocol_slot_parity.py`)

- Imports `phase49_fiscal_dispatcher_stub`, `activate_membership_from_webhook`,
  `activate_pt_package_from_webhook`.
- `_worker_register_double_wired_slots` helper registers
  `phase49_fiscal_dispatcher_stub` (was `_stubs.fiscal_receipt_dispatcher_noop_stub`).
- `Test A` asserts `get_fiscal_receipt_dispatcher() is phase49_fiscal_dispatcher_stub`,
  `get_membership_activator() is activate_membership_from_webhook`,
  `get_pt_package_activator() is activate_pt_package_from_webhook`.
- `Test B` asserts `get_fiscal_receipt_dispatcher() is phase49_fiscal_dispatcher_stub`.
- `Test D` asserts `fastapi_fiscal is worker_fiscal is phase49_fiscal_dispatcher_stub`.
- `Test C` unchanged (negative-control for activator HTTP-only invariant).
- Module docstring extended with Phase 49 D-49-22 note.

### New integration parity test (`tests/integration/test_v17_protocol_slot_parity.py`)

Two test functions:

1. `test_v17_protocol_slots_non_none_after_app_startup` — Roadmap
   success-criterion #6: `_reset_v17_slots()` → `create_app()` → all
   4 accessors return non-`None`.
2. `test_fiscal_receipt_dispatcher_is_not_phase47_noop_stub_after_phase49`
   — regression guard against accidental rollback.

## Verification

| Gate | Command | Result |
|------|---------|--------|
| Unit parity test | `cd apps/backend && uv run pytest tests/unit/test_yookassa_protocol_slot_parity.py -x -q` | **4 passed** |
| Integration parity test | `cd apps/backend && uv run pytest tests/integration/test_v17_protocol_slot_parity.py -x -q` | **2 passed** |
| Combined | both files | **6 passed** |
| Ruff | `ruff check app/main.py app/workers/__init__.py tests/integration/test_v17_protocol_slot_parity.py tests/unit/test_yookassa_protocol_slot_parity.py apps/backend/app/modules/{memberships,pt_packages}/service.py` | clean |
| Mypy strict (target files) | `mypy app/main.py app/workers/__init__.py app/modules/memberships/service.py app/modules/pt_packages/service.py` | **no errors in target files** (pre-existing errors in unrelated `auth/router.py`, `online_payments/router.py`, etc.) |
| `lint-imports` | `uv run lint-imports` | **Contracts: 3 kept, 0 broken** |
| Smoke (4 slots non-None) | `uv run python` heredoc | `all 4 slots non-None` |
| **W5** grep count | `grep -c "phase49_fiscal_dispatcher_stub" apps/backend/tests/unit/test_yookassa_protocol_slot_parity.py` | **10 matches** (acceptance: ≥ 4) ✓ |

## Acceptance Criteria — All Met

| Criterion | Outcome |
|-----------|---------|
| `register_membership_activator(activate_membership_from_webhook)` in main.py | 1 match ✓ |
| `register_pt_package_activator(activate_pt_package_from_webhook)` in main.py | 1 match ✓ |
| `register_fiscal_receipt_dispatcher(phase49_fiscal_dispatcher_stub)` in main.py | 1 match ✓ |
| Same in workers/__init__.py | 1 match ✓ |
| `register_membership_activator` in workers/__init__.py | 0 matches ✓ |
| `register_pt_package_activator` in workers/__init__.py | 0 matches ✓ |
| `fiscal_receipt_dispatcher_noop_stub` in main.py | 0 matches ✓ |
| `membership_activator_noop_stub` in main.py | 0 matches ✓ |
| `pt_package_activator_noop_stub` in main.py | 0 matches ✓ |
| Parity test file exists | ✓ |
| `def test_` in new file | 2 matches ✓ |
| `is not None` in new file | 4 matches ✓ |
| **W5** `phase49_fiscal_dispatcher_stub` ≥ 4 matches in unit parity test | **10 matches** ✓ |

## Parity Test Pass Counts

- `tests/unit/test_yookassa_protocol_slot_parity.py`: **4 / 4**
- `tests/integration/test_v17_protocol_slot_parity.py`: **2 / 2**
- **Total: 6 / 6** (as expected by `<output>` block: 4 + 2 = 6)

## W5 Confirmation

`grep -c "phase49_fiscal_dispatcher_stub" apps/backend/tests/unit/test_yookassa_protocol_slot_parity.py` → **10** (≥ 4 acceptance holds).

## Deviations from Plan

None — plan executed exactly as written.

The single auto-fix was a ruff `I001` import-sort fix on
`tests/unit/test_yookassa_protocol_slot_parity.py` after the import-block
update (ruff `--fix`); no semantic change.

## Threat Model Outcomes

- **T-49-06-01** (Elevation of Privilege — accidentally promoting
  activators to worker): mitigated. `Test C` in unit parity test still
  asserts `register_membership_activator` / `register_pt_package_activator`
  do not appear in `app/workers/__init__.py` (verified by grep: 0 / 0).
- **T-49-06-02** (Tampering — premature swap to real implementation):
  mitigated. Activator and fiscal-dispatcher stubs all raise
  `NotImplementedError("Phase 50 ...")` — any caller path surfaces the
  raise rather than silent fall-through.
- **T-49-06-03** (Repudiation — lost audit chain on premature call):
  accepted. `NotImplementedError` is loud at the call site.
- **T-49-06-04** (DoS — repeated registration): accepted. `register_*`
  setters are idempotent (Phase 47 D-47-01 docstring) and tests reset
  between cases.

## Self-Check: PASSED

- File `apps/backend/tests/integration/test_v17_protocol_slot_parity.py`: FOUND
- File `apps/backend/app/modules/memberships/service.py` (touched): FOUND
- File `apps/backend/app/modules/pt_packages/service.py` (touched): FOUND
- File `apps/backend/app/main.py` (touched): FOUND
- File `apps/backend/app/workers/__init__.py` (touched): FOUND
- File `apps/backend/tests/unit/test_yookassa_protocol_slot_parity.py` (touched): FOUND
- Commit `148a035`: FOUND in `git log`
- Commit `4e2dcf8`: FOUND in `git log`
- Commit `339cee7`: FOUND in `git log`

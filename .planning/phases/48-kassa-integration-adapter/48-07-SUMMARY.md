---
phase: 48-kassa-integration-adapter
plan: 07
subsystem: integrations
tags: [composition-root, lifespan, on-startup, protocol-slot, reg-29-03, yookassa, d-48-25, d-48-26]
requires:
  - 48-03 (build_yookassa_client factory)
  - 47-04 (Phase 47 noop stub baseline + parity test)
provides:
  - YooKassaClient reachable from HTTP request path via deps.get_yookassa_client_provider()
  - YooKassaClient reachable from ARQ worker job path via ctx["yookassa_client"]
  - Lifecycle-bound long-lived httpx.AsyncClient (D-48-06)
affects:
  - apps/backend/app/main.py
  - apps/backend/app/workers/__init__.py
  - apps/backend/tests/unit/test_yookassa_protocol_slot_parity.py
tech-stack:
  added: []
  patterns: [lazy-app-state-closure, reg-29-03-double-wire, structural-source-parity]
key-files:
  created:
    - .planning/phases/48-kassa-integration-adapter/48-07-SUMMARY.md
  modified:
    - apps/backend/app/main.py
    - apps/backend/app/workers/__init__.py
    - apps/backend/tests/unit/test_yookassa_protocol_slot_parity.py
decisions:
  - D-48-25 enacted: real YooKassaClient wired into both composition roots; each process owns its own httpx.AsyncClient; parity test relaxed from object-identity to structural source-grep.
  - D-48-26 honored: fiscal_receipt_dispatcher / membership_activator / pt_package_activator stubs remain wired (swapped in Phase 49/50).
  - Closure name LOCKED as `_yookassa_client_provider` in both main.py and workers/__init__.py — the parity test asserts this literal name via `__name__` on the FastAPI side and source-grep on the worker side.
metrics:
  duration: ~30m
  tasks: 4
  files: 3
  completed: 2026-05-22
---

# Phase 48 Plan 07: Composition-Root Wiring Summary

YooKassaClient wired into both the FastAPI HTTP-request lifecycle and the ARQ worker job lifecycle via REG-29-03 double-wire, replacing the Phase 47 no-op stub registrations. Each process owns its own long-lived `httpx.AsyncClient` (D-48-06) created in lifespan/on_startup and closed in teardown/on_shutdown. The Phase 47 byte-equal parity test is relaxed to structural source-grep (D-48-25) because closures cannot be shared across process boundaries; the surviving Phase 47 byte-equal invariants for the three other v1.7 stubs (D-48-26) are preserved.

## Tasks Executed

| Task | Name | Commit | Files |
|------|------|--------|-------|
| 1 | Rewire app/main.py — lifespan construction + lazy create_app provider closure | `6e24009` | apps/backend/app/main.py |
| 2 | Mirror in app/workers/__init__.py — on_startup construction + on_shutdown teardown | `8afa0de` | apps/backend/app/workers/__init__.py |
| 3a | Rewrite parity Tests A + B (structural source-grep) + helper trim | `9da20fd` | apps/backend/tests/unit/test_yookassa_protocol_slot_parity.py |
| 3b | Rewrite parity Test D (closure-name `__name__` + source-grep) | `91ab217` | apps/backend/tests/unit/test_yookassa_protocol_slot_parity.py |

## Wiring Changes

### app/main.py (FastAPI HTTP composition root)

- **Imports**: added `YooKassaClient`, `build_yookassa_client`, `YooKassaSettings`; removed `yookassa_client_provider_noop_stub` from the `_stubs` import block. The three other stubs stay imported.
- **combined_lifespan**: after `arq_pool` init, `YooKassaSettings()` is constructed and `app.state.yookassa_client = await build_yookassa_client(settings=yookassa_settings)` runs. The `finally` block awaits `app.state.yookassa_client.aclose()` BEFORE `arq_pool.aclose()` (reverse-order teardown so the httpx pool drains while the event loop is still healthy).
- **create_app()**: a closure `async def _yookassa_client_provider() -> YooKassaClient: return app.state.yookassa_client` is registered via `register_yookassa_client_provider(_yookassa_client_provider)`. Mirrors the `set_auth_redis_factory(lambda: app.state.redis)` pattern (Phase 43 D-43-26). The three other Phase 47 stub registrations (fiscal/membership/pt_package) remain unchanged per D-48-26.

### app/workers/__init__.py (ARQ worker composition root)

- **Imports** (added inside `on_startup` import block, mirroring the email-factory locality): `YooKassaClient`, `build_yookassa_client`, `YooKassaSettings`. Removed `yookassa_client_provider_noop_stub` from the `_stubs` import; `fiscal_receipt_dispatcher_noop_stub` stays.
- **on_startup**: after `register_email_dispatcher(enqueue_email_dispatch)`, the worker constructs its own `YooKassaSettings()` + `await build_yookassa_client(...)` and stores the client on `ctx["yookassa_client"]`. A worker-local closure `_yookassa_client_provider` returns the cached client and is registered via `register_yookassa_client_provider`. `register_fiscal_receipt_dispatcher(fiscal_receipt_dispatcher_noop_stub)` is preserved per D-48-26.
- **on_shutdown**: `ctx.get("yookassa_client")` is awaited `.aclose()` BEFORE the DB AsyncExitStack closes — same teardown order as the FastAPI side.

### tests/unit/test_yookassa_protocol_slot_parity.py

- **Module docstring**: extended with the Phase 48 D-48-25 paragraph explaining structural (closure-per-process) parity replaces byte-equal for the YooKassaClientProvider slot; D-48-26 preserves the other three slots' byte-equal invariants.
- **Imports**: `pathlib.Path` added at module top; `yookassa_client_provider_noop_stub` removed from the `_stubs` import (no longer referenced). Source paths are resolved from `__file__` so the test is pytest-cwd agnostic.
- **`_worker_register_double_wired_slots()` helper**: trimmed — it only registers the surviving Phase 47 byte-equal stub (`fiscal_receipt_dispatcher_noop_stub`) so Test C's reference holds. The YooKassa stub registration is gone (worker owns a real closure now).
- **Test A** (`test_fastapi_create_app_wires_all_four_slots`): the `assert deps.get_yookassa_client_provider() is yookassa_client_provider_noop_stub` line is replaced with three source-grep assertions against `app/main.py` (factory imported, real closure registered, noop stub registration absent). The other three stub-identity assertions stay.
- **Test B** (`test_arq_worker_startup_wires_double_wired_slots`): mirror — same three source-grep assertions against `app/workers/__init__.py`; the `fiscal_receipt_dispatcher` byte-equal assertion stays.
- **Test C** (`test_arq_worker_does_not_wire_single_wired_slots`): UNCHANGED — the single-wire invariant for `MembershipActivator` / `PtPackageActivator` still holds in Phase 48 (D-48-26).
- **Test D** (`test_byte_equal_parity_between_fastapi_and_worker`): rewritten — FastAPI side asserts `deps._yookassa_client_provider.__name__ == "_yookassa_client_provider"` (locks the closure name); worker side asserts both source files contain the literal `async def _yookassa_client_provider` definition (structural closure-name parity); fiscal byte-equal invariant preserved.

## D-48-25 vs D-48-26 Split

| Slot | Phase 47 wiring | Phase 48 disposition | Phase that swaps |
|------|----------------|----------------------|------------------|
| YooKassaClientProvider | noop stub (REG-29-03 double-wire) | REAL closure (REG-29-03 double-wire; closure-name parity, no byte-equal) | **Phase 48 / Plan 07 (this plan)** |
| FiscalReceiptDispatcher | noop stub (REG-29-03 double-wire) | UNCHANGED — still noop stub byte-equal in both | Phase 50 |
| MembershipActivator | noop stub (HTTP single-wire) | UNCHANGED — still noop stub on FastAPI only | Phase 49 |
| PtPackageActivator | noop stub (HTTP single-wire) | UNCHANGED — still noop stub on FastAPI only | Phase 49 |

## Reachability Confirmation

After this plan:

- **HTTP request path** — `get_yookassa_client_provider()` returns the lazy closure that reads `app.state.yookassa_client`; the lifespan populates `app.state.yookassa_client` before the first request is served. Handler-side: `client = await get_yookassa_client_provider()(); result = await client.create_payment(...)` works against the real adapter (Plan 48-02).
- **ARQ worker job path** — `get_yookassa_client_provider()` returns the worker-local closure that reads `ctx["yookassa_client"]`; the per-process client is constructed in `WorkerSettings.on_startup` and held for the worker's lifetime.

Phase 49 will register the real `MembershipActivator` + `PtPackageActivator` slots; Phase 50 will swap `FiscalReceiptDispatcher` to dispatch real receipts.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 3 — Blocking] Path resolution for parity-test source files**
- **Found during:** Task 3a runtime check
- **Issue:** The plan's structural-source-grep snippet used `Path("apps/backend/app/main.py")`, which resolves relative to pytest's cwd. Tests run from `apps/backend/` (per `pyproject.toml`), so the path was a `FileNotFoundError`.
- **Fix:** Compute `_BACKEND_ROOT = Path(__file__).resolve().parents[2]` at module scope and use `_BACKEND_ROOT / "app" / "main.py"` / `_BACKEND_ROOT / "app" / "workers" / "__init__.py"` everywhere. Pytest-cwd agnostic.
- **Files modified:** apps/backend/tests/unit/test_yookassa_protocol_slot_parity.py
- **Commit:** 9da20fd

**2. [Rule 3 — Blocking] Task 3a vs 3b consistency: Test D between the two sub-tasks**
- **Found during:** Task 3a application
- **Issue:** The plan instructs Task 3a to remove the `yookassa_client_provider_noop_stub` import AND keep Test D untouched. Test D referenced that symbol, so the file became NameError/ruff F821-failing — incompatible with the Task 3a acceptance criterion `ruff + mypy strict clean`.
- **Fix:** In Task 3a, replace Test D's body with `pytest.skip("Rewritten in Plan 48-07 Task 3b …")` as a temporary bridge. Task 3b then rewrites the Test D body proper and removes the now-unused `pytest` import. Behavior at the end of Task 3b matches the plan exactly.
- **Files modified:** apps/backend/tests/unit/test_yookassa_protocol_slot_parity.py
- **Commits:** 9da20fd (skip bridge), 91ab217 (proper rewrite)

**3. [Rule 3 — Blocking] Line-length E501 on inline literal**
- **Found during:** Task 3a ruff run
- **Issue:** The structural-grep assertion line `assert "register_yookassa_client_provider(yookassa_client_provider_noop_stub)" not in main_src, (...)` was 101 chars (limit 100).
- **Fix:** Hoist the literal into a local `_noop_main` / `_noop_worker` variable and assert against it.
- **Files modified:** apps/backend/tests/unit/test_yookassa_protocol_slot_parity.py
- **Commit:** 9da20fd

**4. [Rule 1 — Bug] mypy `Any` return annotation drift in the lifespan closure**
- **Found during:** Task 1 mypy check
- **Issue:** Mypy strict warned on `return app.state.yookassa_client` from a function annotated `-> YooKassaClient` because `app.state` attributes resolve to `Any`.
- **Fix:** Added a focused `# type: ignore[no-any-return]` comment on the return line — narrow enough that strict mode passes without weakening the annotation. The worker-side closure (which reads from a typed `ctx["yookassa_client"]`) sidesteps the issue with an explicit local variable.
- **Files modified:** apps/backend/app/main.py
- **Commit:** 6e24009

## Verification

- `cd apps/backend && uv run ruff check app/main.py app/workers/__init__.py tests/unit/test_yookassa_protocol_slot_parity.py` — **PASS** (all checks)
- `cd apps/backend && uv run mypy --strict app/main.py app/workers/__init__.py tests/unit/test_yookassa_protocol_slot_parity.py` — PASS for the touched files (4 pre-existing errors in OTHER `app/modules/auth/*` files unrelated to this plan; confirmed pre-existing by stashing changes and re-running)
- `cd apps/backend && uv run pytest tests/unit/test_yookassa_protocol_slot_parity.py -q` — **4 passed**
- `cd apps/backend && uv run pytest tests/unit/integrations/yookassa tests/unit/test_yookassa_protocol_slot_parity.py tests/unit/test_locked_yookassa_constants_ast.py -q` — **38 passed**
- `! grep -q 'register_yookassa_client_provider(yookassa_client_provider_noop_stub)' apps/backend/app/main.py apps/backend/app/workers/__init__.py` — **PASS**
- `grep -q 'await build_yookassa_client' apps/backend/app/main.py && grep -q 'await build_yookassa_client' apps/backend/app/workers/__init__.py` — **PASS**

### Full-suite note

`uv run pytest -q` from `apps/backend/` reports `89 failed, 973 passed, 670 errors` — confirmed pre-existing (asserted by re-running both `tests/unit/workers/test_worker_settings.py` and `tests/integration/visits/test_visits_rbac.py::test_owner_can_get_visits_list` against the stash baseline: same failures appear). The integration errors are a DB-schema mismatch (`column "deactivated_at" of relation "users" does not exist`) inherited from a prior phase's migration state; the two unit-test failures are a `WorkerSettings.functions` count mismatch (test expects 6, codebase has 7 since Phase 44 added `cleanup_password_reset_tokens`). None are introduced by this plan.

## Success Criteria

- [x] app/main.py constructs YooKassaClient in combined_lifespan, registers lazy provider in create_app(), closes client in lifespan teardown
- [x] app/workers/__init__.py mirrors the same pattern via WorkerSettings.on_startup + on_shutdown (REG-29-03 mirror)
- [x] The Phase 47 noop stub registration for YooKassaClientProvider is removed from BOTH composition roots
- [x] D-48-26 preserved: fiscal_receipt_dispatcher / membership_activator / pt_package_activator stay noop
- [x] Parity test updated (Tasks 3a + 3b): Tests A + B use structural source-grep; Test C unchanged; Test D uses closure-name `__name__` check + structural closure-name parity grep + fiscal byte-equal invariant preserved — D-48-25 reference in docstring
- [x] All 4 parity tests in `test_yookassa_protocol_slot_parity.py` pass
- [x] ruff + mypy strict clean on touched files

## Self-Check: PASSED

- FOUND: apps/backend/app/main.py (commit 6e24009)
- FOUND: apps/backend/app/workers/__init__.py (commit 8afa0de)
- FOUND: apps/backend/tests/unit/test_yookassa_protocol_slot_parity.py (commits 9da20fd, 91ab217)
- FOUND commit 6e24009 in git log
- FOUND commit 8afa0de in git log
- FOUND commit 9da20fd in git log
- FOUND commit 91ab217 in git log

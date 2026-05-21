---
phase: 47-bedrock
plan: 04
subsystem: infra

tags: [protocol-slots, composition-root, yookassa, fiscal-receipt, arq, double-wire, reg-29-03, infra-38]

# Dependency graph
requires:
  - phase: 47-bedrock plan 02
    provides: app/integrations/yookassa/ package (YooKassaSettings, __init__.py)
  - phase: 41-onward (precedent)
    provides: EmailDispatcher Protocol-slot pattern (defensive-raise accessor)
provides:
  - 4 v1.7 Protocol slots in app/core/dependencies.py (YooKassaClientProvider, FiscalReceiptDispatcher, MembershipActivator, PtPackageActivator)
  - 4 no-op stubs in app/integrations/yookassa/_stubs.py (raise NotImplementedError at call-time)
  - Composition-root wiring (FastAPI = 4, ARQ worker = 2 double-wired)
  - tests/unit/test_yookassa_protocol_slot_parity.py (4 parity tests; T-47-04-01/02/03/04 mitigations)
affects:
  - Phase 48 ADAPTER-02 (will replace yookassa_client_provider_noop_stub with real YooKassaClient)
  - Phase 49 (online_payments module — callsites consume get_yookassa_client_provider)
  - Phase 50 WH-05 (will replace membership_activator_noop_stub + pt_package_activator_noop_stub + fiscal_receipt_dispatcher_noop_stub)
  - Phase 51 FISCAL-05 (worker-side fiscal-receipt consumer using FiscalReceiptDispatcher)

# Tech tracking
tech-stack:
  added: []  # No new libraries — pure typing.Protocol + composition root pattern.
  patterns:
    - "Protocol slot trio (class + register_ + defensive-raise get_) extended from 12 -> 16 slots"
    - "Single vs double wire discipline (REG-29-03) — explicit per-slot decision documented in defensive-raise message"
    - "No-op stub pattern at integrations layer (raise NotImplementedError at call-time, not registration-time) — D-47-01 Option A"

key-files:
  created:
    - apps/backend/app/integrations/yookassa/_stubs.py
    - apps/backend/tests/unit/test_yookassa_protocol_slot_parity.py
  modified:
    - apps/backend/app/core/dependencies.py
    - apps/backend/app/main.py
    - apps/backend/app/workers/__init__.py
    - .planning/phases/47-bedrock/deferred-items.md

key-decisions:
  - "Stub Identity over WorkerSettings.on_startup invocation: parity test mirrors the worker's 2 register_* lines instead of calling on_startup({}) directly — on_startup opens a real DB engine + Redis pool + email-client probe (out of scope for unit tests). Identity parity still holds because both processes import the SAME stub symbols from app.integrations.yookassa._stubs."
  - "Single-wire negative-control via source scan: test C reads app/workers/__init__.py as text and asserts register_membership_activator + register_pt_package_activator strings are absent. This is the canonical T-47-04-02 (spoofing) guard against accidental promotion of an HTTP-only activator to a cross-process slot."

patterns-established:
  - "Defensive-raise message NAMES both wiring sites for double-wired slots and explicitly notes 'HTTP-only single-wire — no ARQ entry path' for single-wired slots. Future phases mirror this disambiguation when adding new slots."

requirements-completed: [INFRA-38]

# Metrics
duration: ~12min
completed: 2026-05-21
---

# Phase 47-04: Bedrock — v1.7 Protocol Slots + Composition-Root Wiring Summary

**4 v1.7 Protocol slots (YooKassaClientProvider, FiscalReceiptDispatcher, MembershipActivator, PtPackageActivator) declared in `app/core/dependencies.py` with no-op stubs wired at both composition roots; byte-equal REG-29-03 parity for the 2 cross-process slots enforced by a 4-test suite.**

## Performance

- **Duration:** ~12 min
- **Started:** 2026-05-21T~12:58Z
- **Completed:** 2026-05-21T13:08Z
- **Tasks:** 2 (atomic commits)
- **Files modified:** 4 (+ 1 deferred-items doc)
- **Files created:** 2

## Accomplishments

- Extended composition-root Protocol-slot register from 12 -> 16 slots.
- 4 v1.7 Protocol slots in `app/core/dependencies.py`:
  - `YooKassaClientProvider` — `async __call__() -> Any` — double-wired.
  - `FiscalReceiptDispatcher` — `async __call__(*, fiscal_receipt_id: UUID, audit_correlation_id: UUID | None) -> None` — double-wired.
  - `MembershipActivator` — `async __call__(session: AsyncSession, *, membership_id: UUID, audit_correlation_id: UUID | None) -> Any` — single-wired.
  - `PtPackageActivator` — `async __call__(session: AsyncSession, *, pt_package_id: UUID, audit_correlation_id: UUID | None) -> Any` — single-wired.
- 4 no-op stubs in `app/integrations/yookassa/_stubs.py` raising `NotImplementedError` at call-time (registration succeeds, defensive accessors never trip during Phase 47 request handling).
- FastAPI composition root wires all 4 stubs in `create_app()`.
- ARQ worker registers ONLY the 2 double-wired stubs (`register_yookassa_client_provider` + `register_fiscal_receipt_dispatcher`) inside `WorkerSettings.on_startup` — `register_membership_activator` + `register_pt_package_activator` are deliberately absent from `app/workers/__init__.py`.
- 4-test parity suite passes:
  - Test A — `create_app()` wires all 4 slots (non-None accessors).
  - Test B — worker startup wires the 2 double-wired slots.
  - Test C — `app/workers/__init__.py` source scan: single-wired register_* symbols absent (T-47-04-02 mitigation).
  - Test D — byte-equal identity parity between FastAPI + worker stub objects (T-47-04-01 mitigation).

## Task Commits

1. **Task 1: Append 4 Protocol-slot blocks to `app/core/dependencies.py` + create `_stubs.py`** — `234d77d` (feat)
2. **Task 2: Wire 4 stubs in `app/main.py` + 2 stubs in `app/workers/__init__.py` + parity test** — `945ba1d` (feat)
3. **Plan-level deferred items log** — `8ccff79` (docs)

## Files Created/Modified

- `apps/backend/app/core/dependencies.py` — appended 4 Protocol-slot blocks (class + register_ + defensive-raise get_) following the v1.6 EmailDispatcher pattern at line ~608.
- `apps/backend/app/integrations/yookassa/_stubs.py` (NEW) — 4 no-op async coroutines satisfying the Protocol signatures; layer invariant: no `app.modules.*` imports (importlinter contract `integrations-not-depend-on-modules` stays green).
- `apps/backend/app/main.py` — imported 4 register_* + 4 stubs; added Phase 47 wiring block after `register_user_session_invalidator(...)`.
- `apps/backend/app/workers/__init__.py` — extended `on_startup` local imports with 2 register_* + 2 stubs; added 2 register_* calls after `register_email_dispatcher(enqueue_email_dispatch)`.
- `apps/backend/tests/unit/test_yookassa_protocol_slot_parity.py` (NEW) — 4 tests.
- `.planning/phases/47-bedrock/deferred-items.md` — logged 3 pre-existing issues found out of scope.

## Decisions Made

- **Stub identity over `await WorkerSettings.on_startup({})` invocation.** The plan's draft Test B/D suggested awaiting the worker's `on_startup` directly. That coroutine opens a real DB engine via `db_lifespan_manager()` AND probes the email client via `build_email_client(...)` — both require a live Postgres/Redis/Postbox environment unavailable to unit tests. Identity parity holds because both processes import the SAME stub symbols from `app.integrations.yookassa._stubs` (module attribute lookup → identical object reference). Documented in the test file's module docstring and the helper `_worker_register_double_wired_slots()`.
- **Test C uses source-text scan instead of state-snapshot assertion.** A "did the worker startup touch `_membership_activator`?" snapshot test would have to run `on_startup({})` (see above). A source-text scan of `app/workers/__init__.py` gives a stronger guarantee (the symbol literally does not appear in the worker module) and runs in microseconds.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 — Bug] Removed unused `# type: ignore[assignment]` comments**
- **Found during:** Task 2 (`mypy --strict` post-write check).
- **Issue:** The 4 module-attribute resets in `_reset_v17_slots()` (e.g., `deps._yookassa_client_provider = None`) were drafted with `# type: ignore[assignment]` defensively, but mypy ruled the comments unused (the annotated type `YooKassaClientProvider | None` already permits `None`).
- **Fix:** Removed all 4 `# type: ignore[assignment]` comments.
- **Files modified:** `apps/backend/tests/unit/test_yookassa_protocol_slot_parity.py`
- **Verification:** `uv run mypy --strict ... test_yookassa_protocol_slot_parity.py` clean for the test file (the 4 pre-existing `auth.models.User` attr-defined errors remain — out of scope).
- **Committed in:** `945ba1d` (Task 2 commit, before initial commit was made).

**2. [Rule 1 — Bug] Replaced `import as alias` in test helper with `import module then module.attr`**
- **Found during:** Task 2 (ruff post-write check).
- **Issue:** The drafted test had `from app.integrations.yookassa._stubs import (foo as a, bar as b)` inside a function — ruff flagged unsorted imports.
- **Fix:** Replaced with `from app.integrations.yookassa import _stubs` then `_stubs.foo / _stubs.bar`. Functionally identical (still the same module attribute lookup → identical object reference), cleaner ruff.
- **Files modified:** `apps/backend/tests/unit/test_yookassa_protocol_slot_parity.py`
- **Verification:** `uv run ruff check ...` clean for all 5 plan files.
- **Committed in:** `945ba1d`.

---

**Total deviations:** 2 auto-fixed (2 Rule 1 — lint/type bug fixes in the test file before it was first committed).
**Impact on plan:** Zero scope creep. Both fixes are mechanical lint/type cleanups in a file that had not yet been committed.

## Issues Encountered

- **Two pre-existing unit test failures in `tests/unit/workers/test_worker_settings.py`** (cron_jobs count and functions count drift from Phase 44 `cleanup_password_reset_tokens` addition). Confirmed pre-existing via `git stash` + rerun on the Phase 47 base. Logged to `deferred-items.md`; not fixed (SCOPE BOUNDARY rule). Excluded via `--deselect` for the verification run — 780 unit tests pass alongside the 4 new parity tests.
- **Four pre-existing mypy strict errors** in `app/modules/auth/{service,router,telegram_service}.py` + `app/modules/users/router.py` (`User` not in `__all__` of `app.modules.auth.models`). Confirmed pre-existing. Logged to `deferred-items.md`.

## Verification Snapshot

- `uv run ruff check app/core/dependencies.py app/integrations/yookassa/_stubs.py app/main.py app/workers/__init__.py tests/unit/test_yookassa_protocol_slot_parity.py` → **All checks passed**
- `uv run mypy --strict` on the 5 plan files → **clean for plan files** (4 unrelated `attr-defined` errors in `app.modules.auth.*` confirmed pre-existing).
- `uv run lint-imports` → **3 contracts kept, 0 broken** (including `integrations must not import modules`).
- `uv run pytest tests/unit/test_yookassa_protocol_slot_parity.py -x -v` → **4 passed in 0.14s**.
- `uv run pytest tests/unit --deselect <2 pre-existing>` → **780 passed, 2 deselected**.

## Threat Model Verification

| Threat ID | Status | Mitigation |
|-----------|--------|------------|
| T-47-04-01 (Tampering — slot identity) | ✅ Mitigated | Test D byte-equal `is` identity assertion. |
| T-47-04-02 (Spoofing — single-wired accidentally double-wired) | ✅ Mitigated | Test C source-text scan asserts `register_membership_activator` / `register_pt_package_activator` strings are absent from `app/workers/__init__.py`. |
| T-47-04-03 (DoS — defensive RuntimeError during request handling) | ✅ Mitigated | All 4 slots wired with no-op stubs at composition root (D-47-01 Option A); accessors return non-None at runtime. |
| T-47-04-04 (Tampering — Protocol signature drift) | ✅ Mitigated | `mypy --strict` over `dependencies.py` + `_stubs.py` ensures stub signatures structurally match the Protocols. |
| T-47-04-05 (Info Disclosure — phase ID leak in NotImplementedError) | ⚠️ Accepted | Per plan threat model: phase IDs in error messages carry no credentials/secrets. |

## Confirmation: No `app.modules.*` imports in core/integrations

```bash
$ grep -E '^from app\.modules' apps/backend/app/core/dependencies.py apps/backend/app/integrations/yookassa/_stubs.py
# (no output — verified)
```

The `core-not-depend-on-modules` + `integrations-not-depend-on-modules` importlinter contracts remain green (`lint-imports` exit 0).

## Next Phase Readiness

- **Phase 48 ADAPTER-02** can now import `register_yookassa_client_provider` and replace `yookassa_client_provider_noop_stub` with the real `YooKassaClient` instance. Single edit at `app/main.py:create_app()` + `app/workers/__init__.py:WorkerSettings.on_startup`.
- **Phase 49 online_payments module** can call `get_yookassa_client_provider()` at any callsite — Phase 47 ships a wired slot so the defensive accessor returns non-None (calling the stub raises `NotImplementedError`, which Phase 49's first real callsite will encounter and replace).
- **Phase 50 WH-05** has 3 slots ready to wire: replace each `*_noop_stub` with the concrete `MembershipActivator` / `PtPackageActivator` / `FiscalReceiptDispatcher` implementation.

## Self-Check: PASSED

- `apps/backend/app/core/dependencies.py` — modified, 4 Protocol classes + 4 register_ + 4 get_ accessors present (verified via grep counts).
- `apps/backend/app/integrations/yookassa/_stubs.py` — created, 4 stubs importable.
- `apps/backend/app/main.py` — modified, 4 register_ calls present.
- `apps/backend/app/workers/__init__.py` — modified, exactly 2 register_ calls present (single-wired absent).
- `apps/backend/tests/unit/test_yookassa_protocol_slot_parity.py` — created, 4 tests pass.
- Commits `234d77d`, `945ba1d`, `8ccff79` all present in `git log`.

---
*Phase: 47-bedrock*
*Completed: 2026-05-21*

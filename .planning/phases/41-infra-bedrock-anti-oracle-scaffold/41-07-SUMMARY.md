---
phase: 41-infra-bedrock-anti-oracle-scaffold
plan: 07
subsystem: infra
tags: [contextvar, audit, middleware, arq, actor-attribution, fastapi, asyncio]

# Dependency graph
requires:
  - phase: 41-infra-bedrock-anti-oracle-scaffold (Plan 06)
    provides: audit_log.actor_email_snapshot column (Alembic 0023) + FK SET NULL
provides:
  - app/core/actor_context.py — actor_context_var ContextVar + ActorIdentity TypedDict + set_actor / reset_actor / get_current_actor helpers
  - ActorContextMiddleware in app/core/middleware.py (placed between TimingMiddleware and RequestIdMiddleware in the reversed add-chain)
  - get_current_user (app/core/dependencies.py) now calls set_actor() with resolved (id, email) AFTER auth succeeds — canonical write site
  - audit.emit() accepts actor_email_snapshot kwarg (default None → ContextVar lookup), persists into AuditLog.actor_email_snapshot column
  - WorkerSettings.on_job_start / on_job_end establish a job-scoped actor_context_var envelope
  - CurrentUser Protocol gains email: str
affects: [Phase 42 email transport, Phase 43 multi-user admin, Phase 44 password reset, Phase 45 notifications]

# Tech tracking
tech-stack:
  added: []  # No new libraries — pure stdlib contextvars + existing FastAPI / ARQ wiring
  patterns:
    - "ContextVar set-baseline-None at request envelope, real-value write at dependency boundary"
    - "Defensive identity match in audit.emit() — ContextVar.email adopted only when ContextVar.user_id == passed actor_user_id"
    - "ARQ job-scoped contextvar envelope via on_job_start token stash in ctx['_actor_token']"

key-files:
  created:
    - apps/backend/app/core/actor_context.py
    - apps/backend/tests/unit/test_actor_context.py
  modified:
    - apps/backend/app/core/middleware.py
    - apps/backend/app/core/audit.py
    - apps/backend/app/core/audit_models.py
    - apps/backend/app/core/dependencies.py
    - apps/backend/app/main.py
    - apps/backend/app/workers/__init__.py
    - apps/backend/app/modules/clients/service.py

key-decisions:
  - "ContextVar baseline written by middleware; real identity written by get_current_user dependency (ASGI middleware runs BEFORE per-route dependencies, so request.state.current_user is not yet populated at middleware entry)."
  - "ARQ 0.28 ctx does NOT surface job kwargs (only job_id / job_try / enqueue_time / score); on_job_start sets the envelope to None and stashes the token on ctx['_actor_token'], jobs needing attribution call set_actor() themselves in the job body."
  - "Defensive identity check (T-41-07-02): emit() adopts the ContextVar's email ONLY when its user_id matches the passed actor_user_id — mismatch leaves snapshot None to prevent misattribution."
  - "CurrentUser Protocol extended with email: str — User ORM already has it (app/core/models.py), so the SA model still satisfies the structural type."

patterns-established:
  - "actor_context_var envelope: middleware sets baseline None → dependency writes real identity → emit() reads at INSERT time. Mirror this pattern for any other request-scoped attribute needing to reach audit.emit() in v1.7+."
  - "Defensive ContextVar adoption with identity verification — copy the user_id == actor_user_id idiom into any future emit()-like seam that bridges ContextVar to persistent storage."

requirements-completed: [INFRA-39]

# Metrics
duration: 8min
completed: 2026-05-18
---

# Phase 41 Plan 07: ActorContext runtime wiring + audit.emit() reads ContextVar

**Plumbed `audit_log.actor_email_snapshot` from request-scoped ContextVar through `audit.emit()` with override path, defensive identity match, and an ARQ job envelope — column wired end-to-end with system-emit NULL discipline (D-41-10).**

## Performance

- **Duration:** ~8 min
- **Started:** 2026-05-18T19:02:44Z
- **Completed:** 2026-05-18T19:10:45Z (approx — final commit timestamp)
- **Tasks:** 3 (all auto)
- **Files modified:** 7 (6 source + 1 unrelated callsite type:ignore)
- **Files created:** 2 (`actor_context.py`, `test_actor_context.py`)
- **Tests added:** 7 (all passing; full unit suite 406 passed, 0 new failures)

## Accomplishments

- `apps/backend/app/core/actor_context.py` — leaf module declaring `actor_context_var: ContextVar[ActorIdentity | None]`, the `ActorIdentity` TypedDict (`{user_id: UUID, email: str}` verbatim from D-41-08), and three helpers (`set_actor` / `reset_actor` / `get_current_actor`).
- `ActorContextMiddleware` registered between `TimingMiddleware` and `RequestIdMiddleware` — sets baseline `None` and owns the request-scoped reset envelope.
- `get_current_user` dependency calls `set_actor({"user_id": user.id, "email": user.email})` AFTER auth resolves — the canonical write site. The `CurrentUser` Protocol gained `email: str` (User ORM already had it).
- `audit.emit()` gained a keyword-only `actor_email_snapshot: str | None = None` parameter and reads `get_current_actor()` when the kwarg is `None` and `actor_user_id` is non-NULL. Defensive identity match (T-41-07-02) prevents misattribution. Explicit override wins (D-41-08). System emits (`actor_user_id=None`) skip the lookup → NULL/NULL row (D-41-10).
- `AuditLog` ORM model gained `actor_email_snapshot: Mapped[str | None]` and the FK ondelete flipped from `RESTRICT` to `SET NULL` to match migration 0023.
- `WorkerSettings.on_job_start` / `on_job_end` establish a job-scoped actor envelope (token stashed on `ctx['_actor_token']`); jobs needing attribution call `set_actor()` themselves because ARQ 0.28 does not surface job kwargs on ctx.

## Task Commits

1. **Task 1: actor_context.py + ContextVar + helpers** — `4748c83` (feat)
2. **Task 2: ActorContextMiddleware + audit.emit() + ORM column + dependency** — `e1f63d0` (feat)
3. **Task 3: ARQ on_job_start/on_job_end + unit tests** — `2f1adac` (feat)

## Files Created/Modified

- `apps/backend/app/core/actor_context.py` (NEW) — ContextVar + TypedDict + 3 helpers; 61 lines.
- `apps/backend/app/core/middleware.py` — added `ActorContextMiddleware`; updated `register_middleware` reversed-add docstring to reflect the new 3-middleware chain.
- `apps/backend/app/core/audit.py` — `emit()` signature gains `actor_email_snapshot: str | None = None`; reads `get_current_actor()` with defensive identity check; passes value into `AuditLog` row construction. Docstring updated with override + system-emit semantics.
- `apps/backend/app/core/audit_models.py` — added `actor_email_snapshot: Mapped[str | None]`; FK ondelete flipped to `SET NULL`.
- `apps/backend/app/core/dependencies.py` — `CurrentUser` Protocol gains `email: str`; `get_current_user` calls `set_actor(...)` after successful loader resolution.
- `apps/backend/app/main.py` — docstring step 4 updated to reflect the new middleware insertion.
- `apps/backend/app/workers/__init__.py` — on_job_start sets `actor_context_var` baseline None + stashes token; on_job_end resets. Module docstring documents ARQ 0.28 ctx limitation and the in-job-body attribution pattern.
- `apps/backend/app/modules/clients/service.py` — single-line `# type: ignore[arg-type]` on `**payload` splat into `emit()` (Rule 1 deviation, see below).
- `apps/backend/tests/unit/test_actor_context.py` (NEW) — 7 tests covering all D-41-08-10 paths; 175 lines.

## Decisions Made

- **Middleware writes baseline None, dependency writes the real identity.** The plan documented two design alternatives; this is the chosen one because ASGI middleware runs strictly BEFORE per-route dependencies in Starlette. There is no `request.state.current_user` available at middleware entry — only the `get_current_user` dependency knows when auth has actually succeeded. The middleware's outer `try/finally` is still essential: it guarantees no leak across requests sharing the same asyncio task, regardless of whether any specific request actually authenticated.
- **`CurrentUser` Protocol extended with `email: str`.** The User ORM in `app/core/models.py` already has `email: Mapped[str]`, so the structural-type contract still holds and the Phase 5 D-15 carve-out is preserved.
- **ARQ on_job_start does NOT inspect job kwargs.** ARQ 0.28's `Worker.run_job` only seeds ctx with `job_id / job_try / enqueue_time / score`; the per-call `*args/**kwargs` go directly to the coroutine without landing on ctx. The plan anticipated this fallback explicitly: jobs that need actor attribution call `set_actor()` themselves near the top of the job body. The module docstring documents this as the "ARQ ctx limitation".
- **Defensive identity match in `emit()`.** Per T-41-07-02 in the plan's threat model, `emit()` adopts the ContextVar's email ONLY when `identity["user_id"] == actor_user_id`. Mismatch silently leaves the snapshot None — failing safe rather than risking misattribution if a stale ContextVar leaks (which the request/job envelopes should prevent, but defence-in-depth costs nothing here).

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] CurrentUser Protocol missing `email` field**

- **Found during:** Task 2 (Wiring `get_current_user` to call `set_actor`).
- **Issue:** The plan instructs `get_current_user` to call `set_actor({"user_id": user.id, "email": user.email})`, but `CurrentUser` Protocol only declared `id: UUID` and `role: Role` — no `email`. Mypy strict would have rejected the access.
- **Fix:** Added `email: str` to the Protocol. The User ORM (`app/core/models.py`) already has `email: Mapped[str, nullable=False]`, so the structural-type contract still holds and no other callsite breaks.
- **Files modified:** `apps/backend/app/core/dependencies.py`.
- **Verification:** `uv run mypy --strict app/` reports no new errors (the 3 pre-existing `attr-defined` errors on the auth.models User shim are documented in `deferred-items.md`).
- **Committed in:** `e1f63d0` (Task 2).

**2. [Rule 1 - Bug] mypy strict reject on `**payload` splat into widened `emit()` signature**

- **Found during:** Task 2 (`mypy --strict app/` after adding `actor_email_snapshot: str | None = None`).
- **Issue:** `app/modules/clients/service.py:194` splats a `dict[str, object]` payload into `audit.emit()`. The added typed kwarg made mypy realise the splat could supply a non-`str | None` value to `actor_email_snapshot`.
- **Fix:** Added `# type: ignore[arg-type]` on the `**payload` line with a comment explaining the safety (pre-v1.4 free-form payload contract per D-30-02; `client_updated` never carries `actor_email_snapshot`). This is the localised fix — narrowing every legacy callsite's payload dict would be massive scope creep.
- **Files modified:** `apps/backend/app/modules/clients/service.py`.
- **Verification:** `uv run mypy --strict app/` clean except for the 3 pre-existing auth.models shim errors.
- **Committed in:** `e1f63d0` (Task 2).

**3. [Rule 3 - Blocking] ARQ 0.28 does not surface job kwargs on ctx**

- **Found during:** Task 3 (Inspecting `arq.worker.Worker.run_job` source).
- **Issue:** The plan's primary approach (read `actor_user_id` / `actor_email_snapshot` from `ctx['job_kwargs']` inside `on_job_start`) is not realisable on the installed ARQ 0.28 — `job_kwargs` is not in ctx. The plan explicitly anticipated this fallback.
- **Fix:** Implemented the fallback: `on_job_start` sets `actor_context_var=None` as the job-scoped baseline and stashes the token on `ctx['_actor_token']`; `on_job_end` resets via that token. Jobs needing attribution call `set_actor()` themselves near the top. Documented as the "ARQ ctx limitation" in the module docstring.
- **Files modified:** `apps/backend/app/workers/__init__.py`.
- **Verification:** `tests/unit/test_actor_context.py::test_worker_on_job_start_sets_actor_baseline_none` passes — the outer/inner contextvar envelope round-trip works as designed.
- **Committed in:** `2f1adac` (Task 3).

---

**Total deviations:** 3 auto-fixed (2 bugs surfaced by mypy strict, 1 blocking-but-anticipated ARQ ctx limitation)
**Impact on plan:** All three were correctness fixes within the plan's intent. The Protocol extension closes a gap the plan implicitly assumed; the type:ignore is a narrow-scope localisation; the ARQ fallback was pre-documented in the plan's Concrete approach paragraph. No scope creep.

## Issues Encountered

- `tests/unit/test_permissions.py::test_owner_only_has_exactly_twenty_nine_entries` fails on `master` independently of this plan (verified via `git stash` round-trip). Already logged in `deferred-items.md` (Plan 41-10 entry). Skipped via `--deselect` to confirm Plan 41-07 introduces zero regressions; the full unit suite minus that file shows **406 passed** (was 399 before Plan 07; +7 new actor_context tests).
- The 3 pre-existing `attr-defined` errors on the `app.modules.auth.models.User` shim are likewise documented in `deferred-items.md` (Plan 41-11 entry).
- `import-linter` contracts (`core-not-depend-on-modules`, `modules-independent`, `integrations-not-depend-on-modules`) all KEPT after the changes — no new boundary violations.

## Threat Flags

None — no new network endpoints, no new auth paths, no new trust-boundary surface. The ContextVar lives entirely within the in-process request/job envelope; the audit_log column it populates was already covered by the Plan 06 migration threat model.

## User Setup Required

None — pure backend code change. No environment variables, no external service configuration, no Alembic migration (Plan 06 shipped 0023; Plan 07 only adds the SA ORM mapping for the column already on disk).

## Next Phase Readiness

INFRA-39 is now COMPLETE end-to-end:
- **Schema half** (Plan 06): Alembic 0023 `audit_log.actor_email_snapshot TEXT NULL` + FK SET NULL.
- **Runtime half** (Plan 07, this plan): ContextVar + middleware envelope + dependency write site + `emit()` read + ARQ envelope.

Phase 42 (Email transport) and Phase 43 (Multi-user admin) can now emit audit rows that automatically carry `actor_email_snapshot` without threading the value through every callsite. The override path is available for Phase 45 batch-style emits if needed.

## Self-Check: PASSED

- `apps/backend/app/core/actor_context.py` — FOUND
- `apps/backend/tests/unit/test_actor_context.py` — FOUND
- Commit `4748c83` (Task 1) — FOUND
- Commit `e1f63d0` (Task 2) — FOUND
- Commit `2f1adac` (Task 3) — FOUND
- `apps/backend/app/core/middleware.py:ActorContextMiddleware` — FOUND (introspected via Python import)
- `apps/backend/app/core/audit_models.py:AuditLog.actor_email_snapshot` — FOUND (hasattr check passes)
- `audit.emit` signature contains `actor_email_snapshot` parameter — FOUND (inspect.signature check passes)
- `pytest tests/unit/test_actor_context.py` — 7/7 PASSING
- `pytest tests/unit/ --deselect tests/unit/test_permissions.py` — 406/406 PASSING
- `mypy --strict app/` — clean modulo 3 pre-existing auth.models shim errors (documented)
- `lint-imports` — all 3 contracts KEPT

---
*Phase: 41-infra-bedrock-anti-oracle-scaffold*
*Plan: 07*
*Completed: 2026-05-18*

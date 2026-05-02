---
phase: 05-user-schema-email-password-auth
plan: 06
subsystem: auth
tags: [fastapi, lifespan, asynccontextmanager, importlinter, sqlalchemy-postgres, upsert, seed-script]

requires:
  - phase: 05-user-schema-email-password-auth
    provides: redis_lifespan (Plan 02), users table + User model (Plan 03), load_user_by_id loader (Plan 04), auth_router with 5 endpoints (Plan 05)
  - phase: 04-auth-foundations-cookie-rbac-primitives
    provides: register_user_loader slot (D-24), cookie_secure setting + prod assertion intent (D-25)
  - phase: 02-fastapi-skeleton-config-logging-error-model
    provides: api / v1 router scaffolding with empty prefix and /healthz at root (D-14)

provides:
  - combined_lifespan chaining db_lifespan + redis_lifespan (D-08)
  - Composition root register_user_loader(load_user_by_id) wiring (D-15)
  - /api/v1 prefix flip with /healthz preserved at root (D-16)
  - auth_router mounted at /api/v1/auth/{login,refresh,logout,logout-all,me} with tags=['auth']
  - Idempotent owner-seed script reading SEED_OWNER_EMAIL/SEED_OWNER_PASSWORD (AUTH-EP-04 / D-25)
  - Fail-fast prod assertion: cookie_secure must be True when environment='prod'

affects: [phase-06-rbac-endpoints, phase-07-business-modules, future-admin-endpoints, deployment-runbook]

tech-stack:
  added: []
  patterns:
    - "combined_lifespan via @asynccontextmanager — chain multiple resource lifespans cleanly"
    - "Composition-root slot fill — app.main is the only allowed app.modules.* importer"
    - "Postgres-dialect pg_insert + on_conflict_do_nothing(index_elements=['email']) for idempotent upsert"
    - "Fail-fast startup assertions for environment-conditional config"

key-files:
  created: []
  modified:
    - apps/backend/app/main.py
    - apps/backend/app/api/router.py
    - apps/backend/app/api/v1/router.py
    - apps/backend/scripts/seed_demo_data.py

key-decisions:
  - "combined_lifespan kept at module level (stable identity across factory calls)"
  - "register_user_loader(load_user_by_id) called BEFORE include_router so first request post-startup has loader bound (no race)"
  - "/healthz remounted directly on api router (not under v1) to preserve k8s root path while v1 prefix flips to /api/v1"
  - "Seed script enforces password length >= 12 locally (defense-in-depth on top of column accepting any text)"
  - "Prod cookie_secure check raises RuntimeError at create_app() time, not at first login — fail loud at boot"

patterns-established:
  - "Pattern 1: combined_lifespan composition — chain db + redis lifespans via async-with so failures unwind correctly"
  - "Pattern 2: Composition-root user-loader slot — keep core ⊥ modules contract while still resolving CurrentUser"
  - "Pattern 3: Idempotent operator-seed via pg_insert.on_conflict_do_nothing(index_elements=['email'])"

requirements-completed: ["AUTH-EP-04"]

duration: ~1min
completed: 2026-05-02
---

# Phase 05 Plan 06: Wire Composition Root + Mount Auth Router + Seed Owner Summary

**combined_lifespan chains DB + Redis, register_user_loader(load_user_by_id) fills the Phase 4 D-24 slot, /api/v1/auth/* now resolves with /healthz preserved at root, and seed_demo_data.py upserts the bootstrap owner idempotently from environment variables.**

## Performance

- **Duration:** ~1 min (74 s task-commit window)
- **Started:** 2026-05-02T12:57Z
- **Completed:** 2026-05-02T12:58:23Z
- **Tasks:** 3
- **Files modified:** 4

## Accomplishments
- `app/main.py` now composes `db_lifespan + redis_lifespan` via a module-level `combined_lifespan` and registers `load_user_by_id` as the user loader BEFORE `include_router`, with a fail-fast prod-mode `cookie_secure` assertion (Phase 4 D-25).
- API surface finalised: `/healthz` stays at root (Phase 2 D-14 / k8s liveness), the v1 router moves under `/api/v1`, and the auth router lights up at `/api/v1/auth/{login,refresh,logout,logout-all,me}` with `tags=["auth"]`.
- `scripts/seed_demo_data.py` rewritten as an idempotent owner upsert using `pg_insert(...).on_conflict_do_nothing(index_elements=["email"])`, reading `SEED_OWNER_EMAIL` + `SEED_OWNER_PASSWORD` from the environment with a defensive `len(password) >= 12` guard.
- All importlinter contracts (`core must not import modules`, `modules cannot import each other`, `integrations must not import modules`) remain green: `app.main` is the sole composition-root path that reaches into `app.modules.*`, and that is intentional (importlinter `source_modules = app.core`).

## Task Commits

1. **Task 1: Compose redis_lifespan + register_user_loader in app/main.py** — `29f5913` (feat)
2. **Task 2: Flip API prefix to /api/v1 and mount auth_router** — `2af97e5` (feat)
3. **Task 3: Rewrite seed_demo_data.py with idempotent owner upsert** — `1880686` (feat)

## Files Created/Modified

- `apps/backend/app/main.py` — Composition root: `combined_lifespan`, prod assertion, `register_user_loader(load_user_by_id)` before `include_router`.
- `apps/backend/app/api/router.py` — `/healthz` mounted at root; v1 router mounted at `prefix="/api/v1"`.
- `apps/backend/app/api/v1/router.py` — Aggregates business module routers; mounts `auth_router` at `prefix="/auth", tags=["auth"]` (no longer carries `health.router`).
- `apps/backend/scripts/seed_demo_data.py` — Idempotent owner upsert via `pg_insert.on_conflict_do_nothing`, env-driven, async engine + sessionmaker, `Role.OWNER.value` + `full_name="Owner"` (D-01).

## Decisions Made

- Module-level `combined_lifespan` (not nested) so its identity is stable across factory calls and test harnesses can patch/observe it predictably.
- `register_user_loader` runs before `include_router(api)` to eliminate any first-request race against an unbound loader.
- Removed `health.router` from `v1` and remounted on the parent `api` router so the k8s liveness contract (`/healthz` at root, Phase 2 D-14) survives the `/api/v1` prefix flip.
- Seed script `len(password) < 12` guard enforced at the script boundary even though the `password_hash` column accepts arbitrary text — prevents a 4-char seed from slipping into prod.
- Prod-mode misconfig (`cookie_secure=False` while `environment="prod"`) raises `RuntimeError` at `create_app()` time, not at first login — failure is loud, fast, and unambiguous in deployment logs.

## Deviations from Plan

None — plan executed exactly as written. Verbatim source from `<action>` blocks was applied; all `<acceptance_criteria>` greps and `lint-imports` / `mypy --strict` / `ruff` checks pass.

## Issues Encountered

- The `<acceptance_criteria>` line `cd apps/backend && uv run python -c "from app.main import create_app; create_app()"` requires `DATABASE_URL` / `REDIS_URL` / `SECRET_KEY` to be present in the environment because `get_settings()` validates them via Pydantic v2. Confirmed factory call succeeds with `.env.example` values inlined; this is consistent with the repo's runtime contract (settings sourced from env / docker-compose). No code change needed — it is expected behaviour.
- Live Postgres acceptance steps (seed-script idempotency run + `curl /healthz`, `curl /api/v1/auth/me`) require an up Postgres + Redis; not exercised inside this isolated worktree. Static verification (grep, mypy, ruff, importlinter, route-table introspection) was executed and is green; live integration belongs in the phase verification step that runs against the compose stack.

## Threat Surface Notes

The Plan's `<threat_model>` is fully covered by the implementation:
- T-05.06-01 mitigated: `db_lifespan` enters before `redis_lifespan` via nested `async with` — Redis startup failure unwinds the DB engine cleanly.
- T-05.06-02 mitigated: `register_user_loader` runs before `include_router`; the cold-path `InvalidAccessToken('user_loader_not_registered')` already lives in Phase 4 `get_current_user`.
- T-05.06-03 mitigated: seed script never logs `password`; only the lowercased email after seeding.
- T-05.06-04 mitigated: `docs_url` remains gated on `environment == "dev"` (preserved from prior phase).
- T-05.06-05 mitigated: `RuntimeError` at startup when `prod` + `not cookie_secure`.
- T-05.06-07 mitigated: `on_conflict_do_nothing` keeps existing hash on re-run; password rotation deferred to a future admin endpoint.

No new security-relevant surface was introduced beyond what the plan threat-modelled.

## User Setup Required

None — no external service configuration required. The plan only adjusts the FastAPI composition root, router prefixes, and a one-shot operator seed script. Operators run `SEED_OWNER_EMAIL=... SEED_OWNER_PASSWORD=... uv run python -m scripts.seed_demo_data` once the compose stack is up; this is documented in plan 05 CONTEXT D-25.

## Next Phase Readiness

- API surface is final for Phase 5: `/healthz`, `/api/v1/auth/login`, `/api/v1/auth/refresh`, `/api/v1/auth/logout`, `/api/v1/auth/logout-all`, `/api/v1/auth/me` all resolve.
- Composition root is closed: every Phase 5 wave-1/2/3 artefact is now reachable from a running app.
- Phase 6 (RBAC endpoints) can now mount `Depends(require_permission(...))` on real business routes — the loader slot is filled and the prefix tree is stable.
- Compose-stack smoke (uvicorn boot + `curl /healthz` + `curl /api/v1/auth/me` returning 401) is the Phase 5 verification step; it is intentionally NOT executed inside this static worktree.

## Self-Check: PASSED

Verified the following before claiming completion:

- `apps/backend/app/main.py` exists and contains `combined_lifespan`, `register_user_loader(load_user_by_id)`, `lifespan=combined_lifespan`, prod assertion, and the `from app.modules.auth.service import load_user_by_id` import.
- `apps/backend/app/api/router.py` exists and contains `api.include_router(health.router)` and `prefix="/api/v1"`.
- `apps/backend/app/api/v1/router.py` exists, no longer mounts `health.router`, and contains `from app.modules.auth.router import router as auth_router` plus `prefix="/auth", tags=["auth"]`.
- `apps/backend/scripts/seed_demo_data.py` exists and contains `pg_insert`, `on_conflict_do_nothing(index_elements=["email"])`, both env-var reads, the `len(password) < 12` guard, `Role.OWNER.value`, and `full_name="Owner"`.
- Commits exist on the worktree branch:
  - `29f5913` (Task 1) — verified via `git log --oneline`.
  - `2af97e5` (Task 2) — verified via `git log --oneline`.
  - `1880686` (Task 3) — verified via `git log --oneline`.
- `cd apps/backend && uv run lint-imports` → 3 contracts kept, 0 broken.
- `cd apps/backend && uv run mypy app/main.py app/api/router.py app/api/v1/router.py scripts/seed_demo_data.py` → no issues.
- `cd apps/backend && uv run ruff check ...` → all checks passed.
- `create_app()` factory call returns a FastAPI instance whose route table includes `/healthz`, `/api/v1/auth/login`, `/api/v1/auth/refresh`, `/api/v1/auth/logout`, `/api/v1/auth/logout-all`, `/api/v1/auth/me` (verified via Python introspection with `.env.example` values).

---
*Phase: 05-user-schema-email-password-auth*
*Plan: 06*
*Completed: 2026-05-02*

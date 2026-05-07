---
phase: 18-arq-scheduled-expire-memberships
plan: 04
subsystem: infra
tags: [docker-compose, arq, cron, worker, requirements-reconciliation]

# Dependency graph
requires:
  - phase: 18-arq-scheduled-expire-memberships
    provides: "Plan 18-03 will ship `app.workers.WorkerSettings` with `cron_jobs=[cron(expire_memberships, hour=3, minute=5, ...)]`; this plan's compose `command: uv run arq app.workers.WorkerSettings` references that import path."
  - phase: 15-foundations-rbac-audit-taxonomy-helper-hoisting
    provides: "Inclusive end_date Key Decision (today's row stays active until tomorrow's tick) — anchor for ARQ-TEST-01 wording reconciliation."
provides:
  - "5th compose service `arq-worker` (build from same image as backend/telegram-bot, command `uv run arq app.workers.WorkerSettings`, TZ=UTC, restart-on-crash, depends_on migrate+redis)."
  - "REQUIREMENTS.md ARQ-04 wording reconciled with the canonical compose path (`apps/backend/docker-compose.yml`, not the research-vintage `infra/docker-compose.yml`)."
  - "REQUIREMENTS.md ARQ-TEST-01 wording reconciled with the Phase 15 inclusive-end_date Key Decision and the shipped Plan 18-05 test (count=1, not the stale count=2)."
affects: [18-05, 18-06, 19, future-infra-consolidation]

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "Long-running ARQ worker process modeled on the existing telegram-bot service (build from same image, share env, depend on migrate+redis, no HTTP surface)."
    - "Container TZ=UTC + cron(hour=3) literal pin for all v1.2+ cron jobs (Phase 15 Key Decisions)."

key-files:
  created: []
  modified:
    - "apps/backend/docker-compose.yml — add `arq-worker:` service block between `telegram-bot:` and `migrate:`."
    - ".planning/REQUIREMENTS.md — ARQ-04 + ARQ-TEST-01 wording reconciled (CD-02 path; W-3 stale-count fix)."

key-decisions:
  - "CD-02 honoured: compose file stays at apps/backend/docker-compose.yml; relocation to infra/ deferred to a future infra-consolidation phase."
  - "uv run arq is kept as the literal command (Dockerfile has CMD without ENTRYPOINT, so no double-uv-run conflict per the plan's runtime check). Plan 18-03's WorkerSettings will satisfy the import path; until then, `docker compose up arq-worker` will fail at runtime — expected."
  - "TZ=UTC declared explicitly in the service environment block (not relying on image default) to make the cron(hour=3) → 06:05 MSK pairing tamper-evident in code review."

patterns-established:
  - "Cron worker compose stanza: same image, same env_file, TZ=UTC, restart unless-stopped, depends on migrate (service_completed_successfully) + redis (service_started). Future v1.3+ cron workers (notifications, aggregations) follow this shape."
  - "REQUIREMENTS.md reconciliation pattern: when CD-N or a Key Decision diverges from research-vintage REQ wording, update the bullet in-place with an inline `(per Phase X CD-Y)` annotation; never silently delete the divergent text."

requirements-completed: [ARQ-04]

# Metrics
duration: 2min
completed: 2026-05-07
---

# Phase 18 Plan 04: ARQ worker compose service + REQUIREMENTS reconciliation Summary

**Adds the 5th `arq-worker` compose service (TZ=UTC + `uv run arq app.workers.WorkerSettings`) and reconciles two stale REQUIREMENTS.md bullets (ARQ-04 path per CD-02; ARQ-TEST-01 count per Phase 15 inclusive-end_date Key Decision).**

## Performance

- **Duration:** ~2 min
- **Started:** 2026-05-07T18:39:26Z
- **Completed:** 2026-05-07T18:40:58Z
- **Tasks:** 2
- **Files modified:** 2

## Accomplishments

- New `arq-worker` service in `apps/backend/docker-compose.yml` — the load-bearing operational artifact for the v1.2 cron tick (TZ=UTC + `cron(hour=3, minute=5)` = 06:05 Europe/Moscow).
- ARQ-04 REQ wording now matches the canonical compose location (`apps/backend/docker-compose.yml`), depends_on shape (migrate + redis only, no direct postgres), and full environment block (DATABASE_URL, REDIS_URL, TZ).
- ARQ-TEST-01 REQ wording now matches the shipped Plan 18-05 test (`exactly 1 newly-expired row` + explicit "today's row stays active until tomorrow's tick (inclusive end_date per Phase 15 Key Decisions)" clause), resolving the W-3 warning.

## Task Commits

1. **Task 1: Add `arq-worker` service to `apps/backend/docker-compose.yml`** — `c4ef0fb` (feat)
2. **Task 2: Reconcile REQUIREMENTS.md ARQ-04 + ARQ-TEST-01 wording** — `aae818b` (docs)

## Files Created/Modified

- `apps/backend/docker-compose.yml` — gains the `arq-worker:` service (15 additions, 0 deletions; `git diff` shows no changes outside the new block).
- `.planning/REQUIREMENTS.md` — 2 lines edited (ARQ-04 bullet rewritten with CD-02 annotation; ARQ-TEST-01 bullet count corrected to 1 + inclusive-end_date clause appended); traceability table rows for both REQs unchanged.

### `arq-worker:` block (verbatim, as committed)

```yaml
  arq-worker:
    build: .
    command: uv run arq app.workers.WorkerSettings
    env_file: .env
    environment:
      DATABASE_URL: postgresql+asyncpg://app:app@postgres:5432/sportzal
      REDIS_URL: redis://redis:6379/0
      TZ: UTC
    restart: unless-stopped
    depends_on:
      migrate:
        condition: service_completed_successfully
      redis:
        condition: service_started
```

### REQUIREMENTS.md ARQ-04 — before/after (one-line each)

- **Before:** `ARQ worker is added to \`infra/docker-compose.yml\` as a 5th service ... \`depends_on: [postgres, redis, migrate]\`, \`env_file: ../apps/backend/.env\`, \`environment: { TZ: UTC }\` ...`
- **After:**  `ARQ worker is added to \`apps/backend/docker-compose.yml\` (per Phase 18 CD-02 — the canonical compose file lives at \`apps/backend/\`, not \`infra/\`; relocation deferred to a future infra-consolidation phase) ... \`depends_on: [migrate (service_completed_successfully), redis (service_started)]\`, \`env_file: .env\`, \`environment: { TZ: UTC, DATABASE_URL: postgresql+asyncpg://app:app@postgres:5432/sportzal, REDIS_URL: redis://redis:6379/0 }\` ...`

### REQUIREMENTS.md ARQ-TEST-01 — before/after (one-line each, resolves W-3)

- **Before:** `... expects exactly 2 newly-expired rows and 2 audit events.`
- **After:**  `... expects exactly 1 newly-expired row (yesterday's, end_date < today) and exactly 1 \`membership_expired\` audit event; today's row (end_date == today) stays \`active\` until tomorrow's tick (inclusive end_date per Phase 15 Key Decisions).`

This reconciliation closes W-3 (stale-requirement warning): the requirement no longer asserts an outcome that contradicts the Phase 15 inclusive-`end_date` Key Decision and the shipped test in Plan 18-05.

## Decisions Made

- None new — both tasks were straightforward execution of CD-02 (path) and W-3 reconciliation (count). All deltas trace to either the locked CONTEXT.md decisions or the inclusive-`end_date` Key Decision from Phase 15.

## Deviations from Plan

None — plan executed exactly as written. Both tasks followed the verbatim service stanza and verbatim REQ-line replacements specified in `<action>` blocks. All automated `<verify>` checks (8 grep/yaml asserts in Task 1, 8 grep/count asserts in Task 2) passed on first run.

`docker compose -f apps/backend/docker-compose.yml config` exits 0 (Docker is locally available; no fallback needed). `git diff` for `apps/backend/docker-compose.yml` shows only additions inside the new `arq-worker:` block — `backend`, `telegram-bot`, `migrate`, `postgres`, `redis` services are byte-stable.

## Issues Encountered

- One environment quirk: the host shell has `python3` but no `python` alias. The plan's verify command used `python` literally. Switched to `python3` for the YAML structure assertion run; not a deviation, just a host-shell idiom.

## Operator Smoke Test (manual, optional)

Once Plan 18-03 lands and `app.workers.WorkerSettings` resolves, an operator can validate end-to-end with:

```bash
cd apps/backend
docker compose up arq-worker
# Expected: worker boots, on_startup binds db_lifespan_manager, structlog
# emits "WorkerSettings cron resolution OK", then idles until 03:05 UTC.
# At cron tick: bulk UPDATE runs, audit rows insert, summary log
# `expire_memberships_complete count=N` is emitted.
```

This is **not** part of the automated verify (Docker startup is heavy; the compose stanza itself is the static artifact this plan delivers).

## Next Phase Readiness

- Plan 18-03 (Wave 3 — `WorkerSettings` class + lifecycle hooks + cron registration) can now use this compose service as its production deployment surface. The `command:` in compose pins the canonical import path `app.workers.WorkerSettings`, removing any ambiguity about whether the class lives in `__init__.py` vs `arq_app.py` (CD-01 — `arq_app.py` is the deletion candidate).
- Plan 18-05 (test `count == 1` for ARQ-TEST-01) is now wording-aligned with REQUIREMENTS.md — no future verifier or reader will flag a contradiction.
- No blockers for downstream waves.

## Self-Check: PASSED

- File `apps/backend/docker-compose.yml` exists and contains `arq-worker:` (verified via grep).
- File `.planning/REQUIREMENTS.md` exists and contains the new ARQ-04 wording (verified via grep `apps/backend/docker-compose.yml` + `CD-02`) and the new ARQ-TEST-01 wording (verified via grep `exactly 1 newly-expired` + `inclusive end_date`).
- Commit `c4ef0fb` exists (verified via `git log`).
- Commit `aae818b` exists (verified via `git log`).

---
*Phase: 18-arq-scheduled-expire-memberships*
*Completed: 2026-05-07*

# Phase 2: Backend Skeleton with Quality Tooling — Discussion Log

> **Audit trail only.** Do not use as input to planning, research, or execution agents.
> Decisions captured in `02-CONTEXT.md` — this log preserves the discussion for retrospectives.

**Date:** 2026-04-30
**Phase:** 02-backend-skeleton-with-quality-tooling
**Mode:** discuss (default)
**Areas selected by user:** import-linter contract style & cross-edges; create_app() composition, lifespan & observability
**Areas deferred to Claude's discretion:** quality tooling depth; Settings shape & .env.example

## Area selection

**Question:** Which areas do you want to discuss for Phase 2 (Backend Skeleton)?
**Options presented:**
1. Quality tooling depth & calibration
2. import-linter contract style & cross-edges ✓
3. Settings shape & env conventions
4. create_app() composition, lifespan & observability ✓

**User selected:** Options 2 and 4.

## Area 1 — import-linter contract style & cross-edges

### Q1: Contract API style
**Options presented:**
- (a) Mixed: forbidden + independence (recommended) ✓
- (b) Pure layers contract
- (c) All forbidden (no independence)

**User chose:** (a). Reflected as **D-01** in CONTEXT.md.

### Q2: api → modules import allowed?
**Options presented:**
- (a) Yes — api wires module routers (recommended) ✓
- (b) No — registry indirection

**User chose:** (a). Reflected as **D-02** in CONTEXT.md.

### Q3: workers/modules → integrations allowed?
**Options presented:**
- (a) Both can import integrations (recommended) ✓
- (b) Only workers can import integrations
- (c) Neither — go through core service abstraction

**User chose:** (a). Reflected as **D-03** in CONTEXT.md.

### Q4: integrations → core allowed?
**Options presented:**
- (a) Yes — integrations read Settings + structlog (recommended) ✓
- (b) No — inject from caller

**User chose:** (a). Reflected as **D-04** in CONTEXT.md.

### Q5: How to implement the synthetic-violation check (ROADMAP #3)?
**Options presented:**
- (a) Plan verification step only — ad-hoc git stash diff (recommended) ✓
- (b) Permanent shell script
- (c) Permanent pytest test using subprocess

**User chose:** (a). Reflected as **D-05** in CONTEXT.md.

## Area 2 — create_app() composition, lifespan & observability

### Q1: Async SQLAlchemy engine lifecycle
**Options presented:**
- (a) Lifespan-managed engine (recommended) ✓
- (b) Module-level engine singleton

**User chose:** (a). Reflected as **D-06**, **D-07**, **D-08** in CONTEXT.md.

### Q2: request_id propagation mechanism
**Options presented:**
- (a) Custom ASGI middleware + structlog contextvars (recommended) ✓
- (b) uvicorn access log + structlog processors only
- (c) Third-party (asgi-correlation-id)

**User chose:** (a). Reflected as **D-09**, **D-10**, **D-11** in CONTEXT.md.

### Q3: Where do FastAPI exception handlers register?
**Options presented:**
- (a) core/exceptions.py defines errors + register_exception_handlers(app) (recommended) ✓
- (b) Inline @app.exception_handler decorators in main.py
- (c) core/middleware.py owns handler registration

**User chose:** (a). Reflected as **D-12**, **D-13** in CONTEXT.md.

### Q4: structlog dev-vs-prod renderer detection
**Options presented:**
- (a) Settings.environment Literal['dev','staging','prod'] (recommended) ✓
- (b) TTY detection (sys.stderr.isatty())
- (c) DEBUG flag (Settings.debug: bool)

**User chose:** (a). Drove the Settings shape under "Claude's Discretion" in CONTEXT.md.

## Wrap-up clarifications

### Q: /healthz path placement (resolving API-02 vs ROADMAP #2 tension)
**Options presented:**
- (a) /healthz at root via v1 router with empty prefix (recommended) ✓
- (b) /healthz mounted directly on FastAPI app, business under /api/v1
- (c) Both — /healthz at root AND /api/v1/healthz

**User chose:** (a). Reflected as **D-14** in CONTEXT.md, with explicit `# TODO Phase B+` comment requirement.

### Q: Continue to discuss tooling depth or Settings shape?
**Options presented:**
- (a) No — write CONTEXT.md (recommended) ✓
- (b) Also discuss tooling depth
- (c) Also discuss Settings shape & .env.example

**User chose:** (a). Tooling depth and Settings shape captured under "Claude's Discretion" in CONTEXT.md with sensible defaults (line-length 100, ruff DTZ/N/SIM/RUF added, no sqlalchemy mypy plugin, no env var prefix, working dev defaults in .env.example, uv.lock committed, etc.).

## Pattern observed

The user accepted the recommended option on **all 8 substantive questions** in Areas 1 & 2 (plus the /healthz wrap-up). Strong signal toward "use canonical/idiomatic FastAPI patterns" — recorded in CONTEXT.md `<specifics>` so planner/researcher default to canonical patterns when hitting undocumented sub-decisions.

## Deferred ideas captured (not discussed but flagged for later phases)

See `<deferred>` section in CONTEXT.md. Highlights:
- CORS middleware → Phase X+
- /api/v1 prefix → Phase B+
- Real auth logic → Phase C+
- Real Telegram/SMTP/ЮKassa → Phase X+
- ARQ task implementations → Phase B+
- Tests / Docker / docs → Phase 3
- Permanent synthetic-violation CI script → Phase 3 if needed

## Scope-creep events

None. The user's question selection stayed within the Phase 2 boundary defined by ROADMAP.md.

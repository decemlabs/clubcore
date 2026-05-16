# Phase 34: PT-Session Recording — Discussion Log

**Date:** 2026-05-16
**Mode:** `/gsd-discuss-phase 34 --auto`
**Pass cap:** 1 pass (auto-mode invariant)
**Output:** `34-CONTEXT.md`

This log records every gray area, the options Claude considered, and the recommended default Claude auto-selected. It is for human audit only — downstream agents (researcher, planner, executor) read `34-CONTEXT.md`, not this file.

---

## Auto-resolved gray areas

### Area 1: Migration shape

- **Q:** Single `0015_pt_sessions.py` revision, or bundled with `pt_packages` ALTER?
- **Options:**
  1. Single revision, `CREATE TABLE pt_sessions` only — no schema change to existing tables (RECOMMENDED).
  2. Bundle with ALTER `pt_packages` for any new column.
- **Selected:** Option 1. **Rationale:** No cross-table dependency requires bundling. `pt_packages.sessions_remaining` exists from Phase 33 D-33-03; CHECK `>= 0` already in place. Purely additive table.
- **Captured in:** D-34-01.

### Area 2: Race-safe decrement implementation

- **Q:** Use SQLAlchemy ORM (`sa.update(PtPackage).where(...).returning(...)`) — which forces a cross-module ORM import — or raw `text()` SQL by table name?
- **Options:**
  1. Raw `text()` SQL (RECOMMENDED) — avoids importing `pt_packages.models.PtPackage` into `pt_sessions.repository`; passes `import-linter modules-independent` contract.
  2. SA ORM with explicit importlinter exception for `pt_sessions → pt_packages.models`.
  3. New Protocol slot `register_pt_package_balance_mutator` in `core/dependencies.py`.
- **Selected:** Option 1. **Rationale:** v1.2 visits → clients precedent uses raw `text()` for cross-module table access. Slot proliferation (Option 3) is over-engineering for 2 SQL statements. ImportLinter exception (Option 2) erodes the contract over time.
- **Captured in:** D-34-04 / D-34-04a.

### Area 3: Auto-exhausted transition

- **Q:** When `sessions_remaining` decrements to 0, transition package status `active → exhausted` in the same UoW or via a separate flow?
- **Options:**
  1. Same UoW, single `audit.emit('pt_package_exhausted')`, predicate `WHERE status='active'` guards against concurrent refund (RECOMMENDED).
  2. Async/deferred via ARQ cron — needlessly complex.
- **Selected:** Option 1. **Rationale:** PT-17 explicit: "Auto-transition to 'exhausted' synchronously when decrement returns sessions_remaining = 0 (same UoW; emits pt_package_exhausted once)."
- **Captured in:** D-34-05.

### Area 4: Backdating window math (B-11)

- **Q:** Calendar-days in Europe/Moscow or exact 168h duration?
- **Options:**
  1. `timedelta(days=7)` exact duration (RECOMMENDED) — timezone-agnostic, easy to reason about.
  2. 7 calendar boundaries in Europe/Moscow — more intuitive but DST-prone (Moscow no DST since 2014; still complex to compute).
- **Selected:** Option 1. **Rationale:** Simpler implementation; Moscow's stable +03:00 offset since 2014 makes the difference between options negligible in practice.
- **Q (sub):** Future-dated permitted for owner-unlimited?
- **Options sub:**
  1. Reject future-dated for BOTH roles (RECOMMENDED) — recording is factual; can't record a session that hasn't happened.
  2. Allow owner future-dated (e.g., scheduling-via-recording).
- **Selected:** Option 1. **Rationale:** PT-session is a factual record, not a schedule. Scheduling is a separate domain (bookings/schedule).
- **Captured in:** D-34-06.

### Area 5: Cancel-window measurement origin (B-12)

- **Q:** Measure reception's 24h window from `created_at` (recording-time) or `performed_at` (session-time)?
- **Options:**
  1. `created_at` (RECOMMENDED) — B-12 says "within 24h of recording"; "recording" = INSERT moment.
  2. `performed_at` — would allow reception to record a session for last week and then cancel it today.
- **Selected:** Option 1. **Rationale:** Literal reading of B-12 + intent (correct immediate input mistakes).
- **Captured in:** D-34-07.

### Area 6: Cancel endpoint RBAC vs application-layer window

- **Q:** `(CANCEL, PT_SESSIONS)` is currently in `OWNER_ONLY` (Phase 30 INFRA-19 line 88). PT-18 / B-12 grants reception a 24h window. Resolve how?
- **Options:**
  1. Remove `(CANCEL, PT_SESSIONS)` from `OWNER_ONLY`; enforce 24h window in service layer (RECOMMENDED). Mirrors B-07 uniform-reception discipline for `(REFUND, MEMBERSHIPS)`.
  2. Keep strict RBAC; reception gets 403 even within 24h.
- **Selected:** Option 1. **Rationale:** B-12 verbatim grants reception the 24h window. RBAC layer can't express time-bounded permissions cleanly; application layer is the right place.
- **Side effects:** `core/permissions.py` line 88 removed; admin-web `can.ts` byte-parity entry also removed (admin-web is otherwise frozen, but tooling/parity fixes are permitted).
- **Captured in:** D-34-09 / D-34-09a.

### Area 7: Idempotency-Key on PT-session POSTs

- **Q:** Require `Idempotency-Key` on `POST /pt-sessions` and `POST /pt-sessions/{id}/cancel`?
- **Options:**
  1. Required on BOTH (RECOMMENDED) — mirrors Phase 32 / Phase 33 money-or-balance-mutating discipline.
  2. Required on record only; cancel idempotent via `already_cancelled` 409.
  3. Not required.
- **Selected:** Option 1. **Rationale:** Network retry on a 5xx mid-request could double-decrement (record) or double-restore (cancel). Idempotency layer is the first-line guard.
- **Captured in:** D-34-10.

### Area 8: Cancel → balance restoration scope

- **Q:** When canceling a session, when do we revert parent-package status?
- **Options:**
  1. Revert `exhausted → active` ONLY when prior_status was exhausted; leave `cancelled`/`expired` packages as-is (status stays terminal; balance still incremented for forensic correctness) (RECOMMENDED).
  2. Revert any non-active terminal status.
  3. Refuse cancel if parent package is non-active.
- **Selected:** Option 1. **Rationale:** PT-18 explicit "if package was exhausted, transition back to active" — no other revert. Refusing cancel on terminal packages (Option 3) loses forensic balance correctness.
- **Captured in:** D-34-11 / D-34-11a.

### Area 9: FSM extension policy

- **Q:** Add `exhausted → active` reverse transition to `PT_PACKAGE_STATUS_TRANSITIONS`?
- **Options:**
  1. NO — keep Phase 33 FSM unchanged; perform the reverse transition only via predicate-gated direct UPDATE in `pt_sessions.service.cancel_pt_session` (RECOMMENDED).
  2. YES — extend FSM, allowing any caller to perform the reverse transition.
- **Selected:** Option 1. **Rationale:** The reverse transition is a controlled-context operation tied to the invariant "we just freed a balance unit from an exhausted package." Generalising it (Option 2) weakens the FSM contract.
- **Captured in:** D-34-11a.

### Area 10: Trainer name source for `trainer_name_snapshot` (B-05)

- **Q:** How does `pt_sessions/service` obtain `trainer.full_name` without violating modules-independent?
- **Options:**
  1. Extend `TrainerById` Protocol with `full_name: str` (RECOMMENDED) — single additive attribute; ORM satisfies structurally; zero wiring change.
  2. New Protocol slot `register_trainer_name_resolver`.
  3. Read trainer.full_name via raw `text()` SELECT (separate from resolver).
- **Selected:** Option 1. **Rationale:** Single resolver call already validates existence+active — extending the same return type is the cheapest change. Phase 31 docstring updates to reflect.
- **Captured in:** D-34-12 / D-34-12a.

### Area 11: PT-package metadata read for record-flow

- **Q:** How to load `pt_package` row (status, client_id) given `pt_package_id` from request body?
- **Options:**
  1. Raw `text()` SELECT in `pt_sessions/repository.fetch_pt_package_metadata` (RECOMMENDED) — same escape hatch as decrement/increment.
  2. Use `get_active_pt_package(client_id)` slot — signature mismatch (slot is client→package, body has pt_package_id; would need 2 queries).
  3. Expand `ActivePtPackage` Protocol or add `register_pt_package_by_id_resolver`.
- **Selected:** Option 1. **Rationale:** Consistent with decrement/increment SQL pattern. Slot is purposed for client-history lookups, not record-flow.
- **Captured in:** D-34-13 / D-34-13a.

### Area 12: Read API URL shape

- **Q:** `GET /api/v1/pt-packages/{id}/sessions` (PT-19) is rooted at parent — does it live in `pt_packages/router.py` or `pt_sessions/router.py`?
- **Options:**
  1. Live in `pt_sessions/router.py` via a separate `APIRouter(prefix="/api/v1/pt-packages")` instance, mounted from aggregator (RECOMMENDED). Subject-side ownership principle (D-33-18).
  2. Live in `pt_packages/router.py` — would couple pt_packages to pt_sessions read patterns.
  3. Add a flat `GET /api/v1/pt-sessions?pt_package_id=...` endpoint instead of nested.
- **Selected:** Option 1. **Rationale:** PT-19 specifies nested URL; subject ownership keeps pt_packages clean.
- **Captured in:** D-34-08.

### Area 13: OpenAPI / `schema.d.ts` regen

- **Q:** Regen inside Phase 34 or defer to Phase 35?
- **Options:**
  1. Defer to Phase 35 (RECOMMENDED) — ROADMAP.md Phase 35 owns "atomic single-commit regeneration of all v1.4 typed paths."
  2. Regen inside Phase 34 — would create a partial drift state until Phase 35 reverts to atomic.
- **Selected:** Option 1. **Rationale:** ROADMAP.md descope-2026-05-15 explicit.
- **Captured in:** D-34-20.

### Area 14: Postgres-only race test

- **Q:** How to gate PTS-TEST-01 (concurrent recordings)?
- **Options:**
  1. `@requires_postgres` marker (SKIP on SQLite); Postgres CI gate runs it (RECOMMENDED) — Phase 33 D-33-19 precedent.
  2. Run unconditionally — SQLite cannot reproduce row-level locking semantics, will produce false-positives.
- **Selected:** Option 1. **Rationale:** Direct precedent from Phases 32/33 race tests.
- **Captured in:** D-34-19.

---

## Scope-creep redirects

None encountered (auto mode; no interactive turns).

## Deferred ideas captured

Recorded in `34-CONTEXT.md` `<deferred>` section:
- Edit-after-record (PATCH endpoint)
- Cross-package session history aggregation
- Multi-trainer-per-session
- No-show / late-cancel by client
- Trainer compensation / payroll
- Telegram bot `/sessions` self-history
- Server-side analytics endpoints
- admin-web UI (production ships in v2.0 by design team)
- `pt_session_recorded` payload hash
- Reception >7d backdating with owner-approval workflow
- Reverse cancel (un-cancel)

## Claude's discretion items

- Internal helper split between `pt_sessions/service.py` (orchestration) and `pt_sessions/repository.py` (SQL).
- `permissions.py` may be empty stub.
- Test file naming convention `test_pt_sessions_<concern>.py`.
- Repository helper signatures (positional vs keyword-only).
- Aggregator file for mounting the package-scoped sub-router.

---

*Auto-mode discussion completed in single pass. CONTEXT.md is the canonical artifact for downstream agents.*

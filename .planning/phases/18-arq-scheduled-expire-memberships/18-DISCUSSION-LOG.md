# Phase 18: ARQ scheduled `expire_memberships` - Discussion Log

> **Audit trail only.** Do not use as input to planning, research, or execution agents.
> Decisions are captured in CONTEXT.md — this log preserves the alternatives considered.

**Date:** 2026-05-07
**Phase:** 18-arq-scheduled-expire-memberships
**Areas discussed:** expire_due_memberships service contract

---

## Gray Areas Presented (multiSelect)

| Option | Description | Selected |
|--------|-------------|----------|
| Compose file path | `apps/backend/docker-compose.yml` (current) vs `infra/docker-compose.yml` (REQ wording) | |
| WorkerSettings placement vs arq_app.py | `__init__.py` (REQ) vs keep `arq_app.py` skeleton; deletion choice | |
| expire_due_memberships service contract | Layer placement, return shape, state-guard usage, RETURNING columns | ✓ |
| End-of-run observability + cron-resolve assertion | Defensive structlog summary + on_startup cron-resolve check | |

**User's choice:** Discuss only the service contract; defer the other three to Claude's discretion.

---

## expire_due_memberships service contract

### Sub-question 1 — Layering: where does the UPDATE + audit emit live?

| Option | Description | Selected |
|--------|-------------|----------|
| Service owns UPDATE + audit emits | `memberships/service.py:expire_due_memberships(session, today)` does the bulk `UPDATE … RETURNING id, client_id` and emits per row; worker is a thin wrapper that holds the session + commits. Mirrors Phase 17 cancel pattern; AST commit-gate already in scope; audit-co-transactional invariant preserved. | ✓ |
| Repository owns UPDATE; job emits | `repository.expire_due_rows(session, today)` does only the UPDATE; job-file holds `audit.emit` loop + commit. Job sees full logic in one place but skips BusinessService template; AST commit-gate doesn't cover worker code; loses Phase 17 symmetry. | |

**User's choice:** Service owns UPDATE + audit emits.
**Notes:** Captured as D-01 in CONTEXT.md. The wrinkle is that the worker (not the service) owns `session.commit()` because the worker also opens the session — this requires either an AST-gate auto-exemption for service functions called only from `app.workers.*`, or `# noqa: SVC001` with a documented one-line comment. Planner makes the explicit choice at plan time.

### Sub-question 2 — Return type: what does `expire_due_memberships` return to the worker?

| Option | Description | Selected |
|--------|-------------|----------|
| `int` (count) only | `expire_due_memberships(session, today) -> int`. ARQ writes the count into its result store; matches ROADMAP SC#1 wording ("flips due rows and returns the count") and the research-recommended sketch verbatim. Per-row IDs stay encapsulated. | ✓ |
| `list[tuple[UUID, UUID]]` (id, client_id) | Service returns the (membership_id, client_id) pairs that were expired; worker computes `len(rows)` + can log a sample. More flexible for future expiring-soon notifications, but exposes internal IDs and adds nothing v1.2 needs. | |

**User's choice:** `int` (count) only.
**Notes:** Captured as D-02 in CONTEXT.md.

### Sub-question 3 — State guard: does the bulk path call `_assert_can_expire` per row?

| Option | Description | Selected |
|--------|-------------|----------|
| No — SQL WHERE filter is the exclusive gate | Bulk `UPDATE … WHERE end_date < CURRENT_DATE AND status='active'` guarantees the active→expired transition (Postgres MVCC isolates concurrent admin cancels). `_assert_can_expire` stays in service.py for the TESTS-10 9-cell matrix but is not invoked by the bulk path — calling it would require an N+1 SELECT pre-flight contradicting ROADMAP SC#1's "single-transaction UPDATE…RETURNING". | ✓ |
| Yes — SELECT rows, call guard, per-row UPDATE | First `SELECT id WHERE … FOR UPDATE`, then per-row `_assert_can_expire(membership)` + `repository.update_status(…, status='expired')` + emit. Symmetric with cancel state-machine but loses bulk shape from ROADMAP SC#1 and PITFALLS recommendation. | |

**User's choice:** No — SQL WHERE is the exclusive gate.
**Notes:** Captured as D-03 in CONTEXT.md. `_assert_can_expire` is preserved in `service.py` (CD-06) for the TESTS-10 matrix, even though no production code calls it in v1.2.

---

## Claude's Discretion

The user did not select these areas for interactive discussion; defaults applied with explicit user-override hooks at plan-phase review:

- **CD-01:** Delete `app/workers/arq_app.py` (placeholder; ARQ-03 locks `app.workers.WorkerSettings` import path; keeping both creates two paths to the same class).
- **CD-02:** Add `arq-worker` service to existing `apps/backend/docker-compose.yml` rather than creating a new `infra/docker-compose.yml`. Reconciles ARQ-04 wording with current repo state via a small REQUIREMENTS.md edit or a deviation note in `18-VERIFICATION.md`.
- **CD-03:** Emit one structlog INFO `expire_memberships_complete count=N` from the worker entry after `session.commit()` returns successfully. PITFALLS Pitfall 14 mitigation step 1.
- **CD-04:** `on_startup` cron-resolution assertion (`assert all(c.coroutine.__name__ in {f.__name__ for f in functions} for c in cron_jobs)`). PITFALLS Pitfall 4 step 6 — catches silent no-op trap at boot, not at 06:05 the next morning.
- **CD-05:** Test placement under `tests/integration/workers/` and `tests/unit/workers/` (mirrors clients/memberships).
- **CD-06:** Keep `_assert_can_expire` in `service.py` (Phase 17 D-19 reference) even though no production caller; needed for TESTS-10 9-cell matrix.

## Deferred Ideas

- Bulk-aggregated audit event for runs > 200 rows (matters at 10+ zals, not single-zal v1.2).
- Expiring-soon Telegram notifications (v1.3+ feature; reuses Phase 18 worker infra).
- `time-machine` dev dep (defer until clock-patching tests get painful — Phase 18 uses parameterized `today` instead).
- `infra/docker-compose.yml` relocation (revisit if a future phase consolidates infra files).
- Multi-process ARQ workers per job class (single worker fine at v1.2 scale).

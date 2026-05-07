# Phase 19: Visits — DB + reception check-in (backend) - Discussion Log

> **Audit trail only.** Do not use as input to planning, research, or execution agents.
> Decisions are captured in CONTEXT.md — this log preserves the alternatives considered.

**Date:** 2026-05-07
**Phase:** 19-visits-db-reception-check-in-backend
**Mode:** `--auto` (Claude selected the recommended option for every gray area without interactive prompts)
**Areas discussed:** Cross-module resolver, Anti-fraud chain ordering + reject-path audit, Visit ORM shape, Settings / config, Bot-path edge cases, Tests / fixtures, Plan layout

---

## Cross-Module Resolver Pattern (Visits → Clients)

| Option | Description | Selected |
|--------|-------------|----------|
| Direct import `from app.modules.clients import ...` | Simplest code; one line in `visits/service.py` | |
| `ClientByTelegramResolver` Protocol via `core/dependencies.py` (mirror of Phase 17 `ActiveMembership`) | Preserves `modules-independent` import-linter contract; consistent with Phase 5 + Phase 17 cross-module precedents | ✓ |
| Wide D-06 telegram exception extension (workers→clients import) | Less elegant; doesn't help the visits service path | |

**Auto-selected option:** Protocol resolver via `core/dependencies.py` (D-02).
**Rationale:** Pitfall 7 mandates this pattern; `modules-independent` blocks the direct import; v1.x has two prior precedents (Phase 5 user_loader, Phase 17 active_membership) — Phase 19 makes it three and locks it as the project convention.

---

## Anti-Fraud Chain Order

| Option | Description | Selected |
|--------|-------------|----------|
| `gym_hours → active_membership → insert(unique)` | Cost-gradient ordering, matches REQUIREMENTS VIS-03 verbatim, matches the locked audit-event names | ✓ |
| `active_membership → gym_hours → insert(unique)` | Membership check first feels more "business" — but more expensive (DB hit before time check) | |
| `insert(unique) → fall-back checks` | "Optimistic" — IntegrityError discriminates, but inverts the audit semantics and breaks Pitfall 5 | |

**Auto-selected option:** Locked REQUIREMENTS order (D-03).

---

## Reject-Path Audit Emit + Commit

| Option | Description | Selected |
|--------|-------------|----------|
| Emit + commit + raise on EVERY rejection (deviates from Phase 16/17) | Persistent rejection trail for fraud-detection (Pitfall 9); matches VIS-AUDIT-01 + ROADMAP SC#5 verbatim | ✓ |
| Emit + raise (no commit; rollback at request boundary loses the audit row) | Matches Phase 16/17 pattern; loses anti-fraud signal | |
| No audit on rejections; only on success | Simplest; loses 100% of anti-fraud signal | |

**Auto-selected option:** Emit + commit + raise on every rejection (D-05).
**Notes:** D-08 sub-decision adds the `await session.rollback()` step before the audit-emit on the duplicate-checkin path, because the failed INSERT poisoned the session. Outside-hours and no-membership paths can emit + commit cleanly (no INSERT attempted yet).

---

## Reception + Bot Code Sharing

| Option | Description | Selected |
|--------|-------------|----------|
| Two public functions sharing a private `_create_visit_with_anti_fraud(...)` helper | Matches Pitfall 7 mandate: anti-fraud lives in service, not handler; structurally enforces parity between channels | ✓ |
| Two parallel public functions with copy-paste anti-fraud chains | Risk of channel divergence over time | |
| Single `create_visit(channel, ...)` with conditional branches | Loses type clarity at the call site (reception passes actor; bot passes telegram_user_id) | |

**Auto-selected option:** Shared private chain (D-04).

---

## Visit ORM — `gym_date` Computation

| Option | Description | Selected |
|--------|-------------|----------|
| Postgres GENERATED ALWAYS … STORED column via `sa.Computed("...", persisted=True)` | Race-proof; app cannot disagree on "today" with the DB; matches Pitfall 5 #1 mandate | ✓ |
| App-computed `gym_date` written by service before INSERT | Race window real (Pitfall 5: 23:59 UTC vs 02:30 MSK clock skew) | |
| Function-based partial unique on `(client_id, date_trunc('day', checked_in_at AT TIME ZONE 'Europe/Moscow'))` | Equivalent semantics; less ergonomic for Python ORM mapping | |

**Auto-selected option:** STORED GENERATED column (D-06).
**Notes:** D-15 enforces a real Postgres 16 migration test (`test_alembic_visits.py`) — the only test that proves the GENERATED expression actually runs. SQLite mocks would silently pass on a broken expression.

---

## Visit Soft-Delete Column

| Option | Description | Selected |
|--------|-------------|----------|
| No soft-delete; visits are immutable historical records | Matches Phase 17 Membership pattern (status-driven lifecycle, no `deleted_at`); UNIQUE constraint is unconditional | ✓ |
| Soft-delete column + partial unique `WHERE deleted_at IS NULL` | Allows "undo a wrong check-in" — but inflates the v1.2 spec; reversal is v1.3+ concern | |

**Auto-selected option:** No soft-delete (CD-04).

---

## VisitListQuery Sort Surface

| Option | Description | Selected |
|--------|-------------|----------|
| Fixed `checked_in_at DESC`; no sort enum | Smallest API surface; meets all v1.2 use cases (reception's "сегодня" + client history) | ✓ |
| Sort enum with `checked_in_at_desc / checked_in_at_asc / gym_date_desc` | Premature flexibility; no v1.2 consumer requests it | |

**Auto-selected option:** Fixed sort (D-09).

---

## Reception POST Body Surface

| Option | Description | Selected |
|--------|-------------|----------|
| Sealed body — `{clientId}` only; everything else server-derived | Removes every footgun (FE can't pre-date, override channel, swap membership); minimum trust surface | ✓ |
| `{clientId, channel?, paidAt?, ...}` allowing FE override | More flexible; opens replay/forge attack surface | |

**Auto-selected option:** Sealed body (D-01).

---

## Gym Hours Configuration

| Option | Description | Selected |
|--------|-------------|----------|
| Env vars `GYM_HOURS_START` / `GYM_HOURS_END` parsed by Pydantic v2 to `time` objects, with cross-field validator forbidding midnight-spanning ranges | Tunable per env without redeploy; matches research SUMMARY recommendation | ✓ |
| Hardcoded constants in `core/config.py` | No tunability; doesn't match v1.2 RU CRM conventions | |
| Per-day window with `Settings.gym_schedule: dict[Weekday, tuple[time, time]]` | v1.3+ for non-uniform schedules; overkill for single-zal v1.2 | |

**Auto-selected option:** Env-driven `time` fields with no-spanning validator (D-10, D-11).

---

## Bot-Path "Client Not Linked" Exception

| Option | Description | Selected |
|--------|-------------|----------|
| New `ClientNotLinkedError` (404) raised in service; Phase 20 handler maps to generic Russian DM | Type-safe + Pitfall 8 compliant (no oracle leak in DM) | ✓ |
| Reuse `ClientNotFoundError` from `clients` module | Forbidden — `visits → clients` import violates `modules-independent` | |
| Service silently returns None on unknown tg_id | Loses the typed-exception contract Phase 20 needs | |

**Auto-selected option:** `ClientNotLinkedError` in `core/exceptions.py` (D-12).

---

## VIS-TEST-01 Concurrent Test Fixture

| Option | Description | Selected |
|--------|-------------|----------|
| Sibling `db_session_real_commit` fixture (BEGIN/COMMIT per request, TRUNCATE on cleanup) for VIS-TEST-01 only | Avoids SAVEPOINT interference with concurrent INSERT serialisation | ✓ |
| Use the default SAVEPOINT `db_session` fixture for the concurrent test | SAVEPOINT can mask the IntegrityError ordering; risk of false-pass | |
| Skip the concurrent test; verify the constraint exists by SQL test | Loses Pitfall 5 / VIS-TEST-01 mandate | |

**Auto-selected option:** Real-commit fixture for VIS-TEST-01 (D-13).

---

## Plan Layout (5 vs 6 plans)

| Option | Description | Selected |
|--------|-------------|----------|
| 5 plans (migration+ORM+exceptions+config / resolver wiring / repo+service / router+openapi / tests) | Mirror Phase 16/17 cadence; well-bounded scope per plan | ✓ |
| 6 plans (split tests into integration vs unit) | Adds overhead; tests are tightly coupled to the surface they cover | |
| 4 plans (combine resolver into router plan) | Resolver wiring spans `core/dependencies.py` + `clients/service.py` + `app/main.py` — dedicates own plan for clarity | |

**Auto-selected option:** 5 plans (CD-01).

---

## Claude's Discretion

- **CD-01:** 5-plan layout matches Phase 16/17 cadence.
- **CD-02:** `19-04-PLAN.md` is BLOCKING-after-migration (Phase 17-04 precedent).
- **CD-04:** No soft-delete column on `visits`.
- **CD-05:** Single APIRouter at `/visits` (3 routes) — no router-split.
- **CD-06:** No midnight-spanning gym hours (forbidden at config load).
- **CD-07:** Gym-hours window is `[start, end)` — exclusive on the close boundary (`time = end` → reject).
- **CD-08:** `from`/`to` filter bounds inclusive on both ends.
- **CD-09:** VIS-TEST-01 uses non-SAVEPOINT db fixture (sibling of default `db_session`).

All `D-*` and `CD-*` decisions in CONTEXT.md are user-overridable at `/gsd-plan-phase` review.

## Deferred Ideas

- `GET /api/v1/visits/_meta` for FE gym-hours mirroring → Phase 22.
- D-1 "Кто сейчас в зале" aggregate card → Phase 22 (FE-10).
- D-6 reception per-user "today's visits" log → Phase 22.
- Visit reversal / cancel endpoint → v1.3+.
- Photo turnstile / NFC / geofence → v2+ (accepted residual fraud risk).
- Self check-in handler + Russian DM strings + Redis update_id dedup → Phase 20.
- Visit-count plans / hybrid plans → v1.3+.
- ILIKE search on visits → v1.3+ (only when visit volume exceeds reception's eyeball capacity).
- Midnight-spanning gym hours → v1.3+.
- `actor_kind: 'system' | 'user'` payload field → not needed (`actor_user_id IS NULL` already encodes system events).
- Bulk-aggregated `visit_created` audit event → revisit at >10 zals scale.

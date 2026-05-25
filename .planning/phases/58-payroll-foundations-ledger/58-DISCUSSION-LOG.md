# Phase 58: Payroll Foundations + Ledger - Discussion Log

> **Audit trail only.** Do not use as input to planning, research, or execution agents.
> Decisions are captured in CONTEXT.md — this log preserves the alternatives considered.

**Date:** 2026-05-25
**Phase:** 58-payroll-foundations-ledger
**Mode:** `--auto` — all gray areas auto-resolved to recommended defaults from the v1.9 research convergence (`.planning/research/SUMMARY.md`, `ARCHITECTURE.md`, `PITFALLS.md`). No interactive prompts; review CONTEXT.md before planning.

**Areas auto-resolved:** module placement; schema discipline; idempotency & error codes; endpoint shape; RBAC + audit pre-registration; cross-module access; clawback wiring; attribution model.

---

## Module placement

| Option | Description | Selected |
|--------|-------------|----------|
| New `app/modules/payroll/` module | Greenfield module; clean modules-independent contract | ✓ |
| Extend `app/modules/trainers/` | Co-locate with catalog data | |
| Extend `app/modules/payments/` | Reuse ledger module | |

**Auto-selected:** New `app/modules/payroll/` module.
**Rationale:** Locked by SUMMARY §1 + ARCHITECTURE.md Q1. `trainers` is catalog-only; `payments` is incoming-money ledger (payroll is outgoing wages — different domain). Co-locating would couple financial logic into non-financial modules and break the v1.4 ledger separation pattern.

---

## Comp-config schema discipline

| Option | Description | Selected |
|--------|-------------|----------|
| INSERT-only versioned with `effective_from` | New row per change; resolver picks latest <= today; snapshot at run time | ✓ |
| Single row with `UNIQUE (trainer_id)` upsert | UPDATE in place; simpler reads | |
| Two columns on the `trainers` table | No new table; minimal schema | |

**Auto-selected:** INSERT-only versioned with `effective_from`.
**Rationale:** PITFALL 5 (rate-config drift) directly motivates the snapshot discipline — mirrors v1.2 membership `price_kopecks_snapshot`. Upsert + UPDATE cannot satisfy "snapshot the rate in effect at run time" without time-travel queries. SUMMARY §1 explicitly resolves the FEATURES-vs-PITFALLS discrepancy in favor of the dedicated versioned table.

---

## Rate storage unit

| Option | Description | Selected |
|--------|-------------|----------|
| Basis points (`commission_pct_bps INT`) | 1% = 100 bps; integer math throughout | ✓ |
| Numerator + denominator | `rate_num INT` + `rate_den INT`; fully general fractions | |
| `NUMERIC(5,4)` / FLOAT | Native percentage type | |

**Auto-selected:** Basis points (single INT column).
**Rationale:** PITFALL 3 forbids FLOAT/NUMERIC for money math. Basis points + integer kopeck math + `math.ceil` rounding-in-trainer's-favor is the minimum-column form that satisfies all three constraints (no float, no rounding drift, no sum-of-parts mismatch). ARCHITECTURE.md uses bps; planner can't break this without re-litigating PITFALL 3.

---

## `comp_model` field

| Option | Description | Selected |
|--------|-------------|----------|
| Derived from nullable columns | Both NULL = no config; either non-NULL = active; hybrid = both | ✓ |
| Explicit `comp_model TEXT CHECK IN (...)` enum | Stronger validation; explicit modality | |

**Auto-selected:** Derived from nullable columns.
**Rationale:** REQUIREMENTS PAY-01 verbatim: "оба nullable; оба NULL = payroll для тренера не считается; гибрид допускается". The explicit-enum form would duplicate state and create CHECK-constraint redundancy with the column nullability. Matches the simplest interpretation of the requirement text.

---

## Accrual schema discipline

| Option | Description | Selected |
|--------|-------------|----------|
| Append-only signed-amount ledger; clawback = new negative row with self-FK | v1.4 payments-ledger pattern; immutable rows | ✓ |
| Append-only positive-only + separate `payroll_adjustments` table | Strict typing per row purpose | |
| Mutable rows with status='voided' | UPDATE in place | |

**Auto-selected:** Append-only signed-amount with self-FK clawback.
**Rationale:** PITFALL 1 (recompute drift) + PITFALL 4 (refund clawback) jointly mandate immutable rows + negative-adjustment semantics. Separate adjustments table doubles the schema for no semantic gain — the v1.4 payments ledger handles refunds in the same table with signed amounts, and PAY-06 explicitly says "append-only ... clawback-корректировка в payroll-ledger" (single ledger). REQUIREMENTS PAY-04 explicitly says "операции unpay нет" → rules out mutable/voided rows.

---

## Run idempotency mechanism

| Option | Description | Selected |
|--------|-------------|----------|
| `INSERT ... ON CONFLICT DO NOTHING RETURNING` on UNIQUE (trainer, period_start, period_end) | DB-wins-the-race; no TOCTOU | ✓ |
| Service-level pre-flight SELECT then INSERT | Application-controlled | |
| Application-level lock (Redis / advisory lock) | Distributed-systems pattern | |

**Auto-selected:** DB-wins-the-race ON CONFLICT.
**Rationale:** PITFALL 2 explicitly names the TOCTOU race in pre-flight-SELECT and rules it out. Existing project precedent (visits UNIQUE (client_id, gym_date), membership freeze UNIQUE WHERE ended_at IS NULL) uses the ON CONFLICT pattern verbatim. Partial UNIQUE INDEX `WHERE clawback_of_accrual_id IS NULL` lets clawback rows coexist with the regular accrual they offset.

---

## Endpoint surface

| Option | Description | Selected |
|--------|-------------|----------|
| Verb-flat endpoints (`POST /payroll/accruals`, `POST /payroll/accruals/{id}/mark-paid`, `GET /payroll/preview`, `PUT /payroll/trainer-configs/{id}`) | Mirrors project convention; clearest 409 surfaces | ✓ |
| Resource-nested (`POST /payroll/trainers/{id}/accruals`, `PATCH /payroll/accruals/{id}`) | Stronger trainer-scope semantics | |
| RPC-style (`POST /payroll/run`, `POST /payroll/mark-paid`) | Action-oriented | |

**Auto-selected:** Verb-flat endpoints.
**Rationale:** Matches existing `/api/v1/pt-packages/{id}/refund` precedent (a sub-action POST under a flat resource). `PATCH /payroll/accruals/{id}` would suggest general-purpose mutation — incompatible with PAY-04's single-allowed-transition semantics. Dedicated `mark-paid` sub-action communicates the single-transition guarantee at the URL.

---

## RBAC + audit pre-registration

| Option | Description | Selected |
|--------|-------------|----------|
| Pre-register ALL new OWNER_ONLY pairs + LOCKED_AUDIT_EVENTS in Phase 58 before callsites | INFRA-15 discipline | ✓ |
| Land pairs/events alongside their callsites incrementally | Smaller initial diff | |

**Auto-selected:** Pre-register all in Phase 58.
**Rationale:** ROADMAP Phase 58 SC#5 explicitly requires "all 6 new LOCKED_AUDIT_EVENTS and new OWNER_ONLY pairs ... are pre-registered before any callsite; three-way RBAC parity test ... is green". This is the Phase 54 INFRA-41/INFRA-42 pattern repeated for v1.9 — non-negotiable per project discipline.

---

## Cross-module access for payroll calculation

| Option | Description | Selected |
|--------|-------------|----------|
| Raw-SQL `text()` reads in `payroll/repository.py` | v1.8 reports module precedent; zero ignore_imports edges | ✓ |
| New Protocol slots exposed by `pt_sessions` + `payments` modules | Bi-directional callback pattern | |
| Direct ORM imports with new `ignore_imports` entries | Simplest code, breaks contract | |

**Auto-selected:** Raw-SQL `text()` reads.
**Rationale:** SUMMARY §"Architecture Approach": "v1.9 needs no new Protocol slots — all new cross-module access is read-only raw-SQL text()". Protocol slots exist for cross-module WRITES (clawback uses one for that reason); reads use raw SQL per D-54-08 / D-49-03. Direct ORM imports break the modules-independent contract; that's a non-starter.

---

## Clawback wiring (PAY-06)

| Option | Description | Selected |
|--------|-------------|----------|
| New `PayrollClawbackRecorder` Protocol slot, called from `pt_packages.service.refund_pt_package` in same UoW | Mirrors `PaymentRefunder` pattern | ✓ |
| Raw-SQL append from `pt_packages.service` | No new slot; minimal wiring | |
| Async event / message-bus fanout | Decoupled, eventually consistent | |

**Auto-selected:** New Protocol slot, same-UoW call.
**Rationale:** REQUIREMENTS PAY-06 explicitly requires "same-UoW". Async/event fanout breaks same-UoW (eventual consistency ≠ atomic). Raw-SQL append from `pt_packages.service` would either require an `ignore_imports` edge to payroll's ORM models OR an inline SQL JOIN against payroll tables from outside the payroll module — both break modules-independent. Protocol slot owned by payroll, called by pt_packages within the existing session, is the only pattern that satisfies all four constraints (same-UoW, modules-independent, append-only, audit-chained).

---

## Attribution model

| Option | Description | Selected |
|--------|-------------|----------|
| Hybrid: % on PT-package revenue → `pt_packages.trainer_id` (assigned); fixed-per-session → `pt_sessions.trainer_id` (conducted) | Uses unambiguous existing columns; matches single-gym semantics | ✓ |
| Always conducting trainer | Single attribution source | |
| Always assigned-at-sale trainer | Single attribution source | |
| Split between sold/conducted (largest-remainder method) | Multi-trainer attribution | |

**Auto-selected:** Hybrid with explicit per-component attribution.
**Rationale:** PITFALL 6 names this gray area and recommends exactly this hybrid as the canonical resolution for single-gym semantics. Single-attribution-everywhere mis-attributes one of the two component types. Splitting commission is overkill for a single-gym v1; deferred to a future multi-gym milestone. Inline `-- attribution: ...` comments on every payroll SQL prevent silent drift (project standard for ambiguous JOINs).

---

## Period boundary semantics

| Option | Description | Selected |
|--------|-------------|----------|
| Inclusive `[period_start, period_end]` MSK dates (BETWEEN ... AND ...) | Matches memberships.end_date + visits.gym_date | ✓ |
| Half-open `[period_start, period_end)` (`>= start AND < end`) | Python `range()`-style | |
| Inclusive start, exclusive end at midnight UTC | Database-friendly | |

**Auto-selected:** Inclusive MSK dates (BETWEEN).
**Rationale:** PITFALL 2 explicitly identifies half-open vs inclusive inconsistency as a recurring bug class in this codebase. The project has already standardized inclusive MSK dates everywhere (memberships, visits). Phase 58 inherits the convention; deviating would create a new bug surface.

---

## Claude's Discretion

These were left open for the planner because they're naming / cardinality decisions within already-locked boundaries:

- Exact wording of the 4–6 audit event names (minimum 4 listed in CONTEXT.md D-58-16; planner may split for finer granularity within ROADMAP SC#5's "6 new" target).
- Whether `(EDIT, COMPENSATION)` collapses into `(CREATE, COMPENSATION)` given the INSERT-only versioning model.
- Exact column order, index list, and constraint names in Alembic migration `0041_payroll_foundations.py`.
- Test file layout (one `test_payroll_*.py` per endpoint vs grouped) and exact deterministic kopeck amounts in golden tests.
- Whether `commission_pct_bps` upper bound stays at 10000 (100%) or is raised for promo > 100% commission cases.
- Whether `app/modules/payroll/constants.py` carries locally-pinned subject-kind literals.

## Deferred Ideas

Captured in CONTEXT.md `<deferred>` section. Highlights:

- Membership / online-refund → trainer clawback (PAY-06 is PT-package-only).
- Partial PT-package refund (B-02 still deferred from v1.4).
- `unpay` / accrual void (explicit anti-feature).
- Trainer self-service "view my accruals" portal.
- Compensation history endpoint.
- Filter-by-status on PAY-05 list.
- 1C / external payroll export, payroll PDF.
- `commission_pct_bps > 10000` (promo double-commission).

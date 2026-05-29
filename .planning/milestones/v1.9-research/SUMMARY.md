# Project Research Summary

**Project:** Sportzal
**Milestone:** v1.9 — Trainers Complete (payroll ledger + recurring schedule + time-off + trainer-usage report)
**Domain:** Single-gym CRM backend extension (FastAPI modular monolith, RF/СНГ)
**Researched:** 2026-05-24
**Confidence:** HIGH

## Executive Summary

v1.9 completes the trainer surface of the Sportzal backend. It adds four business capabilities to the existing modular monolith: (1) a **trainer payroll ledger** with per-trainer compensation config, owner-triggered payroll runs, and a "mark paid" lifecycle; (2) **recurring availability slots** generated ahead by an ARQ cron from day-of-week + time patterns; (3) **trainer time-off / unavailability blocks** that gate slot generation and guard against booked-slot conflicts; and (4) an owner-only **trainer-usage report** (sessions, hours, revenue attribution, CSV export). The four researchers converged strongly: every feature is implementable **with zero new dependencies** — the locked stack (Python 3.12, FastAPI, SQLAlchemy 2.0 async, Postgres 16, Redis, ARQ, structlog) plus stdlib `decimal` and `zoneinfo` covers all four features.

The recommended approach is to reuse three established disciplines verbatim rather than invent new patterns: the **v1.4 append-only payments ledger** (immutable accrual rows, atomic INSERT→flush→audit→commit UoW), the **v1.5 slot overlap + tstzrange + race-safe UNIQUE** discipline (extended to recurring generation and time-off), and the **v1.8 read-only reports discipline** (D-54-07/D-54-08: no `models.py`, raw-SQL `text()` cross-module reads, zero new import-linter ignores). New cross-module data access is read-only and therefore needs no Protocol slots — raw-SQL reads suffice. INFRA-15 pre-registration of `LOCKED_AUDIT_EVENTS` and three-way RBAC parity (backend `OWNER_ONLY` ↔ admin-web `can.ts` ↔ `registry.ts`) must land in the first phase, before any callsite.

The dominant risks are financial-correctness pitfalls, all with known precedents in this codebase: **recompute drift** (payroll must be an immutable point-in-time snapshot, not a live view), **rate-config drift** (compensation rate must be snapshotted into the accrual row, mirroring v1.2 membership price snapshots), **float rounding** (integer kopecks only; numerator/denominator rate, never a FLOAT column), **refund clawback** (a refund of an already-paid period must emit a negative adjustment row, not silently leave stale commission), and **idempotency races** on both payroll runs and the slot-generation cron (DB-wins-the-race UNIQUE + `INSERT ... ON CONFLICT DO NOTHING` + ARQ `unique=True`). Mitigation for every one is an established pattern already used elsewhere in the system.

## Key Findings

### Recommended Stack

**Verdict: zero new dependencies.** No library should be added to `pyproject.toml`. All four features reuse existing primitives plus Python stdlib. Adding `python-dateutil`/rrule, `pandas`/`numpy`, `pytz`, `icalendar`, `celery`/`dramatiq`, or any external decimal library is explicitly rejected — the recurrence model is simple DOW+time (≈15 lines of stdlib), aggregation happens in Postgres SQL, and kopeck math needs only `decimal.Decimal` / integer arithmetic.

**Core primitives to reuse:**
- **`decimal.Decimal` (stdlib)** — kopeck-accurate commission math; integer numerator/denominator rate, never float.
- **`zoneinfo.ZoneInfo('Europe/Moscow')` (stdlib)** — all MSK-local slot expansion and date-boundary conversion (`AT TIME ZONE 'Europe/Moscow'` in SQL).
- **v1.4 `payments` ledger pattern** — append-only ORM model, atomic audit chain, SVC001 commit-gate.
- **v1.5 `tstzrange` overlap detection** — extended for time-off and recurring-slot conflict checks.
- **v1.8 reports raw-SQL `text()` + `csv_export.py`** — UTF-8 BOM + RFC-4180 excel dialect.
- **ARQ cron `unique=True, keep_result=60`** — idempotent generate-ahead pattern (cron count goes 8 → 9).

Alembic migrations: current head is `0040`; v1.9 adds `0041`–`0046`.

### Expected Features

**Must have (table stakes, v1.9):**
- **PAY-01** — per-trainer compensation config (model: pct-of-revenue / fixed-per-session / both).
- **PAY-02** — payroll preview computation (read-only, no persistence).
- **PAY-03** — payroll accrual recording (append-only ledger row, immutable, period-unique).
- **PAY-04** — mark accrual as paid (single allowed lifecycle mutation; 409 if already paid).
- **PAY-05** — list accruals per trainer.
- **REC-01** — recurring slot pattern table + CRUD.
- **REC-02** — slot materialization ARQ cron (generate-ahead, bounded horizon).
- **REC-03** — time-off blocks: table + create/delete + 409 conflict guard on booked slots.
- **REC-04** — list patterns + time-off blocks.
- **RPT-01** — trainer load report (sessions, hours, utilization).
- **RPT-02** — PT-package revenue attribution per trainer.
- **RPT-03** — trainer report CSV export.

**Should have (differentiator, easy add):**
- **RPT-04** — payroll accrual summary (`total_accrued`/`total_paid`) folded into the trainer report; trivial once PAY-03 ships.

**Defer (v1.10+ / v2.0):**
- Trainer report frontend integration (admin-web frozen in v1.9).
- Per-session commission proration across period boundaries.
- 1C / external payroll export; iCal sync; recurring client-trainer booking; trainer self-service portal.
- Partial refund for PT-packages (B-02, still deferred from v1.4).

**Explicit anti-features:** tiered commission, reuse of the `payments` table for payroll, auto payroll-period detection, expand-on-read recurring slots, RRULE/EXDATE exceptions, real-time dashboards, predictive analytics, per-client breakdown in the trainer report.

### Architecture Approach

The backend is a FastAPI modular monolith with import-linter enforcing `app.core ↛ app.modules` and module-to-module independence; the only cross-module write mechanism is Protocol slots wired in `app/main.py`. v1.9 needs **no new Protocol slots** — all new cross-module access is read-only raw-SQL `text()`. The work lands across one new module plus two extensions.

**Major components:**
1. **`app/modules/payroll/` (NEW)** — owns `trainer_comp_configs` and `payroll_accruals` tables, the run/mark-paid/list service, and raw-SQL reads of `pt_sessions` + `pt_packages` + `payments`. Append-only ledger discipline; comp config lives here, **not** on `trainers`.
2. **`app/modules/schedule/` (EXTENDED)** — adds `recurring_slot_templates` and `trainer_time_off` tables, time-off conflict-check service (409 on booked overlap), and makes `trainer_availability_slots.created_by_user_id` nullable + adds UNIQUE `(trainer_id, start_time)` for cron idempotency.
3. **`app/modules/reports/` (EXTENDED)** — adds `fetch_trainer_usage` raw-SQL reader and `GET /reports/trainers` + `/reports/trainers.csv`, reusing all v1.8 read-only infrastructure.
4. **`app/workers/scheduled/generate_recurring_slots.py` (NEW)** — daily 07:00 MSK ARQ cron, generate-ahead with `ON CONFLICT DO NOTHING`, skips time-off windows, emits audit only on real inserts.
5. **`app/core/audit.py` + `permissions.py` (EXTENDED)** — 7 new LOCKED_AUDIT_EVENTS and ~5 new OWNER_ONLY pairs, pre-registered with three-way parity.

### Critical Pitfalls

1. **Recompute drift** — never compute payroll as a live view. Write an immutable `payroll_accruals` row at run time with snapshotted counts/revenue/rate; subsequent refunds or backdated sessions must not mutate it.
2. **Rate-config drift mid-period** — never read a mutable rate at run time. Snapshot the rate (numerator/denominator + config id) into the accrual row, mirroring v1.2 membership price snapshots; comp config is INSERT-only / versioned.
3. **Float rounding** — integer kopecks only; store rate as integer numerator/denominator (or bps), compute with `decimal`/integer math, pick one rounding mode and unit-test it. Never a FLOAT/NUMERIC money column.
4. **Idempotency / double-run + double-generate races** — DB-wins-the-race: UNIQUE `(trainer_id, period_start, period_end)` + `INSERT ... ON CONFLICT DO NOTHING RETURNING` (→ 409), UNIQUE `(trainer_id, start_time)` on slots + `ON CONFLICT DO NOTHING`, ARQ `unique=True` on the cron. Inclusive `[start, end]` date boundaries everywhere (matches memberships/visits).
5. **Time-off over a confirmed booking** — never auto-cancel silently. Query confirmed bookings in the window before insert; return 409 with conflicting booking IDs; owner cancels via the existing booking FSM. Generation cron skips time-off windows.
6. **Reports read-only leak / soft-deleted-trainer drop** — reports module stays `text()`-only with zero new import-linter ignores; historical aggregates use `LEFT JOIN`/`trainer_name_snapshot` and never filter on `is_active`. Period boundary off-by-one verified with a golden test.

### Discrepancy Resolutions

Three points where the early-stack/feature research and the deeper architecture/pitfalls research diverged. Resolved in favor of the stronger discipline:

1. **Comp config placement — `trainers` table columns (FEATURES PAY-01) vs. dedicated table (ARCHITECTURE / PITFALLS).** **Resolved: dedicated versioned `trainer_comp_configs` table in the `payroll` module.** Rationale: financial config must not couple into the catalog module, and PITFALL 5 (rate drift) requires an INSERT-only versioned config so a payroll run can snapshot the rate in effect. Two nullable columns on `trainers` cannot satisfy the snapshot requirement.

2. **Refund clawback — silent in FEATURES (anti-feature: "void accrual") vs. mandatory in PITFALLS 4.** **Resolved: clawback hook is required, modeled append-only.** A refund of a payment that appears in an already-paid accrual must emit a **negative adjustment accrual row** (not an UPDATE, not a void) in the same UoW as the refund. This preserves append-only discipline. FEATURES correctly rejects a destructive "void"; PITFALLS supplies the correct append-only form. The clawback hook must be designed into the refund integration path during the payroll phase, even if full implementation is staged.

3. **Phase count — FEATURES suggests 3–4 phases; ARCHITECTURE specifies 6 (58–63).** **Resolved: follow the 6-phase ARCHITECTURE structure (Phases 58–63).** Splitting payroll foundations (RBAC/audit/comp-config) from the payroll ledger, and the recurring-slot CRUD from its ARQ cron, isolates the INFRA-15 bedrock and the highest-risk concurrency surfaces into their own verifiable phases.

## Implications for Roadmap

Based on combined research, the suggested 6-phase structure (continuing from v1.8 which ended at Phase 57):

### Phase 58 — Foundations: RBAC parity + audit pre-registration + comp-config API
**Rationale:** INFRA-15 requires all 7 new LOCKED_AUDIT_EVENTS and the new OWNER_ONLY pairs to exist before any callsite; three-way RBAC parity must be green before any protected endpoint lands; comp config is the prerequisite for payroll computation.
**Delivers:** 7 audit events pre-registered; OWNER_ONLY entries + admin-web `can.ts`/`registry.ts` parity; `app/modules/payroll/` scaffold registered in `.importlinter` modules-independent list; `trainer_comp_configs` model + Alembic 0041; `GET`/`PUT /payroll/trainer-configs/{trainer_id}`; `trainer_comp_config_set` wired.
**Addresses:** PAY-01.
**Avoids:** PITFALL 5 (versioned INSERT-only config), security mistake (owner-only RBAC).

### Phase 59 — Payroll Ledger
**Rationale:** Depends on comp config from Phase 58. Highest financial-correctness surface — isolate it.
**Delivers:** `payroll_accruals` model + Alembic 0042; raw-SQL `fetch_trainer_session_revenue` reader; `run_payroll_period` + `mark_accrual_paid` services; `POST /payroll/run`, `PATCH /payroll/accruals/{id}/paid`, `GET /payroll/accruals`; `payroll_accrual_created` + `payroll_accrual_paid` wired; clawback hook design.
**Addresses:** PAY-02, PAY-03, PAY-04, PAY-05.
**Uses:** v1.4 append-only ledger, `decimal` integer math, raw-SQL cross-module read.
**Avoids:** PITFALLS 1 (snapshot not view), 2 (idempotent run via ON CONFLICT), 3 (integer rounding), 4 (clawback), 13 (concurrent run race), 6 (attribution model documented as a Key Decision before SQL).

### Phase 60 — Recurring Slots + Time-Off (schema + service)
**Rationale:** Independent of payroll; pure schedule extension. Land tables + synchronous service paths before the cron.
**Delivers:** `recurring_slot_templates` + `trainer_time_off` models + Alembic 0043/0044; Alembic 0045 (`created_by_user_id` nullable + UNIQUE `(trainer_id, start_time)`); template CRUD + time-off create/delete/list endpoints; `create_time_off` with 409 booked-conflict guard; `recurring_slot_template_created/cancelled` + `trainer_time_off_created/cancelled` wired.
**Addresses:** REC-01, REC-03, REC-04.
**Avoids:** PITFALL 9 (time-off vs confirmed booking 409), anti-pattern 3 (no cross-module auto-cancel of bookings).

### Phase 61 — Recurring Slot ARQ Cron
**Rationale:** Depends on Phase 60 tables/services. Concurrency-critical — isolate for race testing.
**Delivers:** `generate_recurring_slots.py` ARQ cron (07:00 MSK, `unique=True`); Alembic 0046 performance indexes; WorkerSettings cron extension; integration + race tests (idempotent re-run, time-off skip, audit only on real insert).
**Addresses:** REC-02.
**Avoids:** PITFALLS 7 (DST/zoneinfo expansion), 8 (bounded horizon), 14 (slot generation race).

### Phase 62 — Trainer-Usage Report
**Rationale:** Reads pt_sessions/payments (v1.4) + schedule data (Phase 60/61). Low risk, read-only addition to the v1.8 reports module. Comes after payroll so RPT-04 can fold in accruals.
**Delivers:** `fetch_trainer_usage` raw-SQL reader; `get_trainer_usage_report` + CSV rows; `GET /reports/trainers` + `/reports/trainers.csv`. Optional RPT-04.
**Addresses:** RPT-01, RPT-02, RPT-03 (+ RPT-04).
**Avoids:** PITFALLS 10 (no ORM import / zero new linter ignores), 11 (soft-deleted trainers included), 12 (inclusive period boundary golden test).

### Phase 63 — OpenAPI Handoff + Milestone Verification
**Rationale:** All business surfaces must be stable before regenerating the contract artifact.
**Delivers:** byte-stable `openapi.json` + `schema.d.ts` regen with all v1.9 paths; `_v19Checks` AssertNonNever guards; operator runbook `.planning/handoff/v1.9-trainers-runbook.md`; milestone verification gate.

### Phase Ordering Rationale
- **Bedrock first (58):** INFRA-15 + RBAC parity must precede any callsite; comp config gates payroll.
- **Payroll before its consumers:** accruals must exist for RPT-04 and for clawback hook reasoning.
- **Recurring CRUD (60) before cron (61):** the cron depends on template/time-off tables and the UNIQUE/nullable migration.
- **Report (62) after payroll/schedule:** reads data produced by earlier phases; lowest risk so it lands late.
- **Verification last (63):** OpenAPI regen requires a frozen surface.
- Payroll (58/59) and schedule (60/61) tracks have **no inter-dependency** and could be reordered, but the listed order keeps the highest-risk financial surface earliest.

### Research Flags

Phases likely needing deeper `/gsd-research-phase` during planning:
- **Phase 59:** payroll attribution model (sold-vs-conducted, PITFALL 6) and clawback integration into the existing refund path are decision-heavy; confirm the v1.4 refund flow touch-points before writing SQL.
- **Phase 61:** DST/zoneinfo expansion correctness and cron race semantics warrant a golden-test design pass.

Phases with standard, well-documented patterns (skip research-phase):
- **Phase 58:** mechanical RBAC/audit pre-registration — established discipline.
- **Phase 60:** schema + tstzrange overlap — direct reuse of v1.5 slot discipline.
- **Phase 62:** read-only report — verbatim reuse of v1.8 reports infrastructure.
- **Phase 63:** OpenAPI handoff — repeated per-milestone procedure.

## Confidence Assessment

| Area | Confidence | Notes |
|------|------------|-------|
| Stack | HIGH | Zero new deps; all findings from direct inspection of the locked stack and codebase. |
| Features | HIGH | Domain patterns well-understood; design choices align with existing bedrock; industry sources (MEDIUM) only corroborate compensation models. |
| Architecture | HIGH | Based on direct inspection of all relevant modules; no new Protocol slots; reuses three proven disciplines. |
| Pitfalls | HIGH | Every pitfall derived from existing PROJECT.md Key Decisions and v1.2–v1.8 precedent with a known mitigation. |

**Overall confidence:** HIGH

### Gaps to Address

- **Payroll attribution model (sold vs conducted)** — must be locked as a Key Decision (`D-5x-PAYROLL-ATTRIBUTION`) before any payroll SQL is written (Phase 59 planning). Recommendation: %-of-revenue → `pt_packages.trainer_id`; fixed-per-session → `pt_sessions.trainer_id`.
- **Rounding mode** — choose and document (ceil-in-trainer-favour per freeze-day precedent, or banker's `round()`); encode in `_compute_commission` with a dedicated unit test (Phase 59).
- **Clawback staging** — decide whether the negative-adjustment row is fully implemented in v1.9 or designed-with-hook now and completed alongside partial-refund work (B-02). Resolve in Phase 59 planning.
- **`payroll_accruals` paid lifecycle** — confirm the single-column `status`/`paid_at` flip is the only sanctioned mutation and is covered by the append-only AST gate (Phase 59).
- **Multi-trainer package revenue double-count** — acceptable at single-gym scale; document as a known limitation in the report (Phase 62).

## Sources

### Primary (HIGH confidence)
- Direct codebase inspection — `app/modules/payments/{models,service,constants}.py` (append-only ledger + UoW), `app/modules/reports/{repository,service}.py` + `csv_export.py` (D-54-07/08 read-only discipline), `app/modules/schedule/{models,service,repository}.py` (tstzrange overlap), `app/modules/pt_sessions/models.py` (existing indexes), `app/modules/trainers/models.py`, `app/core/{audit,permissions,dependencies}.py`, `app/workers/scheduled/expire_memberships.py`, `app/main.py`, `.importlinter`, `pyproject.toml`.
- `.planning/PROJECT.md` — v1.9 milestone scope + locked Key Decisions (snapshot pricing v1.2, ceil rounding v1.3, DB-wins-the-race v1.2/v1.3/v1.5, append-only ledger v1.4, INFRA-15 v1.3, D-54-07/08 v1.8, `trainer_name_snapshot` v1.4, three-way RBAC parity).
- Python stdlib — `decimal`, `zoneinfo` (3.9+, present in 3.12).

### Secondary (MEDIUM confidence)
- ISSA / NESTA / Wellyx / Gymdesk — gym commission-structure industry practice (corroborates 3-model compensation).
- SchedulingKit / Trainerize / SmartHealthClubs — fitness scheduling + trainer-utilization KPI conventions (65–70% utilization target).

### Tertiary (LOW confidence)
- None — all findings traced to codebase precedent or official stdlib; industry sources only corroborate non-load-bearing design choices.

---
*Research completed: 2026-05-24*
*Ready for roadmap: yes*

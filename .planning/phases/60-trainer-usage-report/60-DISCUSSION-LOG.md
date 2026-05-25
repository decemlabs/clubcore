# Phase 60: Trainer-Usage Report - Discussion Log

> **Audit trail only.** Do not use as input to planning, research, or execution agents.
> Decisions are captured in CONTEXT.md — this log preserves the alternatives considered.

**Date:** 2026-05-25
**Phase:** 60-trainer-usage-report
**Mode:** `--auto` (no interactive AskUserQuestion calls; recommended defaults auto-selected and grounded in REQUIREMENTS RPT-01..04, STATE.md `D-REPORT-READONLY`/`D-58-21`, and v1.9 research).
**Areas discussed:** Module placement & discipline, Query shape (CTE vs N+1), `total_hours` derivation, Payroll period match (RPT-04), `utilization_pct` formula, Revenue attribution + double-count disclosure, RBAC, Pagination, Audit emission, CSV export, Endpoint registration, Test discipline

---

## Module placement & discipline (D-60-01..02)

| Option | Description | Selected |
|--------|-------------|----------|
| Extend existing `app/modules/reports/` under D-54-07/08 (raw-SQL only, no `models.py`, zero new linter ignores) | Re-applies the v1.8 reports discipline; RPT-04 acceptance criterion mandates zero new ignores | ✓ |
| Create new `app/modules/trainer_reports/` module | Would force a duplicate `csv_export.py`/permissions wiring; no benefit, violates "extend not replace" v1.9 stance |  |
| Cross-module ORM imports (e.g. `from app.modules.pt_sessions.models import …`) | PITFALL 10 — violates `modules-independent` contract; explicitly rejected |  |

**Decision:** Extend `reports/` module under D-54-07/08; raw-SQL `text()` only; zero new `ignore_imports`. CI gate adds `lint-imports && git diff --exit-code .importlinter`.

---

## Query shape (single CTE vs N+1)

| Option | Description | Selected |
|--------|-------------|----------|
| Single CTE-driven `LEFT JOIN` pyramid (one SQL statement) | Matches `fetch_revenue_buckets` precedent; one round-trip; deterministic ordering; easy golden-test | ✓ |
| Per-trainer subquery loop (N+1) | O(N) round-trips; harder to reason about timezone semantics; slower |  |
| Materialized view + daily refresh | Premature for small-N (O(10) trainers); deferred to future milestone |  |

**Decision:** Single CTE shape — `session_agg` + `slot_agg` + `revenue_agg` + `payroll_agg`, `LEFT JOIN` onto `trainers` with NO `is_active` filter (PITFALL 11), period filter via `AT TIME ZONE 'Europe/Moscow'`, signed accrual sum (clawback nets out), `NULLIF` guards on division.

---

## `total_hours` derivation (D-60-04)

| Option | Description | Selected |
|--------|-------------|----------|
| Derive from booked slot's `(end_time - start_time)` via `pt_sessions → bookings → trainer_availability_slots` chain; sessions with no booking contribute `0.0` hours | Matches research's `EXTRACT(EPOCH FROM (s.end_time - s.start_time))`; canonical duration source; avoids fabricating synthetic hour from `performed_at` | ✓ |
| Hard-code a default session duration (e.g. 1.0h) for sessions without a booking | Misleading; fabricates data |  |
| Drop sessions without bookings from `total_hours` AND `session_count` | Wrong: the sessions happened and should count toward load |  |

**Decision:** Slot-derived hours; walk-in sessions (no booking) contribute `0.0` hours but still count in `session_count`. Documented in a `methodology_note` field.

---

## Payroll period match (D-60-05)

| Option | Description | Selected |
|--------|-------------|----------|
| Period **overlap** (`period_start <= :to AND period_end >= :from`); FULL signed sum, no proration | Includes accruals that straddle boundaries; matches v1.9 "no proration" anti-feature stance; clawbacks net out via signed sum | ✓ |
| Period **fully contained** within window | Drops straddling accruals — misleading for monthly reports overlapping a payroll period |  |
| Prorate straddling accruals by day count | Explicit v1.9 anti-feature ("per-session commission proration across period boundaries → v1.10+") |  |

**Decision:** Overlap match; full signed amount per accrual; documented in `methodology_note` (or `payroll_period_match_note`).

---

## `utilization_pct` formula (D-60-06)

| Option | Description | Selected |
|--------|-------------|----------|
| `booked_hours / published_hours`, where `published = active + booked` (cancelled slots excluded from both); NULL when 0 active|booked slots; 0.0 when slots exist but none booked | Matches REQUIREMENTS RPT-01 ("NULL при 0 слотов"); excludes withdrawn capacity (`cancelled`) from denominator | ✓ |
| Include `cancelled` slots in denominator | Inflates denominator with withdrawn capacity; deflates utilization unfairly |  |
| Use recurring slot templates instead of materialized slots | Templates are forward-looking patterns; the report aggregates actual published-vs-booked reality |  |

**Decision:** `(booked_hours / published_hours) * 100`; `published = active + booked` (no `cancelled`); NULL when zero `active|booked` slots in period; round to 2 decimal places at wire layer.

---

## Revenue attribution + double-count disclosure (D-60-07)

| Option | Description | Selected |
|--------|-------------|----------|
| Assigned-at-sale (`pt_packages.trainer_id`) per LOCKED D-58-21; document multi-trainer-package limitation in response envelope `revenue_attribution_note` field | Matches the locked attribution model already used by payroll commission accruals; consistency across financial surfaces | ✓ |
| Conducting trainer (`pt_sessions.trainer_id`) | Would diverge from D-58-21 payroll attribution; breaks the "revenue ≈ commission base" mental model |  |
| Both columns side-by-side | Doubles the SQL complexity; surface confusion for owner; deferred to v2.0 multi-trainer-package feature |  |

**Decision:** Assigned-at-sale; envelope field `revenue_attribution_note` carries the documented limitation string (module constant in `reports/constants.py`).

---

## RBAC (D-60-08)

| Option | Description | Selected |
|--------|-------------|----------|
| Reuse existing `(Action.VIEW, Resource.REPORTS)` OWNER_ONLY pair | Already in `permissions.py:65`; no `can.ts`/`registry.ts` edits; three-way parity test invariant; admin-web stays frozen | ✓ |
| Introduce new `Resource.TRAINER_REPORTS` enum + OWNER_ONLY pair | Would force three-way RBAC edits in v1.9 (admin-web freeze violation); no granularity benefit since both endpoints are owner-only |  |

**Decision:** Reuse `(VIEW, REPORTS)`; zero RBAC edits; route-introspection guard auto-verifies reception → 403.

---

## Pagination (D-60-09)

| Option | Description | Selected |
|--------|-------------|----------|
| Single-shot non-paginated response (all trainers) | O(10) trainers in single-gym domain; matches `fetch_revenue_buckets` precedent; CSV is single-shot stream | ✓ |
| `{items, total, page, pageSize}` envelope | Over-engineering for O(10) rows; complicates CSV export (which exports full dataset anyway) |  |

**Decision:** All trainers in one response; revisit if trainer count exceeds ~100 in a future milestone.

---

## Audit emission (D-60-10)

| Option | Description | Selected |
|--------|-------------|----------|
| ZERO new `LOCKED_AUDIT_EVENTS`; HTTP access log + AUD-01..06 cover the security surface | Matches `/reports/revenue` precedent (no `revenue_report_viewed` event); keeps cardinality flat | ✓ |
| Emit `trainer_report_viewed` + `trainer_report_exported` domain events | Inconsistent with v1.8 reports; would force `LOCKED_AUDIT_EVENTS` growth for a read-only GET surface |  |

**Decision:** Delta = 0 new events; reads are observable via access log.

---

## CSV export (D-60-11)

| Option | Description | Selected |
|--------|-------------|----------|
| Reuse `csv_export.py` BOM + `csv.writer` + StreamingResponse verbatim; `sanitize_csv_text` on `trainer_name_snapshot` only; Russian header strings; `utilization_pct = NULL` → empty cell | Matches Phase 56 EXP-01..04 discipline; passes Excel Cyrillic test; covers formula-injection (CR-01 / T-56-07) on the only free-text column | ✓ |
| Apply `sanitize_csv_text` to all columns including numerics | Wrong — refund-driven negative `total_accrued_kopecks` legitimately starts with `-`; sanitizing would corrupt money cells |  |
| Render `NULL` cell as the string `"NULL"` or `"None"` | Breaks Excel numeric column inference; violates CSV-RFC null convention |  |

**Decision:** Verbatim reuse; `sanitize_csv_text` only on `trainer_name_snapshot`; NULL → empty cell; filename pattern `trainer-usage-{from}-{to}.csv`.

---

## Endpoint registration (D-60-12)

| Option | Description | Selected |
|--------|-------------|----------|
| Mount both endpoints on existing `router` (NOT `audit_log_router`) in `reports/router.py`; CSV uses `response_class=StreamingResponse` matching `/revenue.csv` (L143) | Same `APIRouter` already mounted under `/api/v1/reports/` via `app/api/v1/router.py`; no new mount needed | ✓ |
| Create a separate `trainer_report_router` instance | Unnecessary; complicates `app/api/v1/router.py` includes |  |

**Decision:** Mount on existing `router`; full OpenAPI metadata declared so Phase 61 `openapi.json` regen captures them byte-stably.

---

## Test discipline (D-60-13)

| Option | Description | Selected |
|--------|-------------|----------|
| Mandatory PITFALL goldens (6, 10, 11, 12) + RPT-04 clawback netting + `utilization_pct` NULL/0.0 + CSV BOM/CRLF/Cyrillic/sanitize golden; reception 403 via route-introspection guard | Mirrors Phase 57 VER-02 / Phase 58 PITFALL-13 precedent; each pitfall has a named test with top-of-file comment citing the pitfall | ✓ |
| Skip the import-linter grep guard (rely on CI lint-imports alone) | RPT-04 explicitly mandates zero new ignores; a redundant grep guard is cheap insurance against accidental edits to `.importlinter` |  |

**Decision:** All PITFALL goldens are SHIP gates; `lint-imports && git diff --exit-code .importlinter` is a CI requirement; grep guard against `from app.modules.* import` inside `app/modules/reports/` is added as a pre-commit or test guard.

---

## Claude's Discretion

(See D-60 "Claude's Discretion" section in CONTEXT.md for the canonical list.)

- Exact CTE names + column casts in the SQL.
- Single `notes: list[str]` envelope field vs separate named string fields (`revenue_attribution_note`, `methodology_note`, `payroll_period_match_note`).
- Exact CSV header strings in Russian (matching `revenue.csv` cadence).
- Query-string param naming (`from_date`/`to_date` recommended over `from`/`to`).
- Exact constant name and location for the revenue attribution note string.
- Test file granularity (recommended: one combined `test_trainer_usage.py`).

## Deferred Ideas

(See CONTEXT.md `<deferred>` section for the canonical list.)

- Multi-trainer-package revenue de-duplication / proration (v2.0).
- Per-session commission proration across period boundaries (v1.10+).
- `apps/admin-web` UI integration for the trainer report (post-Phase 61, when `schema.d.ts` is regenerated).
- Caching / materialized view for the report (introduce when query plan degrades).
- Pagination on the trainer list (when count exceeds ~100).
- `report_viewed` / `report_exported` domain audit events (future observability milestone).
- 1C / external payroll export, iCal sync, real-time dashboards, predictive analytics, per-client breakdown.

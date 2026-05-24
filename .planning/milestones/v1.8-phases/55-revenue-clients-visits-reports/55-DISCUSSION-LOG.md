# Phase 55: Revenue + Clients + Visits Reports — Discussion Log

**Date:** 2026-05-24
**Mode:** `--auto` (autonomous — recommended option selected for every gray area; no interactive prompts)

> Human-reference audit trail. Not consumed by downstream agents (researcher/planner/executor read `55-CONTEXT.md`).

## Gray areas auto-selected

`[--auto] Selected all gray areas: Revenue response shape, Date-range semantics & validation, Empty-bucket policy, Visits response composition, Aggregation-index choice.`

## Decisions

### Revenue response shape (REV-01..04)
- **Q:** Flat pivot rows vs nested per-bucket breakdown by method × subject_kind?
- **Selected:** Nested per-bucket object `{ period, netKopecks, byMethod, bySubjectKind }`; refunds net into `netKopecks` as signed sums (recommended default).
- Note: flagged optional per-bucket `refundKopecks` transparency field for researcher to confirm.

### Date-range semantics & validation
- **Q:** Required from/to? Inclusive MSK bounds? Window cap? `within` range?
- **Selected:** from/to required for revenue+visits, inclusive Europe/Moscow day bounds, 366-day window cap (422 over-cap), `within` 1..30 default 7 (v1.3 parity). For clients, from/to scopes only the new-clients counter (recommended default).

### Empty-bucket policy
- **Q:** Zero-fill missing periods/hours vs sparse?
- **Selected:** Sparse — only buckets with data; zero-fill deferred to v2.0 frontend. Average computed over full calendar range, not days-with-visits (recommended default).

### Visits response composition (VIS-R-01..03)
- **Q:** One endpoint returning daily + hourly + average, or split endpoints?
- **Selected:** Single `GET /reports/visits` returning `{ daily, hourly, averagePerDay }` (recommended default — matches SC#3 which lists all three under one endpoint).

### Response envelope / pagination
- **Q:** `PaginatedData[T]` vs bespoke `ResponseEnvelope[T]` payload?
- **Selected:** `ResponseEnvelope[T]` with aggregate payloads; no pagination on aggregates (recommended default).

### Aggregation-index choice
- **Q:** Add revenue composite index `(received_at, method, subject_kind)` now?
- **Selected:** Defer — no new index unless `EXPLAIN ANALYZE` shows a harmful seq scan (recommended; D-54-10 carried the decision to Phase 55 query-plan evidence).

## Scope-creep redirects
- Top-trainers + PT-usage report → out of v1.8 (owner decision); deferred to v1.9/v2.0.
- CSV export + audit-log read API → Phase 56.
- OpenAPI handoff + operator runbook → Phase 57.

## Deferred ideas
- Per-bucket `refundKopecks` field; zero-filled bucket gaps; revenue composite index (on evidence). See `55-CONTEXT.md` §Deferred.

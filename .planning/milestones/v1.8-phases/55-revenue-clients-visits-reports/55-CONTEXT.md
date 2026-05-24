# Phase 55: Revenue + Clients + Visits Reports - Context

**Gathered:** 2026-05-24
**Status:** Ready for planning
**Mode:** `--auto` (decisions auto-selected to recommended defaults; review before planning)

<domain>
## Phase Boundary

Fill the three read-only aggregate report endpoints into the `app/modules/reports/`
scaffold that Phase 54 already wired (import-linter contract, `(VIEW, REPORTS)`
owner-only RBAC, aggregation indexes). All three return authenticated JSON over
`ResponseEnvelope[...]`; money stays integer kopecks; every date bucket is
deterministic in Europe/Moscow.

**In scope (REV-01..05, CLR-01..04, VIS-R-01..04):**
1. `GET /api/v1/reports/revenue?from=&to=&groupBy=day|month` — net revenue buckets
   from the append-only `payments` ledger, broken down by method (`cash`/`online`)
   and `subject_kind` (`membership`/`pt_package`), refunds subtracting as signed rows.
2. `GET /api/v1/reports/clients?from=&to=&within=N` — active membership count,
   expiring-within-N-days count (default 7, range 1..30), new-clients count for a
   date range; all counters exclude soft-deleted rows.
3. `GET /api/v1/reports/visits?from=&to=` — visit counts by `gym_date`, a grouping
   by hour-of-day (peak hours), and average visits/day for the period.

**Out of scope (later phases):**
- CSV export endpoints + StreamingResponse → **Phase 56** (EXP-01..04).
- Audit Log read API → **Phase 56** (AUD-01..06).
- OpenAPI byte-stable regen + `AssertNonNever` forward-guards + operator runbook
  → **Phase 57** (HND/VER). Phase 55 ships endpoint bodies + correctness tests only.
- Frontend dashboards / money formatting → v2.0.
- Top-trainers + PT-usage report → deferred to v1.9/v2.0 (owner decision 2026-05-24).

</domain>

<decisions>
## Implementation Decisions

> Architectural baseline is **locked by Phase 54** (`54-CONTEXT.md` D-06..D-12): raw-SQL
> `text()` cross-module reads (zero new `ignore_imports`), no `models.py` in reports,
> read-only (no SVC001 gate), owner-only via `require_permission(Action.VIEW,
> Resource.REPORTS)`. These are NOT re-decided here.

### Revenue response shape (REV-01..04)
- **D-01:** Each period bucket is a **nested object**, not flat pivot rows:
  `{ period: "2026-05-01" | "2026-05", netKopecks, byMethod: { cash, online },
  bySubjectKind: { membership, ptPackage } }`. Refunds (`subject_kind='refund'`,
  negative `amount_kopecks`) fold into `netKopecks` as signed sums so net revenue is
  correct (REV-04). The refund slice is surfaced separately only inside `netKopecks`
  reduction — `bySubjectKind` keys stay the two positive kinds (refunds are not their
  own subject in the breakdown; they net against the period total).
  - ⚠ **Researcher confirm:** whether owner also wants a `refundKopecks` field exposed
    per bucket for transparency. Default = net-only; add `refundKopecks` if cheap.
- **D-02:** One SQL aggregate `GROUP BY` period-bucket + `method` + `subject_kind` over
  `payments`, pivoted to the nested shape in Python (`service.py`). `period` derived via
  `(received_at AT TIME ZONE 'Europe/Moscow')::date` then `date_trunc('month', ...)` for
  `groupBy=month`. `received_at` is the single temporal column (D-32-01..04;
  `payments/models.py:64`).
- **D-03:** `groupBy` is a literal enum `day` | `month`, **default `day`**. Define as
  `GRAIN_DAY` / `GRAIN_MONTH` constants in `reports/constants.py` (scaffold pre-declared
  `__all__` for them).

### Date-range semantics & validation (all three reports)
- **D-04:** `from` / `to` are `YYYY-MM-DD` **date** query params interpreted as
  **inclusive** Europe/Moscow day bounds. Revenue/visits SQL filters
  `(received_at AT TIME ZONE 'Europe/Moscow')::date BETWEEN :from AND :to`; visits filters
  directly on `gym_date BETWEEN :from AND :to` (already STORED MSK — no secondary TZ
  conversion, VIS-R-04 / D-54 discipline).
- **D-05:** `from`/`to` are **required** for revenue and visits (reject missing with 422);
  for clients, `from`/`to` scope **only** the new-clients counter (CLR-03) — active/expiring
  counters are "as of now" and ignore the range. `to < from` → 422.
- **D-06:** Cap the window at **366 days** (`to - from`) to bound aggregation cost on a
  read endpoint; over-cap → 422 `report_range_too_large`. Single-gym volume is low, but
  the cap prevents accidental unbounded scans.
- **D-07:** `within` (CLR-02) validated `1..30`, **default 7** — byte-parity with the v1.3
  expiring-soon `?within=N` selector. Out-of-range → 422.

### Empty-bucket policy
- **D-08:** Reports return **sparse** buckets — only periods/hours with data appear; no
  zero-fill via `generate_series`. Zero-filling gaps is a presentation concern deferred to
  the v2.0 frontend. Keeps SQL a plain `GROUP BY`. (VIS-R-03 average is still computed over
  the **full calendar range** — see D-10 — not over days-with-visits.)

### Visits response composition (VIS-R-01..03)
- **D-09:** **One** endpoint `GET /reports/visits` returns all three views in a single
  payload: `{ daily: [{ date, count }], hourly: [{ hour, count }], averagePerDay }`. Daily
  groups by `gym_date`; hourly groups by `EXTRACT(HOUR FROM checked_in_at AT TIME ZONE
  'Europe/Moscow')` (0..23) aggregated across the whole range for peak-hour analysis.
- **D-10:** `averagePerDay` = total visits in range ÷ **number of calendar days in the
  requested range** (inclusive `to - from + 1`), per VIS-R-03 wording ("visits / число
  дней"). Returned as a number (kopecks discipline does not apply — this is a count ratio;
  rounding/format deferred to frontend, send raw float or 2-dp — researcher to pick).

### Response envelope / pagination
- **D-11:** Reports are **aggregates, not lists** — wrap each in `ResponseEnvelope[T]` via
  `envelope(...)` with a bespoke payload DTO; do **NOT** use `PaginatedData[T]`
  (`{items,total,page,pageSize}` is for the Phase 56 audit-log listing, not aggregates).
  Query DTOs (`RevenueReportQuery` etc.) extend `BackendSchemaBase`, not `PageQuery`
  (no pagination on aggregates). Response DTOs extend `BackendSchemaBase` (`extra='forbid'`).
  Wire is camelCase; Python snake_case.
- **D-12:** Mount the router in `app/api/v1/router.py` as
  `v1.include_router(reports_router, prefix="/reports", tags=["reports"])`. RBAC enforced
  at the route via `Depends(require_permission(Action.VIEW, Resource.REPORTS))`; reception
  → 403 (SC#4). The existing route-introspection guard covers the new routes automatically.

### Aggregation indexes
- **D-13:** **No new index in Phase 55 by default.** `ix_payments_received_at` (DESC) and
  the visits/audit indexes from Phase 54 (migration 0040) are assumed sufficient at
  single-gym volume. A revenue composite `(received_at, method, subject_kind)` was
  explicitly **deferred from Phase 54 (D-54-10) to Phase 55 query-plan evidence** — add it
  via a new Alembic migration ONLY if `EXPLAIN ANALYZE` on a realistic fixture shows a seq
  scan that hurts. Otherwise no schema change this phase.
  - ⚠ **Researcher confirm:** run `EXPLAIN` on the revenue aggregate against seeded data;
    decide add-vs-skip with evidence, not speculation.

### Claude's Discretion
- Exact DTO field names within the camelCase convention; whether `averagePerDay` is a float
  or 2-dp; whether to expose `refundKopecks` per revenue bucket.
- Internal `service.py` ↔ `repository.py` split of the pivot logic.
- Test fixture amounts / dates for the correctness suite (Phase 57 owns the DST-boundary
  golden-path; Phase 55 should still test net-of-refund + MSK day bucketing).

</decisions>

<canonical_refs>
## Canonical References

**Downstream agents MUST read these before planning or implementing.**

### Requirements & roadmap
- `.planning/REQUIREMENTS.md` — REV-01..05 (lines 18–22), CLR-01..04 (26–29), VIS-R-01..04 (33–36)
- `.planning/ROADMAP.md` §"Phase 55" (lines 163–173) — goal + 5 success criteria
- `.planning/phases/54-foundations-module-scaffold-rbac-parity-indexes/54-CONTEXT.md` — **the locked architectural baseline** (raw-SQL discipline D-54-06/07/08, RBAC D-54-03/04, deferred revenue index D-54-10). Read this first.

### Reports module (scaffold to fill)
- `apps/backend/app/modules/reports/router.py` — scaffold documents the planned Phase 55 surface
- `apps/backend/app/modules/reports/repository.py` — raw-SQL reader pattern + cross-module read discipline (D-54-08)
- `apps/backend/app/modules/reports/service.py` — read-only aggregator invariants (no commit, no ORM cross-import)
- `apps/backend/app/modules/reports/schemas.py` / `constants.py` / `permissions.py` — scaffold notes for the DTOs / grain constants / RBAC chokepoint

### Source tables (read via raw `text()` SELECT — never ORM-import)
- `apps/backend/app/modules/payments/models.py` §44–120 — `payments`: `subject_kind` ∈ (`membership`,`pt_package`,`refund`), signed `amount_kopecks` (CHECK), `method` ∈ (`cash`,`online`), `received_at` (sole temporal col), `ix_payments_received_at DESC`
- `apps/backend/app/modules/memberships/models.py` §107–185 — `memberships`: `status` ∈ (`active`,`expired`,`cancelled`,`frozen`), inclusive `end_date`, NO soft-delete (status-based), `ix_memberships_client_id_status_end_date`
- `apps/backend/app/modules/clients/models.py` — `clients`: `created_at`, `deleted_at` (soft-delete; CLR-04 excludes `deleted_at IS NOT NULL`)
- `apps/backend/app/modules/visits/models.py` §43–111 — `visits`: `gym_date` STORED GENERATED `(checked_in_at AT TIME ZONE 'Europe/Moscow')::date`, `checked_in_at` timestamptz

### Shared API patterns
- `apps/backend/app/core/schemas.py` §36/60/79 — `BackendSchemaBase`, `ResponseEnvelope[T]`, `envelope()`
- `apps/backend/app/core/pagination.py` §20/32 — `PageQuery` / `PaginatedData[T]` (NOT used by reports — reference only)
- `apps/backend/app/api/v1/router.py` §41–93 — `v1.include_router(..., prefix=..., tags=...)` mount site; add the reports mount here
- `apps/backend/app/core/permissions.py` — `require_permission` / `OWNER_ONLY`; `(VIEW, REPORTS)` already present
- `apps/backend/app/modules/online_payments/service.py` §116–142 — raw-SQL cross-module reader exemplar (D-49-03 precedent)

</canonical_refs>

<code_context>
## Existing Code Insights

### Reusable Assets
- **Reports scaffold** (`app/modules/reports/`) — slim module already created and wired by
  Phase 54; Phase 55 only fills router/service/repository/schemas/constants bodies.
- **`envelope()` + `ResponseEnvelope[T]`** (`core/schemas.py`) — standard response wrapper.
- **Raw-SQL reader pattern** (`online_payments/service.py:116-142`) — copy the `text()` +
  bind-params + `.mappings()` shape; document verified columns + source file:line per reader.
- **`require_permission(Action.VIEW, Resource.REPORTS)`** — owner-only chokepoint, already
  in `OWNER_ONLY`; no new RBAC work this phase.

### Established Patterns
- **Europe/Moscow bucketing** — `visits.gym_date` is already STORED MSK (filter directly);
  for `payments.received_at` and visits hour-of-day, convert in SQL via
  `AT TIME ZONE 'Europe/Moscow'` (mirror the STORED-column discipline, no app-layer TZ math).
- **Integer kopecks end-to-end** — aggregates return raw signed kopecks; formatting is a
  frontend (v2.0) concern. `SUM(amount_kopecks)` stays integer.
- **camelCase wire / snake_case Python** — via `BackendSchemaBase` (`extra='forbid'`).

### Integration Points
- `app/api/v1/router.py` ← add `reports_router` mount at `prefix="/reports"`.
- `payments` / `memberships` / `clients` / `visits` tables ← raw `text()` SELECT reads only.
- Possible new Alembic migration ONLY if EXPLAIN justifies a revenue composite index (D-13).

</code_context>

<specifics>
## Specific Ideas

- Net revenue must reconcile against the v1.4 ledger: a full refund of a membership sale
  in the same period must net to zero (`sale + refund = 0`) — this is the canonical
  correctness assertion for the REV-04 test.
- `within=7` default and `1..30` range are a deliberate parity choice with the v1.3
  expiring-soon membership selector — keep the param name and bounds identical.

</specifics>

<deferred>
## Deferred Ideas

- **Per-bucket `refundKopecks` transparency field** — flagged in D-01 as a possible
  owner-friendly addition; default is net-only. Promote in Phase 55 if cheap, else v2.0.
- **Zero-filled bucket gaps** (`generate_series` day/month/hour fill) — presentation
  concern, v2.0 frontend.
- **Revenue composite index** `(received_at, method, subject_kind)` — add only on EXPLAIN
  evidence (D-13); otherwise carries to whenever volume justifies it.
- **CSV export of these three reports** — Phase 56 (EXP-01..04).
- **Top-trainers + PT-usage report** — out of v1.8 entirely (owner decision); v1.9/v2.0.

None of the above are scope creep into Phase 55.

</deferred>

---

*Phase: 55-revenue-clients-visits-reports*
*Context gathered: 2026-05-24*

# Phase 60: Trainer-Usage Report - Context

**Gathered:** 2026-05-25
**Status:** Ready for planning
**Mode:** `--auto` (decisions auto-selected to recommended defaults grounded in REQUIREMENTS RPT-01..04, STATE.md `D-REPORT-READONLY` + `D-58-21`, and v1.9 research; review before planning)

<domain>
## Phase Boundary

The **trainer-usage report** — the final business-feature phase of v1.9. Four
requirements (RPT-01..04) extend the EXISTING `app/modules/reports/` module
(Phase 55 REV / Phase 56 AUD established the v1.8 read-only discipline
D-54-07/D-54-08). NO new module, NO new `.importlinter` entry, ZERO new
`ignore_imports` edges (RPT-04 acceptance criterion).

The phase adds:

1. **`GET /api/v1/reports/trainers` (RPT-01..02, RPT-04)** — owner-only
   read-only aggregate over `pt_sessions` + `trainer_availability_slots` +
   `payments` + `pt_packages` + `trainer_payroll_accruals`. Returns per-trainer
   rows ordered by `session_count DESC` (REQUIREMENTS RPT-01 verbatim),
   with secondary order on `trainer_name_snapshot ASC` for deterministic
   tie-breaking. Each row carries:
   - **Load (RPT-01):** `session_count` (non-cancelled `pt_sessions` in
     period), `cancelled_session_count` (cancelled `pt_sessions` in period),
     `total_hours` (sum of conducted session durations via
     `trainer_availability_slots.end_time - start_time` for the joined
     booking, or fallback derived from session timestamps when there is no
     booking — see D-60-04), `unique_client_count`
     (`COUNT(DISTINCT pt_packages.client_id)` across non-cancelled
     sessions), `utilization_pct` (booked-hours / available-hours, **NULL
     when 0 published `active` slots in the period** — REQUIREMENTS RPT-01
     verbatim).
   - **Revenue (RPT-02):** `revenue_kopecks` (sum of positive
     `payments.amount_kopecks` for `subject_kind='pt_package'` for packages
     the trainer was **assigned at sale** to, per D-58-21), plus
     `avg_revenue_per_session` (`revenue_kopecks // NULLIF(session_count,0)`,
     NULL when no non-cancelled sessions). The response envelope carries an
     explicit `revenue_attribution_note` string documenting the known
     multi-trainer-package double-count limitation (REQUIREMENTS RPT-02
     verbatim; planner finalizes wording).
   - **Payroll (RPT-04):** `total_accrued_kopecks` (sum of
     `trainer_payroll_accruals.accrual_kopecks` — **signed** to allow
     clawbacks to net out per D-58-03), `total_paid_kopecks` (same sum
     restricted to `status='paid'`). Period match is by accrual
     `period_start`/`period_end` overlap with the report's `from`/`to`
     window — see D-60-05.

2. **`GET /api/v1/reports/trainers.csv` (RPT-03)** — owner-only CSV export of
   the same payload via the existing `csv_export.py` helper (UTF-8 BOM,
   RFC-4180 excel dialect, `Content-Disposition: attachment` —
   `sanitize_csv_text` MUST be applied to all free-text columns
   (`trainer_name_snapshot`); kopeck money formatted as
   `'%.2f'` rubles per D-13). Same query params, same RBAC, same
   `response_class=StreamingResponse` pattern as the v1.8
   `/reports/revenue.csv` (router.py:143) and Phase 56 audit-log CSV.

3. **Period query schema** — reuses the v1.8 `from_date`/`to_date` (inclusive
   MSK dates) `RevenueReportQuery` pattern; defaults rejected at the
   schema layer if unspecified (Pydantic v2 validator). Planner finalizes
   exact field names; recommended: `from_date`/`to_date` to mirror
   `/reports/revenue`.

**In scope (RPT-01..04):**
- ZERO new Alembic migrations (head is `0042` post-Phase 59; v1.9 schema is
  already complete — all data exists in `pt_sessions`,
  `trainer_availability_slots`, `payments`, `pt_packages`, `trainers`,
  `trainer_payroll_accruals`).
- New raw-SQL reader `fetch_trainer_usage(session, from_date, to_date)` in
  `apps/backend/app/modules/reports/repository.py` (single CTE-or-LEFT-JOIN
  query, `text()` only, no ORM imports).
- New row-shape Pydantic models in
  `apps/backend/app/modules/reports/schemas.py`
  (`TrainerUsageRow` + `TrainerUsageReportResponse` envelope with
  `revenue_attribution_note: str` field).
- New service function `get_trainer_usage_report` in
  `apps/backend/app/modules/reports/service.py` (thin orchestration: param
  validation → `fetch_trainer_usage` → assemble response with the
  attribution note string from a module constant).
- New router endpoints in `apps/backend/app/modules/reports/router.py`
  (`GET /trainers` JSON + `GET /trainers.csv`), both owner-only via
  `require_can(Action.VIEW, Resource.REPORTS)` (existing OWNER_ONLY pair
  — permissions.py:65 — NO new RBAC entries).
- New CSV row builder in `apps/backend/app/modules/reports/csv_export.py`
  (header + per-trainer row formatter; reuses BOM/dialect/streaming
  helpers; sanitizes `trainer_name_snapshot` via
  `sanitize_csv_text`).
- Integration tests in `apps/backend/tests/integration/` (reports dir
  alongside revenue/audit tests):
  - Owner happy path: 3 trainers seeded with mixed sessions + accruals
    + payments + slots → expected ordered payload.
  - **PITFALL 11 golden:** session conducted by a deactivated trainer
    (`trainers.is_active=False`) appears in the report.
  - **PITFALL 12 golden:** session on `to_date` is INCLUDED;
    session on `to_date + 1 day` is EXCLUDED (mirrors VER-02 / Phase 57).
  - **PITFALL 6 attribution golden:** `revenue_kopecks` for a trainer
    counts ONLY packages where they are `pt_packages.trainer_id` (not
    packages they conducted sessions for but did not sell).
  - **`utilization_pct` golden:** trainer with 0 active slots in period →
    `utilization_pct = null`; trainer with slots but 0 bookings →
    `utilization_pct = 0.0`.
  - **RPT-04 clawback netting:** a positive accrual + a negative clawback
    for the same trainer in the period → `total_accrued_kopecks` reflects
    the net (signed sum, D-58-03).
  - Reception 403 on both endpoints (route-introspection guard).
  - CSV golden: BOM byte sequence (`\xef\xbb\xbf`), CRLF terminators,
    Cyrillic trainer name renders correctly when re-decoded as UTF-8,
    formula-injection-prefixed `trainer_name_snapshot` value (e.g.,
    `=cmd|…`) is rendered as literal text.
- `apps/backend/openapi.json` regen is **deferred to Phase 61 (HND-01)** —
  Phase 60 just adds the endpoints; the byte-stable contract artifact and
  `schema.d.ts` regen happen in the handoff phase.

**Out of scope (later phases / explicit anti-features):**
- OpenAPI byte-stable regen + `schema.d.ts` + `_v19Checks` forward-guards
  (HND-01 → Phase 61).
- Three-way RBAC parity edit (none needed — reuses existing
  `(VIEW, REPORTS)` OWNER_ONLY pair; admin-web stays frozen — see D-60-08).
- `apps/admin-web` UI for the trainer report (admin-web frozen in v1.9;
  v1.10+ owns the FE integration — research's "report frontend integration"
  defer).
- Per-session commission proration across period boundaries (research
  anti-feature; v1.10+).
- 1C / external payroll export, iCal sync, real-time dashboards, predictive
  analytics, per-client breakdown in the trainer report (research
  anti-features).
- Multi-trainer-package revenue de-duplication / proration — RPT-02
  ACCEPTS the known double-count limitation as a documented response-body
  note; fixing it is a v2.0 concern.
- Pagination — the trainer list is small-N (single gym, ≤ a few dozen
  trainers); response returns ALL trainers in one payload. No
  `{items, total, page, pageSize}` envelope. See D-60-09.
- Caching / materialized view — report is computed live per request,
  matching the v1.8 `/reports/revenue` discipline. Performance budget is
  the same single-query CTE/JOIN shape.

</domain>

<decisions>
## Implementation Decisions

> **REQUIREMENTS RPT-01..04 + STATE.md `D-REPORT-READONLY` + `D-58-21`
> (attribution model) are authoritative.** The v1.9 research's "Question 3
> trainer-usage report" sketch is correct on shape but predates the LOCKED
> attribution rule (D-58-21) and RPT-04 payroll fold-in. **The locked
> decisions win.** Where research and locked decisions agree, follow
> research's exact SQL pattern (raw-SQL `text()`, `LEFT JOIN` over `trainers`,
> `pt_sessions.trainer_name_snapshot` for display).

### Module placement & discipline (D-60-01..02)
- **D-60-01:** Trainer-usage report lives in the EXISTING
  `app/modules/reports/` module — D-54-07/D-54-08 / D-REPORT-READONLY
  applies verbatim. NO `models.py` is created in this module, ZERO new
  `ignore_imports` edges, ZERO new `.importlinter` entries, ZERO writes to
  any business table. The phase's CI green-lights MUST include
  `lint-imports` and a `git diff --exit-code` on `.importlinter` to prove
  the discipline holds (RPT-04 acceptance criterion).
- **D-60-02:** ALL cross-module reads use `sqlalchemy.text()` over table
  names — never `from app.modules.pt_sessions.models import …`,
  never `from app.modules.payroll.models import …`. Tables referenced
  directly by raw SQL: `trainers`, `pt_sessions`,
  `trainer_availability_slots`, `pt_packages`, `payments`,
  `trainer_payroll_accruals`, `bookings` (read-only). This mirrors the
  v1.8 `fetch_revenue_buckets` / `fetch_audit_log_page` discipline already
  in `reports/repository.py` (lines 56, 293).

### Single-query CTE shape (D-60-03)
- **D-60-03:** The report is ONE SQL statement (CTE-driven `LEFT JOIN`
  pyramid), not N+1 per trainer. Recommended shape (planner finalizes
  exact CTEs; column names are LOCKED by the schema below):
  ```sql
  WITH session_agg AS (
      -- attribution: conducting trainer (D-58-21)
      SELECT
          ps.trainer_id,
          COUNT(*) FILTER (WHERE ps.cancelled_at IS NULL) AS session_count,
          COUNT(*) FILTER (WHERE ps.cancelled_at IS NOT NULL)
              AS cancelled_session_count,
          COUNT(DISTINCT pkg.client_id) FILTER (WHERE ps.cancelled_at IS NULL)
              AS unique_client_count,
          COALESCE(SUM(
              EXTRACT(EPOCH FROM (s.end_time - s.start_time)) / 3600.0
          ) FILTER (WHERE ps.cancelled_at IS NULL), 0.0) AS total_hours
      FROM pt_sessions ps
      LEFT JOIN pt_packages pkg ON pkg.id = ps.pt_package_id
      LEFT JOIN bookings b      ON b.id = ps.booking_id
      LEFT JOIN trainer_availability_slots s ON s.id = b.slot_id
      WHERE (ps.performed_at AT TIME ZONE 'Europe/Moscow')::date
            BETWEEN :from_date AND :to_date
      GROUP BY ps.trainer_id
  ),
  slot_agg AS (
      SELECT
          trainer_id,
          COALESCE(SUM(
              EXTRACT(EPOCH FROM (end_time - start_time)) / 3600.0
          ), 0.0) AS published_hours,
          COALESCE(SUM(
              EXTRACT(EPOCH FROM (end_time - start_time)) / 3600.0
          ) FILTER (WHERE status = 'booked'), 0.0) AS booked_hours,
          COUNT(*) FILTER (WHERE status IN ('active', 'booked')) AS published_slot_count
      FROM trainer_availability_slots
      WHERE (start_time AT TIME ZONE 'Europe/Moscow')::date
            BETWEEN :from_date AND :to_date
      GROUP BY trainer_id
  ),
  revenue_agg AS (
      -- attribution: assigned-at-sale (D-58-21)
      SELECT
          pkg.trainer_id,
          COALESCE(SUM(p.amount_kopecks) FILTER (
              WHERE p.subject_kind = 'pt_package' AND p.amount_kopecks > 0
          ), 0) AS revenue_kopecks
      FROM pt_packages pkg
      JOIN payments p ON p.subject_id = pkg.id
                     AND p.subject_kind = 'pt_package'
      WHERE pkg.trainer_id IS NOT NULL
        AND (p.paid_at AT TIME ZONE 'Europe/Moscow')::date
            BETWEEN :from_date AND :to_date
      GROUP BY pkg.trainer_id
  ),
  payroll_agg AS (
      SELECT
          trainer_id,
          COALESCE(SUM(accrual_kopecks), 0) AS total_accrued_kopecks,
          COALESCE(SUM(accrual_kopecks) FILTER (WHERE status = 'paid'), 0)
              AS total_paid_kopecks
      FROM trainer_payroll_accruals
      WHERE period_start <= :to_date AND period_end >= :from_date
      GROUP BY trainer_id
  )
  SELECT
      t.id AS trainer_id,
      t.full_name AS trainer_name,
      COALESCE(sa.session_count, 0)              AS session_count,
      COALESCE(sa.cancelled_session_count, 0)    AS cancelled_session_count,
      COALESCE(sa.total_hours, 0.0)              AS total_hours,
      COALESCE(sa.unique_client_count, 0)        AS unique_client_count,
      CASE
          WHEN COALESCE(sla.published_slot_count, 0) = 0 THEN NULL
          ELSE (COALESCE(sla.booked_hours, 0.0)
                / NULLIF(sla.published_hours, 0.0)) * 100.0
      END                                        AS utilization_pct,
      COALESCE(ra.revenue_kopecks, 0)            AS revenue_kopecks,
      CASE WHEN COALESCE(sa.session_count, 0) = 0 THEN NULL
           ELSE COALESCE(ra.revenue_kopecks, 0) / sa.session_count
      END                                        AS avg_revenue_per_session,
      COALESCE(pa.total_accrued_kopecks, 0)      AS total_accrued_kopecks,
      COALESCE(pa.total_paid_kopecks, 0)         AS total_paid_kopecks
  FROM trainers t
  LEFT JOIN session_agg sa  ON sa.trainer_id  = t.id
  LEFT JOIN slot_agg sla    ON sla.trainer_id = t.id
  LEFT JOIN revenue_agg ra  ON ra.trainer_id  = t.id
  LEFT JOIN payroll_agg pa  ON pa.trainer_id  = t.id
  -- PITFALL 11: NO is_active filter — include deactivated trainers
  ORDER BY session_count DESC, t.full_name ASC;
  ```
  The exact CTE names, column casts (`numeric` vs `float8` for hours), and
  whether to push `LEFT JOIN trainers` through a top-level CTE are Claude's
  discretion. The SHAPE — single statement, attribution comments, period
  filter via `AT TIME ZONE 'Europe/Moscow'`, NO `is_active` filter, signed
  accrual sum, `NULLIF` guards on division — is LOCKED.

### total_hours derivation (D-60-04)
- **D-60-04:** `total_hours` is computed from the **booked slot's
  `(end_time - start_time)` window** via the
  `pt_sessions → bookings → trainer_availability_slots` chain (D-38-04
  enforces this 1:1 link). When a session has no booking (legacy
  walk-in sessions inserted directly via PT-package usage), the row
  contributes `0.0` hours to `total_hours` — these sessions still count
  toward `session_count`, but they have no canonical duration. This
  matches the research's `EXTRACT(EPOCH FROM (s.end_time - s.start_time))`
  pattern and avoids fabricating a synthetic hour from a single
  `performed_at` timestamp. Document this in the
  `revenue_attribution_note` companion field
  `methodology_note` (or fold into a single `notes: list[str]` field at
  planner's discretion).

### Payroll period match (D-60-05)
- **D-60-05:** RPT-04 `total_accrued_kopecks` / `total_paid_kopecks`
  match accruals whose period **overlaps** the report window:
  `period_start <= :to_date AND period_end >= :from_date`. This
  includes:
  - accruals whose period is fully inside the window;
  - accruals whose period straddles either boundary;
  - clawback rows (negative `accrual_kopecks`) — signed `SUM` nets them
    out automatically (D-58-03 append-only ledger preserved).
  The sum is over the FULL accrual amount, NOT a prorated fraction —
  proration across period boundaries is an explicit anti-feature for
  v1.9 (PITFALLS research: "per-session commission proration across
  period boundaries → v1.10+"). Document this in the response notes.

### Utilization_pct formula (D-60-06)
- **D-60-06:** `utilization_pct = (booked_hours / published_hours) * 100`,
  where:
  - `booked_hours` = sum of `(end_time - start_time)` for
    `trainer_availability_slots` with `status='booked'` whose
    `start_time` (MSK-date) falls in the report period;
  - `published_hours` = sum of `(end_time - start_time)` for slots with
    `status IN ('active','booked')` whose `start_time` (MSK-date) falls
    in the report period (i.e., available capacity that was either taken
    or still on offer, EXCLUDING `cancelled` slots which represent
    withdrawn capacity);
  - Result is `NULL` when no `active|booked` slots exist for the trainer
    in the period (REQUIREMENTS RPT-01 verbatim: "NULL при 0 слотов");
  - Result is `0.0` when slots exist but none are `booked`.
  Cancelled slots (`status='cancelled'`) are excluded from BOTH numerator
  and denominator — they represent withdrawn capacity, not utilization
  attempts. Round to 2 decimal places at the wire layer (Pydantic
  serializer or `ROUND(...,2)` in SQL — planner picks). Decimal arithmetic
  preferred over float; if float is used, document the precision in the
  notes field.

### Revenue attribution + double-count disclosure (D-60-07)
- **D-60-07:** RPT-02 revenue follows **D-58-21 (assigned-at-sale)** —
  `pt_packages.trainer_id` is the attribution key. The known
  multi-trainer-package double-count (a package conducted by trainer B
  but assigned to trainer A reports revenue ONLY on A — the per-trainer
  rows are correct individually; the **total across all trainers may
  exceed total PT-package revenue** when packages have been transferred
  via assignment changes, OR when future v2.0 multi-trainer packages
  exist) is documented in the response envelope:
  ```python
  class TrainerUsageReportResponse(BaseModel):
      trainers: list[TrainerUsageRow]
      from_date: date
      to_date: date
      revenue_attribution_note: str = (
          "Revenue is attributed to pt_packages.trainer_id (assigned at "
          "sale). Packages currently have a single assigned trainer, so "
          "per-trainer revenue is unambiguous; if a package is reassigned "
          "during its lifecycle, revenue accrues to the trainer assigned "
          "at sale time. Summing revenue across trainers may not equal "
          "the global PT-package revenue total."
      )
  ```
  The note string lives in `apps/backend/app/modules/reports/constants.py`
  as a module-level constant `TRAINER_REPORT_REVENUE_NOTE` (or similar);
  the exact wording is Claude's discretion within the bounds of the
  REQUIREMENTS RPT-02 mandate ("known limitation: пакет с >1 тренером
  даёт revenue double-count на total-уровне"). The wording above
  matches the v1.4 single-trainer-per-package data model; if the planner
  encounters a different reality at codification time, the wording
  adjusts accordingly.

### RBAC (D-60-08)
- **D-60-08:** BOTH endpoints (`/reports/trainers` JSON +
  `/reports/trainers.csv`) gate on the EXISTING
  `(Action.VIEW, Resource.REPORTS)` OWNER_ONLY pair
  (permissions.py:65 — pre-existing). **NO new `Resource`, NO new
  OWNER_ONLY pair, NO `can.ts`/`registry.ts` edits.** Three-way RBAC
  parity test (admin-web ↔ backend) is unchanged for this phase
  (admin-web stays frozen — D-59-08 precedent). The route-introspection
  guard (Phase 56 OWNER_ONLY-route automation) auto-discovers both new
  endpoints and verifies reception → 403 with no per-endpoint test
  duplication.

### Pagination (D-60-09)
- **D-60-09:** The report returns ALL trainers in a single response —
  NO `{items, total, page, pageSize}` envelope, NO `page`/`pageSize`
  query params. Rationale: single-gym domain has O(10) trainers;
  paginating a 10-row report is over-engineering and would complicate
  the CSV export (CSV is a single-shot stream of the full dataset, not
  a paged export). The response envelope is the
  `TrainerUsageReportResponse` shape in D-60-07. The CSV mirrors the
  same dataset 1:1. If trainer count grows past ~100 in a future
  milestone, pagination is added in a follow-up phase. (Matches
  `fetch_revenue_buckets` precedent — single-shot, non-paginated.)

### Audit (D-60-10)
- **D-60-10:** NO new `LOCKED_AUDIT_EVENTS`. The report endpoints are
  read-only owner-only GETs — they are observable through the existing
  request-level structlog access log (the standard "owner viewed report"
  audit is the access log, not a domain audit event). The Phase 56
  AUD-01..06 audit-log endpoints are the read surface for security
  audits; trainer-report viewing does NOT need a new domain audit event
  (matches `/reports/revenue` precedent — no `revenue_report_viewed`
  event exists; the access log is sufficient). The CSV export endpoint
  similarly does NOT emit a domain audit event — its export is
  observable through HTTP access logs and the StreamingResponse content
  length. This keeps `LOCKED_AUDIT_EVENTS` cardinality flat for Phase 60
  (delta = 0).

### CSV export (D-60-11)
- **D-60-11:** Reuse `apps/backend/app/modules/reports/csv_export.py`
  helpers verbatim:
  - `BOM` constant (U+FEFF, never a literal glyph in source — D-11);
  - stdlib `csv.writer` with `QUOTE_MINIMAL`, comma delimiter, `\r\n`
    terminator (RFC-4180);
  - `StreamingResponse(media_type='text/csv; charset=utf-8',
    headers={'Content-Disposition': 'attachment; filename=trainer-usage-{from}-{to}.csv'})`;
  - kopeck money → rubles formatted as `'%.2f'` with period decimal,
    NO thousand separators (D-13);
  - `sanitize_csv_text` applied to `trainer_name_snapshot` (the only
    free-text column; threat T-56-07 / CR-01); machine-formatted numeric
    columns (`%.2f` rubles, integer counts, `utilization_pct` numeric)
    are NOT sanitized (a leading `-` on a refund-driven negative
    `total_accrued_kopecks` is a legitimate signed number, not a
    formula trigger);
  - Header row (Russian column titles for owner consumption — matches
    v1.8 revenue.csv convention; planner picks exact wording within
    project i18n style): e.g.
    `Тренер, Сессий, Отменено, Часов, Уникальных клиентов, Утилизация %, Выручка ₽, Средний чек ₽, Начислено ₽, Выплачено ₽`.
    The exact header strings are Claude's discretion; the COLUMN ORDER
    mirrors the JSON row field order for diffability.
  - `utilization_pct = NULL` → empty CSV cell (NOT `"None"`,
    NOT `"NULL"` — matches CSV-RFC null convention).
  - Filename query-string component normalization
    (`from_date.isoformat()`) is the planner's call; recommended
    `trainer-usage-{from_date}-{to_date}.csv` (matches
    `revenue-{from}-{to}.csv` pattern from Phase 56 EXP-01).

### Endpoint registration (D-60-12)
- **D-60-12:** Both endpoints mount under the EXISTING `router` (NOT
  `audit_log_router`) in `apps/backend/app/modules/reports/router.py`
  — same `APIRouter` instance that owns `/revenue`,
  `/active-memberships`, etc. (router.py:55). The router is mounted
  under `/api/v1/reports/` in `apps/backend/app/api/v1/router.py`
  (verified existing). No new router instance is needed. Endpoint
  decorators follow the existing `@router.get("/revenue", ...)` +
  `Depends(require_owner_action(...))` shape; the CSV endpoint sets
  `response_class=StreamingResponse` exactly like
  `/revenue.csv` (router.py:143). Both endpoints declare full
  OpenAPI metadata (`summary`, `description`, `tags=["reports"]`,
  `responses`) so the Phase 61 `openapi.json` regen captures them
  byte-stably.

### Test discipline (D-60-13)
- **D-60-13:** Tests follow the existing reports-integration test
  shape (`apps/backend/tests/integration/reports/test_revenue.py`
  pattern — verify path by grep at plan time). The PITFALL goldens
  listed in `<domain>` are MANDATORY per-pitfall acceptance gates:
  - PITFALL 10 → import-linter CI green + grep guard
    `! grep -rE "from app.modules.(pt_sessions|trainers|payments|payroll|schedule|bookings|pt_packages).models" apps/backend/app/modules/reports/` (test or pre-commit guard).
  - PITFALL 11 → soft-deleted-trainer historical inclusion test.
  - PITFALL 12 → period-boundary inclusivity test (mirrors VER-02 from
    Phase 57).
  - PITFALL 6 → attribution test (revenue follows assigned-at-sale,
    not conducting).
  No new fixtures need to land in `tests/conftest.py` beyond what
  Phase 58/59 already provide — `authed_client_owner`,
  `authed_client_reception`, SAVEPOINT isolation, factory builders for
  `pt_sessions`, `pt_packages`, `payments`, `trainer_availability_slots`,
  and `trainer_payroll_accruals` are all in place.

### Claude's Discretion
- Exact CTE names + column casts in the SQL (`numeric(10,2)` vs
  `float8` for hours; `ROUND(..., 2)` placement for `utilization_pct`).
- Whether `methodology_note`, `revenue_attribution_note`, and any
  RPT-04 period-overlap note collapse into a single
  `notes: list[str]` field on the envelope, or stay as separate
  string fields. Recommended: separate named fields for OpenAPI
  clarity; planner picks.
- Exact CSV header strings (Russian; project i18n style — match
  `revenue.csv` cadence).
- Exact query-string param names (`from_date`/`to_date` vs `from`/`to`).
  Recommended: `from_date`/`to_date` to mirror the v1.8 endpoints and
  avoid Python `from` keyword collision.
- Whether to emit an explicit `OPTIONS` preflight handler — NO; FastAPI
  handles automatically and the v1.8 endpoints don't.
- Whether the CSV endpoint accepts an additional `dialect=excel-ru`
  param — NO; the dialect is locked by `csv_export.py` and the column
  separator is comma (matches existing exports).
- Naming the constant for `TRAINER_REPORT_REVENUE_NOTE` and where it
  lives (`reports/constants.py` recommended).
- Test file granularity: ONE `test_trainer_usage.py` per endpoint or
  ONE combined file. Recommended: one combined file matching
  `test_revenue.py` precedent.

</decisions>

<canonical_refs>
## Canonical References

**Downstream agents MUST read these before planning or implementing.**

### Requirements & roadmap (source of truth on scope — these WIN over research)
- `.planning/REQUIREMENTS.md` §"RPT-01..04" — verbatim contract:
  per-trainer rows ordered `session_count DESC`; `utilization_pct` NULL
  when 0 slots; reception 403; revenue attribution (with known
  multi-trainer double-count); CSV UTF-8 BOM RFC-4180; RPT-04 folds
  `total_accrued_kopecks` / `total_paid_kopecks` from
  `trainer_payroll_accruals`.
- `.planning/ROADMAP.md` §"Phase 60: Trainer-Usage Report" — goal
  + success criteria 1..4; reception → 403 mandate; CSV BOM + Excel
  dialect; report module makes ZERO new import-linter ignores
  (RPT-04 acceptance criterion).
- `.planning/STATE.md` §"D-REPORT-READONLY" — locked
  raw-SQL/no-models.py/zero-writes/zero-new-ignores discipline for
  the trainer report.
- `.planning/STATE.md` §"D-58-21" (via Phase 58 CONTEXT) — LOCKED
  attribution model: pct-of-revenue → `pt_packages.trainer_id`
  (assigned-at-sale); fixed-per-session → `pt_sessions.trainer_id`
  (conducting). RPT-02 revenue follows the assigned-at-sale leg.
- `.planning/PROJECT.md` — v1.9 milestone goal (Trainers Complete;
  admin-web frozen; reports module EXTENDED not replaced).

### v1.9 research (locked for SQL shape / pitfall coverage; supersedes
### itself where REQUIREMENTS / STATE LOCKED decisions diverge)
- `.planning/research/ARCHITECTURE.md` §"Question 3: Trainer Report"
  (around L?) — module placement (extend reports), `fetch_trainer_usage`
  raw-SQL shape (LEFT JOIN over `trainers`, `text()` only),
  response envelope sketch, RBAC reuse of `(VIEW, REPORTS)`. The
  ARCHITECTURE doc's `TrainerUsageItem` fields are
  CLOSE-BUT-NOT-FINAL — REQUIREMENTS RPT-01..04 + D-60 decisions add
  `cancelled_session_count`, `utilization_pct`, `avg_revenue_per_session`,
  `total_accrued_kopecks`, `total_paid_kopecks`, and the
  `revenue_attribution_note` envelope field. Follow the LOCKED schema.
- `.planning/research/PITFALLS.md` §"Pitfall 6" — revenue attribution
  ambiguity (LOCKED in D-58-21 / D-60-07).
- `.planning/research/PITFALLS.md` §"Pitfall 10" — report read-only
  discipline / zero new import-linter ignores (LOCKED in D-60-01/02).
- `.planning/research/PITFALLS.md` §"Pitfall 11" — soft-deleted
  trainers MUST appear in historical aggregates (LOCKED in D-60-03,
  test in D-60-13).
- `.planning/research/PITFALLS.md` §"Pitfall 12" — period-boundary
  inclusivity (LOCKED in D-60-03, test in D-60-13).
- `.planning/research/SUMMARY.md` §"Phase 62 — Trainer-Usage Report"
  (research's pre-collapse numbering; the actual ROADMAP folds it
  into Phase 60) — pitfall list 10/11/12 + revenue attribution +
  payroll fold-in summary. Follow the ROADMAP numbering, not the
  research's.
- `.planning/research/STACK.md` — confirms zero new deps (no
  `pandas`/`numpy`/external decimal lib needed).

### Backend code under direct edit / extension (READ before planning)
- `apps/backend/app/modules/reports/repository.py` — `fetch_revenue_buckets`
  (L56) + `fetch_audit_log_page` (L293) are the EXACT templates for
  `fetch_trainer_usage`: raw `sa.text()` query, MSK timezone
  via `AT TIME ZONE 'Europe/Moscow'`, `.mappings().all()`, inclusive
  date semantics. New `fetch_trainer_usage` lands here.
- `apps/backend/app/modules/reports/service.py` — read pattern:
  thin orchestrator that calls repository functions and assembles
  the response model. New `get_trainer_usage_report` lands here.
- `apps/backend/app/modules/reports/router.py` (L1-216 covers the
  `router` instance for `/revenue`/etc.; L216+ is the separate
  `audit_log_router`) — new `/trainers` JSON + `/trainers.csv`
  endpoints mount on `router` (NOT `audit_log_router`). `/revenue.csv`
  at L143 is the EXACT template for the CSV endpoint shape.
- `apps/backend/app/modules/reports/schemas.py` — new
  `TrainerUsageRow` + `TrainerUsageReportResponse` lands here. Mirror
  the existing `RevenueReportResponse` shape style.
- `apps/backend/app/modules/reports/csv_export.py` — BOM constant,
  `sanitize_csv_text`, `csv.writer` setup, `StreamingResponse`
  wrapper, `iter_csv_bytes` (or similar) — REUSE verbatim. New
  per-row formatter for trainer-usage rows lands here.
- `apps/backend/app/modules/reports/constants.py` — new
  `TRAINER_REPORT_REVENUE_NOTE` (and any other module-level note
  constants) land here.
- `apps/backend/app/modules/reports/permissions.py` (if it exists
  as a stub) — no edits expected; permission gates use
  `require_owner_action(Action.VIEW, Resource.REPORTS)` from
  `app/core/permissions.py`.
- `apps/backend/app/api/v1/router.py` — verify the
  `reports/router` is already mounted (it is, post-Phase 55); no
  new mount needed for the trainer endpoints.

### Backend code referenced read-only (do NOT edit, must understand)
- `apps/backend/app/modules/pt_sessions/models.py` — `trainer_id`,
  `pt_package_id`, `performed_at`, `cancelled_at`, `booking_id`,
  `trainer_name_snapshot` (NOT NULL, set at INSERT — B-05). The
  CTE reads these columns directly via raw SQL.
- `apps/backend/app/modules/pt_packages/models.py` — `trainer_id`
  (nullable, FK to trainers, `ON DELETE RESTRICT`), `client_id`.
  The revenue-attribution CTE filters `pkg.trainer_id IS NOT NULL`
  and uses `pkg.client_id` for `unique_client_count`.
- `apps/backend/app/modules/schedule/models.py` — `TrainerAvailabilitySlot`
  columns `status` (`active|booked|cancelled`), `start_time`,
  `end_time`, `trainer_id`. The slot-aggregation CTE reads these
  directly. Phase 59 ALTER (nullable `created_by_user_id`, UNIQUE
  `(trainer_id, start_time)`) is in place but does NOT affect this
  read query.
- `apps/backend/app/modules/payments/models.py` — `subject_id`,
  `subject_kind`, `amount_kopecks`, `paid_at`. RPT-02 revenue
  aggregates positive `amount_kopecks` filtered to
  `subject_kind='pt_package'` and joined to `pt_packages.id`.
- `apps/backend/app/modules/payroll/models.py` — `TrainerPayrollAccrual`
  columns `trainer_id`, `period_start`, `period_end`, `status`,
  `accrual_kopecks` (signed, D-58-03), `clawback_of_accrual_id`
  (nullable; clawback rows have negative `accrual_kopecks`). RPT-04
  CTE sums `accrual_kopecks` (signed) over the period-overlap window.
- `apps/backend/app/modules/bookings/models.py` — `slot_id`, `status`.
  Read for the `pt_sessions → bookings → trainer_availability_slots`
  chain when deriving `total_hours`. NOT edited.
- `apps/backend/app/core/permissions.py` §65
  (`(Action.VIEW, Resource.REPORTS)` in OWNER_ONLY frozenset) — the
  pre-existing pair gating both new endpoints. NO edits.
- `apps/backend/app/core/audit.py` — `LOCKED_AUDIT_EVENTS` frozenset.
  Phase 60 adds ZERO new entries (D-60-10).

### Test infrastructure
- `apps/backend/tests/conftest.py` — `authed_client_owner`,
  `authed_client_reception`, SAVEPOINT isolation, factory builders
  (pt_sessions, pt_packages, payments, trainer_availability_slots,
  trainer_payroll_accruals all already available from Phase 58/59).
- `apps/backend/tests/integration/reports/` (verify exact path
  at plan time; grep for `test_revenue.py`) — new
  `test_trainer_usage.py` mirrors the existing `test_revenue.py`
  shape: owner-happy-path + reception-403 + period-boundary golden
  + CSV golden.
- The Phase 56 route-introspection guard (verify path at plan time
  — likely `tests/integration/test_owner_only_routes_introspection.py`)
  auto-discovers new `/reports/trainers` + `/reports/trainers.csv`
  endpoints and verifies reception → 403 with no per-endpoint
  duplicate test.

</canonical_refs>

<code_context>
## Existing Code Insights

### Reusable Assets
- **`reports/csv_export.py` BOM + dialect + StreamingResponse
  helpers** — `sanitize_csv_text` (formula-injection guard),
  `BOM = "\ufeff"` constant (D-11: literal U+FEFF glyph in source
  is a defect — always written as the Python escape),
  `_MSK = timezone(timedelta(hours=3))`,
  kopeck `'%.2f'` formatter. Verbatim reuse — no new helper functions
  needed beyond a per-row builder.
- **`reports/repository.fetch_revenue_buckets` (L56)** — the precise
  template for `fetch_trainer_usage`: `text()` query, MSK
  timezone conversion via `AT TIME ZONE 'Europe/Moscow'`,
  `.mappings().all()` return shape.
- **`reports/repository.fetch_audit_log_page` (L293)** — second raw-SQL
  precedent showing CTE-style query layout, inclusive boundary
  parameters, and `.mappings()` consumption.
- **`reports/router.py /revenue.csv` (L143)** — template for the CSV
  endpoint: `response_class=StreamingResponse`,
  `Content-Disposition`, `require_owner_action(...)` dependency.
- **Existing `(VIEW, REPORTS)` OWNER_ONLY pair** — RBAC gating
  needs ZERO new permission tuples; admin-web stays frozen
  (D-59-08 precedent).
- **`pt_sessions.trainer_name_snapshot` (B-05)** — `NOT NULL`
  display name snapshotted at session creation; available for CSV
  output even when `trainers.deleted_at IS NOT NULL`.
- **`trainer_payroll_accruals` signed `accrual_kopecks` + clawback FK
  (D-58-03)** — RPT-04 signed `SUM` nets clawbacks automatically;
  no special-case clawback handling needed in the report SQL.
- **Phase 56 route-introspection guard** — auto-verifies reception 403
  on all new owner-only routes; no per-endpoint reception-403 test
  duplication needed.

### Established Patterns
- **D-54-07 / D-54-08 / D-REPORT-READONLY** — reports module has
  no `models.py`, uses only `text()` for cross-module reads,
  zero writes, zero new `ignore_imports`. Pitfall 10 prevention.
- **Inclusive `[from_date, to_date]` MSK date semantics** —
  established in v1.2 memberships, v1.8 reports
  (`fetch_revenue_buckets`); Pitfall 12 prevention via golden test.
- **`AT TIME ZONE 'Europe/Moscow'` in SQL for date-boundary
  conversion** — the project-standard timezone-safe truncation
  (avoids naive `timedelta` and `TIMESTAMP WITHOUT TIME ZONE`
  pitfalls, also covers DST edge cases — Phase 57 VER-02 precedent).
- **`LEFT JOIN trainers` with NO `is_active` filter on historical
  aggregates** — Pitfall 11 prevention; matches the v1.8 clients-report
  semantics ("new clients" filters `is_active`; historical
  aggregates do not).
- **CSV column ordering mirrors JSON field ordering** — diffability
  + cognitive load reduction; matches Phase 56 EXP-01..04
  discipline.
- **Reuse existing OWNER_ONLY pairs over inventing new ones** —
  D-59-08 precedent; keeps three-way RBAC parity test invariant.
- **Single-shot non-paginated reports** — `fetch_revenue_buckets`
  precedent; small-N aggregates do not paginate.
- **Read-only GET endpoints emit NO domain audit event** — the HTTP
  access log + AUD-01..06 audit-log endpoints cover the security
  surface; `/reports/revenue` precedent (no `revenue_report_viewed`
  event).

### Integration Points
- `apps/backend/app/api/v1/router.py` — already mounts
  `reports/router` under `/api/v1/reports/`; the two new endpoints
  ride this mount.
- `apps/backend/app/core/permissions.py` (READ ONLY) — the
  `(VIEW, REPORTS)` pair (L65) gates both endpoints.
- `apps/backend/app/modules/payroll/models.py` (READ via raw SQL
  ONLY — NO `from … import`) — RPT-04 reads
  `trainer_payroll_accruals` directly by table name.
- `apps/backend/openapi.json` — UNCHANGED in Phase 60; the
  byte-stable regen happens in Phase 61 (HND-01).
- `packages/api-client/src/schema.d.ts` — UNCHANGED in Phase 60;
  regen + forward-guards (`_v19Checks`) in Phase 61 (HND-01).

</code_context>

<specifics>
## Specific Ideas

- **Pitfall-coverage discipline (D-60-13) is non-negotiable.** The
  PITFALL 6 / 10 / 11 / 12 goldens are phase ACCEPTANCE gates, not
  nice-to-haves. Each golden has an explicit named test function with
  a top-of-file comment citing the pitfall number, mirroring the
  Phase 57 VER-02 / Phase 58 PITFALL-13 precedent.
- **The import-linter green-light is a SHIP gate, not a CI ergonomic.**
  RPT-04 explicitly mandates ZERO new `ignore_imports`. The plan MUST
  include a CI verification step `lint-imports && git diff --exit-code
  .importlinter` and a grep guard against `from app.modules.* import`
  inside `apps/backend/app/modules/reports/` (any module name).
- **CSV `utilization_pct = NULL` renders as an EMPTY cell**, NOT the
  string `"None"` or `"NULL"`. Confirmed by Excel/LibreOffice
  rendering; matches CSV-RFC convention. Golden test asserts the
  byte-level cell value is empty (delimiter-delimiter pair).
- **Filename for CSV download** mirrors `revenue-{from}-{to}.csv`
  pattern from Phase 56: `trainer-usage-{from}-{to}.csv`. The
  `{from}` / `{to}` substitutions are ISO dates
  (`from_date.isoformat()`). NO timestamp in filename — the URL
  query params capture the period, and the download is idempotent
  for the same query.
- **Order tie-breaker:** When two trainers have identical
  `session_count`, secondary order is `t.full_name ASC` for
  deterministic test stability. Tertiary order is `t.id ASC` if
  full_name collides (single-gym data is unlikely to collide on
  full_name, but the determinism contract is critical for golden
  tests).
- **Total-hours edge case:** `pt_sessions` without a `booking_id`
  (legacy walk-in sessions, possible per D-38-04 nullable FK) get
  `0.0` contribution to `total_hours` — they still count in
  `session_count` and `unique_client_count`. Document in
  `methodology_note`.
- **RPT-04 period overlap is ONE-DIRECTIONAL:** an accrual whose
  period straddles the window contributes its FULL signed amount
  (no proration). This is the documented v1.9 behavior; v1.10+ may
  add proration. Documented in `methodology_note` or a dedicated
  `payroll_period_match_note`.

</specifics>

<deferred>
## Deferred Ideas

- **Multi-trainer-package revenue de-duplication / proration** —
  RPT-02 explicitly accepts the double-count limitation as a
  documented response-body note for v1.9. v2.0 may add a
  proration model.
- **Per-session commission proration across period boundaries** —
  research anti-feature; v1.10+.
- **`apps/admin-web` UI for the trainer report** — admin-web frozen
  in v1.9; v1.10+ owns the FE integration (will consume the
  generated `schema.d.ts` post-Phase 61).
- **Caching / materialized view for the report** — computed live
  per request in v1.9, matching `/reports/revenue` discipline. If
  query plan degrades past ~50 trainers + 6-month windows,
  introduce a daily-refresh materialized view in a future phase.
- **Pagination on the trainer list** — single-gym domain is O(10);
  if trainer count grows past ~100, add a paginated variant in a
  follow-up phase.
- **Filename embeds an ISO timestamp suffix for download
  versioning** — explicitly NOT done; URL query params capture the
  period and the download is idempotent for the same params.
- **Trainer-report viewing emits a `report_viewed` audit event** —
  intentionally omitted (D-60-10); HTTP access log + AUD-01..06
  audit-log endpoints cover the security surface. A future
  observability milestone could introduce structured access-log
  domain events if needed.
- **1C / external payroll export, iCal sync, real-time dashboards,
  predictive analytics, per-client breakdown in the trainer
  report** — research anti-features; out of scope.

None of the above are scope creep into Phase 60.

</deferred>

---

*Phase: 60-trainer-usage-report*
*Context gathered: 2026-05-25*

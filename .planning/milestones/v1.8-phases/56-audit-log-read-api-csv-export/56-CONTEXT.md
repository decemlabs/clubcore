# Phase 56: Audit Log Read API + CSV Export - Context

**Gathered:** 2026-05-24
**Status:** Ready for planning
**Mode:** `--auto` (decisions auto-selected to recommended defaults; review before planning)

<domain>
## Phase Boundary

Two capabilities on top of the v1.8 reporting stack:

1. **Audit Log Read API** — a paginated, owner-only JSON endpoint
   (`GET /api/v1/audit-log`) that lets the owner browse and filter the full
   69-event audit log (`app.core.audit_models.AuditLog`), with deterministic
   `created_at DESC, id DESC` ordering for stable pagination.
2. **CSV Export** — UTF-8-BOM, RFC-4180 CSV downloads for all three Phase 55
   reports plus the audit log, streamed via `StreamingResponse`, Excel-friendly
   for Russian (РФ/СНГ) users.

**In scope (AUD-01..06, EXP-01..04):**
- `GET /api/v1/audit-log` → `ResponseEnvelope[PaginatedData[AuditLogItem]]`,
  owner-only, ordered `created_at DESC, id DESC`, all 69 event kinds visible.
- Combinable filters: actor (`actorUserId` exact, `actorEmailSnapshot` substring),
  `resource_type` exact, `action` exact (validated against `LOCKED_AUDIT_EVENTS`),
  time-window `from`/`to` (date, Europe/Moscow `created_at` bounds).
- `.csv` download endpoints: `/reports/revenue.csv`, `/reports/clients.csv`,
  `/reports/visits.csv`, `/audit-log.csv` — same query params as their JSON
  siblings, UTF-8 BOM + RFC-4180 escaping, money rendered as rubles, dates in
  Europe/Moscow.

**Out of scope (later phases / versions):**
- OpenAPI byte-stable regen + `AssertNonNever` forward-guards + operator runbook
  → **Phase 57** (HND/VER). Phase 56 ships endpoint bodies + correctness tests only.
- Frontend audit-log viewer / download buttons / dashboards → v2.0.
- Top-trainers + PT-usage report → out of v1.8 (owner decision, carried from Phase 55).
- Full-timestamp (sub-day) audit filters, server-side cursor export for large volume,
  Russian-Excel semicolon/comma-decimal CSV variant → deferred (see Deferred Ideas).

</domain>

<decisions>
## Implementation Decisions

> **Architectural baseline locked by Phase 54 + Phase 55** (`54-CONTEXT.md`,
> `55-CONTEXT.md`): read-only module discipline, raw-SQL cross-module reads for
> aggregates (zero new `ignore_imports`), camelCase wire / snake_case Python via
> `BackendSchemaBase` (`extra='forbid'`), no try/except in route handlers
> (AppError bubbles to the registered handler). These are NOT re-decided here.

### Endpoint home & routing
- **D-01:** Both the audit-log read API and all CSV endpoints live inside the
  **existing `app/modules/reports/` module** (already `.importlinter`-registered
  and read-only-wired by Phase 54/55). No new module → no import-linter contract
  churn, no new `ignore_imports`.
- **D-02:** **Mount paths follow the roadmap SC verbatim** (top-level, not nested):
  - Audit-log JSON + CSV via a second router `audit_log_router` mounted
    `v1.include_router(audit_log_router, prefix="/audit-log", tags=["audit-log"])`
    → routes `""` (list) and `.csv`.
  - Report CSV routes added to the existing `reports_router`: `/revenue.csv`,
    `/clients.csv`, `/visits.csv` (sit alongside the JSON `/revenue` etc.).
  - All mounts go in `app/api/v1/router.py` next to the existing `reports_router`
    mount (router.py:93).
- **D-03:** **RBAC chokepoint per resource:**
  - Audit-log list + CSV → `Depends(require_permission(Action.LIST, Resource.AUDIT_LOG))`
    (`(LIST, AUDIT_LOG)` is in `OWNER_ONLY`, permissions.py:129).
  - Report CSV → same `(VIEW, REPORTS)` as the JSON siblings (D-55-12).
  - Reception → 403; the existing route-introspection guard covers the new routes
    automatically (AUD-05, SC#1).

### Audit-log query mechanism & filters
- **D-04:** Read the listing via **ORM `select(AuditLog)`** — `AuditLog` lives in
  `app.core.audit_models` and is freely importable by modules (NOT a cross-module
  violation; only module↔module ORM imports are banned). This gives typed columns,
  clean filter composition, and clean keyset ordering. (Reports aggregates keep raw
  `text()` SQL per D-55-02; this divergence is deliberate — audit is a typed listing,
  not a cross-module aggregate.)
- **D-05:** **Filters (all optional, combined with AND):**
  - `actorUserId` → exact UUID equality (`actor_user_id = :id`).
  - `actorEmailSnapshot` → **case-insensitive substring** (`actor_email_snapshot ILIKE
    '%' || :q || '%'`), per AUD-02 ("substring/exact").
  - `resource_type` → exact equality.
  - `action` → exact equality; **validated** against the set of valid event names
    derived from `LOCKED_AUDIT_EVENTS` (the first element of each `(event,
    resource_type)` tuple). `resource_type` likewise validated against the set of
    valid resource types. Unknown value → **422** `audit_filter_invalid` (AUD-03).
- **D-06:** **Time window:** `from` / `to` are `YYYY-MM-DD` **date** params interpreted
  as **inclusive Europe/Moscow day bounds** on `created_at`:
  `(created_at AT TIME ZONE 'Europe/Moscow')::date BETWEEN :from AND :to`
  (consistent with Phase 55 D-04, AUD-04). Both **OPTIONAL** — unlike reports, the
  primary use case is browsing recent activity unfiltered. `to < from` → 422. No
  366-day range cap on the JSON endpoint (bounded by `pageSize`).

### Pagination & ordering
- **D-07:** Audit-log JSON uses **`PageQuery` + `ResponseEnvelope[PaginatedData[AuditLogItem]]`**
  — this is exactly the listing D-55-11 reserved `PaginatedData[T]` for. Defaults
  `page=1`, `pageSize=20`, `pageSize` max 100 (PageQuery bounds, pagination.py).
- **D-08:** Ordering is **always `created_at DESC, id DESC`** (AUD-06, not
  user-configurable) — backed by the `ix_audit_log_created_at (created_at DESC, id DESC)`
  composite added in Phase 54 (audit_models.py:72). This keyset ordering keeps
  pagination stable across concurrent inserts (SC#3).
- **D-09:** `AuditLogItem` DTO fields (camelCase wire): `id`, `createdAt` (ISO-8601
  with offset), `actorUserId` (nullable), `actorEmailSnapshot` (nullable), `action`,
  `resourceType`, `resourceId` (nullable), `payload` (JSONB passed through as a nested
  object). Owner sees full detail including `payload`. Extends `BackendSchemaBase`.

### CSV URL design
- **D-10:** **Dedicated `.csv` suffix routes** (roadmap SC#4 is authoritative and
  lists these exact paths) — NOT `?format=csv`. Each `.csv` route accepts the
  **same query params** as its JSON sibling and produces consistent results
  (EXP-02 + AUD-05 / SC#5 for audit; report CSVs mirror their JSON query DTOs).

### CSV generation mechanism
- **D-11:** Emit via **`StreamingResponse`** wrapping a generator that yields CSV
  text rows. Use the **stdlib `csv` module** (writer over a per-row `io.StringIO`
  shim) for RFC-4180 escaping (`QUOTE_MINIMAL` → quotes fields containing comma /
  quote / newline). **Comma delimiter**, **`\r\n` line terminator** (RFC 4180,
  SC#4 explicit). First yielded chunk is the **UTF-8 BOM** (`(U+FEFF)`) so Excel
  detects UTF-8 (EXP-04, Cyrillic round-trip). Response headers:
  `media_type="text/csv; charset=utf-8"`,
  `Content-Disposition: attachment; filename="<name>.csv"`.
- **D-12:** Factor a small shared **`reports/csv_export.py`** helper (BOM prefix +
  csv.writer shim + `StreamingResponse` assembly) reused by all four endpoints so
  the RFC-4180/BOM discipline lives in one place.

### CSV formatting & column schemas
- **D-13:** **Money columns:** format signed kopecks → rubles with **2 decimals,
  period decimal separator, no thousands grouping** (e.g. `-1234.56`) — keeps fields
  delimiter-safe and RFC-4180-literal (SC#4).
  - ⚠ **Researcher confirm:** Russian Excel locale defaults to comma-decimal /
    semicolon-delimiter. If period-decimal opens as text in ru-Excel, evaluate a
    semicolon-delimited + comma-decimal variant. Default honors the *locked* "RFC
    4180" success criterion; only deviate with evidence.
- **D-14:** **Date columns formatted in Europe/Moscow:** report period buckets keep
  `YYYY-MM-DD` (day) / `YYYY-MM` (month); audit `createdAt` → `YYYY-MM-DD HH:MM:SS`
  MSK (human-readable for Excel, no offset suffix).
- **D-15:** **Column schemas reuse the same Phase 55 service aggregation functions**
  as the JSON endpoints (single source of truth), then flatten:
  - `revenue.csv`: one row per period — `period, netRubles, cashRubles, onlineRubles,
    membershipRubles, ptPackageRubles`.
  - `clients.csv`: single summary row — `fromDate, toDate, within, activeMemberships,
    expiringWithinN, newClients`.
  - `visits.csv`: daily series rows — `date, count` (the JSON hourly/average views are
    out of the primary CSV; see discretion).
  - `audit-log.csv`: `createdAt, actorUserId, actorEmailSnapshot, action, resourceType,
    resourceId, payload` — `payload` serialized as a compact JSON string in one cell.
- **D-16:** **Audit CSV exports ALL rows matching the filters** (no pagination),
  streamed **row-by-row from a server-side query iterator** so memory stays bounded
  at any volume. Same filters as the JSON endpoint (SC#5). Single-gym volume is low,
  so no hard size cap — streaming is the bound.

### Claude's Discretion
- Exact CSV header label casing/wording; whether `visits.csv` also appends an hourly
  section + average row or stays daily-only; whether `clients.csv` is one row or
  key/value rows.
- CSV `filename` strings (e.g. `audit-log-2026-05-24.csv`).
- Internal API of `csv_export.py`; sync generator vs async streaming.
- Internal `service.py` ↔ `repository.py` split for the audit-log read path.
- Test fixture rows/dates for the correctness suite (Phase 57 owns the DST golden-path;
  Phase 56 should still test pagination stability across inserts, filter narrowing,
  Cyrillic CSV round-trip, and BOM presence).

</decisions>

<canonical_refs>
## Canonical References

**Downstream agents MUST read these before planning or implementing.**

### Requirements & roadmap
- `.planning/REQUIREMENTS.md` — AUD-01..06, EXP-01..04 (audit read API + CSV export)
- `.planning/ROADMAP.md` §"Phase 56" — goal + 5 success criteria (authoritative on
  `.csv` suffix paths, ordering, BOM/RFC-4180, reception 403)
- `.planning/phases/55-revenue-clients-visits-reports/55-CONTEXT.md` — **the locked
  report-stack baseline** (D-55-11 reserved `PaginatedData[T]` for THIS audit listing;
  revenue/clients/visits response shapes that the CSV exporters flatten). Read first.
- `.planning/phases/54-foundations-module-scaffold-rbac-parity-indexes/54-CONTEXT.md` —
  RBAC (`Resource.AUDIT_LOG` owner-only pairs) + `ix_audit_log_created_at` composite index.

### Audit log (source of truth for the read API)
- `apps/backend/app/core/audit_models.py` — `AuditLog` ORM: columns `actor_user_id`
  (nullable UUID), `actor_email_snapshot` (nullable Text), `action`, `resource_type`,
  `resource_id` (nullable UUID), `payload` (JSONB), `created_at`; indexes incl.
  `ix_audit_log_created_at (created_at DESC, id DESC)` (line 72), `ix_audit_log_action`,
  `ix_audit_log_resource_type`.
- `apps/backend/app/core/audit.py` §244+ — `LOCKED_AUDIT_EVENTS` frozenset of
  `(event, resource_type)` tuples — the 69-event taxonomy; source for `action` /
  `resource_type` filter validation (D-05).
- `apps/backend/app/core/permissions.py` §57/128-129 — `Resource.AUDIT_LOG = "audit-log"`,
  `(VIEW, AUDIT_LOG)` + `(LIST, AUDIT_LOG)` in `OWNER_ONLY`.

### Reports module (host for both capabilities)
- `apps/backend/app/modules/reports/router.py` — existing JSON report routes + the
  `(VIEW, REPORTS)` chokepoint pattern; add `.csv` routes here and a new `audit_log_router`.
- `apps/backend/app/modules/reports/service.py` / `repository.py` — Phase 55 aggregation
  functions to REUSE for CSV (single source of truth); add audit-log read path.
- `apps/backend/app/modules/reports/schemas.py` / `constants.py` — add `AuditLogItem`,
  audit query DTO, CSV column constants.

### Shared API patterns
- `apps/backend/app/core/pagination.py` §20/32 — `PageQuery` (page/pageSize bounds) +
  `PaginatedData[T]` — USED by the audit-log listing (D-07).
- `apps/backend/app/core/schemas.py` — `BackendSchemaBase`, `ResponseEnvelope[T]`,
  `envelope()`.
- `apps/backend/app/api/v1/router.py` §93 — `reports_router` mount site; add the
  `audit_log_router` (prefix `/audit-log`) mount alongside.
- `apps/backend/app/core/dependencies.py` — `CurrentUser`, `require_permission`.

### CSV (greenfield — no existing StreamingResponse/CSV usage in the codebase)
- Python stdlib `csv` (RFC-4180 escaping) + `fastapi.responses.StreamingResponse`.
  No prior in-tree pattern — establish `reports/csv_export.py` (D-12).

</canonical_refs>

<code_context>
## Existing Code Insights

### Reusable Assets
- **Phase 55 report aggregation** (`reports/service.py`) — revenue/clients/visits
  aggregators are reused verbatim by the CSV exporters; CSV only flattens + formats.
- **`PageQuery` + `PaginatedData[T]`** (`core/pagination.py`) — exact contract the
  audit-log listing needs; D-55-11 explicitly reserved it for this endpoint.
- **`AuditLog` ORM** (`core/audit_models.py`) — typed, importable from the reports
  module; already has the `(created_at DESC, id DESC)` index for keyset ordering.
- **`LOCKED_AUDIT_EVENTS`** (`core/audit.py`) — drives `action`/`resource_type` filter
  validation without hand-maintaining a list.
- **`require_permission(Action.LIST, Resource.AUDIT_LOG)`** — owner-only chokepoint,
  already in `OWNER_ONLY`; no new RBAC work this phase.

### Established Patterns
- **Europe/Moscow bucketing** — convert in SQL/ORM via `AT TIME ZONE 'Europe/Moscow'`
  for `created_at` date-window filtering (mirror Phase 55 D-04 discipline).
- **camelCase wire / snake_case Python** — via `BackendSchemaBase` (`extra='forbid'`).
- **No try/except in route handlers** — AppError subclasses bubble to the registered
  handler; raise typed 422 errors for invalid filters / `to<from`.
- **Read-only reports module** — no `models.py` of its own, no commits; audit read is
  a SELECT-only path.

### Integration Points
- `app/api/v1/router.py` ← add `audit_log_router` mount (`prefix="/audit-log"`); report
  CSV routes attach to the already-mounted `reports_router`.
- `audit_log` table ← ORM `select(AuditLog)` reads (D-04).
- `payments`/`memberships`/`clients`/`visits` ← already read by Phase 55 aggregators
  reused for CSV (no new table access).

</code_context>

<specifics>
## Specific Ideas

- The audit-log endpoint is the owner's "who did what" view across all 69 locked
  events — full `payload` detail is intentionally exposed (owner-only resource).
- CSV is explicitly an **Excel-for-Russia** deliverable: UTF-8 BOM is non-negotiable
  so Cyrillic fields round-trip; the BOM + RFC-4180 combination is the success bar.
- Pagination stability under concurrent inserts (SC#3) is the canonical correctness
  assertion for the audit listing — test by inserting a new row mid-pagination and
  asserting page-1 rows do not shift.

</specifics>

<deferred>
## Deferred Ideas

- **Russian-Excel CSV dialect** (semicolon delimiter + comma decimal) — only if the
  RFC-4180 period-decimal default proves unfriendly in ru-Excel (D-13 researcher flag).
  Default stays RFC-4180 per locked SC#4.
- **Full-timestamp audit filters** (sub-day `from`/`to` as timestamps) — date-granular
  MSK bounds ship now; finer precision deferred to a future phase if needed.
- **Server-side cursor / chunked export** for very large audit CSVs — single-gym volume
  is low; row-by-row streaming (D-16) suffices. Revisit when volume justifies it.
- **Frontend audit-log viewer + CSV download buttons** — v2.0 admin-web work.
- **OpenAPI byte-stable regen + forward-guards + operator runbook** — Phase 57 (HND/VER).

None of the above are scope creep into Phase 56.

</deferred>

---

*Phase: 56-audit-log-read-api-csv-export*
*Context gathered: 2026-05-24*

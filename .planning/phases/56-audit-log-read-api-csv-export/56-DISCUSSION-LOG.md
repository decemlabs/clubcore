# Phase 56: Audit Log Read API + CSV Export - Discussion Log

> **Audit trail only.** Do not use as input to planning, research, or execution agents.
> Decisions are captured in CONTEXT.md — this log preserves the alternatives considered.

**Date:** 2026-05-24
**Phase:** 56-audit-log-read-api-csv-export
**Mode:** `--auto` (all gray areas auto-selected to recommended defaults; no interactive prompts)
**Areas discussed:** Endpoint home & routing, Audit-log query & filters, Pagination & ordering, CSV URL design, CSV generation mechanism, CSV formatting & columns

---

## Endpoint home & routing

| Option | Description | Selected |
|--------|-------------|----------|
| Reuse `app/modules/reports/` | Add audit read API + CSV to the existing import-linter-wired read-only module | ✓ |
| New `app/modules/audit/` module | Dedicated module; requires new `.importlinter` registration | |
| Top-level core router | Mount audit read directly off core | |

**Auto choice:** Reuse `reports/` — no import-linter churn; mount `audit_log_router` at top-level `/audit-log`, attach `.csv` routes to existing `reports_router` (matches roadmap SC paths verbatim).
**Notes:** RBAC per resource — `(LIST, AUDIT_LOG)` for audit, `(VIEW, REPORTS)` for report CSVs; both already in `OWNER_ONLY`.

---

## Audit-log query mechanism & filters

| Option | Description | Selected |
|--------|-------------|----------|
| ORM `select(AuditLog)` | Typed read of the core-owned model (importable, not a cross-module violation) | ✓ |
| Raw `text()` SQL | Mirror Phase 55 reports raw-SQL discipline | |

**Auto choice:** ORM select — cleaner typed filters/keyset ordering; reports aggregates keep raw SQL (deliberate divergence — audit is a typed listing, not a cross-module aggregate).
**Notes:** Filters all optional + AND-combined: `actorUserId` exact, `actorEmailSnapshot` ILIKE substring, `resource_type`/`action` exact and validated against `LOCKED_AUDIT_EVENTS` (422 on unknown), `from`/`to` date-granular Europe/Moscow `created_at` bounds (optional, unlike reports).

---

## Pagination & ordering

| Option | Description | Selected |
|--------|-------------|----------|
| `PageQuery` + `PaginatedData[T]` | The contract D-55-11 reserved for this listing | ✓ |
| Bespoke aggregate envelope | Like the reports aggregates (no pagination) | |

**Auto choice:** `ResponseEnvelope[PaginatedData[AuditLogItem]]`, defaults page=1/pageSize=20 (max 100). Ordering always `created_at DESC, id DESC` (AUD-06), backed by the Phase 54 composite index — stable across concurrent inserts (SC#3).
**Notes:** `AuditLogItem` exposes full detail incl. `payload` (owner-only resource).

---

## CSV URL design

| Option | Description | Selected |
|--------|-------------|----------|
| `.csv` suffix routes | `/reports/revenue.csv`, `/audit-log.csv`, etc. | ✓ |
| `?format=csv` query | Single route, content negotiation | |

**Auto choice:** `.csv` suffix routes — roadmap SC#4 is authoritative and lists these exact paths. Each `.csv` route accepts the same query params as its JSON sibling.

---

## CSV generation mechanism

| Option | Description | Selected |
|--------|-------------|----------|
| `StreamingResponse` + stdlib `csv` + UTF-8 BOM | RFC-4180 escaping, comma delimiter, CRLF, BOM first chunk | ✓ |
| In-memory full-buffer response | Build whole CSV then return | |

**Auto choice:** Streamed generator, stdlib `csv` (QUOTE_MINIMAL), comma delimiter, `\r\n`, UTF-8 BOM first chunk, `text/csv; charset=utf-8` + attachment disposition. Shared `reports/csv_export.py` helper centralizes the discipline. Greenfield — no prior CSV/StreamingResponse code in the tree.

---

## CSV formatting & columns

| Option | Description | Selected |
|--------|-------------|----------|
| RFC-4180 period-decimal rubles | `-1234.56`, comma delimiter, delimiter-safe | ✓ |
| ru-Excel semicolon + comma-decimal | `-1234,56`, `;` delimiter (Russian Excel default) | |

**Auto choice:** RFC-4180 period-decimal (honors locked SC#4). Money = signed kopecks→rubles 2-dp period; dates Europe/Moscow (`YYYY-MM-DD` buckets, `YYYY-MM-DD HH:MM:SS` for audit). Column schemas reuse Phase 55 aggregation functions; audit CSV streams ALL filtered rows row-by-row (no pagination).
**Notes:** ⚠ Researcher to confirm ru-Excel acceptability of period-decimal; semicolon/comma-decimal variant deferred unless evidence shows it's needed.

---

## Claude's Discretion

- CSV header label casing/wording; `visits.csv` hourly-section inclusion; `clients.csv` row vs key/value layout.
- CSV `filename` strings; `csv_export.py` internal API; sync vs async streaming.
- `service.py` ↔ `repository.py` split for the audit read path.
- Test fixture rows/dates (Phase 57 owns the DST golden-path).

## Deferred Ideas

- Russian-Excel CSV dialect (semicolon + comma-decimal) — only on ru-Excel evidence.
- Full-timestamp (sub-day) audit filters.
- Server-side cursor / chunked export for very large audit CSVs.
- Frontend audit-log viewer + CSV download buttons (v2.0).
- OpenAPI byte-stable regen + forward-guards + operator runbook (Phase 57).

---
phase: 54-foundations-module-scaffold-rbac-parity-indexes
plan: "02"
subsystem: backend-schema
tags: [alembic, indexes, audit-log, performance, infra]
dependency_graph:
  requires: []
  provides:
    - ix_audit_log_created_at (composite DESC btree for Phase 56 stable ordering)
    - ix_audit_log_action (single-column btree for event-kind filters)
    - ix_audit_log_resource_type (single-column btree for resource filters)
    - migration 0040_audit_log_report_indexes
  affects:
    - apps/backend/app/core/audit_models.py
    - apps/backend/alembic/versions/0040_audit_log_report_indexes.py
tech_stack:
  added: []
  patterns:
    - literal index name + text() DESC composite index (mirrors payments/models.py:120)
    - alembic migration round-trip (upgrade + check + downgrade + upgrade)
key_files:
  created:
    - apps/backend/alembic/versions/0040_audit_log_report_indexes.py
  modified:
    - apps/backend/app/core/audit_models.py
decisions:
  - "INFRA-43 satisfied: three audit_log indexes added via migration 0040; ORM __table_args__ matches migration exactly so alembic check is clean"
  - "D-10 honored: ix_payments_received_at not touched (already exists in migration 0012)"
  - "D-12 honored: literal index names in both ORM and migration; alembic check reports no drift"
  - "D-11 implemented: composite (created_at DESC, id DESC) + single-column action + resource_type indexes"
metrics:
  duration: "3m"
  completed: "2026-05-24T15:14:08Z"
  tasks_completed: 2
  files_created: 1
  files_modified: 1
---

# Phase 54 Plan 02: Audit Log Report Indexes Summary

**One-liner:** Three audit_log btree indexes via Alembic migration 0040 — composite (created_at DESC, id DESC) for stable pagination + single-column action and resource_type for filter queries, with ORM __table_args__ in lockstep so alembic check round-trips clean.

## Tasks Completed

| Task | Name | Commit | Files |
|------|------|--------|-------|
| 1 | Extend AuditLog.__table_args__ with three new indexes | 176d988 | apps/backend/app/core/audit_models.py |
| 2 | Author migration 0040 and verify full round-trip + alembic check | 17d573a | apps/backend/alembic/versions/0040_audit_log_report_indexes.py |

## Verification Results

- `AuditLog.__table__` exposes `ix_audit_log_created_at`, `ix_audit_log_action`, `ix_audit_log_resource_type` — assertion exits 0
- `uv run alembic upgrade head` — exits 0 (migration 0039 → 0040 applied)
- `uv run alembic check` — exits 0 ("No new upgrade operations detected" — ORM and DB agree)
- `uv run alembic downgrade -1 && uv run alembic upgrade head` — exits 0 (clean round-trip)
- Migration 0040 has zero operational code touching `payments` or `ix_payments_received_at` (D-10 satisfied; only a comment mentions it)

## Decisions Made

- **Literal index names over op.f()**: matches the established project precedent from migrations 0034/0037; ensures `alembic check` autogenerate detects no drift (D-12).
- **DESC via text() predicates**: `sa.text("created_at DESC")` and `sa.text("id DESC")` in the migration; `text("created_at DESC")` and `text("id DESC")` in ORM `__table_args__` — byte-for-byte match keeps alembic check clean.
- **No payments changes**: `ix_payments_received_at` already exists from migration 0012; D-10 explicitly prohibits adding it again.
- **No speculative composites**: only the three indexes confirmed by Phase 55/56 query patterns are added; revenue and multi-column filter composites wait for query-plan evidence per the Deferred Ideas.

## Deviations from Plan

None — plan executed exactly as written.

The .env file was temporarily copied to the worktree backend directory to enable alembic to connect to the running Postgres instance during verification. The file is in .gitignore and was not committed.

## Threat Surface Scan

No new network endpoints, auth paths, or file access patterns introduced. Only read-side indexes added to an existing table. No new trust boundaries.

## Self-Check: PASSED

- FOUND: apps/backend/app/core/audit_models.py
- FOUND: apps/backend/alembic/versions/0040_audit_log_report_indexes.py
- FOUND: .planning/phases/54-foundations-module-scaffold-rbac-parity-indexes/54-02-SUMMARY.md
- FOUND: commit 176d988 (task 1 — extend AuditLog.__table_args__)
- FOUND: commit 17d573a (task 2 — migration 0040)

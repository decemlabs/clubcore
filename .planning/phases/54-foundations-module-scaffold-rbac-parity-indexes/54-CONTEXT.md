# Phase 54: Foundations — Module Scaffold + RBAC Parity + Indexes - Context

**Gathered:** 2026-05-24
**Status:** Ready for planning

<domain>
## Phase Boundary

Establish the architectural foundation for the v1.8 Reports + Audit Log read API **without shipping any report/audit endpoints yet**. Three deliverables only:

1. **INFRA-41** — `app/modules/reports/` module scaffold exists, registered in `.importlinter` `modules-independent`, with read-only discipline (no INSERT/UPDATE/DELETE on business tables).
2. **INFRA-42** — Backend RBAC enums gain the audit-log resource + owner-only pairs, mirrored byte-for-byte into admin-web `can.ts` + `registry.ts`; the three-way parity test stays green with a bumped count.
3. **INFRA-43** — Alembic aggregation indexes applied so Phase 55/56 report and audit queries are performant from day one.

**Out of scope (belongs to Phase 55–57):** any `/reports/*` or `/audit-log` endpoint body, query logic, CSV export, OpenAPI handoff.

</domain>

<decisions>
## Implementation Decisions

### RBAC: Resource & Action extension (INFRA-42)
- **D-01:** Add `Resource.AUDIT_LOG = "audit-log"` to `app/core/permissions.py` (kebab-case on the wire, mirroring the multi-word `USERS`/`SCHEDULE_SLOTS`/`OWNER_AREA` convention). `Resource.REPORTS` **already exists** (`permissions.py:39`) — no new resource needed for reports.
- **D-02:** **Do NOT introduce a new `Action.READ`.** Reuse existing `Action.VIEW` (single/aggregate read) and `Action.LIST` (paginated listing). The Phase 37 INFRA-26 convention already separates VIEW from LIST, `(VIEW, REPORTS)` already exists, and a redundant READ action would require a frontend mirror and break the byte-for-byte parity convention. INFRA-42's literal "Action.READ" wording is satisfied *semantically* by VIEW.
  - ⚠ **Researcher must confirm** this reading of INFRA-42 against the parity test before planning — the requirement text names `Action.READ` explicitly, but the success criterion (SC#2) only tests that the resources + owner-only pairs exist and mirror.

### OWNER_ONLY pairs + parity count (INFRA-42)
- **D-03:** REPORTS — `(VIEW, REPORTS)` is **already present** in both `OWNER_ONLY` (`permissions.py:64`) and `can.ts:14`. Reports endpoints are aggregate reads → VIEW covers them. No new REPORTS pair unless a future list-style report appears.
- **D-04:** AUDIT_LOG — add two owner-only pairs: `(VIEW, AUDIT_LOG)` and `(LIST, AUDIT_LOG)`. The audit read API is a paginated listing plus filterable reads; reception gets **zero** audit perms (403). Mirror byte-for-byte into `can.ts` (OWNER_ONLY array) and `registry.ts` (Resource union gains `'audit-log'`).
- **D-05:** Bump the parity count assertion `33 → 35` in `test_rbac_parity.py` (`test_owner_only_count_is_thirty_three` — rename/retarget the count) and update the three set-equality tests' header docstring counts. Action enum is unchanged (no new value).

### Reports module scaffold & cross-module data access (INFRA-41)
- **D-06:** Create `app/modules/reports/` with the standard *slim* scaffold: `__init__.py`, `router.py`, `service.py`, `repository.py`, `schemas.py`, `constants.py`, `permissions.py`. **No `models.py`** (reports own no tables) and **no `email_templates.py`** (no notifications). In Phase 54 these are scaffold/stubs — endpoint bodies land in Phase 55.
- **D-07:** Read-only discipline — the reports module performs **zero** INSERT/UPDATE/DELETE on business tables. The SVC001 commit-gate does not apply (no write paths).
- **D-08:** Cross-module data is read via **raw SQL `text()` SELECTs** in `reports/repository.py`, **not** by importing other modules' ORM models. This follows the Phase 49 D-49-03 precedent (`online_payments` reads subject tables via raw `text()` SELECT to avoid ORM imports) and keeps `modules-independent` clean with **zero new `ignore_imports` edges**.
  - ⚠ **Researcher confirm:** raw-SQL aggregation across `payments`/`clients`/`visits`/`audit_log` is the recommended path vs. adding `ignore_imports` ORM edges. Raw SQL is preferred here because reports is a pure read aggregator that would otherwise need broad ignore edges into nearly every module.
- **D-09:** Register `app.modules.reports` in the `.importlinter` `[importlinter:contract:modules-independent]` `modules =` list (preemptively, per the INFRA-15 "contract entries land before/with the body" discipline already used for Phases 47/51).

### Aggregation indexes (INFRA-43, Alembic)
- **D-10:** `payments(received_at)` — **ALREADY EXISTS** as `ix_payments_received_at` (`received_at DESC`, `payments/models.py:120`). Do **not** recreate. INFRA-43 is satisfied for this index by the existing schema. A revenue-specific composite (e.g. `(received_at, method, subject_kind)`) is **deferred to Phase 55** query-plan evidence — do not speculatively add.
- **D-11:** Add three NEW indexes on `audit_log` in a single new Alembic migration (next revision `0040_audit_log_report_indexes`):
  - `ix_audit_log_created_at` on `(created_at DESC, id DESC)` — composite chosen so the Phase 56 stable ordering `created_at DESC, id DESC` is fully index-covered.
  - `ix_audit_log_action` on `(action)`.
  - `ix_audit_log_resource_type` on `(resource_type)`.
  Single-column btree for the two filter columns; multi-column filter composites are deferred until a Phase 56 query plan justifies them.
- **D-12:** Index names are **literal strings** (not `op.f()`), DESC expressed via `text(...)` — mirrors `payments/models.py:120` and migration `0037` precedent. Update the `AuditLog.__table_args__` in `app/core/audit_models.py` to match the migration so `alembic check` round-trips clean (autogenerate detects no drift).

### Claude's Discretion
- Exact migration revision number/slug (`0040_...`) and `down_revision` wiring (point at the current head).
- Internal ordering/contents of the scaffold stub files (so long as read-only + no ORM cross-imports hold).

</decisions>

<canonical_refs>
## Canonical References

**Downstream agents MUST read these before planning or implementing.**

### Requirements & roadmap
- `.planning/REQUIREMENTS.md` — INFRA-41 / INFRA-42 / INFRA-43 (lines 12–14)
- `.planning/ROADMAP.md` §"Phase 54" (lines 149–158) — goal + 4 success criteria

### RBAC parity (INFRA-42)
- `apps/backend/app/core/permissions.py` — `Role`/`Action`/`Resource` StrEnums + `OWNER_ONLY` frozenset + `can()`. Source of truth; `Resource.REPORTS` + `(VIEW, REPORTS)` already present.
- `apps/admin-web/src/shared/session/can.ts` — frontend `OWNER_ONLY` array (must mirror byte-for-byte)
- `apps/admin-web/src/shared/session/registry.ts` — frontend `Resource`/`Action` unions (add `'audit-log'`)
- `apps/backend/tests/integration/test_rbac_parity.py` — three set-equality tests + the `OWNER_ONLY` count assertion to bump (33→35)

### Module scaffold + import-linter (INFRA-41)
- `apps/backend/.importlinter` — `modules-independent` + `core-not-depend-on-modules` + `integrations-not-depend-on-modules` contracts; `ignore_imports` precedent comments (esp. Phase 49 raw-SQL discipline)
- `apps/backend/app/modules/payments/` — reference module scaffold layout (slim variant target)

### Indexes / migrations (INFRA-43)
- `apps/backend/app/core/audit_models.py` — `AuditLog` ORM + existing `__table_args__` (only `ix_audit_log_actor_user_id_created_at` today)
- `apps/backend/app/modules/payments/models.py` §108–120 — existing index patterns incl. `ix_payments_received_at` (DESC via `text()`)
- `apps/backend/app/core/database.py` §28 — `NAMING_CONVENTION` (index/constraint naming rules)
- `apps/backend/alembic/versions/0037_online_refunds.py` — migration skeleton precedent: literal index names (no `op.f()`), `text()` predicates, `down_revision` discipline. Current head: `0039_payment_notifications`.

</canonical_refs>

<code_context>
## Existing Code Insights

### Reusable Assets
- **Module scaffold template** — `app/modules/payments/` shows the canonical file set; reports uses a slimmed subset (no `models.py`, no `email_templates.py`).
- **`can()` + `OWNER_ONLY`** (`app/core/permissions.py`) — extend in place; `Resource.REPORTS` + `(VIEW, REPORTS)` already shipped (v1.1).
- **Three-way parity test** (`tests/integration/test_rbac_parity.py`) — static-file analysis, no infra; count assertion + docstring counts must be updated.
- **`NAMING_CONVENTION`** (`app/core/database.py:28`) — governs auto-generated constraint/index names; explicit literal index names bypass it (precedent in payments/models + 0037).
- **Raw-SQL cross-module read precedent** — Phase 49 `online_payments` reads subject tables via `text()` SELECT (D-49-03) to avoid ORM imports; reports adopts the same to stay `modules-independent`-clean.

### Established Patterns
- **Import-linter "contract before body"** — module registered in `.importlinter` preemptively (Phases 47/51), `unmatched_ignore_imports_alerting = warn` cushions edges before bodies land.
- **Migrations** — sequential `NNNN_slug` revision IDs, literal index names, `text()` for DESC/partial predicates, ORM `__table_args__` kept in lockstep so `alembic check` is green.

### Integration Points
- `.importlinter` `modules-independent` list ← add `app.modules.reports`.
- `app/core/permissions.py` + `can.ts` + `registry.ts` ← add `AUDIT_LOG` resource + 2 owner-only pairs (kept in three-way sync).
- New Alembic migration on `audit_log` + matching `audit_models.py` `__table_args__`.

</code_context>

<specifics>
## Specific Ideas

- Audit-log ordering target (drives the `created_at` index shape): `created_at DESC, id DESC` (Phase 56 SC#3 stable pagination). Hence the composite `(created_at DESC, id DESC)` rather than a bare `created_at` index.
- `payments(received_at)` requirement is already met — surface this to the planner so it does not generate a redundant migration.

</specifics>

<deferred>
## Deferred Ideas

- **Revenue composite index** `payments(received_at, method, subject_kind)` — only if Phase 55 `EXPLAIN` shows the existing `ix_payments_received_at` is insufficient. Not in Phase 54.
- **Audit-log multi-column filter composites** — only if Phase 56 query plans justify them; Phase 54 ships single-column `action`/`resource_type` indexes.
- All `/reports/*` and `/audit-log` endpoint bodies, CSV export, OpenAPI handoff — Phases 55–57.

</deferred>

---

*Phase: 54-foundations-module-scaffold-rbac-parity-indexes*
*Context gathered: 2026-05-24*

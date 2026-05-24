# Phase 54: Foundations — Module Scaffold + RBAC Parity + Indexes - Discussion Log

> **Audit trail only.** Do not use as input to planning, research, or execution agents.
> Decisions are captured in CONTEXT.md — this log preserves the alternatives considered.

**Date:** 2026-05-24
**Phase:** 54-foundations-module-scaffold-rbac-parity-indexes
**Mode:** `--auto` (Claude selected recommended option for each gray area; no interactive prompts)
**Areas discussed:** Action-enum strategy, OWNER_ONLY pairs + parity count, Reports module scaffold & data access, Aggregation index shape

---

## Action-enum strategy (INFRA-42)

| Option | Description | Selected |
|--------|-------------|----------|
| Reuse VIEW + LIST | Add only `Resource.AUDIT_LOG`; map reads to existing VIEW, listings to LIST | ✓ |
| Introduce `Action.READ` | Add a new READ action per INFRA-42's literal wording | |

**Choice:** Reuse VIEW + LIST (recommended).
**Notes:** `(VIEW, REPORTS)` already exists; Phase 37 INFRA-26 already separates VIEW/LIST. A new READ action would be redundant with VIEW and require a frontend mirror, breaking the byte-for-byte parity convention. Flagged for researcher to confirm against INFRA-42 wording.

---

## OWNER_ONLY pairs + parity count (INFRA-42)

| Option | Description | Selected |
|--------|-------------|----------|
| (VIEW,AUDIT_LOG) + (LIST,AUDIT_LOG); count 33→35 | Two new audit pairs; REPORTS pair already present | ✓ |
| Single (VIEW,AUDIT_LOG); count 33→34 | Only a view pair for audit log | |

**Choice:** Two new pairs, count 33→35 (recommended).
**Notes:** Audit read API is paginated listing + filterable reads; reception gets zero audit perms. Mirror into can.ts + registry.ts (`'audit-log'`).

---

## Reports module scaffold & cross-module data access (INFRA-41)

| Option | Description | Selected |
|--------|-------------|----------|
| Raw SQL `text()` SELECTs, zero ignore edges | Reports reads other tables via raw SQL; no ORM imports | ✓ |
| ORM imports + `ignore_imports` edges | Import other modules' models, add allowlist edges | |

**Choice:** Raw SQL, zero new ignore_imports (recommended).
**Notes:** Follows Phase 49 D-49-03 precedent. Slim scaffold (no models.py / email_templates.py); read-only discipline. Register `app.modules.reports` preemptively in `.importlinter`.

---

## Aggregation index shape (INFRA-43)

| Option | Description | Selected |
|--------|-------------|----------|
| Reuse existing payments index; 3 audit_log indexes, created_at composite | `ix_payments_received_at` already exists; add `(created_at DESC, id DESC)`, `action`, `resource_type` | ✓ |
| Recreate all 4 indexes incl. payments | Add payments(received_at) again + composites everywhere | |

**Choice:** Reuse + 3 new audit_log indexes (recommended).
**Notes:** `payments(received_at)` already satisfied by `ix_payments_received_at`. Composite `(created_at DESC, id DESC)` backs Phase 56 stable pagination. Literal index names + `text()` DESC; keep ORM `__table_args__` in lockstep.

---

## Claude's Discretion

- Migration revision number/slug (`0040_...`) and `down_revision` wiring.
- Internal contents/ordering of scaffold stub files (read-only + no ORM cross-imports preserved).

## Deferred Ideas

- Revenue composite index `payments(received_at, method, subject_kind)` — only if Phase 55 EXPLAIN shows need.
- Audit-log multi-column filter composites — only if Phase 56 query plans justify.
- All `/reports/*` + `/audit-log` endpoint bodies, CSV export, OpenAPI handoff — Phases 55–57.

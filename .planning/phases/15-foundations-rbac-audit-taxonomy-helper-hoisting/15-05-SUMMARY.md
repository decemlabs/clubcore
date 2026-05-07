---
phase: 15-foundations-rbac-audit-taxonomy-helper-hoisting
plan: 05
subsystem: docs/governance
tags: [docs, key-decisions, project-md, requirements-md, foundations, v1.2, infra-14, d-07]
requires:
  - 15-04 (BackendSchemaBase implementation; this plan's INFRA-12 wording references its final config)
provides:
  - .planning/PROJECT.md ## Key Decisions: 3 v1.2 rows (inclusive end_date, gym_date STORED + UNIQUE, accepted friend-fraud risk)
  - .planning/REQUIREMENTS.md INFRA-12: aligned wording with Pydantic 2.11+ canonical pair (validate_by_name + validate_by_alias)
affects:
  - .planning/PROJECT.md (Key Decisions section only)
  - .planning/REQUIREMENTS.md (INFRA-12 line only)
tech-stack:
  added: []
  patterns:
    - "Documentation-only plan: substance copied from STATE.md ## Decisions; phrasing per CD-02 planner discretion."
    - "INFRA-12 wording locked AFTER Plan 04 ships so doc references the actual implementation outcome (D-07)."
key-files:
  created: []
  modified:
    - .planning/PROJECT.md
    - .planning/REQUIREMENTS.md
decisions:
  - "Land residual friend-fraud risk acceptance in PROJECT.md Key Decisions, NOT in code comments (per SUMMARY.md 'Gaps to flag for plan-phase' item 4 — explicit mandate)."
  - "INFRA-12 wording uses 'replacing the deprecated populate_by_name=True' as a deprecation note, not a config directive — the new line still mentions populate_by_name once but only as historical context."
metrics:
  duration: ~5 min
  tasks: 2
  files-modified: 2
  commits: 2
  completed: 2026-05-07
wave: 3
depends_on: [15-04]
---

# Phase 15 Plan 05: PROJECT.md Key Decisions + REQUIREMENTS.md INFRA-12 wording

**One-liner:** Lock 3 v1.2 Key Decisions in PROJECT.md (inclusive end_date, gym_date STORED + UNIQUE, accepted friend-fraud risk) and align REQUIREMENTS.md INFRA-12 wording with the implementation's `validate_by_name + validate_by_alias` Pydantic 2.11+ spelling.

## Outcome

Documentation-only plan. No code changes, no tests, no behavior change at runtime. Two files touched, exactly the rows / line specified in the plan; no incidental edits.

## Tasks Completed

### Task 1 — Append 3 v1.2 Key Decisions to PROJECT.md (INFRA-14, CD-02)

Commit: `86e1743`

Three new rows appended at the end of `## Key Decisions` table in `.planning/PROJECT.md`, immediately after the existing `clients/service.py write paths…` row (the prior last data row). Verbatim cell text for traceability:

| # | Decision (cell 1) | Outcome (cell 3) |
|---|-------------------|------------------|
| 1 | Membership `end_date` is INCLUSIVE — last valid check-in day | ✓ Good — v1.2 (Phase 15) |
| 2 | `gym_date = (checked_in_at AT TIME ZONE 'Europe/Moscow')::date` materialised as a STORED Postgres column with `UNIQUE (client_id, gym_date)` | ✓ Good — v1.2 (Phase 15 / VIS-01) |
| 3 | Accepted residual friend-fraud risk for v1.2 single-zal scope | ✓ Accepted — v1.2 (Phase 15) |

Diff stat: `1 file changed, 3 insertions(+)`. No other line touched. Existing v1.0 / v1.1 rows preserved byte-for-byte.

Acceptance criteria (all green):
- `grep -c "INCLUSIVE" .planning/PROJECT.md` = 1
- `grep -c "gym_date" .planning/PROJECT.md` = 1
- `grep -c "friend-fraud" .planning/PROJECT.md` = 1
- `grep -c "Phase 15" .planning/PROJECT.md` = 3 (one per new row)
- `grep -c "✓ Accepted — v1.2 (Phase 15)" .planning/PROJECT.md` = 1
- `grep -cE "^\| .* \| .* \| ✓ (Good|Accepted) — v1\.2 \(Phase 15.*\) \|$" .planning/PROJECT.md` = 3

Mandate satisfied: per SUMMARY.md "Gaps to flag for plan-phase" item 4, the residual friend-fraud risk acceptance now lives as a structured Key Decisions entry — discoverable via the standard PROJECT.md scan path, not buried in a code comment.

### Task 2 — REQUIREMENTS.md INFRA-12 wording fix (D-07)

Commit: `cacbb77`

One-line edit on the INFRA-12 bullet. Diff stat: `1 file changed, 1 insertion(+), 1 deletion(-)`.

**Before** (line 18):

```markdown
- [ ] **INFRA-12**: `app/core/schemas.py` exposes `BackendSchemaBase(BaseModel)` with `alias_generator=to_camel`, `populate_by_name=True`, `extra='forbid'`; v1.2 schemas (memberships, visits) inherit from it; ruff `UP007` enforced repo-wide (`X | None` not `Optional[X]`).
```

**After** (line 18):

```markdown
- [ ] **INFRA-12**: `app/core/schemas.py` exposes `BackendSchemaBase(BaseModel)` with `alias_generator=to_camel`, `validate_by_name=True`, `validate_by_alias=True`, `extra='forbid'` (Pydantic 2.11+ canonical pair, replacing the deprecated `populate_by_name=True`); v1.2 schemas (memberships, visits) inherit from it; ruff `UP007` enforced repo-wide (`X | None` not `Optional[X]`).
```

Acceptance criteria (all green):
- `grep -cE "^- \[ \] \*\*INFRA-12\*\*:" .planning/REQUIREMENTS.md` = 1 (still unchecked, single bullet)
- `grep -c "validate_by_name=True" .planning/REQUIREMENTS.md` = 1
- `grep -c "validate_by_alias=True" .planning/REQUIREMENTS.md` = 1
- `grep -c "Pydantic 2.11+ canonical pair" .planning/REQUIREMENTS.md` = 1
- Old config-style `populate_by_name=True,` (where it was a config flag, not deprecation note) — gone.
- The new line still mentions `populate_by_name` once, but only as `replacing the deprecated populate_by_name=True` (historical context, not a directive).

The doc now matches the actual implementation (`apps/backend/app/core/schemas.py` BackendSchemaBase config, post-Plan-04). Future executors reading REQUIREMENTS.md will not regress to the deprecated spelling.

## Confirmation of Scope

- `.planning/PROJECT.md`: only the `## Key Decisions` section was edited; 3 rows appended; `git diff` shows exactly 3 added lines, zero modified or deleted lines.
- `.planning/REQUIREMENTS.md`: only the INFRA-12 bullet was edited; `git diff` shows exactly 1 changed line; INFRA-08…INFRA-11, INFRA-13, INFRA-14, TESTS-08, TESTS-11 IDs unchanged.

## Wave Position

This plan ran in **Wave 3** (per plan frontmatter `wave: 3`, `depends_on: [15-04]`). Wave 3 sequence required this plan to follow Plan 04 because the INFRA-12 wording must reference Plan 04's actual `BackendSchemaBase` config (post-rename, post-config-spelling). Both sides are now locked.

## Deviations from Plan

None — plan executed exactly as written.

## Threat Surface

No new security-relevant surface introduced. This plan only edits planning markdown files. The `<threat_model>` mitigations (T-15-15 friend-fraud documentation, T-15-16 wording-vs-implementation drift) are both addressed:
- **T-15-15** mitigated via Task 1 row 3 (residual friend-fraud risk now in Key Decisions).
- **T-15-16** mitigated via Task 2 (INFRA-12 wording matches `apps/backend/app/core/schemas.py`).

## Self-Check: PASSED

- [x] `.planning/PROJECT.md` modified — 3 rows appended in Key Decisions
- [x] `.planning/REQUIREMENTS.md` modified — INFRA-12 line updated
- [x] Commit `86e1743` exists (PROJECT.md)
- [x] Commit `cacbb77` exists (REQUIREMENTS.md)
- [x] No STATE.md / ROADMAP.md edits (orchestrator-owned)
- [x] No code changes, no tests, no openapi.json drift possible (no Python touched)

---
phase: 62-clubcore-rebrand
plan: 06
subsystem: docs / planning
tags: [rebrand, docs, planning, historical-immutability]
dependency_graph:
  requires:
    - 62-01 (pnpm package rename baseline)
  provides:
    - .planning/HISTORICAL_NOTE.md (boundary documentation for audit-trail-immutability)
    - forward-only .planning/ docs reading under clubcore name
    - top-level repo docs reading under clubcore name
  affects: []
tech_stack:
  added: []
  patterns:
    - Selective rewrite (current-state → clubcore; rename-description → both names; historical-context → preserved)
    - Audit-trail immutability boundary (D-62-09 / D-10-HISTORY-IMMUTABLE)
key_files:
  created:
    - .planning/HISTORICAL_NOTE.md
  modified:
    - .planning/PROJECT.md
    - .planning/MILESTONES.md
    - .planning/RETROSPECTIVE.md
    - CLAUDE.md
    - apps/backend/README.md
    - apps/admin-web/CLAUDE.md
    - apps/admin-web/README.md
decisions:
  - D-62-09 / D-10-HISTORY-IMMUTABLE applied (zero modifications under .planning/phases/47-61/, .planning/audits/, .planning/handoff/v1.[4-9]-*.md)
  - D-62-10 satisfied (.planning/HISTORICAL_NOTE.md authored at 28 lines)
  - D-62-02 honoured (CLUB_BRAND placeholder value "Sportzal" preserved in repo docs where gym-brand context demands it)
requirements: [REB-05]
metrics:
  duration: ~25 min
  completed: 2026-05-26
  files_changed: 7 modified + 1 created
  commits: 3 task commits
---

# Phase 62 Plan 06: Forward-Only .planning/ + Repo Docs Rewrite Summary

## Outcome

Forward-only documentation rewrite for the `sportzal → clubcore` rename completed. The forward-looking `.planning/` docs (PROJECT/MILESTONES/ROADMAP/REQUIREMENTS/RETROSPECTIVE/STATE) and the top-level repo docs (CLAUDE.md, apps/backend/README.md, apps/admin-web/CLAUDE.md, apps/admin-web/README.md) now read as a clubcore-named project. The new `.planning/HISTORICAL_NOTE.md` (28 lines) documents the immutability boundary so future readers grepping `sportzal` in historical artefacts have a single canonical explanation. Historical artefacts under `.planning/phases/47-61/*`, `.planning/audits/*`, and `.planning/handoff/v1.{4..9}-*.md` were not modified (verified via `git diff --name-only HEAD~3 HEAD -- <scopes>` returning empty).

## What Shipped

### Task 1 — HISTORICAL_NOTE.md (NEW file)

Created `.planning/HISTORICAL_NOTE.md` at exactly 28 lines (within 20–35 target window per CONTEXT line 173). Four sections:

1. `## Why grep shows sportzal in .planning/phases/47-61/* and .planning/audits/*` — single paragraph stating commit-message ↔ file-content coherence rationale.
2. `## Active code uses clubcore` — single paragraph listing forward-looking artefacts (PROJECT/MILESTONES/ROADMAP/REQUIREMENTS/STATE/RETROSPECTIVE + handoff/clubcore-*).
3. `## Boundary` — 7-row Markdown table classifying each scope (Immutable vs Active).
4. `## Lineage` — bullets citing D-62-09 / D-10-HISTORY-IMMUTABLE and pointing to STATE.md.

Acceptance grep counts:
- `grep -c 'D-62-09\|D-10-HISTORY-IMMUTABLE'` = 1 ✓
- `grep -c 'phases/47-61'` = 2 ✓
- `grep -c 'audits'` = 3 ✓
- `grep -c 'clubcore'` = 4 ✓
- `## ` section count = 4 ✓
- Total lines = 28 ✓ (within 20–35)

Commit: `78f7c934`

### Task 2 — Forward-only .planning/ docs rewrite

Per-file before/after `clubcore` mention count (across 6 forward-looking files):

| File | Before | After | Notes |
|------|--------|-------|-------|
| `.planning/PROJECT.md` | 12 | 13 | Title `# Sportzal` → `# clubcore`; intro line + CI command line rewritten. Historical v1.X archive blocks preserved. |
| `.planning/MILESTONES.md` | 0 | 3 | Added v1.10 in-progress header entry; updated v1.9-close-time forward-looking text to post-D-10-SPLIT reality. |
| `.planning/ROADMAP.md` | 19 | 19 | Already rewritten in prior 62-0X plans; verified ≥5 threshold met. |
| `.planning/REQUIREMENTS.md` | 11 | 11 | Already rewritten in prior 62-0X plans; verified ≥5 threshold met. |
| `.planning/RETROSPECTIVE.md` | 0 | 1 | Added v1.10 row to Cross-Milestone Process Evolution table. |
| `.planning/STATE.md` | 12 | 12 | Already rewritten in prior 62-0X plans; verified ≥5 threshold met. |

Total clubcore mentions: 59 (≥30 required ✓)

Commit: `e5e63516`

### Task 3 — Top-level repo docs rewrite

| File | Before | After | Notes |
|------|--------|-------|-------|
| `CLAUDE.md` (root) | 0 | 6 | Project header `Sportzal` → `clubcore` (with rename + D-62-02 annotation); 4 localStorage example references rewritten to `clubcore:*:v2` with legacy-shim annotation. |
| `README.md` (root) | — | — | n/a — file does not exist in this tree. |
| `apps/backend/README.md` | 0 | 2 | Title `# sportzal-backend` → `# clubcore-backend`; intro rewritten. |
| `apps/backend/CLAUDE.md` | — | — | n/a — file does not exist in this tree. |
| `apps/admin-web/README.md` | 0 | 2 | Added clubcore project header to generic Vite template. |
| `apps/admin-web/CLAUDE.md` | 0 | 2 | Header `# CLAUDE.md — SportZal Adminka` → `# CLAUDE.md — clubcore Adminka` + rename + D-62-02 annotation; `sportzal:mock:v1` example → `clubcore:mock:v2`. |
| `docs/architecture.md` | — | — | n/a — file does not exist in this tree. |
| `docs/conventions.md` | — | — | n/a — file does not exist in this tree. |

Commit: `72311631`

### Task 4 — Immutability verification

Verification command output (zero modifications under immutable scopes):

```bash
git diff --name-only HEAD~3 HEAD -- \
  .planning/phases/47 .planning/phases/48 .planning/phases/49 .planning/phases/50 \
  .planning/phases/51 .planning/phases/52 .planning/phases/53 .planning/phases/54 \
  .planning/phases/55 .planning/phases/56 .planning/phases/57 .planning/phases/58 \
  .planning/phases/59 .planning/phases/60 .planning/phases/61 .planning/audits \
  '.planning/handoff/v1.4-*.md' '.planning/handoff/v1.5-*.md' \
  '.planning/handoff/v1.6-*.md' '.planning/handoff/v1.7-*' \
  '.planning/handoff/v1.8-*.md' '.planning/handoff/v1.9-*.md'
# → (empty output; 0 files)
```

`git status --short` after all task commits returned empty for these scopes. **PASS.**

## Retained `sportzal` Occurrences (per Selective Rewrite Rules)

Every remaining `sportzal` substring in modified files falls into one of three rule categories:

### Category b — Rename-description prose (`"sportzal → clubcore"`, "renamed from sportzal")

- `CLAUDE.md`: project header annotation `*(переименован из sportzal в Phase 62 / v1.10; ...)*`
- `apps/backend/README.md`: `Backend для clubcore (переименован из sportzal ...)`
- `apps/admin-web/README.md`: `Admin SPA for clubcore (...; renamed from sportzal ...)`
- `apps/admin-web/CLAUDE.md`: `Renamed from "SportZal Adminka" → "clubcore-adminka" ...`
- `.planning/PROJECT.md` (line ~5): `clubcore — CRM (переименован из sportzal в Phase 62 / v1.10; ...)`
- `.planning/MILESTONES.md` (v1.10 entry): `rename sportzal → clubcore across ...`
- `.planning/RETROSPECTIVE.md` (v1.10 row): `project rename sportzal → clubcore across ...`

### Category c — Historical-context citations

- `.planning/PROJECT.md` line 13 (the "Текущее состояние (после v1.3)" snapshot): `pnpm --filter @sportzal/api-client codegen drift-gate` — describes v1.3-era CI command.
- `.planning/PROJECT.md` v1.6 archive (line ~42): `sz:email:circuit:` Redis prefix + `infra/dns/sportzal.ru.zone` — v1.6-shipped state.
- `.planning/PROJECT.md` line ~128: v1.9-archive sentence "API Handoff + Production Hardening ... `npm-publish @sportzal/api-client`" — pre-rename plan-text.
- `.planning/PROJECT.md` line ~253: validated requirement row `✓ Versioned localStorage: sportzal:session:v1, sportzal:ui:v1, sportzal:mock:v1 — pre-existing` — historically true at validation time.
- `.planning/PROJECT.md` line ~348: "**Backend пакет:** имя Python-пакета — `app` (не `sportzal`, не `src/sportzal`)" — historical key-decision clarification.
- `.planning/PROJECT.md` line ~375: Key Decisions row "Python-пакет называется `app`, не `sportzal`" — historical decision.
- `.planning/STATE.md` lines 69–70: `pnpm --filter @sportzal/api-client typecheck/test` — v1.9 milestone-gate verification evidence (factual at that time).
- `.planning/STATE.md` line 109: D-10-HISTORY-IMMUTABLE decision text quoting "почему grep всё ещё находит 'sportzal' в historical artifacts" — meta-citation in decision log.
- `.planning/RETROSPECTIVE.md` line ~215: `infra/dns/sportzal.ru.zone` — v1.6 milestone retrospective ("DNS runbook is code-adjacent, not code") describing a file-name as it existed under the old name.
- `.planning/MILESTONES.md` v1.0 archive line ~191: `@sportzal/ui, @sportzal/api-client` placeholders — v1.0-shipped state.
- `.planning/MILESTONES.md` v1.6 archive (line ~76): `sz:email:circuit:` + `infra/dns/sportzal.ru.zone` — v1.6-shipped state.

### Category — CLUB_BRAND placeholder value `"Sportzal"` (per D-62-02)

Intentionally retained where context demands the gym-brand placeholder (NOT the project name):

- `.planning/PROJECT.md` line ~87: `"Sportzal" placeholder` (in CLUB_BRAND constant description)
- `.planning/PROJECT.md` line ~94: `Hardcoded "Sportzal" в email_templates` (CLUB_BRAND extraction context)
- `.planning/STATE.md` line ~105: `"Sportzal" placeholder` (D-10-NO-NEW-BUSINESS decision)
- `.planning/STATE.md` line ~108: `Hardcoded "Sportzal" в email_templates — placeholder для per-club brand` (D-10-BRAND-DISTINCTION decision)
- `.planning/ROADMAP.md` line ~52: `значение неизменно — "Sportzal" placeholder` (CLUB_BRAND extraction SC)
- `CLAUDE.md` (root) project header annotation: `CLUB_BRAND placeholder value "Sportzal" сохранён per D-62-02`
- `apps/backend/README.md` intro annotation: `CLUB_BRAND gym-name placeholder "Sportzal" сохранён per D-62-02`
- `apps/admin-web/CLAUDE.md` rename note: `CLUB_BRAND placeholder value "Sportzal" (gym-name) preserved per D-62-02`

### Category — Legacy-shim / fallback-chain descriptions

Retained because they describe the active fallback machinery shipped in plan 62-04:

- `.planning/STATE.md` line ~106: `env CLUBCORE_EMAIL_FROM → SPORTZAL_EMAIL_FROM (legacy, deprecated-warning) → hardcoded default chain`
- `.planning/STATE.md` line ~130: deferred-items row `sportzal:* localStorage migration logic + SPORTZAL_EMAIL_FROM env fallback removal → v1.11 / Phase 67 / RUN-07`
- `.planning/PROJECT.md` line ~86: identical fallback chain description
- `.planning/PROJECT.md` line ~331: identical fallback chain description
- `.planning/ROADMAP.md` line ~37 / line ~51 / line ~137: shim-removal task descriptions
- `.planning/REQUIREMENTS.md` line ~16 / REB-04 / RUN-07: identical chain descriptions

Every retained occurrence is classifiable; no current-state prose claims `sportzal` as the project name in any modified file.

## Deviations from Plan

None. Plan executed exactly as written. No authentication gates, no architectural decisions, no auto-fixes required.

## Known Stubs

None. All edits are content rewrites, not stub data.

## Self-Check

Acceptance grep counts (Task 1):
- `wc -l .planning/HISTORICAL_NOTE.md` → 28 (within 20–35) ✓
- `grep -c 'D-62-09\|D-10-HISTORY-IMMUTABLE' .planning/HISTORICAL_NOTE.md` → 1 (≥1) ✓
- `grep -c 'phases/47-61' .planning/HISTORICAL_NOTE.md` → 2 (≥1) ✓
- `grep -c 'audits' .planning/HISTORICAL_NOTE.md` → 3 (≥1) ✓
- `grep -c 'clubcore' .planning/HISTORICAL_NOTE.md` → 4 (≥3) ✓

Acceptance grep counts (Task 2):
- `grep -c 'clubcore' .planning/PROJECT.md` → 13 (≥5) ✓
- `grep -c 'clubcore' .planning/MILESTONES.md` → 3 (≥2) ✓
- `grep -c 'clubcore' .planning/ROADMAP.md` → 19 (≥5) ✓
- `grep -c 'clubcore' .planning/REQUIREMENTS.md` → 11 (≥5) ✓
- `grep -c 'clubcore' .planning/RETROSPECTIVE.md` → 1 (≥1) ✓
- `grep -c 'clubcore' .planning/STATE.md` → 12 (≥5) ✓
- Total across 6 forward-looking docs: 59 (≥30) ✓

Acceptance grep counts (Task 3):
- `grep -c 'clubcore' CLAUDE.md` → 6 (≥1) ✓
- `grep -c 'clubcore' apps/backend/README.md` → 2 (≥1) ✓
- `grep -c 'clubcore Adminka\|clubcore-adminka' apps/admin-web/CLAUDE.md` → 2 (≥1) ✓
- `grep -c 'clubcore:mock:v2' apps/admin-web/CLAUDE.md` → 1 (≥1) ✓
- `grep -c 'clubcore' apps/admin-web/README.md` → 2 (≥1) ✓

Commits exist:
- `78f7c934` — Task 1 ✓
- `e5e63516` — Task 2 ✓
- `72311631` — Task 3 ✓

Files exist:
- `.planning/HISTORICAL_NOTE.md` ✓
- `.planning/PROJECT.md` ✓
- `.planning/MILESTONES.md` ✓
- `.planning/RETROSPECTIVE.md` ✓
- `CLAUDE.md` ✓
- `apps/backend/README.md` ✓
- `apps/admin-web/CLAUDE.md` ✓
- `apps/admin-web/README.md` ✓

## Self-Check: PASSED

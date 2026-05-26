# Historical Note: sportzal → clubcore Rename

**Created:** 2026-05-26 (Phase 62, v1.10)

## Why grep shows sportzal in .planning/phases/47-61/* and .planning/audits/*

These artefacts are the immutable audit trail of decisions, plans, summaries, and verifications made under the project's previous name `sportzal`. Rewriting them would create commit-message ↔ file-content drift — commits in those phases reference `@sportzal/api-client` and the corresponding file content must continue to say `@sportzal/api-client`. Historical context (decisions, lessons, retrospective discussions) must read as written.

## Active code uses clubcore

All current artefacts — code, configs, OpenAPI, OperatorEnv, and forward-looking docs (`.planning/PROJECT.md`, `MILESTONES.md`, `ROADMAP.md`, `REQUIREMENTS.md`, `STATE.md`, `RETROSPECTIVE.md`, `.planning/handoff/clubcore-*`) — use `clubcore`. The `CLUB_BRAND` placeholder value (gym-name string) is intentionally preserved per D-62-02 and is unrelated to the project-name rename.

## Boundary

| Domain | Treatment |
|--------|-----------|
| `.planning/phases/47-61/**` | Immutable — rename source = sportzal era |
| `.planning/phases/62+/**` | Active — sportzal references = historical-context citations only |
| `.planning/audits/**` | Immutable — audit trail |
| `.planning/handoff/v1.4-*.md` … `v1.9-*.md` | Immutable — operator handoffs from prior milestones |
| `.planning/handoff/clubcore-*` | Active — current naming |
| Top-level forward docs (CLAUDE.md, README.md, apps/*/README.md, docs/*) | Active |
| Code, configs, OpenAPI | Active |

## Lineage

- **D-62-09 / D-10-HISTORY-IMMUTABLE** — forward-only `.planning/` rewrite; historical phase folders + audits + v1.4..v1.9 handoffs are intentionally immutable.
- See `.planning/STATE.md` §"Accumulated Context / Decisions" for full decision rationale.

---
phase: 03-tests-dev-infrastructure-documentation
plan: 04
subsystem: docs
tags: [docs, madr, adr, architecture, conventions, readme, mixed-language]
requires:
  - phase-02 (D-01..D-15: importlinter contracts, factory pattern, lifespan-managed engine, AppError hierarchy, structlog renderer policy, Settings shape)
  - 03-01 (planned conftest.py fixtures referenced from conventions.md ## Testing)
  - 03-05 (planned docker-compose stack referenced from README.md Variant 2 + scripts/)
provides:
  - DOCS-01 (architecture.md — modular monolith reference)
  - DOCS-02 (conventions.md — code style / testing / migrations)
  - DOCS-03 (adr/0001-modular-monolith.md — first ADR + adr/template.md MADR skeleton)
  - DOCS-04 (README.md — two-path quick start)
affects:
  - apps/backend/docs/ (new tree)
  - apps/backend/README.md (new file)
tech-stack:
  added: []
  patterns:
    - "MADR 4.0 ADR section set (D-06)"
    - "Mixed-language doc style (D-05): Russian narrative + English code/identifiers"
    - "Two-path README quick start (D-09): local uv + docker compose, both first-class"
key-files:
  created:
    - apps/backend/docs/architecture.md
    - apps/backend/docs/conventions.md
    - apps/backend/docs/adr/0001-modular-monolith.md
    - apps/backend/docs/adr/template.md
    - apps/backend/README.md
  modified: []
decisions:
  - "D-09 README structure honored verbatim: 3 h2 sections (Quick start / Команды / Документация); no ## Скрипты section — scripts/ linked under Документация instead"
  - "D-12 redis port clarification: appended ' (внутри compose-сети)' to the redis port line in README.md so users don't try to curl redis from host (redis is NOT host-exposed per D-12); D-09 wording otherwise preserved"
  - "MADR 4.0 over Nygard ADR style (D-06) — template.md ships alongside ADR-0001 so future ADRs are one cp away"
  - "Architecture diagram is ASCII-only (D-07 forbids mermaid); diagram description rephrased to avoid the literal token 'mermaid' since acceptance grep is case-insensitive"
metrics:
  duration: 4m 53s
  completed_date: 2026-05-01
  task_count: 4
  file_count: 5
  total_lines: 363
---

# Phase 3 Plan 04: Documentation (architecture / conventions / ADR-0001 / README) Summary

Modular-monolith reference docs delivered: 5 markdown files (363 lines total) covering architecture invariants, code conventions, MADR 4.0 ADR skeleton + first ADR, and a two-path README quick start. All five files honor the mixed-language D-05 rule (Russian narrative, English identifiers/commands) and quote the three `.importlinter` contract names verbatim so docs and enforcement files stay in sync.

## Tasks Completed

| Task | Name | Commit | Files |
|------|------|--------|-------|
| 1 | docs/architecture.md (DOCS-01) | `c8795fc` | apps/backend/docs/architecture.md (90 lines) |
| 2 | docs/conventions.md (DOCS-02) | `83e7888` | apps/backend/docs/conventions.md (98 lines) |
| 3 | docs/adr/0001-modular-monolith.md + adr/template.md (DOCS-03) | `820b8dd` | apps/backend/docs/adr/0001-modular-monolith.md (80 lines), apps/backend/docs/adr/template.md (51 lines) |
| 4 | README.md (DOCS-04) | `1dd8d7a` | apps/backend/README.md (44 lines) |

## What Was Built

### `apps/backend/docs/architecture.md` (DOCS-01, 90 lines)

Five sections per D-07 in mandated order: `## Обзор` → `## Слои` → `## Архитектурные инварианты` → `## Запреты на Phase A` → `## Диаграмма`. The invariants list compresses Phase 2 D-01..D-14 into 8 bullets — all three `.importlinter` contract names (`core-not-depend-on-modules`, `modules-independent`, `integrations-not-depend-on-modules`) appear verbatim, plus factory pattern, lifespan-managed engine, REVERSED middleware add order, exception handler placement, and `/healthz` mount. ASCII diagram included; mermaid avoided per D-07.

### `apps/backend/docs/conventions.md` (DOCS-02, 98 lines)

Seven sections per D-08: `## Naming` → `## Imports` → `## Quality gates` → `## Testing` → `## Logging` → `## Errors` → `## Migrations`. The `## Quality gates` section enumerates all five gates as a table (`uv run ruff check`, `uv run ruff format`, `uv run mypy app`, `uv run lint-imports`, `uv run pytest`) and quotes the three import-linter contracts verbatim with their semantics. The `## Testing` section covers `httpx ASGITransport`, `pytest-asyncio` auto mode, the three fixtures (`app` / `async_client` / `db_session`), and explains why `asgi-lifespan.LifespanManager` is non-removable.

### `apps/backend/docs/adr/0001-modular-monolith.md` (DOCS-03, 80 lines)

MADR 4.0 (D-06): Status `accepted`, Date `2026-05-01`, Deciders `Andre`. Sections: `## Context and Problem Statement` → `## Decision Drivers` → `## Considered Options` (4 options: Modular Monolith chosen vs Microservices / Clean Architecture / Plain Monolith) → `## Decision Outcome` → `### Consequences` → `## Pros and Cons of the Options` (per-option subsections). Decision Outcome enumerates all 3 import-linter contracts; Consequences mention the deferred decisions (no multi-tenancy, no auth, no business tables, ЮKassa-only, Stripe forbidden).

### `apps/backend/docs/adr/template.md` (DOCS-03 bonus, 51 lines)

Identical MADR 4.0 section set, blank placeholders. `# ADR-NNNN:` title slot, status enum line `proposed | accepted | deprecated | superseded by ADR-XXXX`. Future ADRs are one `cp template.md 0002-<slug>.md` away.

### `apps/backend/README.md` (DOCS-04, 44 lines)

D-09 verbatim structure: `# sportzal-backend` → `## Quick start` (with `### Вариант 1: локально (требует внешний Postgres + Redis)` and `### Вариант 2: docker compose (всё включено)`) → `## Команды` (all 5 quality gates + `alembic upgrade head`) → `## Документация` (links to architecture / conventions / adr / adr/template / scripts). Both Quick Start paths first-class — no "advanced" or "recommended" markers (acceptance grep enforces this). Three top-level h2 sections exactly per D-09 LOCKED structure.

## Verification Results

All four tasks' `<automated>` grep batteries passed (no exit-code-1 fallthrough). Final `<verification>` battery:

1. ✅ All 5 files exist at declared paths (`apps/backend/docs/architecture.md`, `docs/conventions.md`, `docs/adr/0001-modular-monolith.md`, `docs/adr/template.md`, `apps/backend/README.md`).
2. ✅ architecture.md has all 5 D-07 sections + 3 contract names + ASCII diagram + zero mermaid mentions.
3. ✅ conventions.md has all 7 D-08 sections + all 5 quality gates via `uv run` + 3 contract names + `ASGITransport` / `asgi-lifespan` / `LifespanManager` / `async_client` / `db_session` / `AppError` references.
4. ✅ ADR-0001 has all MADR 4.0 sections + Status `accepted` + Date `2026-05-01` + Deciders `Andre` + 3 contract names + `ЮKassa`.
5. ✅ template.md has identical MADR 4.0 sections, blank, with `ADR-NNNN` title and the canonical status enum.
6. ✅ README.md has both Quick Start paths first-class + ## Команды + ## Документация (exactly 3 h2 sections per D-09).
7. ✅ `grep -rE '^## (Обзор|Слои|Архитектурные инварианты|Запреты на Phase A|Диаграмма)$' docs/architecture.md` returns exactly 5 lines.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 3 — Blocking] Removed literal `mermaid` token from architecture.md `## Диаграмма` description**
- **Found during:** Task 1 acceptance grep (`! grep -q 'mermaid'` failed; expanded acceptance criterion is `grep -ci 'mermaid'` = 0, case-insensitive).
- **Issue:** Initial draft prose read "markdown viewers неоднородны; mermaid отложен" — referenced the absent technology by name, but the acceptance criterion forbids the substring (case-insensitive) to prevent any latent diagram engine reference from surviving review.
- **Fix:** Rephrased to "markdown viewers неоднородны; графические диаграммы отложены" — same semantic intent, no literal `mermaid` token.
- **Files modified:** `apps/backend/docs/architecture.md` (line 66, in-place via Edit tool).
- **Commit:** Folded into the original Task 1 commit `c8795fc` (fix happened pre-commit).

### Auth Gates

None — documentation-only plan; no external services touched.

## Threat Flags

None — no new security-relevant surface (docs only). Threat register T-03-15..T-03-18 (per plan `<threat_model>`) all dispositioned `mitigate` or `accept`:
- T-03-15 (Information Disclosure / docs leaking secrets) — `cp .env.example .env` referenced; never prints real `SECRET_KEY` / DSN values.
- T-03-16 (Tampering / docs↔enforcement drift) — conventions.md ## Quality gates quotes contract names verbatim from `.importlinter`; static grep verified.
- T-03-17 (Repudiation / ADR-0001) — Status / Date / Deciders metadata explicit per MADR 4.0.
- T-03-18 (Information Disclosure / mixed-language signal) — accepted by D-05.

## Known Stubs

None. All five files contain substantive content (no TODO placeholders that mask missing functionality). The `template.md` `<…>` placeholders are intentional and document themselves as a copy-paste skeleton, not a stub awaiting wiring.

## TDD Gate Compliance

Not applicable — plan type is `execute`, not `tdd`. No RED/GREEN/REFACTOR sequence required.

## Self-Check: PASSED

**Files exist:**
- ✅ `apps/backend/docs/architecture.md` (FOUND, 90 lines)
- ✅ `apps/backend/docs/conventions.md` (FOUND, 98 lines)
- ✅ `apps/backend/docs/adr/0001-modular-monolith.md` (FOUND, 80 lines)
- ✅ `apps/backend/docs/adr/template.md` (FOUND, 51 lines)
- ✅ `apps/backend/README.md` (FOUND, 44 lines)

**Commits exist (verified via `git log --oneline`):**
- ✅ `c8795fc` docs(03-04): add architecture.md (DOCS-01)
- ✅ `83e7888` docs(03-04): add conventions.md (DOCS-02)
- ✅ `820b8dd` docs(03-04): add ADR-0001 + MADR template (DOCS-03)
- ✅ `1dd8d7a` docs(03-04): add README.md (DOCS-04)

All five `must_haves.artifacts` from the plan satisfied (paths, `contains` patterns, `min_lines` floor). All four `must_haves.key_links` satisfied (architecture.md → .importlinter contracts; architecture.md → adr/0001-modular-monolith.md; README.md → docs/architecture.md|conventions.md|adr; conventions.md ## Testing → async_client/db_session fixture references). Plan complete.

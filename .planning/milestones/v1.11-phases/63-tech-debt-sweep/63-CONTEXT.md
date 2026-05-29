# Phase 63: Tech-Debt Sweep - Context

**Gathered:** 2026-05-26
**Status:** Ready for planning

<domain>
## Phase Boundary

Clean the v1.10 tree of pre-existing lint/format/type debt so v1.11 contract-freeze work (Phase 64) has a stable green CI baseline. Plus harden the v1.5 verification runbook so it executes without manual hotfixes.

**In scope:**
- `ruff format` pass tree-wide (~297 files) — one atomic commit
- `ruff check --fix` safe-only pass (158 → 0) — separate atomic commit
- mypy strict cleanup in `apps/backend/app/` (11 → 0) including `auth/models.py __all__` fix — separate atomic commit
- `.planning/milestones/v1.5-verification-evidence/run.sh` hardening (4 known hotfixes + RBAC actor on `POST /trainer-slots` + `X-CSRF-Token` header)
- Verification that all 6 backend CI gates exit 0 on the swept tree

**Out of scope (locked):**
- Any business logic / behavior change
- New `# type: ignore`, `# noqa`, or import-linter `ignore_imports` entries
- `--unsafe-fixes` (PITFALLS C-06)
- Touching frontend (`apps/admin-web`) lint/type state
- Any v1.11 contract-freeze, idempotency, or handoff work (Phases 64/65/66/67)

</domain>

<decisions>
## Implementation Decisions

### Plan Granularity (D-63-01)
- **D-63-01:** Phase 63 is broken into **5 plans, one per atomic commit**:
  - **Plan 1 — DEBT-01:** `uv run ruff format` tree-wide. Pure whitespace; trivially reviewable; `ruff check` exit code unchanged afterwards.
  - **Plan 2 — DEBT-02:** `uv run ruff check --fix app tests` (safe fixes only, no `--unsafe-fixes`). 158 errors → 0.
  - **Plan 3 — DEBT-03:** mypy strict cleanup of `apps/backend/app/` (11 → 0) + `auth/models.py __all__` fix per PITFALLS Pitfall #6. Single commit.
  - **Plan 4 — DEBT-04:** `.planning/milestones/v1.5-verification-evidence/run.sh` hardening with the 4 known hotfixes + RBAC actor fix on `POST /trainer-slots` + `X-CSRF-Token` header; revision-log entry inside the runbook.
  - **Plan 5 — DEBT-05:** Run all 6 CI gates locally to confirm exit 0; capture GitHub Actions CI run URL after the sweep PR lands.
- **Why:** Mirrors the three-commit split mandated by PITFALLS C-07 (single regression → bisectable); each plan = one atomic commit = one reviewable diff. Executor cannot accidentally fuse passes.

### Ordering (D-63-02)
- **D-63-02:** Plans execute strictly serially **1 → 2 → 3 → 4 → 5**. DEBT-04 runs **after** the sweep, not before or in parallel.
- **Why:** Sweep first establishes the clean baseline; runbook hardening (shell + markdown only) lands on already-green tree, keeping sweep commits pure-hygiene and runbook commit semantically separate. No file overlap with sweep targets so executor parallelization buys nothing here — sequential ordering preserves the bisect surface.

### mypy Strict Scope (D-63-03)
- **D-63-03:** Add a `[[tool.mypy.overrides]]` section in `apps/backend/pyproject.toml` for `module = "tests.*"` that disables strict-mode flags (`disallow_untyped_defs = false`, etc.). CI gate stays exactly `uv run mypy --strict app`. A full-tree `uv run mypy app tests` run completes without crashing but is **not** a CI gate.
- **Why:** DEBT-03 scopes the strict pass to `app/` only. The override makes that scoping explicit and version-controlled (no surprise CI changes); residual `tests/` type issues stay deferrable without an out-of-band tracker file. Existing `pyproject.toml [tool.mypy]` block at line 38 + 3 override blocks at lines 43/50/57 make this the natural extension point.

### Verification Evidence (D-63-04)
- **D-63-04:** Plan 5 captures the **GitHub Actions CI run URL** (post-merge) as the DEBT-05 evidence; no local-stdout evidence file is created.
- **Why:** CI is authoritative (matches deployed env, runs all 6 gates in their real configuration); a local re-run could pass while CI fails due to env drift. URL is recorded in the Plan 5 commit message and in `.planning/STATE.md` "Last activity". GH run-log retention (90 days by default) is acceptable for a private commercial repo.
- **Trade-off note for planner:** This diverges from the v1.5/v1.7 verification-evidence file convention. If the URL ever needs long-term archival, planner can add a single `evidence:` line to the Plan 5 commit message capturing exit codes per gate as a permanent fallback (does not require a separate file).

### No `--unsafe-fixes` (D-63-05, restated from milestone)
- **D-63-05:** Every `ruff check --fix` invocation in Phase 63 omits `--unsafe-fixes`. This is the executor's contract — even if a residual ruff error looks trivially auto-fixable with the unsafe pass.
- **Why:** PITFALLS C-06 — the codebase uses Protocol-based cross-module wiring; `ARG001` + unsafe rewrites can strip Protocol-required parameters and break mypy without an obvious diff signal.

### Manual Fix Discipline (D-63-06)
- **D-63-06:** If a residual ruff error after Plan 2 cannot be cleanly fixed in code, the executor must NOT add `# noqa: RULECODE`. Instead, refactor the offending site so the rule passes. The DEBT-05 contract is **zero new `# noqa`** — this is the strict reading.
- **Why:** Sweep purpose is to clear debt, not paper over it. If a real refactor is too large for Plan 3, the residual is escalated to user (becomes a deviation), not silenced.

### Claude's Discretion
- Mypy fix order inside Plan 3 (which of the 11 errors to address first) — planner decides; user has no preference.
- Choice between `ruff format apps/backend` vs `ruff format .` for Plan 1 — planner picks the narrower scope that still satisfies DEBT-01's "whole tree (~297 files)" requirement, considering `apps/admin-web` is JS/TS and out of ruff's scope anyway.
- Newman/Postman files do not exist yet — they're Phase 65 — so ruff scope is purely the Python tree.

</decisions>

<canonical_refs>
## Canonical References

**Downstream agents MUST read these before planning or implementing.**

### Phase Requirements & Milestone Decisions
- `.planning/REQUIREMENTS.md` §"Tech-Debt Sweep (Phase 63 — DEBT-*)" — DEBT-01..05 with locked counts, commit ordering, exclusion list
- `.planning/ROADMAP.md` §"Phase 63: Tech-Debt Sweep" — goal, depends-on (Phase 62.1), 5 success criteria

### Pitfalls (MUST READ before planning)
- `.planning/research/PITFALLS.md` §Pitfall C-06 — Never use `--unsafe-fixes`; safe-only sweep order; Protocol-arg stripping risk
- `.planning/research/PITFALLS.md` §Pitfall C-07 — Three-commit split rationale (bisect surface)
- (referenced by DEBT-03) PITFALLS Pitfall #6 — `auth/models.py __all__` fix inside mypy cleanup

### Runbook to Harden (DEBT-04 target)
- `.planning/milestones/v1.5-verification-evidence/run.sh` — file being hardened; 4 known hotfixes (Alembic 32-char limit, `/healthz` not `/health`, `trainer_availability_slots` not `trainer_slots`, `verify_*@local.dev` fixture user defaults) + RBAC actor fix on `POST /trainer-slots` + missing `X-CSRF-Token` header

### Tool Config (DEBT-03 target for mypy override)
- `apps/backend/pyproject.toml` §`[tool.mypy]` (line 38) + existing override blocks (lines 43, 50, 57) — extension point for the new `tests.*` override per D-63-03
- `apps/backend/ruff.toml` — existing ruff config (do NOT add new ignores)

### CI Gates (DEBT-05 surface)
- `.github/workflows/ci.yml` — defines the 6 gates that must exit 0: ruff check + ruff format check + mypy --strict app + import-linter + openapi.json drift + export_openapi

### Project Constraints
- `CLAUDE.md` §Constraints — tooling baseline (ruff + mypy strict + import-linter mandatory)
- `.planning/PROJECT.md` — milestone scope and v1.11 framing

</canonical_refs>

<code_context>
## Existing Code Insights

### Reusable Assets
- Existing `pyproject.toml [tool.mypy]` block (line 38) with 3 override sections — the `tests.*` override (D-63-03) plugs into this established pattern, not a new file.
- `apps/backend/ruff.toml` already configured — no new ignores added; sweep operates within current ruleset.

### Established Patterns
- Three v1.6-era + v1.4-residual code accretion is in `apps/backend/app/` only — frontend (`apps/admin-web`) is out of scope (separate toolchain).
- v1.5 verification-evidence run scripts use bash + curl; runbook hotfixes are localized find-and-replace edits, not architectural changes.
- Prior milestones (v1.7, v1.8) followed verification-evidence-file convention; D-63-04 explicitly diverges from that to the CI-URL approach.

### Integration Points
- Plan 2 (ruff safe-fix) may surface side-effects in Plan 1 (format) diff — if a formatter-induced line goes over E501 limit, fix it inside Plan 2's commit, not by amending Plan 1.
- Plan 3 mypy cleanup may touch the same files Plans 1+2 reformatted — that's expected; mypy edits are semantic and review-distinct from whitespace/safe-fix edits already merged.
- Plan 4 runbook lives in `.planning/milestones/v1.5-verification-evidence/` — zero overlap with `apps/backend/app/`, no risk of accidental sweep interference.

</code_context>

<specifics>
## Specific Ideas

- 158 ruff errors break down to ~80 auto-fixable safely (RUF100, F401, I001) and ~78 manual (E501, RUF002 Cyrillic-in-docstring, RUF059 unused vars) per PITFALLS C-06. Plan 2 handles the 80; Plan 3 handles the 78 alongside mypy.
- The `auth/models.py __all__` fix is a single-symbol export adjustment per PITFALLS Pitfall #6 — atomic with the mypy fixes in Plan 3.
- DEBT-04's 4 hotfixes are line-level find-and-replace; the RBAC actor fix on `POST /trainer-slots` and the missing `X-CSRF-Token` header are also localized edits.

</specifics>

<deferred>
## Deferred Ideas

- Local-stdout verification-evidence file (alternative to D-63-04) — not adopted; CI URL is the chosen evidence channel. Can revisit in v1.12+ if GH run-log retention becomes an issue.
- Parallelizing Plan 4 (runbook) with Plans 1-3 — rejected per D-63-02 to keep history strictly serial; revisit only if Phase 63 wall-clock becomes a bottleneck (it won't).
- Frontend (`apps/admin-web`) lint/type cleanup — out of scope; separate toolchain (ESLint + tsc), no v1.11 driver to clean it now.

</deferred>

---

*Phase: 63-tech-debt-sweep*
*Context gathered: 2026-05-26*

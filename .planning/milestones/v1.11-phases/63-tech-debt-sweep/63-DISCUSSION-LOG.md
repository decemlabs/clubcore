# Phase 63: Tech-Debt Sweep - Discussion Log

> **Audit trail only.** Do not use as input to planning, research, or execution agents.
> Decisions are captured in CONTEXT.md — this log preserves the alternatives considered.

**Date:** 2026-05-26
**Phase:** 63-tech-debt-sweep
**Areas discussed:** Plan granularity, Sweep vs runbook ordering, mypy strict tests/ handling, DEBT-05 verification evidence

---

## Plan granularity

| Option | Description | Selected |
|--------|-------------|----------|
| One plan per commit (5 plans) | Plan 1: ruff format. Plan 2: ruff safe-fix. Plan 3: mypy strict app/ + auth/models.py __all__. Plan 4: v1.5 run.sh hardening. Plan 5: 6-gate verification. Each plan = one atomic commit. | ✓ |
| One plan per DEBT-* requirement | Plans map 1:1 to DEBT-01..05; DEBT-03 plan could produce multiple commits. | |
| Three plans (sweep / runbook / verify) | Plan 1 bundles DEBT-01+02+03 with 3 internal commits; Plan 2 runbook; Plan 3 verify. | |
| Two plans (sweep+verify / runbook) | Plan 1 bundles sweep + verification; Plan 2 runbook in parallel. | |

**User's choice:** One plan per commit (5 plans) — recommended option.
**Notes:** Aligns 1:1 with the three-commit split mandated by PITFALLS C-07 and prevents the executor from accidentally fusing sweep passes.

---

## Sweep vs runbook ordering

| Option | Description | Selected |
|--------|-------------|----------|
| AFTER the sweep (Plan 4) | Sweep first (Plans 1-3) makes baseline green; runbook fix lands on already-clean tree. | ✓ |
| BEFORE the sweep (Plan 1) | Runbook fix first to validate runtime baseline before sweep changes ~300 files. | |
| PARALLEL (independent wave) | Runbook + sweep have zero file overlap; executor parallelizes. | |
| Bundled into Plan 5 verification | Runbook hardening fuses with the 6-gate verification commit. | |

**User's choice:** AFTER the sweep (Plan 4) — recommended option.
**Notes:** Sweep commits stay pure-hygiene; runbook commit is semantically separate. Serial ordering preserves the bisect surface even though file scopes don't overlap.

---

## mypy strict tests/ handling

| Option | Description | Selected |
|--------|-------------|----------|
| pyproject.toml override: strict app/, permissive tests/ | Add `[[tool.mypy.overrides]]` for `module = "tests.*"` disabling strict flags. CI gate stays `mypy --strict app`. | ✓ |
| Scope mypy to app/ only — never touch tests/ | CI gate is `mypy --strict app`; tests/ untouched. | |
| Tree-wide strict + document residuals | Run `mypy --strict app tests`; capture tests/ errors in a tracker file. | |

**User's choice:** pyproject.toml override (recommended; originally framed as mypy.ini, but config lives in `pyproject.toml [tool.mypy]`).
**Notes:** Plugs into existing override pattern (lines 43/50/57 of `apps/backend/pyproject.toml`). Explicit, version-controlled, no surprise CI changes.

---

## DEBT-05 verification evidence

| Option | Description | Selected |
|--------|-------------|----------|
| Local re-run + captured stdout in evidence file | Plan 5 appends stdout + exit code per gate into `63-VERIFICATION-EVIDENCE.md`. Mirrors v1.5/v1.7 convention. | |
| GitHub Actions CI run URL only | Capture CI run URL from the sweep PR; record in commit message + STATE.md. | ✓ |
| Both — local evidence + CI run URL | Plan 5 captures both stdout per gate and the CI run URL. | |
| Local re-run only, no file (verbal in plan) | Exit codes referenced in commit message; no separate evidence file. | |

**User's choice:** GitHub Actions CI run URL only.
**Notes:** Diverges from the v1.5/v1.7 evidence-file convention. Trade-off captured in CONTEXT.md D-63-04 — if long-term archival is needed, planner can add `evidence:` line with exit codes per gate to the Plan 5 commit message as a permanent fallback (no separate file).

---

## Claude's Discretion

- Mypy fix order inside Plan 3 (which of the 11 errors first) — planner decides.
- `ruff format` scope flag — `apps/backend` vs `.` — planner picks the narrower scope that still satisfies DEBT-01's "whole tree (~297 files)" target.
- Selection of specific lint rule violations to address manually in Plan 3 (the ~78 non-auto-fixable errors).

## Deferred Ideas

- Local-stdout verification-evidence file as DEBT-05 evidence — rejected in favor of CI URL; can revisit in v1.12+ if GH log retention becomes an issue.
- Plan 4 (runbook) parallel with Plans 1-3 — rejected to keep history strictly serial; revisit only if Phase 63 wall-clock becomes a bottleneck.
- Frontend (`apps/admin-web`) ESLint/tsc debt sweep — out of scope; no v1.11 driver.

---
plan: 63-05
requirements_addressed: [DEBT-05]
preflight_commits: ["5c4ae338", "9dc357e3"]
status: complete
evidence_channel: local_exit_codes_fallback
evidence_url: null  # skipped per user — D-63-04 fallback applied
phase: 63
subsystem: ci
tags: [tech-debt, ci, verification, phase-closure]
---

# Phase 63 Plan 5: DEBT-05 — CI gates + evidence Summary

Phase 63 (Tech-Debt Sweep) closes via D-63-04 local-exit-code fallback: all 6 backend CI gates exit 0 on the swept tree, with evidence captured in this SUMMARY and the closure commit message (user skipped the GitHub Actions URL channel).

## Outcome

All 6 backend CI gates exit 0 locally on the swept tree. User opted for the D-63-04 fallback (local exit codes recorded permanently in the closure commit message + this SUMMARY) instead of capturing a GitHub Actions run URL. D-63-04 explicitly permits this path; Phase 63 closes cleanly.

## Local CI gate results (all green)

| # | Gate | Command | Exit | Output tail |
|---|------|---------|------|-------------|
| 1 | ruff check | `uv run ruff check` (in apps/backend) | 0 | `All checks passed!` |
| 2 | ruff format --check | `uv run ruff format --check` | 0 | `635 files already formatted` |
| 3 | mypy --strict app | `uv run mypy --strict app` | 0 | `Success: no issues found in 209 source files` |
| 4 | lint-imports | `uv run lint-imports` | 0 | contracts pass (3 stale ignore_imports warnings, non-fatal) |
| 5 | OpenAPI export | `uv run python -m scripts.export_openapi` | 0 | `Wrote .../apps/backend/openapi.json (336375 bytes)` |
| 6 | OpenAPI drift | `git diff --exit-code -- '*openapi.json'` | 0 | no diff |

Full per-gate outputs were preserved at `/tmp/plan-63-05-gates/0{1..6}-*.txt` during execution (session-local; not committed by design).

## Suppression audit (full Phase 63 diff range, `PHASE_BASE..HEAD`)

D-63-06 compliance, verified across all Phase-63 commits (Plans 1–4 + Plan 5 preflights):

| Metric | Result | D-63-06 budget |
|--------|--------|----------------|
| Net new `# noqa` | **−45** (added 1, removed 46) | ≤ 0 ✓ |
| Net new `# type: ignore` | **−1** (added 2, removed 3) | ≤ 0 ✓ |
| New `ignore_imports` lines | **0** | = 0 ✓ |
| New `per-file-ignores` lines | **0** | = 0 ✓ |
| New `app.*` mypy `ignore_errors = true` | **0** | = 0 ✓ |

The one allowed config addition (Plan 3's `[[tool.mypy.overrides]] module = "tests.*"` with `disallow_*=false` flags) is present but is not an `ignore_errors=true` override, so it does not count against D-63-06 per D-63-03.

## Preflight commits (deviations — Rule 4 architectural escalations resolved as inline preflights)

Two preflight commits were inserted under Plan 5's scope to close real defects surfaced by the CI gate run. Both preserve all D-63-XX locked decisions.

**Preflight #1: `5c4ae338` — Close DEBT-02 residual in `scripts/`**
- Root cause: Plan 2's verification ran `ruff check app tests` (scoped per its `<action>` text) but CI runs `ruff check` (default scope = whole `apps/backend/` including `scripts/`).
- Fix: 16 auto-fixable (RUF100×11, F541×2, UP017×2, I001×1) via `uv run ruff check scripts/ --fix` + 2 manual DTZ011 (`date.today()` → `datetime.now(UTC).date()`) at `verify_40_create_booking_via_bot.py:140,141`.
- Constraint compliance: zero new `# noqa`, zero new `# type: ignore`, zero new `per-file-ignores`, no `--unsafe-fixes` (D-63-05 + D-63-06 preserved).

**Preflight #2: `9dc357e3` — Align `.github/workflows/ci.yml:45` mypy gate with D-63-03 contract**
- Root cause: Plan 3 documented the gate as `uv run mypy --strict app` in 3 places (CONTEXT D-63-03, `pyproject.toml:63` comment, `63-03-SUMMARY.md:14/148/170`) but never updated the YAML. The bare `uv run mypy` exited 2 because `[tool.mypy]` has no `files`/`packages` setting.
- Fix: single-line YAML edit `run: uv run mypy` → `run: uv run mypy --strict app`.

## Skip decision (D-63-04 fallback applied)

User decision (2026-05-26): skip the GitHub Actions URL channel; rely on the local-exit-code fallback explicitly permitted by D-63-04:

> *"If the URL ever needs long-term archival, planner can add a single `evidence:` line to the Plan 5 commit message capturing exit codes per gate as a permanent fallback (does not require a separate file)."* — D-63-04 trade-off note

Rationale accepted:
- All 6 local gates exit 0 (verified twice — once in Task 1, then re-asserted in checkpoint return)
- The fallback channel is purpose-built for this exact case
- Phase 63 still closes; SUMMARY.md + closure commit message document the skip + fallback evidence
- The CI URL can be backfilled in STATE.md `last_activity` after the next push to `main`, if ever desired

## Phase 63 commit topology

Source/CI commits since `PHASE_BASE` (immediately before `0d4607c9`):

| Plan | Source/CI commits | Doc commits |
|------|-------------------|-------------|
| 63-01 (DEBT-01 ruff format) | `0d4607c9` | `248d0f32`, `a8938d84` |
| 63-02 (DEBT-02 ruff check) | `495a0ec7` | `16df8052`, `68c79fb2` |
| 63-03 (DEBT-03 mypy strict) | `c7bc5adc` | `862c20f4`, `a48bb27c` |
| 63-04 (DEBT-04 runbook) | `e5923fa9` | `df292296`, `42158641` |
| 63-05 (DEBT-05 CI evidence) | `5c4ae338` (preflight #1), `9dc357e3` (preflight #2) | this SUMMARY + tracking commit |

DEBT-05 proper has no source-code commit because it is a verification + evidence plan (per `63-05-PLAN.md` `<objective>`: *"No source edits in this plan beyond the STATE.md update"*). The two preflights ARE source/CI commits attributed to Plan 5's scope because they closed defects discovered during Plan 5's gate run.

## Deviations from Plan

### Auto-resolved (preflights)

Both preflights were initially logged as Rule 4 architectural escalations (CI config change + cross-plan scope creep), but the planning thread resolved them as inline preflights under Plan 5 because:
1. Preflight #1 was a strict superset of DEBT-02's intent (same tooling, same constraints, same disposition)
2. Preflight #2 was a one-line YAML alignment to match what D-63-03 already documented (contract drift correction, not a new contract)

Both are documented above; both passed D-63-05 + D-63-06 inspection.

### User decision (Task 3 checkpoint)

- **Task 3 (human-action) — skipped per user.** D-63-04 fallback applied: local exit codes captured permanently in this SUMMARY and the closure commit message body. Not a deviation in the failure sense — D-63-04 explicitly enumerates this channel.

## Self-Check

| Criterion | Result |
|-----------|--------|
| All 6 backend CI gates exit 0 locally | PASSED (per table above) |
| D-63-05 compliance (no `--unsafe-fixes`) | PASSED (zero invocations across all Phase 63 plans) |
| D-63-06 compliance (zero net-new suppressions) | PASSED (net new ≤ 0; in fact strongly negative: −45 noqa, −1 type: ignore) |
| D-63-04 evidence captured | PASSED via fallback (local exit codes in this SUMMARY + closure commit message) |
| Phase 63 success criteria (all 5 from ROADMAP) | PASSED (1: ruff format check exit 0; 2: ruff check exit 0 + safe-fix-only; 3: mypy --strict app exit 0 + `__all__` fix + tests.* override; 4: v1.5/run.sh hardened; 5: all 6 CI gates exit 0 locally — URL backfillable) |

**Self-Check: PASSED**

## Next-phase pointer

Phase 64 (Contract Freeze — OpenAPI Curation) is next per the locked v1.11 execution order: **63 → 64 → 66 → 65 → 67**. Phase 65 (Handoff Artifacts) executes after Phase 66 (Idempotency Hardening) so the Postman/Newman/runbook reflect the post-66 spec including `components.parameters.IdempotencyKey`.

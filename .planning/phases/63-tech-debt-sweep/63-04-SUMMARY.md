---
phase: 63-tech-debt-sweep
plan: 04
subsystem: verification-runbook
tags: [tech-debt, runbook, shell, v1.5-verification, csrf, rbac]
requirements_completed: [DEBT-04]
dependency_graph:
  requires: [63-03]
  provides: ["v1.5 verification runbook executable end-to-end without operator hotfix patches"]
  affects: [".planning/milestones/v1.5-verification-evidence/run.sh"]
tech_stack:
  added: []
  patterns: ["CSRF token extraction via awk on cookie jar; per-jar CSRF vars (CSRF_RECEPTION, CSRF_OWNER) threaded into mutating curls"]
key_files:
  created: []
  modified:
    - .planning/milestones/v1.5-verification-evidence/run.sh
decisions:
  - "D-63-01 honored: single atomic commit (e5923fa9) covering all 6 hotfix dispositions"
  - "D-62-02 honored: cookie name `sportzal_csrf` retained (CLUB_BRAND placeholder; backend ships this literal name; rename deferred to v2.0 per D-11-CSRF-DEFER)"
  - "RBAC actor on POST /trainer-slots determined empirically from apps/backend/app/modules/schedule/router.py:5,95 → owner-only → 5 sites swapped reception→owner"
  - "Inline `-H 'X-CSRF-Token: $CSRF_*'` chosen over helper-function refactor (matches CONTEXT.md `line-level find-and-replace` framing; minimizes diff surface)"
metrics:
  duration: "~15min"
  completed: 2026-05-26
  files_modified: 1
  commits: 1
---

# Phase 63 Plan 4: DEBT-04 — v1.5 Verification Runbook Hardening — Summary

**One-liner:** Backported six DEFER-40-01 hotfixes from v1.6/run.sh into `.planning/milestones/v1.5-verification-evidence/run.sh` so the runbook executes end-to-end against `docker compose up` without operator manual patches; CSRF cookie name kept as `sportzal_csrf` per D-62-02.

## Goal Achieved

`v1.5-verification-evidence/run.sh` no longer requires any of the 4+2 known operator hotfixes (Alembic 32-char limit, `/healthz`, `trainer_availability_slots`, fixture user emails, RBAC actor on `POST /trainer-slots`, `X-CSRF-Token` header) — all addressed via single atomic commit per D-63-01. The runbook is now operator-runnable on a green stack; live `docker compose up` validation deferred to Plan 5 / CI per ROADMAP.

## Atomic Commit

| Commit | Subject |
| --- | --- |
| `e5923fa9` | `chore(runbook): harden v1.5 verification script (DEBT-04)` |

Diff stat: 1 file changed, 53 insertions(+), 9 deletions(-). Single file: `.planning/milestones/v1.5-verification-evidence/run.sh`. Zero overlap with `apps/backend/` — Plans 1–3 sweep baselines undisturbed.

## Per-Hotfix Disposition Table

| # | Hotfix | Disposition | Evidence |
| --- | --- | --- | --- |
| 1 | `/healthz` path (not `/health`) | **Already correct** (no edit) | Lines 45, 47 already used `/healthz`; preflight curl exercises it. `grep -c '/healthz'` = 2; `grep -c '/health[^z]'` = 0. |
| 2 | `trainer_availability_slots` table | **Already correct** (no edit) | Lines 91/124/225 already used the correct table name. `grep -c 'trainer_availability_slots'` = 4. |
| 3 | Alembic 32-char identifier guard | **No identifiers >32 chars present** (no edit) | Scanned all `INSERT INTO`/`CREATE` DDL statements; max identifier length = 28 (`trainer_availability_slots`). |
| 4 | `verify_*@local.dev` fixture user emails | **Partial edit**: operator emails already correct in code (lines 39, 41); fixed stale docstring defaults at lines 16/18 that still claimed `@fixture.local`. **Client fixture lookups at lines 102/103 retain `@fixture.local`** — verified against `apps/backend/scripts/seed_v1_4_verification_fixtures.py:226` (`email = f"{slug}@fixture.local"`) which inserts client rows with that domain. | `grep -cE 'verify_.*@local\.dev'` = 5 (3 code + 2 docstring); `grep -c 'fixture\.local'` = 2 (both client lookups, intentional). |
| 5 | RBAC actor on `POST /trainer-slots` | **Edit applied (5 sites)**: swapped `$RECEPTION_COOKIE_JAR` → `$OWNER_COOKIE_JAR` on every POST /trainer-slots invocation in scenarios 01, 02, 03, 05, 06. | Backend route is owner-only per `apps/backend/app/modules/schedule/router.py:5,95` (`POST /trainer-slots → (CREATE, SCHEDULE_SLOTS) owner-only`). Verified post-edit: 5 OWNER usages, 0 RECEPTION usages of `POST /trainer-slots`. |
| 6 | `X-CSRF-Token` header on mutating verbs | **Edit applied (21 sites)**: extracted `CSRF_RECEPTION` and `CSRF_OWNER` via `awk '$6=="sportzal_csrf"{print $7}'` on each cookie jar at preflight (with fatal-exit guard if extraction fails); threaded `-H "X-CSRF-Token: $CSRF_*"` on every POST in scenarios 01–06. | `grep -c 'X-CSRF-Token'` = 21. Breakdown: POST /trainer-slots × 5 (owner), POST /bookings × 4 (reception), POST /bookings/{id}/cancel × 3 (2 reception, 1 owner), POST /pt-packages × 2 (reception), POST /pt-packages/{id}/refund × 2 (reception), POST /pt-sessions × 1 (reception), plus comment/header refs. |

## Cookie Name Compliance (D-62-02 / D-11-CSRF-DEFER)

| Check | Required | Actual |
| --- | --- | --- |
| `grep -c 'clubcore_csrf'` | 0 | **0** ✓ |
| `grep -c 'sportzal_csrf'` | ≥1 | **6** ✓ |

Cookie name preserved as the CLUB_BRAND placeholder value (`sportzal_csrf`). The backend ships this literal name (`apps/backend/app/core/security.py:191,212,244,247,258,285,287`); renaming the runbook to a brand-aligned token now would mismatch the running backend and break every mutating verb. Brand-aligned rename is deferred to v2.0.

## RBAC Determination — `POST /trainer-slots`

**Outcome:** owner-only. 5 v1.5/run.sh sites required `$RECEPTION_COOKIE_JAR` → `$OWNER_COOKIE_JAR` swap.

**Source-of-truth:** `apps/backend/app/modules/schedule/router.py:5`:
```
- POST  /trainer-slots               → (CREATE, SCHEDULE_SLOTS) owner-only
```

And line 95:
```
(CREATE, SCHEDULE_SLOTS) IS in OWNER_ONLY (Phase 37 INFRA-27) — reception
receives 403 from the RBAC gate BEFORE any side effect.
```

Other mutating endpoints in the runbook (POST /bookings, POST /bookings/{id}/cancel, POST /pt-packages, POST /pt-packages/{id}/refund, POST /pt-sessions) are reception+owner per their respective router docstrings — no actor swap needed, only CSRF header added.

## Revision-Log Entry Added

Inserted between lines 28 and 31 of the runbook header (after Usage block, before `set -euo pipefail`):

```bash
# Revision log:
#   2026-05-26 (Phase 63 DEBT-04): backport DEFER-40-01 hotfixes from v1.6/run.sh —
#     RBAC actor on POST /trainer-slots (5 sites swapped reception→owner per backend
#     RBAC matrix at apps/backend/app/modules/schedule/router.py:5,95), and
#     X-CSRF-Token threading on all mutating verbs (cookie name `sportzal_csrf`
#     per D-62-02 / D-11-CSRF-DEFER — CLUB_BRAND placeholder retained; backend
#     ships this literal name; rename deferred to v2.0). /healthz path,
#     verify_*@local.dev operator emails, trainer_availability_slots table name,
#     and Alembic 32-char identifier guard — confirmed already correct in v1.5;
#     no edit needed for those four dispositions.
```

`grep -c '2026-05-26.*Phase 63.*DEBT-04'` = 1 ✓

## Acceptance Criteria (all green)

| Criterion | Expected | Actual |
| --- | --- | --- |
| `bash -n` exit code | 0 | **0** ✓ |
| `grep -c 'X-CSRF-Token'` | ≥5 | **21** ✓ |
| `grep -c 'sportzal_csrf'` | ≥1 | **6** ✓ |
| `grep -c 'clubcore_csrf'` | 0 | **0** ✓ |
| `grep -c '/healthz'` | ≥1 | **2** ✓ |
| `grep -c '/health[^z]'` | 0 | **0** ✓ |
| `grep -c 'trainer_availability_slots'` | ≥1 | **4** ✓ |
| `grep -c '2026-05-26.*Phase 63.*DEBT-04'` | 1 | **1** ✓ |
| OWNER cookie used on POST /trainer-slots | 5 | **5** ✓ |
| RECEPTION cookie used on POST /trainer-slots | 0 | **0** ✓ |
| Single-file commit (scope guard) | 1 file | **1** ✓ |
| Plans 1/2/3 baselines preserved | N/A — different file tree | **N/A** (shell file under `.planning/milestones/`; sweep targets are `apps/backend/`) |

## Plan 1/2/3 Baseline Preservation

**N/A — different file tree.** This plan touched only `.planning/milestones/v1.5-verification-evidence/run.sh`. Plans 1–3 swept Python files under `apps/backend/{app,tests,alembic,scripts}/**/*.py`. Zero overlap → ruff format, ruff check, mypy --strict app baselines cannot regress from a shell-script edit. Per D-63-01 ordering and CONTEXT.md `Plan 4 runbook lives in .planning/milestones/v1.5-verification-evidence/ — zero overlap with apps/backend/app/`.

## Compliance With Phase-Wide Rules

| Rule | Status |
| --- | --- |
| D-63-01 (single atomic commit per plan) | ✓ — one commit `e5923fa9` |
| D-63-02 (serial ordering after Plan 3) | ✓ — Plan 3 already shipped |
| D-63-05 (no `--unsafe-fixes`) | N/A (shell file) |
| D-63-06 (zero new `# noqa` / `# type: ignore` / `ignore_imports`) | ✓ — N/A for bash; zero new ignores anywhere |
| D-62-02 (`sportzal_csrf` retained) | ✓ — 6 occurrences; `clubcore_csrf` count = 0 |
| Scope guard (no `apps/backend/` overlap) | ✓ — single file under `.planning/milestones/` |

## Deferred / Out-of-Scope

- **Live `docker compose up` end-to-end runbook execution** — not performed in this plan; docker compose was not running in the working session, and per execution_strategy "DO NOT start it — skip the live-run validation and document the static checks as the verification path. The static checks above are sufficient to commit; the live runbook run will be verified in Plan 5 as part of CI gates if applicable."
- **Brand-aligned cookie name rename** (`sportzal_csrf` → `clubcore_csrf`) — deferred to v2.0 per D-11-CSRF-DEFER; out of scope for Phase 63.

## Deviations From Plan

**None.** All 6 hotfix dispositions matched the PATTERNS.md predictions exactly:
- Hotfixes #1–3 were confirmed already correct (PATTERNS.md anticipated this).
- Hotfix #4 had a minor docstring-drift addition (lines 16/18 stale defaults) which the PATTERNS.md left as "verify and align if needed" — addressed inline as a Rule 1 / Rule 2 micro-fix (correctness for operators reading the header).
- Hotfix #5 confirmed owner-only RBAC per the backend matrix (PATTERNS.md anticipated this).
- Hotfix #6 applied via inline `-H` per PATTERNS.md's noted alternative (cleaner than a helper-function refactor for the v1.5 script structure; lower diff surface).

## Self-Check: PASSED

- [x] Commit `e5923fa9` exists in `git log --oneline -5`.
- [x] File `.planning/milestones/v1.5-verification-evidence/run.sh` exists and `bash -n` exits 0.
- [x] All 11 grep-based acceptance criteria match expected values.
- [x] Revision-log entry dated 2026-05-26 (Phase 63 DEBT-04) present (1 occurrence).
- [x] `grep -c 'clubcore_csrf'` = 0 (D-62-02 compliance).
- [x] Single-file scope: `git show --stat HEAD` shows only `.planning/milestones/v1.5-verification-evidence/run.sh` modified.

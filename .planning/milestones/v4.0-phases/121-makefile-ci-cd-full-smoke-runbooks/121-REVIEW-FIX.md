---
phase: 121-makefile-ci-cd-full-smoke-runbooks
fixed_at: 2026-06-16T00:00:00Z
review_path: .planning/phases/121-makefile-ci-cd-full-smoke-runbooks/121-REVIEW.md
iteration: 1
findings_in_scope: 5
fixed: 5
skipped: 0
status: all_fixed
---

# Phase 121: Code Review Fix Report

**Fixed at:** 2026-06-16
**Source review:** .planning/phases/121-makefile-ci-cd-full-smoke-runbooks/121-REVIEW.md
**Iteration:** 1

**Summary:**
- Findings in scope: 5 (all Warnings; 6 Info findings out of scope under `critical_warning`)
- Fixed: 5
- Skipped: 0

All fixes were authored and committed inside an isolated git worktree on branch
`gsd-reviewfix/121-74571`, then fast-forwarded onto `master`. Verification was
syntax-level only (`bash -n`, `make -n` dry-parse, GNU Make 3.81 target-specific
export probe) — no live k3d/helm/trivy run was possible or fabricated
(D-V40-LOCAL-VALIDATE honored). Live PASS remains operator-pending.

## Fixed Issues

### WR-01 / WR-02: `set -e` abort risk + ingress DNS addressing in smoke.sh

**Files modified:** `infra/scripts/smoke.sh`
**Commit:** `60936b42`
**Applied fix:**
- **WR-01** — Added a `run_check()` dispatch wrapper (`run_check() { "$@" || true; }`)
  and routed all 8 check calls in `main` through it. Failures are still recorded via
  the existing `fail()` helper (which increments `SMOKE_FAILURES`), so swallowing each
  check function's exit status guarantees every check runs and the PASS/FAIL summary
  banner is always reached under `set -euo pipefail`. The final exit status still
  reflects `SMOKE_FAILURES`, not an incidental `set -e` trip. `set -euo pipefail` and
  the existing `log`/`ok`/`fail` helpers + banner are preserved.
- **WR-02** — Added overridable `INGRESS_IP` (default `127.0.0.1`) and `INGRESS_PORT`
  (default `80`) script variables for the k3d loadbalancer→localhost port map. Checks
  6 (WebSocket), 7 (SPA fallback), and 8 (sw.js + /api/* cache) now use
  `curl --resolve "<host>:<port>:<ip>"` and target `http://<host>:<port>...` so curl
  reaches Traefik via the ingress endpoint while the URL authority still carries the
  `*.clubcore.local` vhost for Host-based routing. This removes the false-negative
  `000`/could-not-resolve failure mode and lets the checks PASS on a correctly-deployed
  k3d without manual `/etc/hosts` edits. The redundant `-H Host:` on check 7 was
  dropped (the authority now carries the vhost).

**Note on commit grouping:** WR-01 and WR-02 edits are interleaved in the same file
(`smoke.sh`) and could not be cleanly separated into two non-overlapping commits
without risking a HEAD that contained only one fix. Per the explicit linearity
instruction ("stack those edits so HEAD contains both"), they were committed together
in a single atomic commit so HEAD reliably contains both fixes.

### WR-03: `make up` double-smoke

**Files modified:** `Makefile`, `infra/scripts/deploy-local.sh`
**Commit:** `4bcbe378`
**Applied fix:** Chose option (b) from the review. Added a `SKIP_INLINE_SMOKE`
(default `0`) env guard to `deploy-local.sh`: when set to `1`, section 6's inline
5-check smoke is skipped (deploy is already complete after `helm install --wait`) and
the script exits 0, deferring to the dedicated standalone smoke. The Makefile `up`
target now sets `up: export SKIP_INLINE_SMOKE := 1` — a GNU Make target-specific
export that propagates to the `deploy` prerequisite recipe (verified via a Make 3.81
probe). Result: `make up` runs `build→scan→tf-validate→helm-lint→deploy→smoke` with the
authoritative 8-check `smoke.sh` running exactly once and no duplicate banner.
Standalone `make deploy` / `bash deploy-local.sh` (no env) keep the inline smoke
unchanged; `make smoke` standalone is unaffected.

### WR-04: Makefile `TAG` missing `-dirty` suffix

**Files modified:** `Makefile`
**Commit:** `92b78323`
**Applied fix:** Replaced `TAG ?= $(shell git rev-parse --short HEAD)` with a derivation
that mirrors `build-images.sh` / `deploy-local.sh` exactly:
`TAG ?= $(shell t=$$(git rev-parse --short HEAD); if ! git diff --quiet || ! git diff --cached --quiet; then t="$$t-dirty"; fi; echo "$$t")`.
Verified with `make -n push` on the dirty worktree — it now emits
`clubcore/backend:<sha>-dirty`, matching what `build-images.sh` produces, so a manual
`make push`/`make helm-lint`/`make helm-validate` in a dirty tree references a tag that
actually exists. The header comment was updated to document the parity requirement.

### WR-05: Runbook `kubectl logs deploy/...` rows ignore `alembic-check` container

**Files modified:** `infra/runbooks/production.md`
**Commit:** `1ca1f1c1`
**Applied fix:** Updated the backend CrashLoop troubleshooting row to point operators
at `kubectl logs deploy/clubcore-backend -c alembic-check` (init guard) then
`-c backend` (app), consistent with the `alembic-check` initContainer referenced at
the 118-4 row. Added a note that `kubectl logs deploy/...` without `-c` selects a single
pod's default container only, and to use `--all-containers` when the failing container
is unknown. Also annotated the telegram-bot row with the single-pod caveat and
`--previous` for crashed instances. Doc-only consistency fix.

## Skipped Issues

None — all 5 in-scope Warnings were fixed.

The 6 Info findings (IN-01 … IN-06) are out of scope under the `critical_warning`
fix scope and were not addressed in this iteration. Rationale: scope was restricted to
Critical + Warning findings; the Info items are low-impact robustness/wording nits
(`/api/v1/ping` endpoint existence, WS key RFC conformance, unused `REPO_ROOT`, help
regex edge case, smoke-count doc wording, Job condition terminology) that the operator
can address during a follow-up `--fix all` pass or live verification.

---

_Fixed: 2026-06-16_
_Fixer: Claude (gsd-code-fixer)_
_Iteration: 1_

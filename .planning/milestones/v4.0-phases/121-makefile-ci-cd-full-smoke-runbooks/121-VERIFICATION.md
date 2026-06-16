---
phase: 121-makefile-ci-cd-full-smoke-runbooks
verified: 2026-06-16T00:00:00Z
status: human_needed
score: 3/3 static must-haves verified; live pipeline operator-pending
overrides_applied: 0
human_verification:
  - test: "Run `make up` end-to-end on a machine with docker + k3d >= 5.6 + helm >= 3.14 + trivy + kubeconform + terraform. Expected final output: `SMOKE: ALL PASS`."
    expected: "build → scan (0 HIGH/CRITICAL) → tf-validate → helm-lint → deploy → smoke — all steps green; SMOKE banner shows 8/8 checks PASS"
    why_human: "k3d, helm, trivy, kubeconform, terraform are not installable in the build sandbox (D-V40-LOCAL-VALIDATE). No fabricated evidence accepted."
  - test: "Run `make smoke` standalone against the deployed cluster. Expected output: `SMOKE: ALL PASS` with all 8 checks enumerated."
    expected: "(1) /healthz 200; (2) migrate Succeeded; (3) Redis AOF yes; (4) TZ=UTC all timezone-sensitive pods; (5) DNS resolves from each workload pod; (6) WS upgrade 101/400/426; (7) SPA fallback 200; (8) sw.js no-cache + /api/* no-store"
    why_human: "Requires a live k3d cluster with all workloads deployed."
  - test: "Run `make logs`, `make psql`, `make rollback` and verify no secret appears in terminal output."
    expected: "`make logs` tails pod logs without credentials; `make psql` opens a psql prompt using in-pod CNPG peer auth (no --password= flag); `make rollback` reverts the Helm release."
    why_human: "Requires kubectl connected to a running cluster. Secret-exposure check cannot be verified statically."
  - test: "Verify `make up` does NOT produce a double PASS/FAIL banner (WR-03 fix: SKIP_INLINE_SMOKE=1 exported to deploy). Only one SMOKE banner should appear at the end."
    expected: "A single `SMOKE: ALL PASS` banner from smoke.sh; no inline SMOKE banner from deploy-local.sh."
    why_human: "Requires a live run of `make up` to observe the terminal output sequence."
---

# Phase 121: Makefile CI/CD + Full Smoke + Runbooks — Verification Report

**Phase Goal:** A single `make up` command builds, scans, validates, and deploys the full stack to k3d; `make smoke` verifies the complete observable checklist; the production runbook documents the operator-pending boundary explicitly.
**Verified:** 2026-06-16T00:00:00Z
**Status:** human_needed
**Re-verification:** No — initial verification

---

## Summary

All static (authorable) must-haves are **VERIFIED** against actual codebase. The three live pipeline truths (make up green, make smoke green, access-wrapper live behavior) are correctly classified as **operator-pending** per D-V40-LOCAL-VALIDATE. The phase cannot be marked `passed` until an operator closes the four human verification items above on a machine with the full toolchain installed.

**Score:** 3/3 static must-haves verified. Live pipeline: 4 items operator-pending.

---

## Goal Achievement

### Observable Truths

The ROADMAP defines 3 success criteria. Under D-V40-LOCAL-VALIDATE, SC-1 and SC-2 split into a static sub-truth (authorable in sandbox) and a live sub-truth (operator-pending). SC-3 is fully static.

| # | Truth | Status | Evidence |
|---|-------|--------|----------|
| SC-1a | All 15 Makefile targets exist and `make -n <target>` dry-parses clean for each | VERIFIED | `make -n` passes for all 15: build, scan, push, tf-validate, tf-plan, helm-lint, helm-validate, deploy, smoke, rollback, logs, psql, backup, up, down |
| SC-1b | `make up` pipeline completes green end-to-end against k3d | OPERATOR-PENDING | k3d/helm/trivy not installed in sandbox; see human verification item 1 |
| SC-2a | `bash -n infra/scripts/smoke.sh` exits 0; all 8 check functions present with correct aggregation (run_check + SMOKE_FAILURES counter + exit 1 on failure) | VERIFIED | `bash -n` passes; 8 check functions confirmed; `run_check` wrapper confirmed (WR-01 fix); PASS/FAIL banner with `exit 1` confirmed |
| SC-2b | `make smoke` exits 0 against a live cluster with all 8 checks green | OPERATOR-PENDING | Requires deployed k3d; see human verification item 2 |
| SC-3 | `infra/runbooks/production.md` documents topology, prerequisites, deploy steps, operations, troubleshooting, operator-pending boundary list (23 UAT items, 2 HARD gates) | VERIFIED | All 8 required sections present; 23 per-phase items (118:4, 119:10, 120:9) + 6 cross-cutting probes; SEC-02 and BAK-03 HARD GATES with checkboxes; both runbook links present |

**Static score:** 3/3 truths verified.

---

### Required Artifacts

| Artifact | Expected | Status | Details |
|----------|----------|--------|---------|
| `Makefile` | All 15 OPS-01 targets + composed `make up` (OPS-02); wraps existing `infra/scripts/*.sh`; help auto-discovery + OPERATOR-PENDING tags; Phase-120 targets preserved | VERIFIED | 112 lines; all 15 targets in `.PHONY`; `build`/`deploy`/`smoke`/`backup` wrap scripts; `push`/`helm-lint`/`helm-validate`/`rollback`/`logs`/`psql`/`down` are thin CLI wrappers (appropriate — no script logic re-implemented); Phase-120 `help`/`tf-validate`/`tf-plan` preserved verbatim |
| `infra/scripts/smoke.sh` | 8-check Looks-Done-But-Isn't smoke; `bash -n` clean; SMOKE_FAILURES aggregation; exit 1 on failure; no secret echoed | VERIFIED | 399 lines; `bash -n` PASS; 8 check functions (`check_healthz`, `check_migrate`, `check_redis_aof`, `check_all_tz`, `check_dns`, `check_websocket`, `check_spa_fallback`, `check_sw_cache`); `run_check()` wrapper; `SMOKE_FAILURES` counter; PASS/FAIL banner; `exit 1` on failures |
| `infra/runbooks/production.md` | OPS-04 runbook: topology + prerequisites + deploy + operations + troubleshooting + operator-pending boundary; >= 120 lines | VERIFIED | 495 lines; all 8 sections present; links to `restore.md` and `sealed-secrets-key-backup.md` confirmed |

---

### Key Link Verification

| From | To | Via | Status | Details |
|------|----|-----|--------|---------|
| Makefile `smoke` target | `infra/scripts/smoke.sh` | `bash infra/scripts/smoke.sh` | VERIFIED | Line 79 of Makefile |
| Makefile `deploy` target | `infra/scripts/deploy-local.sh` | `bash infra/scripts/deploy-local.sh` | VERIFIED | Line 76 of Makefile |
| Makefile `up` target | `build scan tf-validate helm-lint deploy smoke` | prerequisite chain | VERIFIED | Line 108: `up: build scan tf-validate helm-lint deploy smoke` |
| Makefile `up` | `deploy-local.sh` SKIP_INLINE_SMOKE | `up: export SKIP_INLINE_SMOKE := 1` | VERIFIED | Line 107; confirmed in `deploy-local.sh:54,150-151` |
| `production.md` | `restore.md` | markdown link | VERIFIED | Lines 15, 245, 424 |
| `production.md` | `sealed-secrets-key-backup.md` | markdown link | VERIFIED | Lines 16, 106, 118, 391, 409 |
| `production.md` | `make up` | deploy procedure references | VERIFIED | Lines 132, 136-145 |

---

### Data-Flow Trace (Level 4)

Not applicable — all deliverables are infrastructure scripts and Markdown documents, not dynamic data-rendering components.

---

### Behavioral Spot-Checks

| Behavior | Command | Result | Status |
|----------|---------|--------|--------|
| All 15 targets dry-parse without Make syntax error | `for t in build scan push helm-lint helm-validate deploy smoke rollback logs psql backup down tf-validate tf-plan; do make -n $t; done` | All 14 exit 0 | PASS |
| `make -n up` dry-parse: emits build→scan→tf-validate→helm-lint→deploy→smoke sequence | `make -n up` | `bash infra/scripts/build-images.sh` → `bash infra/scripts/scan-images.sh` → `terraform -chdir=...` → `helm lint ...` → `bash infra/scripts/deploy-local.sh` → `bash infra/scripts/smoke.sh` | PASS |
| `bash -n infra/scripts/smoke.sh` exits 0 | `bash -n infra/scripts/smoke.sh` | exits 0 | PASS |
| `make help` shows `up` target with OPERATOR-PENDING tag | `make help` | `up` listed as "Full CD pipeline: build→scan→tf-validate→helm-lint→deploy→smoke, single 8-check smoke (OPERATOR-PENDING — needs k3d/helm/trivy)" | PASS |
| Live `make up` / `make smoke` green | requires k3d + helm + trivy | NOT RUN — toolchain absent | SKIP (operator-pending) |

---

### Probe Execution

No `scripts/*/tests/probe-*.sh` probes declared or conventional for this phase. The authorable validation was confirmed via `make -n` + `bash -n` spot-checks above.

---

### Requirements Coverage

| Requirement | Source Plan | Description | Status | Evidence |
|-------------|------------|-------------|--------|----------|
| OPS-01 | 121-01 | All 15 Makefile targets (static: all exist + dry-parse; live: operator-pending) | PARTIAL (static VERIFIED; live operator-pending) | `make -n` clean for all 15 targets; Makefile line 31 `.PHONY` declaration |
| OPS-02 | 121-01 | `make up` pipeline green against k3d | PARTIAL (static: `make -n up` clean; live: operator-pending) | `make -n up` emits correct pipeline sequence; live execution requires k3d |
| OPS-03 | 121-01 | `make smoke` verifies 8-check Looks-Done-But-Isn't checklist | PARTIAL (static: `bash -n` clean + all 8 checks present; live: operator-pending) | 8 check functions confirmed; `run_check` aggregation confirmed; `bash -n` PASS |
| OPS-04 | 121-02 | Production runbook with topology, prerequisites, deploy steps, operations, troubleshooting, operator-pending boundary | VERIFIED (fully static) | `infra/runbooks/production.md` — 495 lines, all sections present, 23 UAT items + 6 cross-cutting probes, 2 HARD gates with checkboxes |

**Note on OPS-01/02/03 status in REQUIREMENTS.md:** These requirements are correctly left as `[ ]` (not checked) in REQUIREMENTS.md because their full bar includes a live k3d run. This is accurate — the static sub-bar is met, but the requirements are not closeable until the operator closes them in 121-UAT. OPS-04 is correctly marked `[x]` as it is fully static.

---

### Anti-Patterns Found

| File | Line | Pattern | Severity | Impact |
|------|------|---------|----------|--------|
| `infra/scripts/smoke.sh` | 57 | `REPO_ROOT="$(git rev-parse --show-toplevel)"` — variable assigned but never referenced (IN-03 from review) | Info | None — cosmetic dead assignment; will abort if run outside a git repo (minor robustness gap, non-blocking given the script is always run from the repo root) |
| `infra/scripts/smoke.sh` | 338-344 | Check 8b probes `/api/v1/ping` — endpoint existence unverified (IN-01 from review) | Info | Could produce false-negative under live conditions if the endpoint doesn't exist; does not affect static done-bar; non-blocking |
| `infra/scripts/smoke.sh` | 269 | WS key is a fixed 14-byte base64 encoding (non-conforming RFC 6455 nonce, IN-02 from review) | Info | Check accepts 400/426 as PASS regardless, so RFC non-conformance does not cause false failures; non-blocking |

No BLOCKER anti-patterns found. No `TBD`, `FIXME`, or `XXX` debt markers in any phase deliverable. No plaintext secrets in Makefile, `smoke.sh`, or `production.md` (placeholders only: `<bot-token>`, `<db-password>`, `<secret-key>`).

---

### Review Findings Status

All 5 WARNING-level review findings (WR-01 through WR-05) from `121-REVIEW.md` were fixed in `121-REVIEW-FIX.md`:

| Finding | Fix | Verified |
|---------|-----|---------|
| WR-01: `set -e` abort risk in smoke.sh | `run_check()` wrapper added; all 8 checks dispatched through it | `grep -n 'run_check'` confirms 8 dispatch calls |
| WR-02: Check 6/7/8 DNS false-negative (curl `000`) | `INGRESS_IP`/`INGRESS_PORT` + `--resolve` added to checks 6, 7, 8 | `grep -n 'INGRESS_IP\|--resolve'` confirms present |
| WR-03: `make up` double-smoke | `up: export SKIP_INLINE_SMOKE := 1` + guard in `deploy-local.sh` | Confirmed in both files |
| WR-04: Makefile TAG missing `-dirty` suffix | TAG derived with dirty-aware logic matching `build-images.sh` | Line 25 of Makefile |
| WR-05: Runbook `kubectl logs` missing `-c alembic-check` | Troubleshooting table updated with explicit `-c` flags | Confirmed in `production.md:319` |

6 INFO findings (IN-01 through IN-06) were out of scope for the warning-only fix pass and are not blockers.

---

### Human Verification Required

#### 1. `make up` end-to-end pipeline

**Test:** On a workstation with docker + k3d >= 5.6 + helm >= 3.14 + trivy >= 0.50 + kubeconform + terraform >= 1.8: run `bash infra/scripts/k3d-up.sh` to bring up the cluster, then run `make up`.
**Expected:** Pipeline proceeds build → scan (0 HIGH/CRITICAL) → tf-validate → helm-lint → deploy → smoke; final output is `SMOKE: ALL PASS` with all 8 checks green. Exactly ONE smoke banner appears (no double-banner; SKIP_INLINE_SMOKE=1 suppresses the inline deploy smoke).
**Why human:** k3d, helm, trivy, kubeconform, terraform are not installed in the build sandbox and cannot be installed (no sudo/network). D-V40-LOCAL-VALIDATE and D-72-06 forbid fabricated live PASS output.

#### 2. `make smoke` standalone (8-check observable checklist)

**Test:** With the cluster from item 1 deployed, run `make smoke` standalone.
**Expected:** `SMOKE: ALL PASS` with all 8 checks enumerated: (1) `/healthz` 200 on backend pod; (2) migrate Job status.succeeded = 1; (3) Redis CONFIG GET appendonly = yes; (4) TZ=UTC on backend, arq-worker, telegram-bot, Redis pods; (5) `clubcore-postgres-rw` resolves via nslookup/python3/getent from backend, arq-worker, telegram-bot pods; (6) WS path returns 101/400/426 through Traefik ingress; (7) SPA deep-route returns 200 on admin-app and client-pwa; (8) sw.js carries Cache-Control: no-cache; /api/v1/ping carries Cache-Control: no-store.
**Why human:** All checks require a live deployed k3d cluster.

#### 3. Access-wrapper spot-check (no secret exposure)

**Test:** With the cluster deployed, run `make logs`, `make psql`, and `make rollback` (or `make rollback` will fail if only one revision — that is expected and acceptable).
**Expected:** `make logs` tails backend pod logs without any credential appearing in output. `make psql` opens a psql prompt via in-pod CNPG peer/socket auth — no `--password=` flag visible. `make rollback` reverts the Helm release (or reports "no revision to rollback" if only one revision — acceptable for the first deploy).
**Why human:** Secret-exposure verification requires running the commands with a live cluster to confirm no credential leaks to stdout.

#### 4. Double-smoke absence confirmation

**Test:** During item 1 (`make up` run), observe the terminal output carefully.
**Expected:** Only one SMOKE banner appears — from `smoke.sh` at the end of the pipeline. The `deploy-local.sh` inline smoke is suppressed (lines `[6/7] Inline smoke SKIPPED (SKIP_INLINE_SMOKE=1)`).
**Why human:** Requires a live `make up` run to observe the output sequence.

---

### Gaps Summary

No gaps blocking goal achievement. All static deliverables are present, substantive, wired, and pass the authorable done-bar (`make -n` + `bash -n`). The `human_needed` status reflects the live pipeline validation that is correctly deferred to an operator per D-V40-LOCAL-VALIDATE — this is the designed boundary, not a defect.

OPS-01/02/03 requirements are marked `[ ]` in REQUIREMENTS.md consistent with their full bar including a live k3d run. They will be closed when the operator completes 121-UAT.

---

_Verified: 2026-06-16T00:00:00Z_
_Verifier: Claude (gsd-verifier)_

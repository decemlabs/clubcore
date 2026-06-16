---
phase: 121-makefile-ci-cd-full-smoke-runbooks
plan: "01"
subsystem: infra/cd
tags: [makefile, cd, smoke, ops, k3d, helm]
dependency_graph:
  requires: [118-container-images-helm-chart-core-stack, 119-networking-security-csrf-rename, 120-iac-observability-backup]
  provides: [root-cd-layer, smoke-test-suite]
  affects: [infra/scripts/smoke.sh, Makefile]
tech_stack:
  added: []
  patterns: [makefile-target-wraps-script, posix-shell-strict, smoke-check-functions, operator-pending-honesty]
key_files:
  created: [infra/scripts/smoke.sh]
  modified: [Makefile]
decisions:
  - "make up uses prerequisite chaining (up: build scan tf-validate helm-lint deploy smoke) — deterministic ordering without ONESHELL"
  - "TAG variable exposed in Makefile for helm-lint/helm-validate/scan but scripts derive TAG internally for build/deploy to preserve -dirty suffix sync"
  - "COMPONENT ?= backend variable for make logs to allow per-call override without the recipe embedding a fixed component"
  - "smoke.sh check 6 (WebSocket) accepts 101/400/426 — a 4xx proves Traefik routed the path even when auth rejects the handshake"
  - "smoke.sh check 4 (TZ) intentionally skips nginx pods (admin-app, client-pwa) — stateless static servers with no wall-clock reads are explicitly documented as exempt"
metrics:
  duration: "~3 minutes"
  completed: "2026-06-16"
  tasks_completed: 2
  tasks_total: 3
  files_count: 2
---

# Phase 121 Plan 01: Makefile CD Layer + 8-Check Smoke Summary

**One-liner:** Root CD layer via GNU Make 3.81 (13 new OPS-01 targets wrapping existing infra/scripts/*.sh) + standalone `infra/scripts/smoke.sh` covering the 8 Looks-Done-But-Isn't checks extracted from deploy-local.sh and extended with healthz/DNS/WebSocket/SPA/SW-cache probes.

## What Was Built

### Task 1 — Extended Makefile (OPS-01 + OPS-02)

The existing `Makefile` (Phase 120: `help`, `tf-validate`, `tf-plan`) was extended with 13 new targets, all in GNU Make 3.81-compatible syntax (`make -n` dry-parse clean for all 15 targets):

| Target | Wraps | OPERATOR-PENDING |
|--------|-------|-----------------|
| `build` | `bash infra/scripts/build-images.sh` | No (needs docker only) |
| `scan` | `bash infra/scripts/scan-images.sh` | Yes (needs trivy) |
| `push` | `k3d image import ... -c clubcore` | Yes (needs k3d) |
| `helm-lint` | `helm lint infra/helm/clubcore --set image.tag=$(TAG) ...` | Yes (needs helm) |
| `helm-validate` | `helm template ... \| kubeconform ...` | Yes (needs helm + kubeconform) |
| `deploy` | `bash infra/scripts/deploy-local.sh` | Yes (needs k3d + helm) |
| `smoke` | `bash infra/scripts/smoke.sh` | Yes (needs deployed cluster) |
| `rollback` | `helm rollback $(RELEASE)` | Yes (needs helm) |
| `logs` | `kubectl logs --selector=...` | Yes (needs kubectl + cluster) |
| `psql` | `kubectl exec ... -- psql -U app -d clubcore` | Yes (needs kubectl + cluster) |
| `backup` | `bash infra/scripts/restore-verify.sh` | Yes (needs k3d + CNPG) |
| `up` (OPS-02) | Prerequisite chain: build → scan → tf-validate → helm-lint → deploy → smoke | Yes (full pipeline) |
| `down` | `k3d cluster delete $(K3D_CLUSTER)` | Yes (needs k3d) |

Phase-120 targets (`help`, `tf-validate`, `tf-plan`) preserved byte-for-byte.

Security invariants maintained:
- `psql` uses in-pod CNPG peer auth — no `--password=` flag, no secret env on CLI
- `scan` recipe passes through to `scan-images.sh` without overriding `REQUIRE_TRIVY` — gate stays hard in CI
- `logs` is a plain `kubectl logs` wrapper, no credential exposure
- No recipe echoes a plaintext secret

### Task 2 — infra/scripts/smoke.sh (OPS-03)

New 376-line standalone smoke script; `bash -n` syntax-check passes. Implements all 8 Looks-Done-But-Isn't checks as functions with `log()`/`ok()`/`fail()` helpers and `SMOKE_FAILURES` counter:

| # | Check | Source |
|---|-------|--------|
| 1 | `/healthz` 200 via `kubectl exec` + `curl localhost:8000/healthz` on backend pod | NEW |
| 2 | migrate Job Succeeded (WR-06: Succeeded vs Failed vs Timed-out distinction) | EXTRACT — deploy-local.sh lines 145-170 |
| 3 | Redis AOF: `CONFIG GET appendonly` == `yes` (DATA-02) | EXTRACT — deploy-local.sh lines 223-235 |
| 4 | TZ=UTC on all timezone-sensitive pods (backend, arq-worker, telegram-bot, Redis) | EXTRACT + EXTEND — deploy-local.sh lines 184-221 |
| 5 | DNS resolve `clubcore-postgres-rw` from each workload pod (P8/SEC-04 NetworkPolicy evidence) | NEW |
| 6 | WebSocket upgrade through Traefik ingress → 101/400/426 (NET-02) | NEW |
| 7 | SPA deep-route fallback → 200 via nginx try_files (NET-04) | NEW |
| 8 | PWA SW cache: sw.js `no-cache`; `/api/*` `no-store` (NET-04) | NEW |

PASS/FAIL banner with `exit 1` on any failure. No secret echoed.

### Task 3 — Live make up / make smoke (OPERATOR-PENDING)

Auto-deferred per D-V40-LOCAL-VALIDATE. k3d, helm, trivy, kubeconform, terraform are NOT installed in this sandbox and cannot be installed. Live validation is operator-pending — see `121-UAT.md`.

**Operator commands when toolchain is available:**
```bash
# 1. Bring up cluster
bash infra/scripts/k3d-up.sh

# 2. Full CD pipeline
make up

# 3. Standalone smoke
make smoke

# 4. Spot-check access wrappers (no secret should appear)
make logs
make psql
```
Expected: `SMOKE: ALL PASS` with all 8 checks green. [pending — operator]

## Authorable Validation Results

All static/dry checks that do not require k3d/helm/trivy:

```
make -n up:                 OK
make -n build:              OK
make -n scan:               OK
make -n push:               OK
make -n helm-lint:          OK
make -n helm-validate:      OK
make -n deploy:             OK
make -n smoke:              OK
make -n rollback:           OK
make -n logs:               OK
make -n psql:               OK
make -n backup:             OK
make -n down:               OK
make -n tf-validate:        OK
make -n tf-plan:            OK
bash -n infra/scripts/smoke.sh:  OK (376 lines, 8 check markers verified)
make help OPERATOR-PENDING: present for all k3d/helm/trivy-requiring targets
```

## Deviations from Plan

None — plan executed exactly as written.

The `up` target uses prerequisite chaining (`up: build scan tf-validate helm-lint deploy smoke`) rather than a sequential recipe. This is explicitly allowed by the plan's wording ("use prerequisite chaining ... OR a sequential recipe") and produces the same deterministic order with cleaner `make -n` output.

## Known Stubs

None. No stub patterns detected in Makefile or infra/scripts/smoke.sh.

## Threat Flags

No new trust-boundary surfaces introduced beyond what the plan's threat model already covers. The threat register items T-121-01 through T-121-SC were all addressed:

- T-121-01 (logs/psql secret exposure): MITIGATED — no `--password=` flags; psql uses in-pod CNPG auth
- T-121-02 (trivy gate tampering): MITIGATED — scan recipe delegates to `scan-images.sh`'s `REQUIRE_TRIVY` contract without override
- T-121-03 (push/deploy image tampering): MITIGATED — push imports only git-SHA-tagged images to local k3d; deploy gates on helm lint + kubeconform
- T-121-04 (smoke.sh spoofing): MITIGATED — smoke.sh reads cluster state only; no mutation, no secret exposure

## Self-Check

<!-- gsd:self-check -->

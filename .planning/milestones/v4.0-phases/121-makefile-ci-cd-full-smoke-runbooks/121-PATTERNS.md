# Phase 121: Makefile CI/CD + Full Smoke + Runbooks - Pattern Map

**Mapped:** 2026-06-16
**Files analyzed:** 3 (1 modify, 2 new)
**Analogs found:** 3 / 3 (every file has a strong in-repo analog — this is an orchestration phase, no net-new logic)

This is the v4.0 capstone. It ORCHESTRATES the existing 118–120 artifacts via the root Makefile + a smoke script + a production runbook. The Makefile targets WRAP existing `infra/scripts/*.sh` (do not reimplement their logic); the smoke script EXTRACTS/EXPANDS the inline smoke already in `deploy-local.sh`; the runbook FOLLOWS the existing two runbooks' style and aggregates per-phase UAT operator-pending items.

## File Classification

| New/Modified File | Role | Data Flow | Closest Analog | Match Quality |
|-------------------|------|-----------|----------------|---------------|
| `Makefile` (MODIFY — extend) | config / orchestration | batch (target → script) | self (existing `help`/`tf-validate`/`tf-plan`) + `infra/scripts/*.sh` (wrapped targets) | exact (self) |
| `infra/scripts/smoke.sh` (NEW) | script / test | transform (cluster assertions → PASS/FAIL) | `infra/scripts/deploy-local.sh` §6 inline smoke (a–e) | exact |
| `infra/runbooks/production.md` (NEW) | docs / runbook | document | `infra/runbooks/restore.md` + `infra/runbooks/sealed-secrets-key-backup.md` | exact |

## Pattern Assignments

### `Makefile` — EXTEND, do not clobber (config/orchestration, batch)

**Analog:** the existing `Makefile` itself (Phase 120 added `help`, `tf-validate`, `tf-plan`). Preserve those three targets verbatim; ADD the OPS-01 targets in the same style.

**Existing target/help/`.PHONY` style to match** (`Makefile` lines 11–21):
```makefile
.PHONY: tf-validate tf-plan help

help: ## Show available targets
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | awk 'BEGIN {FS = ":.*?## "}; {printf "  %-20s %s\n", $$1, $$2}'

tf-validate: ## Validate both Terraform modules (static; no cluster needed)
	terraform -chdir=infra/terraform/host validate
	terraform -chdir=infra/terraform/cluster validate

tf-plan: ## Plan the cluster module against k3d (OPERATOR-PENDING — needs reachable k3d)
	terraform -chdir=infra/terraform/cluster plan
```

Rules the planner MUST enforce on the extension:
- **Help auto-discovery is the contract.** Every new target needs a `## <description>` trailing comment so `make help` lists it. Keep descriptions <= the `%-20s` column intent.
- **Tag `## (OPERATOR-PENDING ...)`** in the help string of any target that needs k3d/helm/trivy/terraform (matches the `tf-plan` precedent). This is the D-V40-LOCAL-VALIDATE honesty boundary surfaced in `make help`.
- **Add every new target to `.PHONY`** (single line or grouped — Claude's discretion per CONTEXT).
- **GNU Make 3.81** (confirmed `make --version`). Avoid `.ONESHELL`, `$(file ...)`, grouped-target `&:`, and other GNU 4.x-only features. Keep recipes POSIX-shell portable. Validate with `make -n <target>` (dry-parse) — the done-bar's authorable check.

**Target → wrapped script map (call the script; do NOT inline its logic):**
| Target | Wraps | Source analog | Notes |
|--------|-------|---------------|-------|
| `build` | `bash infra/scripts/build-images.sh` | `build-images.sh` | echoes `TAG=<sha>` at end (line 96) |
| `scan` | `bash infra/scripts/scan-images.sh` | `scan-images.sh` | accepts `TAG=` env (line 26); CI path sets `REQUIRE_TRIVY=1` (line 56) |
| `push` | `k3d image import` OR registry push to local k3d registry `localhost:5111` | `k3d-up.sh` lines 28–29, `deploy-local.sh` lines 90–96 | D-V40-MAKEFILE-CD: local k3d registry only, no external registry |
| `helm-lint` | `helm lint infra/helm/clubcore --set image.tag=$(TAG) --set seaweedfs.enabled=false` | `deploy-local.sh` line 103 | copy the exact `--set` flags (lint needs image.tag — WR-02) |
| `helm-validate` | `helm template ... | kubeconform -summary -strict -ignore-missing-schemas -kubernetes-version 1.29.0` | `deploy-local.sh` lines 110–117 | OPERATOR-PENDING (kubeconform absent) |
| `deploy` | `bash infra/scripts/deploy-local.sh` | `deploy-local.sh` | the script already does import + lint + kubeconform + `helm upgrade --install --wait` + inline smoke |
| `smoke` | `bash infra/scripts/smoke.sh` | NEW (see below) | extract+expand the 5-point smoke to 8 checks |
| `rollback` | `helm rollback clubcore` (Claude's discretion: prior revision) | `deploy-local.sh` line 128 (release name `clubcore`) | mechanism = `helm rollback` per CONTEXT discretion |
| `logs` | `kubectl logs` convenience wrapper | `deploy-local.sh` selectors (lines 175, 187) | use `app.kubernetes.io/component=` selectors |
| `psql` | `kubectl exec ... -- psql` into CNPG primary | `restore-verify.sh` lines 107–112 | selector `cnpg.io/cluster=clubcore-postgres,cnpg.io/instanceRole=primary` |
| `backup` | `bash infra/scripts/restore-verify.sh` (verified round-trip) | `restore-verify.sh` | env-var driven (lines 48–54); OPERATOR-PENDING |
| `tf-validate` / `tf-plan` | KEEP AS-IS | self | do not touch |
| `up` | composed: `build` → `scan` → `tf-validate` → `helm-lint` → `deploy` → `smoke` (OPS-02) | — | use prerequisite chaining or sequential recipe; green-against-k3d OPERATOR-PENDING |
| `down` | `k3d cluster delete clubcore` | `k3d-up.sh` line 22 comment | cluster name `clubcore` |

**Variable conventions (Claude's discretion per CONTEXT, suggested):**
```makefile
TAG ?= $(shell git rev-parse --short HEAD)
NAMESPACE ?= default
RELEASE ?= clubcore
K3D_CLUSTER ?= clubcore
```
These mirror the hard-coded values already in the scripts: `CLUSTER_NAME="clubcore"`, `RELEASE_NAME="clubcore"`, `NAMESPACE="default"` (`deploy-local.sh` lines 36–38), registry port `5111` (`k3d-up.sh` line 29). Pass `TAG` through to scripts that read it (`scan-images.sh` line 26) — but note `build-images.sh`/`deploy-local.sh` derive TAG internally incl. the `-dirty` suffix, so prefer NOT overriding their internal derivation to keep the import tag matched (`deploy-local.sh` lines 79–83).

---

### `infra/scripts/smoke.sh` — NEW (script/test, transform)

**Analog:** the inline smoke block inside `deploy-local.sh` §6 (lines 137–286). Extract checks (a)–(e) into a standalone script and ADD the 3 missing checks. Prefer a dedicated script over inline-in-Makefile (CONTEXT: "prefer a script for testability"). Done-bar authorable check: `bash -n infra/scripts/smoke.sh` clean.

**Header/config/helpers pattern to copy** (`deploy-local.sh` lines 33–61):
```bash
set -euo pipefail
CLUSTER_NAME="clubcore"; RELEASE_NAME="clubcore"; NAMESPACE="default"
REPO_ROOT="$(git rev-parse --show-toplevel)"
log()  { echo "[smoke] $*"; }
ok()   { echo "[smoke] PASS: $*"; }
fail() { echo "[smoke] FAIL: $*" >&2; SMOKE_FAILURES=$((SMOKE_FAILURES + 1)); }
SMOKE_FAILURES=0
```

**PASS/FAIL summary + non-zero-exit-on-failure pattern to copy** (`deploy-local.sh` lines 262–286): banner box + `exit 1` when `SMOKE_FAILURES != 0`.

**The 8 OPS-03 checks** (5 already exist in deploy-local.sh, 3 are new). Each check should be a function like `check_tz()` (`deploy-local.sh` lines 184–202) returning via the `ok`/`fail` helpers:

| # | Check | Source / status | Pattern to copy |
|---|-------|-----------------|-----------------|
| 1 | `/healthz` 200 | NEW | `kubectl exec` into backend pod (selector `app.kubernetes.io/component=backend`, `deploy-local.sh` line 175) → `curl -s -o /dev/null -w '%{http_code}' localhost:8000/healthz`, assert `200`. Or `kubectl run` curl probe against the backend Service. |
| 2 | migrate Job completed | EXISTS — `deploy-local.sh` lines 145–170 | copy verbatim incl. WR-06 Succeeded-vs-Failed-vs-Timeout distinction (reads `.status.succeeded`/`.status.failed`/Failed condition) |
| 3 | Redis AOF on | EXISTS — `deploy-local.sh` lines 223–235 | `kubectl exec <redis-pod> -- redis-cli CONFIG GET appendonly` == `yes` |
| 4 | `TZ=UTC` on ALL pods | EXISTS — `deploy-local.sh` lines 182–221 | `check_tz` for backend/arq-worker/telegram-bot + Redis pod; the 8-check spec says ALL pods — extend the component list to cover every app pod |
| 5 | DNS resolve from each pod (P8/P9 evidence) | NEW | per pod: `kubectl exec <pod> -- nslookup clubcore-postgres-rw` (or `getent hosts` / `python -c socket.gethostbyname`); P8 CoreDNS egress is allowed on all 6 NetworkPolicies (119-UAT) — assert in-cluster service DNS resolves from each workload pod |
| 6 | WebSocket upgrade through ingress | NEW | NET-02: WS path `/api/v1/client/ws/*` (119-UAT item 5) — Traefik v3 auto-upgrades (no annotation). Probe `Connection: Upgrade`/`Upgrade: websocket` → expect `101` through the ingress host |
| 7 | SPA fallback 200 | NEW | NET-04 (119-UAT item 6): deep SPA route → 200 via nginx `try_files`; probe a deep path on admin-app/client-pwa host through the ingress |
| 8 | PWA SW cache clean (`/api/*` not cached) | NEW | NET-04: `sw.js`/`manifest` `no-cache`, `/api/*` `no-store`; assert response headers on `/api/*` through the ingress are `no-store` (SW must not cache API) |

**Redis pod discovery pattern to reuse** (`deploy-local.sh` lines 208–211): StatefulSet pod found via `app.kubernetes.io/name=clubcore` selector + `grep redis`.

**Note:** checks 1, 5, 6, 7, 8 are runtime/cluster checks → OPERATOR-PENDING for a live PASS (k3d/helm absent). The script must be authored + `bash -n` clean; live green is operator-pending per D-V40-LOCAL-VALIDATE. Do NOT fabricate PASS output.

---

### `infra/runbooks/production.md` — NEW (docs/runbook, document)

**Analog:** `infra/runbooks/restore.md` + `infra/runbooks/sealed-secrets-key-backup.md`. Match their structure exactly and LINK to both (they are the deep-dive references; production.md is the umbrella).

**Runbook section/style pattern to copy** (from both analogs):
- Title + `**Requirement:**` + `**Risk level:**` header block (`restore.md` lines 1–5, `sealed-secrets-key-backup.md` lines 1–5).
- `## Why This Matters` rationale section.
- Blockquoted `> **OPERATOR-PENDING:**` and `> **SAFETY INVARIANT:**` callouts (`restore.md` lines 22–31, `sealed-secrets-key-backup.md` lines 23–25).
- `## <N> Hard Gate — Acceptance Criteria` with `- [ ]` checkboxes (`restore.md` lines 34–48, `sealed-secrets-key-backup.md` lines 29–37).
- Numbered `## Step N — ...` sections each with a fenced `bash` block + `# Expected:` comments.
- `## Quick Reference — Key Commands` block (`restore.md` lines 346–368).
- `## Security Notes` table | Item | Requirement | (`restore.md` lines 372–381, `sealed-secrets-key-backup.md` lines 215–223).

**Required production.md sections (OPS-04):** topology · prerequisites (toolchain: k3d≥5.6, helm≥3.14, kubectl, docker, trivy, terraform, kubeconform, kubeseal — cross-ref `k3d-up.sh` lines 11–16, `deploy-local.sh` lines 18–24) · deploy steps (`make up` = build→scan→tf-validate→helm-lint→deploy→smoke) · operations (backup/restore/rollback/scale — link `restore.md`; rollback = `helm rollback clubcore`) · troubleshooting · **explicit operator-pending boundary list** (below).

**Operator-pending boundary list — aggregate from per-phase UAT (no-fabrication, D-72-06 / D-V40-LOCAL-VALIDATE):**

From **118-UAT** (`118-container-images-helm-chart-core-stack/118-UAT.md`, 4 pending):
- Live k3d deploy done-bar — `k3d-up.sh && deploy-local.sh` → SMOKE: ALL PASS
- trivy CVE scan gate — `scan-images.sh` (CI sets `REQUIRE_TRIVY=1`, fail-closed)
- helm lint + helm template render (CR-01 multi-release-name correctness)
- alembic check initContainer exits 0 post-deploy

From **119-UAT** (`119-networking-security-csrf-rename/119-UAT.md`, 10 pending):
- **SEC-02 RSA-key off-node backup + restore round-trip (HARD GATE before prod)** — `seal-secrets.sh` + kubeseal, copy key to second PC, verify restore (link `sealed-secrets-key-backup.md`)
- helm lint + `kubectl apply --dry-run=client` clean
- 3-host HTTPS reachability + HTTP→HTTPS 308 redirect (NET-01)
- selfSigned Certificate Ready (NET-03) — and **LE-prod TLS** for real production
- WebSocket upgrade through Traefik v3 (NET-02)
- SPA deep-route fallback + SW cache headers (NET-04)
- kubeseal round-trip — SealedSecret decrypts (SEC-01)
- (plus remaining 119 runtime checks)

From **120-UAT** (`120-iac-observability-backup/120-UAT.md`, 9 pending):
- **BAK-03 verified restore round-trip in k3d (HEADLINE)** — `restore-verify.sh` to SCRATCH, row-count match (link `restore.md`)
- terraform apply (host + cluster modules) — `tf-plan`/`tf-apply` need reachable k3d
- Live `/metrics` scrape + OpenAPI exclusion (OBS-03)
- Grafana dashboards render with live data (OBS-04)
- BAK-04 restore-verify CronJob + alert-on-failure
- **OBS-05 Telegram alert delivery** — needs real sealed bot token
- (plus remaining 120 runtime checks)

Cross-cutting prod probes named in CONTEXT to include: **ЮKassa sandbox probe**, **RU email production probe**, **kubeseal install + SEC-02 key off-node backup**, **LE-prod TLS issuance**.

## Shared Patterns

### Operator-Pending Honesty (D-V40-LOCAL-VALIDATE / D-72-06 no-fabrication)
**Source:** `scan-images.sh` lines 40–67 (fail-closed in CI via `REQUIRE_TRIVY=1`, operator-pending + WARN + `exit 0` locally), `Makefile` line 20 (`## OPERATOR-PENDING` help tag), every `*-UAT.md` `[pending — operator]` marker.
**Apply to:** all three files. Targets/checks needing k3d/helm/trivy/terraform/kubeconform/kubeseal are authored + dry-validated (`make -n`, `bash -n`, `helm lint`), never reported as live-green. The runbook states the boundary explicitly.

### Repo-root anchoring + strict bash
**Source:** `deploy-local.sh` lines 33, 41; `build-images.sh` lines 25, 28; `restore-verify.sh` lines 45.
**Apply to:** `smoke.sh`. `set -euo pipefail` + `REPO_ROOT="$(git rev-parse --show-toplevel)"` so it runs from any cwd.

### Component selectors (kubectl)
**Source:** `deploy-local.sh` lines 175, 187 (`app.kubernetes.io/component=backend|arq-worker|telegram-bot`), lines 208–211 (Redis via `app.kubernetes.io/name=clubcore`), `restore-verify.sh` lines 108–110 (CNPG primary `cnpg.io/cluster=...,cnpg.io/instanceRole=primary`).
**Apply to:** `smoke.sh` (all checks), Makefile `logs`/`psql` targets.

### Image tag derivation (must stay matched)
**Source:** `build-images.sh` lines 35–40, `deploy-local.sh` lines 79–83 (identical `-dirty` suffix logic so import tag == build tag).
**Apply to:** Makefile — do not override the scripts' internal TAG derivation; the `-dirty` suffix must remain consistent build↔deploy.

## No Analog Found

None. Every file maps to a strong in-repo analog. This phase authors no net-new logic — only orchestration (Makefile targets wrapping scripts), extraction (smoke checks from deploy-local.sh), and documentation (runbook aggregating UAT pending items).

## Metadata

**Analog search scope:** `Makefile`, `infra/scripts/`, `infra/runbooks/`, `.planning/phases/{118,119,120}-*/...-UAT.md`, `.planning/REQUIREMENTS.md`, `121-CONTEXT.md`
**Files scanned:** 10 (Makefile, 5 infra scripts, 2 runbooks, 3 UAT files, REQUIREMENTS.md, CONTEXT.md)
**Toolchain reality:** GNU Make 3.81 present; k3d/helm/trivy/terraform/kubeconform/kubeseal absent (operator-pending boundary)
**Pattern extraction date:** 2026-06-16

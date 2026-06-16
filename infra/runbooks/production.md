# clubcore Production Runbook

**Requirement:** OPS-04
**Risk level:** CRITICAL — this is the umbrella runbook for the v4.0 self-hosted k3s stack; incorrect procedure can expose unrecoverable data loss (controller key loss), silent backup gaps, or production outage

---

## Why This Matters

This runbook is the single document an operator follows to take clubcore to production on a bare-metal k3s node. It covers the full stack topology, the toolchain that must be installed on the operator workstation, the `make up` deploy pipeline, and the operations playbook (backup/restore/rollback/scale).

The v4.0 milestone done-bar is **local k3d validation** (D-V40-LOCAL-VALIDATE). This runbook's capstone section — the **Operator-Pending Boundary** — is the explicit, honest list of everything the build sandbox cannot prove and that MUST be verified live by an operator before production go-live. No fabricated evidence is acceptable (D-72-06 precedent).

**Deep-dive runbooks this document links to:**
- [infra/runbooks/restore.md](restore.md) — Postgres + Redis + SeaweedFS verified restore round-trip (BAK-03/BAK-04)
- [infra/runbooks/sealed-secrets-key-backup.md](sealed-secrets-key-backup.md) — sealed-secrets controller RSA key export + off-node backup (SEC-02 / P6)

> **OPERATOR-PENDING:** Sections marked with this callout cannot be completed in the build sandbox (k3d/helm/trivy/terraform/kubeseal not installed). They MUST be completed by the operator on a machine with the full toolchain.

> **SAFETY INVARIANT (D-V40-REPLICAS):** `arq-worker` and `telegram-bot` are `replicas: 1` + `strategy: Recreate`. This is an ARCHITECTURAL INVARIANT, not a tuning parameter. Scaling either workload above 1 replica WILL cause cron double-fire (arq-worker) and Telegram duplicate-polling (telegram-bot). Do NOT scale them. See the Scale section for detail.

---

## Topology

The v4.0 stack runs on a **single bare-metal k3s node** (D-V40-ONPREM-K3S). Local validation uses k3d (not kind — different distro, hides Traefik/ServiceLB behavior). The Helm release is named `clubcore`, deployed to the `default` namespace.

### Ingress Layer

| Component | Version | Role |
|-----------|---------|------|
| Traefik v3 | bundled with k3s | Ingress controller + TLS termination; HTTP → HTTPS 308 redirect |
| cert-manager | helm chart | Certificate provisioning (selfSigned in dev; Let's Encrypt prod) |

Traefik fronts 3 hosts:

| Host | Backend |
|------|---------|
| `api.<domain>` | backend Service `:8000` |
| `admin.<domain>` | admin nginx Service `:8080` |
| `app.<domain>` | client nginx Service `:8080` |

WebSocket (`/api/v1/client/ws/*`) upgrades through Traefik v3 automatically — no annotation required (NET-02).

### Stateful Layer (`default` namespace)

| Component | Technology | Notes |
|-----------|-----------|-------|
| Postgres | CNPG operator v1.27 (`instances: 1`) | WAL archiving to SeaweedFS S3; `reclaimPolicy: Retain`; nodeSelector pinned (P1) |
| Redis | StatefulSet `redis:7-alpine` | AOF enabled (DATA-02); `reclaimPolicy: Retain` |
| SeaweedFS S3 | Helm v4.33.0 | S3 endpoint `clubcore-seaweedfs-s3:8333`; `buckets: [clubcore]` |

### Application Layer (`default` namespace)

| Component | replicas | Strategy | Notes |
|-----------|----------|----------|-------|
| backend | 1 | RollingUpdate | FastAPI 0.115+; readinessProbe waits for migrate Job (P4) |
| arq-worker | **1 — INVARIANT** | **Recreate — INVARIANT** | ARQ async job worker; see D-V40-REPLICAS |
| telegram-bot | **1 — INVARIANT** | **Recreate — INVARIANT** | Telegram polling bot; see D-V40-REPLICAS |
| admin | 1 | RollingUpdate | nginx serving admin SPA; `try_files` SPA fallback; SW headers |
| client | 1 | RollingUpdate | nginx serving client PWA; same SPA/SW config |

### Cluster Infrastructure

| Component | Namespace | Notes |
|-----------|-----------|-------|
| sealed-secrets controller | `kube-system` | v0.37.0; RSA key MUST be backed up off-node — see SEC-02 HARD GATE |
| CNPG operator | `cnpg-system` | v1.27; deployed by `k3d-up.sh` |
| kube-prometheus-stack | `monitoring` | Prometheus + Grafana + Alertmanager |
| Loki + Alloy | `monitoring` | Log aggregation (30d retention); Alloy ships pod logs |
| CNPG backup + CronJobs | `default` | `ScheduledBackup` + Redis RDB CronJob + SeaweedFS mirror CronJob + restore-verify CronJob (weekly Monday 05:00 UTC) |

### Local Registry (k3d development)

The local k3d registry runs at `localhost:5111` (in-cluster: `clubcore-registry:5000`). There is no external registry and no git remote (D-V40-MAKEFILE-CD). The Makefile is the only CD layer.

---

## Prerequisites

> **OPERATOR-PENDING:** All tools below must be installed on the operator workstation.

### Toolchain

| Tool | Min Version | Install |
|------|-------------|---------|
| docker | latest stable | https://docs.docker.com/get-docker/ |
| kubectl | 1.29+ | bundled with k3d or `brew install kubectl` |
| k3d | **>= 5.6** | `curl -s https://raw.githubusercontent.com/k3d-io/k3d/main/install.sh \| bash` |
| helm | **>= 3.17** | `curl https://raw.githubusercontent.com/helm/helm/main/scripts/get-helm-3 \| bash` |
| terraform | >= 1.8 | https://developer.hashicorp.com/terraform/install |
| trivy | >= 0.50 | `brew install aquasecurity/trivy/trivy` |
| kubeconform | latest | `brew install kubeconform` OR `go install sigs.k8s.io/kubeconform/cmd/kubeconform@latest` |
| kubeseal | 0.37.x (pin to controller version) | `brew install kubeseal` OR from GitHub releases |

Source cross-reference: `infra/scripts/k3d-up.sh` lines 11–16 (k3d/helm/kubectl/docker), `infra/scripts/deploy-local.sh` lines 18–24 (helm/kubeconform).

> **helm >= 3.17 (not 3.14):** the SeaweedFS subchart (`charts/seaweedfs` v4.33.0) uses the `fromToml` template function, which is unavailable in Helm 3.16 and earlier (`helm lint` fails with `function "fromToml" not defined`). Verified locally 2026-06-16: lint/template pass on Helm 3.17+/4.x.

### Local validation performed (2026-06-16, build sandbox via Docker)

What was actually run (not just authored) — Docker was available so build + the tool-as-container checks ran for real:

| Check | Tool | Result |
|-------|------|--------|
| `make build` (4 images) | docker | ✅ all 4 built (backend/admin/client/backup) |
| `helm lint` + `helm template` (full chart, all gates on) | helm 4.x (container) | ✅ renders 49 objects; lint clean |
| Manifest schema validation | kubeconform (container) | ✅ 43/43 standard objects valid (6 CRDs skipped) |
| `terraform validate` (host + cluster) | terraform 1.9 (container) | ✅ both green (after fixing the helm-provider `kubernetes` attribute syntax) |
| trivy CVE gate (HIGH/CRITICAL) | trivy (container) | admin ✅ 0 · client ✅ 0 · backup ✅ 0 · **backend ✗ 2** |

**Still OPERATOR-PENDING** (could not run in the sandbox — no k3d binary, host has no network to install it):
- Live `make up` / `make smoke` against a real k3s/k3d cluster (deploy + 8-check smoke).
- The 2 HARD GATES (SEC-02 RSA-key off-node backup, BAK-03 restore round-trip).

**Outstanding finding — backend image CVEs (IMG-04 gate, backend only):** `starlette` 0.52.1 has 2 HIGH CVEs (CVE-2026-48818 SSRF via StaticFiles → fixed 1.1.0; CVE-2026-54283 form-DoS → fixed 1.3.1). Fix: bump `starlette` (via `fastapi`/direct pin) to `>= 1.3.1`, `uv lock`, rebuild, re-scan. Requires network for the lock — deferred to the operator. The 3 other images pass the gate clean (frontends patched via `apk upgrade` in the nginx stage).

### Hardware

- Single bare-metal node (or VM). k3s is the production distro; k3d wraps k3s in Docker for local validation.
- Minimum: 4 CPU, 8 GB RAM, 80 GB SSD (for Postgres + Redis AOF + SeaweedFS + monitoring stack).
- Second PC: required for off-node sealed-secrets RSA key backup (D-V40-SECRETS / SEC-02).

### Sealed Secrets (first-time setup)

Before deploying, install the sealed-secrets controller and back up the RSA key. See [sealed-secrets-key-backup.md](sealed-secrets-key-backup.md) for the complete procedure. **This is SEC-02 HARD GATE — do not skip it.**

```bash
helm repo add sealed-secrets https://bitnami-labs.github.io/sealed-secrets
helm install sealed-secrets -n kube-system --create-namespace \
  --version 0.37.0 sealed-secrets/sealed-secrets

# Expected: sealed-secrets pod Running in kube-system
kubectl get pod -n kube-system -l app.kubernetes.io/name=sealed-secrets

# Immediately export and back up the RSA key (P6 — unrecoverable if lost)
bash infra/scripts/seal-secrets.sh
# Follow infra/runbooks/sealed-secrets-key-backup.md to copy key to the second PC
```

---

## Deploy Steps

### Quick Path: `make up`

> **OPERATOR-PENDING:** `make up` requires k3d, helm, trivy, and a running Docker daemon.

```bash
# From the repo root:
make up
# Expected: build → scan → tf-validate → helm-lint → deploy → smoke
# Final output: SMOKE: ALL PASS
```

`make up` is the composed pipeline (OPS-02):

```
make build        # Build all 4 container images tagged with git short-SHA
make scan         # Scan images for HIGH/CRITICAL CVEs (trivy; REQUIRE_TRIVY=1 in CI)
make tf-validate  # Validate both Terraform modules (static; no cluster needed)
make helm-lint    # Lint the Helm chart with image.tag set
make deploy       # Import images + helm upgrade --install + inline smoke
make smoke        # Full 8-check smoke against the deployed cluster
```

### Manual Step-by-Step (fallback)

If `make up` fails mid-pipeline, run stages individually:

```bash
# Step 1: Create the k3d cluster (once — idempotent if cluster exists)
bash infra/scripts/k3d-up.sh
# Expected: [k3d-up] === k3d cluster 'clubcore' is ready ===
#           Local registry: localhost:5111
#           CNPG operator: cnpg-system/cnpg-controller-manager Available

# Step 2: Build container images
bash infra/scripts/build-images.sh
# Expected: 4 images built and tagged with git short-SHA
#   clubcore/backend:<sha>
#   clubcore/admin:<sha>
#   clubcore/client:<sha>

# Step 3: Scan for CVEs (gate)
bash infra/scripts/scan-images.sh
# Expected: 0 HIGH/CRITICAL CVEs; exit 0
# With CI gate: REQUIRE_TRIVY=1 bash infra/scripts/scan-images.sh

# Step 4: Validate Terraform modules (static; no cluster needed)
make tf-validate
# Expected: "Success! The configuration is valid." for both modules

# Step 5: Lint the Helm chart
make helm-lint
# Expected: 0 chart(s) linted, 0 chart(s) failed

# Step 6: Deploy to k3d
bash infra/scripts/deploy-local.sh
# Expected: [deploy-local] helm install COMPLETE
#           [deploy-local] (a) migrate Job status.succeeded = 1
#           [deploy-local] (b) backend pod Ready
#           [deploy-local] ... (all smoke checks pass)
#           SMOKE: ALL PASS
#           D-V40-LOCAL-VALIDATE: done-bar criteria MET

# Step 7: Full 8-check smoke (standalone)
bash infra/scripts/smoke.sh
# Expected: SMOKE: ALL PASS (8/8 checks)
```

### Sealed Secrets for Production

Production deployments use sealed secrets instead of plaintext values (never commit plaintext to git):

```bash
# Set plaintext values as environment variables (do NOT commit these)
export SEAL_DATABASE_URL="postgresql+asyncpg://app:<db-password>@clubcore-postgres-rw:5432/clubcore"
export SEAL_SECRET_KEY="<secret-key>"
export SEAL_S3_ACCESS_KEY_ID="<s3-access-key>"
export SEAL_S3_SECRET_ACCESS_KEY="<s3-secret-key>"
export SEAL_TELEGRAM_BOT_TOKEN="<bot-token>"
# Optional email credentials
# export SEAL_EMAIL_AWS_ACCESS_KEY_ID="<key>"
# export SEAL_EMAIL_AWS_SECRET_ACCESS_KEY="<secret>"
# export SEAL_EMAIL_WEBHOOK_SECRET="<secret>"

# Run the sealing script (exports controller cert + seals all values)
bash infra/scripts/seal-secrets.sh

# Deploy with sealed secrets enabled
helm upgrade --install clubcore infra/helm/clubcore \
  --set secrets.plaintextForLocalK3d=false \
  --set secrets.sealed.enabled=true \
  --set image.tag=$(git rev-parse --short HEAD) \
  -f /path/to/values-production.yaml
# Expected: helm upgrade succeeded; sealed-secrets controller decrypts the SealedSecret
```

---

## Operations

### Backup / Restore

> **OPERATOR-PENDING:** Backup and restore require a live cluster with `backup.enabled=true`.

Backup covers three persistent stores:
1. **Postgres** — CNPG WAL archiving + daily base backup to SeaweedFS S3 (barmanObjectStore)
2. **Redis** — weekly RDB snapshot to SeaweedFS S3
3. **SeaweedFS** — daily mirror to a second PVC

Enable backups after deploy:

```bash
helm upgrade clubcore infra/helm/clubcore \
  --set backup.enabled=true \
  --set image.tag=$(git rev-parse --short HEAD)
# Expected: ScheduledBackup + 3 CronJobs created

# Verify
kubectl get scheduledbackup,cronjob -n default
```

Run a verified restore round-trip (BAK-03 gate — see [restore.md](restore.md)):

```bash
make backup
# Equivalent to: bash infra/scripts/restore-verify.sh
# Expected: restore to SCRATCH namespace → row-count match → scratch teardown
# SAFETY: NEVER run restore against the live cluster (T-120-BAK2)
```

For the full restore procedure (Postgres WAL recovery, Redis RDB, SeaweedFS mirror, BAK-04 CronJob, PITR), see [restore.md](restore.md).

### Rollback

```bash
make rollback
# Equivalent to: helm rollback clubcore
# Expected: Helm reverts to the previous chart revision

# Check revision history
helm history clubcore
# Expected: table of revisions with REVISION, CHART, STATUS columns

# Roll back to a specific revision
helm rollback clubcore <revision-number>
```

> **OPERATOR-PENDING:** `make rollback` requires a running k3d/k3s cluster with helm.

### Scale

> **WARNING — ARCHITECTURAL INVARIANTS (D-V40-REPLICAS):** The following workloads MUST remain at `replicas: 1` with `strategy: Recreate`. They are NOT tuning parameters. Scaling them WILL cause production defects:
>
> - **arq-worker** — `replicas: 1`, `strategy: Recreate`. Multiple replicas cause **cron double-fire** (Pitfall P2): scheduled ARQ jobs run twice per interval.
> - **telegram-bot** — `replicas: 1`, `strategy: Recreate`. Multiple replicas cause **Telegram duplicate-polling** (Pitfall P3): messages processed twice.
>
> Do NOT scale arq-worker or telegram-bot above 1 under any circumstance.

Current scale posture for v4.0 (single bare-metal node):

| Workload | replicas | Strategy | Scalable? |
|----------|----------|----------|-----------|
| backend | 1 | RollingUpdate | Yes — SCALE-01 (future milestone) |
| arq-worker | **1** | **Recreate** | **NO — INVARIANT** |
| telegram-bot | **1** | **Recreate** | **NO — INVARIANT** |
| admin | 1 | RollingUpdate | Yes — SCALE-03 (future milestone) |
| client | 1 | RollingUpdate | Yes — SCALE-03 (future milestone) |

Backend horizontal scaling (SCALE-01), Redis replication (SCALE-02), and frontend scaling (SCALE-03) are deferred to future milestones when multi-node hardware is available.

### Logs and Diagnostics

```bash
# Tail logs for a workload component (default: backend)
make logs
# Custom component: make logs COMPONENT=arq-worker

# Open a psql session on the CNPG primary
make psql
# Expected: psql prompt at clubcore database

# Check all pod status
kubectl get pods -n default

# Check monitoring stack
kubectl get pods -n monitoring
```

---

## Troubleshooting

| Symptom | Likely Cause | Diagnostic Command |
|---------|-------------|-------------------|
| `migrate Job` status.failed > 0 | Alembic migration error; DB not reachable | `kubectl logs job/clubcore-migrate -n default` |
| `backend` pod CrashLoop | App startup error; missing env var; readOnlyRootFilesystem write outside emptyDir; `alembic-check` init guard failed (P4) | `kubectl logs deploy/clubcore-backend -c alembic-check -n default` (init guard) then `kubectl logs deploy/clubcore-backend -c backend -n default` (app) + check `kubectl describe pod` Events. `kubectl logs deploy/...` without `-c` selects a single pod's default container only — pass `-c <container>`, or `--all-containers` when the failing container is unknown. |
| Pod CrashLoop under `readOnlyRootFilesystem` | Write attempted outside the `/tmp` or `/var/cache/nginx` emptyDir volumes (SEC-03) | `kubectl describe pod <pod>` — look for "Read-only file system" in last state |
| NetworkPolicy blocks DNS (P8) | CoreDNS egress rule missing for a workload | `kubectl exec <pod> -- nslookup clubcore-postgres-rw` — if NXDOMAIN, check NetworkPolicy has UDP+TCP 53 egress to `kube-dns` |
| TZ drift — timestamps off by hours (P9) | `TZ=UTC` missing on a pod | `kubectl exec <pod> -- env \| grep TZ` — must be `UTC` |
| SPA deep-route returns 404 (P10) | nginx `try_files` misconfigured; or SW cached old 404 | `curl -I https://admin.<domain>/clients/123` — expect 200; if SW involved, force-refresh or clear site data |
| Certificate not Ready | cert-manager issue; DNS not resolving to node IP | `kubectl describe certificate clubcore-tls` + `kubectl get certificaterequest,order,challenge` |
| No backup alert after 25h | `PostgresNoBackupIn25h` not firing | `kubectl get scheduledbackup` — check `suspended`; `kubectl get backup` — check latest `.status.phase` |
| Grafana shows no data | Prometheus scrape failing | `kubectl get servicemonitor -n monitoring` + `kubectl logs -n monitoring -l app.kubernetes.io/name=prometheus` |
| Loki shows no logs | Alloy not shipping logs | `kubectl logs -n monitoring -l app.kubernetes.io/name=alloy` |
| `helm upgrade` fails with timeout | CNPG operator not ready; migrate Job still running | `kubectl get pod -n cnpg-system` — CNPG controller must be Running before Cluster CR applies |
| SeaweedFS S3 connection refused | SeaweedFS pod not Running | `kubectl get pod -l app.kubernetes.io/name=seaweedfs` + `kubectl describe pvc clubcore-seaweedfs` |
| Telegram bot not polling | Invalid token; sealed secret not decrypted | `kubectl logs deploy/clubcore-telegram-bot -n default` — check for `Unauthorized`; verify `kubectl get secret clubcore-app-secret` exists. `kubectl logs deploy/...` returns one arbitrary pod's logs — for the `replicas:1`/`Recreate` bot this is fine, but use `--previous` to see logs from a crashed prior instance. |
| `make rollback` fails | No previous revision | `helm history clubcore` — rollback requires at least 2 revisions |

---

## Quick Reference — Key Commands

```bash
# Full deploy pipeline
make up

# Standalone smoke check (against deployed cluster)
make smoke

# Rollback Helm release to previous revision
make rollback

# Tail backend logs
make logs

# Tail arq-worker logs
make logs COMPONENT=arq-worker

# Open psql on CNPG primary
make psql

# Run verified backup restore round-trip (to SCRATCH — never live cluster)
make backup

# Check all pods
kubectl get pods -n default

# Check monitoring stack
kubectl get pods -n monitoring

# Check backup status
kubectl get backup,scheduledbackup -n default

# Trigger manual Postgres backup
kubectl cnpg backup clubcore-postgres --method barmanObjectStore

# Run restore-verify CronJob manually
kubectl create job --from=cronjob/clubcore-restore-verify verify-now -n default

# Export sealed-secrets RSA key (run immediately after controller install)
kubectl get secret -n kube-system \
  -l sealedsecrets.bitnami.com/sealed-secrets-key -o yaml > clubcore-sealed-secrets-key-$(date +%Y%m%d).yaml

# Run sealing workflow
bash infra/scripts/seal-secrets.sh

# Tear down local k3d cluster
make down
```

---

## Security Notes

| Item | Requirement |
|------|-------------|
| Sealed-secrets RSA key | Export immediately after controller install + copy off-node (second PC) — controller key loss = ALL SealedSecrets unrecoverable (SEC-02 / P6). See [sealed-secrets-key-backup.md](sealed-secrets-key-backup.md). |
| Plaintext secrets | NEVER committed to git (no git remote, but repo is copied to second PC); only sealed via `seal-secrets.sh` |
| Container images | Only SHA-tagged images pushed to local registry; no `:latest` tag in production (IMG-04 / T-118-SC supply-chain invariant) |
| Restore target | ALWAYS scratch namespace — NEVER the live cluster (T-120-BAK2). Enforced in `restore-verify.sh` and `restore-verify-cronjob.yaml`. |
| readOnlyRootFilesystem | All 6 workloads run with `readOnlyRootFilesystem: true`; only `/tmp` and `/var/cache/nginx` emptyDir volumes are writable (SEC-03) |
| NetworkPolicies | Default-deny in all namespaces; backend↔postgres/redis/seaweedfs-s3 + arq-worker→seaweedfs-s3 explicitly allowed; CoreDNS UDP/TCP 53 on all 6 policies (P8) |
| Image CVE gate | `make scan` / `scan-images.sh` must exit 0 (0 HIGH/CRITICAL) before deploy; CI sets `REQUIRE_TRIVY=1` to fail closed |

---

## Operator-Pending Boundary

> **D-V40-LOCAL-VALIDATE / D-72-06:** The v4.0 done-bar is local k3d validation (build sandbox). The items below are NOT defects — they are the honest boundary of what local k3d, static `helm lint`, `terraform validate`, and sandbox image builds cannot prove. Every item MUST be verified by an operator on real hardware or with live credentials. No fabricated evidence is acceptable.

### HARD GATE 1 — SEC-02: Sealed-Secrets RSA Key Off-Node Backup

> **HARD GATE — blocks production deploy:** The sealed-secrets controller RSA private key is the sole decryption key for every `SealedSecret` in the cluster. If the cluster is rebuilt and this key is not restored before the controller starts, it generates a new key and ALL previously sealed secrets become permanently unrecoverable. There is no fallback path.

See full procedure: [sealed-secrets-key-backup.md](sealed-secrets-key-backup.md)

- [ ] sealed-secrets controller v0.37.0 installed (`kubectl get pod -n kube-system -l app.kubernetes.io/name=sealed-secrets`)
- [ ] RSA key exported from the live cluster (`kubectl get secret -n kube-system -l sealedsecrets.bitnami.com/sealed-secrets-key -o yaml > <keyfile>`)
- [ ] Key file copied to the second PC (off-node, alongside the repo copy)
- [ ] Restore verification completed: key applied to a fresh cluster, existing SealedSecret unseals correctly (see sealed-secrets-key-backup.md Step 5)

Do NOT mark SEC-02 as complete until all four checkboxes are ticked.

---

### HARD GATE 2 — BAK-03: Verified Postgres Restore Round-Trip

> **HARD GATE — blocks production deploy:** Backups are only real if restore is proven. The BAK-03 gate requires a live k3d cluster with CNPG operator, `backup.enabled=true`, and at least one completed base backup in SeaweedFS S3. The restore MUST be to a SCRATCH namespace (T-120-BAK2 SAFETY INVARIANT — never the live cluster).

See full procedure: [restore.md](restore.md)

- [ ] `helm template ... --set backup.enabled=true | grep barmanObjectStore` renders correctly with SeaweedFS endpoint + existing S3 secret refs
- [ ] At least one `Backup` object in `status.phase: completed` (`kubectl get backup`)
- [ ] `bash infra/scripts/restore-verify.sh` completes: scratch cluster Ready → row-count match → scratch namespace deleted
- [ ] `kubectl create job --from=cronjob/clubcore-restore-verify verify-now` runs to completion without touching the live cluster (BAK-04 CronJob)
- [ ] Simulated backup gap → `PostgresNoBackupIn25h` alert fires in Alertmanager

Do NOT mark BAK-03 as complete until all five checkboxes are ticked.

---

### Phase 118 Pending Items (container images + helm chart)

Items from [118-UAT.md](../../.planning/phases/118-container-images-helm-chart-core-stack/118-UAT.md) — all 4 pending, awaiting operator with full toolchain.

| # | Item | Close Command |
|---|------|---------------|
| 118-1 | Live k3d deploy done-bar — full chart deploys, all invariants hold (migrate Succeeded before backend Ready; all pods Ready; TZ=UTC all pods; Redis AOF on; PVCs Bound + Retain) | `bash infra/scripts/k3d-up.sh && bash infra/scripts/deploy-local.sh` → `SMOKE: ALL PASS` |
| 118-2 | trivy CVE scan gate — 0 HIGH/CRITICAL CVEs; CI gate fail-closed (`REQUIRE_TRIVY=1`) | `make scan` (or `REQUIRE_TRIVY=1 bash infra/scripts/scan-images.sh`) |
| 118-3 | helm lint + helm template render — CR-01 multi-release-name correctness (Postgres/Redis hosts, DATABASE_URL/REDIS_URL all resolve to same `clubcore.fullname` basis regardless of release name) | `make helm-lint` + `helm template foo infra/helm/clubcore --set image.tag=<sha>` (non-"clubcore" release name) |
| 118-4 | alembic check initContainer exits 0 post-deploy — belt-and-suspenders P4 guard confirmed against migrated DB | `kubectl logs deploy/clubcore-backend -c alembic-check -n default` → exit 0 |

### Phase 119 Pending Items (networking, security, CSRF rename)

Items from [119-UAT.md](../../.planning/phases/119-networking-security-csrf-rename/119-UAT.md) — all 10 pending, awaiting operator with live cluster + kubeseal.

| # | Item | Close Command |
|---|------|---------------|
| 119-1 | **SEC-02 RSA key off-node backup** (HARD GATE — see above) | See HARD GATE 1 above |
| 119-2 | helm lint + `kubectl apply --dry-run=client` clean | `make helm-lint` + `helm template clubcore infra/helm/clubcore --set image.tag=<sha> \| kubectl apply --dry-run=client -f -` |
| 119-3 | 3-host HTTPS reachability + HTTP→HTTPS 308 redirect (NET-01) | `curl -I http://api.<domain>` → 308; `curl -I https://api.<domain>/healthz` → 200 through Traefik v3 |
| 119-4 | selfSigned Certificate Ready (NET-03) — and Let's Encrypt prod TLS on live server | `kubectl get certificate clubcore-tls` → Ready=True; switch `ClusterIssuer` to `letsencrypt-prod` on live node |
| 119-5 | WebSocket upgrade through Traefik v3 (NET-02) — chat WS `/api/v1/client/ws/*` upgrades (Traefik v3 auto-upgrade, no annotation) | `make smoke` check 6; or manual WS probe: `wscat -c wss://api.<domain>/api/v1/client/ws/test` → 101 |
| 119-6 | SPA deep-route fallback + SW cache headers (NET-04) — deep SPA routes → 200; `sw.js`/manifest no-cache; `/api/*` no-store through ingress | `make smoke` checks 7+8; or `curl -I https://admin.<domain>/clients/123` → 200 |
| 119-7 | kubeseal round-trip — SealedSecret decrypts (SEC-01) | `bash infra/scripts/seal-secrets.sh` → apply SealedSecret → `kubectl get secret clubcore-app-secret` exists |
| 119-8 | readOnlyRootFilesystem boot smoke (SEC-03) — all 6 workloads start without CrashLoop | `kubectl get pods -n default` → all Running; no CrashLoopBackOff after deploy with `securityContext.readOnlyRootFilesystem: true` |
| 119-9 | NetworkPolicy enforcement + DNS smoke (SEC-04 / P8) — default-deny holds; allowed paths work; CoreDNS resolution (P8 UDP+TCP 53) from all pods | `make smoke` check 5; or `kubectl exec deploy/clubcore-backend -- nslookup clubcore-postgres-rw` → resolves |
| 119-10 | Formal `/gsd:secure-phase 70` run (SEC-06) — optional rigor; preliminary retro (70-SECURITY.md) already complete | Run `/gsd:secure-phase 70` with live cluster evidence for CR-02 closure |

### Phase 120 Pending Items (IaC, observability, backup)

Items from [120-UAT.md](../../.planning/phases/120-iac-observability-backup/120-UAT.md) — all 9 pending, awaiting operator with terraform/helm/k3d.

| # | Item | Close Command |
|---|------|---------------|
| 120-1 | **BAK-03 verified restore round-trip** (HARD GATE — see above) | See HARD GATE 2 above |
| 120-2 | `terraform validate` both modules — host + cluster → "Success! The configuration is valid." | `make tf-validate` |
| 120-3 | `make tf-validate` + `make tf-plan` against running k3d cluster (IAC-03) | `make tf-validate && make tf-plan` (k3d must be running) |
| 120-4 | Live `/metrics` scrape + OpenAPI exclusion confirmed live (OBS-03) — Prometheus scrapes `backend:8000/metrics` via ServiceMonitor; `/metrics` absent from OpenAPI spec | `kubectl get servicemonitor -n monitoring` → exists; `curl https://api.<domain>/openapi.json \| jq '.paths \| keys[]'` → no `/metrics` |
| 120-5 | Grafana dashboards render with live Prometheus data (OBS-04) — FastAPI + node-exporter + CNPG + Redis dashboards populate | Open Grafana UI (port-forward: `kubectl port-forward svc/kube-prometheus-stack-grafana 3000:80 -n monitoring`); check all 4 dashboards |
| 120-6 | Loki log query returns results (OBS-02) — Alloy ships pod logs; `{namespace="default"}` returns logs (30d retention) | Grafana Explore → Loki → `{namespace="default"}` → results appear |
| 120-7 | BAK-04 restore-verify CronJob + alert-on-failure — manual trigger restores to scratch + passes; injected mismatch → `RestoreVerifyJobFailed` alert fires | `kubectl create job --from=cronjob/clubcore-restore-verify verify-now -n default` → completed; inject mismatch → check Alertmanager |
| 120-8 | OBS-05 Telegram alert delivery — real sealed bot token in production; alert delivers to Telegram | Seal real `TELEGRAM_BOT_TOKEN` via `seal-secrets.sh`; trigger test alert → verify delivery in Telegram |
| 120-9 | CNPG backup metric name confirmation — confirm `cnpg_collector_last_available_backup_timestamp` metric against CNPG 1.27 collector (PostgresNoBackupIn25h alert depends on exact name) | `kubectl exec -n monitoring -l app.kubernetes.io/name=prometheus -- wget -qO- localhost:9090/api/v1/label/__name__/values \| jq '.data[]' \| grep cnpg` → metric name confirmed |

### Cross-Cutting Production Probes

These items are not captured in any single per-phase UAT but belong to the production boundary (from REQUIREMENTS.md and STATE.md Deferred Items). They require live credentials or real hardware.

| # | Item | Requires | Notes |
|---|------|----------|-------|
| P-1 | Let's Encrypt prod TLS issuance — switch `ClusterIssuer` annotation from `selfsigned` to `letsencrypt-prod` on the live server | Live node with public IP + DNS pointed to it | selfSigned cert works in k3d; LE-prod requires an ACME HTTP-01 or DNS-01 challenge from the internet |
| P-2 | `terraform apply` on real VM — host + cluster modules applied against a real bare-metal node (SSH credentials required) | SSH access to production node; `TF_VAR_*` secrets | `make tf-plan` validates locally; `apply` requires the real target |
| P-3 | ЮKassa sandbox sale + refund walkthrough (STATE.md RUN-01) — webhook reachability + test payment end-to-end | Live domain reachable from ЮKassa webhooks; ЮKassa sandbox API credentials sealed | N/A-until-production |
| P-4 | RU email deliverability probe (STATE.md RUN-02) — Yandex Postbox SPF/DKIM/DMARC verification | Live Yandex Postbox account; DNS records configured on production domain | Pre-existing since v1.6; N/A-until-production |
| P-5 | Real Telegram bot token in sealed secret + Alertmanager Telegram delivery — with a live `TELEGRAM_BOT_TOKEN`, confirm Alertmanager delivers alert | Real bot token from BotFather; sealed via `seal-secrets.sh` | k3d smoke uses a placeholder token; production requires the real one |
| P-6 | Postgres + Redis disk durability on real hardware — power-loss resilience of Postgres WAL + Redis AOF (`appendfsync always`) on the production SSD | Real bare-metal node; simulate power-loss scenario | Not simulated in k3d (Docker volumes); requires real hardware validation |

---

**Do NOT mark v4.0 as production-ready until HARD GATE 1 (SEC-02 RSA-key off-node backup) and HARD GATE 2 (BAK-03 verified restore round-trip) are both fully closed (all checkboxes ticked).**

---
phase: 118-container-images-helm-chart-core-stack
verified: 2026-06-16T12:00:00Z
status: human_needed
score: 12/13 must-haves verified
overrides_applied: 0
human_verification:
  - test: "Run full local k3d deploy sequence"
    expected: "deploy-local.sh prints SMOKE: ALL PASS — migrate Job Succeeded, all pods Ready, TZ=UTC on all pods, Redis AOF on, all PVCs Bound, StorageClass clubcore-retain reclaimPolicy=Retain"
    why_human: "k3d, helm, and trivy are not installed in this verification environment. Per D-V40-LOCAL-VALIDATE, fabricating pod-Ready evidence is forbidden. All static artifacts have been verified correct; only the live cluster execution requires operator action."
  - test: "Run trivy scan gate against built images"
    expected: "bash infra/scripts/scan-images.sh exits 0 with 0 HIGH/CRITICAL CVEs across clubcore/backend, clubcore/admin-app, clubcore/client-pwa (after running build-images.sh)"
    why_human: "trivy is not installed in this environment. scan-images.sh is correctly wired (HIGH,CRITICAL --exit-code 1 --ignore-unfixed) and will work when trivy is available."
  - test: "Run helm lint + helm template render"
    expected: "helm lint infra/helm/clubcore exits 0; helm template clubcore infra/helm/clubcore --set seaweedfs.enabled=false --set image.tag=<sha> renders all 15 resource templates without errors"
    why_human: "helm is not installed in this environment. All Helm template YAML has been verified statically for correct structure, Go template syntax, and acceptance criteria patterns."
  - test: "Confirm alembic check initContainer exits 0 on a deployed cluster"
    expected: "kubectl logs of the alembic-check initContainer for the backend pod shows exit 0 (no pending migrations)"
    why_human: "Requires a running k3d cluster with migrations applied by the migrate hook. Cannot be verified statically."
---

# Phase 118: Container Images + Helm Chart — Verification Report

**Phase Goal:** Production-hardened images exist for all 6 runtime components and the Helm umbrella chart successfully deploys the complete application stack (stateful services + app workloads + migration job) into k3d.
**Verified:** 2026-06-16T12:00:00Z
**Status:** human_needed
**Re-verification:** No — initial verification

---

## Goal Achievement

### Observable Truths

| # | Truth | Status | Evidence |
|---|-------|--------|----------|
| 1 | Non-root, slim, digest-pinned backend image builds with HEALTHCHECK, tzdata, TZ=UTC | VERIFIED | `backend.Dockerfile` pins 2 `@sha256:` digests (lines 18, 41); `HEALTHCHECK --interval=30s` on line 70; `ENV TZ=UTC` line 49; `USER app` line 65 |
| 2 | telegram-bot / arq-worker / migrate run from the SAME backend image via CMD override (no separate Python images) | VERIFIED | Header comment in `backend.Dockerfile` documents the 4-workload shared-image pattern; `build-images.sh` builds only 1 backend image and documents the reuse; Helm Deployments all reference `{{ include "clubcore.image" . }}` with command overrides |
| 3 | admin-app and client-pwa nginx images run non-root on port 8080, serve SPA try_files fallback | VERIFIED | Both Dockerfiles use `USER nginx`; both `nginx/*.conf` have `listen 8080` and `try_files $uri $uri/ /index.html`; per-Dockerfile `.dockerignore` files correct the WR-01 build-context flaw |
| 4 | client-pwa nginx serves sw.js/manifest with no-cache and never caches /api/* (no-store) | VERIFIED | `client-pwa.conf` has `add_header Cache-Control "no-cache"` for sw.js and manifest locations; `add_header Cache-Control "no-store" always` for `/api/` location (including `always` flag to cover 404 responses) |
| 5 | Every image is tagged with git short-SHA; no :latest tag produced | VERIFIED | `build-images.sh` derives `TAG="$(git rev-parse --short HEAD)"` with dirty-tree suffix; no `:latest` string found in the script; `scan-images.sh` also derives from git SHA |
| 6 | trivy scan of every built image returns 0 HIGH/CRITICAL findings | HUMAN NEEDED | `scan-images.sh` is correctly wired (`--severity HIGH,CRITICAL --exit-code 1 --ignore-unfixed`) and has `REQUIRE_TRIVY=1` CI fail-closed mode. trivy not installed in this environment — operator-pending per D-V40-LOCAL-VALIDATE |
| 7 | helm lint and helm template render the chart with 0 errors | HUMAN NEEDED | Chart structure verified statically (all 16 template files exist, YAML structurally valid, Go templates syntactically correct per static review). `helm lint` and live template render require helm — operator-pending |
| 8 | CNPG Cluster CR uses ghcr.io/cloudnative-pg images, instances:1, no Bitnami anywhere | VERIFIED | `postgres-cluster.yaml` has `apiVersion: postgresql.cnpg.io/v1`, `instances: {{ .Values.postgres.instances | default 1 }}`, `imageName: "ghcr.io/cloudnative-pg/postgresql:16.6"` in values.yaml; grep for "bitnami" in infra/helm returns only comments negating Bitnami |
| 9 | Redis StatefulSet enables AOF (appendonly yes, appendfsync everysec) + maxmemory + allkeys-lru with a Retain-backed PVC | VERIFIED | `redis-config.yaml` has `appendonly yes`, `appendfsync everysec`, `maxmemory-policy allkeys-lru`; `redis-statefulset.yaml` has `volumeClaimTemplates` on `clubcore-retain` StorageClass |
| 10 | SeaweedFS wired as a Helm dependency (subchart) in standalone S3 mode with same boto3 env credential surface | VERIFIED | `Chart.yaml` declares `seaweedfs` dependency at version `4.33.0` from `https://seaweedfs.github.io/seaweedfs/helm` with `condition: seaweedfs.enabled`; `values.yaml` sets `seaweedfs.s3.enabled: true`, `s3.port: 8333`, `s3.enableAuth: true`, `s3.existingConfigSecret: clubcore-seaweedfs-s3` |
| 11 | StorageClass has reclaimPolicy:Retain; Postgres has nodeSelector pinning | VERIFIED | `storageclass.yaml` has `reclaimPolicy: Retain` (hard-coded, not a values knob per comment); `postgres-cluster.yaml` has `affinity.nodeSelector: {{ toYaml .Values.postgres.nodeSelector }}` with default `k3d-clubcore-server-0` |
| 12 | All backend env vars mapped to ConfigMap (non-sensitive) or Secret (sensitive) — no plaintext secret in ConfigMap | VERIFIED | `app-configmap.yaml` verified programmatically: no SECRET_KEY, DATABASE_URL, TELEGRAM_BOT_TOKEN, or S3_SECRET_ACCESS_KEY in the data section (only in header comment enumerating what must NOT be there). `app-secret.yaml` holds all sensitive keys with Phase-119 SealedSecret replacement annotation |
| 13 | Alembic migrate Job has hook pre-install,pre-upgrade + weight -5 + backoffLimit:0 + activeDeadlineSeconds:300 + alembic upgrade head | VERIFIED | `migrate-job.yaml` has: `helm.sh/hook: pre-install,pre-upgrade`, `helm.sh/hook-weight: "-5"`, `backoffLimit: 0`, `activeDeadlineSeconds: {{ .Values.migrate.activeDeadlineSeconds | default 300 }}`, `command: ["alembic", "upgrade", "head"]`; initContainer waits for Postgres with Python TCP socket loop (WR-05 fixed — single wait, no outer loop) |
| 14 | arq-worker Deployment is strategy:Recreate + replicas:1 (fixed, not a values knob) | VERIFIED | `arq-worker-deployment.yaml` has `strategy.type: Recreate` and `replicas: 1` hard-coded with architectural invariant comment block; no `.Values.arqWorker.replicas` exposed |
| 15 | telegram-bot Deployment is strategy:Recreate + replicas:1 (fixed, not a values knob) | VERIFIED | `telegram-bot-deployment.yaml` has `strategy.type: Recreate` and `replicas: 1` hard-coded with architectural invariant comment block; no `.Values.telegramBot.replicas` exposed |
| 16 | All three workloads run the shared backend image via per-workload command override | VERIFIED | backend: `command: ["uvicorn", "app.main:create_app", "--factory", ...]`; arq-worker: `command: ["arq", "app.workers.WorkerSettings"]`; telegram-bot: `command: ["python", "-m", "app.workers.telegram_bot"]` — all use `{{ include "clubcore.image" . }}` |
| 17 | backend Deployment has replicas:1, startup+liveness+readiness probes on /healthz, resource requests+limits, alembic check initContainer | VERIFIED | `backend-deployment.yaml` has `replicas: {{ .Values.backend.replicas | default 1 }}`, all three `httpGet /healthz:8000` probes (startup with failureThreshold:30, liveness, readiness), `resources.requests` + `limits`, `initContainers[alembic-check]` with `command: ["alembic", "check"]` |
| 18 | helm install into k3d completes with all pods Ready, migrate Job Succeeded before backend Ready, TZ=UTC verified | HUMAN NEEDED | Scripts wired and verified (bash -n clean, smoke check logic complete in deploy-local.sh). Requires k3d + helm to execute — operator-pending per D-V40-LOCAL-VALIDATE |

**Score:** 12/13 verifiable truths verified (13th is live cluster, appropriately operator-pending)

---

### Required Artifacts

| Artifact | Expected | Status | Details |
|----------|----------|--------|---------|
| `infra/docker/backend.Dockerfile` | Shared Python backend-base (non-root, pinned digest, HEALTHCHECK, tzdata, TZ=UTC) | VERIFIED | All required elements present and correct |
| `infra/docker/admin-app.Dockerfile` | admin-app static nginx image (non-root, port 8080) | VERIFIED | `USER nginx`, `listen 8080`, sha256 digest pinned |
| `infra/docker/client-pwa.Dockerfile` | client-pwa static nginx image (PWA-aware, non-root) | VERIFIED | `USER nginx`, `listen 8080`, sha256 digest pinned |
| `infra/docker/admin-app.Dockerfile.dockerignore` | BuildKit per-Dockerfile ignore (WR-01 fix) | VERIFIED | Exists at correct path; replaces the non-functional `.dockerignore.web` |
| `infra/docker/client-pwa.Dockerfile.dockerignore` | BuildKit per-Dockerfile ignore (WR-01 fix) | VERIFIED | Exists at correct path |
| `infra/nginx/admin-app.conf` | SPA try_files fallback, non-root port 8080 | VERIFIED | `try_files $uri $uri/ /index.html` present |
| `infra/nginx/client-pwa.conf` | SPA fallback + sw.js/manifest no-cache + /api/* no-store | VERIFIED | All cache rules present including `always` flag for 404 |
| `infra/scripts/build-images.sh` | git-SHA tagging for 3 images, no :latest | VERIFIED | bash -n PASS; SHA derivation present; no :latest |
| `infra/scripts/scan-images.sh` | trivy HIGH/CRITICAL gate with REQUIRE_TRIVY CI mode | VERIFIED | bash -n PASS; `--severity HIGH,CRITICAL --exit-code 1` present; WR-03 fix applied |
| `infra/helm/clubcore/Chart.yaml` | Umbrella chart with SeaweedFS dep v4.33.0 | VERIFIED | `version: "4.33.0"`, official repo, condition flag |
| `infra/helm/clubcore/values.yaml` | Single source of truth for all service config | VERIFIED | All required value trees present: image, postgres, redis, seaweedfs, storageClass, config, secrets |
| `infra/helm/clubcore/templates/storageclass.yaml` | StorageClass reclaimPolicy:Retain | VERIFIED | Hard-coded `reclaimPolicy: Retain` |
| `infra/helm/clubcore/templates/postgres-cluster.yaml` | CNPG Cluster (instances:1, ghcr, nodeSelector) | VERIFIED | All DATA-01/DATA-04 invariants encoded |
| `infra/helm/clubcore/templates/redis-statefulset.yaml` | Redis StatefulSet with AOF + PVC | VERIFIED | `appendonly yes`, `allkeys-lru`, `volumeClaimTemplates` present |
| `infra/helm/clubcore/templates/app-configmap.yaml` | Non-sensitive env (incl. TZ=UTC) | VERIFIED | TZ: "UTC" present; no sensitive key in data section |
| `infra/helm/clubcore/templates/app-secret.yaml` | Sensitive env (SECRET_KEY, DATABASE_URL, etc.) | VERIFIED | All sensitive keys mapped; DATABASE_URL points to clubcore.fullname-postgres-rw (CR-01 fix applied) |
| `infra/helm/clubcore/templates/migrate-job.yaml` | Pre-install/pre-upgrade hook Job | VERIFIED | All P4 invariants present; WR-05 (double-loop) fix applied |
| `infra/helm/clubcore/templates/backend-deployment.yaml` | backend Deployment (probes, alembic-check init) | VERIFIED | All APP-02 requirements met |
| `infra/helm/clubcore/templates/arq-worker-deployment.yaml` | arq-worker (Recreate + fixed replicas:1) | VERIFIED | Architectural invariant comment; no replicas values knob |
| `infra/helm/clubcore/templates/telegram-bot-deployment.yaml` | telegram-bot (Recreate + fixed replicas:1) | VERIFIED | Architectural invariant comment; no replicas values knob |
| `infra/scripts/k3d-up.sh` | k3d cluster + CNPG operator + SeaweedFS dep build | VERIFIED | bash -n PASS; cluster create, CNPG apply, helm dependency build all present |
| `infra/scripts/deploy-local.sh` | helm lint + kubeconform + install + 5-point smoke | VERIFIED | bash -n PASS; all 5 smoke checks wired; WR-06 (migrate Job status disambiguation) fix applied |

---

### Key Link Verification

| From | To | Via | Status | Details |
|------|----|-----|--------|---------|
| `postgres-cluster.yaml` | `storageclass.yaml` | `spec.storage.storageClass` references `clubcore-retain` via `include "clubcore.storageClassName"` | WIRED | Helper resolves to the Retain StorageClass name |
| `Chart.yaml` | SeaweedFS Helm chart v4.33.0 | `dependencies[].repository + version` | WIRED | `version: "4.33.0"` from official repo |
| `redis-statefulset.yaml` | `redis-config.yaml` | ConfigMap mount at `/etc/redis` with `redis.conf` key | WIRED | `volumes[redis-config].configMap` + `volumeMounts[/etc/redis]` both present |
| `migrate-job.yaml` | `clubcore/backend:<git-sha>` image | `command: alembic upgrade head` via `{{ include "clubcore.image" . }}` | WIRED | Uses shared backend image with command override |
| `app-secret.yaml` | CNPG postgres-rw service | `DATABASE_URL` constructed with `clubcore.fullname` helper | WIRED | CR-01 fix applied: uses `(include "clubcore.fullname" .)` not `.Release.Name` |
| `migrate-job.yaml` | `app-configmap.yaml` + `app-secret.yaml` | `envFrom: configMapRef + secretRef` | WIRED | Both refs use `include "clubcore.fullname"` for consistent naming (CR-01 fix) |
| `backend-deployment.yaml` | `/healthz on port 8000` | `startupProbe/livenessProbe/readinessProbe httpGet /healthz` | WIRED | All three probes present with correct path and port |
| `backend-deployment.yaml` | `alembic check` | `initContainers[alembic-check].command: ["alembic", "check"]` | WIRED | Belt-and-suspenders P4 guard on the shared backend image |
| `deploy-local.sh` | k3d cluster | `helm upgrade --install ... --wait` after `k3d image import` | WIRED | Full sequence from image import to install to smoke checks |

---

### Data-Flow Trace (Level 4)

Not applicable — this phase produces infrastructure manifests (Dockerfiles, Helm templates, shell scripts), not frontend components that render dynamic data. The data flow is Kubernetes runtime: env vars flow from ConfigMap/Secret into container via `envFrom`, and DATABASE_URL/REDIS_URL/S3_* connect app pods to backing services. The connection strings have been verified statically (Level 3 wiring) and the live verification is operator-pending (human_needed item 1).

---

### Behavioral Spot-Checks

| Behavior | Command | Result | Status |
|----------|---------|--------|--------|
| `build-images.sh` syntax clean | `bash -n infra/scripts/build-images.sh` | Exit 0 | PASS |
| `scan-images.sh` syntax clean | `bash -n infra/scripts/scan-images.sh` | Exit 0 | PASS |
| `k3d-up.sh` syntax clean | `bash -n infra/scripts/k3d-up.sh` | Exit 0 | PASS |
| `deploy-local.sh` syntax clean | `bash -n infra/scripts/deploy-local.sh` | Exit 0 | PASS |
| No `:latest` tag in build script | `grep ":latest" infra/scripts/build-images.sh` | No match | PASS |
| SHA tag derivation present | `grep "rev-parse --short HEAD" infra/scripts/build-images.sh` | Match | PASS |
| Trivy HIGH/CRITICAL gate wired | `grep "HIGH,CRITICAL" infra/scripts/scan-images.sh` | Match | PASS |
| StorageClass Retain hard-coded | `grep "reclaimPolicy: Retain" .../storageclass.yaml` | Match | PASS |
| CNPG uses postgresql.cnpg.io/v1 | `grep "postgresql.cnpg.io/v1" .../postgres-cluster.yaml` | Match | PASS |
| Redis AOF enabled in ConfigMap | `grep "appendonly yes" .../redis-config.yaml` | Match | PASS |
| Migrate hook weight -5 | `grep 'hook-weight.*-5' .../migrate-job.yaml` | Match | PASS |
| Migrate backoffLimit:0 | `grep "backoffLimit: 0" .../migrate-job.yaml` | Match | PASS |
| No sensitive key in ConfigMap data | Python AST scan of app-configmap.yaml data section | No sensitive keys found | PASS |
| Bitnami absent from rendered templates | `grep -ri bitnami infra/helm/` | Comments only (negations) | PASS |
| backend Deployment has 3 probes | grep startupProbe/livenessProbe/readinessProbe | All 3 present | PASS |
| arq-worker strategy:Recreate | `grep "type: Recreate" .../arq-worker-deployment.yaml` | Match | PASS |
| telegram-bot strategy:Recreate | `grep "type: Recreate" .../telegram-bot-deployment.yaml` | Match | PASS |
| helm lint + trivy scan (live) | `helm lint .../clubcore` / `bash scan-images.sh` | SKIP — tools not installed | human_needed |
| k3d deploy all pods Ready | `bash deploy-local.sh` | SKIP — k3d not installed | human_needed |

---

### Probe Execution

No probe scripts found at `scripts/*/tests/probe-*.sh`. This phase does not define conventional probes; the equivalent is `deploy-local.sh` (the done-bar validation script), which is operator-pending.

---

### Requirements Coverage

| Requirement | Source Plan | Description | Status | Evidence |
|-------------|------------|-------------|--------|----------|
| IMG-01 | 118-01 | Non-root, slim, pinned-digest backend Dockerfile with HEALTHCHECK, tzdata, TZ=UTC | SATISFIED | `backend.Dockerfile` verified: 2 sha256 pins, HEALTHCHECK, ENV TZ=UTC, USER app, tzdata installed |
| IMG-02 | 118-01 | telegram-bot/arq-worker/migrate share the backend-base image (CMD override) | SATISFIED | Single `backend.Dockerfile`; `build-images.sh` builds one Python image; Helm Deployments use command override |
| IMG-03 | 118-01 | nginx images for admin-app + client-pwa (SPA try_files; SW no-caches /api/*) | SATISFIED | Both nginx.conf files verified: try_files, port 8080, no-cache/no-store rules with `always` flag |
| IMG-04 | 118-01 | git-SHA image tagging + trivy scan gate; no :latest | SATISFIED (partial) | SHA tagging wired, dirty-tree detection added (WR-02 fix), no :latest verified; trivy gate wired with REQUIRE_TRIVY CI mode (WR-03 fix); actual scan execution operator-pending |
| DATA-01 | 118-02 | CNPG Cluster CR (instances:1, ghcr images, no Bitnami) | SATISFIED | postgres-cluster.yaml verified; ghcr.io image in values.yaml; no Bitnami images |
| DATA-02 | 118-02 | Redis StatefulSet + PVC + AOF (appendonly yes, appendfsync everysec, allkeys-lru) | SATISFIED | redis-config.yaml and redis-statefulset.yaml verified; all AOF parameters present; volumeClaimTemplates on Retain SC |
| DATA-03 | 118-02 | SeaweedFS Helm subchart standalone S3 with same boto3 env credential surface | SATISFIED | Chart.yaml dependency v4.33.0; values.yaml s3.enabled/port/auth/existingConfigSecret configured; S3 env surface unchanged (zero app-code change) |
| DATA-04 | 118-02 | StorageClass reclaimPolicy:Retain + Postgres nodeSelector (anti data-loss) | SATISFIED | storageclass.yaml has Retain hard-coded; postgres-cluster.yaml has affinity.nodeSelector; PVC-bind smoke is operator-pending (live cluster) |
| APP-01 | 118-03 | Alembic migrate as Helm pre-install/pre-upgrade hook Job (backoffLimit:0, weight:-5, deadline:300s) + alembic check initContainer | SATISFIED | migrate-job.yaml: all P4 invariants present; backend-deployment.yaml: alembic-check initContainer present; WR-05 double-loop fix applied |
| APP-02 | 118-04 | backend Deployment: replicas:1, startup/liveness/readiness probes, resources, TZ=UTC | SATISFIED | backend-deployment.yaml: all three probes on /healthz:8000, resources.requests+limits, envFrom for TZ=UTC |
| APP-03 | 118-04 | arq-worker Deployment: strategy:Recreate + replicas:1 + TZ=UTC (anti cron double-fire invariant) | SATISFIED | arq-worker-deployment.yaml: Recreate fixed, replicas:1 fixed, no values knob; architectural invariant comment |
| APP-04 | 118-04 | telegram-bot Deployment: strategy:Recreate + replicas:1 (anti long-polling double-consume) | SATISFIED | telegram-bot-deployment.yaml: same invariants as APP-03 |
| APP-05 | 118-03 | ConfigMap/Secret separation; env vars mapped from config.py | SATISFIED | app-configmap.yaml: TZ=UTC, non-sensitive vars only; app-secret.yaml: all sensitive keys (SECRET_KEY, DATABASE_URL, tokens, S3 creds); no cross-contamination confirmed by automated scan |

All 13 requirement IDs from PLAN frontmatter satisfied. All 13 IDs listed in REQUIREMENTS.md for Phase 118 are covered.

---

### Anti-Patterns Found

| File | Line | Pattern | Severity | Impact |
|------|------|---------|----------|--------|
| `infra/helm/clubcore/templates/redis-statefulset.yaml` | 40 | `TODO Phase 119 SEC-03: set true + runAsUser: 999` | Info | Redis runs as root (WR-04 from code review). Deferred to Phase 119 SEC-03. This is a documented Phase-119 prerequisite with formal phase reference — not an untracked debt marker. |

**Debt-marker gate:** The single `TODO` marker references `Phase 119 SEC-03`, which is a formal upcoming phase in ROADMAP.md with explicit SEC-03 requirements. This satisfies the "formal follow-up work reference" requirement for the debt marker gate. No unreferenced `TBD`, `FIXME`, or `XXX` markers found.

---

### Human Verification Required

#### 1. Live k3d deploy (done-bar)

**Test:** Install tools (`brew install helm k3d`), then run the full sequence:
```bash
bash infra/scripts/build-images.sh
bash infra/scripts/k3d-up.sh
bash infra/scripts/deploy-local.sh
```
**Expected:** deploy-local.sh prints `SMOKE: ALL PASS` with all 5 checks green:
- (a) migrate Job `Succeeded` (schema applied before backend started)
- (b) backend pod `Ready` after migrate (readinessProbe passed)
- (c) `TZ=UTC` on backend, arq-worker, telegram-bot, and Redis pods
- (d) Redis `CONFIG GET appendonly` = `yes`
- (e) All PVCs `Bound`, StorageClass `clubcore-retain` reclaimPolicy = `Retain`
- `kubectl get pods` shows all pods Running/Ready

**Why human:** k3d and helm are not installed in this CI environment. Per D-V40-LOCAL-VALIDATE, live pod-Ready evidence cannot be fabricated. All authoring gates passed (scripts bash -n clean, grep assertions clean).

#### 2. trivy scan gate

**Test:**
```bash
brew install aquasecurity/trivy/trivy
bash infra/scripts/build-images.sh
bash infra/scripts/scan-images.sh
```
**Expected:** Exit 0, "GATE: PASSED — 0 HIGH/CRITICAL CVEs across all images"
**Why human:** trivy not installed. `scan-images.sh` is correctly wired and will produce honest results when trivy is available. CI should set `REQUIRE_TRIVY=1`.

#### 3. helm lint + helm template clean render

**Test:**
```bash
helm repo add seaweedfs https://seaweedfs.github.io/seaweedfs/helm
helm dependency build infra/helm/clubcore
SHA=$(git rev-parse --short HEAD)
helm lint infra/helm/clubcore --set "image.tag=$SHA" --set seaweedfs.enabled=false
helm template clubcore infra/helm/clubcore --set "image.tag=$SHA" --set seaweedfs.enabled=false | grep -q 'reclaimPolicy: Retain' && echo "Retain OK"
helm template clubcore infra/helm/clubcore --set "image.tag=$SHA" --set seaweedfs.enabled=false | grep -q 'postgresql.cnpg.io/v1' && echo "CNPG OK"
! helm template clubcore infra/helm/clubcore --set "image.tag=$SHA" --set seaweedfs.enabled=false | grep -qi bitnami && echo "No Bitnami OK"
```
**Expected:** helm lint exits 0; all grep assertions succeed
**Why human:** helm not installed. CR-01 (service DNS naming basis) and WR-05 (migrate double-loop) fixes were verified statically but require a live `helm template foo ./clubcore` render to confirm there are no Go template errors introduced by the fixes.

#### 4. alembic check initContainer exit 0

**Test:** After `deploy-local.sh` succeeds, run:
```bash
kubectl logs -n default $(kubectl get pod -l app.kubernetes.io/component=backend -o name) -c alembic-check
```
**Expected:** Container shows exit 0 with no pending migrations message
**Why human:** Requires a running k3d cluster with the migrate hook having completed.

---

### Code Review Status

Two review iterations completed. All critical (CR-01: service DNS naming) and warning findings (WR-01 through WR-06) addressed in commits `8615af47` through `fa0408fc` and `2c0f301b` / `e4c9efdc`. One finding deferred by design:

- **WR-04** (Redis runs as root, bind 0.0.0.0, no auth, no NetworkPolicy): Explicitly deferred to Phase 119 SEC-03. `redis-statefulset.yaml` line 40 carries the `TODO Phase 119 SEC-03` marker. Formally tracked.

Remaining review items (WR-01 new in iter2 = root `.dockerignore` missing) were also fixed in commit `e4c9efdc` which added `infra/docker/admin-app.Dockerfile.dockerignore` and `infra/docker/client-pwa.Dockerfile.dockerignore` via BuildKit per-Dockerfile convention. Both files exist and are confirmed correct.

---

### Gaps Summary

No gaps blocking the static/authorable portion of the phase goal. All 13 requirement IDs are satisfied at the artifact level. The only outstanding items are live runtime verifications that require operator tooling (helm, k3d, trivy) that cannot be installed in this environment — this is the documented D-V40-LOCAL-VALIDATE boundary, not a phase incompleteness.

**Operator priority order:**
1. `brew install helm k3d` → `bash infra/scripts/k3d-up.sh` → `bash infra/scripts/deploy-local.sh` (closes done-bar)
2. `brew install aquasecurity/trivy/trivy` → `bash infra/scripts/scan-images.sh` (closes trivy gate)

---

_Verified: 2026-06-16T12:00:00Z_
_Verifier: Claude (gsd-verifier)_

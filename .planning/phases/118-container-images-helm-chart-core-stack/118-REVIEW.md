---
phase: 118-container-images-helm-chart-core-stack
reviewed: 2026-06-16T00:00:00Z
depth: standard
files_reviewed: 14
files_reviewed_list:
  - infra/docker/backend.Dockerfile
  - infra/docker/admin-app.Dockerfile
  - infra/docker/client-pwa.Dockerfile
  - infra/nginx/admin-app.conf
  - infra/nginx/client-pwa.conf
  - infra/helm/clubcore/templates/app-secret.yaml
  - infra/helm/clubcore/templates/app-configmap.yaml
  - infra/helm/clubcore/templates/migrate-job.yaml
  - infra/helm/clubcore/templates/postgres-cluster.yaml
  - infra/helm/clubcore/templates/redis-statefulset.yaml
  - infra/scripts/build-images.sh
  - infra/scripts/scan-images.sh
  - infra/scripts/k3d-up.sh
  - infra/scripts/deploy-local.sh
findings:
  critical: 1
  warning: 6
  info: 4
  total: 11
status: issues_found
---

# Phase 118: Code Review Report

**Reviewed:** 2026-06-16
**Depth:** standard
**Files Reviewed:** 14 (plus cross-referenced: values.yaml, _helpers.tpl, Chart.yaml, redis-config.yaml, redis-service.yaml, storageclass.yaml, postgres-app-secret.yaml, backend-deployment.yaml, seaweedfs-s3-secret.yaml, seaweedfs-values.yaml, .dockerignore, .dockerignore.web)
**Status:** issues_found

## Summary

This is a pure-infrastructure phase: three container images, two nginx configs, a Helm umbrella chart, and four bash orchestration scripts. Container hardening is largely solid — all base images are digest-pinned, all app containers run non-root, frozen lockfiles are used, and the trivy gate is wired. Secret/ConfigMap separation is correct: no sensitive key leaks into the ConfigMap, and the plaintext-placeholder-for-local-k3d pattern is documented and intentional (Phase 119 seals it), so it is not flagged as a leak.

The most serious problem is a latent service-discovery bug: half the chart names resources with `Release.Name` and the other half with the `clubcore.fullname` helper, which only collapse to the same string when the release is literally named `clubcore`. The deploy scripts hard-code that release name, so local validation passes and the bug stays hidden. Several secondary issues weaken the stated supply-chain/secret-exclusion guarantees (the web `.dockerignore` is never applied by Docker) and the deploy-time tag/manifest contract.

## Narrative Findings (AI reviewer)

## Critical Issues

### CR-01: Service DNS breaks for any release name not containing "clubcore"

**File:** `infra/helm/clubcore/templates/app-secret.yaml:55`, `infra/helm/clubcore/templates/app-configmap.yaml:49`, `infra/helm/clubcore/templates/migrate-job.yaml:110,113,141,143`, `infra/helm/clubcore/templates/backend-deployment.yaml:89,91`

**Issue:** The chart is internally inconsistent about how it derives resource names. Stateful resources and their services are named with the `clubcore.fullname` helper:

- CNPG `Cluster` → `{{ include "clubcore.fullname" . }}-postgres` ⇒ CNPG auto-creates service `<fullname>-postgres-rw` (`postgres-cluster.yaml:27`)
- Redis `Service` and `StatefulSet.serviceName` → `{{ include "clubcore.fullname" . }}-redis` (`redis-service.yaml:16`, `redis-statefulset.yaml:24`)

But the connection strings and `envFrom` references that must point at those services are built from `.Release.Name`:

- `DATABASE_URL: postgresql+asyncpg://app:%s@%s-postgres-rw:5432/clubcore` using `.Release.Name` (`app-secret.yaml:55`)
- `REDIS_URL: redis://%s-redis:6379/0` using `.Release.Name` (`app-configmap.yaml:49`)
- migrate-job wait-loop polls `{{ include "clubcore.fullname" . }}-postgres-rw` (correct) but the `DATABASE_URL` it loads from the Secret points at `{{ .Release.Name }}-postgres-rw` (wrong) — they disagree with each other inside the same Job.

Per `_helpers.tpl:13-24`, `fullname` returns `.Release.Name` only when `Release.Name` *contains* the chart name `clubcore`; otherwise it returns `<Release.Name>-clubcore`. So with `helm install foo ./clubcore`:
- Postgres service = `foo-clubcore-postgres-rw`, but `DATABASE_URL` host = `foo-postgres-rw` → DNS NXDOMAIN, backend and migrate Job cannot connect.
- Redis service = `foo-clubcore-redis`, but `REDIS_URL` host = `foo-redis` → ARQ/cache/session backend cannot connect.

This is masked locally only because `deploy-local.sh:37` and `k3d-up.sh:27` hard-code `RELEASE_NAME="clubcore"`. Any other release name (multi-tenant install, staging side-by-side, or a Phase-119 rename) silently produces a non-functional cluster.

**Fix:** Use one naming source consistently. Since the services are named via `clubcore.fullname`, the connection strings must use the same helper:
```yaml
# app-secret.yaml
DATABASE_URL: {{ printf "postgresql+asyncpg://app:%s@%s-postgres-rw:5432/clubcore" .Values.postgres.password (include "clubcore.fullname" .) | quote }}

# app-configmap.yaml
REDIS_URL: {{ .Values.config.redisUrl | default (printf "redis://%s-redis:6379/0" (include "clubcore.fullname" .)) | quote }}
```
Also align the ConfigMap/Secret object names (`{{ .Release.Name }}-config`, `-app-secret`) and all `envFrom` references to a single helper, and make `postgres.appSecretName` / `s3` secret names release-scoped rather than the hard-coded literal `clubcore-...`. Add a `helm template foo ./clubcore` (non-"clubcore" release name) render check to the deploy gate so this divergence cannot regress.

## Warnings

### WR-01: Web `.dockerignore` is never applied — `.env*`/`.git` exclusion (T-118-03) not enforced

**File:** `infra/docker/.dockerignore.web:1`, `infra/docker/admin-app.Dockerfile:9`, `infra/docker/client-pwa.Dockerfile:10`

**Issue:** Docker only honors a `.dockerignore` located at the root of the build context, or (with BuildKit) a file named `<dockerfile-basename>.dockerignore` next to the Dockerfile *and resolved relative to the context*. The frontend images build with context = repo root (`build-images.sh:51,61`) and the Dockerfile lives at `infra/docker/admin-app.Dockerfile`. A file at `infra/docker/.dockerignore.web` matches none of these rules and is silently ignored. The comment claims it enforces T-118-03 ("Environment files never in build context"), but in practice the entire repo root — including `.git/`, root `.env*`, and every `node_modules/` — is sent to the daemon. Secrets are not *baked into image layers* (the Dockerfiles `COPY` only explicit paths), so this is not a CR, but the stated supply-chain/secret-exclusion guarantee is not actually realized, and the large context slows every build.

**Fix:** Either place the ignore rules in a real `.dockerignore` at the repo root, or rename per BuildKit convention so it resolves against the context — e.g. `infra/docker/admin-app.Dockerfile.dockerignore` and `client-pwa.Dockerfile.dockerignore` (with `# syntax=docker/dockerfile:1.7` already present, BuildKit looks up `<path-to-Dockerfile>.dockerignore`). Verify by adding a root `.env` and confirming it is absent from the build context (`docker build --no-cache` + check it is not COPYable).

### WR-02: build-images.sh and Helm default tag can silently disagree (dirty tree / uncommitted build)

**File:** `infra/scripts/build-images.sh:28`, `infra/scripts/deploy-local.sh:77`, `infra/helm/clubcore/values.yaml:14`

**Issue:** Both scripts derive the tag from `git rev-parse --short HEAD`, but neither checks for a dirty working tree. If images are built from uncommitted changes, the tag reflects the parent commit while the image contents do not — two different image builds can share one tag, defeating the IMG-04 "immutable tag" intent. Separately, `values.yaml:14` hard-codes `tag: "6e42d106"`; `migrate-job.yaml` / `backend-deployment.yaml` consume `.Values.image.tag` directly. `deploy-local.sh` always passes `--set image.tag=$TAG`, but anyone running `helm install` manually (or `helm template` for the kubeconform gate without `--set`, e.g. CI on a different checkout) gets the stale pinned tag, pulling/failing on an image that may not exist locally.

**Fix:** In both scripts, fail or append `-dirty` when `! git diff --quiet || ! git diff --cached --quiet`. Consider making `values.yaml` `image.tag` empty with a `required` guard, or document that it must be overridden, so a stale literal can never be silently deployed.

### WR-03: scan-images.sh exits 0 when trivy is absent — gate is bypassable

**File:** `infra/scripts/scan-images.sh:35-53`

**Issue:** When `trivy` is not on PATH the script prints an "OPERATOR-PENDING" warning and `exit 0`. If `scan-images.sh` is wired into an automated pipeline (the header and `build-images.sh:75` present it as the next step), a CI runner without trivy installed turns the HIGH/CRITICAL CVE gate into a no-op while reporting success. The D-V40-LOCAL-VALIDATE "no fabricated evidence" intent is honored for a human operator, but for an automated gate this is a security control that silently fails open.

**Fix:** Add an opt-in strict mode, e.g. `if [[ "${REQUIRE_TRIVY:-0}" == "1" ]]; then err "trivy required"; fi` before the soft-exit, and have any CI invocation set `REQUIRE_TRIVY=1`. At minimum emit the warning to stderr so it is visible in failing-fast pipelines.

### WR-04: Redis is reachable cluster-wide with no auth and `bind 0.0.0.0`

**File:** `infra/helm/clubcore/templates/redis-config.yaml:38-45`, `infra/helm/clubcore/templates/redis-statefulset.yaml:39-40`

**Issue:** `redis.conf` sets `bind 0.0.0.0` with no `requirepass` and `protected-mode` left at default (which Redis disables once an explicit `bind` is present). The headless Service exposes 6379 cluster-wide and there is no NetworkPolicy. Any pod in the cluster — including a compromised frontend or a future tenant — can read/write/`FLUSHALL` the session/cache/queue store. `runAsNonRoot: false` (`redis-statefulset.yaml:40`) additionally leaves the Redis container running as root. Both are explicitly tagged as Phase-119 deferrals in-code, so this is a documented gap rather than an oversight, but it is a real exposure if anything ships before Phase 119 hardening lands.

**Fix:** Track as a hard Phase-119 prerequisite: add `requirepass` from a Secret (and `REDIS_URL` with credentials), set `runAsNonRoot: true` + `runAsUser: 999`, and add a NetworkPolicy restricting 6379 to backend/arq pods. Until then, do not expose this cluster to any untrusted workload.

### WR-05: migrate-job double-loops the postgres wait with conflicting deadlines

**File:** `infra/helm/clubcore/templates/migrate-job.yaml:108-127`

**Issue:** The init wait runs `until python3 -c "...inner 240s deadline loop..."; do sleep 1; done`. The inner Python already loops to a 240s deadline and `sys.exit(1)` on timeout; the outer `until ... do sleep 1; done` then *retries the whole 240s Python loop forever* on that non-zero exit, relying solely on the Job's `activeDeadlineSeconds: 300` to terminate. With `set -e` active this is the only thing that stops an unreachable-Postgres Job from hanging at the outer loop. The two timeout mechanisms (inner 240s, Job 300s) overlap confusingly and the outer `until` is logically dead code on the success path and a near-infinite retry on the failure path.

**Fix:** Drop the outer `until/do/done` and run the Python wait once — let its own deadline + the Job `activeDeadlineSeconds` govern. Ensure the inner deadline (240s) is comfortably below `activeDeadlineSeconds` (300s) so the Python timeout message reaches the logs before the Job is force-killed.

### WR-06: deploy-local.sh smoke check (a) treats missing/false Job status as a hard fail but swallows wait errors

**File:** `infra/scripts/deploy-local.sh:136-148`

**Issue:** `kubectl wait job ... --for=condition=Complete ... 2>/dev/null || true` discards both the timeout and any error (e.g. the Job condition becoming `Failed`). The subsequent `status.succeeded` read defaults to `"0"` via `|| echo "0"`, so a *Failed* migration and a *still-running* migration both surface identically as `succeeded = '0'`. With `set -e`, the `|| true` is required to avoid aborting, but it also masks the distinct "Job Failed" signal that an operator most needs. The smoke summary then reports a generic failure without the underlying Job condition.

**Fix:** After the wait, also read `.status.failed` and `.status.conditions[?(@.type=="Failed")]` and report the distinction (Failed vs Timed-out vs Running). Capture `kubectl wait` stderr to a log rather than `2>/dev/null` so the operator sees why it failed.

## Info

### IN-01: HEALTHCHECK urlopen has no explicit timeout

**File:** `infra/docker/backend.Dockerfile:71`

**Issue:** `urllib.request.urlopen('http://127.0.0.1:8000/healthz')` has no `timeout` argument; it relies entirely on the `HEALTHCHECK --timeout=3s` to bound a hung connection. If Docker's timeout enforcement is loose under load, the probe process can linger.

**Fix:** Pass an explicit timeout: `urllib.request.urlopen('http://127.0.0.1:8000/healthz', timeout=2)`.

### IN-02: build-images.sh comments describe React 18, project is React 19

**File:** `infra/scripts/build-images.sh:14-15`

**Issue:** Comments say "React 18 + TanStack" / "React 18 + vite-plugin-pwa", but CLAUDE.md and package manifests specify React 19. Stale documentation only; no behavioral impact.

**Fix:** Update the comments to React 19.

### IN-03: redis-statefulset comment claims TZ via env but P9 contract is envFrom ConfigMap

**File:** `infra/helm/clubcore/templates/redis-statefulset.yaml:54-57`

**Issue:** Redis sets `TZ=UTC` via an inline `env` entry while every other workload gets `TZ` from the `clubcore-config` ConfigMap (the documented P9 mechanism). This works, but it is a second source of truth for the same invariant; if the ConfigMap value ever changes, Redis will drift. The smoke check `check_tz`/Redis branch in `deploy-local.sh:185-199` reads `env` so it still passes either way.

**Fix:** Optionally consume `TZ` from the ConfigMap via `envFrom` for consistency, or add a comment noting the intentional divergence (alpine Redis image without the ConfigMap mounted).

### IN-04: app-secret/app-configmap header comments list "YooKassa keys" but no such key is templated

**File:** `infra/helm/clubcore/templates/app-configmap.yaml:9`, `infra/helm/clubcore/templates/app-secret.yaml`

**Issue:** The ConfigMap invariant comment enumerates "YooKassa keys" among sensitive keys that must live in the Secret, but neither template defines any YooKassa key. Either a payment-provider secret was dropped from this phase or the comment is aspirational. Worth confirming the backend does not expect `YOOKASSA_*` env vars at startup (config.py), since a missing required SecretStr would fail-fast the pods.

**Fix:** Verify backend config requirements; either add the YooKassa keys to `app-secret.yaml` (sensitive) or remove the misleading reference from the comment.

---

_Reviewed: 2026-06-16_
_Reviewer: Claude (gsd-code-reviewer)_
_Depth: standard_

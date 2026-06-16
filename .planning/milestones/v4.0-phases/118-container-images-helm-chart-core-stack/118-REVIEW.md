---
phase: 118-container-images-helm-chart-core-stack
reviewed: 2026-06-16T00:00:00Z
depth: standard
iteration: 2
files_reviewed: 19
files_reviewed_list:
  - infra/helm/clubcore/templates/app-configmap.yaml
  - infra/helm/clubcore/templates/app-secret.yaml
  - infra/helm/clubcore/templates/seaweedfs-s3-secret.yaml
  - infra/helm/clubcore/templates/migrate-job.yaml
  - infra/helm/clubcore/templates/postgres-cluster.yaml
  - infra/helm/clubcore/templates/redis-statefulset.yaml
  - infra/helm/clubcore/templates/redis-service.yaml
  - infra/helm/clubcore/templates/backend-deployment.yaml
  - infra/helm/clubcore/templates/arq-worker-deployment.yaml
  - infra/helm/clubcore/templates/telegram-bot-deployment.yaml
  - infra/helm/clubcore/templates/_helpers.tpl
  - infra/helm/clubcore/values.yaml
  - infra/docker/backend.Dockerfile
  - infra/docker/admin-app.Dockerfile
  - infra/docker/client-pwa.Dockerfile
  - infra/scripts/build-images.sh
  - infra/scripts/scan-images.sh
  - infra/scripts/deploy-local.sh
  - infra/scripts/k3d-up.sh
findings:
  critical: 0
  warning: 2
  info: 3
  total: 5
status: issues_found
---

# Phase 118: Code Review Report (Re-review — Iteration 2)

**Reviewed:** 2026-06-16
**Depth:** standard
**Files Reviewed:** 19
**Status:** issues_found (no new Critical / no regression in the CR-01 fix)

## Summary

This is iteration 2, focused on confirming the iteration-1 fixes are internally
consistent and introduced no regressions. The primary goal — verifying the CR-01
service-DNS-divergence fix — is **CONFIRMED RESOLVED**. The chart now names stateful
services, builds `DATABASE_URL` / `REDIS_URL`, and runs the migrate wait-loop on one
consistent basis, and `helm install <any-name> ./clubcore` is correct.

**CR-01 trace (the load-bearing verification):**

- **Postgres leg** — CNPG `Cluster` is named `{{ include "clubcore.fullname" . }}-postgres`
  (`postgres-cluster.yaml:27`). CNPG derives the `-rw` service from the cluster name,
  so the read-write service is `<fullname>-postgres-rw`. `DATABASE_URL` in
  `app-secret.yaml:60` is built with `(include "clubcore.fullname" .)` → host
  `<fullname>-postgres-rw`. The migrate `initContainer` wait-loop (`migrate-job.yaml:110,120`)
  also targets `<fullname>-postgres-rw`. All three agree. ✓
- **Redis leg** — StatefulSet, headless Service, and `serviceName` all use
  `<fullname>-redis` (`redis-statefulset.yaml:19,24`, `redis-service.yaml:16`).
  `REDIS_URL` in `app-configmap.yaml:51` is built with `(include "clubcore.fullname" .)`
  → `redis://<fullname>-redis:6379/0`. All agree. ✓
- **SeaweedFS leg** — `S3_ENDPOINT_URL` (`app-configmap.yaml:59`) and the S3 identity
  Secret name (`seaweedfs-s3-secret.yaml:34`) both use `.Release.Name`, which is the
  **correct** basis for a subchart dependency (a subchart derives its own resource names
  from `.Release.Name`, not the parent's `fullname`). The fixer correctly did NOT convert
  these to `clubcore.fullname` — doing so would have re-introduced divergence against the
  subchart's own naming. `seaweedfs.s3.existingConfigSecret` is a fixed literal read
  identically by both the producing Secret and the subchart lookup, so they agree for any
  release name. ✓

The mixed basis (`fullname` for first-party resources, `Release.Name` for the subchart)
is internally consistent because each reference matches the naming basis of the resource
it points at. No CR-01 regression.

**Other iteration-1 fixes confirmed:**

- **`clubcore.image` required-tag guard** (`_helpers.tpl:80-83`) — `required` on
  `.Values.image.tag` fires before `printf`, so a missing tag fails loudly. Used uniformly
  across migrate Job, backend/arq/telegram Deployments. `values.yaml:18` keeps `tag: ""`.
  `deploy-local.sh:103,131` and the `helm lint` path all pass `--set image.tag=${TAG}`. ✓
- **scan-images.sh fail-closed-in-CI** (`scan-images.sh:56-67`) — `REQUIRE_TRIVY=1`
  branch exits 1 when trivy is absent (before the operator-pending `exit 0`); diagnostics
  on stderr. `set -euo pipefail` present. ✓
- **migrate single-wait-loop** (`migrate-job.yaml:108-134`) — the outer shell `until`
  loop was removed; the Python wait runs once with its own 240s deadline, `set -e` fails
  the initContainer on non-zero exit, and the Job `activeDeadlineSeconds: 300` is the outer
  backstop (240 < 300, so the timeout message reaches logs before force-kill). Logic is
  sound; both the success path (`sys.exit(0)`) and failure path (`sys.exit(1)`) are reachable. ✓

Remaining issues are NEW quality/reliability concerns (the frontend build context lacks a
`.dockerignore`) plus latent multi-tenancy items — none block this phase given the local-k3d
scope and the explicit Phase-119 deferrals.

## Known / Deferred (NOT re-flagged as new Criticals)

- **WR-04 (Redis runs as root, `bind 0.0.0.0`, no auth, no NetworkPolicy)** — explicit
  Phase-119 deferral (SEC-03 + NET + sealed-secrets). `redis-config.yaml:38-49` and
  `redis-statefulset.yaml:40` carry TODO Phase-119 markers. Recorded as a known item, not a
  new blocker.
- **Plaintext secret placeholders in `values.yaml`** (postgres password, secretKey, S3 keys,
  telegram token) — documented LOCAL-k3d-only pattern; every Secret template carries the
  `clubcore.io/replace-with-sealed-secret: "phase-119-sec-01"` annotation. Not a leak.
- **Render verification (helm / k3d / trivy / kubeconform)** — tooling not installed in this
  environment; reasoned statically. All findings below derive from source inspection, not a
  live render.

## Warnings

### WR-01: Frontend image builds ship the host `node_modules` / `.git` / `.planning` into the build context (no root `.dockerignore`)

**File:** `infra/docker/admin-app.Dockerfile:39`, `infra/docker/client-pwa.Dockerfile:40`, `infra/scripts/build-images.sh:60,70` (build context = repo root)
**Issue:** Both frontend Dockerfiles use the **repo root** as their build context
(`build-images.sh` passes `"${REPO_ROOT}"`). There is **no root `.dockerignore`** — only
`apps/backend/.dockerignore` exists, and it does not apply to the root context. Two distinct
problems result:

1. **Build-corruption risk (reliability).** After the frozen-lockfile `pnpm install`, the
   Dockerfiles run `COPY apps/admin-app/ ./apps/admin-app/` and
   `COPY packages/api-client/ ./packages/api-client/`. With no ignore rules, these COPY
   commands pull in the developer's **host** `node_modules` (verified present:
   `apps/admin-app/node_modules` = 357M, `packages/api-client/node_modules`) and host `dist/`
   directories on top of the clean in-image install. A macOS-built `node_modules` copied into
   `node:20-alpine` can shadow the clean install with platform-mismatched native binaries and
   stale workspace symlinks — a classic "passes on a fresh checkout, breaks from a dev
   machine" failure. This was not caught because the review environment cannot run `docker build`.
2. **Context bloat (build hygiene).** The daemon receives `node_modules` (796M root +
   357M admin-app), `.git` (72M), and `.planning` (27M) on every frontend build — ~1.2GB of
   irrelevant context that also busts the layer cache whenever any of those change.

**Fix:** Add a root `.dockerignore` (the build context root) so the frontend builds are
reproducible regardless of host working-tree state:
```gitignore
# /.dockerignore — applies to repo-root build context (frontend images)
**/node_modules
**/dist
**/.venv
.git
.planning
**/.turbo
**/coverage
**/*.log
.env*
```
The backend image is unaffected (it builds from `apps/backend/` and already has its own
`.dockerignore`), but consider adding `**/node_modules` + `dist` symmetry there as well.

### WR-02: First-party stateful Secrets / StorageClass use fixed literal names, so two releases collide in one namespace

**File:** `infra/helm/clubcore/values.yaml:48,128,27`; `postgres-app-secret.yaml:24`; `seaweedfs-s3-secret.yaml:34`; `storageclass.yaml:14`
**Issue:** The CR-01 fix made the app config/services release-name-correct, but three
resource names remain **hardcoded literals** rather than `fullname`/`Release.Name`-scoped:
`postgres.appSecretName: clubcore-postgres-app`, `seaweedfs.s3.existingConfigSecret:
clubcore-seaweedfs-s3`, and `storageClass.name: clubcore-retain`. These are internally
consistent (producer and consumer read the same literal), so they do not break the
"any release name" goal for a single install — but installing **two** releases of this
chart into the same namespace would collide on the Postgres app Secret and the SeaweedFS
identity Secret, and the cluster-scoped StorageClass collides even across different
namespaces. For the documented single-node v4.0 scope this is latent, not active — hence
Warning, not Blocker.
**Fix:** Either document the single-release-per-cluster constraint explicitly, or derive the
namespaced Secret names from `clubcore.fullname` (and gate StorageClass creation behind a
`storageClass.create` flag so the shared cluster-scoped object is created once):
```yaml
# values.yaml
postgres:
  appSecretName: ""   # empty = derive {{ include "clubcore.fullname" . }}-postgres-app
```
```yaml
# postgres-app-secret.yaml
name: {{ .Values.postgres.appSecretName | default (printf "%s-postgres-app" (include "clubcore.fullname" .)) }}
```

## Info

### IN-01: `deploy-local.sh` smoke checks hardcode `RELEASE_NAME="clubcore"` and `${RELEASE_NAME}-retain`

**File:** `infra/scripts/deploy-local.sh:37,147,248-253`
**Issue:** The smoke checks reference `${RELEASE_NAME}-migrate` and the StorageClass
`${RELEASE_NAME}-retain`. The StorageClass check only passes because `RELEASE_NAME=clubcore`
*coincidentally* equals `storageClass.name=clubcore-retain`; if the release were renamed the
StorageClass lookup (`clubcore-retain`, a fixed literal) would diverge from
`${RELEASE_NAME}-retain`. This is a local-script convenience constant, not a chart defect,
but the coupling is fragile.
**Fix:** Read the StorageClass name from values (`helm get values` / a `--set` echo) or pin a
`STORAGECLASS_NAME="clubcore-retain"` constant separate from `RELEASE_NAME`.

### IN-02: tag-derivation logic duplicated across three scripts; `scan-images.sh` omits the dirty suffix

**File:** `infra/scripts/build-images.sh:32-37`, `infra/scripts/deploy-local.sh:79-83`, `infra/scripts/scan-images.sh:26`
**Issue:** The `<sha>` / `<sha>-dirty` tag logic is duplicated in three scripts. `build` and
`deploy-local` both reproduce the dirty-suffix branch; `scan-images` derives only the bare
SHA (`TAG="${TAG:-$(git rev-parse --short HEAD)}"`) with no dirty suffix. On a dirty tree,
`build-images.sh` produces `clubcore/backend:<sha>-dirty`, but a bare `scan-images.sh` (no
`TAG=` override) would scan `clubcore/backend:<sha>` — a non-existent tag. The header comments
tell the operator to pass `TAG=` explicitly, so this is a documented foot-gun rather than a bug.
**Fix:** Factor tag derivation into a shared `infra/scripts/_tag.sh` sourced by all three, so
the dirty-suffix rule is defined once.

### IN-03: Header comment drift — frontends are React 19, `build-images.sh` says "React 18"

**File:** `infra/scripts/build-images.sh:14-15`
**Issue:** Comments describe the frontends as "React 18 + TanStack". Per CLAUDE.md the stack is
React 19.2.5. Cosmetic, but worth correcting to avoid future confusion.
**Fix:** Update the comment to "React 19".

---

_Reviewed: 2026-06-16_
_Reviewer: Claude (gsd-code-reviewer)_
_Depth: standard (iteration 2 re-review)_

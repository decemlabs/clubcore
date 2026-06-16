---
phase: 118-container-images-helm-chart-core-stack
fixed_at: 2026-06-16T00:00:00Z
review_path: .planning/phases/118-container-images-helm-chart-core-stack/118-REVIEW.md
iteration: 1
findings_in_scope: 7
fixed: 6
skipped: 1
status: all_fixed
---

# Phase 118: Code Review Fix Report

**Fixed at:** 2026-06-16
**Source review:** .planning/phases/118-container-images-helm-chart-core-stack/118-REVIEW.md
**Iteration:** 1

**Summary:**
- Findings in scope: 7 (1 critical + 6 warning)
- Fixed: 6
- Skipped: 1 (WR-04 — explicit Phase-119 deferral)

> Tooling note: helm / k3d / trivy / kubeconform are not installed in this
> environment, so `helm template`/`helm lint`/`bash` smoke renders could NOT be
> executed. Helm template correctness was verified statically (reasoning through
> both `helm install clubcore` and `helm install foo` render paths, Go-template
> brace balance) and all bash edits passed `bash -n`. The CR-01 and WR-05 fixes
> are flagged "requires human verification" — confirm with a real
> `helm template foo ./clubcore` render and a k3d deploy before sign-off.

## Fixed Issues

### CR-01: Service DNS breaks for any release name not containing "clubcore"

**Files modified:** `infra/helm/clubcore/templates/app-secret.yaml`, `infra/helm/clubcore/templates/app-configmap.yaml`, `infra/helm/clubcore/templates/migrate-job.yaml`, `infra/helm/clubcore/templates/backend-deployment.yaml`, `infra/helm/clubcore/templates/arq-worker-deployment.yaml`, `infra/helm/clubcore/templates/telegram-bot-deployment.yaml`, `infra/helm/clubcore/templates/seaweedfs-s3-secret.yaml`
**Commit:** 8615af47
**Status:** fixed: requires human verification (Helm render not executable here)
**Applied fix:** Standardized on a single naming basis — the `clubcore.fullname` helper, which is what the CNPG `Cluster` and redis `Service` are already named with. Changed the `DATABASE_URL` host (`%s-postgres-rw`) and `REDIS_URL` host (`%s-redis`) to use `include "clubcore.fullname" .` instead of `.Release.Name`; renamed the `clubcore-config` ConfigMap and `clubcore-app-secret` Secret objects to the fullname basis; and updated every `envFrom` `configMapRef`/`secretRef` across the migrate Job, backend, arq-worker, and telegram-bot to match. The migrate-Job wait-loop already used `clubcore.fullname` for `postgres-rw`, so the Job is now internally consistent (wait host == DATABASE_URL host). `S3_ENDPOINT_URL` was intentionally left on `.Release.Name` because the SeaweedFS subchart names its own service `<release>-seaweedfs-s3` (documented in `seaweedfs-values.yaml:43`) — using fullname there would BREAK the subchart wiring. The seaweedfs-s3 Secret object name was bound to `.Values.seaweedfs.s3.existingConfigSecret` so the produced Secret always matches the literal the subchart mounts, for any release name. Verified statically: with `helm install clubcore` fullname==`clubcore` and with `helm install foo` fullname==`foo-clubcore`; in both cases the URL host and the rendered service name now agree.

### WR-01: Web `.dockerignore` is never applied

**Files modified:** `infra/docker/.dockerignore.web` (removed), `infra/docker/admin-app.Dockerfile.dockerignore` (new), `infra/docker/client-pwa.Dockerfile.dockerignore` (new)
**Commit:** 2c0f301b
**Applied fix:** Replaced the silently-ignored `infra/docker/.dockerignore.web` with two BuildKit per-Dockerfile ignore files named `<dockerfile>.dockerignore`. Both Dockerfiles already declare `# syntax=docker/dockerfile:1.7`, so BuildKit resolves `<context>/<dockerfile-path>.dockerignore` against the repo-root build context, i.e. `infra/docker/admin-app.Dockerfile.dockerignore` and `infra/docker/client-pwa.Dockerfile.dockerignore`. Content (including the `**/.env*` and `.git/` exclusions for T-118-03) preserved verbatim. New file created (allowed — the fix explicitly requires the correctly-named ignore files).

### WR-02: build-images.sh and Helm default tag can silently disagree

**Files modified:** `infra/scripts/build-images.sh`, `infra/scripts/deploy-local.sh`, `infra/helm/clubcore/values.yaml`, `infra/helm/clubcore/templates/_helpers.tpl`, `infra/helm/clubcore/templates/backend-deployment.yaml`, `infra/helm/clubcore/templates/migrate-job.yaml`, `infra/helm/clubcore/templates/arq-worker-deployment.yaml`, `infra/helm/clubcore/templates/telegram-bot-deployment.yaml`
**Commit:** 58aded32
**Applied fix:** Both scripts now append `-dirty` to the tag when `! git diff --quiet || ! git diff --cached --quiet`, so a clean and an uncommitted build can never share a tag (IMG-04). Removed the stale literal `tag: "6e42d106"` from values.yaml (now `tag: ""`) and added a `clubcore.image` helper that wraps the tag in `required`, so a manual `helm install`/`helm template` without `--set image.tag` fails loudly instead of deploying a stale/empty tag. Replaced the six real `image:` field references with the helper (the four `{{/* */}}` doc-comment references are inert). `deploy-local.sh` `helm lint` now also passes `--set image.tag=${TAG}` so the lint gate still renders.

### WR-03: scan-images.sh exits 0 when trivy is absent

**Files modified:** `infra/scripts/scan-images.sh`
**Commit:** 6e7bda1b
**Applied fix:** Added a `REQUIRE_TRIVY` strict mode. When `REQUIRE_TRIVY=1` (set by any CI invocation) a missing trivy now `exit 1` — the HIGH/CRITICAL CVE gate fails closed and can never become a silent no-op. When unset/0 the local operator-pending path (`exit 0` + WARN) is preserved, keeping D-V40-LOCAL-VALIDATE honesty. All diagnostics moved to stderr so they stay visible in fail-fast pipelines.

### WR-05: migrate-job double-loops the postgres wait

**Files modified:** `infra/helm/clubcore/templates/migrate-job.yaml`
**Commit:** 2bb87a6a
**Status:** fixed: requires human verification (control-flow change; Helm render + k3d run not executable here)
**Applied fix:** Removed the outer `until python3 -c "..."; do sleep 1; done` wrapper so the Python wait runs exactly once. Its internal 240s deadline drives the retry loop; on timeout it `sys.exit(1)` and, under `set -e`, fails the initContainer (and Job). The Job `activeDeadlineSeconds` (300s) remains the outer backstop, comfortably above the 240s inner deadline so the timeout message reaches the logs before force-kill. Eliminates the dead-code success path and the near-infinite retry failure path.

### WR-06: deploy-local.sh smoke check (a) conflates Failed and Running

**Files modified:** `infra/scripts/deploy-local.sh`
**Commit:** fa0408fc
**Applied fix:** Smoke check (a) now captures `kubectl wait` output to a temp log (instead of `2>/dev/null`) and additionally reads `.status.failed` and the `Failed` condition. It reports three distinct outcomes — Succeeded, Failed (with a pointer to `kubectl logs job/...`), and Timed-out/Running (emitting the captured wait output) — so an operator can tell a failed migration from a slow one. The `|| true` required under `set -e` is retained but no longer masks the failure signal.

## Skipped Issues

### WR-04: Redis reachable cluster-wide with no auth and `bind 0.0.0.0`

**File:** `infra/helm/clubcore/templates/redis-config.yaml:38-45`, `infra/helm/clubcore/templates/redis-statefulset.yaml:39-40`
**Reason:** skipped (deferred to Phase 119 SEC/NET). The review itself notes this is "explicitly tagged as Phase-119 deferrals in-code", and the fix-pass scope guardrails explicitly direct NOT to implement NetworkPolicy / Redis auth / sealed-secrets here — that is Phase-119 SEC/NET work (requirepass from a Secret, `runAsNonRoot: true` + `runAsUser: 999`, NetworkPolicy restricting 6379 to backend/arq pods). Adding it now would be scope creep into Phase 119. Tracked as a hard Phase-119 prerequisite.
**Original issue:** `redis.conf` sets `bind 0.0.0.0` with no `requirepass` and protected-mode disabled; the headless Service exposes 6379 cluster-wide with no NetworkPolicy, and the container runs as root — any pod in the cluster could read/write/FLUSHALL the session/cache/queue store.

## Info findings (out of scope for critical_warning pass)

IN-01 (healthcheck timeout), IN-02 (React 18→19 stale comment), IN-03 (Redis TZ via env vs ConfigMap), IN-04 (YooKassa-key comment) were not in scope (`fix_scope: critical_warning`) and were not modified.

---

_Fixed: 2026-06-16_
_Fixer: Claude (gsd-code-fixer)_
_Iteration: 1_

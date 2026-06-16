# Phase 118: Container Images + Helm Chart (Core Stack) - Pattern Map

**Mapped:** 2026-06-16
**Files analyzed:** 22 net-new/modified artifacts (4 image groups + ~18 Helm templates/values)
**Analogs found:** 5 strong analogs / 22 (infra phase — most Helm/k8s artifacts are net-new with NO codebase precedent)

> This is a pure-infrastructure phase. The only **code** analogs are `apps/backend/Dockerfile` (the backend-base for all Python images) and the existing `docker-compose.yml` (the service topology + entrypoint + env-var truth source). Every Helm/k8s artifact (Chart, CNPG Cluster CR, Redis StatefulSet, SeaweedFS values, Deployments, migrate hook Job, ConfigMap/Secret) is **net-new infra** — no existing analog. Where no analog exists, the planner should drive from REQUIREMENTS acceptance text + STATE.md locked decisions, NOT fabricate a precedent.

## File Classification

| New/Modified Artifact | Role | Data Flow | Closest Analog | Match Quality |
|---|---|---|---|---|
| `infra/docker/backend.Dockerfile` (or reuse `apps/backend/Dockerfile`) — IMG-01 | image / Dockerfile | build (request-response runtime) | `apps/backend/Dockerfile` | **exact** — already production-shaped |
| telegram-bot / arq-worker / migrate images — IMG-02 | image / Dockerfile (shared backend-base) | build (worker / batch / one-shot) | `apps/backend/Dockerfile` + `docker-compose.yml` commands | **exact** — same image, different CMD |
| `infra/docker/admin-app.Dockerfile` + nginx conf — IMG-03 | image / static nginx | request-response (static + SPA fallback) | none — **net-new infra** (no nginx config exists; `infra/nginx/` is `.gitkeep`) | none |
| `infra/docker/client-pwa.Dockerfile` + nginx conf — IMG-03 | image / static nginx + PWA SW | request-response (static + SW cache rules) | `apps/client-pwa/vite.config.ts` (SW denylist convention) | partial — SW rule precedent only |
| `.dockerignore` per image — IMG-01 | config | build | `apps/backend/.dockerignore` (verify exists) / docker-compose volume mounts | role-match |
| git-SHA tagging + trivy gate — IMG-04 | config / CI shell | build gate | none — **net-new** (Makefile is Phase 121; here just the tag/scan convention) | none |
| Helm umbrella `Chart.yaml` + `values.yaml` — chart root | config / Helm | n/a | none — **net-new infra** | none |
| CNPG `Cluster` CR template — DATA-01 | manifest (CRD) | CRUD (stateful db) | `docker-compose.yml` postgres service (env/db-name only) | partial — name/creds surface |
| Redis StatefulSet + PVC template — DATA-02 | manifest (StatefulSet) | CRUD / cache | `docker-compose.yml` redis service (image tag only) | partial |
| SeaweedFS Helm subchart values — DATA-03 | config / Helm values | file-I/O (object store) | `docker-compose.yml` s3 service + `docker/seaweedfs-s3.json` | role-match — env/cred surface |
| StorageClass + PVC reclaim/nodeSelector — DATA-04 | manifest | persistence | none — **net-new** (P1 invariant) | none |
| migrate hook `Job` template — APP-01 | manifest (Job) | batch / one-shot | `docker-compose.yml` migrate service (`alembic upgrade head`) | role-match — exact command |
| backend `Deployment` + probes — APP-02 | manifest (Deployment) | request-response | `docker-compose.yml` backend + `/healthz` route | role-match — CMD + probe path |
| arq-worker `Deployment` (Recreate) — APP-03 | manifest (Deployment) | event-driven / cron | `docker-compose.yml` arq-worker (`arq app.workers.WorkerSettings`) | role-match — exact command |
| telegram-bot `Deployment` (Recreate) — APP-04 | manifest (Deployment) | long-poll / event-driven | `docker-compose.yml` telegram-bot (`python -m app.workers.telegram_bot`) | role-match — exact command |
| ConfigMap + Secret templates — APP-05 | config | n/a | `app/core/config.py` env surface + `docker-compose.yml` `environment:` | role-match — env var names |

## Pattern Assignments

### Python images: backend / telegram-bot / arq-worker / migrate (IMG-01, IMG-02)

**Analog:** `apps/backend/Dockerfile` — this IS the backend-base. Do NOT rewrite from scratch; the multi-stage build, non-root user, venv-on-PATH, and factory CMD are already production-shaped (Phase 3 D-01..D-04).

**Multi-stage build pattern** (`apps/backend/Dockerfile:1-50`):
```dockerfile
# syntax=docker/dockerfile:1.7
FROM ghcr.io/astral-sh/uv:python3.12-bookworm-slim AS builder
ENV UV_LINK_MODE=copy UV_COMPILE_BYTECODE=1 UV_PROJECT_ENVIRONMENT=/app/.venv
WORKDIR /app
COPY pyproject.toml uv.lock ./
RUN --mount=type=cache,target=/root/.cache/uv \
    uv sync --frozen --no-install-project --no-dev   # deps-only layer (cache-friendly)
COPY app ./app
COPY alembic ./alembic
COPY alembic.ini ./alembic.ini
RUN --mount=type=cache,target=/root/.cache/uv uv sync --frozen --no-dev

FROM python:3.12-slim-bookworm AS runtime
RUN groupadd --system app && useradd --system --gid app --create-home app   # non-root (IMG-01)
WORKDIR /app
COPY --from=builder --chown=app:app /app /app
ENV PATH="/app/.venv/bin:$PATH" PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1
USER app
EXPOSE 8000
CMD ["uvicorn", "app.main:create_app", "--factory", "--host", "0.0.0.0", "--port", "8000"]
```

**IMG-01 gaps to add on top of the existing Dockerfile** (acceptance criteria not yet satisfied by the file):
- **Pinned base digest** — current `FROM` uses tags, not `@sha256:` digests. Pin both stages.
- **HEALTHCHECK** instruction — not present; add (e.g. curl/python probe against `/healthz`). Note k8s probes (APP-02) are the real gate, but IMG-01 requires the Dockerfile-level HEALTHCHECK too.
- **`tzdata` + `TZ=UTC`** — `python:3.12-slim-bookworm` has no tzdata by default; `apt-get install tzdata` in runtime stage + `ENV TZ=UTC` (P9 invariant).
- **`.dockerignore`** — confirm/author at `apps/backend/.dockerignore` (exclude `.venv`, `__pycache__`, tests, `.env`).

**IMG-02 — shared base, different entrypoints.** The 4 Python images are the SAME image with a CMD override (exactly as docker-compose already does). Use a single base image + per-workload `command:` in the Helm Deployment/Job spec, OR thin derived Dockerfiles. Entrypoints are authoritative in `docker-compose.yml`:
```
backend:       uvicorn app.main:create_app --factory --host 0.0.0.0 --port 8000   (NO --reload in prod)
telegram-bot:  python -m app.workers.telegram_bot
arq-worker:    arq app.workers.WorkerSettings
migrate:       alembic upgrade head
```
The worker module `apps/backend/app/workers/telegram_bot.py` and `app.workers.WorkerSettings` are confirmed to exist.

---

### nginx static images: admin-app + client-pwa (IMG-03)

**Analog:** none — **net-new infra**. `infra/nginx/` is `.gitkeep` only; no nginx.conf exists anywhere in the repo. The only precedent is the SW caching convention.

**Build pattern (to author, no analog):** multi-stage `node:20-alpine` (pnpm build → `dist/`) → `nginx:alpine` static serve. Both SPAs already produce `dist/` (verified: `apps/admin-app/dist/`, `apps/client-pwa/dist/`). Could also COPY a pre-built `dist/` to keep the image node-free, but pnpm-workspace build-in-image is cleaner for reproducibility.

**SPA fallback (P10, NET-04) — author in nginx.conf:**
```nginx
location / { try_files $uri $uri/ /index.html; }
```

**PWA SW must NOT cache `/api/*`** — the convention is already enforced at build time in `apps/client-pwa/vite.config.ts:11-18`:
```ts
workbox: {
  navigateFallbackDenylist: [/^\/api\//],   // PWA-07 / T-69-07
  runtimeCaching: [],                         // no API origin cached at runtime
}
```
nginx must reinforce: serve `sw.js` / `manifest.webmanifest` with `Cache-Control: no-cache` (or short max-age) so SW updates propagate; `/api/*` is reverse-proxied (same-origin in prod), never cached. Note `apps/client-pwa/public/` ships `sw.js`, `manifest.json`, `offline.html`, icons — preserve these in the image.

---

### CNPG Postgres `Cluster` CR (DATA-01) — net-new infra

**Analog:** none for the manifest. Only the connection/credential surface comes from `docker-compose.yml` postgres:
```
POSTGRES_USER: app   POSTGRES_DB: clubcore
DATABASE_URL: postgresql+asyncpg://app:app@postgres:5432/clubcore   (backend driver: asyncpg)
```
**Locked constraints (STATE.md / CONTEXT):** `ghcr.io/cloudnative-pg` images only (no Bitnami), `Cluster` CR `instances: 1`. **P1 invariant:** `nodeSelector` PVC pinning + `reclaimPolicy: Retain`. **Research flag (resolve at plan time):** verify `Cluster.spec.backup.barmanObjectStore` field names against CNPG v1 API (BAK-01 lands in Phase 120, but the field shape may need a placeholder now).

### Redis StatefulSet (DATA-02) — net-new infra

**Analog:** `docker-compose.yml` redis service supplies only `image: redis:7` and `REDIS_URL: redis://redis:6379/0`. Constraint: plain `redis:7-alpine` StatefulSet (no Bitnami). **Acceptance:** AOF on (`appendonly yes`, `appendfsync everysec`), `maxmemory` + `allkeys-lru`, PVC. These are net-new config values — drive from DATA-02 text.

### SeaweedFS (DATA-03) — Helm subchart, net-new values

**Analog:** `docker-compose.yml` s3 service + `apps/backend/docker/seaweedfs-s3.json` give the env/cred surface and the drop-in contract (same boto3/aioboto3 vars):
```
S3_ENDPOINT_URL: http://s3:8333   S3_BUCKET: clubcore-local
S3_ACCESS_KEY_ID / S3_SECRET_ACCESS_KEY / S3_REGION
WEED_S3_ACCESS_KEY / WEED_S3_SECRET_KEY (server-side, via s3.json)
```
Constraint: SeaweedFS Helm chart **v4.33.0, standalone S3 mode**. **Research flag:** verify current values schema at plan time. Bucket auto-created at app startup (`ensure_bucket()` lifespan) — no pre-create needed (per compose comment).

### migrate hook Job (APP-01) — net-new manifest

**Analog:** `docker-compose.yml` migrate service — exact command `alembic upgrade head`, `depends_on postgres healthy`. Alembic is wired (`apps/backend/alembic/`, `alembic.ini` copied into image).
**P4 invariant (acceptance gates):** Helm hook annotations `pre-install,pre-upgrade` + `hook-weight: "-5"` + `backoffLimit: 0` + `activeDeadlineSeconds: 300`, PLUS an `alembic check` initContainer on the backend Deployment (belt-and-suspenders).

### backend Deployment + probes (APP-02) — net-new manifest

**Analog:** `docker-compose.yml` backend (CMD, port 8000) + the liveness route. **`/healthz` is mounted at ROOT, no auth** (k8s liveness convention, Phase 2 D-14) — confirmed `apps/backend/app/api/v1/health.py:10` (`@router.get("/healthz")`) and `app/main.py:269`. Use `/healthz` for startup/liveness/readiness probes on port 8000.
**Constraints:** `replicas: 1`, startup+liveness+readiness probes, `resources.requests`+`limits`, `TZ=UTC` (P9).

### arq-worker (APP-03) + telegram-bot (APP-04) Deployments — net-new manifests

**Analog:** `docker-compose.yml` arq-worker / telegram-bot (exact commands above).
**ARCHITECTURAL INVARIANTS (not tuning, encode as acceptance criteria):** both `strategy: Recreate` + `replicas: 1`. Violating arq-worker → cron double-fire (P2); violating telegram-bot → long-polling double-consume (P3). arq-worker compose already sets `TZ: UTC` — carry to all pods.

### ConfigMap / Secret split (APP-05) — net-new manifests

**Analog:** env var NAMES come from `apps/backend/app/core/config.py` (`BaseSettings`, **no prefix — raw env var names**, `env_file=".env"`) and the `environment:` blocks in `docker-compose.yml`.
- **Secret** (sensitive — `SecretStr`/creds in config.py): `SECRET_KEY`, `TELEGRAM_BOT_TOKEN`, `S3_ACCESS_KEY_ID`, `S3_SECRET_ACCESS_KEY`, `WEBHOOK_SECRET`, YooKassa creds, AWS/email creds (`aws_access_key_id`, `aws_secret_access_key`), DB password component of `DATABASE_URL`.
- **ConfigMap** (non-sensitive): `ENVIRONMENT`, `REDIS_URL`, `S3_ENDPOINT_URL`, `S3_BUCKET`, `S3_REGION`, `FRONTEND_BASE_URL`, `PWA_BASE_URL`, `WS_ALLOWED_ORIGINS`, `TELEGRAM_BOT_USERNAME`, `CLUBCORE_EMAIL_FROM`, JWT TTLs, `TZ=UTC`.
- Note `dev_otp_pin_enabled` must be False unless `ENVIRONMENT=dev` (config.py fail-fast `@model_validator`) — ensure `ENVIRONMENT` is set correctly in the ConfigMap.
- `.env.example` (permission-blocked for direct read) is the canonical doc; the planner should read it at plan time for the exhaustive list. `config.py` is the authoritative fallback.

## Shared Patterns

### Non-root user + slim runtime
**Source:** `apps/backend/Dockerfile:31-45`
**Apply to:** all 4 Python images (already inherited); admin-app/client-pwa nginx images must also run non-root (`nginx:alpine` runs as root by default — add non-root + adjust listen port / dirs, prep for SEC-03 in Phase 119).

### TZ=UTC everywhere (P9 invariant)
**Source:** convention — `docker-compose.yml:84` arq-worker sets `TZ: UTC`
**Apply to:** every Dockerfile (`ENV TZ=UTC` + tzdata) AND every pod spec (ConfigMap `TZ=UTC`). Smoke-verified via `kubectl exec` (OPS-03, Phase 121).

### Shared backend-base, CMD override
**Source:** `docker-compose.yml` — 4 services build the same image, differ only by `command:`
**Apply to:** backend / telegram-bot / arq-worker / migrate — single image, per-workload command in Helm spec.

### Env var names = raw, no prefix
**Source:** `apps/backend/app/core/config.py` (`SettingsConfigDict(env_file=".env")`, no `env_prefix`)
**Apply to:** ConfigMap/Secret keys (APP-05) — keys map 1:1 to UPPER_SNAKE env var names.

## No Analog Found

| Artifact | Role | Reason |
|---|---|---|
| Helm `Chart.yaml` / umbrella `values.yaml` | Helm | No Helm chart exists anywhere in repo |
| CNPG `Cluster` CR | CRD manifest | No k8s manifests exist; CNPG is net-new |
| Redis StatefulSet | manifest | No StatefulSet precedent |
| SeaweedFS Helm values | Helm values | Subchart net-new (compose used raw `weed server`) |
| StorageClass / PVC reclaim+nodeSelector | manifest | P1 invariant, net-new |
| All Deployment / Job / ConfigMap / Secret templates | manifest | No k8s YAML in repo |
| admin-app + client-pwa nginx.conf | nginx config | `infra/nginx/` is `.gitkeep` only |
| git-SHA tagging + trivy gate shell | CI shell | Makefile is Phase 121; only the convention here |

For all of the above the planner drives from REQUIREMENTS acceptance text (IMG/DATA/APP) + STATE.md locked decisions (D-V40-*) + PITFALLS invariants (P1/P2/P3/P4/P9/P10). Two research flags to resolve at plan time: CNPG `barmanObjectStore` field names (CNPG v1 API) and SeaweedFS Helm v4.33.0 values schema.

## Metadata

**Analog search scope:** `apps/backend/` (Dockerfile, docker-compose.yml, app/core/config.py, app/workers/, app/api/v1/health.py), `apps/admin-app/`, `apps/client-pwa/` (vite.config.ts, public/, dist/), `infra/` (placeholders only)
**Files scanned:** ~12 source/config files; full-repo grep for Dockerfile/Chart.yaml/values.yaml/nginx confirmed zero Helm/k8s/nginx artifacts outside `.claude/worktrees/`
**Pattern extraction date:** 2026-06-16

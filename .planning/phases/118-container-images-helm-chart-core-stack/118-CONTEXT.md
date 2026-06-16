# Phase 118: Container Images + Helm Chart (Core Stack) - Context

**Gathered:** 2026-06-16
**Status:** Ready for planning
**Mode:** Auto-generated (infrastructure phase — discuss skipped per smart-discuss infra detection)

<domain>
## Phase Boundary

Production-hardened container images exist for all 6 runtime components (backend API, telegram-bot, arq-worker, migrate, admin-app nginx, client-pwa nginx) and a Helm umbrella chart successfully deploys the complete application stack — stateful services (CNPG Postgres, Redis StatefulSet, SeaweedFS) + app workloads + Alembic migration Job — into a local **k3d** cluster.

**In scope:** IMG-01..04, DATA-01..04, APP-01..05 (13 requirements).
**Out of scope (later phases):** ingress/TLS/NetworkPolicies/secrets-sealing (119), Terraform/observability/backup (120), Makefile CI/CD orchestration + full smoke (121).

**Done-bar (per D-V40-LOCAL-VALIDATE):** local validation only — `helm lint` + `helm template` clean, images build + `trivy` green, chart deploys into k3d with all pods Ready and the migrate hook Job succeeding. Live-server apply is operator-pending.

</domain>

<decisions>
## Implementation Decisions

### Locked milestone decisions (from STATE.md — binding constraints, not at discretion)
- **D-V40-ONPREM-K3S**: target = k3s; local validation on **k3d** (NOT kind). Ingress controller is Traefik v3 (bundled) — but ingress wiring itself is Phase 119.
- **D-V40-BITNAMI-PAYWALLED**: Postgres via **CloudNativePG operator** (`ghcr.io/cloudnative-pg` images) + `Cluster` CR `instances: 1`; Redis via plain `redis:7-alpine` StatefulSet. No Bitnami images anywhere.
- **D-V40-MINIO-RETIRED**: object storage = **SeaweedFS** Helm chart (v4.33.0, standalone S3 mode) — drop-in, same boto3/aioboto3 env vars, zero app-code change.
- **D-V40-REPLICAS**: backend `replicas: 1`; **arq-worker + telegram-bot are `strategy: Recreate` + `replicas: 1` — architectural invariants** (violating either → cron double-fire / Telegram long-polling double-consume). Encode as acceptance criteria, not tuning knobs.
- **Pitfall invariants (acceptance gates):** P1 Postgres PVC `nodeSelector` pinning + `reclaimPolicy: Retain`; P4 migrate as `pre-install,pre-upgrade` hook + `hook-weight: "-5"` + `backoffLimit: 0` + `activeDeadlineSeconds: 300` + `alembic check` initContainer on backend; P9 `TZ=UTC` on every pod (verify via `kubectl exec`).

### Claude's Discretion
All remaining implementation choices are at Claude's discretion within the locked constraints above — chart directory layout, values.yaml structure, ConfigMap/Secret key naming (APP-05), healthcheck/probe tuning, image tag SHA derivation, `.dockerignore` contents, trivy invocation. Use ROADMAP success criteria, REQUIREMENTS acceptance text, the existing `apps/backend/Dockerfile`, and codebase conventions to guide decisions. Research flags to resolve at plan time: CNPG `Cluster.spec.backup.barmanObjectStore` field names (verify vs CNPG v1 API) and SeaweedFS Helm chart current values schema.

</decisions>

<code_context>
## Existing Code Insights

### Reusable Assets
- `apps/backend/Dockerfile` — production multi-stage build already exists (Phase 3): `ghcr.io/astral-sh/uv:python3.12-bookworm-slim` builder → `python:3.12-slim-bookworm` runtime, non-root `app` user, venv on PATH, `EXPOSE 8000`, factory CMD `uvicorn app.main:create_app --factory`. This is the **backend-base** for IMG-01/IMG-02 — telegram-bot/arq-worker/migrate share it with different entrypoints.
- `apps/backend/docker-compose.yml` — existing local dev compose (reference for service topology + env var surface).
- `apps/backend` carries `pyproject.toml`, `uv.lock`, `app/`, `alembic/`, `alembic.ini` — Alembic is already wired (migrate Job + `alembic check` initContainer build on this).
- `apps/admin-app`, `apps/client-pwa` — React 19 SPAs producing static `dist/` (IMG-03 nginx images: SPA `try_files` fallback, SW must NOT cache `/api/*`).

### Established Patterns
- Backend env surface comes from `.env.example` (maps to ConfigMap + Secret refs, APP-05).
- Codebase maps available: `.planning/codebase/{ARCHITECTURE,STACK,STRUCTURE,CONVENTIONS,INTEGRATIONS,CONCERNS,TESTING}.md` — read at plan time.

### Integration Points
- `infra/docker/` and `infra/nginx/` exist as placeholders (`.gitkeep` only) — natural home for new Dockerfiles / nginx configs.
- New Helm chart has no existing home yet — chart root location is a plan-time decision (e.g. `infra/helm/` or `deploy/`).

</code_context>

<specifics>
## Specific Ideas

No specific UI/UX requirements — infrastructure phase. The 13 requirements (IMG/DATA/APP) and the locked decisions above are the spec.

</specifics>

<deferred>
## Deferred Ideas

None — infrastructure phase, scope fixed by ROADMAP requirement mapping (118 = IMG/DATA/APP only).

</deferred>

---
phase: 118-container-images-helm-chart-core-stack
plan: "03"
subsystem: infra/helm
tags: [helm, configmap, secret, seaweedfs, alembic, migrate-hook, app-05, app-01]
dependency_graph:
  requires:
    - "infra/helm/clubcore/values.yaml (plan 118-02 — postgres.password single source of truth)"
    - "infra/helm/clubcore/templates/_helpers.tpl (plan 118-02 — clubcore.fullname/labels helpers)"
    - "infra/scripts/build-images.sh (plan 118-01 — image.repository/tag referenced in migrate Job)"
  provides:
    - "infra/helm/clubcore/templates/app-configmap.yaml (ConfigMap clubcore-config, non-sensitive env)"
    - "infra/helm/clubcore/templates/app-secret.yaml (Secret clubcore-app-secret, sensitive env)"
    - "infra/helm/clubcore/templates/seaweedfs-s3-secret.yaml (Secret clubcore-seaweedfs-s3, S3 identities)"
    - "infra/helm/clubcore/templates/migrate-job.yaml (Alembic migrate Helm hook Job)"
    - "infra/helm/clubcore/values.yaml (config.* + secrets.* + migrate.* value trees added)"
  affects:
    - "Phase 118 plan 04 (app Deployments consume clubcore-config + clubcore-app-secret via envFrom)"
    - "Phase 119 SEC-01 (replaces all plaintext Secret values with SealedSecrets)"
tech_stack:
  added:
    - "Helm ConfigMap template: clubcore-config (non-sensitive env, 20+ keys)"
    - "Helm Secret template: clubcore-app-secret (Opaque, sensitive env, Phase-119 annotation)"
    - "Helm Secret template: clubcore-seaweedfs-s3 (s3.json identities, T-118-13)"
    - "Helm batch/v1 Job template: clubcore-migrate (Helm pre-install/pre-upgrade hook)"
  patterns:
    - "ConfigMap/Secret hard split: T-118-10 invariant — sensitive key NEVER in ConfigMap"
    - "DATABASE_URL constructed from postgres.password (single source, plan 02) + Release.Name"
    - "seaweedfs-s3-secret.yaml credentials mirror app-secret.yaml S3 keys (T-118-13 alignment)"
    - "Migrate Job P4 invariant: hook pre-install/pre-upgrade + weight -5 + backoffLimit 0 + deadline 300s"
    - "Postgres-wait initContainer: TCP poll loop before alembic upgrade head (mirrors compose depends_on)"
    - "envFrom pattern: all workloads consume both configMapRef + secretRef (plan 04 contract)"
    - "Phase-119 replacement annotations on all Secret templates"
key_files:
  created:
    - infra/helm/clubcore/templates/app-configmap.yaml
    - infra/helm/clubcore/templates/app-secret.yaml
    - infra/helm/clubcore/templates/seaweedfs-s3-secret.yaml
    - infra/helm/clubcore/templates/migrate-job.yaml
  modified:
    - infra/helm/clubcore/values.yaml
decisions:
  - "DATABASE_URL in app-secret.yaml constructed as postgresql+asyncpg://app:<postgres.password>@<release>-postgres-rw:5432/clubcore — single-source password from plan-02 value"
  - "SeaweedFS S3 Secret key name is s3.json (SeaweedFS subchart v4.33.0 existingConfigSecret expected key)"
  - "Postgres-wait initContainer uses Python socket loop (no pg_isready binary in backend image; avoids extra postgres-client image dependency)"
  - "migrate.activeDeadlineSeconds tunable in values.yaml but defaults to 300 (P4 minimum)"
  - "helm template validation marked operator-pending — helm not installed in build environment per D-V40-LOCAL-VALIDATE"
metrics:
  duration: "~25 minutes"
  completed_date: "2026-06-16"
  tasks_completed: 2
  tasks_total: 2
  files_created: 4
  files_modified: 1
---

# Phase 118 Plan 03: ConfigMap/Secret Split + Migrate Hook Job Summary

ConfigMap/Secret environment configuration split (APP-05) with a hard T-118-10 security invariant (no sensitive key in ConfigMap), SeaweedFS S3 identity Secret aligned with backend credentials (T-118-13), and a Helm `pre-install,pre-upgrade` Alembic migrate hook Job with full P4 architectural invariant set (APP-01).

## Resolved Values

| Item | Value |
|------|-------|
| ConfigMap name | `clubcore-config` |
| Secret name | `clubcore-app-secret` |
| SeaweedFS S3 Secret name | `clubcore-seaweedfs-s3` |
| Migrate Job name | `clubcore-migrate` |
| Hook annotation | `pre-install,pre-upgrade` |
| Hook weight | `-5` |
| Hook delete policy | `before-hook-creation` |
| backoffLimit | `0` (P4 architectural invariant) |
| activeDeadlineSeconds | `300` (P4 architectural invariant, tunable via migrate.activeDeadlineSeconds) |
| ENVIRONMENT default | `prod` (never "dev" — blocks dev_otp_pin_guard validator) |
| TZ | `UTC` (P9 invariant in ConfigMap, consumed by all envFrom workloads) |
| REDIS_URL | `redis://clubcore-redis:6379/0` (auto-derived from Release.Name) |
| S3_ENDPOINT_URL | `http://clubcore-seaweedfs-s3:8333` (auto-derived from Release.Name) |
| DATABASE_URL | `postgresql+asyncpg://app:<postgres.password>@clubcore-postgres-rw:5432/clubcore` |
| Migrate image | `{{ .Values.image.repository }}:{{ .Values.image.tag }}` (shared backend, plan 01) |

## Tasks Completed

| Task | Name | Commit | Files |
|------|------|--------|-------|
| 1 | ConfigMap / Secret split + SeaweedFS S3 Secret (APP-05) | `116e129e` | app-configmap.yaml, app-secret.yaml, seaweedfs-s3-secret.yaml, values.yaml |
| 2 | Alembic migrate Helm pre-install/pre-upgrade hook Job (APP-01) | `441da7d2` | migrate-job.yaml |

## Acceptance Criteria Status

### Task 1 — ConfigMap / Secret Split (APP-05)

| Criterion | Status |
|-----------|--------|
| ConfigMap contains TZ: UTC | PASSED — static value, line verified |
| ConfigMap contains ENVIRONMENT: prod (non-dev) | PASSED — default "prod", config.py guard never trips |
| ConfigMap contains COOKIE_SECURE: "true" | PASSED — hard-coded |
| ConfigMap contains REDIS_URL, S3_ENDPOINT_URL/BUCKET/REGION, base URLs | PASSED — all mapped |
| ConfigMap contains NO sensitive key (SECRET_KEY, DATABASE_URL, tokens, S3 secret keys) | PASSED — strict grep confirmed (comment-only matches, no data entries) |
| Secret contains SECRET_KEY (required, no default) | PASSED — required validator present |
| Secret contains DATABASE_URL → clubcore-postgres-rw | PASSED — postgres-rw in constructed URL |
| Secret contains TELEGRAM_BOT_TOKEN, S3_ACCESS_KEY_ID/SECRET_ACCESS_KEY | PASSED |
| Secret contains EMAIL__AWS_* creds + EMAIL__WEBHOOK_SECRET | PASSED — conditional blocks |
| Secret carries Phase-119 SEC-01 replacement annotation | PASSED |
| seaweedfs-s3-secret.yaml reproduces s3.json identities structure | PASSED — s3.json key with identities JSON |
| S3 creds in seaweedfs-s3-secret.yaml match app-secret.yaml values | PASSED — both reference secrets.s3AccessKeyId / secrets.s3SecretAccessKey |
| Env keys raw UPPER_SNAKE, nested email fields use EMAIL__ delimiter | PASSED |
| `helm template` render | OPERATOR-PENDING — helm not installed per D-V40-LOCAL-VALIDATE |

### Task 2 — Migrate Hook Job (APP-01)

| Criterion | Status |
|-----------|--------|
| Job carries `helm.sh/hook: pre-install,pre-upgrade` | PASSED — static annotation verified |
| Job carries `helm.sh/hook-weight: "-5"` | PASSED — static annotation verified |
| Job carries `helm.sh/hook-delete-policy: before-hook-creation` | PASSED — static annotation verified |
| `backoffLimit: 0` | PASSED — P4 invariant, static value |
| `activeDeadlineSeconds: 300` | PASSED — default from values.yaml (tunable) |
| `restartPolicy: Never` | PASSED |
| Runs shared `clubcore/backend:<sha>` image | PASSED — `{{ .Values.image.repository }}:{{ .Values.image.tag }}` |
| `command: alembic upgrade head` | PASSED |
| `envFrom: configMapRef clubcore-config + secretRef clubcore-app-secret` | PASSED |
| initContainer waits for CNPG -rw service before migrating | PASSED — Python TCP socket loop |
| Cross-reference comment for plan-04 alembic check initContainer | PASSED — comment in migrate-job.yaml |
| Non-root securityContext stub (runAsUser: 1000) | PASSED |
| `helm template` render | OPERATOR-PENDING — helm not installed per D-V40-LOCAL-VALIDATE |

## ConfigMap Key List (clubcore-config)

All keys below are non-sensitive. No key from the SECRET list appears here.

| Key | Default | Source |
|-----|---------|--------|
| `ENVIRONMENT` | `prod` | values.config.environment |
| `DEBUG` | `false` | values.config.debug |
| `TZ` | `UTC` | hard-coded (P9 invariant) |
| `COOKIE_SECURE` | `"true"` | hard-coded (prod invariant) |
| `REDIS_URL` | `redis://<release>-redis:6379/0` | values.config.redisUrl (auto-derived) |
| `S3_ENDPOINT_URL` | `http://<release>-seaweedfs-s3:8333` | values.config.s3EndpointUrl (auto-derived) |
| `S3_BUCKET` | `clubcore` | values.config.s3Bucket |
| `S3_REGION` | `ru-central1` | values.config.s3Region |
| `FRONTEND_BASE_URL` | `https://admin.clubcore.ru` | values.config.frontendBaseUrl |
| `PWA_BASE_URL` | `https://app.clubcore.ru` | values.config.pwaBaseUrl |
| `WS_ALLOWED_ORIGINS` | `[]` | values.config.wsAllowedOrigins |
| `TELEGRAM_BOT_USERNAME` | `clubcore_bot` | values.config.telegramBotUsername |
| `ACCESS_TOKEN_TTL_SECONDS` | `900` | values.config.accessTokenTtlSeconds |
| `REFRESH_TOKEN_TTL_SECONDS` | `2592000` | values.config.refreshTokenTtlSeconds |
| `QR_TOKEN_TTL_SECONDS` | `60` | values.config.qrTokenTtlSeconds |
| `EMAIL__PROVIDER` | `sandbox` | values.config.emailProvider |
| `EMAIL__FROM_ADDRESS` | `noreply@mail.clubcore.ru` | values.config.emailFromAddress |
| `EMAIL__FROM_DOMAIN` | `""` | values.config.emailFromDomain |
| `EMAIL__SANDBOX_MODE` | `false` | values.config.emailSandboxMode |
| `CLUBCORE_EMAIL_FROM` | *(conditional, if set)* | values.config.clubcoreEmailFrom |

## Secret Key List (clubcore-app-secret)

All keys below are sensitive. None appear in the ConfigMap.

| Key | Notes |
|-----|-------|
| `SECRET_KEY` | Required (no default) — JWT signing key |
| `DATABASE_URL` | Constructed: `postgresql+asyncpg://app:<postgres.password>@<release>-postgres-rw:5432/clubcore` |
| `TELEGRAM_BOT_TOKEN` | Default: placeholder sentinel (safe for dev) |
| `S3_ACCESS_KEY_ID` | Required — must match seaweedfs-s3-secret.yaml identity |
| `S3_SECRET_ACCESS_KEY` | Required — must match seaweedfs-s3-secret.yaml identity |
| `EMAIL__AWS_ACCESS_KEY_ID` | Conditional (non-sandbox provider) |
| `EMAIL__AWS_SECRET_ACCESS_KEY` | Conditional (non-sandbox provider) |
| `EMAIL__WEBHOOK_SECRET` | Default: "" (empty = sandbox mode) |

## Migrate Job Annotation Set (P4 Invariant — Verbatim)

```yaml
annotations:
  helm.sh/hook: pre-install,pre-upgrade
  helm.sh/hook-weight: "-5"
  helm.sh/hook-delete-policy: before-hook-creation
spec:
  backoffLimit: 0
  activeDeadlineSeconds: 300
```

These annotations are architectural acceptance criteria. Any change requires an architectural review (Deviation Rule 4).

## Deviations from Plan

None — plan executed exactly as written. All templates are structurally correct Helm/YAML. `helm template` validation marked operator-pending (helm not installed per tooling_preflight note / D-V40-LOCAL-VALIDATE).

**Implementation notes:**

- Postgres-wait initContainer uses a Python `socket.create_connection` loop rather than `pg_isready` because the backend image does not include the PostgreSQL client tools binary. This is equivalent (tests TCP reachability on port 5432) and avoids adding a separate postgres-client init image (supply-chain simplicity). Documented as a decision.

## Operator-Pending Items

### Helm Lint + Template Render (plan 03 templates)

`helm` is not installed in this build environment. Run operator-side after `helm dependency build`:

```bash
# 1. Vendor SeaweedFS subchart (if not already done)
helm repo add seaweedfs https://seaweedfs.github.io/seaweedfs/helm
helm dependency build infra/helm/clubcore

# 2. Lint the chart (includes plan 03 templates)
helm lint infra/helm/clubcore

# 3. Template render with seaweedfs disabled
helm template clubcore infra/helm/clubcore --set seaweedfs.enabled=false

# 4. Verify ConfigMap/Secret security invariants:
# TZ=UTC present in ConfigMap
helm template clubcore infra/helm/clubcore --set seaweedfs.enabled=false | grep -q 'TZ: UTC' && echo "TZ OK"
# No SECRET_KEY in ConfigMap
! helm template clubcore infra/helm/clubcore --set seaweedfs.enabled=false | \
  awk '/name: clubcore-config/{p=1} /^---/{p=0} p' | grep -q 'SECRET_KEY' && echo "No SECRET_KEY in ConfigMap OK"
# DATABASE_URL → clubcore-postgres-rw
helm template clubcore infra/helm/clubcore --set seaweedfs.enabled=false | grep -q 'clubcore-postgres-rw' && echo "DB URL OK"

# 5. Verify migrate Job P4 invariants:
helm template clubcore infra/helm/clubcore --set seaweedfs.enabled=false \
  --show-only templates/migrate-job.yaml | grep -q 'helm.sh/hook: pre-install,pre-upgrade' && echo "hook OK"
helm template clubcore infra/helm/clubcore --set seaweedfs.enabled=false \
  --show-only templates/migrate-job.yaml | grep -q 'helm.sh/hook-weight: "-5"' && echo "weight OK"
helm template clubcore infra/helm/clubcore --set seaweedfs.enabled=false \
  --show-only templates/migrate-job.yaml | grep -q 'backoffLimit: 0' && echo "backoffLimit OK"
helm template clubcore infra/helm/clubcore --set seaweedfs.enabled=false \
  --show-only templates/migrate-job.yaml | grep -q 'activeDeadlineSeconds: 300' && echo "deadline OK"
helm template clubcore infra/helm/clubcore --set seaweedfs.enabled=false \
  --show-only templates/migrate-job.yaml | grep -q 'alembic' && echo "alembic OK"
```

## Known Stubs

None — all ConfigMap/Secret values are fully wired. Local-k3d plaintext defaults in values.yaml are intentional (documented with Phase-119 replacement warnings) and are NOT stubs that prevent the plan's goal — they are the correct local development values, to be replaced by SealedSecrets in Phase 119 SEC-01.

## Threat Coverage

| Threat | Mitigation | Status |
|--------|-----------|--------|
| T-118-10 Information Disclosure (ConfigMap) | Hard split: sensitive keys ONLY in Secret objects; strict grep confirmed no data-section leak | DONE |
| T-118-11 Tampering (migrate race) | P4 invariant: `pre-install,pre-upgrade` + weight `-5` + `backoffLimit:0` + deadline 300s + Postgres-wait initContainer | DONE |
| T-118-12 Information Disclosure (plaintext defaults) | Phase-119 annotation + "LOCAL K3D ONLY" comments in app-secret.yaml, seaweedfs-s3-secret.yaml, values.yaml | DONE |
| T-118-13 Spoofing (SeaweedFS S3 identity) | seaweedfs-s3-secret.yaml S3 creds exactly match app-secret.yaml S3 keys (both from secrets.s3AccessKeyId/s3SecretAccessKey) | DONE |
| T-118-SC Tampering (migrate image) | Job uses same git-SHA-pinned `clubcore/backend` image as plan 01; no `:latest`, no separate image | DONE |

## Self-Check: PASSED

**Files created:**
- `infra/helm/clubcore/templates/app-configmap.yaml` — EXISTS
- `infra/helm/clubcore/templates/app-secret.yaml` — EXISTS
- `infra/helm/clubcore/templates/seaweedfs-s3-secret.yaml` — EXISTS
- `infra/helm/clubcore/templates/migrate-job.yaml` — EXISTS
- `infra/helm/clubcore/values.yaml` (modified) — EXISTS

**Commits:**
- `116e129e` — feat(118-03): ConfigMap/Secret split + SeaweedFS S3 Secret (Task 1)
- `441da7d2` — feat(118-03): Alembic migrate Helm pre-install/pre-upgrade hook Job (Task 2)

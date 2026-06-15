# Architecture Research: v4.0 Production Infrastructure — k3s Integration

**Domain:** On-prem bare-metal k3s; existing full-stack gym CRM containerized and infra-as-code'd
**Researched:** 2026-06-16
**Confidence:** HIGH (all mappings derived from live docker-compose.yml + WorkerSettings + Dockerfile; k8s resource choices from established patterns for these workload types)

---

## System Overview

```
┌─────────────────────────────────────────────────── k3s cluster (single bare-metal node) ──┐
│                                                                                             │
│  ┌─── Ingress (Traefik/nginx-ingress) ──────────────────────────────────────────────────┐  │
│  │  admin.example.com → admin-app Service                                               │  │
│  │  app.example.com   → client-pwa Service                                              │  │
│  │  api.example.com   → backend Service  (+ /ws/* sticky WS)                           │  │
│  │  TLS: cert-manager (self-signed local / Let's Encrypt prod)                          │  │
│  └───────────────────────────────────────────────────────────────────────────────────────┘  │
│                                                                                             │
│  ┌── Stateless Workloads (Deployments) ──────────────────────────────────────────────────┐ │
│  │  backend-api   (replicas=2, HPA optional)   │  admin-app-nginx  (replicas=1)          │ │
│  │  arq-worker    (replicas=1, SINGLE)         │  client-pwa-nginx (replicas=1)          │ │
│  │  telegram-bot  (replicas=1, SINGLE)         │                                         │ │
│  └───────────────────────────────────────────────────────────────────────────────────────┘ │
│                                                                                             │
│  ┌── One-Shot Jobs ───────────────────────────────────────────────────────────────────────┐ │
│  │  migrate-job (Job, backoffLimit=0, runs alembic upgrade head before other pods start) │ │
│  └───────────────────────────────────────────────────────────────────────────────────────┘ │
│                                                                                             │
│  ┌── Stateful Workloads (StatefulSets + PVCs) ───────────────────────────────────────────┐ │
│  │  postgres-0  (StatefulSet, PVC postgres-data 20Gi)                                    │ │
│  │  redis-0     (StatefulSet, PVC redis-data 2Gi, appendonly yes + AOF)                  │ │
│  │  minio-0     (StatefulSet, PVC minio-data 10Gi) — replaces SeaweedFS in prod          │ │
│  └───────────────────────────────────────────────────────────────────────────────────────┘ │
│                                                                                             │
│  ┌── Observability (Namespace: monitoring) ──────────────────────────────────────────────┐ │
│  │  prometheus  │  grafana  │  loki  │  promtail                                         │ │
│  └───────────────────────────────────────────────────────────────────────────────────────┘ │
│                                                                                             │
│  ┌── Backup CronJobs ────────────────────────────────────────────────────────────────────┐ │
│  │  pg-backup-cronjob (daily, pg_dump → MinIO)   │  redis-backup-cronjob (weekly RDB)   │ │
│  └───────────────────────────────────────────────────────────────────────────────────────┘ │
└─────────────────────────────────────────────────────────────────────────────────────────────┘
```

---

## Component → K8s Resource Mapping

### 1. backend API (FastAPI/uvicorn)

**K8s Resource:** `Deployment`

```
name: backend-api
replicas: 2  (or 1 for pet project; HPA on CPU/RPS optional — single gym won't need it)
image: clubcore/backend:SHA  (multi-stage Dockerfile already production-ready, non-root)
command: uvicorn app.main:create_app --factory --host 0.0.0.0 --port 8000
  (no --reload in prod; Dockerfile CMD already correct)
```

**Service:** `ClusterIP` on port 8000. Ingress points at this Service.

**Ingress:** One Ingress rule for `api.example.com`:
- All paths → backend Service
- `/ws` or `/api/v1/client/ws/*` → same backend Service BUT requires WS sticky annotation (see Ingress/routing section)

**HPA:** Optional for this single-gym pet project. If added: min=1, max=3, CPU target=70%. The WebSocket constraint (see below) means replicas > 1 requires sticky sessions or Redis-backed pub/sub (already in place via Redis channel broadcasting in v2.5 messaging module — pub/sub fan-out makes multi-replica safe for WS).

**Readiness probe:** `GET /healthz` returns 200 (endpoint exists per PROJECT.md). Liveness: same, initialDelaySeconds=10.

**Init dependency on migrate:** Do NOT use initContainers here. Use the Job + `helm hook` ordering pattern (see migrate section). The Helm `post-install` hook on the Job + a `wait-for-migrate` initContainer on the backend Deployment reading a ConfigMap sentinel is the clean approach. Simpler: keep the `depends_on: migrate: service_completed_successfully` semantics by using a Kubernetes Job with a `helm.sh/hook: pre-install,pre-upgrade` annotation.

---

### 2. telegram-bot worker

**K8s Resource:** `Deployment`

```
name: telegram-bot
replicas: 1  ← MUST be exactly 1, forever. Long-polling Telegram API is single-consumer.
             Multiple replicas = duplicate update processing, duplicate DMs sent.
```

**No Service** — this pod initiates outbound connections only (to Telegram API + Redis + Postgres). It is never called inbound. No ClusterIP, no Ingress, no ports exposed.

**Restart policy:** `restartPolicy: Always` (Docker compose `restart: unless-stopped` → Deployment's default). Telegram bot reconnects on restart.

**Single-replica enforcement:** No HPA. No PodDisruptionBudget that could create overlap during rolling updates. Use `strategy: Recreate` (not RollingUpdate) to ensure the old pod is killed before the new pod starts. This eliminates the window where two bot instances could both poll Telegram simultaneously.

```yaml
strategy:
  type: Recreate
```

**Ordering:** initContainer or helm hook waiting for migrate Job to complete before bot starts (same as backend-api).

---

### 3. ARQ worker (cron scheduler)

**K8s Resource:** `Deployment`

```
name: arq-worker
replicas: 1  ← MUST be exactly 1 for cron correctness.
```

**Why replicas=1 is mandatory for cron:**

ARQ uses `unique=True` on all cron jobs (confirmed in WorkerSettings — every `cron(...)` call has `unique=True, keep_result=60`). `unique=True` means ARQ stores a Redis key before enqueuing; a second worker instance seeing the same tick will skip it. HOWEVER:

- The `unique=True` guard is "second line of defence" per the code's own comments; SQL-level idempotency is the primary gate.
- With two workers, if one acquires the Redis unique lock and then crashes mid-job, the other instance will not pick it up until `keep_result` TTL expires (60 seconds). This creates a 60-second blackout window.
- More importantly: `monitor_stale_fiscal_receipts` runs every 15 minutes (4×/hour) with `FOR UPDATE SKIP LOCKED`; two workers would both dequeue from Redis and attempt concurrent execution.
- Two ARQ worker processes means two `on_startup` calls, two `build_yookassa_client()` instances, two email dispatcher registrations — the per-process singletons become ambiguous.

**Conclusion:** Keep replicas=1. Use `strategy: Recreate`. No HPA.

**No Service** — outbound only (Redis + Postgres + ЮKassa HTTPS + Yandex email SMTP).

**TZ env must be set:** `TZ: UTC` (locked in docker-compose; the cron schedule hour/minute offsets are UTC-based, e.g. `hour=3, minute=5` = 06:05 Moscow). This env var must be in the Deployment's env.

---

### 4. migrate (Alembic one-shot)

**K8s Resource:** `Job` (not initContainer on every pod)

**Rationale for Job over initContainer:**
- `~70 migrations` — a cold migrate-from-zero takes 10–30 seconds. Duplicating this as an initContainer on backend + arq-worker + telegram-bot means 3 parallel `alembic upgrade head` runs competing against each other at cluster startup. Alembic has per-revision locking via `alembic_version` table but concurrent runs are a correctness risk.
- A `Job` with `backoffLimit=0` (fail fast) runs ONCE, completes, and all other Deployments wait for it.
- Helm lifecycle annotation: `helm.sh/hook: pre-install,pre-upgrade` + `helm.sh/hook-weight: "-1"` runs the Job before any Deployment is created or updated.

**Ordering enforcement pattern:**

Option A (recommended for simplicity): Helm hook ordering. The migrate Job has `pre-install,pre-upgrade` hook annotation. Helm waits for the Job to succeed before proceeding to create Deployments. The Job fails the release if migrations fail.

Option B (belt-and-suspenders): Each Deployment (backend, arq-worker, telegram-bot) has an initContainer running `python -c "import sys; from alembic.runtime.migration import MigrationContext; ..."` that checks the DB version matches HEAD, sleeping 5s and retrying until true. This prevents a race if Helm hooks are bypassed (e.g., `kubectl apply` direct).

**Recommendation:** Use both — Helm hook as primary ordering + a lightweight initContainer on backend that does `alembic check` (exits 0 if already at head, exits 1 otherwise) with retry, so the Deployment self-heals if the Job is still running.

```yaml
# Job spec
spec:
  backoffLimit: 0
  template:
    spec:
      restartPolicy: Never
      containers:
      - name: migrate
        command: ["alembic", "upgrade", "head"]
```

---

### 5. Postgres 16

**K8s Resource:** `StatefulSet` (not an operator)

**Rationale for StatefulSet over operator (e.g., CloudNative-PG):**
- Pet project, single gym, single node. Operator complexity (CRDs, controller deployments, failover logic) adds operational overhead with no benefit for a single-instance deployment.
- StatefulSet with a single replica gives stable pod identity (`postgres-0`), stable DNS (`postgres-0.postgres.namespace.svc.cluster.local`), and persistent storage via PVC.
- CloudNative-PG is worth considering only if HA/failover is needed. It is not for this scope.

```yaml
name: postgres
replicas: 1
image: postgres:16  (pinned digest in prod)
volumeClaimTemplates:
  - metadata:
      name: postgres-data
    spec:
      accessModes: ["ReadWriteOnce"]
      resources:
        requests:
          storage: 20Gi
```

**Service:** Headless Service (`clusterIP: None`) for StatefulSet DNS, plus a regular ClusterIP Service named `postgres` on port 5432 that other pods use. The DNS `postgres.namespace.svc.cluster.local` replaces the docker-compose service name `postgres` in DATABASE_URL.

**Persistence:** PVC backed by local-path provisioner (k3s ships `local-path-provisioner` by default — no extra storage class setup needed on bare metal). For production, pin to a specific node or use `hostPath` + `nodeAffinity`.

**Liveness/readiness:** `exec: pg_isready -U app -d clubcore` — mirrors docker-compose healthcheck exactly.

---

### 6. Redis 7

**K8s Resource:** `StatefulSet`

```yaml
name: redis
replicas: 1
image: redis:7  (pinned digest)
command: ["redis-server", "--appendonly", "yes", "--save", "60", "1"]
volumeClaimTemplates:
  - metadata:
      name: redis-data
    spec:
      accessModes: ["ReadWriteOnce"]
      resources:
        requests:
          storage: 2Gi
```

**Why StatefulSet:** Redis in this app is NOT a pure cache — it stores sessions (JWT refresh-token families), rate-limit counters, idempotency keys (86400s TTL), circuit-breaker state, ARQ job queue, and WebSocket pub/sub channels. Data loss on pod restart = user sessions invalidated + ARQ queue flushed + in-flight idempotency keys lost. Persistence (AOF + RDB snapshot) is mandatory.

**Service:** ClusterIP on port 6379. DNS `redis.namespace.svc.cluster.local` replaces `redis` in REDIS_URL.

**No Redis operator needed** for single-node, non-HA use case.

---

### 7. Object Storage (MinIO replacing SeaweedFS in production)

**K8s Resource:** `StatefulSet`

**Why MinIO over SeaweedFS in production:**
- SeaweedFS (`chrislusf/seaweedfs:3.84`) is used in docker-compose dev. It works but has complex multi-daemon architecture (master + volume servers). For single-node prod, MinIO is the standard S3-compatible choice: simpler StatefulSet, well-documented k8s deployment, OCI-compliant image, better k8s tooling ecosystem.
- The backend uses boto3/aiobotocore S3 API (`S3_ENDPOINT_URL`, `S3_BUCKET`, `S3_ACCESS_KEY_ID`, `S3_SECRET_ACCESS_KEY`, `S3_REGION` env vars). MinIO is a drop-in replacement — no code changes needed.
- Keep SeaweedFS in docker-compose for local dev (already working); switch to MinIO in k8s (prod + kind local-validation).

```yaml
name: minio
replicas: 1
image: minio/minio:RELEASE.2025-xx-xx  (pinned)
command: ["server", "/data", "--console-address", ":9001"]
volumeClaimTemplates:
  - metadata:
      name: minio-data
    spec:
      accessModes: ["ReadWriteOnce"]
      resources:
        requests:
          storage: 10Gi
```

**Service:** ClusterIP on port 9000 (S3 API). Console on 9001 (optional Ingress for admin).

---

### 8. Static frontends (admin-app + client-pwa)

**K8s Resource:** `Deployment` (each) + `ConfigMap` for nginx.conf

**Image:** Multi-stage — `node:20-alpine` builds Vite SPA → `nginx:stable-alpine` serves `dist/`. No server-side logic.

```
admin-app-nginx:
  replicas: 1
  image: clubcore/admin-app:SHA
  ports: [80]

client-pwa-nginx:
  replicas: 1  
  image: clubcore/client-pwa:SHA
  ports: [80]
```

**Service:** ClusterIP on port 80 for each.

**Critical nginx.conf for client-pwa:** The Service Worker MUST NOT cache `/api/*`. The nginx config must set:
```nginx
location /api/ {
    proxy_pass http://backend-api.namespace.svc.cluster.local:8000;
}
location /ws/ {
    proxy_pass http://backend-api.namespace.svc.cluster.local:8000;
    proxy_http_version 1.1;
    proxy_set_header Upgrade $http_upgrade;
    proxy_set_header Connection "upgrade";
}
```
Wait — actually in the k8s model, the nginx frontend pod does NOT proxy to the backend; Ingress does. The nginx config needs `try_files $uri $uri/ /index.html;` for SPA routing, and the Service Worker in the PWA code already has `never caches /api/*` (confirmed in PROJECT.md: "SW (`gym-v3`) never caches `/api/*`"). The nginx serving the SPA only serves static assets; Ingress routes `/api/*` to the backend Service directly.

**nginx.conf pattern for SPAs:**
```nginx
server {
    listen 80;
    root /usr/share/nginx/html;
    index index.html;
    # Cache static assets, not index.html
    location ~* \.(js|css|png|jpg|svg|woff2)$ {
        expires 1y;
        add_header Cache-Control "public, immutable";
    }
    location / {
        try_files $uri $uri/ /index.html;
        add_header Cache-Control "no-cache";  # index.html never cached
    }
}
```

---

## Ingress / Routing Design

### Host Layout

```
api.clubcore.local     → backend-api Service :8000  (HTTP + WS)
admin.clubcore.local   → admin-app-nginx Service :80
app.clubcore.local     → client-pwa-nginx Service :80
```

(Replace `.clubcore.local` with real domain in production.)

### WebSocket Routing

WebSocket connections (`/api/v1/client/ws/{thread_id}`) require:

1. **Ingress annotations** (Traefik or nginx-ingress):
   - Traefik: `traefik.ingress.kubernetes.io/router.entrypoints: websecure` + sticky sessions if replicas > 1
   - nginx-ingress: `nginx.ingress.kubernetes.io/proxy-read-timeout: "3600"` + `nginx.ingress.kubernetes.io/proxy-send-timeout: "3600"` + `nginx.ingress.kubernetes.io/configuration-snippet` to set `proxy_set_header Upgrade $http_upgrade; proxy_set_header Connection "Upgrade";`

2. **Sticky sessions for WS when replicas > 1:** If backend API has replicas > 1, WS connections must be routed to the same backend pod for the lifetime of the connection. The Redis pub/sub architecture means messages are delivered regardless of which pod handles the connection (the pub/sub fan-out reaches all pods), but the initial WS upgrade handshake and the connection state live on one pod. Use `nginx.ingress.kubernetes.io/affinity: "cookie"` sticky session annotation.

3. **For replicas=1 (single-gym pet project):** Sticky sessions not needed. Simple routing works.

### TLS Termination

cert-manager (`cert-manager.io`) manages TLS:
- **Local validation (kind):** `ClusterIssuer` with `selfSigned` issuer. Generates a self-signed CA + per-Ingress certificates. No external DNS required.
- **Production (bare-metal):** `ClusterIssuer` with Let's Encrypt ACME HTTP-01 challenge. Requires the host to be reachable on port 80 from the internet for challenge verification.
- **Offline production alternative:** ACME DNS-01 challenge with a supported DNS provider, or purchase a certificate and load it as a Secret manually.

```yaml
# cert-manager ClusterIssuer for local
apiVersion: cert-manager.io/v1
kind: ClusterIssuer
metadata:
  name: selfsigned-issuer
spec:
  selfSigned: {}
```

Ingress TLS section:
```yaml
tls:
- hosts:
  - api.clubcore.local
  secretName: api-tls
```

---

## Terraform Module Layout

### Separation Principle

**Two module groups, two providers, two state files:**

```
infra/terraform/
├── host/                          # bare-metal provisioning (SSH + shell scripts)
│   ├── main.tf                    # null_resource + remote-exec: install k3s, set up dirs
│   ├── variables.tf               # host IP, SSH key, k3s version
│   ├── outputs.tf                 # kubeconfig path, cluster endpoint
│   └── terraform.tfvars.example  # template (no secrets committed)
│
├── cluster/                       # in-cluster resources (kubernetes + helm provider)
│   ├── main.tf                    # helm_release for each chart, kubernetes_secret for sealed creds
│   ├── providers.tf               # kubernetes provider + helm provider (kubeconfig from host output)
│   ├── variables.tf               # image tags, domain names, replica counts
│   ├── outputs.tf                 # service URLs, ingress IPs
│   └── terraform.tfvars.example
│
└── modules/
    ├── k3s-install/               # reusable: SSH + k3s install script
    ├── postgres-statefulset/      # reusable: StatefulSet + Service + PVC
    ├── redis-statefulset/         # reusable: StatefulSet + Service + PVC
    └── backend-deployment/        # reusable: Deployment + Service + Ingress
```

### Local State

```hcl
# host/main.tf
terraform {
  backend "local" {
    path = "../../.terraform-state/host/terraform.tfstate"
  }
}
```

State file lives outside the repo (add `.terraform-state/` to `.gitignore`). For a solo dev this is sufficient; no remote state needed.

### validate/plan Without a Live Cluster

```
terraform validate   # parses HCL, resolves variable types, no network calls
terraform plan       # requires provider connectivity
```

**Problem:** `terraform plan` for the `cluster/` group (kubernetes/helm provider) requires a running k3s cluster — it calls the K8s API to diff current state vs desired.

**Solution — local validation architecture (see Local Validation section below).**

For `host/` group: `terraform validate` always works (null_resource with remote-exec has no provider API calls at validate time). `terraform plan` also works — the `null_resource` plan shows "will run remote-exec" without actually SSH-ing.

For `cluster/` group: `terraform validate` works (HCL syntax). `terraform plan` requires a kind/k3d cluster to be running. The Makefile target `make plan` should start a kind cluster first if not running.

---

## Helm Chart Structure

### Recommended: Umbrella Chart

```
helm/
└── clubcore/
    ├── Chart.yaml            # name: clubcore, version, appVersion
    ├── values.yaml           # default values (local/dev)
    ├── values.prod.yaml      # production overrides (domain, image tags, resources)
    ├── values.local.yaml     # kind/local overrides (no TLS, NodePort, lower resources)
    ├── templates/
    │   ├── NOTES.txt
    │   ├── _helpers.tpl      # common labels, selector helpers
    │   ├── namespace.yaml
    │   ├── configmap.yaml    # DATABASE_URL, REDIS_URL, S3_ENDPOINT_URL, TZ, etc.
    │   ├── secret.yaml       # refs to pre-existing Secrets (not inline values)
    │   ├── migrate-job.yaml  # Job with helm.sh/hook: pre-install,pre-upgrade
    │   ├── backend/
    │   │   ├── deployment.yaml
    │   │   ├── service.yaml
    │   │   └── ingress.yaml
    │   ├── arq-worker/
    │   │   └── deployment.yaml
    │   ├── telegram-bot/
    │   │   └── deployment.yaml
    │   ├── postgres/
    │   │   ├── statefulset.yaml
    │   │   ├── service.yaml
    │   │   └── pvc.yaml
    │   ├── redis/
    │   │   ├── statefulset.yaml
    │   │   └── service.yaml
    │   ├── minio/
    │   │   ├── statefulset.yaml
    │   │   └── service.yaml
    │   ├── admin-app/
    │   │   ├── deployment.yaml
    │   │   ├── service.yaml
    │   │   └── ingress.yaml
    │   ├── client-pwa/
    │   │   ├── deployment.yaml
    │   │   ├── service.yaml
    │   │   └── ingress.yaml
    │   ├── networkpolicies/
    │   │   └── default-deny.yaml
    │   └── backup/
    │       ├── pg-backup-cronjob.yaml
    │       └── redis-backup-cronjob.yaml
    └── charts/               # subchart dependencies (cert-manager, etc.) if using umbrella deps
```

**Why umbrella over per-component charts:** Single `helm upgrade clubcore ./helm/clubcore` installs/upgrades the full stack. For a solo dev, the overhead of managing 8+ separate chart releases (with cross-chart value passing) is not worth it. The umbrella chart with `values.local.yaml` vs `values.prod.yaml` is the right tradeoff.

**Values for local vs prod:**
```yaml
# values.yaml (defaults / local)
global:
  domain: clubcore.local
  imageRegistry: ""  # local kind registry or "" for local images
  imagePullPolicy: IfNotPresent

backend:
  replicas: 1
  image: clubcore/backend
  tag: latest
  resources:
    requests: { cpu: 100m, memory: 128Mi }

postgres:
  storage: 1Gi  # small for local
  
ingress:
  tls: false  # no TLS in kind local
  className: traefik
```

```yaml
# values.prod.yaml (overlay)
global:
  domain: clubcore.ru
  
backend:
  replicas: 2
  tag: "abc123def456"  # pinned SHA

postgres:
  storage: 20Gi

ingress:
  tls: true
  certIssuer: letsencrypt-prod
```

**Secret refs:** Secrets are never in values files. The `secret.yaml` template references pre-existing Secret names that must be created out-of-band (by SOPS + age/gpg or sealed-secrets):
```yaml
# In deployment.yaml
envFrom:
- secretRef:
    name: clubcore-app-secrets   # must exist before helm install
```

---

## Config / Secrets Flow

### Existing .env.example → ConfigMaps + Secrets

**Split rule:** public non-sensitive config → ConfigMap; credentials/keys → Secret.

| .env.example variable | K8s object | Notes |
|----------------------|------------|-------|
| `DATABASE_URL` | Secret `clubcore-app-secrets` | Contains password; entire URL in Secret |
| `REDIS_URL` | ConfigMap `clubcore-config` | No auth in current setup; move to Secret if AUTH added |
| `S3_ENDPOINT_URL` | ConfigMap `clubcore-config` | Not sensitive |
| `S3_BUCKET` | ConfigMap `clubcore-config` | Not sensitive |
| `S3_ACCESS_KEY_ID` | Secret `clubcore-app-secrets` | Credential |
| `S3_SECRET_ACCESS_KEY` | Secret `clubcore-app-secrets` | Credential |
| `S3_REGION` | ConfigMap `clubcore-config` | Not sensitive |
| `SECRET_KEY` (JWT signing) | Secret `clubcore-app-secrets` | Critical — rotate via new Secret version |
| `TELEGRAM_BOT_TOKEN` | Secret `clubcore-app-secrets` | Credential |
| `YOOKASSA_SHOP_ID` | Secret `clubcore-app-secrets` | Credential |
| `YOOKASSA_SECRET_KEY` | Secret `clubcore-app-secrets` | Credential |
| `YOOKASSA_TRUSTED_IPS` | ConfigMap `clubcore-config` | Public IP list |
| `TZ` | ConfigMap `clubcore-config` | `UTC` for arq-worker |
| SMTP / email config | Secret `clubcore-app-secrets` | API key / password |
| `CLUB_BRAND` | ConfigMap `clubcore-config` | `Sportzal` placeholder value |

### Secrets Management: SOPS + age (recommended)

**Why SOPS over sealed-secrets:**
- sealed-secrets requires the controller to be running in the cluster to decrypt. If the cluster is lost, re-sealing requires recreating the controller key.
- SOPS with age (or gpg) encrypts secrets files that can be stored in git. The age private key lives offline. Decryption + `kubectl apply` is a one-command Makefile target.
- For a solo dev, SOPS is simpler operational model.

**Workflow:**
```
# Encrypt once
sops --encrypt --age $AGE_PUBLIC_KEY secrets.plaintext.yaml > secrets.enc.yaml
git add secrets.enc.yaml  # safe to commit

# Deploy
sops --decrypt secrets.enc.yaml | kubectl apply -f -
```

The plaintext `secrets.plaintext.yaml` lives on the developer's machine only (in `.gitignore`). `secrets.enc.yaml` is committed.

### NAME-01 CSRF Cookie Rename

The `clubcore_csrf` cookie rename (from `sportzal_csrf`) is already the live cookie name per the memory note ("real staff cookies are cc_access/cc_refresh/clubcore_csrf"). The OpenAPI spec update (additive, not breaking) is a carry-over task for this milestone. Map in ConfigMap as `CSRF_COOKIE_NAME=clubcore_csrf`.

---

## Local Validation Architecture

### Tool Choice: kind (not k3d, not real k3s)

**Recommendation: kind (Kubernetes IN Docker)**

| Tool | Pros | Cons | Decision |
|------|------|------|----------|
| kind | Pure Docker, no VM, fast to start/stop, CI-friendly, well-tested with Terraform kubernetes provider | Not k3s (uses kubeadm), Traefik not built-in | **USE THIS** |
| k3d | k3s in Docker (closer to prod), Traefik built-in | More complex setup, less CI tooling | Consider if Traefik-specific behavior must be validated |
| real k3s VM | Identical to prod | Requires a VM (CPU/RAM overhead), slow iteration | Prod target, not for local dev loop |

For most validation goals, kind is sufficient. The differences from bare-metal k3s are:
- kind uses containerd not k3s's embedded containerd (functionally identical)
- kind lacks k3s's built-in Traefik; install nginx-ingress or Traefik via helm into kind
- Local-path provisioner behavior is slightly different (kind has its own `local-path` provisioner)
- No cloud LoadBalancer (use NodePort or port-forward for local access)

### What Local Validation Proves vs Cannot Prove

| Validation | Tool | Proves | Cannot Prove |
|-----------|------|--------|--------------|
| `terraform validate` | Terraform | HCL syntax, variable types, resource schema | Provider connectivity, actual resource creation |
| `terraform plan` (host/) | Terraform + null_resource | Plan output shows correct remote-exec commands | SSH connectivity to real host |
| `terraform plan` (cluster/) | Terraform + kind running | Kubernetes resource diff, Helm release diff | Actual k3s behavior, bare-metal networking |
| `helm lint` | Helm | Template syntax, required values, chart structure | Runtime behavior, actual image pull |
| `helm template` | Helm | Generated manifests are valid YAML + correct labels | Pod scheduling, PVC binding |
| `helm install` (kind) | kind + Helm | All pods reach Running, Services route correctly, Ingress responds | TLS cert-manager LE prod, external DNS, bare-metal storage |
| `smoke test` | pytest / curl | API returns 200, DB migrations applied, Redis connected, S3 bucket created | ЮKassa webhook (no live creds), RU email delivery |
| Image scan | trivy | CVE count, CRITICAL vulnerabilities | Runtime security |

### Local Validation Makefile Targets

```makefile
# Full local validation pipeline
validate-all: terraform-validate helm-lint kind-up helm-install-local smoke

terraform-validate:
	cd infra/terraform/host && terraform init -backend=false && terraform validate
	cd infra/terraform/cluster && terraform init -backend=false && terraform validate

helm-lint:
	helm lint helm/clubcore -f helm/clubcore/values.local.yaml

kind-up:
	kind create cluster --name clubcore-local --config infra/kind/config.yaml
	kubectl apply -f https://raw.githubusercontent.com/kubernetes/ingress-nginx/.../deploy.yaml
	helm repo add cert-manager https://charts.jetstack.io
	helm install cert-manager cert-manager/cert-manager --set installCRDs=true

helm-install-local:
	# Build local images first
	docker build -t clubcore/backend:local apps/backend/
	kind load docker-image clubcore/backend:local --name clubcore-local
	# Apply secrets (plaintext for local only)
	kubectl apply -f infra/k8s/local-secrets.yaml
	# Install chart
	helm upgrade --install clubcore helm/clubcore \
	  -f helm/clubcore/values.local.yaml \
	  --wait --timeout 300s

smoke:
	# Wait for migrate job, then hit /healthz
	kubectl wait --for=condition=complete job/clubcore-migrate --timeout=120s
	kubectl port-forward svc/backend-api 8000:8000 &
	curl -f http://localhost:8000/healthz

kind-down:
	kind delete cluster --name clubcore-local
```

### Differences Between kind and Real Bare-Metal k3s

1. **Ingress controller:** kind needs nginx-ingress installed; k3s ships Traefik. Both handle `Ingress` resources, but annotation keys differ. Use nginx-ingress annotations in Helm templates, OR detect via values.yaml `ingress.className: nginx` vs `traefik`.

2. **Storage:** kind uses a `rancher.io/local-path` provisioner (different name than k3s's); both satisfy `ReadWriteOnce` PVCs. PVC provisioner annotation may differ.

3. **Node labels:** Real k3s node has `node-role.kubernetes.io/master`. kind nodes have different labels. Node affinity rules in Helm templates must handle both or avoid node-specific selectors.

4. **LoadBalancer:** In kind, LoadBalancer Services get no external IP (use NodePort or `cloud-provider-kind` tooling). In real k3s on bare metal with MetalLB, they get a local IP. The Ingress approach (all traffic via Ingress, not LoadBalancer) sidesteps this difference.

5. **Traefik IngressRoute vs standard Ingress:** k3s Traefik supports both standard `networking.k8s.io/v1` Ingress and Traefik-specific `IngressRoute` CRD. Use standard Ingress objects for portability.

---

## Suggested Build Order

Build order follows dependency chains: you cannot write Helm templates before knowing the resource shape; you cannot test locally before the chart works; you cannot do observability before the app is running.

### Phase Dependency Graph

```
[1] Docker images (hardened)
      ↓
[2] Helm chart skeleton + StatefulSets (Postgres, Redis, MinIO)
      ↓
[3] migrate Job + backend Deployment (API running in kind)
      ↓
[4] Telegram-bot + ARQ-worker Deployments (all app pods running)
      ↓
[5] Static frontend Deployments + Ingress + TLS
      ↓
[6] Terraform IaC (wrap what's already tested in Helm into TF modules)
      ↓
[7] Secrets management (SOPS) + NetworkPolicies
      ↓
[8] Observability (Prometheus + Grafana + Loki)
      ↓
[9] Backup CronJobs + restore runbook
      ↓
[10] CI/CD Makefile + full smoke test
      ↓
[11] Documentation runbook
      ↓
[12] Operator-pending: live bare-metal apply
```

### Rationale for Order

1. **Images first** — everything else is blocked on having working container images. Harden the existing Dockerfile (pinned digests, `.dockerignore`, trivy clean), add frontend Dockerfiles (multi-stage Vite build → nginx). No k8s work starts until images build and run correctly.

2. **StatefulSets before Deployments** — app pods need DB + Redis to be running. Postgres and Redis StatefulSets are simpler to write and validate than the app Deployments (no migration ordering complexity). Validate PVC binding in kind first.

3. **migrate Job + backend** — this is the critical ordering problem. Solve it early (Helm hook + initContainer strategy). Once the backend API reaches `/healthz` in kind, the core integration is proven.

4. **Worker Deployments** — arq-worker and telegram-bot are simpler than backend (no Ingress, no Service). They share the same image. Validate the `TZ=UTC` and `replicas=1, strategy: Recreate` constraints here.

5. **Frontends + Ingress + TLS** — nginx static serving is straightforward. Ingress routing is where most debugging happens (host headers, WS upgrade, TLS). Tackle this as a unit.

6. **Terraform** — write Terraform AFTER the Helm chart is working. Terraform wraps tested Helm releases; writing TF for untested resources wastes iteration. `terraform validate` and `terraform plan` against kind prove the HCL is correct.

7. **Secrets + NetworkPolicies** — secrets management (SOPS workflow) needs to be finalized before any real credentials are applied. NetworkPolicies (default-deny + per-pod allow rules) come after the topology is stable so you know which pod→pod paths to allow.

8. **Observability** — Prometheus + Grafana + Loki are installed via community Helm charts into a separate namespace. These don't block the app running; add after the app stack is stable.

9. **Backup** — CronJobs for pg_dump and Redis snapshot. Write the restore runbook and test it (round-trip restore to a fresh PVC) in kind before production.

10. **Makefile CI/CD** — the Makefile is the glue. Write it last when all individual pieces work. One-command `make deploy` = build → load → helm upgrade → smoke.

11. **Runbook documentation** — the production runbook documents what was built. Write it during or after implementation, not before.

12. **Live apply is operator-pending** — per the milestone definition, live bare-metal apply requires real server access + live ЮKassa/email credentials. Autonomous work stops at local validation.

---

## Architectural Patterns

### Pattern 1: Helm Hook for Migration Ordering

**What:** `Job` with `helm.sh/hook: pre-install,pre-upgrade` ensures Alembic runs to completion before Helm creates or updates any Deployment.

**When to use:** Any stateful schema migration that must complete before app code runs. This is the canonical pattern — do not use `initContainers` as the sole ordering mechanism when the migration is heavyweight.

**Trade-offs:** If the Job fails, the Helm release fails (good — you want loud failure). The Job pod stays around for debugging (`backoffLimit=0`, `ttlSecondsAfterFinished: 300`).

### Pattern 2: Recreate Strategy for Single-Instance Workers

**What:** `strategy: type: Recreate` on telegram-bot and arq-worker Deployments.

**When to use:** Any workload where two instances running simultaneously is incorrect. Recreate kills the old pod before starting the new one (zero-overlap guarantee).

**Trade-offs:** Brief downtime during updates (seconds). Acceptable for background workers where the Telegram long-polling reconnects automatically and ARQ resumes from Redis.

### Pattern 3: Redis Pub/Sub Makes Backend API Multi-Replica Safe for WS

**What:** The v2.5 messaging WebSocket uses Redis pub/sub fan-out. Any backend pod subscribed to the channel receives the message and pushes it to its connected WS clients.

**When to use:** Already in use. The architectural implication for k8s: the backend-api Deployment can safely run replicas > 1 even with active WS connections, as long as Ingress has sticky sessions (so a given client's WS stays on the same pod for the connection lifetime).

### Pattern 4: ConfigMap + Secret Separation in Helm

**What:** Public config (URLs without passwords, feature flags, region) in ConfigMap. Credentials in Secret. Deployments reference both via `envFrom`. Secrets are created out-of-band (SOPS) and referenced by name, never templated with `{{ .Values.secretValue }}`.

**When to use:** Always. This pattern ensures `helm template` output (which goes in git or CI artifacts) never contains plaintext credentials.

---

## Anti-Patterns to Avoid

### Anti-Pattern 1: ARQ Worker Replicas > 1

**What people do:** Set `replicas: 2` on arq-worker for "availability" — if one pod dies, the other keeps running.

**Why wrong:** ARQ's `unique=True` cron dedup is best-effort (Redis NX key). Two workers processing the same tick concurrently can execute a cron job twice in the same minute window. The SQL-level idempotency guards (ON CONFLICT DO NOTHING, WHERE status='active') prevent double-charges but the duplicate execution wastes resources and produces duplicate log entries. More importantly, `monitor_stale_fiscal_receipts` and `poll_pending_refunds` run every 15/30 minutes and use `FOR UPDATE SKIP LOCKED` — two worker instances dequeue different rows and both execute concurrently, which is the intended behavior for task queues but not for singleton "sweep" crons.

**Instead:** replicas=1, strategy: Recreate. Accept brief downtime during deployments for cron workers. If zero-downtime is required, use a leader election pattern (e.g., a Redis SETNX lease in `on_startup`) — but this is overkill for a single-gym pet project.

### Anti-Pattern 2: telegram-bot Rolling Update

**What people do:** Leave default `strategy: RollingUpdate` on the telegram-bot Deployment, which creates the new pod before terminating the old.

**Why wrong:** During the rolling update window, both old and new pods call `application.run_polling()` simultaneously. The Telegram Bot API delivers each update to exactly one poller (the one that first calls `getUpdates`). In practice, both pollers compete; some updates are lost (consumed by the dying pod) or processed twice (if the API delivers to both before SIGTERM). Russian-language DMs and `/checkin` responses become unreliable.

**Instead:** `strategy: Recreate`. The update takes ~5 seconds of bot downtime. Users typing `/checkin` during that window get no response until the pod restarts, then the Telegram API re-delivers the pending update (Telegram queues unacknowledged updates for 24 hours).

### Anti-Pattern 3: SeaweedFS in Production k8s

**What people do:** Lift-and-shift the docker-compose SeaweedFS into k3s as-is.

**Why wrong:** SeaweedFS in `server -s3` mode bundles master + volume + filer into a single process, but the image's entrypoint in the compose setup (`chrislusf/seaweedfs:3.84 server -s3 -s3.config=...`) is not designed for k8s restart semantics. Volume re-mount behavior after a pod reschedule is poorly documented. The `healthcheck` in compose relies on a `grep Forbidden` wget — not a standard k8s readiness probe.

**Instead:** MinIO in prod k8s. The backend S3 client code is identical (boto3/S3 API); only the endpoint changes. Keep SeaweedFS in docker-compose for dev (it works there).

### Anti-Pattern 4: Storing Secrets in Helm values.yaml

**What people do:** Put `TELEGRAM_BOT_TOKEN: "123:ABC..."` in `values.prod.yaml` and commit it.

**Why wrong:** The value ends up in git history, Helm release history (stored in cluster Secrets), and any CI artifact that runs `helm template`. Token rotation is difficult.

**Instead:** Create the Secret out-of-band with SOPS before `helm install`. Helm template references `secretKeyRef: name: clubcore-app-secrets` — it only knows the Secret name, not the value. Rotate by updating and re-applying the SOPS-encrypted file.

---

## Integration Points

### External Services

| Service | Integration Pattern | Notes |
|---------|---------------------|-------|
| ЮKassa | HTTPS webhook POST to `/_internal/yookassa/webhook` | Must be publicly reachable; Ingress must route this path to backend; IP allowlist (`YOOKASSA_TRUSTED_IPS`) verified in backend |
| Telegram Bot API | Outbound HTTPS from telegram-bot pod | No inbound; requires egress to `api.telegram.org` |
| Yandex Email (SMTP/SES-V2) | Outbound HTTPS from arq-worker | Requires egress to Yandex Cloud endpoints |
| cert-manager ACME | Outbound HTTPS from cert-manager pod + inbound HTTP-01 challenge | Requires port 80 reachable from internet for LE |

### Internal Boundaries (pod → pod)

| Boundary | Communication | K8s Implementation |
|----------|---------------|--------------------|
| backend-api → postgres | TCP 5432 | ClusterIP Service `postgres:5432` |
| backend-api → redis | TCP 6379 | ClusterIP Service `redis:6379` |
| backend-api → minio | HTTP 9000 | ClusterIP Service `minio:9000` |
| arq-worker → redis | TCP 6379 | Same ClusterIP Service |
| arq-worker → postgres | TCP 5432 | Same ClusterIP Service |
| telegram-bot → redis | TCP 6379 | Same ClusterIP Service |
| telegram-bot → postgres | TCP 5432 | Same ClusterIP Service |
| arq-worker → minio | HTTP 9000 | Same ClusterIP Service (for forward_to_staff photo task) |
| ingress → backend-api | HTTP 8000 | ClusterIP Service `backend-api:8000` |
| ingress → admin-app-nginx | HTTP 80 | ClusterIP Service `admin-app:80` |
| ingress → client-pwa-nginx | HTTP 80 | ClusterIP Service `client-pwa:80` |

**NetworkPolicy minimum allow rules (after default-deny):**
- backend-api → postgres: port 5432
- backend-api → redis: port 6379
- backend-api → minio: port 9000
- arq-worker → postgres, redis, minio (same ports)
- telegram-bot → postgres, redis (same ports)
- ingress-controller → backend-api, admin-app, client-pwa (HTTP)
- All pods → kube-dns (UDP 53) — easy to forget, breaks DNS

---

## Sources

- Live `apps/backend/docker-compose.yml` — authoritative topology (read 2026-06-16)
- Live `apps/backend/app/workers/__init__.py` (WorkerSettings) — confirms cron scheduling model, `unique=True` on all cron_jobs, `TZ=UTC` requirement, per-process singleton wiring
- Live `apps/backend/app/workers/telegram_bot.py` — confirms long-polling model, single process requirement
- Live `apps/backend/Dockerfile` — multi-stage, non-root, production-ready; no frontend Dockerfiles exist yet
- `.planning/PROJECT.md` — v4.0 milestone scope, locked decisions (on-prem k3s, local-validation bar, Prometheus+Grafana+Loki, Makefile CI/CD, SOPS/sealed-secrets, NAME-01 CSRF rename)
- k3s documentation: StatefulSet + local-path provisioner patterns
- ARQ 0.28 documentation: `unique=True` cron semantics, `keep_result` TTL
- Helm best practices: hook lifecycle, values overlay pattern
- cert-manager: selfSigned issuer for local validation

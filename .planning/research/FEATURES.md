# Feature Research

**Domain:** Production Infrastructure — Self-Hosted k3s (v4.0)
**Researched:** 2026-06-16
**Confidence:** HIGH — based on PROJECT.md v4.0 milestone scope, locked decisions (on-prem k3s, local-only CI, Terraform IaC, Prometheus+Grafana+Loki, sealed-secrets/SOPS), existing docker compose topology, and industry standard practices for single-app bare-metal k3s deployments.

---

## Context

v4.0 is a pure infra/DevOps milestone — no business features, no OpenAPI changes. The starting point is a working `docker compose up` stack:

- **Backend** — FastAPI/uvicorn (Python 3.12, multi-stage Dockerfile exists)
- **Telegram bot worker** — long-polling single instance
- **ARQ cron worker** — multiple ARQ cron jobs
- **Alembic migrate** — one-shot job
- **Postgres 16** — primary datastore, ~50 Alembic migrations
- **Redis 7** — sessions / rate-limit / idempotency / circuit-breaker / ARQ queue / chat WS pub/sub
- **SeaweedFS / S3** — object storage for chat photo attachments
- **Mailpit** — dev-only mail catcher
- **Two static frontends** — admin-app + client-pwa, React + Vite, served by nginx
- **`.github/workflows/ci.yml`** — 7 test gates (ruff, mypy, pytest, typecheck, lint, vitest, Redocly)

Locked decisions that drive all categorizations:
- **On-prem bare-metal k3s** — no managed cloud, no Yandex/AWS
- **Done = local validation** — kind/k3s deploy + terraform validate/plan + helm lint + smoke; live apply is operator-pending
- **CI/CD = local Makefile** — no external runner, no git remote (repo copied to backup PC)
- **Observability = Prometheus + Grafana + Loki** — chosen stack, not under discussion
- **IaC = Terraform** — chosen, state local
- **Secrets = sealed-secrets or SOPS** — out-of-repo

---

## Feature Landscape

### Dimension 1: Containerization

**Table Stakes — must have:**

| Feature | Why Expected | Complexity | Notes |
|---------|--------------|------------|-------|
| Multi-stage production Dockerfile for backend API | Already exists in project; must be production-hardened (non-root user, slim base, no dev deps) | LOW | Python 3.12-slim or distroless Python. Builder stage installs uv deps; runtime stage copies only the installed packages. Non-root UID (e.g. uid=1000). |
| Separate image for telegram-bot worker | Bot is a long-polling process with its own runtime; sharing an image with the API is workable but a separate image is cleaner for independent restarts | LOW | Same base as backend; different CMD. Can share a base layer. |
| Separate image for ARQ worker | ARQ worker has separate process lifecycle (cron jobs, different resource needs) | LOW | Same base as backend; different CMD. |
| Alembic migrate as a Kubernetes Job image | Migrate must run once before the API starts; Job semantic is correct | LOW | Same Python image, CMD `alembic upgrade head`. |
| nginx-served static frontends (admin-app + client-pwa) | Both frontends are already Vite-built static SPAs; nginx is the correct server | LOW | Two separate nginx containers or one with two server blocks. `npm run build` in builder stage, `nginx:alpine` in runtime stage. |
| `.dockerignore` for each app | Without it, Docker COPY sends node_modules, `.git`, `__pycache__` to the build context, causing slow builds and large layers | LOW | Standard practice; easy to forget. |
| Healthcheck INSTRUCTION in Dockerfiles | k8s probes can use exec healthchecks; Docker-level HEALTHCHECK also useful for local compose debugging | LOW | Backend: `GET /healthz`. Frontends: check nginx process. |
| Non-root user in all images | CIS Docker Benchmark baseline; prevents container breakout privilege escalation | LOW | `RUN adduser --system --uid 1000 appuser; USER appuser` |
| Pinned base image digests (not just tags) | `python:3.12-slim` tags can change silently; production should use `@sha256:...` digests | MEDIUM | Adds friction to updates but is the correct production discipline. Can be a per-phase hardening step. |

**Differentiators — justified for this project:**

| Feature | Value Proposition | Complexity | Notes |
|---------|-------------------|------------|-------|
| Distroless Python runtime image | Smaller attack surface, no shell, no package manager in the final image | MEDIUM | `gcr.io/distroless/python3` is a real option; requires that all deps are installed in the builder stage. Tradeoff: harder to debug. Justified for the API container (longest-running, most attack surface). Bot and ARQ workers can use slim. |
| Layer caching discipline (deps copied before source) | Faster rebuilds — uv/pip install layer is reused if only source changes | LOW | Standard multi-stage discipline: COPY pyproject.toml uv.lock first, install, THEN COPY source. Already a best practice but easy to do wrong. |

**Anti-Features — do NOT do:**

| Feature | Why Requested | Why It's Wrong Here | What to Do Instead |
|---------|---------------|---------------------|-------------------|
| Separate images for each ARQ cron function | "Isolation between cron tasks" | All ARQ cron jobs run in the same worker process; splitting them into separate images means reimplementing the ARQ scheduler in Kubernetes CronJob semantics — more complexity, more images to maintain, no benefit at 1 gym | One ARQ worker container; k8s CronJob triggers are not needed — ARQ handles its own schedule internally |
| Image signing (Sigstore/Cosign) | "Supply chain security" | At solo pet-project scale with no image registry and no team, image signing provides zero practical benefit — there is no one to verify signatures | Pinned digests give sufficient provenance for this deployment |
| Multi-arch builds (arm64 + amd64) | "Works on any hardware" | Unless the bare-metal host is ARM, this adds build complexity for zero benefit | Single arch matching the production host (amd64) |
| Docker content trust / Notary | Enterprise supply-chain feature | No external registry, no team, notary is not configured by default in k3s | Skip entirely |

---

### Dimension 2: IaC (Terraform)

**Table Stakes — must have:**

| Feature | Why Expected | Complexity | Notes |
|---------|--------------|------------|-------|
| `terraform validate` and `terraform plan` green locally | The stated done-bar for v4.0; live apply is operator-pending | LOW | Local state backend (`backend "local"`). No remote state (no git remote, no S3). |
| k3s installation module (on-prem host) | Terraform provisions the k3s binary + service on the bare-metal host via `null_resource` + `remote-exec` or a `local-exec` Ansible call | MEDIUM | k3s has a documented install script (`curl -sfL https://get.k3s.io | sh`). Terraform wraps this. Alternatively: Terraform provisions the VM/host config, k3s install is a separate shell step — splitting is cleaner. |
| Kubernetes/Helm Terraform providers for in-cluster resources | Using Terraform for both host provisioning AND k8s resources is a common pattern; keeps everything in one IaC layer | MEDIUM | `hashicorp/kubernetes` and `hashicorp/helm` providers. Authenticate via the k3s-generated kubeconfig. |
| Namespace definitions in Terraform | `clubcore` namespace (and `monitoring` for Prometheus/Grafana/Loki) should be declared in Terraform | LOW | Simple `kubernetes_namespace` resources. |
| ConfigMap/Secret declarations for non-sensitive config | Terraform manages the k8s objects that Helm won't manage | LOW | Database URL (without password), Redis URL, env flags |
| Module structure: `modules/k3s-host`, `modules/k8s-apps` | Separating host provisioning from in-cluster resources is the standard two-layer Terraform pattern for k3s | MEDIUM | `modules/k3s-host/` — SSH, k3s install, firewall. `modules/k8s-apps/` — namespaces, secrets from SOPS, Helm releases. |
| `terraform.tfvars.example` | Documents required variables without committing secrets | LOW | Standard practice; easy to miss. |

**Differentiators — justified for this project:**

| Feature | Value Proposition | Complexity | Notes |
|---------|-------------------|------------|-------|
| SOPS-encrypted `.tfvars` for secrets | Secrets (DB password, Redis password, YooKassa key, Telegram token) stay encrypted in-repo but are decryptable locally | MEDIUM | `mozilla/sops` with age encryption. Simpler than Vault, no server required, fits the no-remote-registry solo-dev workflow. Alternative: sealed-secrets (k8s-native). SOPS is better for Terraform variables specifically; sealed-secrets is better for k8s Secrets in Helm. Use both: SOPS for `.tfvars` / Helm values, sealed-secrets for k8s Secret objects. |
| Separate `terraform plan` output saved to file | Enables reviewing planned changes before apply, especially useful when AI agents drive execution | LOW | `terraform plan -out=tfplan` + `terraform show tfplan`. One Makefile target. |

**Anti-Features — do NOT do:**

| Feature | Why Requested | Why It's Wrong Here | What to Do Instead |
|---------|---------------|---------------------|-------------------|
| Remote Terraform state (S3/GCS/Terraform Cloud) | "Best practice for teams" | No team, no git remote — remote state adds an external dependency with no collaborator benefit. State file on the local machine (or backed up with the repo) is correct here. | `backend "local"` with the state file in `.terraform/` (gitignored) |
| Terragrunt | "DRY Terraform configuration" | Terragrunt is a wrapper that adds complexity for multi-account/multi-region patterns. Single-server single-env does not benefit from it. | Clean Terraform module structure is sufficient |
| Full CIS Kubernetes benchmark via Terraform | "Hardened cluster configuration" | CIS k8s benchmark is hundreds of controls; implementing them all in Terraform would take longer than the rest of the milestone. k3s defaults are already more locked-down than vanilla k8s. | PodSecurityAdmission (built into k3s 1.24+), NetworkPolicies for least-privilege networking, and pod security contexts cover the practical threat model |
| Terraform Cloud / Atlantis for plan/apply automation | "GitOps IaC" | No git remote exists. Atlantis requires a git webhook. | Local `make tf-plan`, `make tf-apply` targets |
| Multiple environments (dev/staging/prod workspaces) | "Proper environment separation" | One gym, one server, one environment. Terraform workspaces add cognitive overhead with zero benefit. | Single workspace, single state file |

---

### Dimension 3: K8s / Helm

**Table Stakes — must have:**

| Feature | Why Expected | Complexity | Notes |
|---------|--------------|------------|-------|
| Deployment for backend API (uvicorn) | Core app; Deployment is the correct k8s primitive for a stateless replicated service | LOW | `replicas: 1` to start (single-node cluster). Resource requests and limits set. `terminationGracePeriodSeconds: 30` (uvicorn graceful shutdown). |
| Deployment for telegram-bot worker | Long-polling worker; must be a single instance (Telegram requires one polling connection) | LOW | `replicas: 1`. No HPA (would break Telegram long-polling). |
| Deployment for ARQ worker | Cron job runner; single instance is correct (ARQ handles internal scheduling + `unique=True` on cron jobs) | LOW | `replicas: 1`. No HPA. |
| StatefulSet + PersistentVolumeClaim for Postgres 16 | Postgres requires stable storage and stable network identity; StatefulSet is the correct primitive | MEDIUM | PVC backed by local-path provisioner (k3s default). `storageClassName: local-path`. Size: 10–20 GB initial. |
| StatefulSet + PVC for Redis 7 | Redis persistence (AOF + RDB snapshots); requires stable storage | MEDIUM | Same local-path provisioner. Redis 7 with `appendonly yes`. |
| StatefulSet + PVC for object storage (MinIO) | Chat photo attachments currently use SeaweedFS; MinIO is a simpler S3-compatible alternative for k8s — or SeaweedFS if it's already containerized | MEDIUM | MinIO is better supported in k8s with Helm charts. Consider migrating from SeaweedFS to MinIO here. PVC for data volume. |
| Alembic migrate as a Kubernetes Job | One-shot migration before the API starts; Job semantic + `initContainer` or a pre-deploy Job is the correct pattern | MEDIUM | Helm `hook: pre-install,pre-upgrade`. Requires the same database credentials as the API. |
| ConfigMaps for non-secret configuration | Environment variables that are not secret (app name, timezone, log level, API URLs) should be in ConfigMaps, not baked into the image | LOW | One ConfigMap per component or a shared app ConfigMap. |
| Kubernetes Secrets for sensitive config | Database passwords, Redis password, JWT secret, YooKassa API key, Telegram bot token | LOW | Populated from SOPS-decrypted values at deploy time. NOT committed to git in plaintext. |
| Liveness and readiness probes for all Deployments | Without probes, k8s cannot know when a container is healthy; traffic may be sent to an unready pod | LOW | Backend: `GET /healthz`. Readiness fails during startup (DB not yet ready). Liveness kills loops. Bot worker: TCP or exec probe. ARQ worker: exec probe (check process). |
| Resource requests and limits for all containers | Without limits, a runaway process (e.g., ARQ job bug) can starve the entire single-node cluster | MEDIUM | Start conservative: backend `requests: {cpu: 100m, memory: 256Mi}`, `limits: {cpu: 500m, memory: 512Mi}`. Adjust after observability data is collected. |
| Helm chart(s) for the application stack | Helm provides templating, release management, upgrade/rollback; essential for a repeatable deploy | MEDIUM | One umbrella chart `charts/clubcore/` with subcharts or one flat chart. Values split: `values.yaml` (defaults) + `values-prod.yaml` (production overrides, gitignored or SOPS-encrypted). |
| `helm lint` passing in CI | The stated done-bar; validates chart syntax | LOW | One Makefile target. |

**Differentiators — justified for this project:**

| Feature | Value Proposition | Complexity | Notes |
|---------|-------------------|------------|-------|
| Helm `pre-upgrade` hook for Alembic migrate | Ensures migrations always run before the new API version starts; prevents version skew on upgrades | MEDIUM | `helm.sh/hook: pre-install,pre-upgrade` annotation on the Job. `helm.sh/hook-delete-policy: before-hook-creation` to avoid stale Jobs. |
| Pod anti-affinity for Postgres (soft) | Prevents Postgres from being scheduled on the same node as the API if additional nodes are added later | LOW | `preferredDuringSchedulingIgnoredDuringExecution`. Trivial to add but demonstrates correct thinking. |
| Separate namespace `monitoring` for observability stack | Isolates Prometheus/Grafana/Loki from the app namespace; cleaner RBAC boundaries | LOW | `kubectl create namespace monitoring` (or via Terraform). |

**Anti-Features — do NOT do:**

| Feature | Why Requested | Why It's Wrong Here | What to Do Instead |
|---------|---------------|---------------------|-------------------|
| HPA (Horizontal Pod Autoscaler) for backend API | "Auto-scale under load" | Single-node cluster: HPA has nowhere to schedule new pods. At 1-gym scale, the load is predictably low (dozens of concurrent users at peak). HPA configuration also requires accurate resource metrics from metrics-server. | Set `replicas: 1`. Revisit if the project ever runs on multi-node. |
| PodDisruptionBudget for stateful services | "High availability during node drain" | Single node means there is always exactly one pod. A PDB of `minAvailable: 1` on a single-replica StatefulSet will prevent the node from being drained at all. | Skip PDB on single-node. Add when multi-node topology is introduced. |
| Separate HelmRelease per microservice (FluxCD/ArgoCD) | "GitOps continuous deployment" | No git remote. GitOps CD requires a remote repo that the controller polls. The entire GitOps premise is incompatible with the no-remote-registry constraint. | Local Makefile `make helm-upgrade` target. |
| Istio / Linkerd service mesh | "Observability and traffic management" | Service mesh adds per-pod sidecar proxies, a control plane, and significant operational complexity. For a handful of services on a single node, the overhead is not justified. Prometheus scraping provides the observability needed. | Direct service-to-service communication via k8s DNS. NetworkPolicies for security. Prometheus for metrics. |
| Kustomize overlays in addition to Helm | "DRY manifests" | Helm already provides templating and values files. Adding Kustomize on top creates a two-layer configuration system with no benefit at single-env scale. | Helm values files are sufficient |
| Argo Rollouts / canary deployments | "Zero-downtime deployments" | At 1 gym with predictable maintenance windows, a rolling update (default Kubernetes) is sufficient. Canary complexity is for multi-replica, production-critical deployments with real traffic SLAs. | `strategy: RollingUpdate` with `maxUnavailable: 0, maxSurge: 1` (on single replica, this means: bring up new before killing old — works if resource headroom exists) |

---

### Dimension 4: Networking

**Table Stakes — must have:**

| Feature | Why Expected | Complexity | Notes |
|---------|--------------|------------|-------|
| Ingress for backend API (`/api/v1/*` and `/healthz`) | External traffic must reach the FastAPI backend | LOW | k3s ships Traefik as the default ingress controller. Alternatively, replace with nginx-ingress. Traefik is fine for this scale. Ingress rule: host `api.clubcore.local` (dev) or real domain (prod). |
| Ingress for admin-app frontend | Staff admin panel must be reachable | LOW | Separate Ingress or path-based routing. Host: `admin.clubcore.local` / `admin.yourdomain.ru`. |
| Ingress for client-pwa frontend | Client-facing PWA must be reachable | LOW | Host: `app.clubcore.local` / `app.yourdomain.ru`. |
| TLS via cert-manager (self-signed in local validation) | HTTPS is required for PWA (Service Workers, WebCrypto, httpOnly cookies work over HTTPS only) | MEDIUM | cert-manager with a `ClusterIssuer`. Local: self-signed. Production: Let's Encrypt (`letsencrypt-prod`). |
| Internal service-to-service DNS via k8s DNS | Backend connects to Postgres, Redis by service name (e.g., `postgres.clubcore.svc.cluster.local`) | LOW | k3s includes CoreDNS. No additional work — just use k8s Service names in environment variables instead of hostnames. |
| NodePort or LoadBalancer for ingress (bare-metal) | Bare-metal k3s has no cloud load balancer; ingress must be exposed via NodePort or MetalLB | MEDIUM | k3s default: Traefik uses NodePort. For a single-node bare-metal deployment, NodePort on port 80/443 is sufficient. MetalLB adds complexity with no benefit at single-node. |

**Differentiators — justified for this project:**

| Feature | Value Proposition | Complexity | Notes |
|---------|-------------------|------------|-------|
| NetworkPolicy: deny-all default + explicit allow rules | Implements least-privilege network access; prevents a compromised container from scanning the internal network | MEDIUM | `default-deny-all` NetworkPolicy in the `clubcore` namespace. Explicit allow: backend → postgres, backend → redis, backend → object-storage, bot-worker → redis, arq-worker → postgres + redis. Frontends do not need to reach the database directly (they don't — they talk to the API). |
| TLS redirect: HTTP → HTTPS at ingress level | Prevents accidental unencrypted access to the app | LOW | Traefik annotation `traefik.ingress.kubernetes.io/redirect-entry-point: https`. One-line config. |

**Anti-Features — do NOT do:**

| Feature | Why Requested | Why It's Wrong Here | What to Do Instead |
|---------|---------------|---------------------|-------------------|
| MetalLB for load balancing | "Proper bare-metal load balancing" | Single-node cluster: MetalLB allocates IP addresses for LoadBalancer services, but there is only one node to route to. NodePort achieves the same result with zero additional components. | NodePort on 80/443, or `hostPort` on Traefik. Revisit if multi-node. |
| Calico / Cilium CNI replacement | "Better NetworkPolicy support" | k3s ships Flannel by default. Flannel supports NetworkPolicy via a companion policy controller. Replacing the CNI on a working cluster is a risky low-value operation. | Flannel + NetworkPolicy (k3s includes the policy controller). |
| External DNS automation | "Automatic DNS record management" | No git remote, no cloud DNS API integration. External DNS requires a DNS provider API key and a GitOps workflow. DNS records can be set manually once when going to production. | Manual DNS record pointing to the bare-metal server IP. |
| mTLS between services (via Istio/Linkerd) | "Encrypted inter-service communication" | All services are in the same cluster. Traffic between pods in the same namespace does not traverse untrusted networks. NetworkPolicies provide the access control needed. mTLS would require a service mesh. | NetworkPolicies + TLS at ingress only |

---

### Dimension 5: Security

**Table Stakes — must have:**

| Feature | Why Expected | Complexity | Notes |
|---------|--------------|------------|-------|
| Secrets out of repository (sealed-secrets or SOPS) | Plaintext secrets in git is an immediate disqualifier for any production system | MEDIUM | SOPS with age key for Terraform variables and Helm values. For k8s Secrets managed by Helm, use `helm-secrets` plugin with SOPS. Or: sealed-secrets for k8s Secrets + SOPS for Terraform `.tfvars`. Both are acceptable; sealed-secrets is more k8s-native. |
| Non-root pod security context for all containers | Defense-in-depth; a process running as root inside a container can more easily exploit a container escape | LOW | `securityContext: runAsNonRoot: true, runAsUser: 1000`. Enforced at the Deployment spec level. Consistent with the non-root user in the Dockerfile. |
| `readOnlyRootFilesystem: true` where possible | Prevents an attacker from writing malicious files to the container filesystem | LOW | Backend API and frontends can run with a read-only root. Exceptions: Postgres and Redis need writable data directories (handled by PVC mounts). |
| `allowPrivilegeEscalation: false` | Prevents a process from gaining more privileges than its parent | LOW | One-line addition to every container's `securityContext`. |
| Drop all Linux capabilities | Containers should not have NET_ADMIN, SYS_ADMIN, etc. unless explicitly needed | LOW | `capabilities: drop: ["ALL"]`. None of the app containers need elevated capabilities. |
| Trivy image scan in `make scan` | Detect known CVEs in base images before deploying | LOW | `trivy image <image-name>` on each built image. Run locally as part of the build pipeline. Accept HIGH/CRITICAL threshold; fail on CRITICAL by default. |
| PodSecurityAdmission (built-in k3s 1.24+) | Cluster-level enforcement that pods meet a security baseline | LOW | Set namespace label `pod-security.kubernetes.io/enforce: restricted` for the `clubcore` namespace. Note: `restricted` profile requires non-root + read-only root filesystem — must be implemented first. |
| CSRF rename: `sportzal_csrf` → `clubcore_csrf` | NAME-01 carry-over from v4.0 scope; additive cookie rename | LOW | Already scoped in PROJECT.md as an additive change (`cc_access`/`cc_refresh`/`clubcore_csrf` are the real names; the v3.0 migration already happened). Verify and document. |

**Differentiators — justified for this project:**

| Feature | Value Proposition | Complexity | Notes |
|---------|-------------------|------------|-------|
| Kubernetes RBAC for service accounts | Each workload (backend, bot, arq) should have a dedicated ServiceAccount with only the permissions it needs within the cluster | MEDIUM | Create `ServiceAccount` for each Deployment. The backend SA does not need to call the k8s API at all (it only calls Postgres/Redis/MinIO). Minimal RBAC: no ClusterRole needed for app services. Only the metrics-reader SA for Prometheus needs get/list/watch permissions. |
| Network egress restrictions for non-network services | The Alembic migrate Job should not be able to reach the internet during runtime | LOW | NetworkPolicy with `egress: [{to: [{podSelector: {app: postgres}}]}]` on the migrate Job. |

**Anti-Features — do NOT do:**

| Feature | Why Requested | Why It's Wrong Here | What to Do Instead |
|---------|---------------|---------------------|-------------------|
| HashiCorp Vault | "Enterprise secret management" | Vault is a production secret management platform that requires its own HA deployment, unsealing procedure, and lease management. For a single-gym pet project, it's more infrastructure than the app itself. SOPS with a local age key stored on the operator's machine is sufficient. | SOPS + age key |
| OPA / Gatekeeper policy enforcement | "Policy as code" | OPA Gatekeeper is a validating admission webhook that enforces custom policies. For a single developer, PodSecurityAdmission (built into k3s) covers the practical security needs. OPA requires writing Rego policies and maintaining a separate webhook deployment. | PodSecurityAdmission `restricted` profile |
| Full CIS Kubernetes Benchmark implementation | "Hardened cluster" | The CIS benchmark has 100+ controls. Implementing all of them would consume more time than the rest of the milestone combined. Many controls (e.g., etcd encryption, audit logging to external system) are irrelevant for a single-node pet project. | Non-root pods + NetworkPolicies + PodSecurityAdmission covers the relevant threat model |
| Image vulnerability scanning in a remote registry (Trivy + registry webhook) | "Continuous CVE monitoring" | No remote registry. Local `make scan` before deploy is sufficient for the solo-dev workflow. | Local `trivy image` in the Makefile |
| Runtime security (Falco) | "Detect anomalous container behavior at runtime" | Falco is a kernel-level eBPF/ptrace security monitor. Excellent for production multi-tenant environments. Adds a privileged DaemonSet and alert noise for a single-user system. | Standard logging via Loki — application logs capture security-relevant events (audit log already has 69 locked events) |
| Mutual TLS between services | Already listed in Networking anti-features | See above | NetworkPolicies |

---

### Dimension 6: Observability

**Table Stakes — must have:**

| Feature | Why Expected | Complexity | Notes |
|---------|--------------|------------|-------|
| Prometheus + kube-state-metrics + node-exporter | Cluster-level metrics: pod status, CPU/memory, node health | MEDIUM | Deploy via `kube-prometheus-stack` Helm chart (bundles Prometheus, Alertmanager, kube-state-metrics, node-exporter, Grafana). One chart deploys the full stack. |
| FastAPI metrics endpoint (`/metrics`) | Application-level metrics: request rate, latency by endpoint, error rate, active connections | MEDIUM | `prometheus-fastapi-instrumentator` library. Expose `GET /metrics` (Prometheus text format). Add a `ServiceMonitor` CRD so Prometheus scrapes it automatically. |
| Grafana with pre-built dashboards | Visualize metrics; the stated done-bar requires dashboards for latency/errors/resources/cron | MEDIUM | Import community dashboards: FastAPI dashboard (ID: 14282 or equivalent), node-exporter dashboard (ID: 1860), Postgres dashboard (ID: 9628), Redis dashboard (ID: 11835). Persist Grafana data in a PVC. |
| Loki + Promtail for structured log aggregation | structlog JSON logs from the backend must be queryable | MEDIUM | Deploy Loki + Promtail (Grafana Loki stack Helm chart). Promtail as a DaemonSet reads container logs from `/var/log/pods/`. Loki stores them. Grafana connects to Loki as a data source. |
| JSON log format from backend (structlog) | Loki benefits from structured logs; structlog JSON is already used | LOW | Already implemented. Verify the Promtail pipeline parses JSON correctly and indexes `level`, `event`, `module` fields as labels. |
| Basic alerting rules (Alertmanager) | Operator needs to know when the service is down, not just when they check manually | MEDIUM | Critical alerts: pod CrashLoopBackOff, pod OOMKilled, Postgres unavailable, disk > 80%, TLS cert expiry < 14 days. Route to Telegram (Alertmanager has a Telegram receiver) — consistent with the existing Telegram notification channel. |
| ARQ cron job success/failure metrics | The 7 cron jobs (expire memberships, send notifications, mark no-show, etc.) must be observable | MEDIUM | Options: (1) ARQ exposes job metrics via a custom endpoint; (2) structlog emits a `cron_job_completed` event with result, which Loki captures and can be alerted on. Option 2 is simpler — no ARQ metrics plugin needed. Add a Loki-based alert rule: no `cron_job_completed` event for `expire_memberships` in the last 26 hours. |

**Differentiators — justified for this project:**

| Feature | Value Proposition | Complexity | Notes |
|---------|-------------------|------------|-------|
| Telegram Alertmanager receiver | Alerts arrive where the operator already works (Telegram), not in a separate system | LOW | Alertmanager Telegram integration: `telegram_configs` in alertmanager.yaml. Sends to the operator's personal Telegram or a dedicated alerts group. Consistent with the existing bot infrastructure. |
| Grafana dashboard for ЮKassa payment success/failure rate | Payment failures are high-priority operational events; a dashboard panel makes them visible without log-searching | MEDIUM | Requires a counter metric in the backend: `yookassa_webhook_received_total` with labels `event_type` (payment.succeeded, payment.canceled, refund.succeeded). One Prometheus counter, one Grafana panel. |
| Uptime/availability SLI panel in Grafana | A single "is it up?" panel is the most useful thing for a solo operator | LOW | Probe endpoint with `blackbox-exporter` or simply use the backend `GET /healthz` scrape success metric from Prometheus. |

**Anti-Features — do NOT do:**

| Feature | Why Requested | Why It's Wrong Here | What to Do Instead |
|---------|---------------|---------------------|-------------------|
| Distributed tracing (Jaeger, Tempo, OpenTelemetry) | "End-to-end request tracing" | Distributed tracing shines when requests span multiple independently deployed services. This is a monolith — a FastAPI request goes to one process. structlog's correlation IDs + Loki log search achieves the same debugging goal. Tracing adds an entire new storage backend (Tempo) and instrumentation overhead. | structlog `request_id` in every log line. Loki query `{app="backend"} |= "request_id=abc123"` traces a request. |
| SLO/SLA tracking with error budget burn rates | "Reliability engineering" | Error budgets make sense when there is a team and release velocity to optimize. Solo developer with AI agents does not need burn-rate alerts. | Simple error rate alert (>5% 5xx in 5 minutes → alert). |
| Synthetic monitoring (endpoint probing from multiple regions) | "Global availability monitoring" | The gym is in one city, clients are in one city. Multi-region probing is meaningless. | Single `blackbox-exporter` probe from within the cluster or from the host. |
| PagerDuty / Opsgenie integration | "On-call rotation management" | No team, no on-call rotation. Telegram alert is sufficient. | Alertmanager → Telegram |
| More than 10 alert rules | "Comprehensive alerting" | Alert fatigue is a real problem. 10 well-tuned alerts are better than 100 noisy ones. For this app, 5-7 critical alerts are sufficient. | Pod down, OOM, disk >80%, error rate, cert expiry, Postgres lag (replication if added), no cron in 26h |
| Log retention > 30 days in Loki | "Audit trail" | The application already has a Postgres-backed, 69-event `audit_log` table for business audit. Loki is for operational debugging, not business audit. 30 days of logs is sufficient for debugging recent incidents. | `loki.retention: 30d`. The audit_log table is the business record. |

---

### Dimension 7: Backup and Recovery

**Table Stakes — must have:**

| Feature | Why Expected | Complexity | Notes |
|---------|--------------|------------|-------|
| Postgres backup CronJob → object storage | Postgres is the single source of truth for all business data (clients, memberships, payments, audit log). Loss = catastrophic. | MEDIUM | k8s CronJob using `pg_dump` → gzip → `mc` (MinIO client) → object storage bucket. Daily at 03:00 MSK. Retention: 7 daily + 4 weekly. Use a dedicated `backup` ServiceAccount with minimal permissions. |
| Tested restore procedure (documented runbook) | A backup that has never been tested is not a backup. The project already has a precedent: v1.10 DB rename round-trip was verified. | MEDIUM | Runbook: (1) download latest backup from object storage, (2) `pg_restore` to a test Postgres instance, (3) verify row counts, (4) verify application startup against restored DB. Document in `infra/runbooks/restore.md`. Mark as operator-pending (requires live MinIO + production backup to exist). |
| Redis backup (RDB snapshot) | Redis holds active sessions, rate-limit state, idempotency keys, circuit-breaker state, ARQ queue, and WS pub/sub state. Losing Redis means all active sessions are invalidated and in-flight ARQ jobs are lost. | LOW | Redis 7 RDB snapshot (`SAVE` command or `save 3600 1` config). Snapshots copied to object storage by the same backup CronJob. On restore: copy RDB file to the Redis PVC and restart the pod. |
| Object storage backup (MinIO → external) | Chat photo attachments are stored in MinIO. Loss = permanent loss of user-uploaded content. | LOW | `mc mirror minio/photos external-backup/photos` — periodic sync to another storage location (local disk snapshot, external USB, or a second object store bucket). Low priority at current scale (chat is a secondary feature), but should be documented. |
| Backup retention policy declared | Without a retention policy, backups accumulate indefinitely and fill the disk | LOW | 7 daily + 4 weekly + 3 monthly Postgres dumps. Implemented in the backup script via `mc rm --older-than` or a lifecycle policy on the MinIO bucket. |
| RTO and RPO targets declared (for documentation) | Defines what "recovery" means for this project; prevents scope creep | LOW | **RPO: 24 hours** (daily backup; acceptable for a single gym — at worst, yesterday's data is restored, manual re-entry for the day). **RTO: 4 hours** (restore Postgres from backup, redeploy k3s cluster, verify). These are pet-project targets, not SLA commitments. |

**Differentiators — justified for this project:**

| Feature | Value Proposition | Complexity | Notes |
|---------|-------------------|------------|-------|
| Backup verification CronJob (weekly pg_restore smoke) | A weekly smoke test that restores the latest backup to a test database and checks row counts — catches backup corruption before an actual disaster | HIGH | This is the most valuable backup feature. Creates a temporary Postgres pod, restores the latest backup, runs a SQL count query, posts result to Telegram. Teardown after verification. Complexity is high but the value justifies it as a differentiator. Mark as operator-pending if it doesn't fit in v4.0 scope. |
| Grafana alert: last successful backup > 25 hours old | If the backup job fails silently, the operator needs to know | MEDIUM | The backup CronJob emits a structured log line on success. Loki alert: no `backup_completed` log in 25 hours → Alertmanager → Telegram. |

**Anti-Features — do NOT do:**

| Feature | Why Requested | Why It's Wrong Here | What to Do Instead |
|---------|---------------|---------------------|-------------------|
| Continuous WAL archiving / point-in-time recovery (PITR) | "Recover to any point in time" | PITR requires WAL archiving configuration, a separate WAL archive storage, and a complex restore procedure. For a pet project with RPO=24h, daily `pg_dump` is sufficient and simpler. PITR infrastructure (pgBackRest, Barman) is enterprise complexity. | Daily `pg_dump` + 7-day retention |
| Velero for full cluster backup | "Kubernetes-native cluster backup" | Velero backs up k8s resources (Deployments, ConfigMaps, Secrets, PVCs). For a pet project where the k8s manifests are in Helm/Terraform (and therefore reproducible), only the data volumes need backup. | Postgres pg_dump + Redis RDB + MinIO sync. Kubernetes manifests are reproduced from Helm/Terraform. |
| Multi-region backup replication | "Geo-redundancy" | One gym, one server, one operator. Multi-region replication adds S3/Yandex Object Storage costs and configuration complexity for zero practical benefit until the project scales. | Local disk backup + manual off-site copy (the repo already gets copied to another PC — the same discipline applies to backup files). |
| Backup encryption at rest | "Data protection compliance" | For a Russian single-gym pet project, backup files contain gym CRM data (member names, attendance records). Encryption adds a key management burden. The backup storage (MinIO on the same server) is already protected by OS-level access controls. The threat model (server theft) is addressed by the risk acceptance. | Document the risk; implement if regulatory requirements emerge. |

---

### Dimension 8: CI/CD and Makefile Automation

**Table Stakes — must have:**

| Feature | Why Expected | Complexity | Notes |
|---------|--------------|------------|-------|
| `make build` — build all Docker images | Single command to build all images (backend, bot, arq, migrate, admin-app nginx, client-pwa nginx) | LOW | `docker build -t clubcore/backend:$(VERSION) -f apps/backend/Dockerfile .` × 6 images. VERSION from git describe or a `.version` file. |
| `make lint` — helm lint + terraform validate | Pre-deploy quality gate | LOW | `helm lint charts/clubcore/` + `terraform -chdir=infra validate`. Fast. |
| `make tf-plan` — terraform plan | Review infrastructure changes before applying | LOW | `terraform -chdir=infra plan -out=infra/tfplan` |
| `make tf-apply` — terraform apply (operator-confirmed) | Apply the planned infrastructure changes | LOW | `terraform -chdir=infra apply infra/tfplan`. Operator-confirmed because live apply is outside the v4.0 done-bar. |
| `make deploy` — helm upgrade --install + smoke | Deploy the application to the k3s cluster | MEDIUM | `helm upgrade --install clubcore charts/clubcore/ --values values-prod.yaml --namespace clubcore --wait`. Then run smoke tests. |
| `make smoke` — smoke test against the deployed cluster | Verify the deployment is alive | LOW | Hit `GET /healthz`, verify 200. Optionally: hit the frontend URLs, verify they serve HTML. |
| `make down` — tear down the local kind cluster | Clean up after local development | LOW | `kind delete cluster --name clubcore-local` |
| `make up` — stand up a local kind cluster | Reproducible local k8s environment for testing Helm charts and Terraform | MEDIUM | `kind create cluster --config kind-config.yaml` + load images + deploy. This is the primary local validation workflow. |
| `make scan` — trivy scan all images | Security gate before deploy | LOW | `trivy image --exit-code 1 --severity CRITICAL clubcore/backend:$(VERSION)` × images |
| `VERSION` variable from git or explicit | Ensures images and Helm releases are versioned consistently | LOW | `VERSION ?= $(shell git describe --tags --always)` in the Makefile header. |

**Differentiators — justified for this project:**

| Feature | Value Proposition | Complexity | Notes |
|---------|-------------------|------------|-------|
| `make rollback` — helm rollback to previous release | The most important operational command after a bad deploy; must be a single command | LOW | `helm rollback clubcore -n clubcore`. Documents the release number to roll back to (from `helm history clubcore`). |
| `make logs` — tail logs from all pods | Faster than `kubectl logs -f deploy/backend -n clubcore` | LOW | `kubectl logs -f -l app.kubernetes.io/instance=clubcore -n clubcore --prefix=true`. One Makefile alias. |
| `make psql` — open a psql shell to the Postgres pod | Essential for operational debugging without exposing Postgres externally | LOW | `kubectl exec -it statefulset/postgres -n clubcore -- psql -U clubcore`. |
| `make backup` — trigger a manual backup | On-demand backup before risky operations (migrations, upgrades) | LOW | `kubectl create job --from=cronjob/postgres-backup postgres-backup-manual-$(date +%s) -n clubcore` |

**Anti-Features — do NOT do:**

| Feature | Why Requested | Why It's Wrong Here | What to Do Instead |
|---------|---------------|---------------------|-------------------|
| GitHub Actions / GitLab CI pipeline for deploy | "Automated CI/CD" | No git remote. CI runners require a remote repository to pull from. The existing `.github/workflows/ci.yml` runs the test gates (ruff, mypy, pytest, etc.) — these should continue to be runnable locally. There is no remote to trigger them on. | `make test` runs the same gates locally. `make build && make deploy` is the deploy workflow. |
| ArgoCD / FluxCD GitOps | "Continuous deployment from git" | Requires a git remote, a running CD controller in the cluster, and reconciliation loops. Incompatible with the no-remote-registry constraint. | `make deploy` is the CD pipeline. |
| Semantic versioning automation (semantic-release) | "Automatic version bumps from commit messages" | Solo developer with AI agents; the overhead of semantic-release (npm package, configuration, CI integration) is not worth the automation at this scale. | Manual version tag (`git tag v4.0`) before deployment. `make build VERSION=v4.0`. |
| Container registry (Harbor, Docker Hub push) | "Central image registry" | No git remote. Pushing images to a registry requires either a local registry (which k3s can load from) or a remote one (incompatible with the no-registry constraint). k3s supports `ctr images import` or `kind load docker-image` for local image loading. | `make load-images` — `kind load docker-image` or `k3s ctr images import` for loading images into the cluster without a registry. |
| Automated secret rotation | "Security best practice" | SOPS-encrypted secrets with an age key are rotated manually when needed. Automated rotation requires a secret store (Vault) and a rotation policy engine — overkill for a pet project. | Document the manual rotation procedure in the runbook. |
| Blue/green or canary deployment | Already listed in k8s anti-features | See above | Rolling update |

---

## Feature Dependencies

```
Containerization (hardened images)
  └──required by──> K8s/Helm (Deployments reference images)
  └──required by──> CI/CD (make build produces images)
  └──required by──> Security (trivy scans images)

IaC / Terraform
  └──required by──> K8s cluster existence (k3s install via Terraform)
  └──required by──> Namespace + ServiceAccount creation
  └──used by──> Secrets management (SOPS-decrypted values fed to Terraform)

Secrets management (SOPS/sealed-secrets)
  └──required by──> K8s Secrets (Helm releases need DB password, JWT secret, etc.)
  └──required by──> Terraform (`.tfvars` contain infrastructure credentials)

K8s/Helm (Deployments, StatefulSets, Jobs)
  └──required by──> Networking (Ingress needs Services to exist)
  └──required by──> Observability (ServiceMonitor references Services)
  └──required by──> Backup (CronJobs need PVCs to exist)

Networking (Ingress + TLS)
  └──required by──> Frontends being reachable
  └──required by──> TLS cert-manager (must be deployed before issuing certs)
  └──depends on──> cert-manager Helm chart

Observability (Prometheus + Grafana + Loki)
  └──depends on──> K8s cluster running (deploys as Helm charts into monitoring namespace)
  └──depends on──> Backend /metrics endpoint (for FastAPI metrics)
  └──depends on──> Alertmanager → Telegram (requires Telegram bot token from secrets)

Backup CronJob
  └──depends on──> MinIO running (backup target)
  └──depends on──> Postgres StatefulSet running
  └──depends on──> Secrets (backup credentials for MinIO)

Makefile automation
  └──wraps──> All of the above (orchestration layer)
  └──depends on──> kind (local k3s simulation)
  └──depends on──> terraform CLI, helm CLI, kubectl CLI, trivy CLI installed locally
```

### Dependency Notes

- **Alembic migrate Job must run before backend API Pod becomes ready.** Implemented as a Helm pre-install/pre-upgrade Job hook. If the migration fails, Helm rolls back. The API should have a readiness probe that fails until Postgres is reachable.
- **cert-manager must be deployed before the Ingress is created**, or the `Certificate` resource will remain in a pending state. Deploy cert-manager as a Helm chart dependency with `--wait` before the app chart.
- **Loki requires Promtail to be running on every node** (DaemonSet). On a single-node cluster, this is trivially one pod.
- **Telegram bot token is needed by both the bot worker (application) AND Alertmanager (observability).** These should use the same token (same bot) with separate chat targets, or different tokens/bots. Deduplicate the secret.
- **SOPS age key must be present on the operator's machine** before any `make tf-plan` or `make deploy` can run. This is the single point of failure for the entire secret management scheme. Document prominently in the runbook.

---

## MVP Definition (Phase ordering implications)

### Phase group 1: Foundation (must be first)
- [x] Containerization — production images for all 6 components
- [x] IaC foundation — Terraform modules for k3s host + namespaces
- [x] Secrets management — SOPS setup + initial secrets encrypted

### Phase group 2: Core k8s (requires group 1)
- [x] Helm chart — all Deployments, StatefulSets, ConfigMaps, Secrets
- [x] Alembic migrate Job as Helm pre-upgrade hook
- [x] Resource limits + liveness/readiness probes

### Phase group 3: Networking + Security (requires group 2)
- [x] Ingress + TLS (cert-manager, self-signed locally)
- [x] NetworkPolicies (default-deny + explicit allow)
- [x] Pod security contexts (non-root, read-only root fs, drop capabilities)
- [x] Trivy scan in Makefile

### Phase group 4: Observability (requires group 2)
- [x] kube-prometheus-stack (Prometheus + Grafana + Alertmanager)
- [x] Loki + Promtail
- [x] FastAPI /metrics endpoint
- [x] Grafana dashboards (FastAPI, node-exporter, Postgres, Redis)
- [x] Alert rules (pod down, OOM, disk, cert expiry, error rate)
- [x] Alertmanager → Telegram

### Phase group 5: Backup + Runbook (requires group 2 + 3)
- [x] Postgres backup CronJob → MinIO
- [x] Redis RDB backup
- [x] Restore runbook (documented, operator-pending execution)
- [x] Production runbook (topology, deploy, rollback, backup/restore, troubleshooting)

### Phase group 6: Makefile + Local Validation (continuous, wraps all above)
- [x] `make up/down/build/deploy/smoke/rollback/scan/logs/psql/backup`
- [x] `make lint` (helm lint + terraform validate)
- [x] `make tf-plan` green
- [x] kind-based local k3s smoke test

---

## Sources

- PROJECT.md — v4.0 milestone scope, locked decisions, existing topology
- PROJECT.md — no git remote constraint, local Makefile CI/CD requirement
- k3s documentation — default ingress (Traefik), CNI (Flannel), local-path provisioner, PodSecurityAdmission
- kube-prometheus-stack Helm chart — standard observability bundle for k8s
- Grafana Loki Helm chart — log aggregation for k8s
- cert-manager documentation — TLS automation for bare-metal k3s
- SOPS + age — secret encryption without a secret server
- mozilla/sops + helm-secrets plugin — Helm values encryption pattern
- Trivy — container image CVE scanning
- ARQ documentation — internal cron scheduler (no k8s CronJob needed for ARQ cron)
- Existing codebase: `docker compose` topology, `apps/backend/Dockerfile` (already exists), `.github/workflows/ci.yml` (7 gates)

---

*Feature research for: v4.0 Production Infrastructure — Self-Hosted k3s*
*Researched: 2026-06-16*

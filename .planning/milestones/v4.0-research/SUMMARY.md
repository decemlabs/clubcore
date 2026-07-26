# Project Research Summary

**Project:** clubcore v4.0 Production Infrastructure — Self-Hosted k3s
**Domain:** On-prem bare-metal k3s; IaC; observability; secrets; backup
**Researched:** 2026-06-16
**Confidence:** HIGH

---

## Executive Summary

v4.0 is a pure infra/DevOps milestone — no business features, no OpenAPI changes beyond the additive CSRF cookie rename (NAME-01). The starting point is a proven `docker compose up` stack: FastAPI backend with WebSocket chat, a Telegram long-polling worker, an ARQ cron scheduler, one-shot Alembic migrate, Postgres 16, Redis 7 (sessions/queue/pub-sub), SeaweedFS object storage, and two nginx-served SPAs. The goal is to lift this topology into a bare-metal k3s cluster declared as code (Terraform + Helm), with the done-bar set at **local validation only** — k3d smoke + `terraform validate/plan` + `helm lint` — before an operator-confirmed live apply.

The recommended approach builds in layers: harden and finalise all Docker images first (production multi-stage, non-root, pinned digests, trivy-clean), then author the Helm umbrella chart component by component (stateful services → migrate Job → app Deployments → networking + TLS → observability → backup), and wrap everything with a Terraform IaC layer and a root-level Makefile. Three decisions have critical external forcing functions: ingress-nginx was **retired and archived March 2026** — use only Traefik (bundled with k3s); the MinIO community repository was **archived April 2026** — keep SeaweedFS with its actively maintained Helm chart (v4.33.0); Bitnami Helm images are **behind the Broadcom paywall** — use CloudNativePG for Postgres and a plain StatefulSet for Redis.

The highest operational risks are: (1) ARQ cron double-fire and Telegram duplicate polling if Deployment `strategy: Recreate` + `replicas: 1` invariants are ever violated; (2) Postgres PVC node-affinity data loss on pod reschedule using k3s `local-path-provisioner`; (3) sealed-secrets controller key loss on cluster rebuild when there is no git remote — mitigated by immediately exporting and backing up the key to the off-node PC. Secrets management is resolved in favour of **sealed-secrets as primary** (k8s-native, well-suited for a no-git-remote project) with no SOPS layer needed.

---

## Reconciliation Decisions

Three researcher disagreements are resolved here. These decisions override conflicting recommendations in the individual research files.

### R1: Postgres in-cluster — CloudNativePG operator vs plain StatefulSet

**Decision: CloudNativePG (CNPG) operator.**

Bitnami PostgreSQL Helm chart is paywalled (images moved to `bitnamilegacy`, no updates). That leaves CNPG or a plain StatefulSet. CNPG wins on two concrete v4.0 deliverables: (a) built-in WAL archiving + scheduled base backups to any S3-compatible endpoint (SeaweedFS), which is the Postgres backup story without a separate `pg_dump` CronJob; (b) own PostgreSQL images from `ghcr.io/cloudnative-pg/postgresql:16-bookworm`, completely Bitnami-free. Operator complexity is manageable at `instances: 1`: `helm install cnpg` + one `Cluster` CR. For a solo dev the operational cost is lower than maintaining a custom backup CronJob + ReclaimPolicy + nodeSelector setup. Deploy with `instances: 1`; bump to 2 for HA when needed — a one-line Cluster CR change.

### R2: Object storage — SeaweedFS vs MinIO

**Decision: SeaweedFS in both docker-compose and k3s.**

The MinIO community (`minio/minio`) GitHub repository was archived April 25, 2026. Pre-compiled binary releases are discontinued; the community Helm chart is frozen. ARCHITECTURE.md's recommendation to switch to MinIO in k3s was written without knowledge of the archive event. SeaweedFS is the correct call: already in the docker-compose stack; S3 API is a drop-in replacement (zero app code change — same boto3/aioboto3 client, same env vars); Helm chart v4.33.0 (released 2026-06-11) is actively maintained under AGPLv3. Deploy SeaweedFS in standalone mode (`server -s3`) via Helm in both docker-compose and k3s — eliminate the dev/prod split.

### R3: Backend replicas — fixed 2 vs replicas=1

**Decision: `replicas: 1` for v4.0; document the WS-safe path to 2 as a future upgrade.**

FEATURES.md correctly flags HPA as an anti-feature on a single node — there is nowhere to schedule additional pods. ARCHITECTURE.md's note that a **fixed** `replicas: 2` is WS-safe (Redis pub/sub fan-out ensures all backend pods receive and push WebSocket messages) is architecturally correct, but resource contention on a single bare-metal node with Postgres, Redis, SeaweedFS, and the monitoring stack makes `replicas: 2` premature. Start with `replicas: 1`. The `values.prod.yaml` should document: "Increase to 2 when observability data confirms headroom; add Traefik sticky-session annotation to the backend Ingress first." Do NOT add HPA.

---

## Key Findings

### Recommended Stack

All versions verified via GitHub releases and ArtifactHub on 2026-06-16. Version choices are driven by concrete external events, not preference. Full pinned version table in `.planning/research/STACK.md`.

**Core technologies:**

- **k3s v1.33.x (stable channel) + k3d v5.9.0** — production runtime and local mirror. k3d wraps k3s in Docker for genuine parity. Do NOT use kind — it runs a different Kubernetes distribution and hides k3s-specific Traefik/ServiceLB behaviour.
- **Helm v3.21.1** — Helm 4 (released Nov 2025) has breaking schema changes in `terraform-provider-helm`; defer migration. Helm 3 EOL security Feb 2027.
- **Terraform v1.15.6 + providers kubernetes/helm v3.2.0** — local `backend "local"` state. `hashicorp/helm` v3.x changed the `set` block schema to a list of objects — all `helm_release` resources must use the new list syntax.
- **Traefik v3 (bundled with k3s)** — ingress-nginx was officially retired and archived March 2026; no security patches will ever be issued. Traefik is the only viable option.
- **cert-manager v1.20.2** — TLS automation. Use `selfSigned` ClusterIssuer for local k3d validation; `letsencrypt-staging` for iterative testing; LE production ONLY on the operator-confirmed live apply.
- **CloudNativePG operator** — CNCF Sandbox; own PostgreSQL 16 images on ghcr.io; built-in WAL archiving to S3; Bitnami is paywalled.
- **Redis 7 — plain StatefulSet** — `redis:7-alpine`; no operator; ~80 lines of YAML; AOF persistence mandatory (Redis stores sessions, ARQ queue, WS pub/sub — not a cache).
- **SeaweedFS Helm v4.33.0** — S3-compatible; replaces docker-compose `chrislusf/seaweedfs:3.84`; MinIO community archived April 2026.
- **kube-prometheus-stack v86.2.3** — bundles Prometheus Operator, Prometheus, Alertmanager, Grafana, node-exporter, kube-state-metrics. Single-node resource tuning required (see STACK.md values).
- **Loki community chart v17.3.1** — OSS Loki chart moved from `grafana/grafana` to `grafana-community/helm-charts` March 2026; old repo frozen at v6.55.0. Deploy in monolithic mode + Grafana Alloy log shipper (replaces promtail, included as sub-chart).
- **sealed-secrets v0.37.0** — `SealedSecret` manifests are safe on-disk; `kubeseal` CLI seals on the dev machine. CRITICAL: export and back up the controller RSA key immediately after installation.
- **prometheus-fastapi-instrumentator v7.1.0** — pin `>=7.1.0,<8`. v8.0.0 requires FastAPI >=0.133 + Starlette v1; current stack pins fastapi>=0.115.
- **Trivy v0.71.0 + kubeconform v0.8.0** — local Makefile gates only; no in-cluster components.

### Expected Features

See `.planning/research/FEATURES.md` for full tables.

**Must have (table stakes):**
- Production-hardened multi-stage Dockerfiles: non-root user, slim base, no dev deps, `.dockerignore`, healthcheck, pinned digests.
- Separate images for all 6 components (backend, telegram-bot, arq-worker, migrate, admin-app nginx, client-pwa nginx).
- Alembic migrate as Helm `pre-install,pre-upgrade` hook Job — single execution per deploy.
- All Deployments: `resources.requests` + `resources.limits` + `startupProbe` + `livenessProbe` + `readinessProbe`.
- `strategy: Recreate` + `replicas: 1` on telegram-bot and arq-worker — architectural invariant, not a tuning parameter.
- Ingress for three hostnames (API, admin-app, client-pwa) with TLS and HTTP→HTTPS redirect via Traefik middleware.
- NetworkPolicies: default-deny + explicit allow including CoreDNS egress (UDP/TCP 53) for every pod.
- Secrets out-of-repo via sealed-secrets; `TZ=UTC` in all ConfigMaps.
- kube-prometheus-stack + Loki + Alertmanager → Telegram receiver; 5-7 critical alert rules.
- FastAPI `/metrics` via `prometheus-fastapi-instrumentator==7.1.0,<8` + ServiceMonitor CRD.
- CNPG WAL archiving to SeaweedFS S3 as the Postgres backup mechanism.
- Redis AOF persistence (`appendonly yes`, `appendfsync everysec`) + PVC + `maxmemory` + `maxmemory-policy: allkeys-lru`.
- Root-level Makefile: `build`, `scan`, `push`, `tf-validate`, `tf-plan`, `helm-lint`, `helm-validate`, `deploy`, `smoke`, `rollback`, `logs`, `psql`, `backup`, `up`, `down`.
- Terraform local backend; module split: `infra/terraform/host/` + `infra/terraform/cluster/`.

**Defer (v2+):**
HPA, PodDisruptionBudgets, MetalLB, service mesh, ArgoCD/FluxCD, Vault, OPA/Gatekeeper, distributed tracing, image signing, multi-region backup, blue/green deployments, semantic-release automation.

### Architecture Approach

The topology maps one-for-one from docker-compose to Kubernetes primitives. Key structural decisions: one Helm umbrella chart (`helm/clubcore/`) with `values.yaml` (k3d defaults) and `values.prod.yaml` (production overrides); Terraform in two independent layers applied sequentially; observability in a dedicated `monitoring` namespace; backup CronJobs in the app namespace. See `.planning/research/ARCHITECTURE.md` for full component map, Terraform module tree, and Helm chart directory structure.

**Major components:**

1. **Helm umbrella chart** (`helm/clubcore/`) — Deployments for backend (replicas=1), telegram-bot (Recreate/replicas=1), arq-worker (Recreate/replicas=1), admin-app nginx, client-pwa nginx; Redis StatefulSet; CNPG Cluster CR; SeaweedFS Helm chart; migrate Job (pre-install hook); ConfigMaps + Secret refs.
2. **Terraform IaC** — `host/` provisions k3s on the bare-metal node via `null_resource` + `remote-exec`; `cluster/` manages Helm releases and namespaces via kubernetes/helm providers authenticated via kubeconfig from `host/` output.
3. **Observability stack** (`monitoring` namespace) — kube-prometheus-stack + Loki monolithic + Grafana Alloy. Alertmanager routes to Telegram.
4. **Secrets layer** — sealed-secrets controller; `kubeseal` on dev machine; SealedSecret YAMLs committed to repo; controller RSA key backed up off-node.
5. **Makefile automation** — only CI/CD layer; no git remote, no external runner; wraps k3d (local) and kubectl/helm/terraform (prod); local image registry via `k3d --registry-create`.

### Critical Pitfalls

Full details in `.planning/research/PITFALLS.md`.

1. **ARQ cron double-fire + Telegram duplicate polling** — `RollingUpdate` strategy creates a pod overlap window where two instances run simultaneously. Fix: `strategy: Recreate` + `replicas: 1` on arq-worker AND telegram-bot. Encode as a helm lint / kubeconform assertion so it cannot regress.
2. **Postgres PVC node-affinity data loss** — `local-path-provisioner` PVs are node-bound; pod reschedule to another node mounts a blank volume. Fix: `nodeSelector` pinning Postgres to the storage node + `reclaimPolicy: Retain` on the StorageClass. CNPG operator manages this more gracefully via its WAL archive restore path.
3. **Migrate Job races API boot** — without Helm hook ordering, both Job and Deployment are created simultaneously; API hits `column does not exist`. Fix: `helm.sh/hook: pre-install,pre-upgrade` + `helm.sh/hook-weight: "-5"` on migrate Job; optionally add `alembic check` initContainer to backend as belt-and-suspenders.
4. **NetworkPolicy silently breaks DNS** — default-deny without an explicit egress rule to CoreDNS (kube-system, UDP/TCP 53) causes all outbound connections to timeout with no obvious error. Fix: standard DNS egress rule in every pod's NetworkPolicy; test with `nslookup postgres-svc` from each pod.
5. **Sealed-secrets controller key loss** — no git remote means the RSA key lives only on the node. Fix: export key YAML immediately after install; back up to off-node PC alongside the repo.
6. **Redis data loss on pod restart** — sessions, ARQ queue, WS pub/sub lost if only RDB snapshots enabled. Fix: `appendonly yes` + `appendfsync everysec` + `maxmemory` + PVC.
7. **TZ=UTC invariant violated** — copying compose env files can carry `TZ=Europe/Moscow`, causing ARQ crons to fire 3 hours late and corrupting `gym_date STORED` column values. Fix: all containers MUST have `TZ=UTC`; verify with `kubectl exec <pod> -- env | grep TZ`.

---

## Implications for Roadmap

The build order follows hard dependency chains: images before manifests; stateful services before app Deployments; Helm before Terraform; networking/security/observability after the app stack is stable.

### Phase 1: Docker Image Hardening

**Rationale:** Everything else is blocked on correct, production-grade container images. Backend Dockerfile exists but needs hardening; frontend Dockerfiles do not exist yet.
**Delivers:** Production Dockerfiles for all 6 components; `.dockerignore` files; non-root users; pinned base digests; `tzdata` verified; `TZ=UTC` smoke tests; trivy scan green; git-SHA image tagging established.
**Avoids:** Pitfalls P9 (non-root + tzdata + venv PATH + :latest), P10 (nginx SPA fallback + SW caching).

### Phase 2: Helm Chart — Stateful Services (CNPG + Redis + SeaweedFS)

**Rationale:** Stateful services are the dependency foundation for all app Deployments. Validating them in isolation is simpler than debugging alongside app startup issues.
**Delivers:** CNPG operator Helm install + `Cluster` CR (`instances: 1`, WAL archiving to SeaweedFS S3); Redis StatefulSet + ConfigMap (AOF enabled, maxmemory set) + PVC; SeaweedFS Helm chart (standalone S3 mode); `reclaimPolicy: Retain` on StorageClass; PVC binding smoke test in k3d.
**Avoids:** Pitfalls P1 (Postgres PVC node-affinity), P5 (Redis AOF). Bitnami images entirely absent.
**Research flag:** CNPG `Cluster.spec.backup.barmanObjectStore` fields for SeaweedFS S3 endpoint need verification against CNPG v1 API docs during planning.

### Phase 3: Helm Chart — App Workloads + Migration Ordering

**Rationale:** Solve the migrate-before-API ordering problem here; it is the hardest correctness constraint and should be proven before adding workers.
**Delivers:** Migrate Job (`helm.sh/hook: pre-install,pre-upgrade`; `backoffLimit=0`; `activeDeadlineSeconds: 300`; `alembic check` initContainer on backend); backend Deployment (replicas=1, all probes, resource limits); arq-worker Deployment (`strategy: Recreate`, replicas=1, `TZ=UTC`); telegram-bot Deployment (`strategy: Recreate`, replicas=1); ConfigMap/Secret separation.
**Avoids:** Pitfalls P2 (ARQ double-fire), P3 (Telegram duplicate-consume), P4 (migrate race), P11 (OOMKill + liveness), P12 (TZ drift).

### Phase 4: Helm Chart — Frontends, Ingress, TLS

**Rationale:** Networking is the biggest source of iteration debugging. Tackle as a dedicated phase after the app tier is stable.
**Delivers:** admin-app nginx Deployment + Ingress; client-pwa nginx Deployment + Ingress (correct `try_files` SPA fallback + nginx SW cache headers); backend Ingress with WebSocket annotation and `FORWARDED_ALLOW_IPS` set; cert-manager v1.20.2 with `selfSigned` + `letsencrypt-staging` ClusterIssuers; HTTP→HTTPS Traefik middleware.
**Avoids:** Pitfalls P7 (Traefik WS + LE rate limits + redirect loop), P10 (SPA fallback + SW).
**Research flag:** Traefik v3 WebSocket sticky session annotation syntax — verify exact key during planning.

### Phase 5: Secrets Management + Security Hardening

**Rationale:** Finalise secrets workflow before any real credentials are applied. NetworkPolicies come after topology is stable to avoid DNS debugging noise during development.
**Delivers:** sealed-secrets v0.37.0 controller; `kubeseal` workflow; all production secrets sealed + committed; controller RSA key backed up + documented; pod `securityContext` (runAsNonRoot, readOnlyRootFilesystem, allowPrivilegeEscalation: false, drop ALL capabilities); NetworkPolicy default-deny + explicit allow rules including CoreDNS DNS egress; `make scan` Trivy gate; `NAME-01` CSRF cookie rename verified.
**Avoids:** Pitfalls P6 (sealed-secrets key loss), P8 (DNS breakage from missing CoreDNS rule).

### Phase 6: Terraform IaC

**Rationale:** Write Terraform AFTER the Helm chart works. Terraform wraps tested Helm releases; writing TF for untested resources multiplies iteration cost.
**Delivers:** `infra/terraform/host/` module (k3s install via `null_resource` + `remote-exec`; `terraform.tfvars.example`; local state); `infra/terraform/cluster/` module (namespaces; `helm_release` resources using provider v3.2 list syntax; `terraform.tfvars.example`; local state); `make tf-validate` + `make tf-plan` green against k3d.
**Avoids:** Remote state, Terragrunt, Terraform Cloud, multiple workspaces.

### Phase 7: Observability

**Rationale:** Observability is isolated in `monitoring` namespace and does not block the app. Adding after the app stack is stable means ServiceMonitors immediately have live targets to scrape.
**Delivers:** kube-prometheus-stack v86.2.3 (single-node resource tuning: Prometheus 256Mi/512Mi, Grafana 128Mi, Alertmanager 64Mi; 7d retention); Loki community chart v17.3.1 (monolithic mode + Grafana Alloy, 30d retention); `prometheus-fastapi-instrumentator==7.1.0,<8` + `/metrics` endpoint + ServiceMonitor; Grafana dashboards (FastAPI, node-exporter, CNPG Postgres, Redis); 5-7 Alertmanager rules; Alertmanager → Telegram receiver.
**Avoids:** Distributed tracing, Fluentd/Logstash, promtail (use Alloy), instrumentator v8.
**Research flag:** Loki v17.x community chart Alloy sub-chart values schema changed from v6.x — review migration guide during planning.

### Phase 8: Backup + Runbooks

**Rationale:** CNPG WAL archiving is already configured in Phase 2; this phase adds the restore runbook, Redis and SeaweedFS backup CronJobs, and documents the operator-pending boundary.
**Delivers:** CNPG `Cluster.spec.backup` stanza (WAL archiving + daily base backup to SeaweedFS S3); Redis RDB CronJob (weekly copy to SeaweedFS); SeaweedFS mirror CronJob (daily sync to second PVC); 7-daily/4-weekly retention; restore runbook (`infra/runbooks/restore.md`); production runbook (`infra/runbooks/production.md`).
**Avoids:** Velero, PITR/pgBackRest, multi-region replication, backup encryption at this stage.

### Phase 9: Makefile CI/CD + Full Local Smoke

**Rationale:** The Makefile is the glue layer. Write it last when all individual pieces work independently.
**Delivers:** Root-level `Makefile` with all targets; `make up` pipeline (build → scan → push → tf-validate → helm-lint → deploy → smoke) green against k3d; `make smoke` verifying: `/healthz` 200, migrate Job completed, Redis AOF on, `TZ=UTC` on all pods, DNS resolution from each pod, WebSocket upgrade through ingress, SPA fallback routing 200, PWA SW Cache Storage clean; operator-pending list finalised in production runbook.
**Acceptance criteria:** Use the "Looks Done But Isn't" checklist from PITFALLS.md as the complete smoke definition.

### Phase Ordering Rationale

- Images before manifests: k8s resources reference image tags that must exist and be trivy-clean first.
- Stateful services before app Deployments: Postgres and Redis must be running before migrate Job; SeaweedFS must be running before backend lifespan `ensure_bucket` call.
- App workloads before networking: debugging Ingress annotations is easier when pods are confirmed healthy.
- Helm before Terraform: Terraform wraps working Helm releases — not the reverse.
- Secrets + NetworkPolicies after topology is stable: default-deny policies during active development create DNS noise that obscures real bugs.
- Observability after app stack: ServiceMonitors need live targets; Alertmanager Telegram token is a sealed secret finalised in Phase 5.
- Backup after observability: the "no backup log in 25h" alert depends on Alertmanager.
- Makefile last: `make up` is only meaningful when every underlying piece works independently.

### Research Flags

Needs research during planning:
- **Phase 2 (CNPG backup stanza):** Verify exact `barmanObjectStore` fields for SeaweedFS S3 endpoint against CNPG v1 API docs.
- **Phase 4 (Traefik v3 WS sticky):** WebSocket sticky session annotation key may differ between Traefik v2 and v3. Verify before writing the Ingress template.
- **Phase 7 (Loki v17.x Alloy):** Community chart v17.x has a new values schema for the Alloy sub-chart. Review migration guide before writing values files.

Standard patterns (no research phase needed):
- **Phase 1 (Docker):** Multi-stage Dockerfile for Python/nginx is well-documented. No research phase.
- **Phase 3 (Helm hooks):** Helm pre-install hook for Jobs is canonical and stable.
- **Phase 5 (sealed-secrets):** `kubeseal` workflow is well-documented.
- **Phase 6 (Terraform):** `null_resource` + `helm_release` patterns are standard. Verify `hashicorp/helm` v3.x list syntax during writing only.
- **Phase 8 (Backup):** pg_dump CronJob is well-established.
- **Phase 9 (Makefile):** No research phase — use PITFALLS.md "Looks Done But Isn't" as the acceptance checklist.

---

## Confidence Assessment

| Area | Confidence | Notes |
|------|------------|-------|
| Stack | HIGH | All versions verified via GitHub releases and ArtifactHub on 2026-06-16. Archive/retirement events confirmed via official sources. |
| Features | HIGH | Derived from the actual docker-compose topology (read live) + locked milestone decisions from PROJECT.md. No inference needed. |
| Architecture | HIGH | Component mapping derived from live codebase (docker-compose.yml, WorkerSettings, Dockerfile). Single reconciliation (MinIO→SeaweedFS) resolved by STACK.md archive finding. |
| Pitfalls | HIGH | 12 pitfalls derived from live code (ARQ unique=True implementation, Dockerfile USER/chown, TZ comments in workers). All have concrete verification commands. |

**Overall confidence: HIGH**

### Gaps to Address

- **CNPG SeaweedFS backup stanza:** Exact `barmanObjectStore` fields for non-AWS S3 need verification against live CNPG API docs. Documentation lookup during Phase 2 planning.
- **Traefik v3 WebSocket sticky session annotation:** Key may have changed between Traefik v2 and v3. Verify during Phase 4 planning before writing the Ingress template.
- **Loki v17.x Alloy configuration schema:** New community chart sub-chart values keys need to be read during Phase 7 planning.
- **Sealed-secrets key backup as acceptance criterion:** The key backup step must be an explicit Phase 5 acceptance criterion, not a post-hoc action. PITFALLS.md P6 calls this out as a high-risk operator-pending item.
- **prometheus-fastapi-instrumentator v8 upgrade path:** Schedule as a follow-on task with its own regression gate against the 729-test auth stack. Do not couple to any infra phase.

---

## What Local Validation Cannot Catch (Operator-Pending Boundary)

| Item | What Is Missing |
|------|-----------------|
| Let's Encrypt TLS (production ACME) | Switch ClusterIssuer from `letsencrypt-staging` to `letsencrypt-prod` on live server |
| Postgres disk durability on real hardware | Actual bare-metal disk failure is not simulatable in k3d |
| Redis AOF on real power loss | Verify `aof-use-rdb-preamble yes` on live server after deployment |
| YooKassa webhook reachability | Register real webhook URL; send sandbox test payment |
| RU email deliverability (Yandex Postbox) | SPF/DKIM/DMARC verification — pre-existing operator-pending from v1.6 |
| Telegram bot token in production | Set real `TELEGRAM_BOT_TOKEN` in sealed secret before live apply |
| `terraform apply` on real VM | Requires real SSH credentials to the bare-metal server |
| Prometheus alert delivery to Telegram | Alertmanager has no real Telegram bot token in local validation |

---

## Sources

### Primary (HIGH confidence)

- `apps/backend/docker-compose.yml` — live topology (read 2026-06-16)
- `apps/backend/app/workers/__init__.py` (WorkerSettings) — ARQ cron unique=True, TZ=UTC, MSK offsets confirmed
- `apps/backend/Dockerfile` — non-root user, venv PATH, chown coverage
- `.planning/PROJECT.md` — v4.0 milestone scope, locked decisions
- https://github.com/k3s-io/k3s/releases — k3s stable channel v1.33.x (verified 2026-06-16)
- https://github.com/k3d-io/k3d/releases/tag/v5.9.0 — k3d v5.9.0 (2026-06-02)
- https://github.com/helm/helm/releases — Helm v3.21.1 latest v3 (2026-05-14)
- https://developer.hashicorp.com/terraform/install — Terraform v1.15.6 (verified 2026-06-16)
- https://github.com/hashicorp/terraform-provider-helm/releases — v3.2.0; breaking schema change from 2.x confirmed
- https://kubernetes.io/blog/2025/11/11/ingress-nginx-retirement/ — ingress-nginx retirement official
- https://github.com/minio/minio — archived April 25, 2026 (confirmed)
- https://artifacthub.io/packages/helm/prometheus-community/kube-prometheus-stack — v86.2.3 (2026-06-13)
- https://github.com/grafana-community/helm-charts/releases/tag/loki-17.3.1 — Loki community chart v17.3.1 (2026-06-10)
- https://grafana.com/docs/loki/latest/setup/upgrade/upgrade-to-community/ — Loki repo migration official
- https://github.com/bitnami-labs/sealed-secrets/releases/tag/v0.37.0 — v0.37.0 (2026-05-21)
- https://artifacthub.io/packages/helm/seaweedfs/seaweedfs — SeaweedFS Helm v4.33.0 (2026-06-11)
- https://github.com/trallnag/prometheus-fastapi-instrumentator/releases — v8.0.0 breaking; v7.1.0 for FastAPI >=0.115
- https://cert-manager.io/docs/releases/ — v1.20.2 latest stable (2026-04-11)
- https://github.com/aquasecurity/trivy/releases/tag/v0.71.0 — Trivy v0.71.0 (2026-06-01)
- https://newreleases.io/project/github/yannh/kubeconform/release/v0.8.0 — kubeconform v0.8.0 (2026-06-04)

### Secondary (MEDIUM confidence)

- https://www.youngju.dev/blog/database/2026-04-11-kubernetes-database-operators-guide.en — Bitnami paywall + CNPG recommendation
- https://itnext.io/minio-alternative-seaweedfs-41fe42c3f7be — SeaweedFS as MinIO replacement (2026-01-30)
- ARQ 0.28 codebase — `unique=True` cron lock implementation (`arq/cron.py`)
- k3s documentation — local-path-provisioner node affinity behaviour

---

*Research completed: 2026-06-16*
*Ready for roadmap: yes*

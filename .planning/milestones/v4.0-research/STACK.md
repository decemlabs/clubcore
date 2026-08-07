# Stack Research — v4.0 Production Infrastructure

**Domain:** Self-hosted bare-metal k3s deployment, IaC, observability, secrets, backup
**Researched:** 2026-06-16
**Confidence:** HIGH (all versions verified via GitHub releases / ArtifactHub, June 2026)

---

## 1. Kubernetes Platform

### Local Validation Cluster

**Use k3d v5.9.0** (released 2026-06-02) — not kind.

k3d wraps k3s in Docker, so local testing uses the **same binary** that runs on the bare-metal target. kind runs a different vanilla Kubernetes distribution, which can hide k3s-specific behaviour (built-in Traefik, ServiceLB, local-path-provisioner). For a project that deploys to k3s on-prem, k3d is the only tool that gives genuine parity.

```bash
# Install
brew install k3d           # macOS
# or
curl -s https://raw.githubusercontent.com/k3d-io/k3d/main/install.sh | TAG=v5.9.0 bash

# Create a 1-node cluster (mirrors single bare-metal host)
k3d cluster create clubcore \
  --k3s-arg "--disable=traefik@server:0" \   # managed via HelmChartConfig instead
  --port "80:80@loadbalancer" \
  --port "443:443@loadbalancer"
```

### Production Runtime

**k3s — stable channel = v1.33.x** (as of June 2026; stable is pinned at v1.33; k3s maintainers mark a minor version stable only at patch .3/.4). Latest in the v1.33 line is v1.33.12+k3s1.

Do NOT run latest (v1.36.x) on production without waiting for the stable channel to advance.

```bash
# Install on bare-metal host
curl -sfL https://get.k3s.io | INSTALL_K3S_CHANNEL=stable sh -
# Or pin to exact version:
curl -sfL https://get.k3s.io | INSTALL_K3S_VERSION=v1.33.12+k3s1 sh -
```

### kubectl

Ships with k3s (`k3s kubectl`) and is also installed standalone via `brew install kubectl`. Pin to same minor as cluster (1.33).

---

## 2. Package Management — Helm

**Use Helm v3.21.1** (released 2026-05-14, latest v3 as of June 2026).

Helm 4 (released November 2025) exists but has breaking schema changes in the `helm_release` Terraform provider. Migrating a new infra milestone to Helm 4 adds no value and introduces upgrade risk. Helm 3 receives security patches through February 2027. Pin v3 until a dedicated migration sprint.

```bash
brew install helm@3           # macOS
# or
curl https://raw.githubusercontent.com/helm/helm/main/scripts/get-helm-3 | bash
```

---

## 3. Infrastructure as Code — Terraform

**Use Terraform v1.15.6** (released 2026-05-27, latest stable as of June 2026).

OpenTofu v1.12.0 (2026-05-14) is the open-source fork and a drop-in swap if BSL becomes a concern. For this project (no CI/CD runner, no BSL concern, solo developer, local state), HashiCorp Terraform is fine.

**Local state** — `backend "local"` in `terraform.tfstate`. No S3/remote state needed for a single-operator project with no git remote.

### Terraform Providers

| Provider | Version | Purpose |
|----------|---------|---------|
| `hashicorp/kubernetes` | `3.2.0` (2026-06-04) | Deploy K8s resources (Secrets, ConfigMaps, Jobs) via Terraform |
| `hashicorp/helm` | `3.2.0` (2026-06-04) | Manage Helm releases via Terraform `helm_release` resource |
| `hashicorp/null` | `3.x` | `null_resource` + `local-exec` for shell steps (k3s install on host via SSH) |
| `hashicorp/local` | `2.x` | Write kubeconfig, rendered manifests to local files |

**Important:** `hashicorp/helm` v3.0 (released June 2025) switched from SDK v2 to Plugin Framework — breaking schema changes. `set`, `set_list`, and `set_sensitive` are now lists of nested objects, not blocks. If upgrading from an existing helm provider pin, update all `helm_release` resource configs.

```hcl
terraform {
  required_version = ">= 1.15.0"
  required_providers {
    kubernetes = { source = "hashicorp/kubernetes", version = "~> 3.2" }
    helm       = { source = "hashicorp/helm",       version = "~> 3.2" }
    null       = { source = "hashicorp/null",       version = "~> 3.0" }
    local      = { source = "hashicorp/local",      version = "~> 2.0" }
  }
  backend "local" {}
}
```

---

## 4. TLS / Ingress

### Ingress Controller — Traefik v3 (bundled with k3s)

**CRITICAL: ingress-nginx was officially retired and archived March 2026.** No security patches will ever be issued for it again. Do not install ingress-nginx. k3s ships Traefik v3 by default — use it.

Traefik in k3s is managed via a `HelmChartConfig` CRD. Override values at the cluster level without running a separate Helm release.

```yaml
# k3s HelmChartConfig to tune Traefik
apiVersion: helm.cattle.io/v1
kind: HelmChartConfig
metadata:
  name: traefik
  namespace: kube-system
spec:
  valuesContent: |-
    ports:
      web:
        redirectTo: websecure
    logs:
      general:
        level: ERROR
```

Use standard `Ingress` resources with `ingressClassName: traefik`. Traefik-specific middleware (rate-limit, IP allowlist, redirect) goes in `Middleware` CRDs and is referenced via the annotation `traefik.io/router.middlewares`.

### TLS — cert-manager v1.20.2

**cert-manager v1.20.2** (released 2026-04-11, latest stable as of June 2026). Supports Kubernetes 1.32–1.35. For local validation use a `ClusterIssuer` with `selfSigned` issuer or Let's Encrypt staging. For production use Let's Encrypt ACME HTTP-01 (or DNS-01 if wildcard needed).

```bash
helm install cert-manager jetstack/cert-manager \
  --namespace cert-manager --create-namespace \
  --version v1.20.2 \
  --set crds.enabled=true
```

---

## 5. Observability Stack

### Prometheus + Grafana — kube-prometheus-stack

**Use kube-prometheus-stack v86.2.3** (released 2026-06-13, appVersion Prometheus Operator v0.91.0).

This chart bundles Prometheus Operator, Prometheus, Alertmanager, Grafana, node-exporter, kube-state-metrics, and pre-built dashboards. One chart replaces what would otherwise be 4-5 separate installs. The "overkill for single-node" argument does not apply — the chart supports single-node with minimal resources via values overrides.

```bash
helm install kube-prometheus-stack \
  oci://ghcr.io/prometheus-community/charts/kube-prometheus-stack \
  --version 86.2.3 \
  --namespace monitoring --create-namespace \
  -f monitoring-values.yaml
```

Minimum values for single-node (avoids OOM on a small bare-metal host):
```yaml
prometheus:
  prometheusSpec:
    retention: 7d
    resources:
      requests: { memory: 256Mi, cpu: 100m }
      limits:   { memory: 512Mi }
grafana:
  resources:
    requests: { memory: 128Mi, cpu: 50m }
alertmanager:
  alertmanagerSpec:
    resources:
      requests: { memory: 64Mi }
```

### Log Aggregation — Loki

**MIGRATION NOTE (March 2026):** The Loki Helm chart for OSS users moved from the `grafana/grafana` repo to `grafana-community/helm-charts`. The last old-repo release was `6.55.0`. Current community repo release is **loki-17.3.1** (released 2026-06-10, appVersion Loki 3.7.x).

```bash
helm repo add grafana-community https://grafana-community.github.io/helm-charts
helm install loki grafana-community/loki \
  --version 17.3.1 \
  --namespace monitoring \
  -f loki-values.yaml
```

Deploy in **monolithic mode** (single Deployment, single PVC). Microservices/scalable mode is for multi-TB workloads — overkill for a single gym.

Use **Grafana Alloy** (successor to promtail + grafana-agent, now the single recommended log shipper) to tail pod logs and push to Loki. Alloy is included as a sub-chart in the Loki community chart.

### FastAPI Metrics — prometheus-fastapi-instrumentator

**Version to pin: v7.1.0** (released 2025-03-19).

**Do NOT use v8.0.0** at this time. v8 is a breaking release that requires `starlette>=1.0.0` and `fastapi>=0.133.0`. The clubcore backend currently pins `fastapi>=0.115`. FastAPI 0.133.0 (released 2026-02-24) added Starlette v1 support, but upgrading FastAPI is a separate task that needs its own regression gate (729 backend tests, auth stack, middleware). Do not couple that upgrade to the infra milestone.

v7.1.0 works with `fastapi>=0.115` + current Starlette <1.0.

```python
# apps/backend/app/main.py  (additive — no business logic change)
from prometheus_fastapi_instrumentator import Instrumentator
Instrumentator().instrument(app).expose(app)
```

Dependency pin:
```toml
# pyproject.toml addition
"prometheus-fastapi-instrumentator>=7.1.0,<8"
```

---

## 6. Secrets Management

**Use sealed-secrets v0.37.0** (released 2026-05-21).

Reasoning for this project context:

| Option | Verdict | Reason |
|--------|---------|--------|
| **sealed-secrets** | **USE THIS** | Encrypts K8s Secrets with a cluster key; `SealedSecret` manifests are safe to store on-disk or in-repo; `kubeseal` CLI seals on the dev machine |
| SOPS + age | Skip | More powerful but more moving parts — separate key management, per-file encryption ceremony. Overkill for solo no-remote project |
| External Secrets Operator + Vault | Do NOT add | Vault is explicitly in the "what not to add" list; ESO adds an entire control-plane component |

For a no-git-remote project, sealed-secrets is ideal: the `SealedSecret` YAML files can live in the repo tree without exposing plaintext; they can only be decrypted by the controller running in the cluster. If the cluster key is lost, re-seal with a new key (single operator, acceptable risk).

```bash
# Install controller
kubectl apply -f https://github.com/bitnami-labs/sealed-secrets/releases/download/v0.37.0/controller.yaml

# Install kubeseal CLI
brew install kubeseal

# Seal a secret
kubectl create secret generic db-creds \
  --from-literal=password=... \
  --dry-run=client -o yaml \
  | kubeseal --format yaml > infra/secrets/db-creds-sealed.yaml
```

---

## 7. Object Storage

**Keep SeaweedFS. Do NOT switch to MinIO.**

MinIO's community (`minio/minio`) GitHub repository was **archived April 25, 2026**. Pre-compiled binary releases for the community version are discontinued. The community Helm chart at `charts.min.io` is frozen. MinIO now requires building from source (Go) or the commercial AIStor product.

SeaweedFS is the correct call for this project:
- Already in the stack (docker-compose uses `chrislusf/seaweedfs:3.84`)
- S3-compatible API — zero app code changes (same boto3/aioboto3 client)
- Actively maintained — Helm chart **v4.33.0** released 2026-06-11
- AGPLv3 open-source, no paywall
- Single-node standalone mode matches the existing docker-compose topology

```bash
helm repo add seaweedfs https://seaweedfs.github.io/seaweedfs/helm
helm install seaweedfs seaweedfs/seaweedfs \
  --version 4.33.0 \
  --namespace storage --create-namespace \
  -f seaweedfs-values.yaml
```

---

## 8. Stateful Services — Postgres and Redis

### Postgres 16 — CloudNativePG operator

**Do NOT use Bitnami PostgreSQL Helm chart.** Broadcom moved all Bitnami Docker images and Helm chart OCI packages behind a paid subscription in 2025. The `bitnami` org images are now `bitnamilegacy` and receive no updates or security patches.

**Use CloudNativePG (CNPG) operator** — CNCF Sandbox project, fully open-source, uses its own PostgreSQL images (no Broadcom dependency).

```bash
helm repo add cnpg https://cloudnative-pg.github.io/charts
helm install cnpg cnpg/cloudnative-pg \
  --namespace cnpg-system --create-namespace --wait
```

Then declare a `Cluster` resource:
```yaml
apiVersion: postgresql.cnpg.io/v1
kind: Cluster
metadata:
  name: clubcore-pg
  namespace: app
spec:
  instances: 1          # single-gym: 1 instance is correct; add replica later
  imageName: ghcr.io/cloudnative-pg/postgresql:16-bookworm
  storage:
    size: 20Gi
  bootstrap:
    initdb:
      database: clubcore
      owner: app
      secret:
        name: pg-app-secret
```

CNPG handles the `migrate` Job sequencing: the Alembic Job connects after the CNPG cluster reaches `Ready`. CNPG also provides built-in point-in-time recovery and WAL archiving to object storage (SeaweedFS S3 endpoint) — which is the primary Postgres backup mechanism.

For single-gym scale, `instances: 1` is correct. Bump to 2 for HA when needed.

### Redis 7 — plain StatefulSet

For Redis, use a **plain StatefulSet + Service** — no operator, no Helm chart, just ~80 lines of YAML. Redis 7 official image from Docker Hub (`redis:7-alpine`) is unaffected by the Bitnami situation.

The Bitnami Redis chart (even from the legacy org) still functions for Redis since the risk of unpatched Redis images is lower than for a full database, but a plain StatefulSet is simpler and has no vendor dependency at all.

Redis at single-gym scale (sessions + rate-limits + ARQ queue + pub/sub) has no HA requirement. A PVC with local-path-provisioner volume is sufficient.

---

## 9. Image Scanning — Trivy

**Use Trivy v0.71.0** (released 2026-06-01) in the local Makefile. No cluster component needed.

Trivy integrates into the `make build` step: scan each image immediately after `docker build`, block on CRITICAL/HIGH CVEs.

```makefile
IMAGES := backend telegram-bot arq-worker admin-app client-pwa

.PHONY: scan
scan:
	@for img in $(IMAGES); do \
	  echo "==> Scanning $$img"; \
	  trivy image --exit-code 1 --severity CRITICAL,HIGH \
	    --ignore-unfixed clubcore/$$img:$(TAG); \
	done
```

Install:
```bash
brew install trivy          # macOS
# or
curl -sfL https://raw.githubusercontent.com/aquasecurity/trivy/main/contrib/install.sh | \
  sh -s -- -b /usr/local/bin v0.71.0
```

---

## 10. Manifest Validation — kubeconform

**Use kubeconform v0.8.0** (released 2026-06-04). Kubeval is deprecated and unmaintained; kubeconform is the active replacement.

```bash
# Validate all Helm-rendered manifests before apply
helm template clubcore ./charts/clubcore | kubeconform -strict -summary
```

Install:
```bash
brew install kubeconform
# or
go install github.com/yannh/kubeconform/cmd/kubeconform@v0.8.0
```

---

## 11. Makefile Automation (CI/CD)

No external CI runner. No git remote. All automation lives in a root-level `Makefile`.

```
Makefile targets:
  make build         # docker build all images (multi-stage, pinned)
  make scan          # trivy scan all built images
  make push          # push to local registry (k3d built-in registry)
  make tf-plan       # terraform validate + plan
  make tf-apply      # terraform apply (IaC: k3s install + provider bootstrap)
  make helm-lint     # helm lint charts/*
  make helm-validate # helm template | kubeconform -strict
  make deploy        # helm upgrade --install all charts
  make smoke         # wait for pods ready + curl /healthz
  make up            # full pipeline: build → scan → push → deploy → smoke
  make down          # k3d cluster delete (local) / helm uninstall (remote)
```

Local registry: `k3d cluster create` supports `--registry-create` to spin up a local Docker registry at `k3d-registry.localhost:5000`. Images are pushed there; k3d nodes pull directly without internet.

---

## 12. Backup — Postgres + SeaweedFS + Redis

### Postgres (CNPG)
CloudNativePG supports scheduled WAL archiving + base backups to S3 (SeaweedFS endpoint). Configure the `Cluster.spec.backup` stanza pointing at the SeaweedFS S3 endpoint. This is the cleanest backup path — no separate CronJob.

### SeaweedFS
Daily `CronJob` that runs `weed shell` or `mc mirror` to copy bucket contents to a second PVC (local backup) or another S3 bucket. Retention: 7 daily, 4 weekly.

### Redis
Redis RDB snapshot via `CONFIG SET save "3600 1"` — persisted via PVC. Restore = copy RDB file to new pod. Sufficient for a single-gym context.

---

## 13. What NOT to Add

This section is as important as the stack above.

| Tool | Why NOT for this project |
|------|--------------------------|
| **Service mesh (Istio, Linkerd, Cilium mesh)** | Single-node, single-gym, monolith. mTLS between Pods on the same node adds zero security benefit and real ops cost. |
| **ArgoCD / Flux** | GitOps CD requires a git remote. The project deliberately has no git remote — backups are manual file copies to another PC. ArgoCD would be an infrastructure component that cannot function. |
| **Vault** | Sealed-secrets covers the secret management need at 1/20th the operational complexity. Vault requires its own HA setup, unseal ceremony, and audit log. |
| **Multi-node k3s HA** | Single gym = single host. Etcd HA requires minimum 3 nodes. Over-engineering for a pet project. |
| **ingress-nginx** | **RETIRED March 2026**. No security patches will ever be issued. Use Traefik (bundled with k3s). |
| **Helm 4** | Helm 4 (released Nov 2025) has breaking provider schema changes for terraform-provider-helm. Helm 3 is supported through Feb 2027. Migrate in a dedicated sprint, not inside an infra milestone. |
| **Prometheus Adapter / KEDA** | HPA based on custom metrics — irrelevant for a single-gym app where load is deterministic and small. |
| **OPA / Kyverno** | Policy-as-code admission controllers. Adds a blocking webhook to every pod admission. For a solo dev single cluster, the benefit (enforce pod security standards) is met more simply by `securityContext` fields in Helm chart values. |
| **Separate log shipping (Fluentd, Logstash)** | Grafana Alloy (sub-chart in Loki 17.x) does the job. Fluentd/Logstash are overengineered for < 10 pods. |
| **MinIO** | Community repo archived April 2026. No prebuilt binaries. Keep SeaweedFS which is already in the stack and actively maintained. |
| **Bitnami Helm charts (Postgres/Redis)** | Images moved behind Broadcom paywall 2025. Use CloudNativePG for Postgres; plain StatefulSet for Redis. |
| **prometheus-fastapi-instrumentator v8** | Requires FastAPI >=0.133 + Starlette v1. Current stack pins fastapi>=0.115. Upgrading FastAPI mid-infra-milestone risks breaking the 729-test auth stack. Use v7.1.0 now; schedule the FastAPI upgrade separately. |

---

## 14. Version Compatibility Summary

| Component | Version | Verified date | Notes |
|-----------|---------|---------------|-------|
| k3s | v1.33.12+k3s1 (stable channel) | 2026-06-16 | Latest stable; k3d wraps same binary locally |
| k3d | v5.9.0 | 2026-06-02 | Local cluster for `make smoke` |
| kubectl | v1.33.x | — | Ships with k3s |
| Helm | v3.21.1 | 2026-05-14 | v3 EOL security Feb 2027; Helm 4 deferred |
| Terraform | v1.15.6 | 2026-05-27 | Latest stable; local backend |
| tf-provider-kubernetes | v3.2.0 | 2026-06-04 | — |
| tf-provider-helm | v3.2.0 | 2026-06-04 | Breaking schema change from 2.x; new list syntax |
| Traefik | v3 (bundled k3s) | — | ingress-nginx retired March 2026; do not use |
| cert-manager | v1.20.2 | 2026-04-11 | Helm chart; supports k8s 1.32-1.35 |
| kube-prometheus-stack | 86.2.3 | 2026-06-13 | Prometheus Operator v0.91.0 |
| Loki (community chart) | 17.3.1 | 2026-06-10 | Moved to grafana-community repo March 2026 |
| Grafana Alloy | sub-chart in Loki 17.x | — | Successor to promtail; use this, not promtail |
| sealed-secrets | v0.37.0 | 2026-05-21 | Controller + `kubeseal` CLI |
| SeaweedFS Helm | v4.33.0 | 2026-06-11 | Replaces docker-compose `chrislusf/seaweedfs:3.84` |
| CloudNativePG operator | current via cnpg chart | — | CNCF; image: ghcr.io/cloudnative-pg/postgresql:16-bookworm |
| Redis (plain StatefulSet) | redis:7-alpine | — | No Helm chart needed |
| prometheus-fastapi-instrumentator | v7.1.0 | 2025-03-19 | Do NOT use v8 (needs FastAPI >=0.133) |
| Trivy | v0.71.0 | 2026-06-01 | Local Makefile scan, not in-cluster |
| kubeconform | v0.8.0 | 2026-06-04 | Manifest validation; kubeval is dead |

---

## 15. Integration with Existing Stack (docker-compose to k8s mapping)

| docker-compose service | K8s equivalent | Notes |
|------------------------|----------------|-------|
| `backend` | `Deployment` (1 replica) + `Service` + `Ingress` | Same multi-stage Dockerfile, non-root user already set |
| `telegram-bot` | `Deployment` (1 replica, **no HPA**) | Telegram long-polling = single instance only; `strategy: Recreate` |
| `arq-worker` | `Deployment` (1 replica) | ARQ uses `unique=True` cron tasks; single replica avoids duplicate cron fires |
| `migrate` | `Job` (pre-install Helm hook) | `alembic upgrade head`; runs before backend pods start via `helm.sh/hook: pre-install,pre-upgrade` |
| `postgres` | CNPG `Cluster` (1 instance) | PVC via local-path-provisioner; WAL archive to SeaweedFS |
| `redis` | `StatefulSet` (1 replica) + `Service` | Plain YAML, redis:7-alpine, PVC for RDB snapshot |
| `s3` (SeaweedFS) | SeaweedFS Helm chart, standalone mode | `S3_ENDPOINT_URL` env points to in-cluster ClusterIP Service |
| `mailpit` | Omit from K8s | Dev-only; not part of production cluster |

---

## Sources

- https://github.com/k3s-io/k3s/releases — k3s v1.36.1+k3s1 latest; stable channel = v1.33.x (verified 2026-06-16)
- https://github.com/k3s-io/k3s/discussions/12950 — stable channel tracks .3/.4 patch (confirmed)
- https://github.com/k3d-io/k3d/releases/tag/v5.9.0 — k3d v5.9.0 (2026-06-02)
- https://github.com/helm/helm/releases — Helm v3.21.1 latest v3 (2026-05-14); v3 EOL note confirmed
- https://github.com/helm/helm-www/blob/main/blog/2026-06-02-helm3-eol.md — Helm 3 EOL timeline official
- https://developer.hashicorp.com/terraform/install — Terraform v1.15.6 (verified 2026-06-16)
- https://github.com/hashicorp/terraform-provider-kubernetes/releases — v3.2.0 (2026-06-04)
- https://github.com/hashicorp/terraform-provider-helm/releases — v3.2.0 (2026-06-04)
- https://kubernetes.io/blog/2025/11/11/ingress-nginx-retirement/ — ingress-nginx retirement announced
- https://dev.to/devpops/how-to-properly-set-up-k3s-on-your-homelab-or-server-2026-edition-595 — ingress-nginx archived March 2026 confirmed
- https://cert-manager.io/docs/releases/ — v1.20.2 latest stable (2026-04-11)
- https://artifacthub.io/packages/helm/prometheus-community/kube-prometheus-stack — v86.2.3 (2026-06-13)
- https://github.com/grafana-community/helm-charts/releases/tag/loki-17.3.1 — Loki community chart v17.3.1 (2026-06-10)
- https://grafana.com/docs/loki/latest/setup/upgrade/upgrade-to-community/ — Loki repo migration official docs
- https://github.com/bitnami-labs/sealed-secrets/releases/tag/v0.37.0 — v0.37.0 (2026-05-21)
- https://artifacthub.io/packages/helm/seaweedfs/seaweedfs — SeaweedFS Helm v4.33.0 (2026-06-11)
- https://github.com/minio/minio — minio/minio repo ARCHIVED April 25, 2026
- https://github.com/aquasecurity/trivy/releases/tag/v0.71.0 — Trivy v0.71.0 (2026-06-01)
- https://newreleases.io/project/github/yannh/kubeconform/release/v0.8.0 — kubeconform v0.8.0 (2026-06-04)
- https://github.com/trallnag/prometheus-fastapi-instrumentator/releases — v8.0.0 breaking (Starlette v1); v7.1.0 for FastAPI >=0.115
- https://github.com/fastapi/fastapi/releases/tag/0.133.0 — FastAPI 0.133.0 = first Starlette v1 release (2026-02-24)
- https://www.youngju.dev/blog/database/2026-04-11-kubernetes-database-operators-guide.en — Bitnami paywall + CNPG recommendation
- https://jasongodson.com/blog/cloudnative-pg-migration/ — Bitnami images moved to bitnamilegacy, no updates
- https://itnext.io/minio-alternative-seaweedfs-41fe42c3f7be — SeaweedFS as MinIO replacement (2026-01-30)

---
*Stack research for: clubcore v4.0 Production Infrastructure (on-prem k3s)*
*Researched: 2026-06-16*

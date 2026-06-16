---
phase: 120-iac-observability-backup
plan: "02"
subsystem: observability
tags: [obs, prometheus, loki, alloy, grafana, alertmanager, telegram, fastapi-metrics, servicemonitor, networkpolicy]
dependency_graph:
  requires: [120-01]
  provides: [backend-metrics, servicemonitor, observability-values, grafana-dashboards, alertmanager-rules]
  affects: [apps/backend, infra/helm/clubcore, infra/observability]
tech_stack:
  added:
    - prometheus-fastapi-instrumentator==7.1.0
    - prometheus-client==0.25.0 (transitive)
  patterns:
    - Instrumentator().instrument(app).expose() inside create_app() — additive, no middleware regression
    - include_in_schema=False keeps /metrics out of OpenAPI security enforcement
    - ServiceMonitor CR gated on observability.serviceMonitor.enabled (CRD presence gate)
    - monitoring-ns ingress NetworkPolicy rule — intra-cluster Prometheus scrape only
    - Loki SingleBinary monolithic mode (filesystem, 30d, tsdb v13 schema)
    - Alloy DaemonSet: discovery.kubernetes → loki.source.kubernetes → loki.write
    - PrometheusRule CRD (6 alert rules) + Alertmanager Telegram receiver via bot_token_file
key_files:
  created:
    - infra/helm/clubcore/templates/servicemonitor-backend.yaml
    - infra/observability/kube-prometheus-stack-values.yaml
    - infra/observability/loki-values.yaml
    - infra/observability/alloy-values.yaml
    - infra/observability/grafana-dashboards/fastapi.json
    - infra/observability/grafana-dashboards/node-exporter.json
    - infra/observability/grafana-dashboards/cnpg-postgres.json
    - infra/observability/grafana-dashboards/redis.json
    - infra/observability/grafana-dashboards/README.md
    - infra/observability/alertmanager-rules.yaml
  modified:
    - apps/backend/pyproject.toml
    - apps/backend/app/main.py
    - apps/backend/uv.lock
    - infra/helm/clubcore/templates/networkpolicy-allow.yaml
    - infra/helm/clubcore/values.yaml
decisions:
  - "prometheus-fastapi-instrumentator pinned <8 (ADVOPS-01: v8 requires FastAPI >=0.133 + Starlette v1 — deferred)"
  - "Instrumentator placed after include_router(api) before _customize_openapi — keeps /metrics out of cookieAuth/csrfHeader global security"
  - "ServiceMonitor gated on observability.serviceMonitor.enabled:false default (CRD absent until OBS-01 installed)"
  - "Loki SingleBinary/filesystem (not SeaweedFS S3) — keeps observability independent of application storage"
  - "Grafana dashboards: node-exporter ID 1860, CNPG ID 20417, Redis ID 763 (curated grafana.com); FastAPI custom (instrumentator metrics)"
  - "6 alert rules chosen: pod-down, 5xx-error-rate, disk-pressure, cert-expiry, no-backup-25h (BAK-01 CNPG metric), restore-verify-failed (BAK-04)"
  - "Telegram bot_token_file (not inline) — T-120-OBS2; delivery OPERATOR-PENDING"
metrics:
  duration: "~25 minutes"
  completed: "2026-06-16"
  tasks_completed: 3
  tasks_total: 4
  files_created: 10
  files_modified: 5
---

# Phase 120 Plan 02: Observability Summary

Stand up the full clubcore observability stack: FastAPI `/metrics` instrumentation, ServiceMonitor scrape path, Prometheus/Loki/Alloy values, Grafana dashboards, and Alertmanager rules with Telegram receiver.

## What Was Built

### OBS-03: FastAPI /metrics Instrumentation (Task 1)

**Dependency installed:** `uv add 'prometheus-fastapi-instrumentator>=7.1,<8'` SUCCEEDED (network up). `prometheus-fastapi-instrumentator==7.1.0` + `prometheus-client==0.25.0` installed via uv; `uv.lock` updated.

**Backend instrumentation** (`apps/backend/app/main.py`):
- Import added: `from prometheus_fastapi_instrumentator import Instrumentator` (alpha-ordered in third-party group, after fastapi.routing before structlog — but actually placed correctly between fastapi and structlog)
- Wired inside `create_app()` after `app.include_router(api)`, before `_customize_openapi` closure: `Instrumentator().instrument(app).expose(app, endpoint="/metrics", include_in_schema=False)`
- `include_in_schema=False` is load-bearing: the `_customize_openapi` post-processor applies a global `security=[{cookieAuth, csrfHeader}]` to all schema paths; `/metrics` is excluded so the Prometheus scrape endpoint is never force-secured

**Behavior tests (all PASS — dep installed, tests run live):**
- Test 1: `/metrics` route registered in FastAPI routes
- Test 2: `/metrics` NOT in `create_app().openapi()["paths"]` (include_in_schema=False working)
- Test 3: `/healthz` still returns 200 (instrumentation is additive, no regression)

**ServiceMonitor** (`infra/helm/clubcore/templates/servicemonitor-backend.yaml`):
- `apiVersion: monitoring.coreos.com/v1` / `kind: ServiceMonitor`
- Gated on `{{- if .Values.observability.serviceMonitor.enabled }}`
- Targets backend Service via `clubcore.selectorLabels` + `component: backend`; endpoint port `http`, path `/metrics`, interval from values (default 30s)
- `namespaceSelector` scoped to the release namespace

**NetworkPolicy** (`infra/helm/clubcore/templates/networkpolicy-allow.yaml`):
- Added second `ingress` entry to Policy 1 (backend): `namespaceSelector matchLabels kubernetes.io/metadata.name: monitoring` on TCP :8000
- Traefik/kube-system rule and P8 CoreDNS egress untouched

**values.yaml**: added `observability.serviceMonitor.{enabled: false, interval: "30s"}` subtree with documentation comment.

### OBS-01/02: kube-prometheus-stack + Loki + Alloy Values (Task 2)

**kube-prometheus-stack-values.yaml** (chart v86.2.3):
- Prometheus: `retention: 7d`, `serviceMonitorSelectorNilUsesHelmValues: false` (cross-ns ServiceMonitor discovery), single-node resource tuning
- Grafana: admin via `existingSecret: grafana-admin-credentials` (no plaintext — T-120-OBS4), sidecar dashboard autodiscovery enabled
- Alertmanager: enabled with PVC storage
- NodeExporter + kubeStateMetrics: enabled (feed OBS-04 dashboards)
- k3d-noisy components disabled: `kubeControllerManager`, `kubeScheduler`, `kubeProxy`, `kubeEtcd`

**loki-values.yaml** (chart v17.3.1 — RESEARCH-RESOLVED paths used verbatim):
- `deploymentMode: SingleBinary`, `loki.commonConfig.replication_factor: 1`
- `loki.storage.type: filesystem`, `loki.auth_enabled: false`
- `loki.schemaConfig.configs`: tsdb / v13 schema from 2024-01-01
- `loki.limits_config.retention_period: 720h` (30 days), `loki.compactor.retention_enabled: true`
- `singleBinary.replicas: 1` with 30Gi PVC
- `chunksCache.enabled: false`, `resultsCache.enabled: false`, `minio.enabled: false`
- `backend/read/write replicas: 0` (scale-out disabled)
- `gateway.enabled: true` (Alloy push endpoint)

**alloy-values.yaml** (RESEARCH-RESOLVED paths used verbatim):
- `controller.type: daemonset`, `alloy.mounts.varlog: true`
- `alloy.configMap.content`: River pipeline — `discovery.kubernetes "pods"` → relabeling (pod/namespace/container/component labels) → `loki.source.kubernetes "pod_logs"` → `loki.write "default"` (endpoint `http://loki-gateway.monitoring.svc.cluster.local/loki/api/v1/push`)

All three files YAML-valid (python `yaml.safe_load` verified).

### OBS-04/05: Grafana Dashboards + Alertmanager Rules (Task 3)

**Dashboards** (all JSON-valid):
- `fastapi.json`: custom dashboard wired to `prometheus-fastapi-instrumentator` metrics; panels for RPS, error-rate stat, p50/p99 latency stats, request rate by status, latency percentiles timeseries, top-10 paths by rate
- `node-exporter.json`: import wrapper for grafana.com ID 1860 (Node Exporter Full by rfmoz) with basic CPU/memory/disk stat panels
- `cnpg-postgres.json`: import wrapper for grafana.com ID 20417 (CloudNativePG official) with cluster-up, last-backup-age (wired to `cnpg_collector_last_available_backup_timestamp`), and connections panels
- `redis.json`: import wrapper for grafana.com ID 763 (Redis Dashboard by oliver006); requires `oliver006/redis_exporter`
- `README.md`: grafana.com IDs, FastAPI metric mapping, ConfigMap sidecar import path

**alertmanager-rules.yaml** (6 alert rules + Telegram receiver):
- `kind: PrometheusRule`, `labels.release: kube-prometheus-stack` (discovery label)
- 6 rules covering the OBS-05 requirement set:
  1. `KubePodNotReady` — pod in Pending/Unknown/Failed >5m (severity: critical)
  2. `HighHTTPErrorRate` — 5xx/total >5% over 5m (severity: critical)
  3. `NodeDiskPressure` — root filesystem <15% free (severity: warning)
  4. `CertManagerCertExpiringSoon` — cert expiry <14 days (ties to NET-03)
  5. `PostgresNoBackupIn25h` — `time() - cnpg_collector_last_available_backup_timestamp > 25*3600` (BAK-01 metric)
  6. `RestoreVerifyJobFailed` — BAK-04 restore-verify CronJob `kube_job_failed > 0`
- Alertmanager ConfigMap: route → Telegram receiver, `bot_token_file: /etc/alertmanager/secrets/telegram/bot_token` (T-120-OBS2 — no inline token), `chat_id: -1001234567890` (placeholder, OPERATOR-PENDING)

### Task 4: Checkpoint auto-approved (auto mode active)

## Operator-Pending Items

| Item | Reason | How to Resolve |
|------|--------|---------------|
| `helm lint`/`helm template` for all values files | helm absent in sandbox | `helm template infra/helm/clubcore -f infra/observability/kube-prometheus-stack-values.yaml` on a machine with helm |
| Live backend scrape verification | No k3d cluster in sandbox | `kubectl -n default port-forward svc/clubcore-backend 8000:8000 && curl localhost:8000/metrics` |
| Grafana dashboard import + live data | No k3d cluster | Install kube-prometheus-stack → enable `observability.serviceMonitor.enabled=true` → import dashboards via ConfigMap |
| Loki log-query | No k3d cluster | `{namespace="default"}` in Grafana Explore after Alloy DaemonSet ships logs |
| Telegram alert delivery | Real bot token required (sealed secret) | Create sealed secret `alertmanager-telegram-bot-token` with real token; update chat_id in alertmanager-rules.yaml; apply and trigger test alert |
| Redis exporter for Redis dashboard | Requires `oliver006/redis_exporter` deploy | Add redis_exporter Deployment alongside Redis StatefulSet |

## Deviations from Plan

None — plan executed exactly as written. The `uv add` succeeded (network up), so the dep is in pyproject.toml AND uv.lock (not just manually appended). All three behavior tests passed at authoring time.

## Threat Surface Scan

No new network endpoints or auth paths introduced beyond what the plan's `<threat_model>` specified:
- `/metrics` is intra-cluster only (NetworkPolicy-gated; `include_in_schema=False`)
- Alertmanager Telegram token via file ref — no plaintext committed (T-120-OBS2 verified by grep gate)
- Grafana admin credentials via `existingSecret` (no plaintext in values — T-120-OBS4)

## Self-Check: PASSED

All 14 created/modified files exist on disk. All 3 task commits verified in git log:
- `3c6b18ef` feat(120-02): OBS-03 FastAPI /metrics instrumentation + ServiceMonitor + monitoring-ns NetworkPolicy
- `13cedcad` feat(120-02): OBS-01/02 kube-prometheus-stack + Loki + Alloy values files
- `cc26936a` feat(120-02): OBS-04/05 Grafana dashboards + Alertmanager rules + Telegram receiver

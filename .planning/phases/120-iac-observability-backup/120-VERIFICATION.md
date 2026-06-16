---
phase: 120-iac-observability-backup
verified: 2026-06-16T14:30:00Z
status: human_needed
score: 12/12
overrides_applied: 0
human_verification:
  - test: "terraform validate both modules"
    expected: "'Success! The configuration is valid.' for host and cluster modules"
    why_human: "terraform binary not installed in sandbox; cannot fabricate output per D-V40-LOCAL-VALIDATE"
  - test: "make tf-validate exits 0"
    expected: "Both terraform validate commands succeed (exit 0)"
    why_human: "terraform absent; make -n dry-run confirmed commands print correctly, but execution requires terraform"
  - test: "make tf-plan against k3d"
    expected: "Terraform plan shows monitoring namespace + 3 helm_release resources"
    why_human: "requires terraform + reachable k3d cluster"
  - test: "Backend /metrics returns Prometheus metrics"
    expected: "HTTP 200 with content-type text/plain and metric lines (http_request_duration_seconds etc)"
    why_human: "requires live k3d cluster; dep installed (uv add succeeded) but live scrape verification needs running pod"
  - test: "/metrics is NOT in OpenAPI schema"
    expected: "curl localhost:8000/openapi.json | jq '.paths[\"/metrics\"]' returns null"
    why_human: "requires running backend pod; static grep confirms include_in_schema=False is present and placement is correct"
  - test: "ServiceMonitor target shows UP in Grafana"
    expected: "Prometheus Status → Targets shows backend ServiceMonitor target as UP"
    why_human: "requires kube-prometheus-stack installed + ServiceMonitor CRD present + k3d cluster"
  - test: "Grafana dashboards load with live data"
    expected: "FastAPI, node-exporter, CNPG Postgres, Redis dashboards show live data points"
    why_human: "requires full observability stack running in k3d"
  - test: "Loki receives logs from all pods"
    expected: "{namespace=\"default\"} query in Grafana Explore returns live log lines"
    why_human: "requires Alloy DaemonSet running + Loki deployed in k3d"
  - test: "BAK-03 restore round-trip in k3d (HEADLINE OPERATOR-PENDING CHECK)"
    expected: |
      1. Enable backup.enabled=true, helm upgrade → barmanObjectStore active
      2. Wait for CNPG WAL objects in SeaweedFS s3://clubcore/postgres
      3. Run infra/runbooks/restore.md Steps 1-4: take base backup → restore to scratch namespace → row-count check
      4. Live count and scratch count must match (or satisfy tolerance)
      5. Scratch cluster deleted; live cluster untouched
      This is the phase headline deliverable for BAK-03.
    why_human: "requires k3d + CNPG operator + SeaweedFS running; no live cluster in sandbox; the runbook and restore-verify.sh are authored and bash-n clean, but the actual execution is gated on operator"
  - test: "BAK-04 restore-verify CronJob runs + fails closed on mismatch"
    expected: |
      kubectl create job --from=cronjob/<release>-restore-verify verify-now
      Job restores to scratch, row-count-checks, tears down scratch namespace.
      On injected mismatch: Job exits non-zero → KubeBackupJobFailed + RestoreVerifyJobFailed alert fires in Alertmanager.
    why_human: "requires k3d + RBAC ServiceAccount configured (operator-install dep noted in runbook)"
  - test: "Alertmanager Telegram delivery"
    expected: "Test alert delivered to Telegram chat after sealing real bot_token and updating chat_id"
    why_human: "requires real Telegram bot token in sealed secret + correct chat_id; placeholder -1001234567890 documented as operator-pending"
  - test: "Redis RDB backup and SeaweedFS mirror CronJob execution"
    expected: "Jobs complete successfully; S3 object appears in s3://clubcore/redis; /mnt/backup/current/ populated on mirror PVC"
    why_human: "requires k3d + SeaweedFS + backup image built and pushed to local k3d registry"
  - test: "CNPG PostgresNoBackupIn25h alert metric name"
    expected: "cnpg_collector_last_available_backup_timestamp is the correct metric name on CNPG 1.27"
    why_human: "metric name requires confirmation against installed CNPG collector version; WR-06 fix added absent() guard but metric name is unverified without running collector"
---

# Phase 120: IaC, Observability + Backup — Verification Report

**Phase Goal:** Infrastructure declared as Terraform code that passes validate and plan; metrics/logs/dashboards live for all pods; CNPG WAL backup active; verified restore round-trip completed in k3d and documented in a runbook.
**Verified:** 2026-06-16T14:30:00Z
**Status:** human_needed
**Re-verification:** No — initial verification

## Goal Achievement

All static (authorable) must-haves are VERIFIED. All runtime must-haves (terraform validate/plan, live scrape, live backup, the BAK-03 restore round-trip) are operator-pending per D-V40-LOCAL-VALIDATE — terraform, helm, and k3d are absent in the verification sandbox. No fabricated evidence.

### Observable Truths

| # | Truth | Status | Evidence |
|---|-------|--------|----------|
| 1 | `make tf-validate` runs both terraform validate commands (operator-pending exit-0; structure authored) | VERIFIED | `make -n tf-validate` dry-run prints `terraform -chdir=infra/terraform/host validate` then `terraform -chdir=infra/terraform/cluster validate`; both module directories exist with valid HCL structure |
| 2 | `make tf-plan` runs cluster plan (operator-pending — needs k3d) | VERIFIED | Target present in Makefile: `terraform -chdir=infra/terraform/cluster plan`; no phase-121 targets present |
| 3 | host module provisions k3s via null_resource + remote-exec with backend local and placeholder-only tfvars | VERIFIED | `grep null_resource` + `grep remote-exec` + `grep 'backend "local"'` all pass; tfvars.example has 192.0.2.10 placeholder, no private key body |
| 4 | cluster module manages monitoring ns + helm_releases using hashicorp/helm v3.2.0 list-of-objects set syntax | VERIFIED | `grep '"3.2.0"'` + `grep -Eq 'set\s*=\s*\['` pass; `grep -E 'set\s*\{'` finds no map syntax |
| 5 | Backend /metrics returns Prometheus metrics from prometheus-fastapi-instrumentator>=7.1,<8 inside create_app() | VERIFIED (static) | `pyproject.toml` has `prometheus-fastapi-instrumentator>=7.1,<8`; `main.py:748` has `Instrumentator().instrument(app).expose(app, endpoint="/metrics", include_in_schema=False)` placed after `include_router(api):740` and before `_customize_openapi:766` |
| 6 | /metrics has include_in_schema=False bypassing global OpenAPI security | VERIFIED (static) | `include_in_schema=False` present on line 748; `_customize_openapi` closure starts at line 766; placement is correct |
| 7 | ServiceMonitor CR targets backend Service; monitoring-ns NetworkPolicy ingress present | VERIFIED | `servicemonitor-backend.yaml` has `kind: ServiceMonitor`, `path: /metrics`, port `http`, gated on `observability.serviceMonitor.enabled`; `networkpolicy-allow.yaml` has `kubernetes.io/metadata.name: monitoring` ingress on :8000 |
| 8 | kube-prometheus-stack single-node tuned 7d; Loki SingleBinary 30d; Alloy daemonset ships logs to Loki | VERIFIED | All 3 YAML files parse clean; kube-prometheus: `retention: 7d`, `serviceMonitorSelectorNilUsesHelmValues: false`, `existingSecret: grafana-admin-credentials`; loki: `SingleBinary`, `720h`; alloy: `daemonset`, `loki.write` pipeline |
| 9 | 4 Grafana dashboards (FastAPI, node-exporter, CNPG, Redis) + 5-7 alert rules + Telegram receiver (no plaintext token) | VERIFIED | 4 JSON files parse clean (7/4/6/4 panels); alertmanager-rules.yaml YAML-valid, 7 alert rules (>=5), `kind: PrometheusRule`, `bot_token_file` path (no inline bot token); includes KubeBackupJobFailed (WR-05) and PostgresNoBackupIn25h with absent() guard (WR-06) |
| 10 | CNPG barmanObjectStore points at SeaweedFS S3, reusing EXISTING S3 secret; ScheduledBackup CR present | VERIFIED | `postgres-cluster.yaml` has real `barmanObjectStore` block (placeholder comment removed); `S3_ACCESS_KEY_ID` secretKeyRef to `clubcore-app-secret`; `scheduledbackup-postgres.yaml` has `kind: ScheduledBackup`, `method: barmanObjectStore`, gated on `backup.enabled` |
| 11 | Redis RDB + SeaweedFS mirror CronJobs with SEC-03 hardening; restore-verify CronJob with scratch-only invariant | VERIFIED | Both backup CronJobs use `clubcore.backupImage` (pre-baked, no runtime apk add); `hardenedSecurityContext` + `TZ` + `/tmp` emptyDir present; `restore-verify-cronjob.yaml` has scratch-only comment and `hardenedSecurityContext`; `bitnami/kubectl:1.31.5` pinned (not :latest) |
| 12 | restore.md runbook + restore-verify.sh (bash -n clean, scratch-only, row-count-checks, fail-closed) | VERIFIED | `bash -n restore-verify.sh` PASS; `set -euo pipefail` present; `count(*)` from `users` table on both live and scratch; case guards reject empty/non-numeric; exit non-zero on mismatch; BAK-03 tag in runbook; OPERATOR-PENDING callout present |

**Score:** 12/12 truths verified (all static; runtime checks operator-pending)

### Required Artifacts

| Artifact | Expected | Status | Details |
|----------|----------|--------|---------|
| `infra/terraform/host/main.tf` | k3s null_resource + remote-exec, backend local | VERIFIED | null_resource, remote-exec, backend "local" confirmed |
| `infra/terraform/cluster/main.tf` | monitoring ns + helm_releases, helm v3.2.0 list-set | VERIFIED | hashicorp/helm 3.2.0, kubernetes_namespace, list-of-objects set syntax |
| `infra/terraform/host/terraform.tfvars.example` | placeholders only, no secrets | VERIFIED | 192.0.2.10 placeholder; no private key body |
| `infra/terraform/cluster/terraform.tfvars.example` | placeholders only | VERIFIED | exists |
| `Makefile` | tf-validate + tf-plan only (no phase-121 targets) | VERIFIED | exactly 2 relevant targets; no build/deploy/smoke |
| `apps/backend/pyproject.toml` | prometheus-fastapi-instrumentator>=7.1,<8 | VERIFIED | dependency present |
| `apps/backend/app/main.py` | Instrumentator inside create_app(), include_in_schema=False | VERIFIED | line 748, correct placement |
| `infra/helm/clubcore/templates/servicemonitor-backend.yaml` | ServiceMonitor CR gated on enabled | VERIFIED | kind: ServiceMonitor, path /metrics, gated |
| `infra/observability/kube-prometheus-stack-values.yaml` | 7d retention, single-node, existingSecret | VERIFIED | YAML-valid; all required keys present |
| `infra/observability/loki-values.yaml` | SingleBinary, 30d retention | VERIFIED | YAML-valid; deploymentMode: SingleBinary, 720h |
| `infra/observability/alloy-values.yaml` | daemonset, loki.write pipeline | VERIFIED | YAML-valid; daemonset, loki.write confirmed |
| `infra/observability/grafana-dashboards/fastapi.json` | valid JSON, prometheus-fastapi metrics | VERIFIED | 7 panels, JSON-valid |
| `infra/observability/grafana-dashboards/cnpg-postgres.json` | valid JSON | VERIFIED | 4 panels, JSON-valid |
| `infra/observability/grafana-dashboards/redis.json` | valid JSON | VERIFIED | 6 panels, JSON-valid |
| `infra/observability/grafana-dashboards/node-exporter.json` | valid JSON | VERIFIED | 4 panels, JSON-valid |
| `infra/observability/alertmanager-rules.yaml` | PrometheusRule, >=5 alerts, no inline token | VERIFIED | 7 alerts, kind: PrometheusRule, bot_token_file (no inline token) |
| `infra/helm/clubcore/templates/postgres-cluster.yaml` | barmanObjectStore + WAL, reusing S3 secret | VERIFIED | barmanObjectStore present, S3_ACCESS_KEY_ID secretKeyRef, placeholder comment replaced |
| `infra/helm/clubcore/templates/scheduledbackup-postgres.yaml` | ScheduledBackup CR, daily, gated | VERIFIED | kind: ScheduledBackup, method: barmanObjectStore, backup.enabled gate |
| `infra/helm/clubcore/templates/backup-redis-cronjob.yaml` | CronJob, backupImage, hardenedSecurityContext, S3 creds | VERIFIED | uses clubcore.backupImage, hardenedSecurityContext, S3_ACCESS_KEY_ID secretKeyRef |
| `infra/helm/clubcore/templates/backup-seaweedfs-cronjob.yaml` | CronJob, backupImage, incremental sync | VERIFIED | uses clubcore.backupImage, `--delete` sync, `--exclude "postgres/*"` (WR-03 fix) |
| `infra/helm/clubcore/templates/restore-verify-cronjob.yaml` | CronJob, scratch-only, fail-closed, bitnami/kubectl pinned | VERIFIED | scratch-only comment, hardenedSecurityContext, bitnami/kubectl:1.31.5 (not :latest) |
| `infra/scripts/restore-verify.sh` | bash -n clean, scratch, count(*), fail-closed | VERIFIED | bash -n PASS, set -euo pipefail, SELECT count(*) FROM users, case guards, err on mismatch |
| `infra/runbooks/restore.md` | BAK-03 tag, OPERATOR-PENDING callout, round-trip steps | VERIFIED | BAK-03 present, OPERATOR-PENDING present, 9-checkbox Hard Gate |
| `infra/docker/backup.Dockerfile` | pre-baked redis-cli + aws-cli, non-root USER 1000 | VERIFIED | aws-cli, redis, USER 1000, adduser -D -u 1000 backup |

### Key Link Verification

| From | To | Via | Status | Details |
|------|-----|-----|--------|---------|
| Makefile | infra/terraform/host + cluster | `terraform -chdir=<module> validate/plan` | WIRED | make -n dry-run confirmed |
| infra/terraform/cluster/main.tf | infra/observability/*-values.yaml | `file("${path.module}/../../observability/*-values.yaml")` | WIRED | 3 file() references confirmed (lines 78, 105, 130) |
| apps/backend/app/main.py | /metrics endpoint | `Instrumentator().instrument(app).expose(app, endpoint="/metrics", include_in_schema=False)` | WIRED | Line 748, after include_router:740, before _customize_openapi:766 |
| infra/helm/clubcore/templates/servicemonitor-backend.yaml | backend Service :8000 /metrics | spec.selector.matchLabels + endpoints path /metrics | WIRED | matchLabels uses clubcore.selectorLabels + component backend; port: http, path: /metrics |
| infra/observability/alloy-values.yaml | Loki write endpoint | `loki.write "default"` with monitoring-ns endpoint | WIRED | loki.write confirmed in configMap.content |
| infra/helm/clubcore/templates/postgres-cluster.yaml | SeaweedFS S3 + existing app-secret | barmanObjectStore.s3Credentials.secretKeyRef | WIRED | S3_ACCESS_KEY_ID / S3_SECRET_ACCESS_KEY from clubcore-app-secret |
| restore-verify-cronjob.yaml | infra/scripts/restore-verify.sh + OBS-05 alert | CronJob inline logic exits non-zero → KubeBackupJobFailed + RestoreVerifyJobFailed | WIRED | alert-linkage annotation present; exit non-zero path confirmed |

### Data-Flow Trace (Level 4)

Not applicable — no React/Vue/frontend components in this phase. All artifacts are Terraform HCL, Helm templates, YAML values files, bash scripts, and a Python backend instrumentation hook. Data-flow traces for static config/infra artifacts are not meaningful at this level.

### Behavioral Spot-Checks

| Behavior | Command | Result | Status |
|----------|---------|--------|--------|
| restore-verify.sh shell syntax | `bash -n infra/scripts/restore-verify.sh` | Clean (no errors) | PASS |
| Makefile tf-validate dry-run | `make -n tf-validate` | Prints both terraform validate commands | PASS |
| Dashboard JSON validity | `python3 -c "json.load(...)"` x4 | All 4 JSON files parse clean | PASS |
| YAML files validity | `python3 -c "yaml.safe_load(...)"` x5 | kube-prometheus-stack, loki, alloy, alertmanager-rules, loki-values all YAML-valid | PASS |
| terraform validate (host module) | `terraform -chdir=infra/terraform/host validate` | SKIP — terraform absent | OPERATOR-PENDING |
| terraform validate (cluster module) | `terraform -chdir=infra/terraform/cluster validate` | SKIP — terraform absent | OPERATOR-PENDING |
| BAK-03 restore round-trip | `bash infra/scripts/restore-verify.sh` | SKIP — k3d absent | OPERATOR-PENDING |

### Probe Execution

No `scripts/*/tests/probe-*.sh` files exist for this phase. The operator verification commands are in the PLAN task-4 checkpoint blocks for each plan.

### Requirements Coverage

| Requirement | Source Plan | Description | Status | Evidence |
|-------------|------------|-------------|--------|----------|
| IAC-01 | 120-01 | Terraform host module (k3s null_resource + remote-exec, backend local) | SATISFIED | `infra/terraform/host/main.tf` has null_resource, remote-exec, backend "local"; tfvars.example placeholder-only |
| IAC-02 | 120-01 | Terraform cluster module (namespaces + helm_release v3.2 list-syntax) | SATISFIED | `infra/terraform/cluster/main.tf` has hashicorp/helm 3.2.0, kubernetes_namespace, list-of-objects set syntax |
| IAC-03 | 120-01 | `make tf-validate` + `make tf-plan` targets | SATISFIED | Makefile has tf-validate + tf-plan; make -n dry-run confirmed |
| OBS-01 | 120-02 | kube-prometheus-stack single-node 7d retention | SATISFIED | kube-prometheus-stack-values.yaml: YAML-valid, retention: 7d, existingSecret, serviceMonitorSelectorNilUsesHelmValues: false |
| OBS-02 | 120-02 | Loki monolithic SingleBinary 30d + Alloy daemonset | SATISFIED | loki-values.yaml: SingleBinary, 720h, replication_factor: 1; alloy-values.yaml: daemonset, loki.write |
| OBS-03 | 120-02 | FastAPI /metrics via prometheus-fastapi-instrumentator + ServiceMonitor | SATISFIED (static) | pyproject.toml dep present; main.py line 748 correct placement; ServiceMonitor CR present; NetworkPolicy monitoring-ns ingress present |
| OBS-04 | 120-02 | 4 Grafana dashboards (FastAPI, node-exporter, CNPG, Redis) | SATISFIED | 4 JSON files JSON-valid with panels; README records grafana.com IDs |
| OBS-05 | 120-02 | 5-7 Alertmanager rules + Telegram receiver (no plaintext token) | SATISFIED | 7 rules including KubeBackupJobFailed (WR-05) and PostgresNoBackupIn25h with absent() guard (WR-06); bot_token_file (no inline token) |
| BAK-01 | 120-03 | CNPG barmanObjectStore + ScheduledBackup daily to SeaweedFS | SATISFIED | postgres-cluster.yaml real barmanObjectStore block; scheduledbackup-postgres.yaml kind: ScheduledBackup; backup.enabled gate |
| BAK-02 | 120-03 | Redis RDB weekly + SeaweedFS mirror daily CronJobs, 7d/4w retention | SATISFIED | backup-redis-cronjob.yaml + backup-seaweedfs-cronjob.yaml exist with backupImage, hardenedSecurityContext, retention prune; WR-03 fix adds --exclude "postgres/*" to mirror |
| BAK-03 | 120-03 | Restore runbook + verified round-trip (live run operator-pending) | SATISFIED (static) | restore.md: BAK-03 tag, OPERATOR-PENDING callout, 9-checkbox Hard Gate, numbered steps; live round-trip is the headline operator-pending item |
| BAK-04 | 120-03 | Weekly restore-verify CronJob to scratch + row-count + alert on failure | SATISFIED (static) | restore-verify-cronjob.yaml: scratch-only invariant, hardenedSecurityContext, RestoreVerifyJobFailed + KubeBackupJobFailed linkage; restore-verify.sh: bash -n clean, fail-closed |

### Anti-Patterns Found

| File | Line | Pattern | Severity | Impact |
|------|------|---------|----------|--------|
| `infra/observability/alertmanager-rules.yaml` | 270 | `chat_id: -1001234567890` placeholder | Info | Intentional: documented operator-pending item; delivery requires real bot token in sealed secret; not a code stub — a config placeholder with explicit operator instructions |
| `infra/scripts/restore-verify.sh` | ~146 | `--from-literal=password="${DB_PASSWORD:-clubcore-scratch-verify-pw}"` | Info (IN-03, out-of-scope) | REVIEW.iter2 classified as Info/out-of-scope; scratch cluster is ephemeral + isolated; low blast radius; psql exec uses in-pod CNPG trust/peer auth so password is cosmetic |

No TBD/FIXME/XXX unreferenced debt markers found in any phase-created file.

### Human Verification Required

The operator checklist is ordered by dependency — do them top-down on a machine with terraform >= 1.6, helm >= 3, and a running k3d cluster.

#### 1. terraform validate — host module

**Test:** `cd infra/terraform/host && terraform init && terraform validate`
**Expected:** "Success! The configuration is valid."
**Why human:** terraform binary absent in sandbox; static HCL authored per HashiCorp provider docs

#### 2. terraform validate — cluster module

**Test:** `cd infra/terraform/cluster && terraform init && terraform validate`
**Expected:** "Success! The configuration is valid."; confirm v3.2 list-set syntax raises no deprecation warning
**Why human:** terraform absent; list-of-objects set syntax confirmed correct by grep but init+validate required to catch provider-schema mismatch

#### 3. make tf-validate and make tf-plan

**Test:** `make tf-validate` then `make tf-plan` (k3d must be running)
**Expected:** tf-validate exits 0 (both modules valid); tf-plan shows monitoring namespace + kube-prometheus-stack + loki + alloy helm_releases
**Why human:** requires terraform + k3d

#### 4. Backend /metrics endpoint live verification

**Test:**
```bash
kubectl -n default port-forward svc/clubcore-backend 8000:8000 &
curl -s localhost:8000/metrics | head -5   # expect Prometheus metric lines
curl -s localhost:8000/openapi.json | python3 -c "import json,sys; d=json.load(sys.stdin); print('/metrics' in d['paths'])"  # expect False
```
**Expected:** /metrics returns text/plain Prometheus metrics; /metrics NOT in openapi paths (False)
**Why human:** requires running backend pod; static placement of include_in_schema=False confirmed correct but live behavior needs live pod

#### 5. Grafana dashboards with live data

**Test:** After helm upgrade with `observability.serviceMonitor.enabled=true`: open Grafana, navigate to each of the 4 dashboards
**Expected:** FastAPI, node-exporter, CNPG Postgres, Redis dashboards show panels with real data points (not "No data")
**Why human:** requires full observability stack running; dashboards depend on metric exporters being deployed

#### 6. Loki log query

**Test:** Grafana Explore: `{namespace="default"}` query
**Expected:** Live log lines from pods in the default namespace
**Why human:** requires Alloy DaemonSet running and pushing to Loki

#### 7. Alertmanager Telegram delivery

**Test:**
```bash
# 1. Create sealed secret with real bot token
kubectl create secret generic alertmanager-telegram-bot-token \
  --from-literal=bot_token=<real_token> --dry-run=client -o yaml | kubeseal | kubectl apply -f -
# 2. Update chat_id in alertmanager-rules.yaml with real group ID
# 3. Apply and trigger test alert (e.g., scale down a pod momentarily)
```
**Expected:** Telegram message received in the configured chat
**Why human:** requires real Telegram bot token; chat_id -1001234567890 is placeholder

#### 8. BAK-03: Verified Postgres restore round-trip in k3d [HEADLINE CHECK]

**Test:** Follow `infra/runbooks/restore.md` Steps 1-4 with `backup.enabled=true`:
```bash
helm upgrade clubcore infra/helm/clubcore --set backup.enabled=true --set image.tag=<sha>
# Wait for CNPG to produce WAL objects in SeaweedFS s3://clubcore/postgres
bash infra/scripts/restore-verify.sh  # or trigger the CronJob manually
```
**Expected:** Live row count (users table) captured; backup restored to scratch namespace `clubcore-restore-verify-scratch`; scratch row count equals live count; scratch namespace deleted; exit 0
**Why human:** This is the BAK-03 gate — requires k3d + CNPG operator + SeaweedFS running; restore-verify.sh is bash -n clean and the logic is authored, but the actual k3d execution is the operator-pending deliverable

#### 9. BAK-04: restore-verify CronJob real run

**Test:**
```bash
# Configure BAK-04 RBAC (restore.md BAK-04 RBAC Setup section)
helm upgrade clubcore infra/helm/clubcore --set backup.restoreVerify.enabled=true ...
kubectl create job --from=cronjob/clubcore-restore-verify verify-now -n default
kubectl logs job/verify-now -f
```
**Expected:** Job completes successfully; scratch cluster created + row-count-checked + torn down; live cluster untouched; injected mismatch triggers KubeBackupJobFailed + RestoreVerifyJobFailed alert
**Why human:** requires RBAC ServiceAccount + k3d + full backup stack active

#### 10. CNPG metric name confirmation

**Test:** After CNPG operator is running: `kubectl exec -n monitoring <prometheus-pod> -- curl -s localhost:9090/api/v1/label/__name__/values | jq '.data[]' | grep cnpg`
**Expected:** `cnpg_collector_last_available_backup_timestamp` appears in metric names (or identify the actual name for PostgresNoBackupIn25h alert correction)
**Why human:** WR-06 added `or absent(...)` guard to tolerate missing metric, but the exact metric name must be confirmed against the installed CNPG 1.27 collector to ensure the alert fires correctly when backup is genuinely stale

#### 11. Redis and SeaweedFS backup CronJobs execution

**Test:** Trigger both CronJobs manually; verify S3 object appears under `s3://clubcore/redis`; verify `/mnt/backup/current/` populated on mirror PVC
**Expected:** Both Jobs complete with exit 0; retention prune epoch-based comparison works correctly
**Why human:** requires built and pushed `clubcore/backup` image + k3d + SeaweedFS

### Gaps Summary

No gaps found. All 12 must-haves are verified at the static level (artifacts exist, are substantive, and are correctly wired). All runtime verification items are operator-pending per D-V40-LOCAL-VALIDATE — this was explicitly planned and all three PLAN files include `checkpoint:human-verify` gates documenting the operator-pending boundary. The code review cycle (2 iterations, 4 BLOCKERs + 9 warnings fixed) completed before this verification; all traced fixes were CONFIRMED in 120-REVIEW.md iteration-2.

The BAK-03 verified restore round-trip in k3d is the headline human verification item — it is the phase's differentiating deliverable and must be executed by the operator before the phase can be considered fully complete.

---

_Verified: 2026-06-16T14:30:00Z_
_Verifier: Claude (gsd-verifier)_

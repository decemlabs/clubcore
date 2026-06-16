# Phase 120: IaC, Observability + Backup - Pattern Map

**Mapped:** 2026-06-16
**Files analyzed:** 22 (new/modified)
**Analogs found:** 14 / 22 (8 net-new with no codebase analog — Terraform + community observability values)

## Orientation

This is a pure infra/DevOps phase. "Role" maps to infra artifact kind (helm-template, helm-values, bash-script, runbook, terraform-module, python-instrumentation, makefile). "Data flow" maps to the operational concern (backup, scrape/metrics, log-ship, provision, restore). Terraform is net-new to the repo — no analogs exist, do NOT fabricate them; use HashiCorp/CNPG/community-chart docs (planner has context7/WebFetch) per the research flags.

**Tooling reality (D-V40-LOCAL-VALIDATE):** terraform / helm / k3d are NOT installed in the build sandbox. Done-bar = code template-validated + `bash -n` shape-correct + `terraform fmt`-shape-correct. `terraform validate/plan`, `helm template/lint`, live scrape, real backup-to-S3, and the live restore round-trip are operator-pending. No fabricated evidence.

## File Classification

| New/Modified File | Role | Concern (data flow) | Closest Analog | Match Quality |
|-------------------|------|---------------------|----------------|---------------|
| `infra/helm/clubcore/templates/postgres-cluster.yaml` (MODIFY) | helm-template | backup config | self (existing CNPG Cluster CR) | exact (in-place edit) |
| `infra/helm/clubcore/templates/servicemonitor-backend.yaml` (NEW) | helm-template | scrape/metrics | `templates/backend-service.yaml` | role-match |
| `infra/helm/clubcore/templates/backup-redis-cronjob.yaml` (NEW) | helm-template | backup | `templates/migrate-job.yaml` (Job/initContainer shape) | role-match |
| `infra/helm/clubcore/templates/backup-seaweedfs-cronjob.yaml` (NEW) | helm-template | backup | `templates/migrate-job.yaml` | role-match |
| `infra/helm/clubcore/templates/restore-verify-cronjob.yaml` (NEW) | helm-template | restore | `templates/migrate-job.yaml` + `postgres-cluster.yaml` | role-match |
| `infra/helm/clubcore/values.yaml` (MODIFY) | helm-values | all | self (existing values.yaml) | exact |
| `apps/backend/app/main.py` (MODIFY) | python-instrumentation | scrape/metrics | self (FastAPI app factory) | exact (in-place edit) |
| `apps/backend/pyproject.toml` (MODIFY) | manifest | dependency-add | self (`[project].dependencies`) | exact |
| `infra/terraform/host/main.tf` (NEW) | terraform-module | provision (k3s install) | NONE | net-new |
| `infra/terraform/host/variables.tf` (NEW) | terraform-module | provision | NONE | net-new |
| `infra/terraform/host/terraform.tfvars.example` (NEW) | terraform-config | provision | NONE | net-new |
| `infra/terraform/cluster/main.tf` (NEW) | terraform-module | provision (helm_release) | NONE | net-new |
| `infra/terraform/cluster/variables.tf` (NEW) | terraform-module | provision | NONE | net-new |
| `infra/terraform/cluster/terraform.tfvars.example` (NEW) | terraform-config | provision | NONE | net-new |
| `infra/observability/kube-prometheus-stack-values.yaml` (NEW) | helm-values | scrape/metrics | NONE (community chart) | net-new (doc-sourced) |
| `infra/observability/loki-values.yaml` (NEW) | helm-values | log-ship | NONE (community chart) | net-new (doc-sourced) |
| `infra/observability/alloy-values.yaml` (NEW) | helm-values | log-ship | NONE (community chart) | net-new (doc-sourced) |
| `infra/observability/grafana-dashboards/*.json` (NEW) | dashboard-config | scrape/metrics | NONE | net-new (grafana.com IDs) |
| `infra/observability/alertmanager-rules.yaml` (NEW) | helm-values | alerting | NONE (PrometheusRule CRD) | net-new (doc-sourced) |
| `infra/runbooks/restore.md` (NEW) | runbook | restore | `infra/runbooks/sealed-secrets-key-backup.md` | exact |
| `infra/scripts/restore-verify.sh` (NEW, BAK-04 evidence) | bash-script | restore | `infra/scripts/k3d-up.sh` | exact |
| `Makefile` (NEW, root — only `tf-validate` + `tf-plan`) | makefile | provision | NONE (no Makefile exists yet) | net-new |

## Pattern Assignments

### `infra/helm/clubcore/templates/postgres-cluster.yaml` (MODIFY — BAK-01)

**Analog:** self. The Cluster CR already exists; the `spec.backup.barmanObjectStore` block was deliberately omitted (lines 83-86 are the literal placeholder comment marking the insertion point).

**Insertion point** (existing comment, postgres-cluster.yaml:83-86):
```yaml
  # NOTE: spec.backup (barmanObjectStore) is intentionally absent.
  # BAK-01 (Phase 120) adds CNPG WAL archiving to SeaweedFS S3.
  # Research flag: verify CNPG v1.27 barmanObjectStore field names ...
```

**Existing value-binding convention to mirror** (postgres-cluster.yaml:37, 47-50): every field is `{{ .Values.postgres.<x> | default <y> }}`; secret refs use `secret.name: {{ .Values.postgres.appSecretName | default "clubcore-postgres-app" }}`. New backup block follows the same `.Values.postgres.backup.*` binding discipline and adds a `secretkeyref` to the EXISTING SeaweedFS S3 secret (do not invent a new secret).

**RESEARCH FLAG (do NOT guess):** verify CNPG v1.27 `Cluster.spec.backup.barmanObjectStore` field shape against CNPG docs — `endpointURL`, `destinationPath`, `s3Credentials.accessKeyId.{name,key}` + `secretAccessKey.{name,key}`, `wal.compression`, `data.compression`, plus a sibling `ScheduledBackup` CR for the daily base backup. SeaweedFS S3 endpoint is in-cluster `<release>-seaweedfs-s3` service.

---

### `infra/helm/clubcore/templates/servicemonitor-backend.yaml` (NEW — OBS-03 chart half)

**Analog:** `infra/helm/clubcore/templates/backend-service.yaml`

**Header-comment + labels convention** (backend-service.yaml:1-19):
```yaml
{{/*
servicemonitor-backend.yaml — ServiceMonitor for the backend /metrics endpoint
*/}}
apiVersion: monitoring.coreos.com/v1
kind: ServiceMonitor
metadata:
  name: {{ include "clubcore.fullname" . }}-backend
  labels:
    {{- include "clubcore.labels" . | nindent 4 }}
    app.kubernetes.io/component: backend
```

**Selector pattern** (mirror backend-service.yaml:22-24 selectorLabels) — the ServiceMonitor `spec.selector.matchLabels` targets the existing backend Service (`clubcore-backend:8000`, port name `http`, endpoint path `/metrics`). The `monitoring.coreos.com/v1` CRD requires kube-prometheus-stack installed (OBS-01) — gate the template behind `{{- if .Values.observability.serviceMonitor.enabled }}`.

---

### `infra/helm/clubcore/templates/backup-redis-cronjob.yaml` + `backup-seaweedfs-cronjob.yaml` (NEW — BAK-02)

**Analog:** `infra/helm/clubcore/templates/migrate-job.yaml` (the closest batch-workload template — initContainer + env-from-secret + resource limits + securityContext discipline).

**Reuse the SeaweedFS S3 creds the way the app does** — backup containers read S3 creds from the SAME secret keys as `seaweedfs-s3-secret.yaml` / `app-secret.yaml` (`secrets.s3AccessKeyId` / `secrets.s3SecretAccessKey`). Do NOT mint new credentials.

**Schedules + retention** (Claude's discretion within D decisions): Redis RDB weekly → SeaweedFS, SeaweedFS mirror daily → second PVC, retention 7-daily / 4-weekly. Gate behind `{{- if .Values.backup.enabled }}`.

**securityContext invariant (SEC-03 / P-pattern):** every new pod template carries `runAsNonRoot`, `readOnlyRootFilesystem`, `allowPrivilegeEscalation: false`, drop ALL capabilities, `TZ=UTC` (P9). Copy the block verbatim from `migrate-job.yaml`.

---

### `infra/helm/clubcore/templates/restore-verify-cronjob.yaml` (NEW — BAK-04, the differentiator)

**Analog:** `migrate-job.yaml` (CronJob/Job shell) + `postgres-cluster.yaml` (CNPG connection + secret refs).

**Behavior (D-V40-BAK04-INCLUDED — actually restores, not passive):** weekly CronJob restores the latest CNPG backup into a scratch namespace/cluster, runs a row-count check, and alerts on failure (emit a metric the Alertmanager rule in OBS-05 watches, or exit non-zero so the Job's failure surfaces). Wraps `infra/scripts/restore-verify.sh`.

---

### `apps/backend/app/main.py` (MODIFY — OBS-03 instrumentation half)

**Analog:** self (the FastAPI app factory). The instrumentation MUST be added inside `create_app()` (apps/backend/app/main.py:412), AFTER `app.include_router(api)` (line 739) and BEFORE the OpenAPI post-processor block, OR right after `register_middleware(app)` (line 486) — planner picks; keep it inside the factory body, NEVER a module-level `app = ...` (the top-doc lines 4-7 forbid that).

**Import convention to mirror** (main.py:51-57): third-party imports grouped, alpha-ordered:
```python
from prometheus_fastapi_instrumentator import Instrumentator
```

**Wiring shape** (add inside `create_app()`):
```python
    # OBS-03 — expose Prometheus /metrics (scraped by the backend ServiceMonitor).
    Instrumentator().instrument(app).expose(app, endpoint="/metrics", include_in_schema=False)
```

**Caveat — keep `/metrics` out of auth + out of OpenAPI:** the OpenAPI post-processor at main.py:757 applies a GLOBAL `security=[{cookieAuth, csrfHeader}]` default. Expose `/metrics` with `include_in_schema=False` so it never enters `schema["paths"]` and is not force-secured; the scrape is in-cluster only (NetworkPolicy from SEC-04 must allow Prometheus → backend:8000 — note as an integration point, may need a networkpolicy-allow.yaml egress/ingress rule).

---

### `apps/backend/pyproject.toml` (MODIFY — OBS-03 dependency)

**Analog:** self, `[project].dependencies` (pyproject.toml:6-26). Append, keeping the existing `name>=X,<Y` pinning style:
```toml
    "prometheus-fastapi-instrumentator>=7.1,<8",
```
v8 is explicitly deferred (ADVOPS-01 — needs FastAPI ≥0.133 + Starlette v1). Pin `<8`.

---

### `infra/terraform/host/` + `infra/terraform/cluster/` (NEW — IAC-01 / IAC-02) — NET-NEW, NO ANALOG

There is NO existing Terraform in the repo. Do NOT fabricate an analog. Source field shapes from HashiCorp provider docs (planner has context7).

**Locked conventions (D-V40-TF-PROVIDER — binding):**
- `hashicorp/helm` provider **v3.2.0** — BREAKING from v2.x: every `helm_release` `set` block MUST use **list-of-objects** syntax, NOT map:
```hcl
  set = [
    { name = "key.path", value = "val" },
  ]
```
- `backend "local"` state in both modules (no remote backend — no git remote per project model).
- `host/` = `null_resource` + `provisioner "remote-exec"` for k3s install on bare-metal; `validate` is the done-bar, **apply operator-pending** (SSH creds).
- `cluster/` = namespaces (`monitoring` etc.) + `helm_release` for the observability stack; `validate` static here, `plan` against k3d is operator-pending.
- Each module ships a `terraform.tfvars.example` (Claude's discretion on contents) and `variables.tf`.

---

### `infra/observability/*-values.yaml` (NEW — OBS-01/02/04/05) — NET-NEW, doc-sourced

Community charts (kube-prometheus-stack, Loki, Alloy, Grafana) are **operator-installed**, NOT vendored into the umbrella chart. Author values files only.

**RESEARCH FLAG (do NOT guess — STATE.md Phase-120 flag):** Loki community chart v17.x + Grafana Alloy sub-chart values schema changed from v6.x — review the migration guide before writing `loki-values.yaml` / `alloy-values.yaml`.

**Discretion (D):** kube-prometheus-stack single-node resource-tuned + 7d retention; Loki monolithic + 30d retention; dashboards via curated grafana.com IDs (FastAPI, node-exporter, CNPG Postgres, Redis); 5–7 Alertmanager rules + Telegram receiver (delivery operator-pending — real bot token in a sealed secret).

---

### `infra/runbooks/restore.md` (NEW — BAK-03)

**Analog:** `infra/runbooks/sealed-secrets-key-backup.md` — follow its structure exactly.

**Structure to copy** (sealed-secrets-key-backup.md:1-37):
```markdown
# <Title> Runbook
**Requirement:** BAK-03
**Risk level:** ...
---
## Why This Matters
> OPERATOR-PENDING: <what cannot be done in the sandbox>
---
## Hard Gate — Acceptance Criteria
- [ ] ...
---
## Step 1 — ...
```@bash fenced command blocks with `# Expected:` annotations (lines 43-55). Include the verified round-trip (restore + row-count check in k3d) as the gate; the ACTUAL k3d run is operator-pending.

---

### `infra/scripts/restore-verify.sh` (NEW — BAK-04 evidence script)

**Analog:** `infra/scripts/k3d-up.sh`

**Header + safety + helper convention to copy verbatim** (k3d-up.sh:1-56):
```bash
#!/usr/bin/env bash
# restore-verify.sh — <one-line purpose>
#
# Responsibilities: ...
# Prerequisites: ...
# Usage: bash infra/scripts/restore-verify.sh
# Composable: intended to be called from Phase-121 `make` ...

set -euo pipefail

CLUSTER_NAME="clubcore"
REPO_ROOT="$(git rev-parse --show-toplevel)"

log() { echo "[restore-verify] $*"; }
err() { echo "[restore-verify] ERROR: $*" >&2; exit 1; }

check_prereq() { command -v "$1" >/dev/null 2>&1 || err "'$1' not installed"; }
```
Numbered step logging (`[1/N]`), idempotent guards (`if ... already ... — skipping`), and a closing "Next step:" echo block. Done-bar: `bash -n` clean (no live k3d here).

---

### `Makefile` (NEW, root — IAC-03, ONLY `tf-validate` + `tf-plan`)

**Analog:** NONE (no Makefile exists yet). Phase 121 (OPS-01) builds the FULL Makefile with all targets. Phase 120 adds ONLY these two targets as IAC-03's deliverable. Author them so Phase 121 composes the rest (don't pre-build the full one).

```makefile
.PHONY: tf-validate tf-plan
tf-validate: ## Validate both Terraform modules (static; no cluster needed)
	terraform -chdir=infra/terraform/host validate
	terraform -chdir=infra/terraform/cluster validate
tf-plan: ## Plan the cluster module against k3d (operator-pending — needs reachable k3d)
	terraform -chdir=infra/terraform/cluster plan
```
(Exact target bodies are the planner's to refine; the two target NAMES are the IAC-03 contract.)

## Shared Patterns

### Helm template header + label discipline
**Source:** every file in `infra/helm/clubcore/templates/` (e.g. `backend-service.yaml:1-19`, `postgres-cluster.yaml:1-29`)
**Apply to:** all new chart templates (servicemonitor, 3× backup/restore cronjobs)
- Leading `{{/* ... */}}` doc-comment naming the file + requirement tag + DNS/notes.
- `metadata.name: {{ include "clubcore.fullname" . }}-<component>`
- `labels: {{- include "clubcore.labels" . | nindent 4 }}` + `app.kubernetes.io/component: <x>`
- Selectors via `{{- include "clubcore.selectorLabels" . | nindent N }}`
- Every tunable bound as `{{ .Values.<path> | default <y> }}`; new subtrees gated behind `{{- if .Values.<feature>.enabled }}`.

### Pod securityContext + TZ invariant (SEC-03 / P9)
**Source:** `infra/helm/clubcore/templates/migrate-job.yaml`
**Apply to:** all new pod-spawning templates (backup + restore-verify CronJobs)
`runAsNonRoot: true`, `readOnlyRootFilesystem: true`, `allowPrivilegeEscalation: false`, `capabilities.drop: [ALL]`, `env: TZ=UTC`. Copy verbatim — these are invariants, not tuning.

### SeaweedFS S3 credential reuse (BAK-01 / BAK-02)
**Source:** `infra/helm/clubcore/templates/seaweedfs-s3-secret.yaml:34, 56-57` + `app-secret.yaml`
**Apply to:** CNPG barmanObjectStore + Redis/SeaweedFS backup CronJobs
Backup creds = the EXISTING `secrets.s3AccessKeyId` / `secrets.s3SecretAccessKey` (already sealed in Phase 119). Reference the existing secret via `secretKeyRef`; never create a parallel credential.

### Bash script conventions
**Source:** `infra/scripts/k3d-up.sh:1-56, 121-130`
**Apply to:** `restore-verify.sh`
`set -euo pipefail`, `REPO_ROOT="$(git rev-parse --show-toplevel)"`, `log()`/`err()`/`check_prereq()` helpers, numbered `[n/N]` step logging, idempotent skip-guards, closing "Next step:" echo.

### Runbook conventions
**Source:** `infra/runbooks/sealed-secrets-key-backup.md:1-60`
**Apply to:** `restore.md`
Requirement tag + risk level header, "Why This Matters", a `> OPERATOR-PENDING:` callout, a "Hard Gate — Acceptance Criteria" checkbox list, numbered Steps with `# Expected:`-annotated bash blocks.

### Operator-pending honesty (D-V40-LOCAL-VALIDATE)
**Apply to:** ALL plans
terraform/helm/k3d absent in sandbox → validate/plan/template/lint/scrape/restore are operator-pending. Code is template-validated + `bash -n`/`terraform fmt`-shape-correct only. No fabricated evidence (D-72-06 precedent). Host `apply` + live alert delivery + real backup-to-S3 are always operator-pending.

## No Analog Found

Planner should use RESEARCH.md / context7 docs, not a codebase analog, for these:

| File | Role | Reason |
|------|------|--------|
| `infra/terraform/host/*`, `infra/terraform/cluster/*` | terraform-module | No Terraform exists anywhere in the repo — net-new; use HashiCorp helm/null provider docs + D-V40-TF-PROVIDER v3.2 list-syntax |
| `infra/observability/kube-prometheus-stack-values.yaml` | helm-values | Operator-installed community chart; values authored from chart docs |
| `infra/observability/loki-values.yaml` + `alloy-values.yaml` | helm-values | Community chart; **RESEARCH FLAG** Loki v17.x/Alloy schema changed from v6.x — read migration guide |
| `infra/observability/grafana-dashboards/*.json` | dashboard-config | Sourced from curated grafana.com dashboard IDs, not hand-built |
| `infra/observability/alertmanager-rules.yaml` | helm-values | PrometheusRule CRD; 5–7 rules + Telegram receiver authored from kube-prometheus-stack docs |
| `Makefile` (root) | makefile | No Makefile exists yet; Phase 120 adds only `tf-validate`/`tf-plan`, Phase 121 builds the rest |

## Metadata

**Analog search scope:** `infra/helm/clubcore/templates/`, `infra/scripts/`, `infra/runbooks/`, `apps/backend/app/main.py`, `apps/backend/pyproject.toml`, repo root (Makefile), `infra/` (Terraform — none found)
**Files scanned:** ~12 read in full/targeted
**Pattern extraction date:** 2026-06-16

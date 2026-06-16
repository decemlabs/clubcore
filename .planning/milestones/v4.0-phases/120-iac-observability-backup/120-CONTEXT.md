# Phase 120: IaC, Observability + Backup - Context

**Gathered:** 2026-06-16
**Status:** Ready for planning
**Mode:** Auto-generated (infrastructure phase — discuss skipped per smart-discuss infra detection; locked decisions in STATE.md)

<domain>
## Phase Boundary

Infrastructure is declared as **Terraform** code that passes `validate` and `plan`; metrics/logs/dashboards are live for all pods; CNPG WAL backup is active; and a verified restore round-trip has been completed in k3d and documented in a runbook.

**In scope:** IAC-01..03, OBS-01..05, BAK-01..04 (12 requirements).
**Out of scope:** images/Helm core (118, done); networking/security (119, done); Makefile CI/CD + full smoke (121).

**Done-bar (D-V40-LOCAL-VALIDATE):** Terraform `validate` (+ `plan` for the cluster module against k3d) green; observability charts + dashboards + alert rules authored and `helm lint`/`helm template` clean; CNPG `barmanObjectStore` backup config + backup CronJobs authored; restore runbook + a verified restore round-trip in k3d. **terraform/helm/k3d are NOT installed in the build sandbox (no sudo/network)** → `terraform validate/plan`, `helm template`, live observability scrape, real backup-to-S3, and the live restore round-trip are operator-pending. Host `apply` is always operator-pending (SSH creds). No fabricated evidence.
</domain>

<decisions>
## Implementation Decisions

### Locked milestone decisions (from STATE.md — binding)
- **D-V40-TF-PROVIDER**: use `hashicorp/helm` provider **v3.2.0** — BREAKING from v2.x: all `helm_release` `set` blocks MUST use **list-of-objects** syntax (`set = [{ name = "...", value = "..." }]`), NOT map syntax. local `backend "local"` state (no remote backend — no git remote per project model).
- **D-V40-ONPREM-K3S**: cluster validation on **k3d**; ingress = Traefik v3 (already wired Phase 119).
- **D-V40-BAK04-INCLUDED**: BAK-04 weekly automated restore-verification CronJob IS in scope (justified differentiator — actually restores to scratch + row-count check + alert on failure; not passive backup-only).
- **D-V40-MINIO-RETIRED**: backups target **SeaweedFS S3** (BAK-01 CNPG barmanObjectStore → SeaweedFS endpoint; BAK-02 Redis/SeaweedFS CronJobs).

### Research flags (resolve at plan time — planner has context7/WebFetch; do NOT guess field names)
- **BAK-01 / CNPG `Cluster.spec.backup.barmanObjectStore`**: verify the current CNPG v1 API field shape (endpointURL, destinationPath, s3Credentials secret refs, wal/data compression) against CNPG docs before writing. This block was deliberately KEPT OUT of the Phase-118 CNPG Cluster — Phase 120 adds it.
- **OBS-02 / Loki community chart v17.x + Grafana Alloy**: the Alloy sub-chart values schema changed from v6.x — review the migration guide before writing values files.

### Operator-pending boundaries (honest, per D-V40-LOCAL-VALIDATE)
- IAC-01 host module (`null_resource` + `remote-exec` k3s install): `validate` green is the done-bar; **apply operator-pending** (needs SSH creds to the bare-metal node).
- IAC-02 cluster module: `validate` + `plan` against k3d (plan needs a reachable k3d + helm — operator-pending here; validate is static).
- OBS-05 Alertmanager Telegram delivery: real bot token in a sealed secret → **delivery operator-pending**; rules + receiver config authorable.
- BAK-03/04 restore round-trip + verification CronJob: the CronJob, scripts, and runbook are authorable; the ACTUAL verified restore-in-k3d is operator-pending (no k3d here).

### Claude's Discretion
Terraform module layout (`infra/terraform/host/` + `infra/terraform/cluster/`), tfvars.example contents, kube-prometheus-stack resource tuning (single-node, 7d retention) + Loki monolithic (30d retention) values, dashboard JSON sourcing (curated vs grafana.com dashboard IDs), the 5–7 Alertmanager rules chosen, Redis RDB / SeaweedFS mirror CronJob schedules within the stated retention (7-daily / 4-weekly). OBS-03 instrumentation wiring in `apps/backend/app/main.py`.

</decisions>

<code_context>
## Existing Code Insights

### Reusable Assets
- `infra/helm/clubcore/` — the umbrella chart (118 + 119). OBS ServiceMonitor (OBS-03) + CNPG backup block (BAK-01) extend existing templates (`postgres-cluster.yaml`); backup CronJobs (BAK-02) are new templates. SeaweedFS S3 creds/secret already exist (119 SealedSecret + 118 seaweedfs-s3-secret) — backups reuse them.
- `infra/scripts/` (build/scan/k3d-up/deploy-local/seal-secrets) + `infra/runbooks/sealed-secrets-key-backup.md` — established bash + runbook conventions; `restore.md` (BAK-03) follows the runbook style.
- `apps/backend/app/main.py` — FastAPI app factory; OBS-03 adds `prometheus-fastapi-instrumentator>=7.1,<8` `/metrics` instrumentation here (+ a ServiceMonitor CRD in the chart). Backend Service is `<fullname>-backend:8000`.
- CNPG `Cluster` (`infra/helm/clubcore/templates/postgres-cluster.yaml`, instances:1) — BAK-01 adds `spec.backup.barmanObjectStore`.

### Established Patterns
- Done-bar honesty (D-V40-LOCAL-VALIDATE); tooling reality: terraform/helm/k3d absent → validate/plan/scrape/restore operator-pending, code template-validated + `bash -n`/`terraform fmt`-shape-correct.

### Integration Points
- `monitoring` namespace (OBS-01/02) — new; Terraform cluster module (IAC-02) may manage namespaces + helm_releases for the observability stack.
- `make tf-validate` / `make tf-plan` (IAC-03) — Makefile targets; the full root Makefile is Phase 121, but these two TF targets are IAC-03's deliverable (add them now; 121 composes the rest).

</code_context>

<specifics>
## Specific Ideas

No UI/UX requirements — observability/IaC/backup infra. The 12 IAC/OBS/BAK requirements + locked decisions are the spec. Grafana dashboards are JSON config (OBS-04), not hand-built UI.

</specifics>

<deferred>
## Deferred Ideas

None — scope fixed by ROADMAP requirement mapping (120 = IAC/OBS/BAK). Live apply / real backup-to-S3 / live restore round-trip / alert delivery are operator-pending, not deferred-out-of-milestone.

</deferred>

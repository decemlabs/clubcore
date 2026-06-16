---
phase: 120-iac-observability-backup
plan: "01"
subsystem: infra
tags: [terraform, helm, k3s, kubernetes, null_resource, remote-exec, monitoring, prometheus, loki, alloy]

requires:
  - phase: 119-networking-security
    provides: k3d cluster setup, sealed-secrets, SeaweedFS S3 secret already in place
  - phase: 118-container-images-helm
    provides: umbrella chart layout at infra/helm/clubcore/, k3d setup script patterns

provides:
  - Terraform host module (IAC-01): k3s bare-metal install via null_resource + remote-exec, backend local
  - Terraform cluster module (IAC-02): monitoring namespace + kube-prometheus-stack/loki/alloy helm_releases using v3.2 list-set syntax
  - Root Makefile tf-validate + tf-plan targets (IAC-03)
  - Structural foundation for Plan 02 (OBS-01/02 values files, BAK-01/02/03/04)

affects: [120-02, 120-03, 121-01]

tech-stack:
  added:
    - "hashicorp/null ~3.2 (Terraform provider for null_resource)"
    - "hashicorp/helm 3.2.0 (Terraform provider — v3.2 list-set syntax breaking change)"
    - "hashicorp/kubernetes ~2.30 (Terraform provider for k8s namespaces)"
  patterns:
    - "Terraform backend local — no remote backend (D-V40-MAKEFILE-CD)"
    - "helm_release set = [{name, value}] list-of-objects (D-V40-TF-PROVIDER v3.2)"
    - "Makefile scoped delivery — only IAC-03 targets, full Makefile deferred to Phase 121"

key-files:
  created:
    - infra/terraform/host/main.tf
    - infra/terraform/host/variables.tf
    - infra/terraform/host/terraform.tfvars.example
    - infra/terraform/cluster/main.tf
    - infra/terraform/cluster/variables.tf
    - infra/terraform/cluster/terraform.tfvars.example
    - Makefile

key-decisions:
  - "D-V40-TF-PROVIDER enforced: all helm_release set blocks use list-of-objects syntax [{ name=, value= }] not map syntax"
  - "backend local in both modules — no remote backend per D-V40-MAKEFILE-CD (no git remote)"
  - "terraform validate is the sandbox done-bar; plan/apply are operator-pending (no terraform binary here)"
  - "Traefik NOT disabled in k3s install (D-V40-ONPREM-K3S — bundled ingress)"
  - "grafana_admin_password declared sensitive in variables.tf — forced via tfvars (no default)"

patterns-established:
  - "Terraform file layout: infra/terraform/<module>/{main.tf,variables.tf,terraform.tfvars.example}"
  - "tfvars.example carries placeholder values + header comment mandating real values in un-committed terraform.tfvars"
  - "Makefile scoped to current phase; subsequent phases compose additional targets"

requirements-completed: [IAC-01, IAC-02, IAC-03]

duration: 10min
completed: "2026-06-16"
---

# Phase 120 Plan 01: IaC Terraform Modules Summary

**Terraform host module (k3s null_resource+remote-exec) and cluster module (monitoring ns + 3 observability helm_releases with hashicorp/helm v3.2 list-set syntax) authored with backend local; root Makefile exposes tf-validate + tf-plan (IAC-03 only).**

## Performance

- **Duration:** ~10 min
- **Started:** 2026-06-16T12:10:00Z
- **Completed:** 2026-06-16T12:21:27Z
- **Tasks:** 3 of 3 auto tasks complete (Task 4 = checkpoint:human-verify, operator-pending)
- **Files created:** 7

## Tooling Preflight (recorded per plan requirement)

| Tool | Status | Impact |
|------|--------|--------|
| terraform | ABSENT (no binary in sandbox) | `validate`/`plan`/`apply` are OPERATOR-PENDING — no fabricated output |
| k3d | ABSENT | `plan` against k3d is OPERATOR-PENDING |
| make | PRESENT (GNU Make 3.81) | `make -n tf-validate` dry-run verified |

## Accomplishments

- IAC-01: `infra/terraform/host/` module installs k3s on a bare-metal node via `null_resource` + SSH `connection` + `provisioner "remote-exec"` running the official get.k3s.io install script pinned to `v1.32.5+k3s1`; Traefik kept per D-V40-ONPREM-K3S; `backend "local" {}`; `terraform.tfvars.example` has placeholder values only (T-120-TF mitigated)
- IAC-02: `infra/terraform/cluster/` module manages `kubernetes_namespace.monitoring` + 3 `helm_release` resources (kube-prometheus-stack v86.2.3 / loki v6.29.0 / alloy v0.12.5) with `hashicorp/helm` pinned exactly to `3.2.0`; all `set` blocks use list-of-objects syntax per D-V40-TF-PROVIDER; values files reference `infra/observability/*-values.yaml` authored in Plan 02
- IAC-03: root `Makefile` with ONLY `tf-validate` + `tf-plan` targets; `make -n tf-validate` dry-run prints both validate commands; no Phase-121 build/deploy/smoke targets pre-built

## Task Commits

1. **Task 1: Terraform host module** — `e69ee2b3` (feat)
2. **Task 2: Terraform cluster module** — `079df78d` (feat)
3. **Task 3: Root Makefile tf-validate + tf-plan** — `4ba1475e` (feat)

## Files Created/Modified

- `infra/terraform/host/main.tf` — null_resource k3s_install, SSH connection, remote-exec, backend local
- `infra/terraform/host/variables.tf` — ssh_host, ssh_user, ssh_private_key_path (no defaults), k3s_version
- `infra/terraform/host/terraform.tfvars.example` — placeholder values only; T-120-TF header comment
- `infra/terraform/cluster/main.tf` — kubernetes + helm providers, monitoring namespace, 3 helm_releases with list-set syntax
- `infra/terraform/cluster/variables.tf` — kubeconfig_path, kube_context, chart versions, grafana_admin_password (sensitive)
- `infra/terraform/cluster/terraform.tfvars.example` — placeholder values only
- `Makefile` — tf-validate + tf-plan targets, scoped to IAC-03

## Decisions Made

- D-V40-TF-PROVIDER enforced throughout: `set = [{ name = "...", value = "..." }]` list syntax on every `helm_release`; comment in file explicitly labels the anti-pattern to avoid
- `grafana_admin_password` is declared `sensitive = true` in `variables.tf` with no default, forcing operators to supply it via `terraform.tfvars` (never default or leaked)
- `k3s_version` has a default (`v1.32.5+k3s1`) since it's a version pin not a secret; `ssh_host`, `ssh_user`, `ssh_private_key_path` have NO defaults (force explicit supply)
- Values files in `infra/terraform/cluster/main.tf` reference `../../observability/*-values.yaml` — these files are authored in Plan 02; `terraform validate` passes before them because `file()` is only evaluated at `plan` time

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] Comment in cluster/main.tf triggered the `set {` grep gate**
- **Found during:** Task 2 verification
- **Issue:** The header comment `# NEVER the v2.x map form: set { name = ... }` contained the literal text `set {` which caused the acceptance-criteria grep `! grep -E 'set[[:space:]]*\{'` to exit 1
- **Fix:** Rephrased the comment to describe the forbidden pattern without using the `set {` literal: "NEVER use the v2.x map form for `set` blocks (e.g. the legacy syntax with braces instead of brackets)"
- **Files modified:** `infra/terraform/cluster/main.tf`
- **Committed in:** `079df78d` (Task 2 commit)

---

**Total deviations:** 1 auto-fixed (Rule 1 — comment text triggered verification grep)
**Impact on plan:** Trivial comment rewording; no functional change.

## Operator-Pending Boundary (honest record per D-V40-LOCAL-VALIDATE)

The following steps CANNOT be completed in the sandbox (terraform absent, no reachable k3d):

| Step | Command | Reason |
|------|---------|--------|
| Host module validate | `terraform -chdir=infra/terraform/host validate` | terraform binary absent |
| Cluster module validate | `terraform -chdir=infra/terraform/cluster validate` | terraform binary absent |
| make tf-validate | `make tf-validate` | calls terraform |
| make tf-plan | `make tf-plan` | needs terraform + reachable k3d |
| Host terraform apply | `terraform -chdir=infra/terraform/host apply` | SSH creds + real node |

**Operator verification steps (Task 4 checkpoint, run on machine with terraform ≥ 1.6 + k3d):**

```bash
# 1. Host module validate
cd infra/terraform/host && terraform init && terraform validate
# Expected: "Success! The configuration is valid."

# 2. Cluster module validate
cd infra/terraform/cluster && terraform init && terraform validate
# Expected: "Success! The configuration is valid."

# 3. Both via Makefile
make tf-validate
# Expected: exit 0 (both modules valid)

# 4. Cluster plan against k3d (operator-pending — needs running k3d cluster)
make tf-plan
# Expected: Terraform plan showing monitoring namespace + 3 helm_release resources

# 5. Verify v3.2 list-set syntax did not raise deprecation error
# (No "Warning: Argument is deprecated" for `set` blocks)
```

No fabricated validate/plan output recorded. Sandbox-verified checks: `make -n tf-validate` dry-run prints both validate commands (GNU Make 3.81 confirmed present).

## Issues Encountered

None beyond the comment grep deviation noted above.

## Known Stubs

None — this plan authors structural IaC scaffolding. The `values = [file("...")]` references in `cluster/main.tf` point to Plan 02's outputs (`infra/observability/*-values.yaml`); those files do not exist yet and will be created in Plan 02. This is intentional and expected — `file()` is only evaluated at `terraform plan` time, not `validate` time.

## Threat Surface Scan

No new network endpoints or auth paths introduced. All files are Terraform HCL and a Makefile — no running processes. T-120-TF (tfvars.example secret disclosure) mitigated by placeholder-only values + header comments + `sensitive = true` on `grafana_admin_password`. T-120-TF2 (helm provider set syntax) mitigated by pinning `3.2.0` + list-of-objects enforcement.

## Next Phase Readiness

- Plan 02 (OBS-01/02/04/05): can now create `infra/observability/*-values.yaml` — the cluster module already references them
- Plan 03 (BAK-01/02/03/04): can extend `infra/helm/clubcore/templates/postgres-cluster.yaml` with `barmanObjectStore`
- Phase 121 (OPS-01): root `Makefile` exists; Phase 121 can append additional targets without conflict

---
*Phase: 120-iac-observability-backup*
*Completed: 2026-06-16*

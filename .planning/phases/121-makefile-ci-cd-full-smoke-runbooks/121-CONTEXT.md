# Phase 121: Makefile CI/CD + Full Smoke + Runbooks - Context

**Gathered:** 2026-06-16
**Status:** Ready for planning
**Mode:** Auto-generated (infrastructure phase — discuss skipped per smart-discuss infra detection; capstone of v4.0)

<domain>
## Phase Boundary

A single `make up` command builds, scans, validates, and deploys the full stack to **k3d**; `make smoke` verifies the complete "Looks-Done-But-Isn't" observable checklist; and the production runbook documents the operator-pending boundary explicitly.

**In scope:** OPS-01..04 (4 requirements).
**Out of scope:** everything in 118–120 (already built — this phase only ORCHESTRATES it via the Makefile + documents it).

**Done-bar (D-V40-LOCAL-VALIDATE / D-V40-MAKEFILE-CD):** the root Makefile is the ONLY CD layer (no external runner/registry, local k3d registry). All targets authored + `make -n <target>` dry-parses correctly + the smoke script `bash -n` clean. `make up` green against k3d and `make smoke` passing are **operator-pending** (k3d/helm/trivy/terraform not installable in the build sandbox). The production runbook's operator-pending boundary list is the authorable capstone deliverable.
</domain>

<decisions>
## Implementation Decisions

### Locked milestone decisions (from STATE.md — binding)
- **D-V40-MAKEFILE-CD:** the Makefile is the ONLY CD layer — no git remote, no external runner, no ArgoCD/FluxCD. Local k3d registry via `k3d --registry-create`. Build → scan → validate → deploy → smoke is the pipeline.
- **D-V40-LOCAL-VALIDATE:** `make up`/`make smoke` against k3d = operator-pending (tooling absent); author correct + dry-validate. The production runbook MUST state the operator-pending boundary explicitly (D-72-06 no-fabrication precedent).

### Scope specifics
- **OPS-01:** root `Makefile` targets — `build`, `scan`, `push`, `tf-validate`, `tf-plan`, `helm-lint`, `helm-validate`, `deploy`, `smoke`, `rollback`, `logs`, `psql`, `backup`, `up`, `down`. (tf-validate + tf-plan ALREADY EXIST from Phase 120 — EXTEND the existing Makefile, do not clobber them.) Targets wire the existing `infra/scripts/*.sh` (build-images, scan-images, k3d-up, deploy-local, restore-verify, seal-secrets) — do NOT reimplement script logic in the Makefile; call the scripts.
- **OPS-02:** `make up` = build → scan → tf-validate → helm-lint → deploy → smoke (composed target). Green-against-k3d operator-pending.
- **OPS-03:** `make smoke` checklist (8 "Looks-Done-But-Isn't" checks): `/healthz` 200, migrate Job completed, Redis AOF on, `TZ=UTC` on ALL pods, DNS resolve from each pod (P8/P9 evidence), WebSocket upgrade through ingress, SPA fallback 200, PWA SW cache clean (`/api/*` not cached). `deploy-local.sh` already has a 5-point smoke — extract/expand into a dedicated `make smoke` (or `infra/scripts/smoke.sh`) covering all 8.
- **OPS-04:** `infra/runbooks/production.md` — topology, prerequisites, deploy steps, operations (backup/restore/rollback/scale), troubleshooting, AND an explicit **operator-pending boundary** list aggregating every operator-pending item across v4.0 (k3d/trivy/helm/terraform apply, kubeseal + SEC-02 RSA-key off-node backup, restore round-trip BAK-03, LE-prod TLS, Telegram alert delivery, ЮKassa sandbox + RU email production probes).

### Claude's Discretion
Makefile variable conventions (TAG, NAMESPACE, RELEASE, K3D_CLUSTER), `.PHONY` grouping, whether smoke lives inline in the Makefile vs a dedicated `infra/scripts/smoke.sh` (prefer a script for testability), `make help` formatting, rollback mechanism (`helm rollback`), `logs`/`psql` convenience wrappers (`kubectl logs`/`kubectl exec ... psql`). Runbook section ordering + troubleshooting depth.

</decisions>

<code_context>
## Existing Code Insights

### Reusable Assets
- `Makefile` (root) — already exists with `help`, `tf-validate`, `tf-plan` (Phase 120). EXTEND it with the OPS-01 targets; preserve the 120 targets.
- `infra/scripts/`: `build-images.sh` (→ make build), `scan-images.sh` (→ make scan, trivy gate), `k3d-up.sh` (→ part of make up / a `k3d` target), `deploy-local.sh` (→ make deploy; already has helm lint + kubeconform gate + 5-point smoke), `restore-verify.sh` (→ make backup-verify), `seal-secrets.sh`. Wire these; do not duplicate their logic.
- `infra/runbooks/` — `sealed-secrets-key-backup.md` + `restore.md` exist; `production.md` (OPS-04) follows the same runbook style and links to them.
- `infra/helm/clubcore/` — the full chart (118 stateful+app, 119 networking+security, 120 observability+backup) is what `make deploy` installs; `make smoke` asserts against the deployed release.

### Established Patterns
- Done-bar honesty per D-V40-LOCAL-VALIDATE; tooling reality: k3d/helm/trivy/terraform/kubeconform NOT installed → `make up`/`make smoke`/live pipeline operator-pending. `make -n` dry-parse + `bash -n` on the smoke script ARE achievable. GNU Make 3.81 present.
- Smoke checks mirror the per-phase UAT items (118-UAT migrate/AOF/TZ/PVC; 119-UAT 3-host HTTPS/WS/SPA/SW; 120-UAT scrape/restore) — the operator-pending boundary list in production.md should aggregate the per-phase *-UAT.md pending items.

### Integration Points
- `make up` composes targets across all four phases' artifacts — it is the single entry point an operator runs on a real node.

</code_context>

<specifics>
## Specific Ideas

No UI — operations/orchestration/documentation. The 4 OPS requirements + the explicit operator-pending boundary list are the spec.

</specifics>

<deferred>
## Deferred Ideas

None — final v4.0 phase, scope fixed by ROADMAP requirement mapping (121 = OPS only). `make up`/`make smoke` green-against-k3d is operator-pending, not deferred-out-of-milestone.

</deferred>

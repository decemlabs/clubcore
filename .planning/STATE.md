---
gsd_state_version: 1.0
milestone: v4.0
milestone_name: Production Infrastructure — Self-Hosted k3s
status: verifying
stopped_at: Completed 118-01-PLAN.md — container images
last_updated: "2026-06-16T11:36:50.318Z"
last_activity: 2026-06-16
progress:
  total_phases: 4
  completed_phases: 2
  total_plans: 7
  completed_plans: 7
  percent: 50
---

# Project State

## Project Reference

See: .planning/PROJECT.md

**Core value:** Соло backend-разработчик с AI-агентами должен уметь поэтапно наращивать бизнес-фичи зала на стабильном, архитектурно ограниченном каркасе — без переписывания структуры по мере роста.
**Current focus:** Phase 118 — Container Images + Helm Chart (Core Stack)

## Current Position

Phase: 118 (Container Images + Helm Chart (Core Stack)) — EXECUTING
Plan: 4 of 4
Status: Phase complete — ready for verification
Last activity: 2026-06-16

Progress: [██████████] 100%

## v4.0 Roadmap Summary

| Phase | Goal | Requirements |
|-------|------|--------------|
| 118. Container Images + Helm Chart (Core Stack) | Production-hardened Docker images (all 6 components) + full Helm umbrella chart deployed in k3d (CNPG + Redis + SeaweedFS + migrate Job + app Deployments) | IMG-01..04, DATA-01..04, APP-01..05 |
| 119. Networking, Security + CSRF Rename | Traefik v3 ingress + cert-manager TLS; sealed-secrets + RSA key backup; pod securityContexts; NetworkPolicies + CoreDNS egress; NAME-01 CSRF rename; SEC-06 secure-phase 70 retro | NET-01..04, SEC-01..06 |
| 120. IaC, Observability + Backup | Terraform host/cluster modules (validate+plan green); kube-prometheus-stack + Loki + Alloy; Grafana dashboards; Alertmanager; CNPG WAL backup; Redis/SeaweedFS backup CronJobs; restore round-trip in k3d | IAC-01..03, OBS-01..05, BAK-01..04 |
| 121. Makefile CI/CD + Full Smoke + Runbooks | Root Makefile all targets; `make up` pipeline green against k3d; `make smoke` full checklist; production runbook with operator-pending boundary | OPS-01..04 |

**Coverage:** 39/39 v4.0 requirements mapped (118: 13 · 119: 10 · 120: 12 · 121: 4). **Execution order: 118 → 119 → 120 → 121.**

## v3.2 Roadmap Summary (shipped 2026-06-16 — historical)

| Phase | Goal | Requirements |
|-------|------|--------------|
| 112. Critical Money & Access | Arbitrary payment refund + staff role-change — P0 operational gaps | REF-01, TEAM-01 |
| 113. Promo Codes CRUD | Staff CRUD over existing `promo_codes` backend; wire PlansPage mock→real | PROMO-01, PROMO-02 |
| 114. Attendance Analytics on Existing Reports | FE analytics widgets wired to existing `reports/visits` aggregate | ANL-01 |
| 115. Live & Advanced Analytics | Cohort/anomaly/risk + LiveNow + dashboard KPIs on existing read endpoints | ANL-02, ANL-03, ANL-04 |
| 116. Chat Inbox & Exports | Staff REST over existing messaging module + CSV exports | MSG-01, MSG-02, EXP-01, EXP-02 |
| 117. OpenAPI Handoff + Milestone Gate | Additive openapi regen + `_v32Checks` + ≥1 real-backend contract test per domain + full gate | HND-01 |

## Accumulated Context

### v4.0 Architecture Context (current milestone)

- **D-V40-LOCAL-VALIDATE**: done-bar = local validation only (k3d + `terraform validate/plan` + `helm lint` + `make smoke`); live server apply / LE-prod TLS / real ЮKassa-leg / RU email-SMS — operator-pending (no fabricated evidence, per D-72-06 precedent)
- **D-V40-ONPREM-K3S**: ingress = Traefik v3 (bundled with k3s; ingress-nginx retired + archived March 2026 — no security patches); local validation = k3d (NOT kind — different distro, hides Traefik/ServiceLB behavior)
- **D-V40-MINIO-RETIRED**: MinIO community repo archived April 25, 2026 — SeaweedFS in both docker-compose and k3s (zero app code change; same boto3/aioboto3 env vars); SeaweedFS Helm v4.33.0 actively maintained
- **D-V40-BITNAMI-PAYWALLED**: Bitnami Postgres + Redis images behind Broadcom paywall (moved to `bitnamilegacy`); use CNPG operator (ghcr.io images, built-in WAL archiving) + plain Redis StatefulSet (`redis:7-alpine`)
- **D-V40-SECRETS**: sealed-secrets v0.37.0 as primary (k8s-native, no git remote needed); SOPS/age considered and rejected; CRITICAL: export controller RSA key immediately after install and back up off-node alongside repo (PITFALLS P6 — controller key loss on cluster rebuild is the highest-risk single-point-of-failure)
- **D-V40-REPLICAS**: backend `replicas: 1` for v4.0 (single bare-metal node, resource contention); arq-worker + telegram-bot `strategy: Recreate` + `replicas: 1` are ARCHITECTURAL INVARIANTS (not tuning): violating either creates cron double-fire / Telegram duplicate-polling
- **D-V40-MAKEFILE-CD**: Makefile is the only CD layer (no git remote, no external runner, no ArgoCD/FluxCD); local k3d registry via `k3d --registry-create`
- **D-V40-TF-PROVIDER**: `hashicorp/helm` provider v3.2.0 — breaking schema change from v2.x: all `helm_release` `set` blocks must use list-of-objects syntax, not map syntax
- **D-V40-SCOPE-ADDITIVE**: OpenAPI contract unchanged except additive NAME-01 (CSRF cookie `sportzal_csrf → clubcore_csrf`); staff drift-gate expects additive diff, not byte-stable
- **D-V40-BAK04-INCLUDED**: BAK-04 weekly automated restore-verification CronJob included in scope (justified differentiator — round-trip restore verification vs passive backup-only)
- **D-V40-SEC06-INCLUDED**: SEC-06 `/gsd:secure-phase 70` retro included in Phase 119 (carry-over from v2.0 close: proxy rate-limit bucket, QR post-decode existence check, cancel idempotency)
- **Pitfall invariants (from PITFALLS.md — encode as acceptance criteria):**
  - P1: Postgres PVC node-affinity → `nodeSelector` pinning + `reclaimPolicy: Retain`
  - P2/P3: ARQ double-fire + Telegram duplicate-consume → `strategy: Recreate` + `replicas: 1`
  - P4: migrate race → `pre-install,pre-upgrade` hook + `hook-weight: "-5"` + `alembic check` initContainer
  - P6: sealed-secrets key loss → export RSA key + confirm off-node backup (hard acceptance gate)
  - P8: NetworkPolicy breaks DNS → explicit CoreDNS egress (UDP/TCP 53) in every pod's NetworkPolicy
  - P9: TZ drift → `TZ=UTC` on all pods (verify via `kubectl exec`)
  - P10: SPA fallback + SW → nginx `try_files` + SW doesn't cache `/api/*`

### Research Flags (investigate at plan-phase time, not pre-flight)

- **Phase 118**: CNPG `Cluster.spec.backup.barmanObjectStore` field names for SeaweedFS S3 endpoint — verify against CNPG v1 API docs
- **Phase 119**: Traefik v3 WebSocket sticky-session annotation key — may differ from v2; verify before writing Ingress template
- **Phase 120**: Loki community chart v17.x Alloy sub-chart values schema changed from v6.x — review migration guide before writing values files

### Pending Todos

- v4.0 roadmap created (Phases 118–121). Next: `/gsd-plan-phase 118` (Container Images + Helm Chart — Core Stack).
- Phase 118 plan: read existing `apps/backend/Dockerfile` and `docker-compose.yml` before building (living codebase, not from scratch); check SeaweedFS Helm chart current values schema at plan time.
- Phase 119 plan: investigate Traefik v3 WS annotation before writing Ingress; SEC-06 retro is running an existing skill (`/gsd:secure-phase 70`), not infra construction.
- Phase 120 plan: verify CNPG `barmanObjectStore` fields + Loki v17.x Alloy schema at plan time; BAK-04 restore-verify CronJob is a differentiator — include restore evidence script.

### Blockers/Concerns

None at milestone open.

## Deferred Items

**Carried forward from v3.2 close (2026-06-16):**

| Category | Item | Status |
|----------|------|--------|
| tech-debt (test-infra) | Full backend pytest not run green — systemic PRE-EXISTING test-isolation deadlock (`permissive_booking_config` × `working_hours_config`). Out of v3.2 scope. Diagnosis in `117-HUMAN-UAT.md`. | deferred → test-infra refactor |
| human-verify | Browser/human UAT for all 6 v3.2 phases (112-117 VERIFICATION = human_needed) | pending — see per-phase *-UAT.md |
| security | Phase 70 CR-02/IN-01/IN-02 (proxy rate-limit, QR post-decode, cancel idempotency) | → SEC-06 in Phase 119 |
| production | RUN-01 ЮKassa sandbox sale+refund walkthrough | N/A-until-production |
| production | RUN-02 RU email deliverability probe | N/A-until-production |

## Session Continuity

Last session: 2026-06-16T11:36:50.313Z
Stopped at: Completed 118-01-PLAN.md — container images
Resume: `/gsd-plan-phase 118` (Container Images + Helm Chart — Core Stack)

## Operator Next Steps

- `/gsd-plan-phase 118` to begin Phase 118 planning

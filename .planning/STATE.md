---
gsd_state_version: 1.0
milestone: v4.1
milestone_name: Codebase Hardening
status: planning
last_updated: "2026-07-26T10:41:31.474Z"
last_activity: 2026-07-26
progress:
  total_phases: 0
  completed_phases: 0
  total_plans: 0
  completed_plans: 0
  percent: 0
---

# Project State

## Project Reference

See: .planning/PROJECT.md

**Core value:** Соло backend-разработчик с AI-агентами должен уметь поэтапно наращивать бизнес-фичи зала на стабильном, архитектурно ограниченном каркасе — без переписывания структуры по мере роста.
**Current focus:** Phase 118 — Container Images + Helm Chart (Core Stack)

## Current Position

Phase: Not started (defining requirements)
Plan: —
Status: Defining requirements
Last activity: 2026-07-26 — Milestone v4.1 started

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

### Quick Tasks Completed

| # | Description | Date | Commit | Directory |
|---|-------------|------|--------|-----------|
| 260616-xa9 | Rename apps: admin-app→admin, client-pwa→client (dirs + package names + all infra/backend/CI/docs refs) | 2026-06-16 | f2a3570c | [260616-xa9-rename-apps-admin-app-to-admin-client-pw](./quick/260616-xa9-rename-apps-admin-app-to-admin-client-pw/) |
| 260726-hou | UAT audit follow-through: fix audit-uat's false All Clear after milestone archival + reconcile 11 stale UAT statuses + pin the Phase-94 typing-indicator consumer path | 2026-07-26 | 299de980 | [260726-hou-sync-stale-uat-statuses-fix-audit-uat-gl](./quick/260726-hou-sync-stale-uat-statuses-fix-audit-uat-gl/) |

## Deferred Items

**Restored to the ledger by the 2026-07-26 cross-phase UAT audit (quick `260726-hou`).**
These were tracked at v2.5 close, then silently dropped when the v2.5 block was pruned —
v2.6 was expected to carry them but became Referral System instead. They are open, not done.

| Category | Item | Status |
|----------|------|--------|
| bug (dormant) | **Chat typing indicator does not surface in the live dev browser.** Consumer path is now PROVEN CORRECT in jsdom — `apps/client/src/screens/ChatScreen.typing.test.jsx`, 5/5 green: bridge installs, dots + «печатает…» render in the open thread, 5s auto-dismiss fires, WR-06 ownership guard restores the previous handler. So the defect is NOT the component's render logic; likeliest cause is the original console probe having REPLACED `window.__chatTyping` with its own counting wrapper (suppresses the real handler while still reporting handlerCalls=1), or a stale service worker. | open — but UNREACHABLE in production: no typing PRODUCER exists (Telegram has no typing API; the staff frontend never got one). Close together with a producer. See `94-VERIFICATION.md`. |
| tech-debt (v2.6 carry) | RCPT-02 typing PRODUCER — WS fan-out + PWA consumer are wired, nothing publishes `publish_typing` | open — needs a staff-side producer |
| infra | `seaweedfs-s3` gateway pod CrashLoops in-cluster (surfaced in the 2026-06-16 live k3s run; not diagnosed — backend was the critical path; possibly S3 `existingConfigSecret`/auth) | open — needs a live cluster to reproduce |
| test-infra | 6 unresolved `test_sell_*` online-payment tests use unscoped `select(OnlinePayment)` and assert absolute row counts, so leftover rows in the host `clubcore` DB break them | open — see `999.5-…/deferred-items.md` |

**Carried forward from v3.2 close (2026-06-16):**

| Category | Item | Status |
|----------|------|--------|
| tech-debt (test-infra) | ~~Full backend pytest not run green — systemic test-isolation deadlock (`permissive_booking_config` × `working_hours_config`)~~ | ✅ RESOLVED `f438ced2` (2026-06-17) — autouse fixture held an uncommitted `working_hours_config` row lock that alembic-downgrade subprocess tests + the real-commit booking-race test deadlocked against. Fix: `no_permissive_booking_config` marker on those 4 modules + booking-race teardown restore + `pytest-timeout` 180s safety net + suppress starlette-1.x TestClient deprecation that aborted collection. Full suite now completes ~15m: 3058 passed / 3 failed / 2 errors (all pre-existing/flaky). Diagnosis: `.planning/debug/pytest-isolation-deadlock.md`. |
| human-verify | Browser/human UAT for all 6 v3.2 phases (112-117 VERIFICATION = human_needed) | ✅ SMOKE-PASSED 2026-06-17 (live browser, owner+client) — admin Dashboard(115)/Reports+CSV(114/115/116)/Finance+CSV(112)/Plans+promo FIRST500·FIT10(113)/Chat inbox(116)/Audit-log-with-null-actor(the v3.0 crash case, now clean) all render with ZERO console errors; client PWA OTP→onboarding→home on real seeded plan. CAVEAT: fresh re-seed has no transactions, so revenue-POPULATED report/finance views weren't exercised live — those shapes are covered by the v3.2 real-backend contract tests (green). Hero KPIs (847 clients/MRR) remain known decorative mock chrome. |
| security | Phase 70 CR-02/IN-01/IN-02 (proxy rate-limit, QR post-decode, cancel idempotency) | → SEC-06 in Phase 119 |
| production | RUN-01 ЮKassa sale+refund | ✅ TEST-SHOP SUFFICIENT (user decision 2026-06-17 — live credentialed leg NOT needed for MVP/demo). Verified live: client checkout against sandbox shop 1372271 (`YOOKASSA_SANDBOX=true`) returns a real `confirmationUrl` (yoomoney.ru hosted page) + `onlinePaymentId`. Demo: pay with test card 5555 5555 5555 4477, activate via webhook (`POST /api/v1/_internal/yookassa/webhook` with the real online_payments id). Live prod creds remain the only un-done part, explicitly out of scope. |
| production | RUN-02 RU email deliverability probe | N/A-until-production |

**Acknowledged and deferred at v4.0 close (2026-06-16):**

These are the D-V40-LOCAL-VALIDATE operator-pending boundary — static validation passed; live legs require a real k3d/helm/terraform toolchain. Full list + 2 HARD GATES in `infra/runbooks/production.md` (§ Operator-Pending Boundary) and the per-phase `*-UAT.md` files.

| Category | Item | Status |
|----------|------|--------|
| human-verify | Phase 118 verification (118-UAT: 4 items — live k3d deploy, trivy scan, helm lint, alembic-check) | human_needed — operator-pending |
| human-verify | Phase 119 verification (119-UAT: 10 items — 3-host HTTPS/TLS, WS, kubeseal round-trip, NetworkPolicy enforcement; **HARD GATE SEC-02** RSA-key off-node backup) | human_needed — operator-pending |
| human-verify | Phase 120 verification (120-UAT: 9 items — terraform validate/plan, live scrape, alert delivery; **HARD GATE BAK-03** verified restore round-trip) | human_needed — operator-pending |
| human-verify | Phase 121 verification (121-UAT: 4 items — live `make up`/`make smoke` against k3d) | human_needed — operator-pending |
| planning (backlog) | `2026-06-02-future-milestones-sequence-post-v2-1.md` todo (future-milestone sequencing idea) | deferred → backlog |

**Live-deploy findings (2026-06-16 — real k3s-in-Docker run; partial smoke).** Stood up k3s in Docker, imported the 4 images, installed CNPG 1.27, `helm install`ed the core stack. Verified live: CNPG Postgres 16.6 serving SQL, Redis (AOF + allkeys-lru), SeaweedFS master/filer/volume, both nginx frontends, CoreDNS, TZ=UTC, Retain SC binding PVCs. Surfaced (fixed where safe, else logged):

| Severity | Finding | Status |
|----------|---------|--------|
| 🟢 fixed | Terraform cluster module: `provider "helm"` used v2.x `kubernetes { }` block; v3.x needs `kubernetes = { }` attr → `terraform validate` failed | FIXED `6f91e93e` (both modules validate green) |
| 🟢 fixed | Frontend images: HIGH CVEs (nghttp2-libs, zlib) in nginx:1.27-alpine base | FIXED `deeda373` (apk upgrade → 0 HIGH/CRITICAL) |
| 🟢 fixed | Runbook helm prereq `>=3.14`; SeaweedFS subchart needs `fromToml` (Helm ≥3.17) | FIXED `deeda373` |
| 🟢 fixed | migrate Job was a `pre-install` hook but CNPG `Cluster` is a normal resource → on **first** `helm install` the hook waited for a Postgres that didn't exist yet → deadlock/timeout. | FIXED `ce845397` (migrate is now a NORMAL chart resource, not a helm hook) + `79df66d2` (`backoffLimit:3` to ride out CNPG bootstrap connection race). See `infra/helm/clubcore/templates/migrate-job.yaml:52-79`. |
| 🟢 fixed | `alembic upgrade head` on a FRESH DB failed at rev `0033_…`: `alembic_version.version_num` was VARCHAR(32) but 7 revision ids exceed 32 chars; Phase-108 `version_num_col_type` kwarg was silently ignored. | FIXED `ce845397` + `059a885e` (env.py pre-creates `alembic_version` as VARCHAR(255) and ALTERs it wide BEFORE migrations run). See `apps/backend/alembic/env.py:142-156`. |
| 🟢 fixed | backend image: `starlette` 0.52.1 → HIGH CVE-2026-48710 "BadHost" (host-header auth-bypass, fixed in starlette 1.0.1) | FIXED `1352ef74` (starlette→1.3.1, pinned `>=1.0.1`; prometheus-fastapi-instrumentator→8 since 7.1 capped starlette<1.0.0; FastAPI unchanged — floors `>=0.46.0`). mypy clean, unit tests + live healthz/login/metrics 200. |
| 🟡 minor | `seaweedfs-s3` gateway pod CrashLoops in-cluster (not diagnosed — backend was the critical path; possibly S3 `existingConfigSecret`/auth) | OPEN — investigate at live bring-up |
| ℹ️ note | `postgres.nodeSelector` defaults to k3d node name `k3d-clubcore-server-0` (correct for the documented k3d setup; override for other clusters). Helm map-merge gotcha: an empty `{}` override does NOT clear it — set the concrete hostname. | not a bug — documented behavior |

## Session Continuity

Last session: 2026-06-16T14:15:59.209Z
Stopped at: Completed 118-01-PLAN.md — container images
Resume: `/gsd-plan-phase 118` (Container Images + Helm Chart — Core Stack)

## Operator Next Steps

- Start the next milestone with /gsd-new-milestone

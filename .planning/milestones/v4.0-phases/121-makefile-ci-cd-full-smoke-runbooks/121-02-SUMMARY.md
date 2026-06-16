---
phase: 121-makefile-ci-cd-full-smoke-runbooks
plan: "02"
subsystem: infra/runbooks
tags: [runbook, operations, ops-04, production, operator-pending, k3s, k3d]
dependency_graph:
  requires: [121-01]
  provides: [OPS-04, production-runbook]
  affects: [infra/runbooks/]
tech_stack:
  added: []
  patterns:
    - Runbook style matching restore.md + sealed-secrets-key-backup.md (header block / OPERATOR-PENDING callouts / HARD GATE checkboxes / Quick Reference + Security Notes)
key_files:
  created:
    - infra/runbooks/production.md
  modified: []
decisions:
  - "OPS-04 production runbook authored as umbrella document linking to restore.md (BAK-03/BAK-04 deep dive) and sealed-secrets-key-backup.md (SEC-02 P6 deep dive)"
  - "Operator-Pending Boundary aggregates all 23 per-phase UAT items (118:4 + 119:10 + 120:9) plus 6 cross-cutting production probes in a single section — the explicit honesty boundary per D-V40-LOCAL-VALIDATE / D-72-06"
  - "SEC-02 and BAK-03 flagged as HARD GATES with blockquoted callouts and [ ] acceptance checkboxes — both must be closed before production deploy"
  - "arq-worker/telegram-bot replicas:1 + Recreate documented as ARCHITECTURAL INVARIANTS in the Scale section (D-V40-REPLICAS)"
  - "No real secret embedded — placeholders only (<bot-token>, <db-password>, <secret-key>); sealing workflow references seal-secrets.sh"
metrics:
  duration: "~4 minutes"
  completed_date: "2026-06-16"
  tasks_completed: 2
  files_created: 1
---

# Phase 121 Plan 02: Production Runbook Summary

**One-liner:** Umbrella production runbook (OPS-04) for the v4.0 k3s stack covering topology, toolchain prerequisites, `make up` deploy pipeline, backup/restore/rollback/scale operations, troubleshooting, and an explicit 23-item + 6-probe operator-pending boundary list with 2 HARD gates.

---

## What Was Built

`infra/runbooks/production.md` (495 lines) — the OPS-04 umbrella runbook. It follows the established runbook style (restore.md + sealed-secrets-key-backup.md analogs) and links to both as deep-dive references.

### Sections authored

| Section | Content |
|---------|---------|
| Topology | Single bare-metal k3s node; Traefik v3 ingress (3 hosts: api/admin/client-pwa); CNPG Postgres (instances:1) + Redis StatefulSet (AOF) + SeaweedFS; arq-worker + telegram-bot (Recreate/replicas:1 INVARIANTS); monitoring namespace (kube-prometheus-stack + Loki + Alloy + Grafana + Alertmanager); sealed-secrets controller; backup CronJobs. Architecture decisions D-V40-ONPREM-K3S + D-V40-REPLICAS referenced. |
| Prerequisites | Toolchain versions table (k3d>=5.6, helm>=3.14, kubectl, docker, trivy>=0.50, terraform>=1.8, kubeconform, kubeseal 0.37.x); hardware spec (4 CPU / 8 GB / 80 GB SSD + second PC for key backup); first-time sealed-secrets setup with SEC-02 hard gate cross-reference. |
| Deploy Steps | `make up` quick path + manual step-by-step fallback (build-images.sh → k3d-up.sh → deploy-local.sh → smoke.sh); production sealed-secrets deploy path. Fenced bash with `# Expected:` comments in analog style. |
| Operations | Backup/restore (links restore.md for full procedure); rollback (`make rollback` = `helm rollback clubcore`; helm history usage); scale (table of all workloads with explicit MUST NOT scale >1 warning for arq-worker + telegram-bot, annotated as ARCHITECTURAL INVARIANTS per D-V40-REPLICAS); logs/psql convenience wrappers. |
| Troubleshooting | 13-row table: migrate Job failure, CrashLoop, readOnlyRootFilesystem, NetworkPolicy/DNS P8, TZ drift P9, SPA/SW cache P10, cert not Ready, backup alert, Grafana/Loki no data, helm timeout, SeaweedFS down, Telegram bot failing, rollback failure. Each with diagnostic command. |
| Quick Reference | 15 key commands (make up/smoke/rollback/logs/psql/backup, kubectl pods, backup operations, sealed-secrets export, seal-secrets.sh, make down). |
| Security Notes | 7-row table covering RSA key, plaintext secrets, SHA-tagged images, restore target safety, readOnlyRootFilesystem, NetworkPolicies, CVE gate. |
| Operator-Pending Boundary | 2 HARD GATES + 23 per-phase UAT items + 6 cross-cutting production probes (see below). |

### Operator-Pending Boundary — complete item count

| Source | Items |
|--------|-------|
| Phase 118 UAT | 4 (live k3d deploy; trivy CVE scan; helm lint CR-01; alembic check) |
| Phase 119 UAT | 10 (SEC-02 HARD GATE; helm dry-run; NET-01 HTTPS; NET-03 cert; NET-02 WS; NET-04 SPA/SW; SEC-01 kubeseal; SEC-03 readOnly; SEC-04 NetworkPolicy; SEC-06 secure-phase) |
| Phase 120 UAT | 9 (BAK-03 HARD GATE; tf-validate; tf-plan; OBS-03 /metrics; OBS-04 Grafana; OBS-02 Loki; BAK-04 CronJob; OBS-05 Telegram; metric name confirm) |
| Cross-cutting probes | 6 (LE-prod TLS; terraform apply real VM; ЮKassa sandbox; RU email deliverability; Telegram bot token; disk durability) |
| **Total** | **29 items** (23 per-phase + 6 cross-cutting) |

Both HARD gates have blockquoted callouts + `- [ ]` acceptance checkboxes in the sealed-secrets-key-backup.md style. Final line: "Do NOT mark v4.0 as production-ready until HARD GATE 1 (SEC-02) and HARD GATE 2 (BAK-03) are both fully closed."

---

## Deviations from Plan

None — plan executed exactly as written. Both tasks completed in a single pass. The 6 cross-cutting production probes were included as specified in the plan's task 2 action (from REQUIREMENTS.md and STATE.md Deferred Items).

---

## Threat Flags

None. No new network endpoints, auth paths, file access patterns, or schema changes introduced — this plan authors a Markdown document only. T-121-05 (no real secret embedded) verified: only placeholders `<bot-token>`, `<db-password>`, `<secret-key>` present.

---

## Self-Check: PASSED

- [x] `infra/runbooks/production.md` exists (495 lines)
- [x] Commit `add09c7a` exists: `git log --oneline | head -1`
- [x] All required sections present (Topology, Prerequisites, Deploy, Operations, Troubleshooting, Quick Reference, Security Notes, Operator-Pending Boundary)
- [x] Both runbook links present: `restore.md` and `sealed-secrets-key-backup.md`
- [x] `make up` referenced as the deploy entry point
- [x] SEC-02 and BAK-03 flagged as HARD GATES with `- [ ]` checkboxes
- [x] 23 per-phase UAT items aggregated (118:4 + 119:10 + 120:9)
- [x] 6 cross-cutting production probes included
- [x] No real secret embedded (grep for real tokens/keys confirms only placeholders)
- [x] arq-worker/telegram-bot MUST NOT scale >1 explicitly warned in Scale section

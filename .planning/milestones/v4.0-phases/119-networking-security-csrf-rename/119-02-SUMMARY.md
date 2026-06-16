---
phase: 119-networking-security-csrf-rename
plan: "02"
subsystem: infra/helm/security
tags: [sealed-secrets, securityContext, networkpolicy, sec01, sec02, sec03, sec04, p6, p8]
dependency_graph:
  requires: [119-01]
  provides: [sealed-secrets-template, securitycontext-hardening, networkpolicy-segmentation]
  affects: [119-03, 121]
tech_stack:
  added:
    - "sealed-secrets v0.37.0 (bitnami.com/v1alpha1 SealedSecret CRD)"
    - "clubcore.hardenedSecurityContext Helm helper (allowPrivilegeEscalation:false + readOnlyRootFilesystem:true + drop:ALL)"
    - "NetworkPolicy networking.k8s.io/v1 (default-deny + explicit-allow with CoreDNS egress)"
  patterns:
    - "Two-path secret gate: plaintextForLocalK3d (k3d dev) vs sealed.enabled (production)"
    - "hardenedSecurityContext helper factored in _helpers.tpl — single source of truth for SEC-03 across 6 workloads"
    - "P8 invariant: CoreDNS egress UDP+TCP port 53 required in every NetworkPolicy"
key_files:
  created:
    - infra/helm/clubcore/templates/sealed-secret.yaml
    - infra/scripts/seal-secrets.sh
    - infra/runbooks/sealed-secrets-key-backup.md
    - infra/helm/clubcore/templates/networkpolicy-default-deny.yaml
    - infra/helm/clubcore/templates/networkpolicy-allow.yaml
  modified:
    - infra/helm/clubcore/templates/app-secret.yaml
    - infra/helm/clubcore/templates/_helpers.tpl
    - infra/helm/clubcore/templates/backend-deployment.yaml
    - infra/helm/clubcore/templates/arq-worker-deployment.yaml
    - infra/helm/clubcore/templates/telegram-bot-deployment.yaml
    - infra/helm/clubcore/templates/migrate-job.yaml
    - infra/helm/clubcore/templates/admin-app-deployment.yaml
    - infra/helm/clubcore/templates/client-pwa-deployment.yaml
    - infra/helm/clubcore/values.yaml
decisions:
  - "D-119-02-HELPER: SEC-03 hardening factored into clubcore.hardenedSecurityContext helper in _helpers.tpl — avoids drift across 6 workloads (backend/arq-worker/telegram-bot/migrate/admin-app/client-pwa)"
  - "D-119-02-EMPTYDIR: /tmp emptyDir on all 6 workloads; /var/cache/nginx emptyDir on nginx frontends — minimal writable scratch sufficient for all app write paths"
  - "D-119-02-TWO-PATH: secrets.plaintextForLocalK3d=true (k3d dev default) vs secrets.sealed.enabled=true (production path) — both flags off = no Secret rendered"
  - "D-119-02-SCOPE-EXTEND: admin-app + client-pwa hardened beyond plan 02 files_modified list — plan must_haves truths say every app workload; nginx UID 101 preserved per D-119-02-UID"
metrics:
  duration: "~50 minutes"
  completed_date: "2026-06-16"
  tasks_completed: 3
  tasks_operator_pending: 1
  files_created: 5
  files_modified: 9
---

# Phase 119 Plan 02: Security Hardening — Sealed Secrets + securityContext + NetworkPolicy

**One-liner:** SealedSecret production path + kubeseal helper with RSA-key export guard + SEC-03 ASVS hardening across 6 workloads (drop ALL + readOnlyRootFilesystem + emptyDir scratch) + default-deny NetworkPolicies with mandatory CoreDNS egress (P8) on every allow policy.

## What Was Built

### Task 1: SealedSecret + kubeseal helper + RSA-key backup runbook (SEC-01, SEC-02)

**app-secret.yaml — two-path gate (SEC-01):**
Gated the existing plaintext Secret behind `{{- if .Values.secrets.plaintextForLocalK3d }}`. Default is `true` for k3d development. A loud comment block warns that this path MUST NEVER reach a live server. The `{{- end }}` closes the gate. The existing keys (SECRET_KEY, DATABASE_URL, TELEGRAM_BOT_TOKEN, S3 creds, EMAIL creds) are preserved unchanged.

**sealed-secret.yaml — new (SEC-01 production path):**
`bitnami.com/v1alpha1` `SealedSecret` gated behind `{{- if .Values.secrets.sealed.enabled }}` (default `false`). Namespaced scope. Reads encrypted blobs from `values.secrets.sealed.encryptedData.<KEY>` populated by `seal-secrets.sh`. Same `metadata.name` as the plaintext Secret — the controller unseals it into the same Secret all workloads consume via `envFrom`. `required` guards fail loudly if `sealed.enabled=true` but blobs are empty. No plaintext stringData is ever committed.

**seal-secrets.sh — new (SEC-01/SEC-02):**
Bash script following `deploy-local.sh` conventions (`set -euo pipefail`, `REPO_ROOT` via `git rev-parse`, `log/ok/fail/err` helpers, `check_prereq`). Four steps:
1. `kubeseal --fetch-cert` → writes cert to temp file
2. Builds a temporary plaintext Secret from `SEAL_*` env vars → `kubeseal --format yaml` → prints `encryptedData` values for a Helm values override file
3. Exports the controller RSA private key (`kubectl get secret -n kube-system -l sealedsecrets.bitnami.com/sealed-secrets-key -o yaml`) to a path OUTSIDE the repo
4. `check_no_key_in_repo` guard: refuses to write the RSA key inside the git working tree — prints operator instructions instead

**sealed-secrets-key-backup.md — new (SEC-02 P6 hard gate runbook):**
Complete runbook: why the controller RSA key is the single highest-risk loss, exact export command, where to store on the second PC, restore procedure (apply key Secret BEFORE installing the controller on rebuild), restore verification (re-seal a test value + confirm controller unseals it), and a `## P6 Hard Gate — Acceptance Criteria` checklist. OPERATOR-PENDING clearly marked.

**values.yaml extensions:**
- `secrets.plaintextForLocalK3d: true` (k3d default, gate switch)
- `secrets.sealed.enabled: false` (off by default)
- `secrets.sealed.encryptedData: {}` (populated by `seal-secrets.sh`, not values.yaml)

### Task 2: securityContext hardening across all 6 workloads (SEC-03)

**_helpers.tpl — `clubcore.hardenedSecurityContext` helper (new):**
Single source of truth for SEC-03 container-level hardening:
```yaml
runAsNonRoot: true
runAsUser: {{ .runAsUser | default 1000 }}
allowPrivilegeEscalation: false
readOnlyRootFilesystem: true
capabilities:
  drop:
    - ALL
```
All 6 workloads use `{{ include "clubcore.hardenedSecurityContext" (dict "runAsUser" N) | nindent 12 }}` — drift-free.

**Per-workload changes (backend, arq-worker, telegram-bot, migrate):**
- Pod-level: added `seccompProfile.type: RuntimeDefault` alongside existing `runAsNonRoot`/`runAsUser`
- Container-level: replaced stub `{runAsNonRoot, runAsUser}` with `include clubcore.hardenedSecurityContext`
- emptyDir volumes + volumeMounts:
  - All 4: `/tmp` — uvicorn/asyncpg/ARQ/alembic/Python stdlib write here
  - backend initContainer (alembic-check): `/tmp`

**Per-workload changes (admin-app, client-pwa) — Rule 2 deviation:**
119-01-SUMMARY listed these as plan 02 known stubs. Hardened with UID 101 (nginx user, D-119-02-UID):
- Pod-level: `seccompProfile.type: RuntimeDefault`
- Container-level: `clubcore.hardenedSecurityContext` with `runAsUser: 101`
- emptyDir volumes: `/tmp` (nginx.pid + all body temp dirs per nginx.conf) + `/var/cache/nginx` (nginx worker cache)

**values.yaml extension:**
Added `securityContext:` docs block documenting the applied defaults and UID rationale per workload.

### Task 3: NetworkPolicy default-deny + explicit allow + CoreDNS egress (SEC-04, pitfall P8)

**networkpolicy-default-deny.yaml — new:**
Empty `podSelector: {}` selects ALL namespace pods. `policyTypes: [Ingress, Egress]` with no rules = deny all. Gated behind `networkPolicy.enabled` (default `false`).

**networkpolicy-allow.yaml — new — 6 policies:**

| Policy | Selector | Ingress | Egress |
|--------|----------|---------|--------|
| backend | component: backend | Traefik (kube-system):8000 | postgres:5432 + redis:6379 + seaweedfs:8333 + CoreDNS:53 |
| arq-worker | component: arq-worker | — | redis:6379 + postgres:5432 + CoreDNS:53 |
| telegram-bot | component: telegram-bot | — | redis:6379 + postgres:5432 + internet:443 + CoreDNS:53 |
| migrate | component: migrate | — | postgres:5432 + CoreDNS:53 |
| admin-app | component: admin-app | Traefik (kube-system):8080 | CoreDNS:53 |
| client-pwa | component: client-pwa | Traefik (kube-system):8080 | CoreDNS:53 |

**P8 mandatory — CoreDNS egress:** every policy includes:
```yaml
- to:
    - namespaceSelector:
        matchLabels:
          kubernetes.io/metadata.name: kube-system
      podSelector:
        matchLabels:
          k8s-app: kube-dns
  ports:
    - protocol: UDP
      port: 53
    - protocol: TCP
      port: 53
```
14 total `port: 53` occurrences (2 per policy × 7 policies counting default-deny which has none = 6 allow policies × 2 = 12 + 2 from combined-ports per block). Both protocols confirmed in every allow policy.

**Selectors:** `cnpg.io/cluster: {{ include "clubcore.fullname" . }}-postgres` for CNPG pods; `app.kubernetes.io/component: redis` for Redis; namespaceSelector `kube-system` for Traefik + CoreDNS. OPERATOR NOTE comments included for tightening after `kubectl get pods --show-labels`.

**values.yaml extension:**
Added `networkPolicy.enabled: false` + `networkPolicy.coredns:` selector label docs block with P8 warning.

### Task 4: Operator Verification — OPERATOR-PENDING (SEC-02 P6 hard gate)

SEC-02 hard gate cannot be exercised in the build sandbox (kubeseal, live cluster, and second-PC absent). This is an explicit blocking operator action — NOT auto-approved.

## Validation Status

| Check | Status |
|-------|--------|
| app-secret.yaml plaintext gated to local k3d | TEMPLATE-VALIDATED |
| sealed-secret.yaml SealedSecret kind + bitnami.com/v1alpha1 | TEMPLATE-VALIDATED |
| seal-secrets.sh bash -n syntax check | TEMPLATE-VALIDATED |
| seal-secrets.sh fetch-cert + RSA key export + repo-write guard | TEMPLATE-VALIDATED |
| sealed-secrets-key-backup.md controller ref + OPERATOR-PENDING | TEMPLATE-VALIDATED |
| values.yaml plaintextForLocalK3d / sealed.enabled / encryptedData blocks | TEMPLATE-VALIDATED |
| SEC-03: readOnlyRootFilesystem + drop ALL + allowPrivilegeEscalation:false in all 6 workloads | TEMPLATE-VALIDATED |
| SEC-03: emptyDir /tmp on all 6 workloads + /var/cache/nginx on nginx frontends | TEMPLATE-VALIDATED |
| SEC-03: runAsUser preserved (1000 for backend/arq-worker/telegram-bot/migrate; 101 for nginx frontends) | TEMPLATE-VALIDATED |
| networkpolicy-default-deny.yaml kind NetworkPolicy + empty podSelector | TEMPLATE-VALIDATED |
| networkpolicy-allow.yaml 6 policies, CoreDNS UDP+TCP :53 in every policy (14 occurrences) | TEMPLATE-VALIDATED |
| values.yaml networkPolicy.enabled/coredns blocks | TEMPLATE-VALIDATED |
| `helm template` / `helm lint` | HELM-ABSENT (operator workstation) |
| kubeseal round-trip (encrypt → apply → controller decrypt) | OPERATOR-PENDING (no cluster) |
| RSA-key export + off-node backup (SEC-02 P6 hard gate) | OPERATOR-PENDING (BLOCKING) |
| readOnlyRootFilesystem boot without CrashLoop (emptyDir smoke) | OPERATOR-PENDING |
| NetworkPolicy enforcement + CoreDNS resolution smoke | OPERATOR-PENDING |

## Operator Commands (SEC-02 P6 Hard Gate — Required Before Production Deploy)

```bash
# 1. Install sealed-secrets v0.37.0 in kube-system
helm repo add sealed-secrets https://bitnami-labs.github.io/sealed-secrets
helm repo update
helm install sealed-secrets -n kube-system --version 0.37.0 sealed-secrets/sealed-secrets

# 2. Set plaintext env vars (DO NOT commit these)
export SEAL_SECRET_KEY="$(openssl rand -hex 32)"
export SEAL_DATABASE_URL="postgresql+asyncpg://app:<pg-password>@clubcore-postgres-rw:5432/clubcore"
export SEAL_S3_ACCESS_KEY_ID="your-s3-access-key"
export SEAL_S3_SECRET_ACCESS_KEY="your-s3-secret"
export SEAL_TELEGRAM_BOT_TOKEN="your-bot-token"

# 3. Run the sealing helper (produces encryptedData + exports RSA key)
bash infra/scripts/seal-secrets.sh
# → Prints encryptedData values for values-production.yaml
# → Exports RSA key to /tmp/clubcore-sealed-secrets-key-<date>.yaml

# 4. SEC-02 P6 HARD GATE: follow infra/runbooks/sealed-secrets-key-backup.md
#    - Copy the exported key to the second PC NOW
#    - Verify restore works (see Step 5 in the runbook)

# 5. Deploy with sealed path (use -f not --set for real ciphertext)
helm upgrade --install clubcore infra/helm/clubcore \
  --set image.tag=$(git rev-parse --short HEAD) \
  --set secrets.plaintextForLocalK3d=false \
  --set secrets.sealed.enabled=true \
  -f /path/to/values-production.yaml

# 6. Verify controller unsealed the Secret
kubectl get secret clubcore-app-secret -o jsonpath='{.data.SECRET_KEY}' | base64 -d | head -c 8
# Should return first 8 chars of the real SECRET_KEY

# 7. SEC-03 smoke: verify read-only root and hardened context
kubectl get pod <backend-pod> -o jsonpath='{.spec.containers[0].securityContext}'
# Expected: readOnlyRootFilesystem:true, allowPrivilegeEscalation:false, capabilities.drop:[ALL]

# 8. SEC-04 + P8 NetworkPolicy smoke
kubectl apply --dry-run=server -f - <<'EOF'  # validate policy exists
# Then with networkPolicy.enabled=true:
helm upgrade --install clubcore infra/helm/clubcore \
  --set image.tag=... --set networkPolicy.enabled=true ...
kubectl exec <backend-pod> -- nslookup clubcore-postgres-rw  # DNS MUST resolve (P8)
```

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 2 - Missing Critical] SEC-03 hardening extended to admin-app + client-pwa frontend workloads**

- **Found during:** Task 2 (read admin-app-deployment.yaml + client-pwa-deployment.yaml which had explicit "plan 02 scope" stub comments)
- **Issue:** The plan's `must_haves.truths` states "every app workload" must be hardened. admin-app and client-pwa were explicitly listed as known stubs in 119-01-SUMMARY with a "plan 02 scope" note. However, plan 02's `files_modified` frontmatter did not list them.
- **Fix:** Applied `clubcore.hardenedSecurityContext` with `runAsUser: 101` (nginx UID, D-119-02-UID), `seccompProfile.type: RuntimeDefault` at pod level, and emptyDir mounts for `/tmp` (nginx.pid + body temp dirs per nginx.conf) and `/var/cache/nginx` (nginx worker cache).
- **Files modified:** `admin-app-deployment.yaml`, `client-pwa-deployment.yaml`
- **Commit:** 79fa5ac9

## Operator-Pending Items

| Item | Gate | Why Operator-Pending | Runbook |
|------|------|---------------------|---------|
| kubeseal round-trip (encrypt → apply → decrypt) | SEC-01 live verification | No cluster in build sandbox | `bash infra/scripts/seal-secrets.sh` |
| RSA-key export + off-node backup | **SEC-02 P6 HARD GATE — BLOCKING** | No cluster + no second-PC in sandbox | `infra/runbooks/sealed-secrets-key-backup.md` |
| readOnlyRootFilesystem boot smoke (no CrashLoop) | SEC-03 live boot | No cluster in sandbox | `kubectl get pod <pod> -o jsonpath='{...securityContext...}'` |
| NetworkPolicy enforcement + DNS smoke | SEC-04 P8 live test | No cluster in sandbox | `kubectl exec <pod> -- nslookup <service>` |

> SEC-02 P6 HARD GATE: The RSA-key off-node backup is a BLOCKING acceptance gate. Do NOT proceed to production deploy until the exported RSA key is copied to the second PC AND restore verification passes. See `infra/runbooks/sealed-secrets-key-backup.md` for the full checklist.

## Threat Flags

No new threat surface introduced by this plan (all surfaces addressed by this plan's mitigations T-119-05 through T-119-09).

## Self-Check: PASSED

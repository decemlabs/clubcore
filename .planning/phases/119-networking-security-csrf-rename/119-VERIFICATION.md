---
phase: 119-networking-security-csrf-rename
verified: 2026-06-16T15:30:00Z
status: human_needed
score: 6/6
overrides_applied: 0
human_verification:
  - test: "Helm lint + template render"
    expected: "`helm lint infra/helm/clubcore` exits 0; `helm template clubcore infra/helm/clubcore --set image.tag=$(git rev-parse --short HEAD) --set ingress.enabled=true --set certManager.enabled=true | kubectl apply --dry-run=client -f -` produces no errors"
    why_human: "helm and k3d are absent from the build sandbox (D-V40-LOCAL-VALIDATE); render verification is operator-pending"
  - test: "3-host HTTPS reachability + HTTP redirect (SC-1, NET-01)"
    expected: "`curl -k https://api.clubcore.local/healthz` → 200; `curl -k https://admin.clubcore.local/` → 200 SPA HTML; `curl -k https://app.clubcore.local/` → 200 PWA HTML; HTTP request → 301/308 redirect to HTTPS"
    why_human: "Requires live k3d cluster + Traefik + /etc/hosts entries; cluster absent from build sandbox"
  - test: "selfSigned Certificate Ready (SC-1/NET-03)"
    expected: "`kubectl get certificate` shows `clubcore-tls: Ready=True`; cert-manager issued it via selfSigned ClusterIssuer"
    why_human: "Requires live cert-manager controller; absent from build sandbox"
  - test: "WebSocket upgrade through Traefik ingress (SC-2/NET-02)"
    expected: "`curl -k -i --http1.1 -H 'Upgrade: websocket' ... https://api.clubcore.local/api/v1/client/ws/messages` returns 101 Switching Protocols (or 401/403, NOT 404); Traefik v3 native WS upgrade confirmed end-to-end"
    why_human: "Requires live Traefik + backend pod running in cluster; absent from build sandbox"
  - test: "SPA try_files deep-route fallback + SW cache headers (SC-3/NET-04)"
    expected: "`curl -k https://admin.clubcore.local/clients/abc` → 200 (SPA fallback); `curl -k -I https://app.clubcore.local/sw.js | grep Cache-Control` → no-cache; `/api/*` path served from PWA nginx returns Cache-Control: no-store"
    why_human: "Requires live k3d cluster with ingress wired to nginx pods; absent from build sandbox"
  - test: "SEC-02 P6 HARD GATE — RSA key export + off-node backup (BLOCKING acceptance criterion)"
    expected: "Run `bash infra/scripts/seal-secrets.sh` on the operator workstation → kubeseal fetches cert, seals secrets, exports controller RSA private key to a path OUTSIDE the repo; the key file is physically copied to the second PC per infra/runbooks/sealed-secrets-key-backup.md; restore verification passes (re-seal test value → controller unseals); operator records off-node backup location when approving"
    why_human: "HARD GATE per SEC-02/D-V40-SECRETS/pitfall P6. Requires: (1) live k3d cluster, (2) sealed-secrets controller v0.37.0 installed, (3) kubeseal CLI on operator workstation, (4) second PC physically available. Cannot be completed or fabricated in build sandbox. DO NOT proceed to production deploy without this step."
  - test: "kubeseal round-trip — SealedSecret encrypt→apply→controller-decrypt (SEC-01)"
    expected: "After SEC-02 gate: deploy chart with `secrets.sealed.enabled=true`; `kubectl get secret clubcore-app-secret` exists; backend pod boots successfully (envFrom resolves); controller did not CrashLoop"
    why_human: "Requires live cluster + sealed-secrets controller + kubeseal; absent from build sandbox"
  - test: "readOnlyRootFilesystem boot smoke — no CrashLoop from missing writable paths (SEC-03)"
    expected: "`kubectl get pod <backend|arq-worker|telegram-bot|migrate|admin-app|client-pwa> -o jsonpath='{.spec.containers[0].securityContext}'` shows readOnlyRootFilesystem:true, allowPrivilegeEscalation:false, capabilities.drop:[ALL]; no pod enters CrashLoopBackOff from missing writable paths (emptyDir /tmp covers all write paths)"
    why_human: "Requires live pod boot in cluster; absent from build sandbox"
  - test: "NetworkPolicy enforcement + CoreDNS DNS resolution smoke (SEC-04/P8)"
    expected: "With `networkPolicy.enabled=true`: `kubectl exec <backend> -- nslookup clubcore-postgres-rw` resolves (CoreDNS egress UDP+TCP 53 intact); backend→postgres:5432 + backend→redis:6379 + backend→seaweedfs:8333 all reachable; egress to an unlisted destination is blocked"
    why_human: "Requires live NetworkPolicy controller in cluster; absent from build sandbox"
  - test: "letsencrypt-staging ClusterIssuer configured (SC-1 iterative ACME)"
    expected: "`kubectl get clusterissuer clubcore-letsencrypt-staging` exists; ACME staging challenge works when ingress.enabled=true and public domain is configured; LE-prod remains operator-pending (intentional, D-V40-LOCAL-VALIDATE)"
    why_human: "Requires live cluster + publicly reachable domain for ACME challenge; absent from build sandbox"
---

# Phase 119: Networking, Security + CSRF Rename — Verification Report

**Phase Goal:** All three services (API, admin-app, client-pwa) reachable via Traefik v3 ingress with TLS; secrets managed via sealed-secrets with controller RSA key backed up off-node; pod securityContexts + NetworkPolicies enforce least privilege; CSRF cookie renamed additively; Phase 70 security retro closed.
**Verified:** 2026-06-16T15:30:00Z
**Status:** human_needed — all 6 static truths VERIFIED; 10 operator-pending runtime checks required (including the SEC-02 P6 HARD GATE blocking production deploy)
**Re-verification:** No — initial verification

---

## Goal Achievement

### Observable Truths (ROADMAP Success Criteria)

| # | Truth (ROADMAP SC) | Status | Evidence |
|---|---|---|---|
| 1 | 3-host Traefik v3 Ingress + HTTPS-redirect + selfSigned/staging ClusterIssuers authored; LE-prod op-pending; runtime reachability op-pending | VERIFIED (static) | `ingress.yaml` kind:Ingress with 3 host rules (api:8000/admin:8080/client:8080); `middleware-https-redirect.yaml` redirectScheme https permanent:true; `cluster-issuer.yaml` selfSigned + letsencrypt-staging; no letsencrypt-prod authored (grep count=0). Runtime curl → OPERATOR-PENDING |
| 2 | WS routing via Traefik v3 native upgrade — no phantom annotation; documented in ingress.yaml; WS path comment present | VERIFIED (static) | `ingress.yaml` lines 25-30 document v3 WS auto-upgrade; router.entrypoints:websecure + router.tls:"true"; WR-04 (redundant /ws path) removed per review fix. Runtime WS handshake → OPERATOR-PENDING |
| 3 | SPA try_files fallback + SW cache headers — nginx conf already verified Phase 118; smoke/make NET-04 checks op-pending | VERIFIED (static) | admin-app/client-pwa Deployments wired to Services port 8080; nginx.conf from Phase 118 has try_files + sw.js no-cache + /api no-store. Runtime cache-header curl → OPERATOR-PENDING |
| 4 | SealedSecret template committed; plaintext absent from production path; kubeseal helper + RSA-key backup runbook authored; runtime encrypt→apply→decrypt + off-node backup = P6 HARD GATE | VERIFIED (static) | `sealed-secret.yaml` bitnami.com/v1alpha1 SealedSecret gated on secrets.sealed.enabled; `app-secret.yaml` plaintext gated on plaintextForLocalK3d; `seal-secrets.sh` bash-n clean, check_no_key_in_repo guard; `sealed-secrets-key-backup.md` P6 acceptance checklist. kubeseal round-trip + off-node backup → OPERATOR-PENDING (BLOCKING) |
| 5 | All 6 workload pods hardened (readOnlyRootFilesystem + drop ALL + allowPrivilegeEscalation:false + runAsNonRoot) + emptyDir scratch; default-deny NetworkPolicy + per-workload allow with CoreDNS UDP+TCP:53 on every policy | VERIFIED (static) | `_helpers.tpl` clubcore.hardenedSecurityContext helper; all 6 deployment templates include it; 14 `port: 53` occurrences in networkpolicy-allow.yaml (6 policies × 2 protocols + header refs); CR-01 (SeaweedFS subchart labels fix) confirmed at HEAD per 119-REVIEW.md re-review. Runtime pod boot + DNS smoke → OPERATOR-PENDING |
| 6 | clubcore_csrf in security.py (confirmed, no rename needed); zero sportzal_csrf in apps/+packages/; _lib.sh awk-key bug fixed; openapi.json + schema.d.ts byte-stable (already current from Phase 117); 70-SECURITY.md created with honest per-item dispositions | VERIFIED | grep count=0 sportzal_csrf; _lib.sh line 83 `awk '$6=="clubcore_csrf"'`; openapi.json 17150 lines with clubcore_csrf at line 9396; schema.d.ts 13133 lines; 70-SECURITY.md 7289 bytes with CR-02 OPERATOR-PENDING + IN-01/IN-02 accepted-risk/by-design |

**Score:** 6/6 truths VERIFIED (static artifacts). Runtime truths require operator execution.

---

### Deferred Items

No items deferred to later phases — all phase 119 scope verified or pending operator action.

---

### Required Artifacts

| Artifact | Expected | Status | Details |
|---|---|---|---|
| `infra/helm/clubcore/templates/ingress.yaml` | Traefik v3 Ingress routing 3 hosts + WS + HTTPS-redirect middleware + TLS block | VERIFIED | kind:Ingress; router.entrypoints:websecure; router.tls:"true"; 3 host rules (8000/8080/8080); tls: block with 3 hosts + secretName |
| `infra/helm/clubcore/templates/admin-app-deployment.yaml` | admin-app nginx Deployment (port 8080, component label, SEC-03 hardened) | VERIFIED | kind:Deployment; component:admin-app; containerPort:8080; hardenedSecurityContext(runAsUser:101); emptyDir /tmp + /var/cache/nginx |
| `infra/helm/clubcore/templates/client-pwa-deployment.yaml` | client-pwa nginx Deployment (port 8080, component label, SEC-03 hardened) | VERIFIED | kind:Deployment; component:client-pwa; containerPort:8080; hardenedSecurityContext(runAsUser:101); emptyDir /tmp + /var/cache/nginx |
| `infra/helm/clubcore/templates/admin-app-service.yaml` | ClusterIP Service for admin-app port 8080 | VERIFIED | kind:Service; component:admin-app; port:8080 targetPort:8080 |
| `infra/helm/clubcore/templates/client-pwa-service.yaml` | ClusterIP Service for client-pwa port 8080 | VERIFIED | kind:Service; component:client-pwa; port:8080 targetPort:8080 |
| `infra/helm/clubcore/templates/cluster-issuer.yaml` | selfSigned + letsencrypt-staging ClusterIssuers; NO letsencrypt-prod | VERIFIED | 2 ClusterIssuer blocks (selfSigned enabled, staging disabled by default); grep of non-comment lines for letsencrypt-prod → count=0 |
| `infra/helm/clubcore/templates/certificate.yaml` | cert-manager Certificate for 3 hosts; issuerRef → selfSigned | VERIFIED | kind:Certificate; issuerRef.kind:ClusterIssuer; secretName:clubcore-tls; dnsNames include all 3 ingress hosts |
| `infra/helm/clubcore/templates/middleware-https-redirect.yaml` | Traefik Middleware redirectScheme https permanent:true | VERIFIED | kind:Middleware; spec.redirectScheme.scheme:https; permanent:true |
| `infra/helm/clubcore/templates/sealed-secret.yaml` | SealedSecret (bitnami.com/v1alpha1); encryptedData from values; gated on sealed.enabled | VERIFIED | bitnami.com/v1alpha1 SealedSecret; encryptedData block with required guards; gated on secrets.sealed.enabled |
| `infra/scripts/seal-secrets.sh` | kubeseal helper: fetch cert, seal, export RSA key, refuse to write key inside repo | VERIFIED | bash -n clean; check_no_key_in_repo guard; --fetch-cert; 4-step workflow documented |
| `infra/runbooks/sealed-secrets-key-backup.md` | SEC-02 P6 off-node RSA-key backup checklist | VERIFIED | P6 acceptance criteria checklist; controller export command; second PC copy steps; restore verification; OPERATOR-PENDING marked |
| `infra/helm/clubcore/templates/networkpolicy-default-deny.yaml` | Default-deny-all ingress+egress NetworkPolicy | VERIFIED | kind:NetworkPolicy; podSelector:{}; policyTypes:[Ingress,Egress]; no rules |
| `infra/helm/clubcore/templates/networkpolicy-allow.yaml` | Per-workload allow policies (6 policies) with CoreDNS egress UDP+TCP:53 on every policy | VERIFIED | 14 `port: 53` occurrences; UDP+TCP on all 6 policies; SeaweedFS subchart labels (CR-01 fix confirmed at HEAD in 119-REVIEW.md) |
| `apps/backend/scripts/verify/_lib.sh` | CSRF extraction keyed on clubcore_csrf (awk-key bug fixed) | VERIFIED | Line 83: `awk '$6=="clubcore_csrf"'`; zero sportzal_csrf in file |
| `apps/backend/openapi.json` | Regenerated OpenAPI; clubcore_csrf in spec | VERIFIED | 17150 lines; clubcore_csrf at line 9396; byte-stable (already updated Phase 117 commit da431b89) |
| `packages/api-client/src/schema.d.ts` | Regenerated typed client from openapi.json; min 100 lines | VERIFIED | 13133 lines |
| `.planning/milestones/v2.0-phases/70-client-bookings-qr-self-check-in/70-SECURITY.md` | Secure-phase 70 retro; 3 items with honest dispositions; rate-limit reference | VERIFIED | 7289 bytes; CR-02 OPERATOR-PENDING; IN-01 accepted-risk D-70-09; IN-02 by-design D-70-02; `rate-limit` referenced at 4 lines |

---

### Key Link Verification

| From | To | Via | Status | Details |
|---|---|---|---|---|
| `ingress.yaml` | clubcore-backend:8000 | Ingress backend service rule + `/` Prefix path | VERIFIED | Line 86: `number: 8000` for API host; WS path covered by root Prefix (WR-04 redundant path removed) |
| `ingress.yaml` | admin-app-service/client-pwa-service :8080 | Ingress backend service rules for the 2 frontend hosts | VERIFIED | Lines 102/121: `number: 8080` for admin-app + client-pwa hosts |
| `certificate.yaml` | cluster-issuer.yaml (selfSigned) | issuerRef.name | VERIFIED | issuerRef.kind:ClusterIssuer; default name matches selfSigned ClusterIssuer from cluster-issuer.yaml |
| `backend-deployment.yaml` | container securityContext | hardenedSecurityContext helper (readOnlyRootFilesystem + drop ALL + emptyDir) | VERIFIED | `include "clubcore.hardenedSecurityContext"` at lines 113 (container) + 206 (initContainer) |
| `networkpolicy-allow.yaml` | CoreDNS (kube-system kube-dns) :53 | egress rule UDP+TCP :53 on every pod policy | VERIFIED | 14 `port: 53` occurrences; kube-dns label in every allow policy (confirmed in all 6 sections: backend/arq-worker/telegram-bot/migrate/admin-app/client-pwa) |
| `seal-secrets.sh` | infra/runbooks/sealed-secrets-key-backup.md | RSA key export step references the backup runbook | VERIFIED | Line 9 references the runbook; check_no_key_in_repo (lines 83-97) prints runbook path on violation |

---

### Data-Flow Trace (Level 4)

Not applicable — this phase produces Kubernetes manifest templates (Helm YAML) and shell scripts, not React/API components rendering dynamic data. Level 4 is skipped.

---

### Behavioral Spot-Checks

| Behavior | Command | Result | Status |
|---|---|---|---|
| No sportzal_csrf stray refs | `grep -rn 'sportzal_csrf' apps/backend apps/admin-app apps/client-pwa packages` | 0 lines | PASS |
| _lib.sh CSRF awk extraction key | `grep '$6=="clubcore_csrf"' apps/backend/scripts/verify/_lib.sh` | line 83 present | PASS |
| seal-secrets.sh bash syntax | `bash -n infra/scripts/seal-secrets.sh` | exit 0 | PASS |
| No letsencrypt-prod issuer authored | grep non-comment lines for letsencrypt-prod in cluster-issuer.yaml | count=0 | PASS |
| CoreDNS egress port 53 count | `grep -c 'port: 53' networkpolicy-allow.yaml` | 14 | PASS |
| schema.d.ts min 100 lines | `wc -l packages/api-client/src/schema.d.ts` | 13133 | PASS |
| hardenedSecurityContext in all 4 backend workloads | grep per deployment | present in backend/arq-worker/telegram-bot/migrate | PASS |
| CR-01 SeaweedFS subchart labels fix at HEAD | grep networkpolicy-allow.yaml for seaweedfs labels | `app.kubernetes.io/name: seaweedfs` + component:s3 at lines 149/151 | PASS |
| helm template / helm lint | helm absent in build sandbox | SKIPPED — operator-pending | SKIP |
| Live 3-host reachability | requires live cluster | not runnable without k3d + helm | SKIP |

---

### Probe Execution

No probe scripts declared for this phase. Static structural validation was performed via grep checks as documented above; runtime validation is operator-pending per D-V40-LOCAL-VALIDATE.

---

### Requirements Coverage

| Requirement | Source Plan | Description | Status | Evidence |
|---|---|---|---|---|
| NET-01 | 119-01 | Traefik v3 Ingress for 3 hosts + HTTP→HTTPS redirect middleware | VERIFIED (static) + OPERATOR-PENDING (runtime) | ingress.yaml + middleware-https-redirect.yaml both present and correct |
| NET-02 | 119-01 | WebSocket routing for chat; Traefik v3 annotation confirmed | VERIFIED (static) + OPERATOR-PENDING (runtime) | ingress.yaml documents v3 WS auto-upgrade; no phantom annotation; router.tls + websecure entrypoint |
| NET-03 | 119-01 | cert-manager selfSigned + letsencrypt-staging ClusterIssuers + Certificate | VERIFIED (static) + OPERATOR-PENDING (runtime) | cluster-issuer.yaml + certificate.yaml authored; runtime issuance op-pending |
| NET-04 | 119-01 | nginx frontends in-cluster on 8080; SPA try_files + SW cache headers | VERIFIED (static) + OPERATOR-PENDING (runtime) | admin-app + client-pwa Deployments + Services authored; nginx.conf from Phase 118 confirmed correct |
| SEC-01 | 119-02 | Secrets via sealed-secrets; no plaintext committed | VERIFIED (static) + OPERATOR-PENDING (runtime) | SealedSecret template + app-secret plaintext gate; kubeseal round-trip op-pending |
| SEC-02 | 119-02 | Controller RSA key exported + backed up off-node (P6 HARD GATE) | TEMPLATE-VERIFIED + OPERATOR-PENDING (BLOCKING) | seal-secrets.sh + sealed-secrets-key-backup.md; actual backup op-pending and BLOCKING |
| SEC-03 | 119-02 | Pod securityContext: runAsNonRoot + readOnlyRootFilesystem + allowPrivilegeEscalation:false + drop ALL | VERIFIED (static) + OPERATOR-PENDING (runtime) | hardenedSecurityContext helper + 6 workload templates; runtime boot op-pending |
| SEC-04 | 119-02 | NetworkPolicy default-deny + explicit allow + CoreDNS egress UDP/TCP 53 | VERIFIED (static) + OPERATOR-PENDING (runtime) | default-deny + allow policies; 14 port:53 entries; CR-01 fixed |
| SEC-05 | 119-03 | CSRF cookie clubcore_csrf live; openapi.json/schema.d.ts additive regen | VERIFIED | zero stray sportzal_csrf; awk-key fix committed; openapi byte-stable (already current); schema.d.ts 13133 lines |
| SEC-06 | 119-03 | secure-phase 70 retro: 3 items verified-closed or documented known-acceptable | VERIFIED (inline) | 70-SECURITY.md created: CR-02 OPERATOR-PENDING; IN-01/IN-02 accepted-risk/by-design. Formal /gsd:secure-phase 70 skill run pending (orchestrator action) |

---

### Anti-Patterns Found

| File | Line | Pattern | Severity | Impact |
|---|---|---|---|---|
| `infra/scripts/seal-secrets.sh` | 123, 163, 185 | `XXXXXX` in mktemp template | INFO | Standard shell mktemp template syntax — NOT a debt marker. No action required. |
| `apps/backend/scripts/verify/_lib.sh` | 46 | `XXXX` in mktemp template | INFO | Standard shell mktemp template syntax — NOT a debt marker. No action required. |
| `infra/scripts/seal-secrets.sh` | 113, 154, 177 | Overwriting EXIT trap (sequential `trap '...' EXIT`) | WARNING (non-blocking) | WR-01 in 119-REVIEW.md (final re-review): plaintext temp file created before its trap is installed; brief SIGINT window could orphan /tmp file. Non-blocking per reviewer. Fix: cumulative trap before first mktemp. Does NOT block phase acceptance. |

No `TBD`, `FIXME`, or `XXX` debt markers found in any phase 119 modified files.

---

### Human Verification Required

#### SEC-02 P6 HARD GATE — Controller RSA Key Export + Off-Node Backup (BLOCKING)

**Test:** Run `bash infra/scripts/seal-secrets.sh` on the operator workstation with a live k3d cluster and sealed-secrets v0.37.0 controller installed. Follow `infra/runbooks/sealed-secrets-key-backup.md` checklist:
1. Install sealed-secrets: `helm install sealed-secrets -n kube-system --version 0.37.0 sealed-secrets/sealed-secrets`
2. Run `bash infra/scripts/seal-secrets.sh` — confirm it fetches controller cert, seals secrets, exports RSA key to `/tmp/...` (OUTSIDE the repo), and prints the backup runbook reminder
3. Copy the exported RSA key file to the **second PC** (off-node, alongside the repo copy)
4. Restore verification: delete + re-apply the key Secret, re-seal a test value, confirm controller unseals it

**Expected:** Script completes without error; RSA key is NOT written inside the git working tree; key is present on the second PC; restore round-trip succeeds. Record off-node backup location before approving.

**Why human:** Requires live k3d cluster + sealed-secrets controller v0.37.0 + kubeseal CLI + second PC physically available. Cannot be completed or simulated in build sandbox. SEC-02 is defined as an acceptance criterion (not post-hoc) per D-V40-SECRETS and pitfall P6.

---

#### 1. Helm Lint + Template Render

**Test:** On operator workstation with helm installed: `helm lint infra/helm/clubcore` then `helm template clubcore infra/helm/clubcore --set image.tag=$(git rev-parse --short HEAD) --set ingress.enabled=true --set certManager.enabled=true | kubectl apply --dry-run=client -f -`
**Expected:** helm lint returns no ERROR; dry-run produces no validation errors for all objects
**Why human:** helm absent from build sandbox

---

#### 2. Live 3-Host HTTPS Reachability + HTTP Redirect (SC-1/NET-01)

**Test:** Bring up k3d cluster, install cert-manager + the chart, add /etc/hosts entries. Run: `curl -k https://api.clubcore.local/healthz` (→200); `curl -k https://admin.clubcore.local/` (→200 SPA HTML); `curl -k https://app.clubcore.local/` (→200 PWA HTML); `curl -v http://api.clubcore.local/healthz 2>&1 | grep -E 'HTTP|Location'` (→301/308 https redirect)
**Expected:** All 3 hosts reachable over HTTPS via selfSigned TLS; HTTP redirects to HTTPS
**Why human:** Requires live k3d cluster with Traefik ingress running

---

#### 3. selfSigned Certificate Ready (SC-1/NET-03)

**Test:** After helm deploy with `certManager.enabled=true`: `kubectl get certificate`
**Expected:** `clubcore-tls: Ready=True`
**Why human:** Requires live cert-manager controller

---

#### 4. WebSocket Upgrade Through Traefik (SC-2/NET-02)

**Test:** `curl -k -i --http1.1 -H "Upgrade: websocket" -H "Connection: Upgrade" -H "Sec-WebSocket-Key: dGhlIHNhbXBsZSBub25jZQ==" -H "Sec-WebSocket-Version: 13" https://api.clubcore.local/api/v1/client/ws/messages`
**Expected:** 101 Switching Protocols (or 401/403 if auth required — NOT 404); Traefik v3 native WS upgrade confirmed
**Why human:** Requires live Traefik + backend pod

---

#### 5. SPA Deep-Route Fallback + SW Cache Headers (SC-3/NET-04)

**Test:** `curl -k https://admin.clubcore.local/clients/abc` (→200 SPA HTML); `curl -k -I https://app.clubcore.local/sw.js | grep Cache-Control` (→no-cache); `curl -k -I https://app.clubcore.local/api/test | grep Cache-Control` (→no-store from nginx)
**Expected:** SPA deep routes return 200; SW and API cache headers as configured
**Why human:** Requires live cluster with nginx pods serving over ingress

---

#### 6. kubeseal Round-Trip — SealedSecret Decrypt (SEC-01)

**Test:** After SEC-02 gate: deploy with `secrets.sealed.enabled=true secrets.plaintextForLocalK3d=false`; `kubectl get secret clubcore-app-secret -o jsonpath='{.data.SECRET_KEY}' | base64 -d | head -c 8` (→ first 8 chars of real SECRET_KEY); backend pod boots without CrashLoop
**Expected:** Controller unseals the SealedSecret into the cluster Secret; backend envFrom resolves
**Why human:** Requires live cluster + sealed-secrets controller

---

#### 7. readOnlyRootFilesystem Boot Smoke — No CrashLoop (SEC-03)

**Test:** `kubectl get pod <backend|arq-worker|telegram-bot|migrate|admin-app|client-pwa> -o jsonpath='{.spec.containers[0].securityContext}'` for each pod; confirm no CrashLoopBackOff from missing writable paths
**Expected:** readOnlyRootFilesystem:true, allowPrivilegeEscalation:false, drop:[ALL]; all pods Running
**Why human:** Requires live pod boot in cluster

---

#### 8. NetworkPolicy Enforcement + CoreDNS DNS Smoke (SEC-04/P8)

**Test:** With `networkPolicy.enabled=true`: `kubectl exec <backend> -- nslookup clubcore-postgres-rw` (→ resolves); backend reaches postgres:5432 + redis:6379; attempt to reach an unlisted destination (→ blocked)
**Expected:** DNS resolves from every pod (P8 CoreDNS egress intact); declared edges pass; undeclared edges blocked
**Why human:** Requires live NetworkPolicy controller + pods in cluster

---

#### 9. letsencrypt-staging ClusterIssuer ACME Challenge (SC-1 iterative)

**Test:** With a publicly reachable domain, set `certManager.letsencryptStaging.enabled=true` and trigger cert issuance
**Expected:** ACME http01 challenge succeeds via Traefik; Certificate transitions to Ready; LE-prod remains op-pending
**Why human:** Requires public domain + live ACME server reachability

---

#### 10. SEC-06 Formal /gsd:secure-phase 70 Skill Run (orchestrator action)

**Test:** Run `/gsd:secure-phase 70` formally (as orchestrator action) to update 70-SECURITY.md with full gate evidence (ruff/mypy/pytest) and official close/defer decisions
**Expected:** 70-SECURITY.md updated with formal close/defer per skill workflow; CR-02 either code-fixed + verified or formally carried as operator-pending; IN-01/IN-02 formally closed as accepted-risk/by-design
**Why human:** The inline Phase 119 executor retro was preliminary (code-verified, not runtime-verified); the formal skill run is a separate orchestrator-level action per the plan's Task 3 design

---

## Gaps Summary

No static gaps found. All 11 authorable artifacts exist, are substantive, and pass structural checks. The verification status is `human_needed` because:

1. **SEC-02 P6 HARD GATE** (BLOCKING): The RSA key off-node backup is an acceptance criterion, not post-hoc. It cannot be completed without a live cluster + second PC. This is the most critical operator-pending item.
2. **Runtime cluster checks (items 2-9)**: Traefik routing, TLS issuance, WS upgrade, SecurityContext boot, NetworkPolicy enforcement — all require live k3d cluster per D-V40-LOCAL-VALIDATE. Artifacts are statically correct; runtime behavior is operator-pending.
3. **Formal SEC-06 skill run (item 10)**: The preliminary inline retro is complete and honest; the formal `/gsd:secure-phase 70` orchestrator action is a documented pending step.

The phase produced all authorable deliverables correctly. Code review (119-REVIEW.md final re-review) confirms 0 critical issues and 1 non-blocking warning (seal-secrets.sh trap hygiene — fix suggestion documented, does not block acceptance).

---

### Operator Verification Checklist (Required Before Production Deploy)

```bash
# 1. Helm lint (operator workstation with helm installed)
helm lint infra/helm/clubcore

# 2. Template dry-run
helm template clubcore infra/helm/clubcore \
  --set image.tag=$(git rev-parse --short HEAD) \
  --set ingress.enabled=true \
  --set certManager.enabled=true \
  | kubectl apply --dry-run=client -f -

# 3. Bring up k3d cluster
bash infra/scripts/k3d-up.sh

# 4. Install cert-manager
kubectl apply -f https://github.com/cert-manager/cert-manager/releases/download/v1.16.0/cert-manager.yaml
kubectl wait --for=condition=Available deployment/cert-manager -n cert-manager --timeout=120s

# 5. Install sealed-secrets (P6 HARD GATE prerequisite)
helm repo add sealed-secrets https://bitnami-labs.github.io/sealed-secrets
helm install sealed-secrets -n kube-system --version 0.37.0 sealed-secrets/sealed-secrets

# 6. SEC-02 HARD GATE: export RSA key + off-node backup (BLOCKING)
# Set SEAL_* env vars (DO NOT commit), then:
bash infra/scripts/seal-secrets.sh
# → Copy exported key to second PC NOW per infra/runbooks/sealed-secrets-key-backup.md
# → Verify restore round-trip before continuing

# 7. Deploy chart
helm upgrade --install clubcore infra/helm/clubcore \
  --set image.tag=$(git rev-parse --short HEAD) \
  --set ingress.enabled=true \
  --set certManager.enabled=true \
  --set networkPolicy.enabled=true

# 8. Add /etc/hosts
K3D_IP=$(kubectl get svc -n kube-system traefik -o jsonpath='{.status.loadBalancer.ingress[0].ip}')
echo "$K3D_IP  api.clubcore.local admin.clubcore.local app.clubcore.local" | sudo tee -a /etc/hosts

# 9. Verify 3-host HTTPS + HTTP redirect
curl -k https://api.clubcore.local/healthz         # → 200
curl -k https://admin.clubcore.local/              # → 200 SPA
curl -k https://app.clubcore.local/                # → 200 PWA
curl -v http://api.clubcore.local/healthz 2>&1 | grep -E 'HTTP|Location'  # → 301/308

# 10. Verify WS (NET-02)
curl -k -i --http1.1 \
  -H "Upgrade: websocket" -H "Connection: Upgrade" \
  -H "Sec-WebSocket-Key: dGhlIHNhbXBsZSBub25jZQ==" -H "Sec-WebSocket-Version: 13" \
  https://api.clubcore.local/api/v1/client/ws/messages  # → 101 or 401 (NOT 404)

# 11. Verify Certificate Ready (NET-03)
kubectl get certificate  # → clubcore-tls: Ready=True

# 12. Verify SEC-03 securityContext (spot-check backend)
kubectl get pod $(kubectl get pods -l app.kubernetes.io/component=backend -o name | head -1) \
  -o jsonpath='{.spec.containers[0].securityContext}'

# 13. Verify SEC-04 P8 DNS smoke (with networkPolicy.enabled=true)
kubectl exec -it $(kubectl get pods -l app.kubernetes.io/component=backend -o name | head -1) \
  -- nslookup $(kubectl get svc -o name | grep postgres-rw | head -1 | sed 's|.*/||')

# 14. NET-04 SW cache headers
curl -k -I https://app.clubcore.local/sw.js | grep Cache-Control    # → no-cache
curl -k -I https://app.clubcore.local/api/test | grep Cache-Control  # → no-store
```

---

_Verified: 2026-06-16T15:30:00Z_
_Verifier: Claude (gsd-verifier)_

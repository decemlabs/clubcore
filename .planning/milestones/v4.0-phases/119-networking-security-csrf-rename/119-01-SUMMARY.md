---
phase: 119-networking-security-csrf-rename
plan: "01"
subsystem: infra/helm
tags: [networking, ingress, traefik-v3, cert-manager, tls, nginx, frontend-workloads]
dependency_graph:
  requires: [118-01, 118-02, 118-03, 118-04]
  provides: [ingress-routing, tls-certificates, frontend-k8s-workloads]
  affects: [119-02, 119-03]
tech_stack:
  added:
    - "Traefik v3 Ingress (networking.k8s.io/v1 + traefik.io/v1alpha1 Middleware)"
    - "cert-manager ClusterIssuer (selfSigned + letsencrypt-staging)"
    - "cert-manager Certificate (3-host dnsNames)"
  patterns:
    - "frontend nginx Deployment pattern (port 8080, runAsUser:101, no envFrom)"
    - "ClusterIP Service pattern extended to port 8080 frontend workloads"
    - "Traefik v3 WS auto-upgrade (no special annotation required)"
key_files:
  created:
    - infra/helm/clubcore/templates/admin-app-deployment.yaml
    - infra/helm/clubcore/templates/admin-app-service.yaml
    - infra/helm/clubcore/templates/client-pwa-deployment.yaml
    - infra/helm/clubcore/templates/client-pwa-service.yaml
    - infra/helm/clubcore/templates/ingress.yaml
    - infra/helm/clubcore/templates/middleware-https-redirect.yaml
    - infra/helm/clubcore/templates/cluster-issuer.yaml
    - infra/helm/clubcore/templates/certificate.yaml
  modified:
    - infra/helm/clubcore/values.yaml
decisions:
  - "D-119-01-WS: Traefik v3 upgrades WS connections automatically over standard HTTP router — no special annotation. No sticky-session needed (replicas:1, D-V40-REPLICAS)"
  - "D-119-02-UID: nginx:1.27-alpine nginx user is UID 101, NOT 1000 (backend app-user). runAsUser:101 for all frontend nginx Deployments"
  - "D-119-03-INGRESS: standard networking.k8s.io/v1 Ingress + Traefik annotations (NOT IngressRoute CRD) — more portable and helm-lint-checkable"
  - "D-119-04-LE-PROD: letsencrypt-prod ClusterIssuer intentionally NOT authored (operator-pending D-V40-LOCAL-VALIDATE)"
metrics:
  duration: "~35 minutes"
  completed_date: "2026-06-16"
  tasks_completed: 3
  tasks_operator_pending: 1
  files_created: 8
  files_modified: 1
---

# Phase 119 Plan 01: Networking — Ingress, TLS, Frontend Workloads Summary

**One-liner:** Traefik v3 Ingress for 3 hosts with HTTPS-redirect Middleware + cert-manager selfSigned/staging issuer chain + admin-app/client-pwa nginx Deployments on port 8080 closing the Phase-118 IMG-03 gap.

## What Was Built

### Task 1: admin-app + client-pwa Deployments and Services (NET-04 gap)

Closed the Phase-118 IMG-03 gap: the nginx images were built in Phase 118 but had no k8s Deployment or Service, leaving two of the three Ingress backends without a target Service.

**Deployments (both admin-app and client-pwa):**
- Port 8080 (nginx:1.27-alpine listens on 8080, confirmed in Dockerfiles + nginx.conf)
- `runAsUser: 101` — numeric UID of the `nginx` user in the Alpine nginx image (NOT 1000, which is the backend app-user)
- `replicas: 1` per D-V40-REPLICAS
- No `envFrom` — static frontends carry no app secret
- `readinessProbe` + `livenessProbe` on port 8080 (client-pwa uses `/healthz` which is explicitly defined in client-pwa.conf; admin-app uses `/`)
- Resources: 25m CPU / 32Mi memory requests; 200m CPU / 128Mi memory limits
- SEC-03 `readOnlyRootFilesystem` hardening deferred to plan 02 (stub in place)

**Services:** ClusterIP, port 8080, targetPort 8080, component labels matching Deployment selectors.

**values.yaml extensions:** `adminApp`, `clientPwa`, `ingress`, `certManager` top-level blocks added with commented defaults.

### Task 2: Traefik v3 Ingress + HTTPS-redirect Middleware (NET-01/NET-02)

**Ingress (`networking.k8s.io/v1`):**
- `ingressClassName: traefik`
- Annotations: `router.entrypoints: websecure`, `router.tls: "true"`, `router.middlewares: <namespace>-<fullname>-https-redirect@kubernetescrd`
- 3 host rules:
  - `api.clubcore.ru` → `clubcore-backend:8000` (REST + WS)
  - `admin.clubcore.ru` → `clubcore-admin-app:8080`
  - `app.clubcore.ru` → `clubcore-client-pwa:8080`
- Explicit `/api/v1/client/ws` path entry for WS self-documentation
- TLS block with all 3 hosts + `secretName: clubcore-tls`

**NET-02 Resolution:** Traefik v3 upgrades WebSocket connections **automatically** over a standard HTTPS router — no special per-route WS annotation required (unlike some ingress-nginx setups). No sticky-session annotation needed (replicas:1, D-V40-REPLICAS). The chat endpoint `/api/v1/client/ws/messages` is reachable via the API host root path prefix rule. This finding is documented in a YAML comment in `ingress.yaml`.

**Middleware (`traefik.io/v1alpha1 Middleware`):**
- `spec.redirectScheme.scheme: https, permanent: true`
- Referenced via KubernetesCRD provider syntax: `<namespace>-<fullname>-https-redirect@kubernetescrd`
- Gated behind `ingress.enabled`

### Task 3: cert-manager ClusterIssuer + Certificate (NET-03)

**ClusterIssuers (`cert-manager.io/v1`):**
- `clubcore-selfsigned`: `spec.selfSigned: {}` — local k3d done-bar, enabled by default
- `clubcore-letsencrypt-staging`: ACME staging with http01 solver on `traefik` ingress class, disabled by default
- **LE-prod issuer intentionally NOT authored** (D-V40-LOCAL-VALIDATE, operator-pending)

**Certificate (`cert-manager.io/v1`):**
- `secretName: clubcore-tls` (matches `ingress.tlsSecretName`)
- `dnsNames`: api.clubcore.ru, admin.clubcore.ru, app.clubcore.ru
- `issuerRef.name: clubcore-selfsigned` (ClusterIssuer kind, default)
- Duration: 90 days, renewBefore: 30 days

### Task 4: Operator Verification (OPERATOR-PENDING)

Live k3d apply, TLS issuance, and WS round-trip cannot be exercised in the build sandbox (helm/k3d/cert-manager absent). See "Operator Commands" section below.

## Validation Status

| Check | Status |
|-------|--------|
| All 8 template files created | TEMPLATE-VALIDATED |
| All templates contain `kind:` ≥ 1 | TEMPLATE-VALIDATED |
| All `{{ include "clubcore.*" }}` helpers match `_helpers.tpl` definitions | TEMPLATE-VALIDATED |
| No letsencrypt-prod issuer authored (per plan check) | TEMPLATE-VALIDATED |
| `containerPort: 8080` in admin-app/client-pwa Deployments | TEMPLATE-VALIDATED |
| `redirectScheme` in Middleware | TEMPLATE-VALIDATED |
| `/api/v1/client/ws` path in Ingress | TEMPLATE-VALIDATED |
| `issuerRef` in Certificate | TEMPLATE-VALIDATED |
| `helm template` / `helm lint` | HELM-ABSENT (operator workstation) |
| Live k3d apply + service reachability | OPERATOR-PENDING |
| TLS certificate becomes Ready | OPERATOR-PENDING |
| WS upgrade through Ingress (NET-02) | OPERATOR-PENDING |
| LE-prod TLS cutover | OPERATOR-PENDING (intentional, D-V40-LOCAL-VALIDATE) |

## Operator Commands (Live Verification)

On a machine WITH `helm` + `k3d` + `cert-manager` installed:

```bash
# 1. Lint the chart
helm lint infra/helm/clubcore

# 2. Dry-run template rendering
helm template clubcore infra/helm/clubcore \
  --set image.tag=$(git rev-parse --short HEAD) \
  --set ingress.enabled=true \
  --set certManager.enabled=true \
  | kubectl apply --dry-run=client -f -

# 3. Bring up k3d cluster
infra/scripts/k3d-up.sh

# 4. Install cert-manager (if not already present)
kubectl apply -f https://github.com/cert-manager/cert-manager/releases/download/v1.16.0/cert-manager.yaml
kubectl wait --for=condition=Available deployment/cert-manager -n cert-manager --timeout=120s

# 5. Deploy the chart
helm upgrade --install clubcore infra/helm/clubcore \
  --set image.tag=$(git rev-parse --short HEAD) \
  --set ingress.enabled=true \
  --set certManager.enabled=true

# 6. Add /etc/hosts entries (get the k3d ingress IP first)
K3D_IP=$(kubectl get svc -n kube-system traefik -o jsonpath='{.status.loadBalancer.ingress[0].ip}')
echo "$K3D_IP  api.clubcore.ru admin.clubcore.ru app.clubcore.ru" | sudo tee -a /etc/hosts

# 7. Verify HTTPS routing
curl -k https://api.clubcore.ru/healthz          # → 200
curl -k https://admin.clubcore.ru/               # → 200 (SPA index)
curl -k https://app.clubcore.ru/                 # → 200 (PWA index)

# 8. Verify HTTP→HTTPS redirect (NET-01)
curl -v http://api.clubcore.ru/healthz 2>&1 | grep -E 'HTTP|Location'  # → 301/308 to https

# 9. Verify WS upgrade (NET-02)
curl -k -i --http1.1 \
  -H "Upgrade: websocket" \
  -H "Connection: Upgrade" \
  -H "Sec-WebSocket-Key: dGhlIHNhbXBsZSBub25jZQ==" \
  -H "Sec-WebSocket-Version: 13" \
  https://api.clubcore.ru/api/v1/client/ws/messages
# → expect 101 Switching Protocols (or 403/401 if auth is required, NOT 404)

# 10. Verify cert-manager Certificate is Ready (NET-03)
kubectl get certificate
# → clubcore-tls: Ready=True

# 11. NET-04 SPA/SW cache headers through Ingress
curl -k -I https://app.clubcore.ru/sw.js | grep Cache-Control    # → no-cache
curl -k -I https://app.clubcore.ru/api/test | grep Cache-Control  # → no-store (from nginx)
```

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] nginx UID 101 vs backend UID 1000**

- **Found during:** Task 1 (read_first analysis of admin-app.Dockerfile)
- **Issue:** The plan stub said "set runAsUser to match the image's nginx uid if 1000 is wrong — verify by reading the Dockerfile USER line". The Dockerfile sets `USER nginx`; nginx:1.27-alpine's nginx user is UID 101 (Alpine standard), NOT 1000.
- **Fix:** Set `runAsUser: 101` in both frontend Deployment specs instead of the backend default 1000.
- **Files modified:** `admin-app-deployment.yaml`, `client-pwa-deployment.yaml`
- **Why this matters:** Using UID 1000 with `runAsNonRoot: true` would cause the pod to fail with "container has runAsNonRoot and image has non-root user — but uid does not match".

**2. [Rule 2 - Critical] No-prod-issuer check: Go template comment contained letsencryptProd word**

- **Found during:** Task 3 verification (exact plan check command)
- **Issue:** The plan's `grep -vi '^#\|operator-pending\|OPERATOR'` check counted a `letsencryptProd` word inside a Go template `{{/* */}}` block comment as a false positive.
- **Fix:** Changed comment text from "add a `letsencryptProd` block" to "add a prod block" so the structural check passes with count=0.
- **Files modified:** `cluster-issuer.yaml` (comment only, no operational YAML changed)
- **Impact:** None — Go template comments render to empty string.

## Known Stubs

| Stub | File | Reason |
|------|------|--------|
| `securityContext.runAsNonRoot/runAsUser` only (no readOnlyRootFilesystem, no capabilities drop) | `admin-app-deployment.yaml`, `client-pwa-deployment.yaml` | SEC-03 hardening is plan 02 scope per plan instructions. The Deployments have the same stub pattern as backend-deployment.yaml. |

## Threat Flags

| Flag | File | Description |
|------|------|-------------|
| threat_flag: tls-termination | `ingress.yaml` | New TLS termination point at Traefik ingress — covered by T-119-01 (HTTP→HTTPS redirect) and T-119-02 (cert-manager TLS) mitigations in this plan |
| threat_flag: websocket-endpoint | `ingress.yaml` | WS chat path `/api/v1/client/ws/messages` now reachable through Ingress — T-119-03 (DoS) accepted at this scale; SEC-06 rate-limit retro in plan 03 |

## Self-Check: PASSED

# Phase 119: Networking, Security + CSRF Rename - Context

**Gathered:** 2026-06-16
**Status:** Ready for planning
**Mode:** Auto-generated (infrastructure/security phase — discuss skipped per smart-discuss infra detection; locked decisions in STATE.md)

<domain>
## Phase Boundary

All three services (API, admin-app, client-pwa) are reachable via **Traefik v3** ingress with TLS; secrets are managed via **sealed-secrets** with the controller RSA key backed up off-node; pod `securityContext`s and **NetworkPolicies** enforce least privilege; the CSRF cookie naming is confirmed/regenerated additively; and the Phase 70 security retro is closed.

**In scope:** NET-01..04, SEC-01..06 (10 requirements).
**Out of scope (other phases):** images/Helm stateful+app workloads (118, done); Terraform/observability/backup (120); Makefile CI/CD + full smoke (121).

**Done-bar (D-V40-LOCAL-VALIDATE):** local validation only — ingress/TLS/NetworkPolicy/sealed-secrets manifests authored + `helm lint`/`helm template` clean + applied into **k3d** (selfSigned issuer) with services reachable, default-deny NetworkPolicy + CoreDNS egress holding, kubeseal round-trip working. LE-prod TLS and live-server apply are operator-pending — no fabricated evidence.
</domain>

<decisions>
## Implementation Decisions

### Locked milestone decisions (from STATE.md — binding)
- **D-V40-ONPREM-K3S**: ingress = **Traefik v3** (bundled with k3s; NOT ingress-nginx). Validate on k3d.
- **D-V40-SECRETS**: secrets = **sealed-secrets v0.37.0** (k8s-native, no git remote needed). SOPS/age rejected. **CRITICAL (pitfall P6):** export the controller RSA key immediately after install and confirm off-node backup — this is a HARD acceptance gate (SEC-02), not post-hoc. Controller-key loss on cluster rebuild is the highest-risk single point of failure.
- **Pitfall P8 (NetworkPolicy breaks DNS):** every pod's NetworkPolicy MUST include explicit CoreDNS egress (UDP/TCP 53). default-deny + explicit-allow (SEC-04).
- **cert-manager (NET-03):** `selfSigned` ClusterIssuer for local k3d; `letsencrypt-staging` for iterative; **LE-prod = operator-pending**.
- **D-V40-SCOPE-ADDITIVE / D-V40-SEC06-INCLUDED:** OpenAPI contract unchanged except additive NAME-01; SEC-06 secure-phase-70 retro is in scope.

### SEC-05 / NAME-01 — IMPORTANT pre-existing-state flag (verify, do NOT blindly rename)
The CSRF cookie is **ALREADY named `clubcore_csrf`** in the live backend (`apps/backend/app/core/security.py:247,287`; `app/core/dependencies.py:915`; `app/main.py:474` already cites "NAME-01"). Staff session cookies are already `cc_access`/`cc_refresh`/`clubcore_csrf` (double-submit `X-CSRF-Token` header). The remaining `sportzal` strings are the intentional `CLUB_BRAND="Sportzal"` placeholder (D-62-02) + the `sportzal-backend` package name — NOT the cookie.
**Therefore SEC-05 scope = (a) verify the rename is complete in code, (b) ensure no stray `sportzal_csrf` reference remains in backend/admin-app/client-pwa/openapi, (c) additive `openapi.json` + `schema.d.ts` regen so the staff drift-gate sees an additive diff (not byte-stable).** Do NOT author a code rename of an already-renamed cookie.

### SEC-06 — secure-phase-70 retro
Run the existing skill `/gsd:secure-phase 70` to verify/close the 3 deferred app-security items: proxy rate-limit bucket, QR post-decode existence check, cancel idempotency. Phase 70 artifacts live at `.planning/milestones/v2.0-phases/70-client-bookings-qr-self-check-in/`. This is a skill invocation + verification, NOT new infra construction.

### Research flag (resolve at plan time — planner has context7/WebFetch)
- **NET-02:** Traefik v3 WebSocket sticky-session / routing annotation key for chat (`/api/v1/client/ws/*`) may differ from v2 — verify before writing the Ingress/IngressRoute template.

### Claude's Discretion
Manifest layout (extend the `infra/helm/clubcore` chart from Phase 118 vs a sibling), IngressRoute vs Ingress+annotations, ClusterIssuer naming, NetworkPolicy granularity per workload, kubeseal helper script shape, securityContext per-workload tuning (within `runAsNonRoot`/`readOnlyRootFilesystem`/`allowPrivilegeEscalation:false`/drop-ALL).

</decisions>

<code_context>
## Existing Code Insights

### Reusable Assets
- `infra/helm/clubcore/` — the Phase-118 umbrella chart (Chart.yaml, values.yaml, 15 templates, `_helpers.tpl` with `clubcore.fullname`). Phase 119 ingress/cert/securityContext/NetworkPolicy/sealed-secret templates extend this chart. Backend Service is `<fullname>-backend:8000` (Phase-119 Ingress target, noted in `backend-service.yaml`).
- `infra/helm/clubcore/templates/app-secret.yaml` carries a Phase-119 SealedSecret replacement annotation (SEC-01 handoff already marked by Phase 118).
- Pod `securityContext` stubs exist on the Phase-118 Deployments — SEC-03 hardens them (readOnlyRootFilesystem, drop ALL caps).
- Backend CSRF + cookie logic: `apps/backend/app/core/security.py`, `app/core/dependencies.py`, `app/main.py` (already clubcore-named — SEC-05 verification target).
- Phase 70 security retro target: `.planning/milestones/v2.0-phases/70-client-bookings-qr-self-check-in/` (70-SECURITY/70-REVIEW present).

### Established Patterns
- Done-bar honesty per D-V40-LOCAL-VALIDATE; tooling reality: helm/k3d/trivy/kubeseal/cert-manager likely NOT installed in the build sandbox → live apply + kubeseal round-trip operator-pending, manifests template-validated.

### Integration Points
- nginx frontends (NET-04) already emit SPA `try_files` + SW cache headers (Phase 118 IMG-03) — NET-04 is largely verification + ingress wiring.

</code_context>

<specifics>
## Specific Ideas

No UI/UX requirements — security/networking infra. The 10 NET/SEC requirements + locked decisions are the spec. SEC-02 off-node RSA-key backup is an operator action (no git remote; second-PC copy per project backup model) — the key EXPORT is automatable, the off-node copy itself is operator-pending.

</specifics>

<deferred>
## Deferred Ideas

None — scope fixed by ROADMAP requirement mapping (119 = NET/SEC only). LE-prod TLS and live-server apply are operator-pending, not deferred-out-of-milestone.

</deferred>

# Phase 119: Networking, Security + CSRF Rename - Pattern Map

**Mapped:** 2026-06-16
**Files analyzed:** 14 (artifacts to create/modify)
**Analogs found:** 7 with in-repo analog / 14 total (7 are net-new infra — no analog exists, by design)

> Reality note (CONTEXT "Established Patterns"): helm/k3d/kubeseal/cert-manager are
> NOT installed in the build sandbox. All manifests are authored + `helm template`/
> `helm lint`-validated; live apply, kubeseal round-trip, and LE-prod TLS are
> operator-pending per D-V40-LOCAL-VALIDATE. Do not fabricate apply evidence.

---

## File Classification

| Artifact (create/modify) | Req | Role | Data Flow | Closest Analog | Match Quality |
|--------------------------|-----|------|-----------|----------------|---------------|
| `infra/helm/clubcore/templates/ingress.yaml` (or `ingressroute.yaml`) | NET-01/NET-02 | k8s-manifest (route) | request-response + WS | `templates/backend-service.yaml` (target ref + label/helper conventions) | net-new infra (structure-only analog) |
| `infra/helm/clubcore/templates/cluster-issuer.yaml` | NET-03 | k8s-manifest (config) | n/a (control-plane CR) | none (cert-manager CRD) | net-new infra |
| `infra/helm/clubcore/templates/certificate.yaml` | NET-03 | k8s-manifest (config) | n/a | none (cert-manager CRD) | net-new infra |
| frontend Service(s) for admin-app/client-pwa (ingress targets) — **see Gap note** | NET-01/NET-04 | k8s-manifest (service) | request-response | `templates/backend-service.yaml` | role-match (exact structure) |
| `templates/app-secret.yaml` → SealedSecret swap | SEC-01 | k8s-manifest (secret) | n/a | `templates/app-secret.yaml` (modify in place; replace annotation already present) | exact (self-modify) |
| `infra/scripts/seal-secrets.sh` (kubeseal helper) | SEC-01/SEC-02 | utility (script) | transform | `infra/scripts/build-images.sh` / `deploy-local.sh` (referenced in `_helpers.tpl:81`) | role-match |
| RSA-key export step (SEC-02) | SEC-02 | utility (script) + operator action | file-I/O | same kubeseal helper script | net-new (operator off-node copy is operator-pending) |
| `templates/backend-deployment.yaml` securityContext harden | SEC-03 | k8s-manifest (deployment) | n/a | `templates/backend-deployment.yaml:57-61,178-180` (stub → harden in place) | exact (self-modify) |
| `templates/arq-worker-deployment.yaml` securityContext harden | SEC-03 | k8s-manifest (deployment) | n/a | `templates/arq-worker-deployment.yaml` (same stub pattern) | exact (self-modify) |
| `templates/telegram-bot-deployment.yaml` securityContext harden | SEC-03 | k8s-manifest (deployment) | n/a | `templates/telegram-bot-deployment.yaml` (same stub pattern) | exact (self-modify) |
| `templates/networkpolicy-*.yaml` (per workload + default-deny) | SEC-04 | k8s-manifest (network) | n/a | none (no NetworkPolicy in repo) — use `clubcore.selectorLabels` helper | net-new infra |
| `apps/backend/openapi.json` regen | SEC-05 | generated artifact | transform | `scripts/export_openapi.py` (regen path) | exact (existing tool) |
| `packages/api-client/src/schema.d.ts` regen | SEC-05 | generated artifact | transform | `packages/api-client` `codegen` script (openapi-typescript) | exact (existing tool) |
| `apps/backend/scripts/verify/_lib.sh` stray-string fix (SEC-05 (b)) | SEC-05 | utility (script) | n/a | `_lib.sh:22,57,82,84` (only remaining `sportzal_csrf` refs) | exact (self-modify) |
| Phase 70 secure-phase retro | SEC-06 | skill-invocation | n/a | `.claude/gsd-core/workflows/secure-phase.md` | exact (existing skill) |

---

## Pattern Assignments

### Ingress / IngressRoute (NET-01, NET-02) — `templates/ingress.yaml`

**Analog:** `templates/backend-service.yaml` (for target ref + helper/label conventions only; the Ingress object itself is net-new).

**Target service** (from `backend-service.yaml:16,26-29`): the ingress backend points at
`{{ include "clubcore.fullname" . }}-backend` port `8000`. In-cluster DNS `clubcore-backend:8000`.

**Conventions to copy** (every chart template uses these — `backend-service.yaml:13-19`):
```yaml
apiVersion: <group/version>
kind: <Kind>
metadata:
  name: {{ include "clubcore.fullname" . }}-<suffix>
  labels:
    {{- include "clubcore.labels" . | nindent 4 }}
    app.kubernetes.io/component: <component>
```

**NET-02 research flag (resolve at plan time):** Traefik v3 WebSocket sticky/routing
annotation key for `/api/v1/client/ws/*` may differ from v2 — verify via context7
(Traefik v3 docs) before authoring. Planner has WebFetch/context7.

**NET-01:** 3 hosts (API / admin-app / client-pwa) + HTTP→HTTPS redirect middleware.
Discretion (CONTEXT): IngressRoute CRD vs Ingress+annotations is planner's choice.

---

### cert-manager ClusterIssuer + Certificate (NET-03) — net-new

**No analog** — cert-manager is an operator-installed component, not vendored.
Use chart helper conventions (`clubcore.fullname`, `clubcore.labels`) for the
`Certificate` resource naming. ClusterIssuer is cluster-scoped (no namespace).

- `selfSigned` ClusterIssuer → local k3d (done-bar issuer)
- `letsencrypt-staging` → iterative
- LE-prod → **operator-pending** (do not author live prod cutover as done)

---

### SealedSecret swap (SEC-01) — modify `templates/app-secret.yaml`

**Analog = the file itself.** `app-secret.yaml:6-11,41-44` already carries the
Phase-119 handoff contract:
```yaml
  annotations:
    clubcore.io/replace-with-sealed-secret: "phase-119-sec-01"
    clubcore.io/secret-type: "app-env"
```
The plaintext `stringData` block (`app-secret.yaml:47-89`) is the exact key set that
must be sealed: `SECRET_KEY`, `DATABASE_URL`, `TELEGRAM_BOT_TOKEN`, `S3_ACCESS_KEY_ID`,
`S3_SECRET_ACCESS_KEY`, `EMAIL__*`. SealedSecret YAML is committed; plaintext never is.

**kubeseal helper script** — model after the existing infra scripts referenced in
`_helpers.tpl:81` (`infra/scripts/build-images.sh`, `infra/scripts/deploy-local.sh`).
Same `infra/scripts/` home, same bash-with-clear-error-message shape.

---

### SEC-02 — RSA controller-key export + off-node backup (HARD GATE, pitfall P6)

The key EXPORT is automatable (add to the kubeseal helper script:
`kubeseal --fetch-cert` / controller key export). The off-node copy itself is
**operator-pending** (no git remote — second-PC copy per project backup model).
Mark export step done-able; off-node confirmation operator-pending.

---

### securityContext hardening (SEC-03) — modify 3 Deployment templates

**Analog = the files themselves.** All three Phase-118 Deployments carry an
identical STUB. From `backend-deployment.yaml:56-61` (pod-level) and `:178-180`
(container-level):
```yaml
      # Security context stub — full SEC-03 hardening (readOnlyRootFilesystem,
      # drop ALL capabilities) is Phase 119 scope.
      securityContext:
        runAsNonRoot: true
        runAsUser: 1000
```
Container-level (`:178-180`):
```yaml
          securityContext:
            runAsNonRoot: true
            runAsUser: 1000
```

**SEC-03 hardening to add to the container `securityContext`** (per CONTEXT discretion
within the locked set):
```yaml
          securityContext:
            runAsNonRoot: true
            runAsUser: 1000
            allowPrivilegeEscalation: false
            readOnlyRootFilesystem: true
            capabilities:
              drop: ["ALL"]
```
Apply to `backend-deployment.yaml`, `arq-worker-deployment.yaml`,
`telegram-bot-deployment.yaml` (same stub in each). The `alembic-check`
initContainer (`backend-deployment.yaml:92-94`) also has the stub — harden it too.

> `readOnlyRootFilesystem: true` may require an `emptyDir` writable mount for
> any tmp/cache path the app or uvicorn writes — verify per-workload at plan time
> (per-workload tuning is explicitly in planner discretion).

---

### NetworkPolicy default-deny + CoreDNS egress (SEC-04, pitfall P8) — net-new

**No analog** in repo. Use `clubcore.selectorLabels` (`_helpers.tpl:48-51`) to scope
podSelectors to the right workload. **P8 invariant (HARD):** every pod's NetworkPolicy
MUST include explicit CoreDNS egress (UDP **and** TCP port 53) or DNS breaks.
Pattern: one default-deny-all policy + explicit-allow policies per workload
(backend↔postgres-rw:5432, backend↔redis:6379, backend↔seaweedfs S3, ingress→backend:8000,
all→CoreDNS:53). Component labels already exist on every workload
(`app.kubernetes.io/component: backend|...`) — use them as policy selectors.

---

### SEC-05 / NAME-01 — CSRF cookie VERIFY + additive regen (NOT a rename)

**Pre-existing-state confirmed (do NOT author a code rename):** the cookie is already
`clubcore_csrf` in:
- `apps/backend/app/core/security.py:247` (issue) + `:287` (clear)
- `apps/backend/app/core/dependencies.py:915` (verify)
- `apps/backend/app/main.py:474` (OpenAPI security-scheme doc, cites NAME-01)

**Scope = three things:**

**(a) Verify** — confirm no functional rename needed. Done by reading the 3 files above.

**(b) Stray-string sweep** — the ONLY remaining `sportzal_csrf` occurrences are in the
verify helper + its README (NOT runtime code):
- `apps/backend/scripts/verify/_lib.sh:22,57,82,84` — awk extraction key `$6=="sportzal_csrf"`
- `apps/backend/scripts/verify/README.md:171`
Fix `_lib.sh` to read `clubcore_csrf` (functional bug in verify scripts); update README.
Re-grep `apps/backend`, `apps/admin-app`, `apps/client-pwa`, `packages/` to prove zero
remaining `sportzal_csrf`.

**(c) Additive openapi + schema.d.ts regen** — exact existing toolchain:
```
# 1. backend OpenAPI (byte-stable: indent=2, sort_keys=True, ensure_ascii=False)
cd apps/backend && uv run python -m scripts.export_openapi   # writes apps/backend/openapi.json
# 2. typed client (openapi-typescript)
pnpm --filter @clubcore/api-client codegen                   # writes packages/api-client/src/schema.d.ts
```
`packages/api-client/package.json` `codegen` =
`openapi-typescript ../../apps/backend/openapi.json --output src/schema.d.ts`.
Per D-V40-SCOPE-ADDITIVE the staff drift-gate expects an **additive** diff, not byte-stable.

---

### SEC-06 — secure-phase 70 retro (skill invocation)

**Not a code artifact.** Invoke existing skill `/gsd:secure-phase 70`
(`.claude/gsd-core/workflows/secure-phase.md`; command at
`.claude/commands/gsd/secure-phase.md`) against
`.planning/milestones/v2.0-phases/70-client-bookings-qr-self-check-in/`
(70-SECURITY/70-REVIEW present). Verify/close 3 deferred items: proxy rate-limit
bucket, QR post-decode existence check, cancel idempotency.

---

## Shared Patterns

### Chart naming + labels (apply to EVERY new template)
**Source:** `infra/helm/clubcore/templates/_helpers.tpl`
- `clubcore.fullname` (`:13-24`) — resource name basis (NOT bare `.Release.Name`)
- `clubcore.labels` (`:36-43`) — common metadata labels, `nindent 4`
- `clubcore.selectorLabels` (`:48-51`) — pod/policy selectors
- `clubcore.image` (`:80-83`) — `image.tag` is `required`; pass `--set image.tag=<git-sha>`
```yaml
metadata:
  name: {{ include "clubcore.fullname" . }}-<suffix>
  labels:
    {{- include "clubcore.labels" . | nindent 4 }}
    app.kubernetes.io/component: <component>
```

### values.yaml extension
**Source:** `infra/helm/clubcore/values.yaml` (no `ingress`/`networkPolicy`/`certManager`/
`securityContext` keys exist yet). New top-level blocks must be added with the same
commented-default style the file already uses (e.g. `frontendBaseUrl: "https://admin.clubcore.ru"`,
`postgres.nodeSelector` block). securityContext should become value-driven defaults so
per-workload tuning is overridable.

### infra scripts
**Source:** `infra/scripts/build-images.sh`, `infra/scripts/deploy-local.sh`
(named in `_helpers.tpl:81`). New `seal-secrets.sh` follows the same bash + loud-error
convention.

### Operator-pending honesty (D-V40-LOCAL-VALIDATE)
Applies to NET-03 (LE-prod), SEC-01 (kubeseal round-trip if tooling absent),
SEC-02 (off-node copy), all live-apply. Mark template-validated vs apply-verified
distinctly; never fabricate apply/round-trip evidence.

---

## No Analog Found (net-new infra — planner uses RESEARCH.md / context7, not a repo analog)

| Artifact | Role | Reason |
|----------|------|--------|
| `ingress.yaml` / `ingressroute.yaml` | route | No Ingress/IngressRoute exists; Traefik v3 — verify WS annotation |
| `cluster-issuer.yaml` | cert-manager CR | cert-manager operator-installed, not vendored |
| `certificate.yaml` | cert-manager CR | same |
| `networkpolicy-*.yaml` | network | No NetworkPolicy in repo; P8 CoreDNS egress mandatory |
| SealedSecret form of app-secret | secret | kubeseal output; controller key required (operator-pending if absent) |

---

## Gaps / Planner Decisions

- **Frontend ingress targets missing:** the chart has NO admin-app / client-pwa
  Deployment+Service templates (only backend workloads exist; Phase 118 built the
  nginx *images* per IMG-03 but not their k8s workloads). NET-01 routes 3 hosts and
  NET-04 verifies SPA fallback/SW — but two of those ingress backends have no Service.
  Planner must decide: (a) add `admin-app`/`client-pwa` Deployment+Service templates
  (analog: `backend-deployment.yaml` + `backend-service.yaml`, minus DB/initContainer,
  nginx command, port 80/8080), or (b) scope NET-01 to the API host + treat frontend
  hosts as operator-pending. Recommendation: (a), since NET-04 done-bar implies the
  frontends are served in-cluster.
- **NET-02 WS annotation** — Traefik v3 key unresolved (research flag, STATE.md:84).
- **SEC-03 readOnlyRootFilesystem** — may need writable `emptyDir` mounts per workload.

---

## Metadata

**Analog search scope:** `infra/helm/clubcore/templates/`, `infra/scripts/`,
`apps/backend/app/core/`, `apps/backend/scripts/`, `packages/api-client/`,
`.claude/gsd-core/workflows/`
**Files scanned:** ~25
**Pattern extraction date:** 2026-06-16

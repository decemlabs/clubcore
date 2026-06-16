---
phase: 119-networking-security-csrf-rename
reviewed: 2026-06-16T00:00:00Z
depth: standard
files_reviewed: 9
files_reviewed_list:
  - infra/helm/clubcore/templates/networkpolicy-allow.yaml
  - infra/helm/clubcore/templates/networkpolicy-default-deny.yaml
  - infra/helm/clubcore/templates/sealed-secret.yaml
  - infra/helm/clubcore/templates/app-secret.yaml
  - infra/helm/clubcore/templates/ingress.yaml
  - infra/helm/clubcore/templates/_helpers.tpl
  - infra/helm/clubcore/templates/backend-deployment.yaml
  - infra/scripts/seal-secrets.sh
  - apps/backend/scripts/verify/_lib.sh
findings:
  critical: 1
  warning: 4
  info: 3
  total: 8
status: issues_found
---

# Phase 119: Code Review Report

**Reviewed:** 2026-06-16
**Depth:** standard
**Files Reviewed:** 9 (plus cross-referenced: values.yaml, Chart.yaml, redis-statefulset.yaml, the other 6 deployment/service/middleware templates, app/core/security.py)
**Status:** issues_found

## Summary

Phase 119 wires SEC-01..04 and NET-01..03 into the Helm chart plus a CSRF cookie rename in the verify harness. The overall structure is sound: default-deny uses a correct empty `podSelector: {}`, every explicit-allow policy includes CoreDNS egress on both UDP and TCP :53 (P8 satisfied), the SealedSecret uses the correct `bitnami.com/v1alpha1` API with no committed plaintext ciphertext, the hardened securityContext helper drops ALL caps with `readOnlyRootFilesystem:true` and matching emptyDir scratch for every workload (Python UID 1000, nginx UID 101), and the seal-secrets script refuses to write the RSA key inside the repo.

However, there is one **BLOCKER**: the backend→SeaweedFS S3 egress NetworkPolicy rule cannot match the SeaweedFS pods, because SeaweedFS is a Helm subchart whose pods do not carry clubcore's selector labels. With `networkPolicy.enabled=true`, default-deny will silently sever all backend→S3 traffic (avatar/document upload, bucket-ensure on boot). Several warnings concern over-broad selectors and stale verify-harness documentation.

Note on scope: helm/k3d/kubeseal are not installed, so render verification is operator-pending; findings below are reasoned statically from template + subchart label semantics.

## Critical Issues

### CR-01: backend→SeaweedFS S3 egress NetworkPolicy selects the wrong pods — S3 traffic silently blocked

**File:** `infra/helm/clubcore/templates/networkpolicy-allow.yaml:136-142`
**Issue:** The backend allow policy's SeaweedFS egress rule uses a podSelector built only from `clubcore.selectorLabels`:

```yaml
    - to:
        - podSelector:
            matchLabels:
              {{- include "clubcore.selectorLabels" . | nindent 14 }}
      ports:
        - protocol: TCP
          port: 8333
```

`clubcore.selectorLabels` (`_helpers.tpl:48-51`) expands to `app.kubernetes.io/name: clubcore` + `app.kubernetes.io/instance: <release>`. But SeaweedFS is a **subchart** (`Chart.yaml` dependency `seaweedfs` v4.33.0). Subchart pods carry the SeaweedFS chart's own labels (`app.kubernetes.io/name: seaweedfs`, and an instance label scoped to the subchart) — they do **not** carry `app.kubernetes.io/name: clubcore`. Therefore this podSelector matches **zero SeaweedFS pods**.

With `networkPolicy.enabled=true`, the default-deny policy (`networkpolicy-default-deny.yaml`) severs all egress, and this rule fails to re-permit backend→S3:8333. Result: the backend cannot reach SeaweedFS — bucket-ensure on startup, avatar/document upload, and presigned-URL backends all fail with connection timeouts the moment NetworkPolicies are enabled. This is a data-path outage, not a degradation. The Redis rule directly above it works (Redis is a clubcore template carrying `component: redis`), which masks the problem in casual review — only the subchart edge is broken.

Contrast: the rule as written is also self-contradictory — it claims to select SeaweedFS but actually selects clubcore-labeled pods on port 8333 (of which none listen on 8333), so it is simultaneously over-broad in intent and matches nothing in practice.

**Fix:** Select the SeaweedFS S3 pods by their actual subchart labels. Determine them via `helm template` / `kubectl get pods --show-labels | grep seaweedfs`, then target them explicitly. For the SeaweedFS chart the S3 component is typically labelled `app.kubernetes.io/name: seaweedfs` + `app.kubernetes.io/component: s3` (verify against v4.33.0):

```yaml
    # ── SeaweedFS S3 API :8333 ──
    - to:
        - podSelector:
            matchLabels:
              app.kubernetes.io/name: seaweedfs
              app.kubernetes.io/component: s3
      ports:
        - protocol: TCP
          port: 8333
```

If SeaweedFS runs in the same namespace this is sufficient; if it can land in a different namespace add a `namespaceSelector`. The arq-worker policy does NOT include an S3 rule — confirm arq tasks never touch S3 (e.g. document-generation jobs); if they do, the same corrected rule must be added to `allow-arq-worker`.

## Warnings

### WR-01: `_lib.sh` documents stale `sz_access` / `sz_refresh` cookie names

**File:** `apps/backend/scripts/verify/_lib.sh:20-26, 90-93`
**Issue:** The CSRF rename to `clubcore_csrf` is correct and complete — `login_as()` extracts `awk '$6=="clubcore_csrf"'` (line 82) and `mut()` sends `X-CSRF-Token` (line 101), matching `app/core/security.py` which sets `clubcore_csrf`. However the docstrings still describe the session cookies as `sz_access` / `sz_refresh`:

```
#       sz_access       HTTP-only access JWT, Path=/
#       sz_refresh      HTTP-only refresh token, Path=/api/v1/auth
```

and line 92: `(auth via sz_access HTTP-only cookie)`. The real cookies (`security.py:224,235`) are `cc_access` / `cc_refresh`. This is **functionally harmless** today because curl reuses the entire cookie jar (`-b "$COOKIE_JAR"`) regardless of cookie name, but it is misleading documentation in a security-sensitive auth harness and undermines confidence that the rename was done thoroughly. Since the phase is explicitly named "csrf-rename," leaving sibling cookie names stale is a defect in the rename's completeness.

**Fix:** Update the `_lib.sh` header block and the inline `mut()` comment to `cc_access` / `cc_refresh`:
```
#       cc_access       HTTP-only access JWT, Path=/
#       cc_refresh      HTTP-only refresh token, Path=/api/v1/auth
#       clubcore_csrf   non-HttpOnly CSRF token, Path=/, used as X-CSRF-Token
```

### WR-02: `_lib.sh` psql DSN still points at database `sportzal`

**File:** `apps/backend/scripts/verify/_lib.sh:119`
**Issue:** `psql_exec` connects to `postgresql://app:app@localhost:5432/sportzal`. The Helm chart, `app-secret.yaml`, and `values.yaml` all use database name **`clubcore`** (`values.yaml:44 database: clubcore`; `app-secret.yaml:74` constructs `.../clubcore`). If the local compose DB has been renamed to `clubcore` in line with the project rename, every `psql_exec` call in the verify suite will fail with `FATAL: database "sportzal" does not exist`. This is in the same rename blast radius as the CSRF cookie and should be checked together.

**Fix:** Confirm the compose Postgres database name. If it is now `clubcore`, update the DSN; if compose still seeds `sportzal` (legacy), add a comment pinning that fact so the divergence is intentional and visible:
```bash
psql "postgresql://app:app@localhost:5432/clubcore" -c "$sql"
```

### WR-03: Telegram-bot internet egress rule is namespace-open (can reach in-cluster pods on :443)

**File:** `infra/helm/clubcore/templates/networkpolicy-allow.yaml:253-255`
**Issue:** The "internet egress :443" rule has no `to:` selector at all:

```yaml
    - ports:
        - protocol: TCP
          port: 443
```

An egress rule with `ports` but no `to` permits egress to **any destination** on :443 — including in-cluster pods and the cluster API server, not just external Telegram IPs. The header comment (lines 247-252) claims it uses an `ipBlock` to restrict to external IPs ("instead use ipBlock to restrict to any external IP (not cluster CIDR)"), but the actual rule contains **no ipBlock** — the comment and code disagree. This is broader than least-privilege intends and contradicts its own documentation.

**Fix:** Either add the promised `ipBlock` excluding the cluster/pod CIDR, or update the comment to admit the rule is "all destinations on :443." Least-privilege form:
```yaml
    - to:
        - ipBlock:
            cidr: 0.0.0.0/0
            except:
              - 10.42.0.0/16   # pod CIDR (k3d default)
              - 10.43.0.0/16   # service CIDR (k3d default)
      ports:
        - protocol: TCP
          port: 443
```
Verify actual k3d CIDRs with `kubectl cluster-info dump | grep -i cidr` before committing.

### WR-04: Ingress API host has no path priority guarantee between `/api/v1/client/ws` and `/`

**File:** `infra/helm/clubcore/templates/ingress.yaml:73-90`
**Issue:** The API host declares two `pathType: Prefix` rules — `/api/v1/client/ws` and `/` — both pointing at the same `clubcore-backend:8000`. Because both backends are identical, this is currently harmless, but the comment (lines 73-75) implies the explicit WS path is doing routing work ("ensures future reviewers know WS is handled here"). If a future edit points the WS path at a different service or port while relying on prefix-longest-match precedence, Traefik v3's Ingress path ordering is **not guaranteed to prefer the longer prefix** the way the comment assumes — IngressRoute priority or explicit `pathType`/ordering would be needed. The redundant rule is a latent trap.

**Fix:** Since both paths resolve to the identical backend, drop the `/api/v1/client/ws` entry (the `/` prefix already covers it and WS upgrade is native in Traefik v3 per the file's own NET-02 note). If kept for documentation, add a comment that it is intentionally redundant and carries no routing precedence, so a future edit does not assume longest-prefix wins.

## Info

### IN-01: SeaweedFS S3 rule comment understates the same-namespace assumption

**File:** `infra/helm/clubcore/templates/networkpolicy-allow.yaml:131-135`
**Issue:** The comment says "Using a namespace-scoped port match (port 8333) is sufficient for same-namespace." A bare `podSelector` is namespace-scoped by definition, but the phrasing suggests the port alone restricts the target, which is not how NetworkPolicy podSelectors work. Tie this comment to the CR-01 fix.
**Fix:** After fixing CR-01, rewrite the comment to state the exact subchart labels matched.

### IN-02: seal-secrets.sh `grep -A100` could capture stray uppercase keys outside encryptedData

**File:** `infra/scripts/seal-secrets.sh:204`
**Issue:** `grep -A100 'encryptedData:' ... | grep -E '^\s+[A-Z_]+:'` extracts encryptedData keys by matching uppercase-with-underscore lines in the 100 lines following `encryptedData:`. For the current kubeseal output this is correct (the only uppercase keys are the secret names; `template:`/`metadata:`/`name:` are lowercase and excluded). It is mildly fragile: any future uppercase field added by kubeseal within 100 lines below `encryptedData:` would be mis-extracted into the values override. Verified harmless for sealed-secrets v0.37.0 output shape.
**Fix:** Optional hardening — parse with a YAML-aware tool (`yq '.spec.encryptedData'`) instead of grep/awk to remove the positional assumption.

### IN-03: `secrets.plaintextForLocalK3d` and `secrets.sealed.enabled` can both be true with no guard

**File:** `infra/helm/clubcore/templates/app-secret.yaml:42` and `sealed-secret.yaml:34`
**Issue:** The two Secret templates are gated independently (`if .Values.secrets.plaintextForLocalK3d` and `if .Values.secrets.sealed.enabled`). values.yaml comment (line 215) states "Only ONE path should be active at a time," but nothing enforces it. If an operator sets both true, two resources named `<fullname>-app-secret` render — the plaintext Secret and the SealedSecret's unsealed output collide on the same name, producing nondeterministic Secret contents (last-applied wins / unseal overwrite races). Not a leak, but a foot-gun for the production cutover.
**Fix:** Add a `fail` guard in one template, e.g. at the top of `sealed-secret.yaml`:
```
{{- if and .Values.secrets.sealed.enabled .Values.secrets.plaintextForLocalK3d }}
{{- fail "secrets.sealed.enabled and secrets.plaintextForLocalK3d are mutually exclusive — set plaintextForLocalK3d=false for production" }}
{{- end }}
```

---

_Reviewed: 2026-06-16_
_Reviewer: Claude (gsd-code-reviewer)_
_Depth: standard_

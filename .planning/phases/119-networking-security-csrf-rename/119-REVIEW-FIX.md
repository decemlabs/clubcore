---
phase: 119-networking-security-csrf-rename
fixed_at: 2026-06-16T00:00:00Z
review_path: .planning/phases/119-networking-security-csrf-rename/119-REVIEW.md
iteration: 1
findings_in_scope: 5
fixed: 5
skipped: 0
status: all_fixed
---

# Phase 119: Code Review Fix Report

**Fixed at:** 2026-06-16
**Source review:** .planning/phases/119-networking-security-csrf-rename/119-REVIEW.md
**Iteration:** 1

**Summary:**
- Findings in scope: 5 (1 BLOCKER + 4 Warnings; 3 Info out of scope)
- Fixed: 5
- Skipped: 0

**Verification note:** helm / k3d / kubeseal are not installed on this host, so
`helm template` render verification is **operator-pending**. All Helm/YAML fixes
were verified statically: the `.go-tmpl` directives were stripped and the
resulting YAML parsed cleanly (6 NetworkPolicy docs, 1 Ingress doc). The shell
script passed `bash -n`. No render evidence is fabricated.

## Fixed Issues

### CR-01 (BLOCKER): backend→SeaweedFS S3 egress NetworkPolicy selects the wrong pods

**Files modified:** `infra/helm/clubcore/templates/networkpolicy-allow.yaml`
**Commit:** 9e85e2dd
**Applied fix:** Replaced the SeaweedFS S3 egress `podSelector` (which used
`clubcore.selectorLabels` → `app.kubernetes.io/name: clubcore`, matching ZERO
SeaweedFS subchart pods) with the SeaweedFS subchart's own standard labels:
`app.kubernetes.io/name: seaweedfs`, `app.kubernetes.io/instance: {{ .Release.Name }}`,
`app.kubernetes.io/component: s3`. Confirmed via Chart.yaml (dep `seaweedfs` v4.33.0)
and values.yaml (`seaweedfs.s3.enabled: true`, dedicated `<release>-seaweedfs-s3:8333`
service). Without this, `networkPolicy.enabled=true` + default-deny silently severed
all backend→S3 traffic (bucket-ensure on boot, avatar/document uploads). Also rewrote
the misleading "selector notes" header bullet (the IN-01 same-rule comment) to state
the exact subchart labels matched.

**Note on arq-worker:** the review flagged that `allow-arq-worker` has no S3 rule and
asked to confirm arq tasks never touch S3. This was NOT changed — adding a speculative
S3 rule to arq-worker is out of scope for this finding and would require confirming arq
job behavior. Flagged here for operator awareness; if document-generation jobs use S3,
the same corrected rule must be added to `allow-arq-worker`.

### WR-01: `_lib.sh` documents stale `sz_access` / `sz_refresh` cookie names

**Files modified:** `apps/backend/scripts/verify/_lib.sh`
**Commit:** fd5f3222
**Applied fix:** Updated the header docstring (`sz_access` → `cc_access`,
`sz_refresh` → `cc_refresh`, "Auth flows via the sz_access cookie" → `cc_access`)
and the inline `mut()` comment ("auth via sz_access" → `cc_access`). Confirmed real
cookie names against `app/core/security.py`. The functional CSRF extraction
(`awk '$6=="clubcore_csrf"'`) was already correct and left untouched. Documentation-only
change; verified with `bash -n`.

### WR-02: `_lib.sh` psql DSN points at non-existent database `sportzal`

**Files modified:** `apps/backend/scripts/verify/_lib.sh`
**Commit:** aba6ec88
**Applied fix:** Changed `psql_exec` DSN from `.../sportzal` to `.../clubcore`
(confirmed `POSTGRES_DB: clubcore` + `DATABASE_URL .../clubcore` in
`apps/backend/docker-compose.yml`) and rewrote the stale `app/app/sportzal` credentials
comment to `app/app/clubcore` with the rename rationale. This was a genuine functional
bug — every `psql_exec` call would have failed with `FATAL: database "sportzal" does
not exist`. Verified with `bash -n`.

### WR-03: Telegram-bot internet egress rule is namespace-open on :443

**Files modified:** `infra/helm/clubcore/templates/networkpolicy-allow.yaml`
**Commit:** 1c4c673f
**Applied fix:** The rule had `ports` with no `to:` selector, permitting egress to ANY
destination on :443 (including in-cluster pods and the cluster API server) — contradicting
its comment that claimed an `ipBlock`. Since `api.telegram.org` resolves to dynamic IPs,
arbitrary internet :443 egress is genuinely required, so the rule was tightened to an
explicit `ipBlock: cidr 0.0.0.0/0` with `except` for the k3d/k3s default pod CIDR
(`10.42.0.0/16`) and service CIDR (`10.43.0.0/16`). This blocks in-cluster :443 lateral
movement while allowing Telegram API egress; default-deny still blocks everything else.
Comment now honestly describes the rule. OPERATOR NOTE in the file instructs verifying
actual cluster CIDRs.

### WR-04: Ingress API host redundant `/api/v1/client/ws` path rule

**Files modified:** `infra/helm/clubcore/templates/ingress.yaml`
**Commit:** c4c84a9e
**Applied fix:** Removed the dedicated `/api/v1/client/ws` `pathType: Prefix` rule. It
pointed at the identical `clubcore-backend:8000` as the catch-all `/` rule (no routing
work) and implied longest-prefix precedence that Traefik v3 Ingress does not guarantee —
a latent trap. The single `/` prefix already routes both WS and REST, and Traefik v3
upgrades WebSocket natively (per the file's NET-02 note). Comment updated to note the `/`
rule covers the WS chat path.

## Skipped Issues

The 3 Info findings are out of scope for this run (`fix_scope: critical_warning`).
Documented here for completeness:

### IN-01: SeaweedFS S3 rule comment understates same-namespace assumption

**File:** `infra/helm/clubcore/templates/networkpolicy-allow.yaml:131-135`
**Reason:** Out of scope (Info). However, because IN-01 is the same comment block as
the CR-01 rule, its substance was effectively resolved as part of the CR-01 fix — the
rule's inline comment and the header "selector notes" bullet now state the exact
subchart labels matched and the same-namespace scoping.

### IN-02: seal-secrets.sh `grep -A100` could capture stray uppercase keys

**File:** `infra/scripts/seal-secrets.sh:204`
**Reason:** Out of scope (Info). Reviewer confirmed it is harmless for sealed-secrets
v0.37.0 output; the suggested `yq`-based hardening is optional and not in the
critical_warning scope.

### IN-03: `plaintextForLocalK3d` and `sealed.enabled` both-true has no guard

**File:** `infra/helm/clubcore/templates/app-secret.yaml:42`, `sealed-secret.yaml:34`
**Reason:** Out of scope (Info). A `fail` guard for the mutually-exclusive secret paths
is a production-cutover foot-gun hardening, not a critical/warning defect.

---

_Fixed: 2026-06-16_
_Fixer: Claude (gsd-code-fixer)_
_Iteration: 1_

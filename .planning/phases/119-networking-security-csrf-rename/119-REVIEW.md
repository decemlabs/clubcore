---
phase: 119-networking-security-csrf-rename
reviewed: 2026-06-16T11:51:48Z
depth: standard
files_reviewed: 7
files_reviewed_list:
  - infra/helm/clubcore/templates/networkpolicy-allow.yaml
  - infra/helm/clubcore/templates/networkpolicy-default-deny.yaml
  - infra/helm/clubcore/templates/ingress.yaml
  - infra/helm/clubcore/templates/sealed-secret.yaml
  - infra/helm/clubcore/templates/app-secret.yaml
  - infra/scripts/seal-secrets.sh
  - apps/backend/scripts/verify/_lib.sh
findings:
  critical: 0
  warning: 1
  info: 0
  total: 1
status: issues_found
---

# Phase 119: Code Review Report (Re-Review — Iteration 2)

**Reviewed:** 2026-06-16T11:51:48Z
**Depth:** standard
**Files Reviewed:** 7
**Status:** issues_found (1 minor WARNING; all prior-iteration findings confirmed fixed)

## Summary

This is a re-review focused on confirming the FINAL state at HEAD after a worktree
last-write-wins hazard had clobbered the CR-01 fix (since re-applied). All four
re-review checklist axes were verified by static reasoning (helm/k3d/kubeseal not
installed — render verification remains operator-pending, but the YAML/templating
is unambiguous).

**Verdict: CR-01 and all four prior warnings (WR-01..04) survived intact at HEAD.
No regressions detected. One minor, low-severity robustness gap noted in the seal
helper (WR-01 below), which is NOT a prior finding and does not block.**

### Re-review checklist — confirmed at HEAD

1. **CR-01 (backend→SeaweedFS-S3 egress) — CONFIRMED PRESENT, NOT REVERTED.**
   `networkpolicy-allow.yaml:146-154` (backend `allow-backend` policy) targets the
   subchart labels `app.kubernetes.io/name: seaweedfs` + `app.kubernetes.io/instance: {{ .Release.Name }}`
   + `app.kubernetes.io/component: s3` on TCP `8333`. It does NOT use
   `clubcore.selectorLabels` (which would match zero SeaweedFS pods → S3 outage).
   The load-bearing fix is present and the explanatory header (lines 55-59, 135-145)
   documents the rationale.

2. **arq-worker S3 follow-up — CONFIRMED PRESENT.**
   `networkpolicy-allow.yaml:213-221` (`allow-arq-worker`) now carries the identical
   SeaweedFS subchart S3 egress rule (same three labels, TCP `8333`). Rationale
   documented at lines 207-212 (`build_storage` at worker startup + `forward_to_staff`
   media handling).

3. **No regression on confirmed-correct items:**
   - default-deny `podSelector: {}` — CONFIRMED (`networkpolicy-default-deny.yaml:35`),
     policyTypes Ingress+Egress with no rules.
   - CoreDNS egress on BOTH UDP+TCP :53 in EVERY allow policy (P8) — CONFIRMED:
     backend (103-114), arq-worker (176-187), telegram-bot (243-254), migrate
     (317-328), admin-app (372-383), client-pwa (415-426). All six present.
   - SealedSecret carries no committed plaintext — CONFIRMED
     (`sealed-secret.yaml:62-70` only emits `encryptedData` sourced from values; the
     plaintext path in `app-secret.yaml` is gated on `secrets.plaintextForLocalK3d`
     and clearly fenced as local-k3d-only).
   - `seal-secrets.sh` does not leak the RSA key — CONFIRMED:
     `check_no_key_in_repo` (72-88) hard-fails on any path under `REPO_ROOT`; default
     export goes to `/tmp`; cert/plaintext/sealed temp files use `mktemp` in `/tmp`
     with EXIT-trap cleanup.

4. **WR-01..04 (prior iteration) survived:**
   - prior WR (cookie docs) — CONFIRMED: `_lib.sh:20-22` documents `cc_access`,
     `cc_refresh`, `clubcore_csrf`; extraction at line 83 reads `clubcore_csrf`.
   - prior WR (psql DSN = clubcore DB) — CONFIRMED: `_lib.sh:28-31, 120` use
     `postgresql://app:app@localhost:5432/clubcore`.
   - prior WR (telegram :443 ipBlock-with-except) — CONFIRMED:
     `networkpolicy-allow.yaml:287-295` uses an explicit `ipBlock` `0.0.0.0/0` with
     `except` for the k3d/k3s pod (`10.42.0.0/16`) and service (`10.43.0.0/16`) CIDRs,
     not an open `ports`-only rule. In-cluster :443 lateral movement is blocked.
   - prior WR (redundant /ws ingress path removed) — CONFIRMED: `ingress.yaml:75-86`
     has only the `/` Prefix rule for the API host; the dedicated `/api/v1/client/ws`
     rule is gone (removal documented at 69-73).

## Warnings

### WR-01: Brief plaintext-secret exposure window between mktemp and trap update in seal-secrets.sh

**File:** `infra/scripts/seal-secrets.sh:153-154` (also 176-177)
**Issue:** The script uses a sequence of single-handler `trap '...' EXIT` statements
that each overwrite the previous one (lines 113, 154, 177) rather than accumulating
cleanup targets. `PLAINTEXT_SECRET_FILE` — written with the operator's REAL plaintext
secrets (SECRET_KEY, DATABASE_URL with DB password, S3 keys, Telegram token) at line
153 — is created BEFORE the trap that covers it is installed at line 154. If the
process receives a signal (e.g. SIGINT/Ctrl-C) in that one-line window, the EXIT trap
in effect is still the line-113 trap, which only removes `CERT_FILE`, leaving the
plaintext secret file orphaned in `/tmp`. The same one-line gap exists at 176-177 for
`SEALED_OUTPUT_FILE` (lower sensitivity — ciphertext only). Additionally none of the
traps handle INT/TERM, so an interrupt mid-run never triggers cleanup at all. This is
a robustness/hygiene gap, NOT a confirmed prior finding; severity is low because the
window is a single non-blocking assignment and `/tmp` is operator-local, but it does
briefly defeat the "plaintext never persists" intent on an ill-timed interrupt.
**Fix:** Pre-declare all temp-file variables and install a single cumulative trap once,
before any sensitive file is created, and cover INT/TERM:
```bash
CERT_FILE="" PLAINTEXT_SECRET_FILE="" SEALED_OUTPUT_FILE=""
cleanup() { rm -f "$CERT_FILE" "$PLAINTEXT_SECRET_FILE" "$SEALED_OUTPUT_FILE"; }
trap cleanup EXIT INT TERM
# ...then assign each var via mktemp as you reach it; the single trap already covers them.
```

## Notes (non-blocking observations, no finding raised)

- `seal-secrets.sh:204` extracts `encryptedData` via
  `grep -A100 'encryptedData:' | grep -E '^\s+[A-Z_]+:'`. The `-A100` could bleed past
  `encryptedData` into the `spec.template` block, but that block's keys are lowercase
  (`name:`, `namespace:`, `labels:`) and do not match the `[A-Z_]+:` filter, so only the
  intended ALL-CAPS encrypted keys are emitted. Brittle but correct for the current
  SealedSecret shape — not flagged.
- `RELEASE_NAME` default in `seal-secrets.sh:45` is `clubcore`, and `SECRET_NAME` is
  built as `${RELEASE_NAME}-app-secret`. This matches the template's
  `{{ include "clubcore.fullname" . }}-app-secret` only when fullname == release name
  (the standard case). For a divergent fullname the sealed Secret name would not match —
  but this is documented operator territory (line 46 references the fullname logic) and
  is tunable via `SEALED_RELEASE`. Consistent with the CR-01 fullname reasoning in
  `app-secret.yaml`. Not flagged.
- The seaweedfs `instance` label uses `{{ .Release.Name }}` (allow.yaml:150, 217) while
  the header comment (line 56) describes it as `app.kubernetes.io/instance=<release>` —
  consistent, since the subchart inherits the parent release name. Render verification
  of the exact subchart label values remains operator-pending (no helm installed).

---

_Reviewed: 2026-06-16T11:51:48Z_
_Reviewer: Claude (gsd-code-reviewer)_
_Depth: standard (render verification operator-pending — helm/k3d/kubeseal not installed)_

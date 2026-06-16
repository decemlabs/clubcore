---
phase: 121-makefile-ci-cd-full-smoke-runbooks
reviewed: 2026-06-16T00:00:00Z
depth: standard
files_reviewed: 3
files_reviewed_list:
  - Makefile
  - infra/scripts/smoke.sh
  - infra/runbooks/production.md
findings:
  critical: 0
  warning: 5
  info: 6
  total: 11
status: issues_found
---

# Phase 121: Code Review Report

**Reviewed:** 2026-06-16
**Depth:** standard
**Files Reviewed:** 3
**Status:** issues_found

## Summary

Reviewed the Phase 121 CD capstone: the `Makefile` orchestration layer, `infra/scripts/smoke.sh` (the 8-check Looks-Done-But-Isn't smoke), and `infra/runbooks/production.md`.

The work is largely sound on the dimensions called out as highest-risk:
- The trivy scan gate is **not** silently bypassed — `make scan` wraps `scan-images.sh`, which fails closed under `REQUIRE_TRIVY=1` (verified by reading the script).
- The Makefile **wraps** existing `infra/scripts/*.sh` (build/scan/deploy/smoke/backup) rather than reimplementing them; only the thin k8s-CLI conveniences (push/helm-lint/helm-validate/rollback/logs/psql/down) are inlined, which is appropriate.
- `logs`/`psql` recipes do **not** echo secrets — no `--password=` literals, no env printing.
- `make up` prerequisite ordering is exactly `build → scan → tf-validate → helm-lint → deploy → smoke`.
- Phase-120 targets (`help`, `tf-validate`, `tf-plan`) are preserved verbatim.
- `smoke.sh` has `set -euo pipefail`, all 8 checks aggregate failures via `SMOKE_FAILURES` and exit non-zero — checks are NOT vacuous no-ops.
- The "4 images" vs "3 imported" discrepancy is **not a bug**: `build-images.sh` documents that `clubcore/backend` is the shared Python base reused by arq-worker + telegram-bot, so only 3 distinct image tags exist. `push` importing 3 is correct.
- The runbook embeds no real secrets (placeholders only), both HARD GATES (SEC-02 + BAK-03) are present, and the arq-worker/telegram-bot `replicas:1`/`Recreate` invariant is loudly documented.

Findings below are correctness/robustness gaps and doc/command-drift issues, none rising to BLOCKER given the OPERATOR-PENDING boundary is honest.

## Warnings

### WR-01: `set -e` + `pipefail` can abort smoke mid-run, skipping later checks and the FAIL banner

**File:** `infra/scripts/smoke.sh:31` (interaction with checks 3, 4, 8a, 8b)
**Issue:** The script runs under `set -euo pipefail`. Several checks use pipelines whose head command can fail or whose `grep` returns non-zero, and they rely on a trailing `|| echo ""` to neutralize it. That guard works only when it is the *last* element of the pipeline. But `pipefail` makes a pipeline fail if **any** stage fails, and the `|| echo ""` only rescues the final stage's status.

Concretely:
- Line 124-125 / 177-178: `kubectl get ... | tr ' ' '\n' | grep redis | head -1 || echo ""`. With `pipefail`, if `grep redis` finds nothing it exits 1; `head -1` then exits 0, but `pipefail` propagates the `grep` failure to the whole pipeline. The `|| echo ""` rescues it — OK here. However if `kubectl` itself errors mid-pipe, the captured value is still empty and handled. This particular one is safe, but it is fragile by construction.
- Line 305 / 317: `if echo "${sw_cache}" | grep -q 'no-cache'` is inside an `if`, so `set -e` does not abort there — safe.
- The real risk: any unguarded external command in a check function that exits non-zero will abort the **entire script** before the FAIL summary banner (line 369-376) runs, so the operator sees a hard stop with no aggregated report and a misleading exit code path. The aggregation design assumes every fallible command is individually guarded; this is true today but easy to break.

**Fix:** Make the aggregation robust to `set -e` by running each check in a context that cannot abort the script, e.g. wrap the check dispatch:
```bash
run_check() { "$@" || true; }   # failures already recorded via fail(); never abort
...
run_check check_healthz
run_check check_migrate
# etc.
```
This guarantees the summary banner always runs and the exit status reflects `SMOKE_FAILURES`, not an incidental `set -e` trip.

### WR-02: Check 7 (SPA fallback) sends a `Host:` header but also resolves the Host as the URL authority — will fail against a single ingress IP

**File:** `infra/scripts/smoke.sh:278-289`
**Issue:** The loop builds the request as `curl ... -H "Host: ${host}" "http://${host}${deep_path}"`. Using `${host}` as *both* the URL authority and the explicit `Host:` header means curl must DNS-resolve `admin.clubcore.local` / `app.clubcore.local` to reach the ingress. In a k3d setup these hostnames typically are not in DNS/`/etc/hosts`, so curl returns `000` (could not resolve) and the check FAILS even when SPA fallback is correctly configured — a false negative. The explicit `Host:` header is redundant when the authority already carries the hostname; the intent of passing `Host:` is usually to hit a known ingress IP/port while spoofing the vhost.
**Fix:** Decide on one addressing strategy and document it. Either rely on `/etc/hosts` entries (and drop the redundant `-H Host:`), or target the ingress endpoint and spoof the host:
```bash
INGRESS="${INGRESS:-http://localhost:80}"
status="$(curl -s -o /dev/null -w '%{http_code}' --max-time 10 \
    -H "Host: ${host}" "${INGRESS}${deep_path}")"
```
The same redundant-authority pattern affects check 6 (line 252) and check 8 (lines 303, 315) — they will also `000` without DNS/hosts entries. Note the operator-pending banner means this is unverified live, so the false-negative risk is latent rather than observed.

### WR-03: `make up` runs `smoke` twice (deploy-local.sh already runs an inline smoke, then `make smoke` runs again)

**File:** `Makefile:72-73, 76, 100`
**Issue:** `deploy` wraps `deploy-local.sh`, whose own header (lines 6, 10, 138 `[6/7] Running smoke checks`) shows it performs inline smoke checks and prints `SMOKE: ALL PASS`. The `up` target then appends a standalone `smoke`. This is not incorrect, but it is wasteful and confusing: an operator sees two PASS banners, and the inline deploy smoke (5 checks) overlaps the standalone smoke (8 checks). If the two diverge over time (e.g. deploy's inline migrate check uses a different condition type than smoke.sh), the operator gets contradictory output.
**Fix:** Either (a) document in the `up` help/comment that the standalone `smoke` is the authoritative superset and the inline deploy smoke is a fast-fail pre-check, or (b) add a flag to `deploy-local.sh` (e.g. `SKIP_INLINE_SMOKE=1`) that `make up` sets so smoke runs exactly once. Prefer (b) to avoid double banners.

### WR-04: `helm-lint`/`helm-validate`/`push` use `$(TAG)` but `deploy`/`build`/`scan` derive TAG internally — drift risk if working tree changes between targets

**File:** `Makefile:22, 52-55, 59, 63-64; cross-ref build-images.sh / deploy-local.sh / scan-images.sh internal TAG derivation`
**Issue:** The header comment (lines 18-21) correctly states scripts derive TAG internally (including the `-dirty` suffix) and the Makefile must not override them. But `push`, `helm-lint`, and `helm-validate` use the Makefile's `TAG ?= $(shell git rev-parse --short HEAD)` — which does **not** include the `-dirty` suffix that `build-images.sh` adds. So in a dirty working tree, `build`/`scan`/`deploy` operate on `clubcore/backend:abc1234-dirty` while `push`/`helm-lint`/`helm-validate` reference `clubcore/backend:abc1234`. In `make up` the order is build→scan→...→deploy (deploy imports images itself), so `push` is not in the pipeline and the mismatch is dormant there. But an operator running `make push` or `make helm-lint` manually after a dirty build will reference a tag that does not exist, causing a confusing "image not found" failure.
**Fix:** Derive the Makefile `TAG` with the same dirty-aware logic the scripts use, e.g.:
```make
TAG ?= $(shell git describe --always --dirty --abbrev=7 2>/dev/null || git rev-parse --short HEAD)
```
or, better, source the single canonical tag from a shared helper the scripts also call, so there is exactly one derivation.

### WR-05: Runbook `kubectl logs deploy/...` diagnostics will fail for arq-worker/telegram-bot Recreate-strategy gaps and for multi-container pods

**File:** `infra/runbooks/production.md:319, 327, 330` (and Quick Reference parity)
**Issue:** Several troubleshooting commands use `kubectl logs deploy/clubcore-backend` / `deploy/clubcore-telegram-bot`. `kubectl logs deploy/X` only returns logs from one (arbitrary) pod of the deployment and, for the backend which has an `alembic-check` init/sidecar container (referenced at line 445), `kubectl logs deploy/clubcore-backend` without `-c` returns the default container only — an operator chasing a startup failure in `alembic-check` (the very scenario in the migrate/CrashLoop rows) will see the wrong container's logs and conclude nothing is wrong. The 118-4 row at line 445 correctly uses `-c alembic-check`, so the troubleshooting table is inconsistent with the documented container topology.
**Fix:** In the CrashLoop / migrate rows, point operators at the init/sidecar container explicitly and at the Job, not the Deployment:
```
kubectl logs job/clubcore-migrate -n default
kubectl logs deploy/clubcore-backend -c alembic-check -n default   # init guard
kubectl logs deploy/clubcore-backend -c backend -n default         # app
```
Add a note that `kubectl logs deploy/...` selects a single pod and use `--all-containers` where the container is unknown.

## Info

### IN-01: Check 8b probes `/api/v1/ping`, but check 6 implies `/api/v1/...` paths require auth — endpoint existence unverified

**File:** `infra/scripts/smoke.sh:315`
**Issue:** Check 8b asserts `Cache-Control: no-store` on `http://${API_HOST}/api/v1/ping`. There is no evidence in the reviewed files that `/api/v1/ping` exists (check 6 uses `/api/v1/client/ws/smoke-probe` and explicitly tolerates 4xx). If `/api/v1/ping` returns 404, the response may carry no `Cache-Control` header at all, failing 8b for an endpoint-naming reason rather than a real caching gap.
**Fix:** Probe a header that is set by the ingress/gateway regardless of route existence (e.g. a known static `/healthz` or whatever path the nginx/Traefik `no-store` rule matches), or confirm `/api/v1/ping` is a real route and document it.

### IN-02: WS smoke key uses a fixed base64 fallback — accepts a non-conforming handshake key

**File:** `infra/scripts/smoke.sh:251`
**Issue:** `Sec-WebSocket-Key: $(echo -n 'clubcore-smoke' | base64 ...)` base64-encodes a fixed 14-byte string, producing a 20-char key. RFC 6455 requires a 16-byte (24-char base64) nonce. A strict server could reject it with 400, which the check tolerates as PASS (line 261-262), so the check still "passes" but for the wrong reason. Low impact because 400/426 are explicitly accepted as "path reachable."
**Fix:** Generate a conforming 16-byte key: `head -c16 /dev/urandom | base64`.

### IN-03: `smoke.sh` computes `REPO_ROOT` but never uses it

**File:** `infra/scripts/smoke.sh:48`
**Issue:** `REPO_ROOT="$(git rev-parse --show-toplevel)"` is assigned but no subsequent line references `${REPO_ROOT}`. Dead variable; also makes the script fail under `set -e` if run outside a git checkout, even though it has no functional dependency on git.
**Fix:** Remove the unused assignment, or guard it `REPO_ROOT="$(git rev-parse --show-toplevel 2>/dev/null || pwd)"` if a future check needs it.

### IN-04: Help-string regex hides `up:` target from `make help`

**File:** `Makefile:33, 100`
**Issue:** `help` greps `^[a-zA-Z_-]+:.*?## .*$$`. The `up` target is defined as `up: build scan tf-validate helm-lint deploy smoke ## ...` — it matches the regex, so it appears. But the column formatting (`%-20s`) and the fact that `up`'s prerequisite list precedes `##` means awk's `FS = ":.*?## "` splits on the first `:` then the `## ` — `$1` becomes `up` (correct). This is fine; noting only that targets whose name contains characters outside `[a-zA-Z_-]` would silently vanish from help. No current target is affected.
**Fix:** None required; flag for future targets (e.g. anything with a `.` or `:` in the name) to keep them discoverable.

### IN-05: Runbook claims `make smoke` "8/8" but deploy inline smoke is 5 checks — potential operator confusion on count

**File:** `infra/runbooks/production.md:144, 189` vs `183`
**Issue:** Line 189 says standalone smoke is "8/8 checks"; line 183 shows the deploy inline smoke output `(all smoke checks pass)`. The two smoke surfaces have different check counts (5 inline vs 8 standalone). An operator reconciling logs may be confused about which "all pass" is authoritative. Ties to WR-03.
**Fix:** State explicitly in the runbook that deploy runs a 5-check fast pre-smoke and `make smoke` is the authoritative 8-check superset.

### IN-06: `migrate` check relies on `condition=Complete` but reports "Succeeded" — terminology drift with k8s Job condition names

**File:** `infra/scripts/smoke.sh:90, 105-106` (and runbook lines 360, 442)
**Issue:** The check waits `--for=condition=Complete` (correct k8s Job condition) but then keys success off `.status.succeeded == 1` and logs "Succeeded." Mixing "Complete" (the condition) and "Succeeded" (the count) is internally consistent here, but the runbook's expected-output strings (`status.succeeded = 1`, "migrate Job: Succeeded") should match the script's actual messages verbatim so operators can grep for them. Minor wording drift only.
**Fix:** Align runbook expected-output snippets with the exact strings smoke.sh prints (`(2) migrate Job status.succeeded = 1`).

---

_Reviewed: 2026-06-16_
_Reviewer: Claude (gsd-code-reviewer)_
_Depth: standard_

---
phase: 120-iac-observability-backup
reviewed: 2026-06-16T13:03:11Z
depth: standard
files_reviewed: 9
files_reviewed_list:
  - infra/scripts/restore-verify.sh
  - infra/helm/clubcore/templates/restore-verify-cronjob.yaml
  - infra/helm/clubcore/templates/backup-redis-cronjob.yaml
  - infra/helm/clubcore/templates/backup-seaweedfs-cronjob.yaml
  - infra/docker/backup.Dockerfile
  - infra/scripts/build-images.sh
  - infra/helm/clubcore/templates/_helpers.tpl
  - infra/helm/clubcore/values.yaml
  - infra/observability/alertmanager-rules.yaml
findings:
  critical: 0
  warning: 3
  info: 3
  total: 6
status: issues_found
---

# Phase 120: Code Review Report (Re-Review — Iteration 2)

**Reviewed:** 2026-06-16T13:03:11Z
**Depth:** standard
**Files Reviewed:** 9
**Status:** issues_found

## Summary

This is iteration-2 verification of the 4 BLOCKER + 6 warning fixes in the Phase 120
backup/restore machinery. I traced each claimed fix statically (helm/k3d/docker not
runnable here).

**Fix-verification verdict — all 5 traced fixes are correct:**

- **CR-01 (heredoc dedent): CONFIRMED.** The heredoc body's top-level keys
  (`apiVersion`/`kind`/`metadata`/`spec`/`externalClusters`) are indented exactly 18
  spaces; the sed pattern `s/^                  //` strips exactly 18 spaces (verified
  by byte count). Top-level keys land at column 0; nested keys retain their relative
  2-space increments (e.g. `name:` 20→2, `clubcore.io/safety:` 22→4,
  `accessKeyId.name` 30→12). No over-strip, no under-strip. The unquoted `SCRATCH_EOF`
  correctly defers `${SCRATCH_CLUSTER_NAME}`/`${S3_BUCKET}` expansion to runtime, and the
  body contains no `{{ }}` so Helm rendering is a no-op on it.
- **CR-02 (pre-baked image): CONFIRMED.** `backup.Dockerfile` is non-root (`USER 1000`,
  `adduser -D -u 1000 backup`), installs `redis` (redis-cli) + `aws-cli` + `coreutils`
  (GNU `date -d`) + `ca-certificates`. Both CronJobs reference `clubcore.backupImage`,
  no longer `apk add` at runtime, and assert tool presence via `command -v` guards.
  `readOnlyRootFilesystem: true` holds; writable scratch goes to `/tmp` emptyDir
  (redis-cli dump) and the mirror PVC. `clubcore.backupImage` helper +
  `backup.image.repository` values wire correctly and inherit the global `image.tag`
  `required` guard.
- **CR-03/CR-04 (restore-verify fail-closed): CONFIRMED.** Both the standalone script
  and the inline CronJob use `SELECT count(*) FROM users`, treat a failed query as a
  hard `err` (no path defaults to 0/PASS), reject empty/non-numeric counts via `case`
  guards, reject a live count of 0, and fail on mismatch via `[ "$LIVE" != "$SCRATCH" ]`
  → `err` → non-zero exit → alert. `users` is a defensible always-non-empty table (≥1
  owner seeded at install). No false-PASS path remains.
- **WR-04 (SeaweedFS incremental mirror): CONFIRMED.** `aws s3 sync --delete` into a
  single stable `current/` dir; `cp -al current → YYYY-MM-DD` hardlink snapshot (both
  under the same PVC `/mnt/backup`, so hardlinks are valid); prune by
  `find -name "20??-??-??"` which does NOT match `current/` (verified). Prune is bounded
  by `RETENTION_DAYS`. The prior full-re-download-per-day overflow is genuinely fixed.
- **WR-05 (namespace-agnostic + KubeBackupJobFailed): CONFIRMED.** New
  `KubeBackupJobFailed` rule with regex `.*(backup-redis|backup-seaweedfs|restore-verify).*`
  matches all three rendered job names (`clubcore-backup-redis-*`,
  `clubcore-backup-seaweedfs-*`, `clubcore-restore-verify-*` — verified). Both backup-job
  alert-linkage annotations correctly point at `KubeBackupJobFailed` (not the
  restore-verify-only rule). Namespace hard-coding removed.

**No-regression checks:** BAK-04 scratch-only invariant intact (separate namespace +
NEW Cluster, never `spec.bootstrap.recovery` on live). SEC-03 hardened securityContext +
`TZ=UTC` present on all containers/initContainers. No new plaintext secrets (bot token is
`bot_token_file`, chat_id is a documented placeholder).

**Remaining issues** are residual/newly-surfaced and documented below — none block the
traced fixes, but WR-01 and WR-02 are genuine robustness/correctness gaps that the prior
fixes intended to close but missed.

## Warnings

### WR-01: `BEFORE_SAVE` is not numeric-guarded before the `-gt` comparison (WR-02 fix incomplete)

**File:** `infra/helm/clubcore/templates/backup-redis-cronjob.yaml:170,180`
**Issue:** The WR-02 fix added a numeric guard for `CURRENT_SAVE` (the `case` at lines
177-179), but the same `-gt` comparison at line 180 also dereferences `BEFORE_SAVE`,
captured once at line 170 with no guard:
```sh
BEFORE_SAVE=$(redis-cli ... LASTSAVE)              # line 170 — unguarded
...
if [ "${CURRENT_SAVE}" -gt "${BEFORE_SAVE}" ]; then  # line 180
```
If the initial `LASTSAVE` returns empty (transient connection blip, redis still loading),
`BEFORE_SAVE=""` and the loop runs `[ "<num>" -gt "" ]`, which under `set -e` aborts the
whole job — the exact failure mode WR-02 set out to eliminate, just on the other operand.
Command-substitution failure does not trip `set -e` on assignment, so an empty value can
reach the comparison.
**Fix:** Guard `BEFORE_SAVE` the same way as `CURRENT_SAVE`, immediately after capture:
```sh
BEFORE_SAVE=$(redis-cli -h "${REDIS_HOST}" -p "${REDIS_PORT}" LASTSAVE)
case "${BEFORE_SAVE}" in
  ''|*[!0-9]*) echo "[backup-redis] ERROR: initial LASTSAVE non-numeric ('${BEFORE_SAVE}')" >&2; exit 1 ;;
esac
```

### WR-02: Redis retention prune relies on a fragile JMESPath string comparison of mismatched timestamp formats

**File:** `infra/helm/clubcore/templates/backup-redis-cronjob.yaml:214-222`
**Issue:** `PRUNE_BEFORE` is formatted `%Y-%m-%dT%H:%M:%SZ` (e.g. `2026-05-19T00:00:00Z`),
then compared lexicographically inside JMESPath:
`Contents[?LastModified<='${PRUNE_BEFORE}']`. The `LastModified` field that
`aws s3api list-objects` returns is serialized by botocore to ISO-8601 with a numeric
offset, typically `2026-05-19T00:00:00+00:00` (and against SeaweedFS may include
fractional seconds). A `Z`-suffixed string and a `+00:00`-suffixed string do not order
correctly as raw strings — for the same instant `'...Z'` sorts after `'...+00:00'`, so
the cutoff is off and prune can silently keep stale objects or delete the wrong ones. The
retention contract is not reliably enforced.
**Fix:** Compare on epoch in shell (mirrors the `CUTOFF_EPOCH` approach already used in
backup-seaweedfs-cronjob.yaml:213) instead of trusting JMESPath string ordering:
```sh
aws s3api list-objects --bucket "${S3_BUCKET}" --prefix "${S3_PREFIX}/" \
  --endpoint-url "${S3_ENDPOINT_URL}" \
  --query "Contents[].[Key,LastModified]" --output text 2>/dev/null | while read -r KEY LM; do
  [ -z "${KEY}" ] && continue
  LM_EPOCH=$(date -u -d "${LM}" +%s 2>/dev/null || echo 0)
  [ "${LM_EPOCH}" -gt 0 ] && [ "${LM_EPOCH}" -lt "${CUTOFF_EPOCH}" ] && \
    aws s3 rm "s3://${S3_BUCKET}/${KEY}" --endpoint-url "${S3_ENDPOINT_URL}"
done
```

### WR-03: SeaweedFS mirror PVC remains at overflow risk — `current/` mirrors the ENTIRE bucket including CNPG WAL/base backups

**File:** `infra/helm/clubcore/templates/backup-seaweedfs-cronjob.yaml:193-198`, `infra/helm/clubcore/values.yaml:143,601`
**Issue:** WR-04's incremental-sync fix correctly eliminates the per-day full
re-download, but the mirror syncs `s3://${S3_BUCKET}/` — the *whole* bucket, which
includes the CNPG `postgres/` barmanObjectStore (30 days of WAL + base backups per
`backup.postgres.retentionPolicy: "30d"`) and the `redis/` RDBs, plus app uploads. The
SeaweedFS volume PVC is `20Gi` (values.yaml:143) and the mirror PVC is also `20Gi`
(values.yaml:601). Hardlink snapshots only dedupe *unchanged* files; CNPG WAL segments
are append-once new objects every day, so each daily snapshot adds genuinely new inodes
that accumulate until the 28-day prune. Worst case the mirror holds `current/` (≈ full
bucket) plus ~28 days of net-new WAL churn, which can exceed a 20Gi PVC sized for a single
copy once the bucket fills its own 20Gi volume. The header comment's "~1 copy + churn" is
optimistic for a write-heavy DB.
**Fix:** Either (a) exclude the CNPG prefix since it is already durable in S3 — the mirror
is DR for app uploads + redis — via `aws s3 sync ... --exclude "postgres/*"`; or (b) size
the mirror PVC explicitly larger than `seaweedfs.volume.size` + (WAL-churn × retentionDays)
and document the formula. At minimum document that mirror PVC size must scale with bucket
size and the prune window.

## Info

### IN-01: Unused `REPO_ROOT` variable in the standalone restore-verify script

**File:** `infra/scripts/restore-verify.sh:48`
**Issue:** `REPO_ROOT="$(git rev-parse --show-toplevel 2>/dev/null || echo "/app")"` is
assigned but never referenced anywhere in the script. Dead code.
**Fix:** Remove line 48.

### IN-02: restore-verify CronJob still pins `bitnami/kubectl:latest` (IMG-04 "no latest tags" invariant)

**File:** `infra/helm/clubcore/templates/restore-verify-cronjob.yaml:112,143`
**Issue:** Both the `wait-for-cnpg` initContainer and the `restore-verify` container use
`image: "bitnami/kubectl:latest"`. The repo-wide IMG-04 invariant (build-images.sh:4,
_helpers.tpl `required` guards) is "every deployment pins an explicit immutable tag — no
latest tags." `:latest` is mutable and risks kubectl-version skew against the cluster.
CR-02 pinned the backup jobs but left this template on `:latest`.
**Fix:** Pin a specific tag, e.g. `bitnami/kubectl:1.30.5` (or a values-driven
`.Values.backup.restoreVerify.kubectlImage`), matching the cluster's kubectl minor.

### IN-03: Weak default password literal in the standalone restore-verify script

**File:** `infra/scripts/restore-verify.sh:146`
**Issue:** `--from-literal=password="${DB_PASSWORD:-clubcore-scratch-verify-pw}"` embeds a
hard-coded fallback password. This is the *standalone* script path (local k3d operator
use) and the scratch cluster is ephemeral + isolated, so blast radius is low — but a
hard-coded credential string is a smell. The production CronJob path correctly uses a bare
`${DB_PASSWORD}` under `set -u` (fails closed if the secret is missing — keep that). Note
the scratch app-user password is effectively cosmetic: the `psql -U app` exec runs over
the in-pod local socket (CNPG trust/peer auth), so neither value gates the count query.
**Fix:** Drop the literal fallback and let `set -u` fail closed in the script too:
`--from-literal=password="${DB_PASSWORD:?DB_PASSWORD must be set}"`.

---

_Reviewed: 2026-06-16T13:03:11Z_
_Reviewer: Claude (gsd-code-reviewer)_
_Depth: standard_

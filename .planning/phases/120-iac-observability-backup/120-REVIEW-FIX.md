---
phase: 120-iac-observability-backup
fixed_at: 2026-06-16T00:00:00Z
review_path: .planning/phases/120-iac-observability-backup/120-REVIEW.md
iteration: 1
findings_in_scope: 10
fixed: 10
skipped: 0
status: all_fixed
---

# Phase 120: Code Review Fix Report

**Fixed at:** 2026-06-16
**Source review:** .planning/phases/120-iac-observability-backup/120-REVIEW.md
**Iteration:** 1

**Summary:**
- Findings in scope (critical + warning): 10
- Fixed: 10
- Skipped: 0
- Out of scope (info, not addressed): 3 (IN-01, IN-02, IN-03)

**Tooling note:** helm / k3d / terraform are NOT installed in this environment, so no
`helm template` / `terraform validate` / live `kubectl apply --dry-run` evidence could be
produced. Verification was done by static reasoning, `bash -n` on the standalone script,
`sh -n` on the extracted (de-dented) CronJob command bodies, the `sed` dedent for CR-01
exercised against a sample heredoc, and PyYAML structural parsing of alertmanager-rules.yaml.

## Fixed Issues

### CR-01: Inlined restore-verify cronjob pipes invalid (indented) YAML to `kubectl apply`

**Files modified:** `infra/helm/clubcore/templates/restore-verify-cronjob.yaml`
**Commit:** 3bc2409c
**Applied fix:** Piped the 18-space-indented heredoc through `sed -e 's/^                  //'`
before `kubectl apply -f -`, stripping the common 18-space prefix so the scratch Cluster's
top-level keys (apiVersion/kind/metadata/spec) land at column 0 while nested keys keep their
relative 2-space increments. Verified the dedent against a sample heredoc — top-level keys
render at column 0.

### CR-02: Backup CronJobs run `apk add` against a read-only root filesystem

**Files modified:** `infra/docker/backup.Dockerfile` (new), `infra/scripts/build-images.sh`,
`infra/helm/clubcore/templates/_helpers.tpl`, `infra/helm/clubcore/values.yaml`,
`infra/helm/clubcore/templates/backup-redis-cronjob.yaml`,
`infra/helm/clubcore/templates/backup-seaweedfs-cronjob.yaml`
**Commit:** 16f7cc9e
**Applied fix:** Created a purpose-built `clubcore/backup` image (alpine + `redis` for
redis-cli, `aws-cli`, `coreutils`) that PRE-BAKES the required CLIs, wired it as a 4th
component into `build-images.sh`, added a `clubcore.backupImage` helper + `backup.image`
values key (shares the global git-SHA `image.tag`), and replaced both CronJobs' images and
removed the runtime `apk add aws-cli`. Replaced the install step with a `command -v`
preflight assertion. SEC-03 `readOnlyRootFilesystem: true` + TZ=UTC preserved. This is the
strongly-preferred reproducible approach (no writable emptyDir over apk paths). The image
build itself was not exercised (docker not run here).

### CR-03: Row-count verification uses `pg_class.reltuples` (planner estimate)

**Files modified:** `infra/scripts/restore-verify.sh`,
`infra/helm/clubcore/templates/restore-verify-cronjob.yaml`
**Commit:** 4aab732b
**Applied fix:** Replaced the `SUM(reltuples)` planner-estimate query with an EXACT
`SELECT count(*) FROM users` on both the live and scratch clusters. `users` is a stable core
domain table that is always non-empty in production (the system requires at least one owner
account, seeded at install). Table is overridable via `VERIFY_TABLE` in the standalone
script. **Requires human verification:** confirm `users` is the right always-non-empty table
for the count-equality assertion (a count *mismatch* between live and scratch can be a false
alarm if rows legitimately change between the live snapshot and the scratch restore point —
consider a `>=` tolerance or a point-in-time snapshot if false MISMATCH alerts appear).

### CR-04: `LIVE_COUNT` silently defaults to `0` and `0 == 0` treated as a successful verify

**Files modified:** `infra/scripts/restore-verify.sh`,
`infra/helm/clubcore/templates/restore-verify-cronjob.yaml`
**Commit:** 4aab732b (stacked with CR-03 — same overlapping hunks)
**Applied fix:** Made the verify FAIL CLOSED. Removed the `2>/dev/null || echo "0"` /
`echo "-1"` fallbacks; a failed `kubectl exec`/`psql` now triggers `err` (non-zero exit).
Added `case` guards rejecting empty/non-numeric counts on both live and scratch, and a
hard error when the live count is `0` (the chosen table must be non-empty). A failed or
empty measurement can no longer be reported as a passing restore. **Requires human
verification:** logic/semantic change to the integrity gate's pass/fail behavior.

### WR-01: `local ec=$?` in cleanup trap can clobber the real exit code under `sh`

**Files modified:** `infra/helm/clubcore/templates/restore-verify-cronjob.yaml`
**Commit:** ce211cae
**Applied fix:** In the inlined `/bin/sh` CronJob trap, replaced `local ec=$?` with a
plain `ec=$?` captured on the first line of `cleanup()` (no preceding builtin). The
standalone script (`#!/usr/bin/env bash`) was left as-is — under bash the RHS `$?` is
evaluated before `local` runs, so the bug is specific to the POSIX-sh inlined copy.

### WR-02: Redis BGSAVE completion wait can crash on empty LASTSAVE / miss completion

**Files modified:** `infra/helm/clubcore/templates/backup-redis-cronjob.yaml`
**Commit:** 9757ca0a
**Applied fix:** Replaced the fixed 30-iteration loop with a wall-clock deadline
(`date +%s` + 60s), added a `case` guard that `continue`s on empty/non-numeric `CURRENT_SAVE`
before the `-gt` integer comparison (so a transient empty LASTSAVE no longer aborts the job
under `set -e`), and a post-loop `BGSAVE_DONE` check for the timeout error.

### WR-03: Redis retention prune only honors the WEEKLY window — `RETENTION_DAILY_COUNT` is dead

**Files modified:** `infra/helm/clubcore/templates/backup-redis-cronjob.yaml`,
`infra/helm/clubcore/values.yaml`
**Commit:** 9757ca0a (cronjob) + 48dc65ef (values, stacked)
**Applied fix:** Removed the dead `RETENTION_DAILY_COUNT` env var/value and rewrote the
header + prune comments to document the real contract: a weekly job with a single age-based
28-day cutoff (`RETENTION_WEEKLY_COUNT` weeks) keeping ~4 weekly snapshots. No fictional
daily tier.

### WR-04: SeaweedFS mirror full re-copies into dated dirs → PVC overflow

**Files modified:** `infra/helm/clubcore/templates/backup-seaweedfs-cronjob.yaml`,
`infra/helm/clubcore/values.yaml`
**Commit:** 48dc65ef
**Applied fix:** Changed the mirror to `aws s3 sync --delete` into a single stable
`/mnt/backup/current/` dir (true incremental semantics — only changed objects transfer,
deletions propagate), then snapshot into a dated dir via `cp -al` hardlinks (~0 extra space
for unchanged files). Prune dated snapshots older than `RETENTION_DAYS` (new
`backup.seaweedfs.retentionDays`, default 28); `current/` is never pruned. Updated PVC sizing
guidance to "one live copy + hardlink churn" instead of "N full copies".

### WR-05: `RestoreVerifyJobFailed` hard-codes `namespace="default"`; backup-job failures unalerted

**Files modified:** `infra/observability/alertmanager-rules.yaml`,
`infra/helm/clubcore/templates/backup-redis-cronjob.yaml`,
`infra/helm/clubcore/templates/backup-seaweedfs-cronjob.yaml`
**Commit:** 832848a7
**Applied fix:** Dropped the `namespace="default"` matcher from `RestoreVerifyJobFailed`
(namespace-agnostic; namespace still surfaced in the annotation for triage) and added a new
`KubeBackupJobFailed` rule matching `job_name=~".*(backup-redis|backup-seaweedfs|restore-verify).*"`
so all three backup jobs alert on failure. Updated the `clubcore.io/alert-linkage` annotations
+ OBS-05 header comments in both backup CronJobs to point at `KubeBackupJobFailed`.

### WR-06: `PostgresNoBackupIn25h` never fires when the metric is absent; metric name unverified

**Files modified:** `infra/observability/alertmanager-rules.yaml`
**Commit:** 832848a7 (stacked with WR-05 — same file)
**Applied fix:** Added `or absent(cnpg_collector_last_available_backup_timestamp)` so a
missing metric (no backup yet / collector down / renamed metric) also fires, updated the
summary/description for the no-data case, and added an inline note + verification command to
confirm the exact CNPG 1.27 metric name. **Requires human verification:** the exact metric
name/unit must be confirmed against the installed CNPG collector version before relying on it.

## Skipped Issues

The following INFO findings are out of scope for `fix_scope: critical_warning` and were not
addressed (no source changes made):

### IN-01: `bitnami/kubectl:latest` / `redis:7-alpine` unpinned mutable tags

**File:** `infra/helm/clubcore/templates/restore-verify-cronjob.yaml:112, 143`
**Reason:** Info-tier, out of scope (critical_warning). Note: CR-02 already moved both
backup CronJobs off `redis:7-alpine` onto the SHA-pinned `clubcore/backup` image, so the
remaining unpinned-tag concern is limited to the restore-verify `bitnami/kubectl:latest`
images. A follow-up should pin a digest and prefer a non-Bitnami kubectl image.

### IN-02: Scratch cluster app-user password default diverges between script and cronjob

**File:** `infra/scripts/restore-verify.sh:137` vs `restore-verify-cronjob.yaml:245`
**Reason:** Info-tier, out of scope (critical_warning).

### IN-03: Inlined cronjob duplicates the standalone script instead of mounting it

**File:** `infra/helm/clubcore/templates/restore-verify-cronjob.yaml:190-315`
**Reason:** Info-tier, out of scope (critical_warning). Note: the CR-01/CR-03/CR-04/WR-01
fixes were applied to BOTH copies to keep them in sync, but the underlying duplication remains
(ConfigMap-mount refactor deferred).

---

_Fixed: 2026-06-16_
_Fixer: Claude (gsd-code-fixer)_
_Iteration: 1_

---
phase: 120-iac-observability-backup
reviewed: 2026-06-16T00:00:00Z
depth: standard
files_reviewed: 9
files_reviewed_list:
  - infra/scripts/restore-verify.sh
  - infra/helm/clubcore/templates/restore-verify-cronjob.yaml
  - infra/helm/clubcore/templates/postgres-cluster.yaml
  - infra/helm/clubcore/templates/backup-redis-cronjob.yaml
  - infra/helm/clubcore/templates/backup-seaweedfs-cronjob.yaml
  - infra/terraform/cluster/main.tf
  - infra/terraform/host/main.tf
  - apps/backend/app/main.py
  - infra/observability/alertmanager-rules.yaml
findings:
  critical: 4
  warning: 6
  info: 3
  total: 13
status: issues_found
---

# Phase 120: Code Review Report

**Reviewed:** 2026-06-16
**Depth:** standard
**Files Reviewed:** 9
**Status:** issues_found

## Summary

Reviewed the v4.0 IaC/Observability/Backup phase with focus on correctness + safety.

**The BAK-04 live-cluster safety invariant holds.** I traced both `restore-verify.sh` and the
inlined cronjob: the live cluster is only ever read (`psql ... -c SELECT`, `kubectl get`); the
only `spec.bootstrap.recovery` is applied to a NEW Cluster in a dedicated SCRATCH namespace; and
the cleanup trap deletes only `${SCRATCH_NAMESPACE}`. There is no path that points recovery at the
live DB. Good. The Terraform helm_release `set` blocks use the v3.2.0 list-of-objects syntax,
`backend "local"` is used, and tfvars.example files carry placeholders only.

**However, the restore-verify mechanism does not actually verify what it claims, and two of the
three backup CronJobs cannot run at all.** The four BLOCKERs below all defeat the stated purpose of
the phase (proven, restorable backups):

1. The inlined cronjob's scratch-Cluster manifest is emitted through an un-stripped heredoc, so the
   YAML piped to `kubectl apply` is indented at column 18 — invalid YAML, fails every run.
2. Both the Redis and SeaweedFS CronJobs run `apk add aws-cli` against a `readOnlyRootFilesystem:
   true` container — `apk` cannot write outside `/tmp`, so these jobs fail at startup every run.
3. The row-count "verification" uses `pg_class.reltuples`, a planner estimate that is unset/`-1` on
   a freshly-restored, never-ANALYZEd cluster — so the check produces false matches and false
   mismatches and proves nothing about data integrity.
4. `LIVE_COUNT` falls back to `0` on any silent query failure, and `0 == 0` is treated as a PASS,
   so a broken live snapshot + empty scratch can report a green restore-verify.

## Critical Issues

### CR-01: Inlined restore-verify cronjob pipes invalid (indented) YAML to `kubectl apply`

**File:** `infra/helm/clubcore/templates/restore-verify-cronjob.yaml:250-284`
**Issue:** The scratch CNPG Cluster manifest is produced with `kubectl apply -f - <<SCRATCH_EOF`
(plain heredoc, not `<<-`). Every body line is indented 18 spaces to match the YAML container
nesting, and that leading whitespace is preserved literally and passed to `kubectl`. The resulting
document has its top-level keys (`apiVersion:`, `kind:`, `metadata:`, `spec:`) at column 18:

```
··················apiVersion:·postgresql.cnpg.io/v1
··················kind:·Cluster
··················metadata:
```

A YAML document whose root mapping is uniformly indented is not valid — `kubectl apply` rejects it
(`error parsing ... did not find expected key` / mapping-indent error). Step `[3/6]` therefore fails
on **every** run, the scratch cluster is never created, step `[4/6]` times out after 900s, and the
Job exits non-zero — meaning the restore-verify CronJob is permanently red (or, worse, masks a real
backup problem behind an infrastructure failure). The standalone `infra/scripts/restore-verify.sh`
heredoc (line 146) is correctly authored at column 0, confirming this is a copy-into-template defect.
**Fix:** Use an indentation-stripping heredoc and tab-indent the body, or (preferred) keep the body
at column 0 inside the container command. Simplest robust fix — pipe through `sed` to strip the
fixed indent, or build the manifest at column 0:
```sh
kubectl apply -f - <<SCRATCH_EOF
apiVersion: postgresql.cnpg.io/v1
kind: Cluster
metadata:
  name: ${SCRATCH_CLUSTER_NAME}
  namespace: ${SCRATCH_NAMESPACE}
...
SCRATCH_EOF
```
(i.e. column-0 body lines inside the `command: - |` block — the surrounding `|` block scalar
tolerates the de-dent as long as it is consistent). Verify with `helm template ... | kubectl apply
--dry-run=client` once a cluster is available.

### CR-02: Backup CronJobs run `apk add` against a read-only root filesystem — every run fails

**File:** `infra/helm/clubcore/templates/backup-redis-cronjob.yaml:143-148` and
`infra/helm/clubcore/templates/backup-seaweedfs-cronjob.yaml:171-176`
**Issue:** Both CronJob containers use `clubcore.hardenedSecurityContext` (`_helpers.tpl:76-84`),
which hard-codes `readOnlyRootFilesystem: true`. The very first command in each container is
`apk add --no-cache aws-cli`. `apk` writes to `/var/cache/apk`, `/lib/apk/db`, `/usr/lib`,
`/usr/bin`, etc. — all on the read-only root filesystem. The only writable mount is the `/tmp`
emptyDir. `apk add` will fail with a read-only filesystem error, the `|| { ...; exit 1; }` guard
fires, and the Job exits non-zero on **every** scheduled run. Redis backups (BAK-02) and the
SeaweedFS mirror (BAK-02) therefore never produce a single artifact. The header comments even claim
"`aws-cli` is installed via apk" as the intended design, so this is not an accidental flag — the
design is incompatible with the SEC-03 hardening that is also applied.
**Fix:** Do not install packages at runtime under a read-only rootfs. Pre-bake an image that
already contains `aws-cli` + `redis-cli` (build a small image in `build-images.sh`), or use an
official `amazon/aws-cli` image with `redis-cli` added, or — if runtime install is truly required —
mount an emptyDir over the apk-writable paths AND set `HOME`/`apk --cache-dir` to `/tmp`
(fragile; not recommended). Preferred: ship a purpose-built backup image and reference it via a
values key, keeping `readOnlyRootFilesystem: true`.

### CR-03: Row-count verification uses `pg_class.reltuples` (planner estimate) — proves nothing

**File:** `infra/scripts/restore-verify.sh:106, 242` and
`infra/helm/clubcore/templates/restore-verify-cronjob.yaml:228, 304`
**Issue:** Both the live and scratch "row counts" are computed as
`SELECT SUM(reltuples::bigint) FROM pg_class WHERE relkind='r' ...`. `pg_class.reltuples` is a
**cached planner estimate**, not an actual row count. It is only refreshed by `ANALYZE` / `VACUUM`
(or autovacuum). On a freshly-restored CNPG scratch cluster that has never been analyzed,
`reltuples` is `-1` for every table on PG 14+ (meaning "unknown"), or a stale value carried in the
catalog from the backup. Consequences:
- The scratch sum can be a large negative number (sum of `-1`s) or `0`, which will essentially never
  equal the live cluster's autovacuum-maintained estimates → constant false MISMATCH → constant
  spurious `RestoreVerifyJobFailed` critical alerts (alert fatigue, then ignored).
- If the live cluster's stats are also stale/zero (e.g. small tables), both sides read `0` and the
  check reports a **false PASS** — the headline guarantee of BAK-04 ("the backup is restorable and
  intact") is never actually tested.

Either way the verification does not validate restorability. **Fix:** Either run `ANALYZE` on the
scratch cluster before reading counts AND use exact counts, or — far more robust — compare exact
counts of the actual application tables:
```sql
SELECT json_object_agg(relname, n) FROM (
  SELECT c.relname, (xpath('/row/c/text()',
    query_to_xml(format('SELECT count(*) AS c FROM %I.%I', n.nspname, c.relname),
                 false, true, '')))[1]::text::bigint AS n
  FROM pg_class c JOIN pg_namespace n ON n.oid = c.relnamespace
  WHERE c.relkind='r' AND n.nspname NOT IN ('pg_catalog','information_schema')
    AND n.nspname NOT LIKE 'pg\_%'
) t;
```
or, simpler and sufficient for a smoke test, `count(*)` a few known business tables (clients,
memberships, payments) and assert each scratch count >= live count - epsilon. Exact `count(*)` per
table is the only thing that actually proves the restore replayed data.

### CR-04: `LIVE_COUNT` silently defaults to `0` and `0 == 0` is treated as a successful verify

**File:** `infra/scripts/restore-verify.sh:101-113, 254-261` and
`infra/helm/clubcore/templates/restore-verify-cronjob.yaml:226-230, 312-314`
**Issue:** The live snapshot query ends in `2>/dev/null || echo "0"`. If the `kubectl exec`/`psql`
fails for any reason (RBAC change, pod not labeled primary yet, transient error), `LIVE_COUNT`
becomes `0` and all stderr is discarded. The standalone script logs a WARNING and explicitly
"proceeds" (lines 110-113). The final comparison is `[ "${LIVE_COUNT}" != "${SCRATCH_COUNT}" ]`.
A scratch cluster that restored an empty/un-analyzed DB also reads `0` (see CR-03), so
`0 != 0` is false → the script logs "Row count MATCH" and **exits 0 (PASS)** even though the live
snapshot never succeeded. A failed measurement is being reported as a successful restore
verification — the worst possible failure mode for a backup-integrity gate. **Fix:** Treat an
unobtained live count as a hard error, not a `0` pass-through. Capture exit status explicitly and
fail closed:
```sh
LIVE_COUNT=$(kubectl exec ... -c "...") || err "Live count query failed — cannot verify"
[ -z "${LIVE_COUNT}" ] && err "Live count empty — cannot verify"
# and reject zero unless the DB is genuinely expected to be empty
[ "${LIVE_COUNT}" = "0" ] && err "Live count is 0 — refusing to claim a passing verify"
```
Combined with exact `count(*)` from CR-03, this makes a green result mean something.

## Warnings

### WR-01: `local ec=$?` in cleanup trap can clobber the real exit code under `set -e`/`sh`

**File:** `infra/helm/clubcore/templates/restore-verify-cronjob.yaml:208-214` (and
`infra/scripts/restore-verify.sh:73-84`)
**Issue:** The trap does `cleanup() { local ec=$?; ...; exit "${ec}"; }`. Two problems: (a) the
inlined cronjob runs under `/bin/sh` with `set -euo pipefail`; `local` is not POSIX and in some
`sh` implementations `local ec=$?` evaluates `$?` *after* the `local` builtin has run, capturing
the status of `local` (0) rather than the failing command — silently turning a failure into a
success-coded exit. (b) `bitnami/kubectl` ships bash, so `/bin/sh` may be bash and behave, but this
is implementation-dependent and fragile for a data-safety gate. **Fix:** Capture `$?` on the first
line with no preceding builtin and avoid `local` in `sh`:
```sh
cleanup() {
  ec=$?
  kubectl delete namespace "${SCRATCH_NAMESPACE}" --ignore-not-found=true --timeout=120s || true
  [ "${ec}" -ne 0 ] && echo "FAILURE (exit ${ec})"
  exit "${ec}"
}
```
Confirm the shebang/interpreter actually supports the constructs used.

### WR-02: Redis BGSAVE completion wait can permanently miss completion at exactly i=30

**File:** `infra/helm/clubcore/templates/backup-redis-cronjob.yaml:160-171`
**Issue:** The loop sleeps 2s then checks `LASTSAVE`. On iteration 30 it checks completion first;
if not yet complete it then hits the `if [ "${i}" -eq 30 ]` branch and errors. But the ordering
means the timeout fires after only ~58–60s of waiting, and more importantly if BGSAVE completes on
the very last tick the success `break` is reachable — acceptable — but if `redis-cli LASTSAVE`
transiently returns an empty string (network blip), `[ "${CURRENT_SAVE}" -gt "${BEFORE_SAVE}" ]`
runs `[ -gt ]` on an empty operand and, under `set -e`, the integer comparison errors out, aborting
the whole job with a confusing message. **Fix:** Validate `CURRENT_SAVE` is numeric before the
comparison (`case "$CURRENT_SAVE" in ''|*[!0-9]*) continue ;; esac`) and base the timeout on a wall
clock rather than loop count.

### WR-03: Redis retention prune only honors the WEEKLY window — `RETENTION_DAILY_COUNT` is dead

**File:** `infra/helm/clubcore/templates/backup-redis-cronjob.yaml:199-212`
**Issue:** The header (lines 8-12, 111-115) and the env var `RETENTION_DAILY_COUNT=7` advertise a
"7-daily / 4-weekly" retention scheme. The actual prune computes a single cutoff
`PRUNE_BEFORE = now - RETENTION_WEEKLY_COUNT weeks` (28 days) and deletes everything older. The
daily count is never used; there is no daily-vs-weekly tiering at all. Since the job runs **weekly**
(`0 3 * * 0`), it produces ~1 RDB/week and keeps ~4 of them — the "7 daily" tier is fictional.
This is not a data-loss bug (28d is the outer bound, so it over-keeps relative to the 7-day claim),
but the implementation does not match its documented contract and the daily knob is misleading dead
configuration. **Fix:** Either implement true tiered retention (keep last 7 dailies + 4 weeklies via
tagging), or delete `RETENTION_DAILY_COUNT` and rename the comments/contract to "28-day age-based
retention" to match reality.

### WR-04: SeaweedFS mirror uses `aws s3 sync --delete` into a dated dir, then never reuses it

**File:** `infra/helm/clubcore/templates/backup-seaweedfs-cronjob.yaml:178-195`
**Issue:** Each daily run writes to a fresh empty dir `/mnt/backup/YYYY-MM-DD/` and runs
`aws s3 sync --delete s3://bucket/ <new-empty-dir>/`. Because the destination is always empty, the
`--delete` flag is a no-op and every run re-downloads the **entire** bucket (full copy, not
incremental) into a new dated dir. Over a 28-day window that is up to 28 full copies of the bucket
on a 20Gi PVC sized to hold a single copy ("Size: 20Gi … must be >= total S3 data size", lines
21-23). The PVC will fill and the mirror job will start failing once cumulative dated copies exceed
20Gi — i.e. as soon as the bucket exceeds ~700MB. **Fix:** Sync to a single stable mirror dir
(`/mnt/backup/current/`) for the incremental `--delete` semantics to work, and snapshot/rotate via
hardlink dirs (`cp -al`) or size the PVC for N full copies. At minimum, size guidance must reflect
`retention_days × bucket_size`, not `1 × bucket_size`.

### WR-05: `RestoreVerifyJobFailed` alert hard-codes `namespace="default"`; Redis/SeaweedFS Job failures are not actually alerted

**File:** `infra/observability/alertmanager-rules.yaml:147-162`
**Issue:** Two problems. (a) The alert matches `namespace="default"`, but the CronJobs are deployed
into the Helm release namespace (`.Release.Namespace`), which the chart does not pin to `default`
and the runbook/values treat as variable. If the release is installed into any other namespace the
alert silently never fires. (b) The backup CronJobs (`backup-redis-cronjob.yaml:42-43`,
`backup-seaweedfs-cronjob.yaml:74-75`) claim "OBS-05 linkage: Job failure surfaces as
kube_job_status_failed … RestoreVerifyJobFailed alert watches" — but the alert's job_name regex is
`.*restore-verify.*`, which does **not** match `*-backup-redis` or `*-backup-seaweedfs`. So a failed
Redis or SeaweedFS backup Job fires **no** alert at all, contradicting the documented linkage. Given
CR-02 guarantees those jobs fail on every run, this means silent, unmonitored backup failure.
**Fix:** Parameterize the namespace (or drop the `namespace=` matcher), and add a general
`KubeBackupJobFailed` rule matching `job_name=~".*(backup-redis|backup-seaweedfs|restore-verify).*"`
so all three backup jobs surface failures.

### WR-06: `PostgresNoBackupIn25h` will fire 25h after enable even when backups are healthy, and metric name is unverified

**File:** `infra/observability/alertmanager-rules.yaml:129-142`
**Issue:** The expression `(time() - cnpg_collector_last_available_backup_timestamp) > 25h`. (a) If
the metric is absent (e.g. before the first backup, or if the CNPG collector does not expose this
exact series), the expression yields no samples and the alert simply never fires — a missing-backup
condition that produces no alert is a monitoring gap; an `absent()` companion clause is needed. (b)
The metric name `cnpg_collector_last_available_backup_timestamp` is asserted in a comment but not
verified against the installed CNPG version (1.27); CNPG has renamed backup metrics across releases
(`cnpg_collector_first_recoverability_point` / `last_available_backup_timestamp` exist in some
versions, gauges vs unix-ts differ). A typo'd metric name yields a permanently silent alert.
**Fix:** Add `or absent(cnpg_collector_last_available_backup_timestamp{...})` to catch the
no-data case, and confirm the exact metric name + unit against the CNPG 1.27 collector before
relying on it.

## Info

### IN-01: `bitnami/kubectl:latest` / `redis:7-alpine` (implicit latest) are unpinned mutable tags

**File:** `infra/helm/clubcore/templates/restore-verify-cronjob.yaml:112, 143`
**Issue:** The restore-verify init + main containers use `image: "bitnami/kubectl:latest"`. `latest`
is mutable and non-reproducible; a future Bitnami change (or the well-publicized Bitnami repo
relicensing/retirement, which this very project cites as the reason for dropping Bitnami Postgres in
`D-V40-BITNAMI-PAYWALLED`) can break the job silently or pull a changed CNPG/kubectl contract.
**Fix:** Pin a digest or explicit version, and prefer a non-Bitnami `kubectl` image consistent with
the project's stated Bitnami-avoidance decision.

### IN-02: Scratch cluster app-user password default diverges between script and cronjob

**File:** `infra/scripts/restore-verify.sh:137` vs
`infra/helm/clubcore/templates/restore-verify-cronjob.yaml:245`
**Issue:** The standalone script defaults the scratch app password to
`${DB_PASSWORD:-clubcore-scratch-verify-pw}`, while the cronjob uses `${DB_PASSWORD}` with no
default (relying on `set -u` to abort if unset). The behaviors differ; the script's hard-coded
fallback is also a (weak) credential literal in a tracked file. Since CNPG recovery resets the app
role password from the provided secret, the value only matters for the post-restore `psql -U app`
connection in step 5 — but the divergence is a latent inconsistency. **Fix:** Make both fail closed
on a missing `DB_PASSWORD` (no literal fallback), or document that the scratch role password is
irrelevant because the row-count `psql` runs via in-pod exec (peer auth).

### IN-03: Inlined cronjob duplicates the standalone script instead of mounting it

**File:** `infra/helm/clubcore/templates/restore-verify-cronjob.yaml:190-315`
**Issue:** The cronjob inlines a near-verbatim re-implementation of `infra/scripts/restore-verify.sh`
(the template even comments "mirrors infra/scripts/restore-verify.sh"). The two copies have already
drifted (CR-01 only affects the inlined copy; IN-02 differs; the script has a 6-step
pre-existing-namespace recreate that the inline version handles differently). The ConfigMap-mount
approach is half-scaffolded but commented out (lines 103-105). Maintaining two copies of a
data-safety-critical script guarantees future drift. **Fix:** Mount the single canonical
`restore-verify.sh` via ConfigMap and `command: ["bash","/scripts/restore-verify.sh"]`, deleting the
inlined duplicate.

---

_Reviewed: 2026-06-16_
_Reviewer: Claude (gsd-code-reviewer)_
_Depth: standard_

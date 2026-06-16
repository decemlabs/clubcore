# Postgres + Redis + SeaweedFS Restore Runbook

**Requirement:** BAK-03 / BAK-04
**Risk level:** CRITICAL — incorrect restore procedure can overwrite live data or leave a silent gap in recovery capability

---

## Why This Matters

Backups are only real if restore is proven. This runbook covers the verified restore round-trip
for all three persistent stores:

1. **Postgres** — CNPG WAL archiving + daily base backup to SeaweedFS S3 (barmanObjectStore)
2. **Redis** — weekly RDB snapshot to SeaweedFS S3 (backup-redis-cronjob.yaml)
3. **SeaweedFS** — daily mirror to a second PVC (backup-seaweedfs-cronjob.yaml)

The **BAK-04 differentiator** is the weekly restore-verify CronJob (restore-verify-cronjob.yaml)
which actually restores the latest Postgres backup into a SCRATCH cluster and row-count-checks it.
If the row count does not match the live snapshot, the Job exits non-zero and the OBS-05
`RestoreVerifyJobFailed` alert fires in Alertmanager (Telegram notification).

> **OPERATOR-PENDING:** The live restore round-trip and the BAK-04 CronJob real run both require
> a k3d cluster with CNPG operator, SeaweedFS, and `backup.enabled=true` applied.
> This step cannot be performed in the build sandbox. It MUST be completed by the operator
> before marking BAK-03 as closed.

> **SAFETY INVARIANT (T-120-BAK2):** The restore-verify procedure ALWAYS restores into a
> SCRATCH namespace/cluster. NEVER run `spec.bootstrap.recovery` against the live cluster.
> The live cluster (`clubcore-postgres` in the `default` namespace) must NEVER be a recovery
> target. This is enforced in `restore-verify.sh` and `restore-verify-cronjob.yaml`.

---

## BAK-03 / BAK-04 Hard Gate — Acceptance Criteria

These gates MUST be closed before marking BAK-03 complete:

- [ ] Postgres: `helm template ... --set backup.enabled=true | grep barmanObjectStore` renders correctly with SeaweedFS endpoint + existing S3 secret refs (no new secret)
- [ ] Postgres: at least one completed `Backup` object exists in the cluster after enabling `backup.enabled=true` (`kubectl get backup`)
- [ ] Postgres: restore to SCRATCH succeeds — scratch cluster becomes Ready, row counts match
- [ ] Redis: at least one RDB snapshot object exists in `s3://clubcore/redis/` after the weekly CronJob runs
- [ ] Redis: RDB restore applied to a test Redis instance — key count matches
- [ ] SeaweedFS: at least one dated directory exists in the mirror PVC after the daily CronJob runs
- [ ] SeaweedFS: objects in the mirror PVC are complete and match S3 content
- [ ] BAK-04: `kubectl create job --from=cronjob/<release>-restore-verify verify-now` runs to completion without touching the live cluster
- [ ] BAK-04: simulate a backup gap → confirm `PostgresNoBackupIn25h` alert fires in Alertmanager

Do NOT mark BAK-03 as complete until all checkboxes are ticked.

---

## BAK-04 RBAC Setup (Operator-Install Prerequisite)

The `restore-verify-cronjob.yaml` pod needs a ServiceAccount with ClusterRole permissions to:
- Create/delete namespaces (`clubcore-restore-verify-scratch`)
- Create/delete `postgresql.cnpg.io/clusters` in the scratch namespace
- Create Secrets (copy S3 creds + DB password into scratch namespace)
- Exec into pods (`kubectl exec` for psql row-count queries)

```bash
# Create the ServiceAccount + ClusterRoleBinding for restore-verify
# Run once before enabling backup.restoreVerify.enabled=true

kubectl apply -f - <<'EOF'
apiVersion: v1
kind: ServiceAccount
metadata:
  name: clubcore-restore-verify-sa
  namespace: default
  labels:
    app.kubernetes.io/component: restore-verify
    clubcore.io/requirement: BAK-04
---
apiVersion: rbac.authorization.k8s.io/v1
kind: ClusterRole
metadata:
  name: clubcore-restore-verify
rules:
  # Manage scratch namespace
  - apiGroups: [""]
    resources: ["namespaces"]
    verbs: ["create", "delete", "get"]
  # Create Secrets in scratch namespace
  - apiGroups: [""]
    resources: ["secrets"]
    verbs: ["create", "delete", "get"]
  # Create/delete CNPG Clusters in scratch namespace
  - apiGroups: ["postgresql.cnpg.io"]
    resources: ["clusters"]
    verbs: ["create", "delete", "get", "list", "watch"]
  # Exec into pods for psql row-count queries
  - apiGroups: [""]
    resources: ["pods/exec"]
    verbs: ["create"]
  - apiGroups: [""]
    resources: ["pods"]
    verbs: ["get", "list"]
---
apiVersion: rbac.authorization.k8s.io/v1
kind: ClusterRoleBinding
metadata:
  name: clubcore-restore-verify
roleRef:
  apiGroup: rbac.authorization.k8s.io
  kind: ClusterRole
  name: clubcore-restore-verify
subjects:
  - kind: ServiceAccount
    name: clubcore-restore-verify-sa
    namespace: default
EOF

# Expected:
#   serviceaccount/clubcore-restore-verify-sa created
#   clusterrole.rbac.authorization.k8s.io/clubcore-restore-verify created
#   clusterrolebinding.rbac.authorization.k8s.io/clubcore-restore-verify created
```

Then enable the CronJob:

```bash
helm upgrade clubcore infra/helm/clubcore \
  --set backup.restoreVerify.enabled=true \
  --set backup.restoreVerify.serviceAccountName=clubcore-restore-verify-sa \
  --set image.tag=$(git rev-parse --short HEAD)

# Expected: CronJob clubcore-restore-verify created
```

---

## Step 1 — Enable Backups

Prerequisites: SeaweedFS running, `clubcore` bucket exists, S3 creds sealed.

```bash
# Verify SeaweedFS S3 endpoint is reachable
kubectl run s3-probe --image=curlimages/curl:latest --restart=Never --rm -it \
  -- curl -s http://clubcore-seaweedfs-s3:8333/ | head -5
# Expected: XML response from SeaweedFS S3 API (may show AccessDenied — that is correct)

# Enable backups (backup.enabled=true activates barmanObjectStore + all CronJobs)
helm upgrade clubcore infra/helm/clubcore \
  --set backup.enabled=true \
  --set image.tag=$(git rev-parse --short HEAD)

# Expected: helm upgrade succeeded; ScheduledBackup + CronJobs created
kubectl get scheduledbackup,cronjob
```

---

## Step 2 — Verify CNPG barmanObjectStore Renders Correctly

```bash
# Confirm barmanObjectStore block renders with correct SeaweedFS endpoint and existing S3 secret
helm template infra/helm/clubcore \
  --set backup.enabled=true \
  --set image.tag=dummy \
  | grep -A 25 barmanObjectStore

# Expected output (key fields):
#   barmanObjectStore:
#     destinationPath: "s3://clubcore/postgres"
#     endpointURL: "http://clubcore-seaweedfs-s3:8333"
#     s3Credentials:
#       accessKeyId:
#         name: clubcore-app-secret
#         key: S3_ACCESS_KEY_ID
#       secretAccessKey:
#         name: clubcore-app-secret
#         key: S3_SECRET_ACCESS_KEY
#     wal:
#       compression: gzip
#     data:
#       compression: gzip
#     retentionPolicy: "30d"
```

---

## Step 3 — Postgres Restore Round-Trip (BAK-03 Gate)

This is the BAK-03 acceptance gate. Run it ONCE on a k3d cluster with a working backup.

```bash
# 1. Check a completed base backup exists
kubectl get backup -n default
# Expected: at least one Backup with status.phase: completed

# 2. Trigger a manual backup (do not wait for the scheduled 02:00 run)
kubectl cnpg backup clubcore-postgres --method barmanObjectStore
# Expected: Backup object created; status.phase transitions to completed within ~5 minutes

# 3. Verify objects landed in SeaweedFS
kubectl run s3-ls --image=amazon/aws-cli:latest --restart=Never --rm -it \
  --env AWS_ACCESS_KEY_ID=<your-key> \
  --env AWS_SECRET_ACCESS_KEY=<your-secret> \
  -- aws s3 ls s3://clubcore/postgres/ --endpoint-url http://clubcore-seaweedfs-s3:8333
# Expected: WAL segments + base backup directory listed

# 4. Run the verified restore round-trip manually
LIVE_CLUSTER_NAME=clubcore-postgres \
LIVE_NAMESPACE=default \
S3_ENDPOINT_URL=http://clubcore-seaweedfs-s3:8333 \
S3_BUCKET=clubcore \
S3_ACCESS_KEY_ID=<your-key> \
S3_SECRET_ACCESS_KEY=<your-secret> \
DB_NAME=clubcore \
DB_OWNER=app \
DB_PASSWORD=<db-password> \
  bash infra/scripts/restore-verify.sh

# Expected output (key lines):
#   [restore-verify] === clubcore restore-verify ===
#   [1/6] Live row count: <N>
#   [2/6] Creating SCRATCH namespace clubcore-restore-verify-scratch...
#   [3/6] Applying SCRATCH Cluster with spec.bootstrap.recovery...
#   [4/6] Scratch cluster Ready
#   [5/6] Live: <N>  Scratch: <N>
#   [6/6] Row count MATCH: <N> rows
#   [restore-verify] === restore-verify PASSED ===
#   [restore-verify] Cleanup: deleting scratch namespace...
#   [restore-verify] SUCCESS: scratch cluster torn down cleanly
```

---

## Step 4 — Redis RDB Restore

```bash
# 1. Verify a weekly RDB backup exists in SeaweedFS
kubectl run s3-ls-redis --image=amazon/aws-cli:latest --restart=Never --rm -it \
  --env AWS_ACCESS_KEY_ID=<your-key> \
  --env AWS_SECRET_ACCESS_KEY=<your-secret> \
  -- aws s3 ls s3://clubcore/redis/ --endpoint-url http://clubcore-seaweedfs-s3:8333
# Expected: redis-rdb-YYYYMMDD-HHMMSS.rdb object listed

# 2. Download the latest RDB snapshot
kubectl run s3-get-redis --image=amazon/aws-cli:latest --restart=Never --rm -it \
  --env AWS_ACCESS_KEY_ID=<your-key> \
  --env AWS_SECRET_ACCESS_KEY=<your-secret> \
  -- aws s3 cp s3://clubcore/redis/redis-rdb-<timestamp>.rdb /tmp/restore.rdb \
     --endpoint-url http://clubcore-seaweedfs-s3:8333
# Expected: download completed

# 3. Apply the RDB to a test Redis instance
# (DO NOT replace the live Redis PVC — use a separate pod for verification)
kubectl run redis-restore-test --image=redis:7-alpine --restart=Never \
  -- redis-server --dir /tmp --dbfilename restore.rdb --save ""
kubectl cp /tmp/restore.rdb redis-restore-test:/tmp/restore.rdb
kubectl exec redis-restore-test -- redis-cli DBSIZE
# Expected: non-zero key count matching the pre-backup DBSIZE

# 4. Clean up
kubectl delete pod redis-restore-test
```

---

## Step 5 — SeaweedFS Mirror Restore

```bash
# 1. Verify daily mirror directory exists on the second PVC
kubectl run pvc-ls --image=busybox:latest --restart=Never \
  --overrides='{"spec":{"volumes":[{"name":"backup","persistentVolumeClaim":{"claimName":"clubcore-seaweedfs-mirror-backup"}}],"containers":[{"name":"pvc-ls","image":"busybox","command":["ls","-la","/mnt/backup"],"volumeMounts":[{"name":"backup","mountPath":"/mnt/backup"}]}]}}'
kubectl logs pvc-ls
# Expected: dated directories (YYYY-MM-DD) listed

# 2. Verify object count matches SeaweedFS S3 content
kubectl run pvc-count --image=busybox:latest --restart=Never \
  --overrides='{"spec":{"volumes":[{"name":"backup","persistentVolumeClaim":{"claimName":"clubcore-seaweedfs-mirror-backup"}}],"containers":[{"name":"pvc-count","image":"busybox","command":["find","/mnt/backup/<date>","-type","f"],"volumeMounts":[{"name":"backup","mountPath":"/mnt/backup"}]}]}}'
kubectl logs pvc-count | wc -l
# Expected: object count matches `aws s3 ls s3://clubcore/ --recursive | wc -l`

# 3. Clean up
kubectl delete pod pvc-ls pvc-count
```

---

## Step 6 — BAK-04 CronJob Verification (Automated Restore-Verify)

```bash
# 1. Ensure backup.restoreVerify.enabled=true and RBAC is configured (see BAK-04 RBAC Setup)
kubectl get cronjob clubcore-restore-verify
# Expected: CronJob listed with schedule "0 5 * * 1"

# 2. Trigger a manual run (do not wait for Monday 05:00 UTC)
kubectl create job --from=cronjob/clubcore-restore-verify verify-manual-$(date +%s) -n default
# Expected: Job created

# 3. Watch the Job run
kubectl get job,pod -l app.kubernetes.io/component=restore-verify -w
# Expected: Pod starts, runs, completes successfully

# 4. Check logs
kubectl logs -l app.kubernetes.io/component=restore-verify --tail=50
# Expected (key lines):
#   [restore-verify] [6/6] Row count MATCH: <N> rows
#   [restore-verify] === restore-verify PASSED ===

# 5. Verify the SCRATCH namespace was cleaned up
kubectl get namespace clubcore-restore-verify-scratch
# Expected: Error from server (NotFound) — scratch namespace was deleted

# 6. Simulate a backup gap to verify OBS-05 alert fires
# Stop the ScheduledBackup for >25h, then check Alertmanager for PostgresNoBackupIn25h
kubectl patch scheduledbackup clubcore-postgres-daily \
  --type=merge -p '{"spec":{"suspend":true}}'
# Wait 25+ hours, then:
# kubectl get prometheusrule -n monitoring | grep restore-verify
# Confirm Alertmanager received the alert and delivered it to Telegram
# Then re-enable:
kubectl patch scheduledbackup clubcore-postgres-daily \
  --type=merge -p '{"spec":{"suspend":false}}'
```

---

## Step 7 — Point-in-Time Recovery (Advanced)

CNPG supports point-in-time recovery (PITR) via the `recoveryTarget.targetTime` field.
This is useful for recovering to a state before a destructive operation.

```bash
# Recover the Postgres cluster to a specific point in time
# (Run in a SCRATCH namespace — NEVER against the live cluster)

# 1. Determine the recovery target time (ISO 8601, UTC)
TARGET_TIME="2026-06-15T10:00:00Z"

# 2. Modify the scratch Cluster manifest (see restore-verify.sh for the full template):
#    spec.bootstrap.recovery.recoveryTarget.targetTime: "2026-06-15T10:00:00Z"

# 3. Apply to the scratch namespace and wait for Ready (as in Step 3 above)
# 4. Verify the recovered data is correct for the target time
# 5. If promoting to live: follow the full CNPG cluster promotion procedure
#    (out of scope for this runbook — consult CNPG docs for live cluster promotion)

# Expected: scratch cluster restores to the WAL state at TARGET_TIME
```

---

## Quick Reference — Key Commands

```bash
# Check backup status
kubectl get backup,scheduledbackup -n default

# Trigger manual base backup
kubectl cnpg backup clubcore-postgres --method barmanObjectStore

# Run restore-verify manually
kubectl create job --from=cronjob/clubcore-restore-verify verify-now -n default

# Check CronJob history
kubectl get jobs -n default | grep restore-verify

# List backup objects in SeaweedFS
aws s3 ls s3://clubcore/postgres/ \
  --endpoint-url http://clubcore-seaweedfs-s3:8333 \
  --recursive

# Run restore-verify.sh directly
bash infra/scripts/restore-verify.sh
```

---

## Security Notes

| Item | Requirement |
|------|-------------|
| S3 credentials | Reuse existing `clubcore-app-secret` keys — NEVER mint new credentials (T-120-BAK1) |
| Restore target | ALWAYS scratch namespace — NEVER the live cluster (T-120-BAK2) |
| RBAC scope | Minimal: create/delete namespace + CNPG Cluster + exec into pods only (T-120-BAK3) |
| Alert coverage | OBS-05: `PostgresNoBackupIn25h` + `RestoreVerifyJobFailed` — silent failures surface (T-120-BAK4) |
| Retention | 7-daily / 4-weekly for Redis RDB; 30d for CNPG WAL (BAK-02) |

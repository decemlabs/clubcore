#!/usr/bin/env bash
# restore-verify.sh — Restore the latest CNPG backup to a SCRATCH cluster and row-count-verify.
#
# Responsibilities:
#   1. Capture a pre-restore row-count snapshot from the LIVE cluster (read-only).
#   2. Restore the latest CNPG barmanObjectStore backup into a SCRATCH namespace/cluster.
#   3. Wait for the scratch cluster to become healthy.
#   4. Run the same row-count query on the scratch cluster.
#   5. Compare counts and exit non-zero (alerting) on any mismatch.
#   6. Tear down the scratch namespace/cluster (always — even on failure).
#
# CRITICAL INVARIANT — T-120-BAK2:
#   Restores ONLY to a SCRATCH namespace/cluster via spec.bootstrap.recovery on a NEW Cluster.
#   NEVER runs spec.bootstrap.recovery against the live cluster.
#   The live cluster (clubcore-postgres) is NEVER modified by this script.
#
# Prerequisites:
#   - kubectl  >= 1.28 (access to the live cluster)
#   - CNPG operator installed (postgresql.cnpg.io/v1 CRD must exist)
#   - RBAC: the calling ServiceAccount must be allowed to create/delete:
#       namespaces, postgresql.cnpg.io/clusters, secrets (copy of the S3 creds into scratch ns)
#   - The CNPG barmanObjectStore backup must have at least one completed base backup in S3.
#   - Environment variables (set by the CronJob via secretKeyRef):
#       LIVE_CLUSTER_NAME     - name of the live CNPG Cluster (e.g. clubcore-postgres)
#       LIVE_NAMESPACE        - namespace of the live cluster (e.g. default)
#       S3_ENDPOINT_URL       - SeaweedFS in-cluster S3 endpoint
#       S3_BUCKET             - S3 bucket name (e.g. clubcore)
#       S3_ACCESS_KEY_ID      - SeaweedFS S3 access key (from clubcore-app-secret)
#       S3_SECRET_ACCESS_KEY  - SeaweedFS S3 secret key (from clubcore-app-secret)
#       DB_NAME               - database name to row-count (e.g. clubcore)
#       DB_OWNER              - database owner / app user (e.g. app)
#       DB_PASSWORD           - database password for the scratch cluster app user
#
# Usage:
#   # Run locally against a k3d cluster (operator-pending):
#   LIVE_CLUSTER_NAME=clubcore-postgres LIVE_NAMESPACE=default \
#     bash infra/scripts/restore-verify.sh
#
#   # Invoked by restore-verify-cronjob.yaml weekly:
#   # Env vars are injected from secretKeyRef; no manual invocation needed.
#
# Composable: intended to be called from the restore-verify CronJob (Phase 120 BAK-04).
# To run standalone in k3d: ensure kubectl has in-cluster permissions for the scratch namespace.

set -euo pipefail

# ── Configuration ─────────────────────────────────────────────────────────────
LIVE_CLUSTER_NAME="${LIVE_CLUSTER_NAME:-clubcore-postgres}"
LIVE_NAMESPACE="${LIVE_NAMESPACE:-default}"
SCRATCH_NAMESPACE="clubcore-restore-verify-scratch"
SCRATCH_CLUSTER_NAME="clubcore-restore-scratch"
DB_NAME="${DB_NAME:-clubcore}"
DB_OWNER="${DB_OWNER:-app}"
S3_BUCKET="${S3_BUCKET:-clubcore}"

# ── Helpers ───────────────────────────────────────────────────────────────────
log()   { echo "[restore-verify] $*"; }
err()   { echo "[restore-verify] ERROR: $*" >&2; exit 1; }
step()  { echo "[restore-verify] ── Step $* ──"; }

check_prereq() {
    local cmd="$1"
    if ! command -v "${cmd}" >/dev/null 2>&1; then
        err "'${cmd}' is not installed or not in PATH.
  Install kubectl: https://kubernetes.io/docs/tasks/tools/
  Ensure CNPG operator is running: kubectl get deploy -n cnpg-system"
    fi
}

# ── Cleanup trap — ALWAYS tear down scratch, even on failure ─────────────────
# T-120-BAK2: the scratch namespace is ephemeral; the live cluster is NEVER touched.
cleanup() {
    local exit_code=$?
    log "Cleanup: tearing down scratch namespace ${SCRATCH_NAMESPACE} (exit_code=${exit_code})"
    kubectl delete namespace "${SCRATCH_NAMESPACE}" --ignore-not-found=true --timeout=120s \
      2>/dev/null || log "WARNING: scratch namespace deletion timed out — manual cleanup may be needed"
    if [ "${exit_code}" -ne 0 ]; then
        log "FAILURE: restore-verify exited with non-zero status ${exit_code}"
        log "  OBS-05 alert: kube_job_status_failed will fire (RestoreVerifyJobFailed rule)"
        exit "${exit_code}"
    fi
    log "SUCCESS: scratch cluster torn down cleanly"
}
trap cleanup EXIT

# ── Pre-flight ────────────────────────────────────────────────────────────────
log "=== clubcore restore-verify ==="
log "Live cluster: ${LIVE_CLUSTER_NAME} in namespace ${LIVE_NAMESPACE}"
log "Scratch target: ${SCRATCH_CLUSTER_NAME} in namespace ${SCRATCH_NAMESPACE}"

check_prereq kubectl

# Confirm CNPG CRD is present
kubectl get crd clusters.postgresql.cnpg.io >/dev/null 2>&1 \
  || err "CNPG CRD clusters.postgresql.cnpg.io not found — is the CNPG operator installed?"

# ── Step 1: Capture live row-count snapshot ───────────────────────────────────
# CR-03: use an EXACT count(*) of a stable, always-non-empty core table (users —
# the system always has at least one owner account, seeded at install). The
# previous pg_class.reltuples sum is a planner ESTIMATE that is unset/-1 on a
# freshly-restored, never-ANALYZEd cluster, so it proved nothing about restorability.
# CR-04: FAIL CLOSED — a failed/empty/non-numeric/zero live count is a hard error,
# NOT a silent default of 0 that can later "match" an empty scratch DB (false PASS).
VERIFY_TABLE="${VERIFY_TABLE:-users}"
step "1/6 — Capture live row-count snapshot from ${LIVE_CLUSTER_NAME} (READ-ONLY)"
log "Connecting to live cluster read-write service: ${LIVE_CLUSTER_NAME}-rw.${LIVE_NAMESPACE}"
LIVE_COUNT=$(kubectl exec -n "${LIVE_NAMESPACE}" \
  "$(kubectl get pod -n "${LIVE_NAMESPACE}" \
     -l cnpg.io/cluster="${LIVE_CLUSTER_NAME}",cnpg.io/instanceRole=primary \
     -o jsonpath='{.items[0].metadata.name}')" \
  -- psql -U "${DB_OWNER}" -d "${DB_NAME}" -At \
  -c "SELECT count(*) FROM ${VERIFY_TABLE};") \
  || err "Live count query failed (table ${VERIFY_TABLE}) — cannot verify restorability (FAIL CLOSED)"
log "Live row-count snapshot: ${LIVE_COUNT} rows in ${VERIFY_TABLE}"

# CR-04: reject empty / non-numeric / zero — a measurement we could not obtain (or
# an empty core table) must never be reported as a passing verify.
case "${LIVE_COUNT}" in
    ''|*[!0-9]*) err "Live count empty or non-numeric ('${LIVE_COUNT}') — cannot verify (FAIL CLOSED)" ;;
esac
[ "${LIVE_COUNT}" = "0" ] && err "Live count for ${VERIFY_TABLE} is 0 — refusing to claim a passing verify (FAIL CLOSED)"

# ── Step 2: Create scratch namespace and copy S3 credentials ─────────────────
step "2/6 — Create scratch namespace ${SCRATCH_NAMESPACE}"
if kubectl get namespace "${SCRATCH_NAMESPACE}" >/dev/null 2>&1; then
    log "Scratch namespace ${SCRATCH_NAMESPACE} already exists — deleting and recreating for idempotency"
    kubectl delete namespace "${SCRATCH_NAMESPACE}" --timeout=120s
fi
kubectl create namespace "${SCRATCH_NAMESPACE}"
log "Scratch namespace created: ${SCRATCH_NAMESPACE}"

# Copy the S3 credentials Secret into the scratch namespace so the CNPG Cluster there
# can access the barmanObjectStore backup (T-120-BAK2: credentials flow, not data overwrite).
log "Copying S3 credentials Secret to scratch namespace..."
kubectl create secret generic "${SCRATCH_CLUSTER_NAME}-s3-creds" \
    -n "${SCRATCH_NAMESPACE}" \
    --from-literal=S3_ACCESS_KEY_ID="${S3_ACCESS_KEY_ID}" \
    --from-literal=S3_SECRET_ACCESS_KEY="${S3_SECRET_ACCESS_KEY}"

# Copy the Postgres app-user credentials (same password as live for the schema owner)
kubectl create secret generic "${SCRATCH_CLUSTER_NAME}-app" \
    -n "${SCRATCH_NAMESPACE}" \
    --type=kubernetes.io/basic-auth \
    --from-literal=username="${DB_OWNER}" \
    --from-literal=password="${DB_PASSWORD:-clubcore-scratch-verify-pw}"

# ── Step 3: Apply scratch CNPG Cluster with spec.bootstrap.recovery ───────────
# CRITICAL T-120-BAK2: this creates a NEW Cluster — NEVER spec.bootstrap.recovery
# on the LIVE cluster (${LIVE_CLUSTER_NAME} in ${LIVE_NAMESPACE}).
step "3/6 — Restore to SCRATCH Cluster ${SCRATCH_CLUSTER_NAME} (NEVER the live cluster)"
log "Applying scratch CNPG Cluster with spec.bootstrap.recovery from barmanObjectStore..."

# Note the recoveryTarget.backupID: empty = restore to latest available backup.
cat <<SCRATCH_CLUSTER_EOF | kubectl apply -f -
apiVersion: postgresql.cnpg.io/v1
kind: Cluster
metadata:
  name: ${SCRATCH_CLUSTER_NAME}
  namespace: ${SCRATCH_NAMESPACE}
  labels:
    app.kubernetes.io/managed-by: restore-verify
    clubcore.io/purpose: restore-verify-scratch
  annotations:
    # T-120-BAK2: SCRATCH CLUSTER ONLY — NEVER apply this manifest to the live namespace.
    clubcore.io/safety: "scratch-restore-verify-only"
spec:
  instances: 1
  imageName: "ghcr.io/cloudnative-pg/postgresql:16.6"
  enableSuperuserAccess: false

  bootstrap:
    recovery:
      # externalCluster reference: pull from the barmanObjectStore of the live cluster.
      # This is a NEW cluster recovering from backup — NOT the live cluster.
      source: live-backup-source
      # recoveryTarget: empty = restore to latest completed base backup + replay all WAL.
      # For point-in-time recovery, set: targetTime: "2026-06-15T10:00:00Z"
      # recoveryTarget:
      #   targetTime: ""

  # externalClusters: the barmanObjectStore source (the live cluster's backup location)
  externalClusters:
    - name: live-backup-source
      barmanObjectStore:
        destinationPath: "s3://${S3_BUCKET}/postgres"
        endpointURL: "${S3_ENDPOINT_URL}"
        s3Credentials:
          accessKeyId:
            name: ${SCRATCH_CLUSTER_NAME}-s3-creds
            key: S3_ACCESS_KEY_ID
          secretAccessKey:
            name: ${SCRATCH_CLUSTER_NAME}-s3-creds
            key: S3_SECRET_ACCESS_KEY
        wal:
          compression: gzip
        data:
          compression: gzip

  storage:
    size: "10Gi"
    storageClass: clubcore-retain

  # Disable persistent connections pool for the verify-only scratch cluster
  resources:
    requests:
      cpu: "250m"
      memory: "256Mi"
    limits:
      cpu: "1000m"
      memory: "1Gi"
SCRATCH_CLUSTER_EOF

log "Scratch Cluster ${SCRATCH_CLUSTER_NAME} applied in namespace ${SCRATCH_NAMESPACE}"

# ── Step 4: Wait for scratch cluster to become healthy ────────────────────────
step "4/6 — Wait for scratch cluster to reach Ready state"
log "Polling for ${SCRATCH_CLUSTER_NAME} status.readyInstances = 1 (timeout: 15 min)..."
WAIT_TIMEOUT=900  # 15 minutes
WAIT_ELAPSED=0
POLL_INTERVAL=15
while [ "${WAIT_ELAPSED}" -lt "${WAIT_TIMEOUT}" ]; do
    READY=$(kubectl get cluster "${SCRATCH_CLUSTER_NAME}" \
        -n "${SCRATCH_NAMESPACE}" \
        -o jsonpath='{.status.readyInstances}' 2>/dev/null || echo "0")
    PHASE=$(kubectl get cluster "${SCRATCH_CLUSTER_NAME}" \
        -n "${SCRATCH_NAMESPACE}" \
        -o jsonpath='{.status.phase}' 2>/dev/null || echo "unknown")
    log "  ${WAIT_ELAPSED}s: readyInstances=${READY} phase=${PHASE}"
    if [ "${READY}" = "1" ]; then
        log "Scratch cluster is Ready (phase=${PHASE})"
        break
    fi
    sleep "${POLL_INTERVAL}"
    WAIT_ELAPSED=$((WAIT_ELAPSED + POLL_INTERVAL))
    if [ "${WAIT_ELAPSED}" -ge "${WAIT_TIMEOUT}" ]; then
        err "Scratch cluster did not become Ready within ${WAIT_TIMEOUT}s — restore failed"
    fi
done

# ── Step 5: Row-count check on scratch cluster ────────────────────────────────
step "5/6 — Row-count verification on scratch cluster"
SCRATCH_POD=$(kubectl get pod -n "${SCRATCH_NAMESPACE}" \
    -l "cnpg.io/cluster=${SCRATCH_CLUSTER_NAME},cnpg.io/instanceRole=primary" \
    -o jsonpath='{.items[0].metadata.name}' 2>/dev/null \
    || err "No primary pod found in scratch cluster ${SCRATCH_CLUSTER_NAME}")

log "Running row-count query on scratch cluster pod: ${SCRATCH_POD}"
# CR-03: exact count(*) of the same stable table on the restored scratch cluster.
# CR-04: FAIL CLOSED on a query failure rather than substituting a sentinel that
# could be misread as a legitimate count.
SCRATCH_COUNT=$(kubectl exec -n "${SCRATCH_NAMESPACE}" "${SCRATCH_POD}" \
  -- psql -U "${DB_OWNER}" -d "${DB_NAME}" -At \
  -c "SELECT count(*) FROM ${VERIFY_TABLE};") \
  || err "Row-count query on scratch cluster FAILED — backup may be corrupted or restore incomplete (FAIL CLOSED)"

log "Live row count:    ${LIVE_COUNT}"
log "Scratch row count: ${SCRATCH_COUNT}"

# ── Step 6: Compare and alert on mismatch ────────────────────────────────────
step "6/6 — Compare row counts and exit non-zero on mismatch"
case "${SCRATCH_COUNT}" in
    ''|*[!0-9]*) err "Scratch count empty or non-numeric ('${SCRATCH_COUNT}') — backup may be corrupted or restore incomplete (FAIL CLOSED)" ;;
esac

if [ "${LIVE_COUNT}" != "${SCRATCH_COUNT}" ]; then
    err "ROW COUNT MISMATCH — live: ${LIVE_COUNT} vs scratch: ${SCRATCH_COUNT}
  This indicates the backup is incomplete or the restore did not replay all WAL.
  OBS-05 alert: RestoreVerifyJobFailed will fire.
  Action required: inspect the CNPG backup logs and the scratch cluster restore events.
    kubectl describe cluster ${SCRATCH_CLUSTER_NAME} -n ${SCRATCH_NAMESPACE}
    kubectl logs -n cnpg-system -l app.kubernetes.io/name=cloudnative-pg | tail -50"
fi

log "Row count MATCH confirmed: ${LIVE_COUNT} rows (live) = ${SCRATCH_COUNT} rows (scratch)"
log "=== restore-verify PASSED ==="
log ""
log "Next step: This result is recorded as a successful Job run."
log "  View Job history: kubectl get jobs -n ${LIVE_NAMESPACE} | grep restore-verify"
log "  View logs:        kubectl logs -n ${LIVE_NAMESPACE} -l app.kubernetes.io/component=restore-verify --tail=100"

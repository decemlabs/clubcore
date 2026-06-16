#!/usr/bin/env bash
# k3d-up.sh — Create the local clubcore k3d cluster with all prerequisites.
#
# Responsibilities:
#   1. Create k3d cluster named "clubcore" with a bundled local registry.
#   2. Wait for the cluster node to be Ready.
#   3. Install the CloudNativePG operator (required before Chart applies Cluster CR).
#   4. Wait for the CNPG operator Deployment to be Available.
#   5. Add the SeaweedFS Helm repo and run `helm dependency build`.
#
# Prerequisites:
#   - k3d      >= 5.6 (https://k3d.io — install: curl -s https://raw.githubusercontent.com/k3d-io/k3d/main/install.sh | bash)
#   - helm     >= 3.14 (https://helm.sh — install: curl https://raw.githubusercontent.com/helm/helm/main/scripts/get-helm-3 | bash)
#   - kubectl  (bundled with k3d or install separately)
#   - docker   (running daemon required)
#
# Usage:
#   cd /path/to/clubcore
#   bash infra/scripts/k3d-up.sh
#
# Composable: intended to be called from Phase-121 `make up`.
# To tear down:  k3d cluster delete clubcore

set -euo pipefail

# ── Configuration ─────────────────────────────────────────────────────────────
CLUSTER_NAME="clubcore"
REGISTRY_NAME="${CLUSTER_NAME}-registry"
REGISTRY_PORT="5111"   # local registry port on the host (avoid collision with 5000)

# CNPG operator — v1.27 release manifest (plan 02 SUMMARY decision)
CNPG_MANIFEST="https://raw.githubusercontent.com/cloudnative-pg/cloudnative-pg/release-1.27/releases/cnpg-1.27.0.yaml"
CNPG_NAMESPACE="cnpg-system"

# SeaweedFS Helm repo (plan 02 SUMMARY)
SEAWEEDFS_REPO_NAME="seaweedfs"
SEAWEEDFS_REPO_URL="https://seaweedfs.github.io/seaweedfs/helm"

# Repo root (so the script works from any cwd)
REPO_ROOT="$(git rev-parse --show-toplevel)"
CHART_DIR="${REPO_ROOT}/infra/helm/clubcore"

# ── Helpers ───────────────────────────────────────────────────────────────────
log() { echo "[k3d-up] $*"; }
err() { echo "[k3d-up] ERROR: $*" >&2; exit 1; }

check_prereq() {
    local cmd="$1"
    if ! command -v "${cmd}" >/dev/null 2>&1; then
        err "'${cmd}' is not installed or not in PATH.
  Install:
    k3d    → curl -s https://raw.githubusercontent.com/k3d-io/k3d/main/install.sh | bash
    helm   → curl https://raw.githubusercontent.com/helm/helm/main/scripts/get-helm-3 | bash
    docker → https://docs.docker.com/get-docker/"
    fi
}

# ── Pre-flight ────────────────────────────────────────────────────────────────
log "=== clubcore k3d cluster bring-up ==="
log "Cluster: ${CLUSTER_NAME}  |  Registry: ${REGISTRY_NAME}:${REGISTRY_PORT}"
echo ""

check_prereq k3d
check_prereq helm
check_prereq kubectl
check_prereq docker

# Verify Docker daemon is reachable
if ! docker info >/dev/null 2>&1; then
    err "Docker daemon is not running. Start Docker and retry."
fi

# ── 1. Create k3d cluster with local registry ─────────────────────────────────
if k3d cluster list 2>/dev/null | grep -q "^${CLUSTER_NAME}"; then
    log "[1/5] k3d cluster '${CLUSTER_NAME}' already exists — skipping create."
else
    log "[1/5] Creating k3d cluster '${CLUSTER_NAME}' with registry '${REGISTRY_NAME}' ..."
    k3d cluster create "${CLUSTER_NAME}" \
        --registry-create "${REGISTRY_NAME}:0.0.0.0:${REGISTRY_PORT}" \
        --wait \
        --timeout 120s
    log "      → cluster created"
fi

# ── 2. Wait for node Ready ─────────────────────────────────────────────────────
log "[2/5] Waiting for cluster node Ready ..."
kubectl wait node \
    --selector='!node-role.kubernetes.io/control-plane' \
    --for=condition=Ready \
    --timeout=120s 2>/dev/null || \
kubectl wait node \
    --for=condition=Ready \
    --timeout=120s
log "      → node Ready"

# ── 3. Install CNPG operator ──────────────────────────────────────────────────
if kubectl get deployment/cnpg-controller-manager -n "${CNPG_NAMESPACE}" >/dev/null 2>&1; then
    log "[3/5] CNPG operator already installed — skipping."
else
    log "[3/5] Installing CNPG operator (v1.27) ..."
    log "      Manifest: ${CNPG_MANIFEST}"
    kubectl apply -f "${CNPG_MANIFEST}"
    log "      → CNPG manifests applied"
fi

# ── 4. Wait for CNPG operator Available ───────────────────────────────────────
log "[4/5] Waiting for CNPG operator Deployment Available ..."
kubectl wait deployment/cnpg-controller-manager \
    -n "${CNPG_NAMESPACE}" \
    --for=condition=Available \
    --timeout=120s
log "      → CNPG operator Available"

# ── 5. SeaweedFS Helm repo + helm dependency build ────────────────────────────
log "[5/5] Adding SeaweedFS Helm repo and running dependency build ..."
helm repo add "${SEAWEEDFS_REPO_NAME}" "${SEAWEEDFS_REPO_URL}" --force-update
helm repo update "${SEAWEEDFS_REPO_NAME}"
helm dependency build "${CHART_DIR}"
log "      → helm dependencies vendored into ${CHART_DIR}/charts/"

# ── Done ──────────────────────────────────────────────────────────────────────
echo ""
log "=== k3d cluster '${CLUSTER_NAME}' is ready ==="
echo ""
echo "  Local registry: localhost:${REGISTRY_PORT} (in-cluster: ${REGISTRY_NAME}:5000)"
echo "  CNPG operator:  ${CNPG_NAMESPACE}/cnpg-controller-manager Available"
echo "  Helm deps:      ${CHART_DIR}/charts/ populated"
echo ""
echo "  Next step: bash infra/scripts/deploy-local.sh"

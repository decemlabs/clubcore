#!/usr/bin/env bash
# seal-secrets.sh — kubeseal helper: seal app-secret + export controller RSA key.
#
# SEC-01: encrypts the app-secret keys against the sealed-secrets controller cert
#         so only RSA-encrypted ciphertext is committed to git (not plaintext).
# SEC-02: exports the sealed-secrets controller RSA private key for off-node backup.
#         The controller RSA key is the highest-risk single point of failure in the
#         cluster — loss means all SealedSecrets become unrecoverable on rebuild.
#         See: infra/runbooks/sealed-secrets-key-backup.md
#
# Prerequisites:
#   - sealed-secrets controller v0.37.0 installed in kube-system:
#       helm repo add sealed-secrets https://bitnami-labs.github.io/sealed-secrets
#       helm install sealed-secrets -n kube-system --version 0.37.0 \
#            sealed-secrets/sealed-secrets
#   - kubeseal CLI installed and matching the controller version:
#       brew install kubeseal   OR   https://github.com/bitnami-labs/sealed-secrets/releases
#   - kubectl pointing at the target cluster (verify: kubectl cluster-info)
#   - The plaintext app-secret values ready in a local env file (NOT committed to git).
#
# Usage:
#   cd /path/to/clubcore
#   bash infra/scripts/seal-secrets.sh
#
# Output:
#   - Prints kubeseal encryptedData blocks to stdout (pipe to a values-override.yaml).
#   - Exports the controller RSA private key to a path OUTSIDE the repo (operator instruction).
#   - Prints a LOUD reminder to follow infra/runbooks/sealed-secrets-key-backup.md.
#
# ── NOTE: The kubeseal round-trip (encrypt → apply → controller decrypt) and the
#    off-node key backup CANNOT be completed in the build sandbox (no cluster, no kubeseal).
#    These steps are OPERATOR-PENDING.  See the OPERATOR ACTIONS section below.

set -euo pipefail

# ── Temp-file cleanup (security) ────────────────────────────────────────────────
# One cumulative trap covering EXIT *and* INT/TERM so an ill-timed Ctrl-C never
# orphans the plaintext-secret manifest in /tmp. Vars are pre-declared empty and
# the trap is installed BEFORE any temp file is created; `rm -f ""` is a no-op,
# so the handler is safe to fire at any point.
CERT_FILE=""
PLAINTEXT_SECRET_FILE=""
SEALED_OUTPUT_FILE=""
cleanup() { rm -f "${CERT_FILE}" "${PLAINTEXT_SECRET_FILE}" "${SEALED_OUTPUT_FILE}"; }
trap cleanup EXIT INT TERM

# ── Configuration ─────────────────────────────────────────────────────────────
REPO_ROOT="$(git rev-parse --show-toplevel)"
CHART_DIR="${REPO_ROOT}/infra/helm/clubcore"
CONTROLLER_NAMESPACE="kube-system"
CONTROLLER_LABEL="sealedsecrets.bitnami.com/sealed-secrets-key"
SECRET_NAME_SUFFIX="app-secret"
# Namespace of the target Secret (must match the Helm release namespace).
TARGET_NAMESPACE="${SEALED_NAMESPACE:-default}"
# Helm release name (used to derive the Secret name via clubcore.fullname logic).
RELEASE_NAME="${SEALED_RELEASE:-clubcore}"
# Full Secret name: matches `{{ include "clubcore.fullname" . }}-app-secret` in the template.
SECRET_NAME="${RELEASE_NAME}-${SECRET_NAME_SUFFIX}"

# ── Helpers ───────────────────────────────────────────────────────────────────
log()  { echo "[seal-secrets] $*"; }
ok()   { echo "[seal-secrets] OK: $*"; }
fail() { echo "[seal-secrets] FAIL: $*" >&2; exit 1; }
err()  { echo "[seal-secrets] ERROR: $*" >&2; exit 1; }

# ── check_prereq — abort loudly if a required command is missing ───────────────
check_prereq() {
    local cmd="$1"
    if ! command -v "${cmd}" >/dev/null 2>&1; then
        err "'${cmd}' is not installed or not in PATH.

  Install instructions:
    kubeseal: brew install kubeseal   OR   https://github.com/bitnami-labs/sealed-secrets/releases
    kubectl:  https://kubernetes.io/docs/tasks/tools/

  Ensure the sealed-secrets controller v0.37.0 is running in kube-system:
    helm repo add sealed-secrets https://bitnami-labs.github.io/sealed-secrets
    helm install sealed-secrets -n kube-system --version 0.37.0 sealed-secrets/sealed-secrets"
    fi
}

# ── check_no_key_in_repo — refuse to write the RSA key inside the working tree ─
check_no_key_in_repo() {
    local output_path="$1"
    # Resolve to absolute path for comparison
    local abs_output
    abs_output="$(cd "$(dirname "${output_path}")" 2>/dev/null && pwd)/$(basename "${output_path}")" || true
    if [[ "${abs_output}" == "${REPO_ROOT}/"* ]] || [[ "${abs_output}" == "${REPO_ROOT}" ]]; then
        fail "Refusing to write the controller RSA key inside the git working tree.
  Requested path: ${output_path}
  Repo root:      ${REPO_ROOT}

  The controller RSA private key MUST be stored OFF-NODE and OUTSIDE the git repo.
  Committing it to git defeats the entire sealed-secrets security model.

  Follow the backup checklist:
    cat infra/runbooks/sealed-secrets-key-backup.md"
    fi
}

# ── Pre-flight ─────────────────────────────────────────────────────────────────
log "=== seal-secrets.sh — sealed-secrets v0.37.0 (SEC-01 / SEC-02) ==="
log "Repo root:        ${REPO_ROOT}"
log "Target namespace: ${TARGET_NAMESPACE}"
log "Secret name:      ${SECRET_NAME}"
echo ""

check_prereq kubeseal
check_prereq kubectl

# Verify kubeconfig is reachable
log "Verifying kubectl cluster access ..."
if ! kubectl cluster-info >/dev/null 2>&1; then
    err "kubectl cannot reach the cluster. Verify your kubeconfig:
  kubectl cluster-info
  kubectl config current-context"
fi
ok "kubectl connected to cluster"
echo ""

# ── Step 1: Fetch controller public cert ──────────────────────────────────────
log "[1/4] Fetching sealed-secrets controller public certificate ..."
CERT_FILE="$(mktemp /tmp/sealed-secrets-cert-XXXXXX.pem)"

# kubeseal --fetch-cert retrieves the RSA public certificate from the controller.
# This is the cert used for encryption — it is safe to commit (not the private key).
kubeseal \
    --controller-name sealed-secrets \
    --controller-namespace "${CONTROLLER_NAMESPACE}" \
    --fetch-cert > "${CERT_FILE}"
ok "Controller certificate saved to: ${CERT_FILE}"
echo ""

# ── Step 2: Create and seal a temporary app-secret manifest ───────────────────
# Build a temporary plaintext Secret manifest from environment variables.
# The env vars must be sourced by the operator before running this script.
#
# Required env vars (set these before running — do NOT commit them anywhere):
#   SEAL_SECRET_KEY             → SECRET_KEY
#   SEAL_DATABASE_URL           → DATABASE_URL
#   SEAL_TELEGRAM_BOT_TOKEN     → TELEGRAM_BOT_TOKEN
#   SEAL_S3_ACCESS_KEY_ID       → S3_ACCESS_KEY_ID
#   SEAL_S3_SECRET_ACCESS_KEY   → S3_SECRET_ACCESS_KEY
#   SEAL_EMAIL_AWS_ACCESS_KEY_ID    → EMAIL__AWS_ACCESS_KEY_ID (optional)
#   SEAL_EMAIL_AWS_SECRET_ACCESS_KEY→ EMAIL__AWS_SECRET_ACCESS_KEY (optional)
#   SEAL_EMAIL_WEBHOOK_SECRET       → EMAIL__WEBHOOK_SECRET (optional)

log "[2/4] Sealing app-secret keys with kubeseal ..."
echo ""

# Verify required env vars are set
: "${SEAL_SECRET_KEY:?SEAL_SECRET_KEY env var is required — set it to the JWT signing key (not your shell history if possible: export SEAL_SECRET_KEY=\$(openssl rand -hex 32))}"
: "${SEAL_DATABASE_URL:?SEAL_DATABASE_URL env var is required — format: postgresql+asyncpg://app:<password>@clubcore-postgres-rw:5432/clubcore}"
: "${SEAL_S3_ACCESS_KEY_ID:?SEAL_S3_ACCESS_KEY_ID env var is required}"
: "${SEAL_S3_SECRET_ACCESS_KEY:?SEAL_S3_SECRET_ACCESS_KEY env var is required}"

TELEGRAM_BOT_TOKEN="${SEAL_TELEGRAM_BOT_TOKEN:-placeholder-telegram-bot-token-not-real}"
EMAIL_AWS_ACCESS_KEY_ID="${SEAL_EMAIL_AWS_ACCESS_KEY_ID:-}"
EMAIL_AWS_SECRET_ACCESS_KEY="${SEAL_EMAIL_AWS_SECRET_ACCESS_KEY:-}"
EMAIL_WEBHOOK_SECRET="${SEAL_EMAIL_WEBHOOK_SECRET:-}"

# Write a temporary plaintext Secret manifest
PLAINTEXT_SECRET_FILE="$(mktemp /tmp/app-secret-plaintext-XXXXXX.yaml)"

cat > "${PLAINTEXT_SECRET_FILE}" <<EOF
apiVersion: v1
kind: Secret
metadata:
  name: ${SECRET_NAME}
  namespace: ${TARGET_NAMESPACE}
type: Opaque
stringData:
  SECRET_KEY: "${SEAL_SECRET_KEY}"
  DATABASE_URL: "${SEAL_DATABASE_URL}"
  TELEGRAM_BOT_TOKEN: "${TELEGRAM_BOT_TOKEN}"
  S3_ACCESS_KEY_ID: "${SEAL_S3_ACCESS_KEY_ID}"
  S3_SECRET_ACCESS_KEY: "${SEAL_S3_SECRET_ACCESS_KEY}"
  EMAIL__AWS_ACCESS_KEY_ID: "${EMAIL_AWS_ACCESS_KEY_ID}"
  EMAIL__AWS_SECRET_ACCESS_KEY: "${EMAIL_AWS_SECRET_ACCESS_KEY}"
  EMAIL__WEBHOOK_SECRET: "${EMAIL_WEBHOOK_SECRET}"
EOF

# Seal the plaintext Secret against the controller cert.
# Output the SealedSecret YAML to stdout and as a values snippet.
SEALED_OUTPUT_FILE="$(mktemp /tmp/sealed-secret-output-XXXXXX.yaml)"

kubeseal \
    --cert "${CERT_FILE}" \
    --format yaml \
    --namespace "${TARGET_NAMESPACE}" \
    --name "${SECRET_NAME}" \
    < "${PLAINTEXT_SECRET_FILE}" \
    > "${SEALED_OUTPUT_FILE}"

ok "SealedSecret YAML written to: ${SEALED_OUTPUT_FILE}"
echo ""

# Extract encryptedData values for use in a Helm values override file.
log "Extracting encryptedData blobs (for Helm values override) ..."
echo ""
echo "# ─────────────────────────────────────────────────────────────────────────"
echo "# Copy this block into a SEPARATE values-override.yaml (NOT values.yaml)"
echo "# and pass it to helm: helm upgrade ... -f values-production.yaml"
echo "# ─────────────────────────────────────────────────────────────────────────"
echo "secrets:"
echo "  plaintextForLocalK3d: false"
echo "  sealed:"
echo "    enabled: true"
echo "    encryptedData:"
# Extract each encryptedData key from the kubeseal output YAML using grep + awk.
# kubeseal outputs: `  KEY: "AgABC..."` under spec.encryptedData.
grep -A100 'encryptedData:' "${SEALED_OUTPUT_FILE}" | grep -E '^\s+[A-Z_]+:' | while IFS= read -r line; do
    key=$(echo "${line}" | awk -F: '{gsub(/^[ \t]+/,""); print $1}')
    val=$(echo "${line}" | sed 's/^[^:]*: //')
    printf "      %s: %s\n" "${key}" "${val}"
done
echo ""
echo "# ─────────────────────────────────────────────────────────────────────────"
echo ""
ok "encryptedData blobs extracted — add to your values-production.yaml"
echo ""

# ── Step 3: Export the controller RSA private key (SEC-02 HARD GATE) ─────────
log "[3/4] Exporting controller RSA private key (SEC-02 — P6 hard gate) ..."
echo ""
echo "╔══════════════════════════════════════════════════════════════════════════╗"
echo "║  SEC-02 HARD GATE — CONTROLLER RSA PRIVATE KEY EXPORT                  ║"
echo "║                                                                          ║"
echo "║  The controller RSA private key is the SINGLE most critical backup in   ║"
echo "║  this cluster.  If the controller pod is deleted and the key Secret is  ║"
echo "║  not backed up, ALL SealedSecrets become permanently unrecoverable.     ║"
echo "║                                                                          ║"
echo "║  YOU MUST complete the off-node backup checklist BEFORE any production  ║"
echo "║  deploy.  See: infra/runbooks/sealed-secrets-key-backup.md              ║"
echo "╚══════════════════════════════════════════════════════════════════════════╝"
echo ""

# Determine a safe off-node export path (default: /tmp/clubcore-sealed-secrets-key.yaml).
# The operator MUST copy this file off-node immediately after export.
# We REFUSE to write it inside the repo (see check_no_key_in_repo above).
KEY_EXPORT_PATH="${SEALED_KEY_EXPORT_PATH:-/tmp/clubcore-sealed-secrets-key-$(date +%Y%m%d).yaml}"

# Safety check: refuse to write inside the repo
check_no_key_in_repo "${KEY_EXPORT_PATH}"

log "Exporting controller RSA key Secret to: ${KEY_EXPORT_PATH}"
log "Override export path: export SEALED_KEY_EXPORT_PATH=/path/outside/repo/key.yaml"
echo ""

# Export the controller RSA key Secret from the cluster.
# The label sealedsecrets.bitnami.com/sealed-secrets-key selects only the key Secret(s).
kubectl get secret \
    -n "${CONTROLLER_NAMESPACE}" \
    -l "${CONTROLLER_LABEL}" \
    -o yaml > "${KEY_EXPORT_PATH}"

if [ -s "${KEY_EXPORT_PATH}" ]; then
    KEY_SIZE="$(wc -c < "${KEY_EXPORT_PATH}")"
    ok "Controller RSA key exported: ${KEY_EXPORT_PATH} (${KEY_SIZE} bytes)"
else
    err "Controller RSA key export failed — the output file is empty.
  Verify the sealed-secrets controller is running:
    kubectl get pod -n ${CONTROLLER_NAMESPACE} -l name=sealed-secrets-controller
  Verify the key Secret exists:
    kubectl get secret -n ${CONTROLLER_NAMESPACE} -l ${CONTROLLER_LABEL}"
fi

echo ""
echo "╔══════════════════════════════════════════════════════════════════════════╗"
echo "║  OPERATOR ACTION REQUIRED — SEC-02 P6 HARD GATE                        ║"
echo "║                                                                          ║"
echo "║  Exported key file: ${KEY_EXPORT_PATH}"
echo "║                                                                          ║"
echo "║  YOU MUST NOW:                                                           ║"
echo "║    1. Copy the key file to a second PC (off-node backup)                 ║"
echo "║    2. Follow the full checklist in:                                      ║"
echo "║       infra/runbooks/sealed-secrets-key-backup.md                        ║"
echo "║    3. Verify restore works BEFORE committing the SealedSecret to git     ║"
echo "║    4. Delete ${KEY_EXPORT_PATH} from this machine after backup           ║"
echo "║                                                                          ║"
echo "║  NEVER commit this file to git. NEVER leave it on a single machine.     ║"
echo "╚══════════════════════════════════════════════════════════════════════════╝"
echo ""

# ── Step 4: Summary ───────────────────────────────────────────────────────────
log "[4/4] Summary ..."
echo ""
echo "  Status:   Complete (in-sandbox steps)"
echo "  Cert:     ${CERT_FILE} (temporary — deleted on exit)"
echo "  Sealed:   ${SEALED_OUTPUT_FILE} (temporary — deleted on exit)"
echo "  RSA key:  ${KEY_EXPORT_PATH} (MUST copy off-node NOW)"
echo ""
echo "  OPERATOR-PENDING (SEC-02 P6 hard gate):"
echo "    - Copy RSA key to the second PC (see sealed-secrets-key-backup.md)"
echo "    - Add the encryptedData values to values-production.yaml"
echo "    - Deploy: helm upgrade --install clubcore infra/helm/clubcore \\"
echo "              --set secrets.plaintextForLocalK3d=false \\"
echo "              --set secrets.sealed.enabled=true \\"
echo "              -f /path/to/values-production.yaml"
echo ""
log "DONE — follow sealed-secrets-key-backup.md before any production deploy"

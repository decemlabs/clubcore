#!/usr/bin/env bash
# scan-images.sh — Trivy HIGH/CRITICAL security scan gate for all clubcore images.
#
# IMG-04: Runs `trivy image --severity HIGH,CRITICAL --exit-code 1 --ignore-unfixed`
#          over every built image tag. Exits non-zero if ANY image has HIGH/CRITICAL CVEs.
#
# If trivy is not on PATH, the scan is marked operator-pending and the script exits 0
# with a clear WARN (per D-V40-LOCAL-VALIDATE — no fabricated evidence).
#
# Usage:
#   TAG=$(git rev-parse --short HEAD)
#   bash infra/scripts/build-images.sh     # build first
#   bash infra/scripts/scan-images.sh      # scan
#
# Or supply TAG explicitly:
#   TAG=abc1234 bash infra/scripts/scan-images.sh

set -euo pipefail

# ── Tag derivation ────────────────────────────────────────────────────────────
TAG="${TAG:-$(git rev-parse --short HEAD)}"

IMAGES=(
    "clubcore/backend:${TAG}"
    "clubcore/admin-app:${TAG}"
    "clubcore/client-pwa:${TAG}"
)

echo "=== clubcore trivy scan gate ==="
echo "Tag     : ${TAG}"
echo "Images  : ${#IMAGES[@]}"
echo ""

# ── Trivy availability check ──────────────────────────────────────────────────
if ! command -v trivy &>/dev/null; then
    echo "WARN: trivy is not installed / not on PATH."
    echo ""
    echo "  IMG-04 scan gate: OPERATOR-PENDING"
    echo ""
    echo "  To complete the gate manually, install trivy and run:"
    for img in "${IMAGES[@]}"; do
        echo "    trivy image --severity HIGH,CRITICAL --exit-code 1 --ignore-unfixed ${img}"
    done
    echo ""
    echo "  Install options:"
    echo "    brew install aquasecurity/trivy/trivy   (macOS)"
    echo "    curl -sfL https://raw.githubusercontent.com/aquasecurity/trivy/main/contrib/install.sh | sh -s -- -b /usr/local/bin"
    echo ""
    echo "  Record scan results in .planning/phases/118-container-images-helm-chart-core-stack/118-01-SUMMARY.md"
    echo ""
    # Exit 0: operator-pending is a known state, not a failure (D-V40-LOCAL-VALIDATE).
    exit 0
fi

echo "trivy version: $(trivy --version 2>&1 | head -1)"
echo ""

# ── Scan loop ─────────────────────────────────────────────────────────────────
SCAN_FAILED=0
SCAN_RESULTS=()

for img in "${IMAGES[@]}"; do
    echo "--- Scanning ${img} ---"
    if trivy image \
        --severity HIGH,CRITICAL \
        --exit-code 1 \
        --ignore-unfixed \
        "${img}"; then
        SCAN_RESULTS+=("PASS: ${img}")
        echo "  ✓ ${img} — 0 HIGH/CRITICAL"
    else
        SCAN_RESULTS+=("FAIL: ${img}")
        echo "  ✗ ${img} — HIGH/CRITICAL CVEs found!"
        SCAN_FAILED=1
    fi
    echo ""
done

# ── Summary ───────────────────────────────────────────────────────────────────
echo "=== Scan summary ==="
for result in "${SCAN_RESULTS[@]}"; do
    echo "  ${result}"
done
echo ""

if [[ "${SCAN_FAILED}" -eq 1 ]]; then
    echo "GATE: FAILED — one or more images have HIGH/CRITICAL CVEs."
    echo "Resolve findings before deploying (update base images or apply patches)."
    exit 1
else
    echo "GATE: PASSED — 0 HIGH/CRITICAL CVEs across all images."
    exit 0
fi

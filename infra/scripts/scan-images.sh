#!/usr/bin/env bash
# scan-images.sh — Trivy HIGH/CRITICAL security scan gate for all clubcore images.
#
# IMG-04: Runs `trivy image --severity HIGH,CRITICAL --exit-code 1 --ignore-unfixed`
#          over every built image tag. Exits non-zero if ANY image has HIGH/CRITICAL CVEs.
#
# If trivy is not on PATH, behavior depends on REQUIRE_TRIVY:
#   - REQUIRE_TRIVY=1 (CI / automated gate): FAIL CLOSED — exit non-zero. A missing
#     scanner must never turn the CVE gate into a silent no-op (WR-03).
#   - REQUIRE_TRIVY unset/0 (local operator): mark operator-pending and exit 0 with a
#     clear WARN on stderr (per D-V40-LOCAL-VALIDATE — no fabricated evidence).
# Any automated pipeline invoking this script MUST set REQUIRE_TRIVY=1.
#
# Usage:
#   TAG=$(git rev-parse --short HEAD)
#   bash infra/scripts/build-images.sh     # build first
#   bash infra/scripts/scan-images.sh      # scan (local: operator-pending if no trivy)
#   REQUIRE_TRIVY=1 bash infra/scripts/scan-images.sh   # CI: fail closed if no trivy
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
    # All diagnostics go to stderr so they remain visible in fail-fast pipelines.
    echo "WARN: trivy is not installed / not on PATH." >&2
    echo "" >&2
    echo "  To complete the gate manually, install trivy and run:" >&2
    for img in "${IMAGES[@]}"; do
        echo "    trivy image --severity HIGH,CRITICAL --exit-code 1 --ignore-unfixed ${img}" >&2
    done
    echo "" >&2
    echo "  Install options:" >&2
    echo "    brew install aquasecurity/trivy/trivy   (macOS)" >&2
    echo "    curl -sfL https://raw.githubusercontent.com/aquasecurity/trivy/main/contrib/install.sh | sh -s -- -b /usr/local/bin" >&2
    echo "" >&2

    # WR-03: in an automated gate the CVE check must FAIL CLOSED. A CI runner
    # without trivy must not pass the gate by default. CI sets REQUIRE_TRIVY=1.
    if [[ "${REQUIRE_TRIVY:-0}" == "1" ]]; then
        echo "ERROR: REQUIRE_TRIVY=1 but trivy is not installed — failing the gate." >&2
        echo "       Install trivy in the CI image or remove REQUIRE_TRIVY for a local run." >&2
        exit 1
    fi

    echo "  IMG-04 scan gate: OPERATOR-PENDING" >&2
    echo "  Record scan results in .planning/phases/118-container-images-helm-chart-core-stack/118-01-SUMMARY.md" >&2
    echo "" >&2
    # Local operator path: operator-pending is a known state, not a failure
    # (D-V40-LOCAL-VALIDATE — no fabricated evidence). CI must set REQUIRE_TRIVY=1.
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

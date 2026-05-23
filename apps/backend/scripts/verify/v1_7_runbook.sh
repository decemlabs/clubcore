#!/usr/bin/env bash
# v1.7 operator runbook — VER-01 (Phase 53).
#
# One-command entry point for the complete v1.7 online-payment-to-fiscal
# walkthrough. Drives the live `docker compose up` stack with no manual
# intervention.
#
# Flow:
#   1. Pre-flight gate (_preflight.sh) — confirms env vars, CLI tools, backend
#      liveness, Postgres, Redis, ARQ worker, YOOKASSA_SANDBOX.
#   2. Iterates scenario scripts 09_*.sh and 1[0-9]_*.sh in order, aborting on
#      the first non-zero exit and directing the operator to the evidence file.
#   3. On full success, prints "ALL SCENARIOS PASS" (exact string — the runbook's
#      success signal per VER-01 acceptance criteria).
#
# D-01: Extends the existing scripts/verify/ numbered-scenario harness rather
#       than writing a monolith. _lib.sh cookie-jar isolation is preserved per
#       scenario; _preflight.sh readiness gate runs once at the top.
# D-02: Webhook delivery is simulated by raw curl POSTs to the local
#       /_internal/yookassa/webhook endpoint.
#
# Evidence directory: .planning/milestones/v1.7-verification-evidence/
# Each scenario tees its output to a per-scenario .txt file in that directory.
#
# Prerequisites (export before running):
#   SECRET_KEY                   ≥48 bytes
#   SEED_VERIFY_OWNER_PASSWORD   ≥12 chars; also as VERIFY_OWNER_PASSWORD
#   SEED_VERIFY_RECEPTION_PASSWORD ≥12 chars; also as VERIFY_RECEPTION_PASSWORD
#   YOOKASSA_SANDBOX=true        must be set in the compose-stack env
#                                (docker-compose.yml or .env); required so the
#                                webhook simulation passes verify_yookassa_ip
#                                sandbox bypass (webhook_verifier.py:84-86).
#
# Inline-regression hard cap: 5 (D-05 / D-36-15..17 lineage).
# Beyond 5 regressions → STOP, roll to v1.8 DEFER (do not extend this runbook).
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

echo "=== v1.7 runbook ==="
echo "started: $(date -u +%Y-%m-%dT%H:%M:%SZ)"

# --- Step 1: Pre-flight gate ---
echo ""
echo "--- pre-flight ---"
bash "$SCRIPT_DIR/_preflight.sh"

# --- Step 2: Scenario sweep (09_*.sh + 10_*.sh ... 19_*.sh) ---
# Loop iterates in glob order (numeric). If no matching file exists for the
# 1[0-9] pattern, the glob is unexpanded and we skip it safely (set -e-safe
# because we test with compgen).
echo ""
echo "--- v1.7 scenarios ---"

SCENARIO_FILES=()
# Collect 09_*.sh
for f in "$SCRIPT_DIR"/09_*.sh; do
  [ -f "$f" ] && SCENARIO_FILES+=("$f")
done
# Collect 1[0-9]_*.sh (10..19)
for f in "$SCRIPT_DIR"/1[0-9]_*.sh; do
  [ -f "$f" ] && SCENARIO_FILES+=("$f")
done

if [ "${#SCENARIO_FILES[@]}" -eq 0 ]; then
  echo "ERROR: no v1.7 scenario scripts (09_*.sh or 1[0-9]_*.sh) found in $SCRIPT_DIR"
  exit 1
fi

for s in "${SCENARIO_FILES[@]}"; do
  echo ""
  echo "--- $(basename "$s") ---"
  if ! bash "$s"; then
    echo ""
    echo "FAILED: $s — see evidence file in .planning/milestones/v1.7-verification-evidence/"
    exit 1
  fi
done

# --- Step 3: Success signal ---
echo ""
echo "ended: $(date -u +%Y-%m-%dT%H:%M:%SZ)"
echo "ALL SCENARIOS PASS"

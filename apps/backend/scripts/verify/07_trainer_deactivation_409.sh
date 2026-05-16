#!/usr/bin/env bash
# Phase 36 scenario 07 — trainer deactivation + 409 on attempt to record session with inactive trainer.
# Roadmap SC #1 sub-scenario 07. Run AFTER seed_v1_4_verification_fixtures.
# TODO 36-02: fill in scenario body per CONTEXT.md domain block + module router schemas.
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
source "$SCRIPT_DIR/_lib.sh"

EVIDENCE=".planning/milestones/v1.4-verification-evidence/07_trainer_deactivation_409.txt"
mkdir -p "$(dirname "$EVIDENCE")"

# Tee everything (stdout + stderr) into the evidence file per D-36-02.
exec > >(tee "$EVIDENCE") 2>&1

echo "=== scenario 07_trainer_deactivation_409 ==="
echo "started: $(date -u +%Y-%m-%dT%H:%M:%SZ)"

echo "TODO 36-02: scenario body not yet implemented — scaffold-only stub"

echo "ended: $(date -u +%Y-%m-%dT%H:%M:%SZ)"
echo "result: STUB"

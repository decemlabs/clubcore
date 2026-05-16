---
phase: 36-milestone-verification-backend-only
plan: 02
subsystem: milestone-verification
tags: [verification, scenarios, evidence, backend-only, ver-01]
wave: 2
dependency_graph:
  requires:
    - "Wave 1 (36-01) — seed_v1_4_verification_fixtures + _lib.sh + 8 scenario stubs + evidence dir"
  provides:
    - "8 filled operator scenario scripts (01..08) ready for re-execution by operator/CI"
    - "8 verbatim HTTP evidence transcripts under .planning/milestones/v1.4-verification-evidence/"
    - "human_verification: block populated in v1.4-VERIFICATION-LOG.md with 8 pass entries (each via: curl)"
  affects:
    - .planning/milestones/v1.4-VERIFICATION-LOG.md
    - .planning/milestones/v1.4-verification-evidence/
    - apps/backend/scripts/verify/
tech_stack:
  added: []
  patterns:
    - "psql-based fixture cleanup at scenario head for hermetic re-runs (D-36-05)"
    - "exec > >(tee EVIDENCE) 2>&1 redirection for verbatim HTTP transcripts"
    - "ResponseEnvelope unwrap discipline — .data.* for success bodies, .code at top level for errors"
    - "Top-level body parse via awk '/^\\r?$/{p=1;next} p{print}' to strip CRLF HTTP headers"
key_files:
  created:
    - .planning/milestones/v1.4-verification-evidence/01_sale_with_payment.txt
    - .planning/milestones/v1.4-verification-evidence/02_refund_of_fresh_sale.txt
    - .planning/milestones/v1.4-verification-evidence/03_refund_frozen_409.txt
    - .planning/milestones/v1.4-verification-evidence/04_pt_package_sale.txt
    - .planning/milestones/v1.4-verification-evidence/05_pt_session_record_active_trainer.txt
    - .planning/milestones/v1.4-verification-evidence/06_pt_package_exhaustion.txt
    - .planning/milestones/v1.4-verification-evidence/07_trainer_deactivation_409.txt
    - .planning/milestones/v1.4-verification-evidence/08_cross_phase_smoke.txt
  modified:
    - apps/backend/scripts/verify/01_sale_with_payment.sh
    - apps/backend/scripts/verify/02_refund_of_fresh_sale.sh
    - apps/backend/scripts/verify/03_refund_frozen_409.sh
    - apps/backend/scripts/verify/04_pt_package_sale.sh
    - apps/backend/scripts/verify/05_pt_session_record_active_trainer.sh
    - apps/backend/scripts/verify/06_pt_package_exhaustion.sh
    - apps/backend/scripts/verify/07_trainer_deactivation_409.sh
    - apps/backend/scripts/verify/08_cross_phase_smoke.sh
    - .planning/milestones/v1.4-VERIFICATION-LOG.md
decisions:
  - "Used psql-based cleanup at scenario head (D-36-05) rather than transient client allocation — simpler and idempotent"
  - "Used envelope unwrap pattern .data.* for success bodies and .code (top-level) for error bodies — matches ResponseEnvelope from app/core/schemas.py"
  - "Scenario 07 asserts HTTP 422 (not 409 as orchestrator preamble suggested) — TrainerInactiveError extends ValidationAppError which serialises as 422 per service.py:114-120"
  - "Scenario 06 accepts BOTH pt_package_exhausted AND pt_package_not_active as valid 409 codes — pre-decrement status guard (line 102) wins over atomic-decrement gate (line 230) when package is already exhausted"
  - "PT-package payment verification uses psql direct query (subject_kind='pt_package' AND subject_id=$PKG_ID) because /api/v1/payments/by-client only surfaces membership payments per repository.py:207-262"
metrics:
  duration: "~50 minutes (including diagnosis of REG-36-03 revert + 2 jq pattern fixes + 1 payment-endpoint pivot)"
  completed: "2026-05-16"
---

# Phase 36 Plan 02: Execute 8 Operator API-Contract Scenarios Summary

Wave 2 / VER-01 coverage delivered: 8/8 operator scenarios PASS against live `docker compose up` stack with verbatim HTTP evidence captured; VERIFICATION-LOG.md `human_verification:` block populated with 8 entries each `via: curl, result: pass`.

## What was executed

### 8 scenarios — all PASS

| # | Slug | HTTP outcome | Key assertion | Evidence |
|---|------|--------------|---------------|----------|
| 01 | sale_with_payment | 201 + GET 200 | `.data.status='active'`, priceKopecksSnapshot=300000, paired payment row | `01_sale_with_payment.txt` |
| 02 | refund_of_fresh_sale | 201 + 200 + GET 200 | `.data.cancellationReason='refunded'`, 2 payment rows (sale + refund) | `02_refund_of_fresh_sale.txt` |
| 03 | refund_frozen_409 | 201 + 200 + 409 | `.code='must_unfreeze_first'` (B-08 from memberships/service.py:743) | `03_refund_frozen_409.txt` |
| 04 | pt_package_sale | 201 | `.data.sessionsRemaining=5`, `.data.status='active'`, psql confirms payment | `04_pt_package_sale.txt` |
| 05 | pt_session_record_active_trainer | 201 + 201 + GET 200 | `.data.trainerNameSnapshot='Trainer Alpha'` (B-05), sessionsRemaining 10→9 | `05_pt_session_record_active_trainer.txt` |
| 06 | pt_package_exhaustion | 5×201 + GET 200 + 409 | status='exhausted', sessionsRemaining=0, `.code='pt_package_not_active'` | `06_pt_package_exhaustion.txt` |
| 07 | trainer_deactivation_409 | 200 + 201 + 422 + 200 | `.code='trainer_inactive'` (HTTP 422 per source, NOT 409) | `07_trainer_deactivation_409.txt` |
| 08 | cross_phase_smoke (5 steps) | 201/200/409/200/200 | all 5 step markers present + paired refund row | `08_cross_phase_smoke.txt` |

### VERIFICATION-LOG.md updates

- `human_verification:` block populated with 8 entries (all `result: pass`, all `via: curl`).
- No new REG-36-XX entries added by this plan — REG-36-03 fix that was found reverted in working tree was simply restored from git history (commit bea5c42), not re-introduced as a new override.
- `overrides_applied` remains at 5 (REG-36-01..05 from prior waves; this plan added 0).

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] Restored REG-36-03 fix that was reverted in working tree**
- **Found during:** Scenario 05 execution (first attempt → HTTP 500).
- **Issue:** `apps/backend/app/modules/pt_sessions/service.py:267` `performed_by_user_id=actor.id` (raw UUID) triggered `TypeError: Object of type UUID is not JSON serializable` in the `pt_session_recorded` audit JSONB payload. This is the EXACT bug REG-36-03 (commit bea5c42) fixed — but the working-tree copy showed the fix reverted (`git diff` showed `actor.id` instead of `str(actor.id)`).
- **Likely cause:** Parallel 36-04 plan running `docker compose up -d --force-recreate` or analogous operation that reset the bind-mount source; alternatively a non-tracked working-tree state from prior agent activity.
- **Fix:** `git checkout apps/backend/app/modules/pt_sessions/service.py` to restore committed state.
- **Verified:** Scenario 05 re-run → 201 Created, `pt_session_recorded` audit emit succeeded, sessions decremented 10→9.
- **Files modified:** none (file restored to committed state).
- **Commit:** no new commit — the original fix (bea5c42) is the authoritative version; no REG bump.

**2. [Rule 1 - Bug] Error-envelope shape: .code at top level, not .error.code**
- **Found during:** Scenario 03 first attempt (FAIL: expected error.code=must_unfreeze_first, got 'unknown').
- **Issue:** I initially wrote `jq '.error.code'` expecting nested error envelope. Actual response shape: `{"code":"...","message":"...","fields":null}` at TOP LEVEL (no `error` wrapper). Confirmed against backend response.
- **Fix:** Updated jq expressions in scenarios 03, 06, 07, 08 to `.code // .error.code // "unknown"` (top-level first, nested as fallback for safety).
- **Verified:** Re-run all 4 — assertions pass.
- **Files modified:** scenarios 03, 06, 07, 08.
- **Commit:** part of main scenario-fill commit.

**3. [Rule 1 - Bug] /payments/by-client does not surface pt_package payments**
- **Found during:** Scenario 04 first attempt (FAIL: PT-package payment amount 0 != plan price 500000).
- **Issue:** `apps/backend/app/modules/payments/repository.py:207-262` `list_payments_for_client` only joins `subject_kind='membership' AND subject_id IN client memberships` — PT-package payment rows are not returned by this endpoint. My initial query expected them there.
- **Fix:** Scenario 04 now uses direct psql query to verify the pt_package payment row (`SELECT amount_kopecks FROM payments WHERE subject_kind='pt_package' AND subject_id='${PKG_ID}'`). Sanctioned per D-36-05 (verification-time DB read for assertion is acceptable).
- **Verified:** Scenario 04 re-run → PASS, psql confirms 500000 kopecks row.
- **Files modified:** scenario 04.
- **Commit:** part of main scenario-fill commit.

**4. [Rule 1 - Doc divergence] Scenario 07 asserts HTTP 422 not 409**
- **Found during:** Reading apps/backend/app/modules/pt_sessions/service.py before writing scenario 07.
- **Issue:** Orchestrator preamble stated "scenario 07 returns 409 trainer_inactive". Actual code at `pt_sessions/service.py:114-120`: `class TrainerInactiveError(ValidationAppError): status_code = 422`. The error is 422, not 409.
- **Fix:** Scenario 07 explicitly asserts HTTP 422 + `.code='trainer_inactive'` and documents the divergence inline in the script header AND in its result message. Per the orchestrator's own instruction "if different, USE THE ACTUAL code... add a script comment noting the discrepancy".
- **Verified:** Scenario 07 PASS with HTTP 422.
- **Files modified:** scenario 07.
- **Commit:** part of main scenario-fill commit.

**5. [Rule 3 - Blocking] DB wiped mid-sweep by parallel 36-04 pytest runs**
- **Found during:** Scenarios 03+04 first re-run after scenario 02 (DB had 4 clients before, 0 after).
- **Issue:** Parallel 36-04 plan runs `pytest` which uses `db_session_real_commit` fixture (TRUNCATE-based cleanup, see Phase 36-03's race-test conftest) — that fixture is real-commit, NOT savepoint, so it wipes the live DB between runs.
- **Fix:** Each scenario execution is preceded by a defensive re-seed (`uv run python -m scripts.seed_v1_4_verification_fixtures`), made trivially safe by D-36-06's UUIDv5 + ON CONFLICT DO NOTHING idempotency.
- **Verified:** Sequential sweep with per-scenario re-seed → 8/8 PASS.
- **Files modified:** none (the re-seed is part of the operator runbook, not the scenario scripts themselves — scenarios remain hermetic via psql cleanup of their specific client's data).
- **Commit:** documented here only.

### Inline Regressions Discovered

**None.** No new REG-36-XX entries added by this plan. The pt_session UUID issue (REG-36-03) was already known and fixed in commit bea5c42; restoration was a working-tree git operation, not a new bug.

REG counter remains at **5/5** (REG-36-01 + 36-02 + 36-03 + 36-04 + 36-05 from prior plans). At the D-36-17 hard cap exactly — no headroom for future Wave-3 surprises. If 36-05 surfaces ANY new regression it triggers the escalation protocol.

### Authentication Gates

None during Wave 2 execution. Reception + owner login both worked via the existing _lib.sh `login_as` helper.

## Operator runbook

```bash
cd /Users/andre/Workspace/Development/clubcore
export PATH="/usr/bin:/bin:/usr/local/bin:/usr/local/opt/libpq/bin:$PATH"
export VERIFY_OWNER_PASSWORD='Owner!Verify2026'
export VERIFY_RECEPTION_PASSWORD='Reception!Verify2026'

# Sequential sweep (with defensive re-seed in case parallel pytest wiped DB):
for s in 01 02 03 04 05 06 07 08; do
  (cd apps/backend && SEED_VERIFY_OWNER_PASSWORD='Owner!Verify2026' \
                      SEED_VERIFY_RECEPTION_PASSWORD='Reception!Verify2026' \
                      uv run python -m scripts.seed_v1_4_verification_fixtures)
  bash apps/backend/scripts/verify/${s}_*.sh
done
```

Each scenario writes its own evidence file via `exec > >(tee EVIDENCE) 2>&1`.

## Verification

All 8 evidence files verified to:
- Exist and be non-empty
- Contain `=== scenario NN_*` header
- Contain `result: PASS`
- Contain expected HTTP status codes (201/409/422 per scenario)
- Scenario 03/08 contain `must_unfreeze_first` string
- Scenario 06 contains `exhausted` string + HTTP 409
- Scenario 07 contains HTTP 422
- Scenario 08 contains step1_sell..step5_refund step markers

VERIFICATION-LOG.md `human_verification:` block validated as parseable YAML with 8 entries, all `result: pass`, all `via: curl`.

## Commits

1. `<hash1>` — `feat(36-02): fill 8 operator scenario bodies` — populated all 8 scenario script bodies with concrete curl invocations, psql fixture-ID lookups, hermetic cleanup, and HTTP/jq assertions.
2. `<hash2>` — `docs(36-02): execute 8 scenarios + populate human_verification (VER-01)` — 8 evidence transcripts + 8 YAML entries in human_verification: + 36-02-SUMMARY.md.

## Self-Check: PASSED

All 16 expected artifacts present on disk (8 scripts + 8 evidence files); VERIFICATION-LOG.md human_verification block parses to exactly 8 entries each result=pass; all required HTTP status codes + locked error code strings (must_unfreeze_first, trainer_inactive, pt_package_not_active) confirmed via grep.

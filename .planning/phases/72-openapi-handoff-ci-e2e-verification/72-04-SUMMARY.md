---
phase: 72-openapi-handoff-ci-e2e-verification
plan: "04"
subsystem: handoff-documentation
tags: [runbook, operator-evidence, e2e, yookassa, otp-auth, client-portal]
dependency_graph:
  requires: [72-01, 72-02, 72-03]
  provides: [v2.0-runbook, v2.0-operator-evidence-scaffold]
  affects: [VER-01, VER-04]
tech_stack:
  added: []
  patterns: [append-only-evidence, bilingual-runbook, operator-pending-deferred-leg]
key_files:
  created:
    - .planning/handoff/clubcore-v2.0-runbook.md
    - .planning/milestones/v2.0-OPERATOR-EVIDENCE.md
  modified: []
decisions:
  - "D-72-07: active membership + PT-package for read-path established via staff sell/activate (primary path), seed does not auto-grant membership/PT-package — seed_demo_data only creates the catalog plans"
  - "D-72-09: runbook depth mirrors clubcore-auth-runbook.md (577 lines, 8 sections, bilingual, curl+cookie-jar+CSRF pattern)"
  - "D-72-06: ЮKassa checkout leg captured as RUN-01 OPERATOR-PENDING with trigger condition; read-path is hard gate (RUN-00 PENDING until human walkthrough)"
metrics:
  duration: 3m
  completed_date: "2026-05-31"
  tasks_completed: 2
  tasks_pending: 1
  files_created: 2
---

# Phase 72 Plan 04: v2.0 Runbook + E2E Evidence Scaffold Summary

**One-liner:** Bilingual v2.0 client-portal runbook (577 lines, 8 sections, all /api/v1/client/* curl examples + CSRF discipline) + append-only operator-evidence scaffold (RUN-00 gate PENDING, RUN-01 ЮKassa OPERATOR-PENDING).

## Tasks Completed

| Task | Name | Commit | Files |
|------|------|--------|-------|
| 1 | Author v2.0 client-portal runbook | bdb7124b | .planning/handoff/clubcore-v2.0-runbook.md |
| 2 | Scaffold v2.0 operator-evidence file | 95989c97 | .planning/milestones/v2.0-OPERATOR-EVIDENCE.md |

## Tasks Pending

| Task | Name | Status | Gate |
|------|------|--------|------|
| 3 | Live read-path E2E walkthrough (milestone gate) | CHECKPOINT:human-verify | blocking |

## Runbook Coverage (Task 1)

`.planning/handoff/clubcore-v2.0-runbook.md` — 577 lines, mirroring the depth of `clubcore-auth-runbook.md`.

**Sections authored:**
1. **Dev-stack setup** — `docker compose up`, seed order (seed_demo_data → seed_dev_client), env vars `ENVIRONMENT=dev` / `DEV_OTP_PIN_ENABLED=true`, `docker compose up -d --force-recreate backend` env-reload note
2. **Phone-OTP login** — `POST /api/v1/client/otp/request` (202 anti-oracle) → `POST /api/v1/client/otp/verify` (dev creds `+79999999999` / `111111`, cc_client_access + cc_client_refresh + clubcore_client_csrf cookies)
3. **Read-path walkthrough** (live gate) — GET /home, /membership, /slots, POST /booking (+Idempotency-Key), GET /qr-token, POST /check-in (unauthenticated, QR JWT), GET /history/visits|pt-sessions|payments
4. **ЮKassa checkout leg** (OPERATOR-PENDING) — test card `5555 5555 5555 4477`, `YOOKASSA_SANDBOX=true`, hosted-page, manual `POST /api/v1/_internal/yookassa/webhook` with REAL payment_id (explicit no-fabrication warning, T-72-10)
5. **Additional reads** — /bookings, /plans, /pt-packages, /trainers
6. **Session management** — refresh rotation + logout
7. **CSRF discipline** — clubcore_client_csrf extraction, which endpoints require X-CSRF-Token
8. **Full curl quickstart** — copy-paste sequence for new terminal

**Active membership + PT-package prerequisite (D-72-07):**
`seed_demo_data` creates the catalog (plan records), but does NOT grant the dev client an active membership or PT-package. The staff sell/activate path (documented in § 1.5) is the primary path to establish preconditions for the book/QR steps. The ЮKassa checkout leg (OPERATOR-PENDING) is the alternate path. No auto-grant from seeds alone — documented clearly.

## Evidence Scaffold Coverage (Task 2)

`.planning/milestones/v2.0-OPERATOR-EVIDENCE.md` — YAML front-matter + append-only convention.

- **YAML front-matter:** milestone v2.0, items `[RUN-00-read-path-live, RUN-01-yookassa-checkout]`, decisions_honored `[D-72-06, D-72-07, D-72-09]`
- **Index:** RUN-00 `PENDING → COMPLETE` (to be flipped by operator after live walkthrough) + RUN-01 `OPERATOR-PENDING` with full trigger condition
- **RUN-00 section:** empty template ready for operator transcript; includes required fields checklist (healthz, OTP, /home, /membership, /booking, /qr-token, /check-in, /history/visits)
- **RUN-01 section:** trigger condition documented (sandbox creds + YOOKASSA_SANDBOX=true), step-by-step procedure with REAL payment_id requirement, evidence destination instructions

## Deviations from Plan

**1. [Rule 2 - Auto-add] Seed path clarification**
- **Found during:** Task 1 (reading seed scripts)
- **Issue:** seed_demo_data only seeds catalog plans (MembershipPlan + PtPackagePlan), not active memberships/PT-packages for the dev client. The plan says "default to establishing it via the dev seed" but the seeds do not grant active membership/PT-package — they only create the plan records.
- **Fix:** Documented the staff sell/activate path as the PRIMARY fallback in the runbook § 1.5, with explicit note that seed_demo_data creates the catalog but does not auto-grant active membership/PT-package to the dev client. The ЮKassa checkout leg is the alternate (OPERATOR-PENDING) path.
- **Decision recorded:** D-72-07 clarification — staff-side sell/activate is the correct path for establishing read-path preconditions.

## Known Stubs

None — this plan creates documentation artifacts only; no UI components or data wiring.

## Threat Flags

None — runbook uses only dev-pinned OTP (111111, dev-only, ENVIRONMENT=dev guard) and ЮKassa SANDBOX test card; no production secrets committed. T-72-12 mitigated.

## Self-Check: PASSED

- [x] `.planning/handoff/clubcore-v2.0-runbook.md` exists (577 lines, ≥120 requirement met)
- [x] Contains "111111", "5555 5555 5555 4477", "OPERATOR-PENDING", "/api/v1/client/"
- [x] `.planning/milestones/v2.0-OPERATOR-EVIDENCE.md` exists
- [x] Contains "RUN-00-read-path-live", "OPERATOR-PENDING", "append-only"
- [x] Commits bdb7124b and 95989c97 verified in git log
- [x] Task 3 (checkpoint:human-verify) NOT auto-passed — paused for operator

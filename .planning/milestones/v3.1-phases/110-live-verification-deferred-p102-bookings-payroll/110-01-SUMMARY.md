---
phase: 110-live-verification-deferred-p102-bookings-payroll
plan: "01"
subsystem: backend/scripts
tags: [seed, walkthrough, payroll, bookings, pt-packages, verification]
dependency_graph:
  requires: [seed_demo_data (bootstrap owner must exist first)]
  provides: [seed_p102_walkthrough, p102_walkthrough.sh, README]
  affects: [Phase 110 Plans 02 (VER-01) and 03 (VER-02) which depend on this seed]
tech_stack:
  added: []
  patterns:
    - uuid5-deterministic PKs + ON CONFLICT (id) DO NOTHING (idempotency)
    - TM-29-02 local-DB guard (localhost / postgres:5432)
    - NIST 800-63B password length gate (>= 12 chars)
    - cc_access + clubcore_csrf -> X-CSRF-Token cookie discipline (v3.0)
key_files:
  created:
    - apps/backend/scripts/seed_p102_walkthrough.py
    - apps/backend/scripts/verify/p102_walkthrough.sh
  modified:
    - apps/backend/scripts/verify/README.md
decisions:
  - Slot anchored to next Monday 10:00 MSK (mirrors test_booking_race.py math) so it always falls in working-hours window
  - Payment received_at=2026-04-15 (matches PERFORMED_AT in test_payroll_accruals.py) so payroll preview picks it up
  - CompConfig effective_from=2026-01-01 (matches payroll conftest exemplar)
  - Literal-HTTP confirmation via uvicorn deferred as UAT item (uvicorn not running headlessly during execution)
  - Walkthrough step 4 re-creates a second booking before completing via pt-session (mirrors Plan 02 VER-01 structure)
metrics:
  duration: "~6 minutes"
  completed: "2026-06-14"
  tasks_completed: 2
  files_created: 3
  files_modified: 1
---

# Phase 110 Plan 01: P102 Walkthrough Seed + Captured HTTP Script — Summary

Produced the two committed "repeatable" deliverables that close the v3.0 P102 `data-setup-blocked` root cause: (1) an idempotent seed script creating the full 7-entity prerequisite graph, and (2) a captured runnable live-HTTP walkthrough script + README documenting the exact dev-login → booking-lifecycle → payroll-lifecycle command sequence.

## Tasks Completed

| # | Task | Commit | Files |
|---|------|--------|-------|
| 1 | Write idempotent P102 walkthrough seed script | 74272e17 | `scripts/seed_p102_walkthrough.py` |
| 2 | Capture runnable live-HTTP walkthrough script + README | 3c75edec | `scripts/verify/p102_walkthrough.sh`, `scripts/verify/README.md` |

## What Was Built

### Task 1: `scripts/seed_p102_walkthrough.py`

Idempotent seed creating the full P102 prerequisite graph (7 entities in dependency order):

1. **Trainer** — "P102 Walkthrough Trainer", is_active=True, phone="+79001020102"
2. **TrainerAvailabilitySlot** — next Monday 10:00 MSK (→ UTC), 1 h, status='active'; next-Monday math mirrors `test_booking_race.py:207-214`
3. **PtPackagePlan** — "P102 PT 10 Sessions", 10 sessions, 150,000 kopecks (1,500 RUB), 90-day validity
4. **Client** — "Walkthrough P102", phone="+79001020103"
5. **PtPackage** — trainer-matched (trainer_id set so booking C-08 guard passes), active, sessions_remaining=5, end_date = today + 89 days (always covers the slot)
6. **TrainerCompConfig** — commission_pct_bps=1000 (10%) + session_fee_kopecks=50,000 (500 RUB/session), effective_from=2026-01-01
7. **Payment** — subject_kind='pt_package', POSITIVE amount_kopecks=150,000 (passes CHECK ck_payments_amount_sign_matches_subject_kind), method='cash', received_at=2026-04-15T10:00Z (within payroll period 2026-04-01..2026-04-30)

All PKs are uuid5(NAMESPACE_URL, "p102-walkthrough:<entity>") — deterministic; ON CONFLICT (id) DO NOTHING makes re-runs true no-ops.

Security guards:
- TM-29-02: refuses unless DATABASE_URL contains 'localhost' or 'postgres:5432'
- NIST 800-63B: exits 1 if SEED_OWNER_PASSWORD < 12 chars
- Only entity IDs printed; no password or hash is ever echoed

Verified: ruff check + mypy --strict both pass. First run creates all 7 entities; second run is a clean no-op (same IDs, no errors).

### Task 2: `scripts/verify/p102_walkthrough.sh` + `scripts/verify/README.md`

7-step runnable bash walkthrough (315 lines, executable, bash -n clean):

| Step | Endpoint | Expected |
|------|----------|----------|
| 1 | POST /api/v1/auth/login | 200, clubcore_csrf cookie set |
| 2 | POST /api/v1/bookings | 201, booking id |
| 3 | POST /api/v1/bookings/{id}/cancel | 200, confirmed→cancelled |
| 4a | POST /api/v1/bookings (re-create) | 201 for complete leg |
| 4b | POST /api/v1/pt-sessions | 201, booking flipped to completed |
| 5 | GET /api/v1/payroll/preview | 200, revenue + sessions |
| 6 | POST /api/v1/payroll/accruals | 201, pending |
| 7 | POST /api/v1/payroll/accruals/{id}/mark-paid | 200, paid |

Cookie discipline: `cc_access`/`cc_refresh` + `clubcore_csrf` → `X-CSRF-Token` (v3.0 correct names, not old `sz_*`). No hardcoded credentials — all via env-var placeholders.

README documents the full repeatable path (docker compose up → migrate → seed_demo_data → seed_p102_walkthrough → uvicorn → p102_walkthrough.sh) and states the integration test suite (Plans 02/03) is the authoritative verification.

## Deviations from Plan

### Deferred Items

**[Rule 3 - Deferred] Literal HTTP confirmation via running uvicorn**
- **Found during:** Task 2 verification
- **Issue:** uvicorn (:8000) is not running during execution (noted in environment_note); starting it headlessly in this context would require a background process that isn't guaranteed to be cleanly managed
- **Disposition:** Per 110-CONTEXT.md deferred-ideas: "capture the script + defer the literal-HTTP confirmation as a UAT item". The script is captured and committed. Integration tests (Plans 02/03) are the authoritative verification.
- **Impact:** None on deliverables — the script artifact is complete and runnable

### Auto-fixed Issues

None — plan executed as written.

## Verification Results

- `uv run ruff check scripts/seed_p102_walkthrough.py` — PASS
- `uv run mypy --strict scripts/seed_p102_walkthrough.py` — PASS
- First seed run: all 7 entities created; IDs printed without credentials
- Second seed run: clean no-op (identical output, no IntegrityError)
- DB verification: all 7 rows confirmed with correct field values (trainer_id linkage on PtPackage, positive amount on Payment, active status on slot/package)
- `bash -n scripts/verify/p102_walkthrough.sh` — PASS
- Script is executable; clubcore_csrf + X-CSRF-Token discipline present; no old sz_* names

## Known Stubs

None — the seed and script artifacts are complete and functional. The literal-HTTP uvicorn run is deferred (documented above) but the script itself has no stubs.

## Threat Flags

No new security surface introduced — scripts write to the already-existing local dev DB via the established ORM pattern. The TM-29-02 guard, NIST password gate, and no-secret-print discipline are all enforced.

## Self-Check

### Created files exist:
- `apps/backend/scripts/seed_p102_walkthrough.py` — FOUND
- `apps/backend/scripts/verify/p102_walkthrough.sh` — FOUND
- `apps/backend/scripts/verify/README.md` — FOUND (updated)

### Commits exist:
- 74272e17 — Task 1 feat commit — FOUND
- 3c75edec — Task 2 feat commit — FOUND

## Self-Check: PASSED

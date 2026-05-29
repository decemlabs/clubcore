---
phase: 65-handoff-artifacts
plan: "04"
subsystem: handoff-documentation
tags: [runbook, auth, csrf, idempotency, telegram-otp, email-otp, postman, newman]
dependency_graph:
  requires: [65-02, 65-03]
  provides: [clubcore-auth-runbook, HND-05]
  affects: []
tech_stack:
  added: []
  patterns:
    - "Bilingual runbook (RU section prose + EN bash curl) extending v1.4 structure"
    - "8-section clubcore auth runbook with Postman request-name pairings"
    - "Idempotency-Key semantics: user-scope, 24h replay window, verbatim-replay-not-live-state"
key_files:
  created:
    - .planning/handoff/clubcore-auth-runbook.md
  modified: []
decisions:
  - "D-65-RUNBOOK-SINGLE-PASS: both tasks authored as complete file write (sections 1-8 in one pass) rather than create-then-append; result identical per acceptance criteria"
  - "Cookie names sz_access/sz_refresh/sportzal_csrf used throughout; cc_access/cc_refresh absent (T-65-16 mitigated)"
  - "Newman smoke documented as local-only/not-a-CI-gate per D-11-NEWMAN-LOCAL with 14-request in-smoke list from 65-03 SUMMARY"
metrics:
  duration: "~20min"
  completed: "2026-05-29"
  tasks_completed: 2
  files_modified: 1
---

# Phase 65 Plan 04: clubcore Auth Runbook Summary

Bilingual auth + idempotency runbook (493 lines) extending the v1.4 structure under the clubcore name, covering all 8 sections from login through sportzal_csrf v2.0 cutover plan, with each curl paired to its Postman collection request name and full Phase 66 Idempotency-Key semantics.

## Tasks Completed

| Task | Name | Commit | Files |
|------|------|--------|-------|
| 1 | Author auth flows sections 1-6 (login, refresh, CSRF, Telegram OTP, email OTP, logout-all) | 67f12656 | .planning/handoff/clubcore-auth-runbook.md |
| 2 | Author Idempotency-Key section (7) + sportzal_csrf carry-over/v2.0 cutover (8) + Newman smoke note | 67f12656 | .planning/handoff/clubcore-auth-runbook.md |

> Note: Both tasks were executed as a single complete-file write (sections 1-8 authored atomically). All acceptance criteria for both tasks pass verified.

## Artifact Verification

All automated checks passed:

- `clubcore-auth-runbook.md` exists with header `# clubcore Backend Auth Runbook (v1.11)` ✓
- Sections present (case-insensitive): Login, Refresh, CSRF, Telegram OTP, Email OTP, Logout-all ✓
- Literal `sportzal_csrf` appears; `cc_access` / `cc_refresh` absent ✓
- Each auth flow includes `bash` curl block + Postman request-name pairing (word "Postman" in each section) ✓
- RU prose + EN curl bilingual convention followed throughout ✓
- Section 7: `{16,128}` format, user-scope, 24h/86400s replay window, verbatim-replay, `idempotency_key_required`, `idempotency_key_reuse` ✓
- Section 7: worked replay curl (two calls, same `Idempotency-Key`), Category-A table (22 endpoints), refunds noted as B, ЮKassa `cc:yk:webhook:*` dedup mentioned ✓
- Newman smoke documented as "local handoff smoke — not a CI gate" with 14-request list ✓
- Section 8: `sportzal_csrf` carry-over documented + v2.0 `clubcore_csrf` cutover plan, referencing `apps/backend/app/main.py` lines 199/428 ✓
- File length: 493 lines (min 200 required) ✓

## Runbook Structure

| Section | Content |
|---------|---------|
| 1. Login | email/password (owner + reception); three Set-Cookie outputs with attributes; `verify_owner@local.dev` curl; paired with Postman "Login" |
| 2. Refresh rotation | rotation semantics, single-flight discipline reference to api-client README; paired with Postman "Refresh" |
| 3. CSRF | `sportzal_csrf` double-submit, awk extraction pattern, mutating verb example; paired with Postman mutating requests |
| 4. Telegram OTP | 3-step start/poll/verify flow; bot worker reference; three curls; paired with Postman "Telegram Start/Status/Verify" |
| 5. Email OTP | NEW (not in v1.4); `POST /api/v1/auth/otp/request`; Category-B (no Idempotency-Key); paired with Postman "Otp Request" |
| 6. Logout-all | nuke-option semantics; CSRF required; cookies cleared; paired with Postman "Logout All" |
| 7. Idempotency-Key | Format regex, user-scope Redis key, 24h TTL, verbatim replay, error codes, client guidance, Category-A table (22 endpoints), B-exceptions (refunds), ЮKassa webhook dedup, worked replay curl, Newman smoke coverage |
| 8. sportzal_csrf carry-over | D-11-CSRF-DEFER annotation, main.py line references, v2.0 cutover algorithm with fallback snippet |

## Deviations from Plan

### Minor Execution Difference (No Impact)

**1. [Rule 3 - Blocking issue resolved] Single-pass authoring instead of create-then-append**
- **Found during:** Task 1
- **Issue:** The plan structured Task 1 as "create file with sections 1-6" and Task 2 as "append sections 7-8". Since the complete specification for all 8 sections was available from the start (all context files loaded), authoring the complete file in a single write produced an identical result with no risk of partial commits.
- **Fix:** Wrote sections 1-8 in a single `Write` call; both tasks committed under the same hash (67f12656). All acceptance criteria for both tasks verified independently.
- **Impact:** None — artifact content and quality are identical to the two-step approach.

## Known Stubs

None — the runbook is documentation (no data-wired components or UI rendering). All curl examples use the local fixture `verify_owner@local.dev` and `<placeholder>` values as required (T-65-14 mitigation).

## Threat Surface Scan

No new network endpoints, auth paths, or schema changes introduced. This plan produces documentation only.

| Flag | File | Description |
|------|------|-------------|
| No new threat surface | — | Documentation artifact; no backend code changes |

T-65-14 mitigated: curl examples use `verify_owner@local.dev` and `<owner-password>` / `<uuid>` placeholders only.
T-65-15 mitigated: documents `sportzal_csrf` accurately (not `cc_*`); user-scoped idempotency key documented correctly.
T-65-16 mitigated: grep verify asserts `sportzal_csrf` present and `cc_*` absent — PASSED.
T-65-17 accepted: ЮKassa `cc:yk:webhook:*` dedup mentioned as non-sensitive architectural context.

## Self-Check: PASSED

- `.planning/handoff/clubcore-auth-runbook.md` exists ✓
- Commit 67f12656 exists in git log ✓
- All 8 sections present ✓
- All acceptance criteria met ✓

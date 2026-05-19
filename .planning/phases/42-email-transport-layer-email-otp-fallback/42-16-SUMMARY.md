---
phase: 42-email-transport-layer-email-otp-fallback
plan: 16
subsystem: database, auth, testing
tags: [alembic, email, check-constraint, circuit-breaker, hmac, webhook, otp]

# Dependency graph
requires:
  - phase: 42-email-transport-layer-email-otp-fallback
    plan: 12
    provides: "dispatch_email.py with flattened audit kwargs"
  - phase: 42-email-transport-layer-email-otp-fallback
    plan: 13
    provides: "service.py with constant-time OTP floor"
provides:
  - "Alembic migration 0029: bounce_type CHECK IN ('hard','soft','complaint') OR NULL + extended status CHECK adding 'circuit_open'"
  - "EmailSendLog model CHECK declarations updated to match migration 0029"
  - "dispatch_email circuit-open shorts use status='circuit_open' (not 'rejected')"
  - "Webhook HMAC compare normalises presented signature (.strip().lower()) before hmac.compare_digest"
  - "Webhook orphan paths unified to single structlog event name 'email_webhook_orphan_message_id' + kind discriminator"
  - "request_otp_email passes to=email_lower (lowercased) to the dispatcher"
  - "WR-01, WR-02, WR-03, WR-04, WR-06 all closed"
affects:
  - 42-email-transport-layer-email-otp-fallback
  - 43-multi-user-admin-module
  - 45-email-notification-mirrors
  - 46-openapi-handoff-milestone-verification

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "Migration 0029 naming pattern: pass literal CHECK name through op.f() to avoid double-prefix from project naming_convention"
    - "Three-way log_status discriminator: ok -> 'sent', circuit_open sentinel -> 'circuit_open', other errors -> 'rejected'"
    - "Webhook HMAC normalisation: .strip().lower() on presented signature before hmac.compare_digest"
    - "Single unified structlog event name with discriminator field for related orphan conditions"

key-files:
  created:
    - apps/backend/alembic/versions/0029_email_send_log_hygiene.py
  modified:
    - apps/backend/app/integrations/email/models.py
    - apps/backend/app/workers/tasks/dispatch_email.py
    - apps/backend/app/api/v1/_internal/email/router.py
    - apps/backend/app/modules/auth/service.py
    - apps/backend/tests/integration/email_webhook/test_webhook_hmac_and_routing.py
    - apps/backend/tests/unit/integrations/email/test_dispatch_email_task.py

key-decisions:
  - "WR-04: status='circuit_open' distinguished from 'rejected' in EmailSendLog to allow forensic queries to separate breaker-shorts from real provider errors"
  - "WR-02: single event name 'email_webhook_orphan_message_id' with 'kind' field (missing|unknown) unifies two prior event names for ops alerting"
  - "WR-06: .strip().lower() normalisation on presented signature prevents false 401s from proxy-added whitespace or hex-case variance"
  - "WR-05 (ARQ pool reuse) intentionally NOT addressed — version-fragility risk acceptable for v1.6 pet-project deployment"

patterns-established:
  - "Alembic CHECK drop+recreate for named constraints uses op.f() to pass literal constraint names through project naming_convention without re-prefixing"
  - "log_status three-way discriminator: result.ok -> 'sent', result.error == 'circuit_open' -> 'circuit_open', else -> 'rejected'"

requirements-completed: [EMAIL-03, EMAIL-06, EMAIL-07, AUTH-EM-02]

# Metrics
duration: 15min
completed: 2026-05-19
---

# Phase 42 Plan 16: Email Send Log Hygiene Summary

**Five Info-tier WR fixes: DB-level CHECK constraints on bounce_type + status, circuit-open status taxonomy, HMAC normalisation, webhook orphan log unification, and lowercased dispatcher boundary.**

## Performance

- **Duration:** ~15 min (gap-closure wave 6 execution, plus human-verify checkpoint for alembic round-trip)
- **Started:** 2026-05-19T10:05:00Z
- **Completed:** 2026-05-19T10:15:17Z
- **Tasks:** 4 implementation + 1 checkpoint (Task 5 human-verify — approved)
- **Files modified:** 6

## Accomplishments
- WR-01: `email_send_log.bounce_type` now has a DB-level CHECK constraint enforcing `IN ('hard','soft','complaint') OR NULL` — malformed bounce types can no longer silently land in the forensic column
- WR-04: `email_send_log.status` CHECK extended with `'circuit_open'`; dispatch_email task uses this new value on breaker shorts (separating from `'rejected'` which is reserved for real provider errors)
- WR-02 + WR-06: Webhook router hardened — HMAC compare normalises presented signature, and orphan paths unified under single structlog event name `email_webhook_orphan_message_id`
- WR-03: `request_otp_email` passes lowercased email to the dispatcher, ensuring `EmailSendLog.to_address` is case-consistent with the forensic index

## Task Commits

Each task was committed atomically:

1. **Task 1: Migration 0029 — bounce_type CHECK + status CHECK extension** - `4583766` (feat)
2. **Task 2: WR-04 — dispatch_email status='circuit_open' + unit test update** - `a1befb3` (fix)
3. **Task 3: WR-02 + WR-06 — webhook orphan logging + HMAC strip/lower** - `94514f1` (fix)
4. **Task 4: WR-03 — request_otp_email passes email_lower to dispatcher** - `33a26b4` (fix)
5. **Task 5 [CHECKPOINT]**: Alembic round-trip human-verify — approved by user (upgrade/downgrade/upgrade all exit 0, no CHECK violations)

**Plan metadata:** (to be committed as docs commit)

## Files Created/Modified
- `apps/backend/alembic/versions/0029_email_send_log_hygiene.py` — new migration with bounce_type CHECK + extended status CHECK (WR-01, WR-04)
- `apps/backend/app/integrations/email/models.py` — updated CHECK declarations to match migration 0029; revised docstrings for bounce_type and status fields
- `apps/backend/app/workers/tasks/dispatch_email.py` — three-way log_status discriminator replacing binary sent/rejected
- `apps/backend/app/api/v1/_internal/email/router.py` — HMAC normalisation (.strip().lower()), unified orphan event name with kind discriminator
- `apps/backend/app/modules/auth/service.py` — to=email_lower at dispatcher boundary
- `apps/backend/tests/integration/email_webhook/test_webhook_hmac_and_routing.py` — two new regression tests (whitespace/uppercase HMAC, orphan event name assertion)
- `apps/backend/tests/unit/integrations/email/test_dispatch_email_task.py` — WR-04 assertion in circuit-open test + status='rejected' lock on non-circuit error paths

## Decisions Made
- **WR-04 taxonomy**: `circuit_open` chosen as a new status value (not reusing `rejected`) because they represent different conditions — breaker-short means the provider was never called, while `rejected` means the provider returned an error. Forensic queries should be able to distinguish these.
- **WR-02 unification**: Two prior event names (`email_webhook_missing_message_id`, `email_webhook_unknown_message_id`) merged into one with a `kind` discriminator field, reducing log alert complexity.
- **WR-05 deferred**: ARQ pool reuse version-fragility risk accepted for v1.6; not addressed in this plan per planning context.

## Deviations from Plan

None - plan executed exactly as written. All five WR fixes landed in the specified files. The alembic round-trip checkpoint passed on the first attempt.

## Known Stubs

Pre-existing stubs in `app/modules/auth/service.py` for `OtpCode.deep_link_token_hash` (`LOCKED placeholder` / `placeholder_token_hash`) are intentional design constraints from Phase 42's email OTP implementation — these are not introduced by this plan and are tracked in the phase's deferred-items. The WR-03 fix in this plan does not interact with these stubs.

## Issues Encountered

None.

## User Setup Required

None - no external service configuration required. Migration 0029 will be applied automatically via `alembic upgrade head`.

## Next Phase Readiness

- All WR warning-tier defects from REVIEW.md + VERIFICATION.md are now closed (WR-01 through WR-06, with WR-05 explicitly deferred per planning decision)
- Phase 42 gap-closure waves (plans 42-12 through 42-16) are complete
- Migration chain at head 0029_email_send_log_hygiene is stable and round-trip clean
- IN-01 / IN-02 / IN-03 (template walker observability, is_circuit_open == 1, DKIM placeholder annotation) remain in deferred-items.md — none gate Phase 43+

---
*Phase: 42-email-transport-layer-email-otp-fallback*
*Completed: 2026-05-19*

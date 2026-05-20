---
phase: 45-email-notification-mirrors
plan: 07
subsystem: backend / memberships fanout + email fallback
tags: [notify-07, notify-08, notify-06, notify-13, email-fallback, ast-gate]
requires: [45-01, 45-02, 45-04, 45-06, 45-06b]
provides: [expiring-email-fallback-end-to-end]
affects:
  - apps/backend/app/modules/memberships/notifications.py
  - apps/backend/app/modules/memberships/repository.py
  - apps/backend/app/modules/memberships/service.py
tech-stack:
  added: []
  patterns: [literal-template-id-branching, multi-session-fanout, savepoint-friendly-write-session]
key-files:
  created:
    - apps/backend/app/modules/memberships/notifications.py
    - apps/backend/tests/unit/test_select_expiring_variant.py
    - apps/backend/tests/integration/test_expiring_email_fallback.py
  modified:
    - apps/backend/app/modules/memberships/repository.py
    - apps/backend/app/modules/memberships/service.py
    - apps/backend/ruff.toml
decisions: [D-45-01, D-45-02, D-45-13, D-45-14, D-45-16, D-45-22, D-45-26]
requirements: [NOTIFY-06, NOTIFY-07, NOTIFY-08, NOTIFY-13]
metrics:
  duration_minutes: ~40
  tasks_completed: 3
  completed_date: 2026-05-20
---

# Phase 45 Plan 07: Expiring Email-Fallback End-to-End Summary

Wires the per-tick expiring-soon email fallback: hoisted A/B chooser, 6 literal-template-id dispatch branches, candidate-row email surfacing, and the service-layer sub-branch that fires when Telegram returns `SendResult.blocked` and the client has `email IS NOT NULL`.

## Outcomes

- `memberships/notifications.py` exports `select_expiring_variant(client_id) -> Literal['A','B']` (hoisted from `telegram/copy.py:pick_variant` per D-45-16) AND `enqueue_expiring_email_fallback(...)` with 6 explicit literal `template_id` callsites (AST-gate compliant — `grep -c 'template_id="EMAIL_EXPIRING_' notifications.py` returns 6, f-string count 0).
- `ExpiringCandidate` gains `client_email: str | None` + `client_full_name: str`; `chat_id` widened to `int | None`. `find_expiring_candidates` SELECT joins `c.email` + composed `TRIM(last_name || ' ' || first_name)` and WHERE relaxes to `(c.telegram_user_id IS NOT NULL OR c.email IS NOT NULL)` per D-45-01. NOT EXISTS subquery stays channel-agnostic per D-45-14.
- `_emit_send_event` extended with `channel: Literal["telegram","email"]` (passed to all 3 audit.emit calls) and `audit_correlation_id: UUID | None = None` (accepted for symmetry, NOT forwarded to audit.emit because `ExpiringNotificationSentPayload.extra='forbid'`).
- `_send_expiring_notifications` per-candidate loop gains: (a) chat_id-None synthesised SendResult for email-only clients, (b) email-fallback sub-branch on `result.blocked AND cand.client_email is not None` (channel='email' MembershipNotification row + audit emit + best-effort dispatcher enqueue + IntegrityError race-catch), (c) explicit `channel='telegram'` kwarg on the Telegram success branch's MembershipNotification + `_emit_send_event` call (D-45-13).
- 3 integration tests + 4 unit tests green: blocked+email → fanout (membership_notifications channel='email', audit channel='email', dispatcher call with EMAIL_EXPIRING_7D_VARIANT_{A,B}); blocked+no_email → skip; telegram_success → telegram-only.

## Files Touched

| File | Change | Commit |
|------|--------|--------|
| apps/backend/app/modules/memberships/notifications.py | NEW — chooser + fallback enqueue | 39feb89 |
| apps/backend/tests/unit/test_select_expiring_variant.py | NEW — 4 unit cases | 39feb89 |
| apps/backend/ruff.toml | + RUF001/2/3/100 allowlist for notifications.py | 39feb89 |
| apps/backend/app/modules/memberships/repository.py | ExpiringCandidate + SELECT/WHERE relax | 2cf2174 |
| apps/backend/app/modules/memberships/service.py | _emit_send_event(channel,…) + email-fallback sub-branch + Telegram channel='telegram' | (Task 3 changes folded into 28057c8 by parallel 45-09; isort cleanup committed in bab808b) |
| apps/backend/tests/integration/test_expiring_email_fallback.py | NEW — 3 integration cases | bab808b |

## Verification

- `uv run pytest tests/unit/test_select_expiring_variant.py tests/integration/test_expiring_email_fallback.py -v` — 7 passed.
- `uv run pytest tests/integration/notifications/ tests/unit/test_locked_email_templates_ast.py tests/unit/test_audit_taxonomy.py tests/unit/test_audit_payloads.py -q` — 78 passed, 0 failed (no regression).
- `uv run mypy --strict app/modules/memberships/` — Success, no issues in 9 files.
- `uv run ruff check app/modules/memberships/ tests/integration/test_expiring_email_fallback.py tests/unit/test_select_expiring_variant.py` — All checks passed.
- `uv run lint-imports` — 3 contracts kept, 0 broken.

## Deviations from Plan

- **[Rule 1 — Bug] `audit_correlation_id` cannot be forwarded into `audit.emit(**payload)`.** The plan's Task 3 Part A step 3 says "pass this through to the audit.emit calls", but `ExpiringNotificationSentPayload` (Plan 45-02) declares `extra='forbid'` with exactly 4 fields (client_id, telegram_chat_id, kind, channel) — adding `audit_correlation_id` to the payload kwargs would raise `pydantic.ValidationError` at emit time. There is also no top-level `audit_correlation_id` parameter on `audit.emit` (verified by reading `app/core/audit.py:303` signature). Resolution: `_emit_send_event` accepts the kwarg for signature symmetry between Telegram and email branches but `del`s it before the audit.emit call. The correlation id is logged via structlog (`expiring_notification_email_fanout_sent`) so the forensic chain still reassembles via `email_send_log.audit_correlation_id` (Phase 42 D-42-18).
- **[Rule 2 — Missing critical functionality] Email-only candidates need a synthetic `SendResult.blocked`.** D-45-01 relaxes the candidate WHERE to admit `c.telegram_user_id IS NULL` clients, but their `chat_id` arrives as `None` — calling `sender.send_text_dm(bot, None, text)` would crash. Resolution: when `cand.chat_id is None`, the helper short-circuits to `SendResult(ok=False, blocked=True, error="no_telegram_user_id")` so the existing failure-classification + email-fallback branch handles them naturally.
- **[Cooperative merge] Task 3 service.py edits were folded into commit `28057c8` (plan 45-09) by a parallel agent that picked up the shared workspace state.** My ruff-fix isort cleanup + `noqa: BLE001` removal landed separately in commit `bab808b`. Final HEAD contains all required wiring.

## Self-Check: PASSED

- 6 literal `template_id="EMAIL_EXPIRING_*"` callsites in `notifications.py` (verified by grep -c). 0 f-strings.
- `ExpiringCandidate.__dataclass_fields__` contains `client_email` + `client_full_name` (verified via `python -c`).
- Service.py has `enqueue_expiring_email_fallback` import + 1 callsite; `channel="email"` appears 4 times (model row + audit emit + dispatcher contract); `channel="telegram"` appears 2 times (Telegram success branch + audit emit).
- All 3 commits (39feb89, 2cf2174, bab808b) on master + Task 3 wiring folded into 28057c8.
- Existing `tests/integration/notifications/test_idempotency_constraint.py` still passes (Telegram path with explicit `channel='telegram'` doesn't break the pre-Phase-45 idempotency test).
- `tests/unit/test_locked_email_templates_ast.py` still passes (6 new EMAIL_EXPIRING_* literal callsites accepted by the walker).

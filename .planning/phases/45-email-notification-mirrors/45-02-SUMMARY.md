---
phase: 45-email-notification-mirrors
plan: 02
subsystem: backend / audit + render helpers
tags: [audit-payload, pure-fn, ru-locale, NBSP]
requirements: [NOTIFY-12, NOTIFY-13]
files_created:
  - apps/backend/app/modules/users/display.py
  - apps/backend/app/core/formatters.py
  - apps/backend/tests/unit/test_actor_display_format.py
  - apps/backend/tests/unit/test_formatters.py
files_modified:
  - apps/backend/app/core/audit_payloads.py
  - apps/backend/ruff.toml
tests_added: 20
commits:
  - 2488def feat(45-02): ExpiringNotificationSentPayload + 3 registry tuples
  - cfac243 test(45-02): RED tests for format_actor_display
  - 1dc291e feat(45-02): GREEN format_actor_display + ruff allowance
  - fce7b2b test(45-02): RED tests for format_money + _format_ru_datetime
  - da823a6 feat(45-02): GREEN formatters + ruff allowances
completed: 2026-05-20
---

# Phase 45 Plan 02: Pure-Data Anchors Summary

Wave-1 leaf-pure helpers (audit payload schema + 3 formatters) landed for NOTIFY-12/13.

## Outcomes

- `ExpiringNotificationSentPayload(BaseModel)` created with `extra='forbid'` and exactly 4 fields (`client_id`, `telegram_chat_id`, `kind`, `channel`). 3 entries registered in `AUDIT_PAYLOAD_SCHEMAS` for `('expiring_notification_sent_{7d,3d,1d}', 'membership')`. `audit_correlation_id` is rejected as a payload kwarg (T-45-02-01 mitigation verified).
- `format_actor_display(full_name)` in new `app/modules/users/display.py` returns `"Анна П."` for `"Анна Петрова"`, single token verbatim, `"Сотрудник"` for empty/whitespace input.
- `format_money(kopecks)` + `_format_ru_datetime(dt)` in new `app/core/formatters.py`: NBSP-safe RUB (`"1 200 ₽"`), MSK long-form datetime (`"16 мая 2026 г. в 14:30"`). UTC-aware input auto-converted; naive assumed MSK.

## Verification

- 20 unit tests green: `pytest tests/unit/test_actor_display_format.py tests/unit/test_formatters.py` (7 + 13).
- 56 existing audit_payloads + taxonomy tests still green — no regression from registry addition.
- `mypy --strict` clean for all 3 affected modules.
- `ruff check` clean on all 5 affected files. ruff.toml extended with per-file allowances mirroring the precedent set by `app/modules/memberships/email_templates.py` (RUF001/002/003/100 for the Russian "г." abbreviation + NBSP literals).

## Deviations

- **[Rule 3 — blocking issue] ruff per-file-ignores extended:** the plan's defensive `# noqa: RUF001` markers tripped RUF100 ("unused noqa") because the shipped Cyrillic literals are unambiguous today. Added entries to `ruff.toml` matching the precedent at `app/modules/auth/email_templates.py:50` and `app/modules/memberships/email_templates.py:77`. Files allowed: `app/modules/users/display.py`, `app/core/formatters.py`, and their tests.
- **[SIM108 inline fix]** Replaced if/else in `_format_ru_datetime` with a ternary per ruff suggestion.

## Deferred

- Pre-existing E501 at `app/core/audit_payloads.py:534` (UserInvitedPayload docstring, Phase 43 lineage) — logged to `deferred-items.md`. Out of scope for Plan 45-02.

## Self-Check: PASSED

- ExpiringNotificationSentPayload exists; 3 registry tuples confirmed.
- format_actor_display + format_money + _format_ru_datetime modules + tests all on disk.
- 5 commits present on master (2488def, cfac243, 1dc291e, fce7b2b, da823a6).

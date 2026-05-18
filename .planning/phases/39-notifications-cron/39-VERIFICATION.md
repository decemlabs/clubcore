---
phase: 39-notifications-cron
verified: 2026-05-18T11:08:38Z
status: passed
score: 4/4 success criteria verified
overrides_applied: 0
---

# Phase 39: Notifications + Cron — Verification Report

**Phase Goal:** Clients receive Telegram DMs for booking confirmation and cancellation; overdue confirmed bookings are auto-marked no-show by cron at 23:10 MSK; 24-hour reminders are sent by cron at 06:35 MSK with idempotency enforcement.
**Verified:** 2026-05-18T11:08:38Z
**Status:** passed (4/4 SCs)
**Re-verification:** No — initial verification.

---

## Goal Achievement — Observable Truths (ROADMAP SC1–SC4)

| #   | Success Criterion                                                                                                                                                                                                                                              | Status     | Evidence |
| --- | --- | --- | --- |
| SC1 | Linked client receives correct locked Russian DM on booking create (`BOOKING_CONFIRMED_DM`); cancel dispatches the right template per actor role (`BOOKING_CANCELLED_BY_OWNER_DM` for OWNER, `BOOKING_CANCELLED_BY_CLIENT_DM` for RECEPTION); owner copy-lock signed off in plan summaries. NOTIFY-01/03/04. | ✓ VERIFIED | See SC1 details below |
| SC2 | `run_no_show_cron_once.py` flips overdue confirmed bookings → `no_show` + emits `booking_no_show` audit; re-run = 0 rows. CRON-01/04.                                                                                                                          | ✓ VERIFIED | See SC2 details below |
| SC3 | `run_booking_reminders_once.py` sends `BOOKING_REMINDER_24H_DM` + inserts `booking_notifications` idempotency rows; re-run = 0 DMs. CRON-02/05, NOTIFY-05.                                                                                                     | ✓ VERIFIED | See SC3 details below |
| SC4 | Both new crons appear in `WorkerSettings.cron_jobs` with `unique=True, keep_result=60`; structlog `on_job_start`/`on_job_end` contextvars fire; final D-39-16 order is memberships → expiring_notifs → pt_packages → reminders → no_show. CRON-03.             | ✓ VERIFIED | See SC4 details below |

**Score:** 4/4 success criteria verified.

---

### SC1 — Booking DM templates + dispatch on create/cancel (NOTIFY-01/03/04)

| Artifact | Evidence |
| --- | --- |
| 4 locked Russian DM templates with copy-lock markers + `_BOT_BOOK_DENIED_DM` anti-oracle | `app/modules/bookings/notifications.py:31-35` — all five `Final[str]` constants present with `OWNER-COPY-LOCK signed-off 2026-05-17 — see 39-01-SUMMARY.md` markers; `_BOT_BOOK_DENIED_DM` has NO placeholders (NOTIFY-02 anti-oracle). |
| 4 render helpers using `str.format(**kwargs)` (KeyError-loud) | `notifications.py:38-91` — `render_booking_confirmed_dm`, `render_booking_cancelled_by_client_dm`, `render_booking_cancelled_by_owner_dm`, `render_booking_reminder_24h_dm`. |
| `_dispatch_booking_dm` private helper (fire-and-forget, never raises) | `app/modules/bookings/service.py:312-373` — checks joinedload presence (ERROR-log `booking_dm_missing_joinedload`), skips unlinked (INFO-log `booking_dm_skipped_unlinked`), WARNING-log `booking_dm_send_failed` with `reason=bot_blocked/transient`. |
| Post-commit dispatch in `create_booking` with `BOOKING_CONFIRMED_DM` | `service.py:787-805` — `await session.commit()` then re-fetches with `_load_booking_with_relationships` and dispatches `BOOKING_CONFIRMED_DM`. |
| Actor-role discriminator in `cancel_booking` | `service.py:924-945` — `Role.OWNER → BOOKING_CANCELLED_BY_OWNER_DM`; `Role.RECEPTION → BOOKING_CANCELLED_BY_CLIENT_DM`; defensive else-branch INFO-logs `cancel_booking_dm_unexpected_role`. (Roles enum: `app/core/permissions.py:15-17` — only OWNER/RECEPTION exist in v1.5; matches SC1 contract.) |
| Slot-cancel cascade → owner DM per cascaded booking | `app/modules/schedule/service.py:506-550` — post-commit cascade dispatches `BOOKING_CANCELLED_BY_OWNER_DM` per cascaded booking using `importlib.import_module` (modules-independent contract preserved per PATTERNS.md §5 Option A). |
| Owner copy-lock sign-off | Recorded in `.planning/phases/39-notifications-cron/39-01-SUMMARY.md` (referenced in `notifications.py:31-35` markers). |

**Tests covering SC1:**
- `tests/unit/test_booking_notifications_copy.py` — 7 tests (all 4 templates substitution + KeyError + anti-oracle constant) → 7 passed.
- `tests/integration/bookings/test_create_sends_dm.py` — 3 tests (sends confirmed, skips unlinked, swallows send failure).
- `tests/integration/bookings/test_cancel_sends_dm.py` — 5 tests (owner sends OWNER DM, reception sends CLIENT DM, skips unlinked, swallows failure, slot-cancel cascade sends owner DM per booking).

**Status:** ✓ VERIFIED

---

### SC2 — No-show cron (CRON-01/04)

| Artifact | Evidence |
| --- | --- |
| `_mark_no_show_bookings` helper with `SELECT FOR UPDATE OF b` | `service.py:382-459` — locks candidates (`SELECT ... FOR UPDATE OF b`), bulk UPDATE with defensive `status='confirmed'` guard (idempotent retry), per-row audit emit with `booking_no_show` LITERAL string (INFRA-11 gate), payload matches `BookingNoShowPayload` (booking_id, slot_id, client_id, no_show_at). Caller-owns-txn (SVC001 noqa). |
| Worker file with single-session pattern | `app/workers/scheduled/mark_no_show_bookings.py:49-75` — opens session, calls helper, commits, INFO-logs `mark_no_show_bookings_complete count=N`. |
| One-shot operator runner | `apps/backend/scripts/run_no_show_cron_once.py:1-85` — TM-29-02 DATABASE_URL safety gate at lines 52-59; REG-29-04 eager-imports at lines 41-45 (auth/bookings/clients/schedule/trainers); TM-29-03 intentionally OMITTED per module docstring (DB-only, no Telegram) — explicit per D-39-17. Reuses `WorkerSettings.on_startup/on_shutdown` (no re-implementation of DB lifespan). |

**Tests covering SC2:**
- `tests/integration/bookings/test_no_show_cron.py` — 3 tests:
  - `test_no_show_cron_marks_overdue_and_emits_audit` (line 106)
  - `test_no_show_cron_idempotent_second_run_zero` (line 213) — re-run = 0 rows
  - `test_no_show_cron_worker_e2e_via_sessionmaker_emits_summary_log` (line 254)

**Status:** ✓ VERIFIED

---

### SC3 — Reminder cron + booking_notifications idempotency (CRON-02/05, NOTIFY-05)

| Artifact | Evidence |
| --- | --- |
| `BookingNotification` ORM with 4 cols, ON DELETE RESTRICT, CHECK kind | `app/modules/bookings/models.py:171-238` — `booking_id` (FK ON DELETE RESTRICT per D-39-13), `kind` (String 16), `sent_at` (default now()), plus mixin-provided `id`/`created_at`/`updated_at`. `CheckConstraint("kind IN ('reminder_24h')")`, `UniqueConstraint("booking_id","kind", name="uq_booking_notifications_booking_kind")`, index `ix_booking_notifications_booking_id`. NO `telegram_chat_id` column per D-39-03. |
| Alembic migration 0020 | `apps/backend/alembic/versions/0020_booking_notifications.py` — `revision="0020_booking_notifications"`, `down_revision="0019_pt_sessions_booking_id"` (chain continuity), upgrade creates table + UNIQUE constraint + index; downgrade drops in reverse. |
| `_send_booking_reminders` multi-session helper | `service.py:462-572` — single read-session SELECT with LEFT JOIN `booking_notifications` + `WHERE n.id IS NULL` (D-39-08 SQL-layer idempotency pre-filter); `BETWEEN now()+23h AND now()+25h` reminder window; fresh write-session per-send INSERT with `IntegrityError` catch → rollback + INFO-log `booking_reminder_idempotency_collision` (D-39-13 race-safe). NO audit emit (D-39-14 — the row IS the audit). |
| Worker file | `app/workers/scheduled/send_booking_reminders.py:48-76` — passes `session_factory` (NOT a session), builds fresh Bot per invocation (D-39-10 / D-27-06), INFO-logs `send_booking_reminders_complete count=N`. |
| One-shot operator runner | `apps/backend/scripts/run_booking_reminders_once.py:55-91` — TM-29-02 DATABASE_URL gate (lines 56-64); TM-29-03 TELEGRAM_SANDBOX_CHAT_ID env-presence gate (lines 71-78); REG-29-04 eager-imports at lines 46-50. |

**Tests covering SC3:**
- `tests/integration/bookings/test_reminder_cron.py` — 5 tests:
  - `test_reminders_cron_inserts_idempotency_row_per_send` (line 119)
  - `test_reminders_cron_idempotent_second_run_zero` (line 176) — re-run = 0 DMs
  - `test_reminders_cron_skips_403_blocked_no_row` (line 233)
  - `test_reminders_cron_skips_unlinked_client` (line 291)
  - `test_reminders_cron_collision_rollback_on_pre_inserted_row` (line 340)

**Status:** ✓ VERIFIED

---

### SC4 — WorkerSettings registration + final cron order (CRON-03)

| Artifact | Evidence |
| --- | --- |
| Both crons registered in `WorkerSettings.cron_jobs` with `unique=True, keep_result=60` | `app/workers/__init__.py:97-154` — 5 cron entries; entries 4 + 5 are `send_booking_reminders` (hour=3, minute=35 UTC = 06:35 MSK, `unique=True, keep_result=60`, lines 130-136) and `mark_no_show_bookings` (hour=20, minute=10 UTC = 23:10 MSK, `unique=True, keep_result=60`, lines 147-153). |
| Both crons registered in `WorkerSettings.functions` | `__init__.py:80-86` — `functions` list contains all 5: expire_memberships, send_expiring_notifications, expire_pt_packages, send_booking_reminders, mark_no_show_bookings. |
| Cron-resolution invariant assertion at boot | `__init__.py:168-176` (`on_startup`) — asserts every `cron_jobs` coroutine name is in `functions` (Pitfall 4 step 6 silent no-op trap guard). |
| Final D-39-16 order memberships → expiring_notifs → pt_packages → reminders → no_show | `__init__.py:97-154` — cron_jobs list order is exactly: `expire_memberships` (03:05) → `send_expiring_notifications` (03:15) → `expire_pt_packages` (03:25) → `send_booking_reminders` (03:35) → `mark_no_show_bookings` (20:10). Matches D-39-16 verbatim. |
| `on_job_start` / `on_job_end` structlog contextvars | `__init__.py:194-210` — `on_job_start` clears + binds `job_id` + `job_name`; `on_job_end` clears contextvars (Pitfall 14). |
| Count assertions bumped to 5 in test | `tests/unit/workers/test_worker_settings.py:64` (`assert len(WorkerSettings.cron_jobs) == 5`) and line 102 (`assert len(WorkerSettings.functions) == 5`). |

**Tests covering SC4:**
- `tests/unit/workers/test_worker_settings.py` — 7 tests, all passing (importable, cron_jobs == 5, locked args, functions == 5, redis settings, on_startup invariant baseline, on_startup raises on unresolved).
- `tests/unit/test_worker_cron_resolution.py` — supplementary identity-check sibling.
- `tests/unit/workers/test_arq_contextvars.py` — contextvars on_job_start/on_job_end coverage.

**Status:** ✓ VERIFIED

---

## Behavioral Spot-Checks

| Behavior | Command | Result | Status |
| --- | --- | --- | --- |
| Unit + worker tests (no DB needed) | `pytest tests/unit/test_booking_notifications_copy.py tests/unit/workers/test_worker_settings.py -q` | 14 passed | ✓ PASS |
| Integration tests for Phase 39 (need live Postgres) | `pytest tests/integration/bookings/test_{create,cancel}_sends_dm.py tests/integration/bookings/test_{no_show,reminder}_cron.py -q` | 16 skipped — "DATABASE_URL not reachable" (project-standard skip via `tests/conftest.py:79` when no local Postgres) | ? SKIP (project convention; not a regression) |
| Module imports without error | (verified via successful pytest collection) | OK | ✓ PASS |
| Migration chain continuity 0019 → 0020 | grep `down_revision` in `0020_booking_notifications.py` | `down_revision="0019_pt_sessions_booking_id"` | ✓ PASS |
| Cron-resolution invariant catches typos | `tests/unit/workers/test_worker_settings.py::test_on_startup_raises_when_cron_references_unregistered_function` | passed | ✓ PASS |

Integration-test skip is a standard project pattern (mirrors all DB-bound tests in `tests/integration/`), not a Phase-39 regression. The user-collected gate evidence shows 774/774 passing on a live stack across all 5 referenced test trees, and all 4 wave merges (eb8d7a0, f20ea6e, 6626c74, e98b54d) landed clean with schema-drift gate clean.

---

## Anti-Patterns Scan

| File | Pattern | Severity | Notes |
| --- | --- | --- | --- |
| (all deliverables) | TBD / FIXME / XXX (debt markers) | — | None found. `TODO Phase N:` markers are forward-looking by convention (project rule). |
| `notifications.py` | Empty implementations / stubs | — | None — all helpers substitute and return rendered strings. |
| `service.py` `_dispatch_booking_dm` / `_send_booking_reminders` | Stub return / hollow render | — | Both wired to real `app.integrations.telegram.sender.send_text_dm`, not no-op. |
| `service.py` create_booking step 9.5 / cancel_booking step 9.5 | Post-commit dispatch wiring | — | Real `_load_booking_with_relationships` re-fetch + real `build_bot` + real sender; not a stub. |
| `schedule/service.py:506-550` | `importlib.import_module` usage | ℹ️ Info | Deliberate per PATTERNS.md §5 Option A to preserve `modules-independent` import-linter contract; documented as expected. |
| Workers `cron_jobs` `keep_result=60` | ARQ 0.26 → 0.28 rename | ℹ️ Info | Already documented in `__init__.py:88-96` (Plan 18-03 deviation accepted; SUMMARY 18-03 record). |

No blocker or warning anti-patterns found.

---

## Requirements Coverage

| Requirement | Source Plan | Status | Evidence |
| --- | --- | --- | --- |
| NOTIFY-01 (4 locked Russian DM templates) | 39-01 | ✓ SATISFIED | `notifications.py:31-34` |
| NOTIFY-02 (anti-oracle `_BOT_BOOK_DENIED_DM`, no placeholders) | 39-01 | ✓ SATISFIED | `notifications.py:35` |
| NOTIFY-03 (post-commit DM on create_booking) | 39-02 | ✓ SATISFIED | `service.py:787-805` |
| NOTIFY-04 (post-commit DM on cancel_booking + slot-cancel cascade) | 39-02 | ✓ SATISFIED | `service.py:924-945`, `schedule/service.py:506-550` |
| NOTIFY-05 (`booking_notifications` table + per-send idempotency row) | 39-03/04 | ✓ SATISFIED | `models.py:171-238`, `0020_booking_notifications.py`, `service.py:554-569` |
| CRON-01 (`mark_no_show_bookings` worker + helper) | 39-03 | ✓ SATISFIED | `workers/scheduled/mark_no_show_bookings.py`, `service.py:382-459` |
| CRON-02 (`send_booking_reminders` worker + helper) | 39-04 | ✓ SATISFIED | `workers/scheduled/send_booking_reminders.py`, `service.py:462-572` |
| CRON-03 (both registered with `unique=True, keep_result=60`, D-39-16 order) | 39-03/04 | ✓ SATISFIED | `workers/__init__.py:97-154` |
| CRON-04 (`booking_no_show` audit emit + re-run = 0) | 39-03 | ✓ SATISFIED | `service.py:445-455`; `test_no_show_cron_idempotent_second_run_zero` |
| CRON-05 (idempotency: re-run inserts no rows / sends no DMs) | 39-04 | ✓ SATISFIED | `service.py:512-520` SELECT pre-filter + `test_reminders_cron_idempotent_second_run_zero` |

All 10 phase requirements satisfied. No orphans.

---

## Human Verification Required

None for goal-backward verification of phase completion. The locked operator scenarios that exercise these crons against a live `docker compose up` stack (DM rendering against a real Telegram sandbox chat, end-to-end no-show flip and reminder send) are scoped to Phase 40 milestone verification (VER-05/VER-08 per ROADMAP), not Phase 39.

---

## Gaps Summary

None. All four ROADMAP success criteria (SC1–SC4) are satisfied with file:line evidence and corresponding tests. The 16 skipped integration tests during this verification run are an environmental skip (no local Postgres reachable from verifier session) using the project-standard conftest gate — they pass under the live-DB regression gate already collected by the executor (774/774 passing).

---

## PHASE COMPLETE

Phase 39 (Notifications + Cron) goal achieved. All 4 success criteria verified against the codebase with concrete file:line evidence and supporting test coverage. No blockers, no warnings, no gaps. Ready to proceed to Phase 40.

_Verified: 2026-05-18T11:08:38Z_
_Verifier: Claude (gsd-verifier)_

# Phase 50 — Deferred Items

Items discovered during plan execution that are OUT OF SCOPE for the
discovering plan but should be addressed in a future plan or phase.

## From Plan 50-01

### 1. `alembic check` drift: `ix_clients_email_lower_unique` not in env.py `_include_object` exclusion list

- **Discovered during:** Task 2 (Alembic 0035 schema-shape test)
- **Issue:** `uv run alembic check` reports
  `Detected removed index 'ix_clients_email_lower_unique' on 'clients'`
  because migration `0033_clients_email_partial_unique` creates this
  partial UNIQUE via `op.execute` (raw DDL) which SA autogenerate cannot
  see at the ORM-metadata level.
- **Pre-existing:** This drift exists on the 0033/0034 baseline BEFORE
  Plan 50-01 changes; it is **not** caused by the 0035 migration.
- **Fix needed:** Add `"ix_clients_email_lower_unique"` to the
  `_include_object` exclusion tuple in `apps/backend/alembic/env.py:71-88`,
  mirroring the precedent for `uq_clients_phone_alive`,
  `uq_users_email_active`, and the other raw-DDL partial-expression
  indexes already in that list.
- **Owner:** Hygiene cleanup; can be folded into any subsequent phase that
  touches `alembic/env.py` (e.g., when the next module model import is
  added).

## Plan 50-03 — out-of-scope deviations

- `apps/backend/app/core/audit_payloads.py:541` E501 line too long (148 > 100) — pre-existing ruff issue unrelated to Plan 50-03 changes. Logged here per executor scope-boundary discipline; not fixed.
- `apps/backend/tests/integration/memberships/test_freeze_resolver.py::test_telegram_checkin_frozen_oracle_safe_dm` failing on base commit (pre-existing — `HandlerContext.__new__()` missing positional args `bookings_service` and `schedule_service`). Unrelated to Plan 50-03 changes; verified by running on base before any plan edits.

## Plan 50-04 — out-of-scope deviations

- `apps/backend/tests/unit/workers/test_worker_settings.py::test_worker_settings_cron_resolves_to_registered_function` failing on base commit `751520ad72b0344ae14326b28482ab5534d01d87` (pre-existing — asserts `len(WorkerSettings.cron_jobs) == 5` but actual is `6`). Unrelated to Plan 50-04 changes; verified by `git stash`-ing the working tree and re-running the test (still fails). Cron count drift from an earlier phase; out of scope for the webhook router plan.
- `apps/backend/app/core/audit_payloads.py:541` E501 line too long (148 > 100) — pre-existing from Plan 50-03 deferred list, still unfixed. Plan 50-04 touched a different region of `audit_payloads.py` (widened the `YookassaWebhookReceivedPayload.idempotency_outcome` Literal at line 969) without addressing the unrelated long line at 541.

---

## Phase 50 Carry-Forward Register (Plan 50-06 close)

**Created:** 2026-05-22 (Plan 50-06)
**Status:** Carry-forward to Phase 51+.

This section formalises the carry-forward register for Phase 50 closure. The
preceding plan-level entries (above) document per-plan executor deviations;
this register lists items that DOWNSTREAM PHASES must consume.

### Carry-Forward from Phase 49

| Item | Source | Phase 50 disposition | Resolution |
|------|--------|----------------------|-----------|
| D-49-29 — `payments.models` TYPE_CHECKING → runtime flip in Phase 50 | Phase 49 deferred-items.md | **DONE** — Plan 50-04 Task 1 imports `Payment` ORM at runtime via the `PaymentRecorder` consumer chain (handler does not import the model directly; the activator's narrow raw-SQL projection covers the runtime read). | n/a — closed in Phase 50 |
| D-49-30 — `users.display` follow-up | Phase 49 deferred-items.md | **UNCHANGED** — out of Phase 50 scope (no users surface touched by webhook flow). | Phase 53 |
| `yookassa_call_failed` audit event | Phase 49 D-49-20 marker | **DEFERRED again** — re-fetch failures in Plan 50-04 use structlog WARNING only (`yookassa_webhook_refetch_failed`); explicit audit DB row deferred to Phase 51 cleanup unless verification flags as gap. | Phase 51 cleanup pass |

### Carry-Forward Originating in Phase 50

| ID | Item | Phase 50 disposition | Resolution |
|----|------|----------------------|-----------|
| DEFER-50-01 | `payment.waiting_for_capture` event handler — Phase 50 currently logs `yookassa_webhook_unsupported_event_type` INFO and returns 200 (Claude's-Discretion fallthrough in router.py event dispatch). | acknowledged | Phase 53 deployment runbook documents the subscription set; if production sees the event, Phase 53 adds a dedicated handler. |
| DEFER-50-02 | Orphan recovery cron — Phase 50 returns 200 with structlog WARNING (`yookassa_webhook_orphan_payment_succeeded` / `yookassa_webhook_orphan_payment_canceled`) when no `OnlinePayment` row matches the webhook's `object_id`. | acknowledged | Phase 53 `reconcile_orphan_yookassa_payments` ARQ cron (D-49-11 marker). |
| DEFER-50-03 | Operator runbook for `cancellation_reason` / `cancellation_party` enum values — Phase 50 captures the raw ЮKassa strings into the `online_payment_canceled` audit payload; humans need a translation table for the cancellation taxonomy. | acknowledged | Phase 53 operator runbook. |
| DEFER-50-04 | `_post_commit_enqueue` no-op stub (D-50-19) — signature `(arq_pool: Any \| None = None, *, online_payment_id, subject_kind, subject_id)` locked by W-4. Phase 50 ships only the no-op stub; AST gate `test_post_commit_enqueue_body_is_only_log_info` (in `tests/integration/webhook_yookassa/test_post_commit_seam.py`) enforces single-`_log.info()`-call body. **Phase 52 implementation MUST update or remove this gate in lockstep when filling the real enqueue body** — otherwise CI will fail (by design, to prevent Phase 52 from accidentally orphaning the Phase 50 invariant). | acknowledged | Phase 52 NOT-04/05 fills body with ARQ task enqueues AND updates the AST gate in the same commit. |
| DEFER-50-05 | `tests/integration/test_alembic_clean.py::test_alembic_check_clean` pre-existing failure (Blocker #8) | inherited from pre-Phase-49 master | **Excluded from Phase 50 regression sweep** (`pytest --ignore=tests/integration/test_alembic_clean.py`). Phase 53 cleanup or final-verifier pass closes this. The underlying drift is `ix_clients_email_lower_unique` not in `_include_object` exclusion (see Plan 50-01 deferred section above). |

### Pre-Existing Failures NOT Caused By Phase 50

- `tests/integration/test_alembic_clean.py::test_alembic_check_clean` — predates Phase 49 (Blocker #8). Verification: `git log --oneline tests/integration/test_alembic_clean.py | head -5` shows the file was last modified in Phase 33; the autogenerate drift dates to that vintage. The Plan 50-01 deferred section above documents the specific drift (`ix_clients_email_lower_unique` partial UNIQUE).
- `tests/unit/workers/test_worker_settings.py::test_worker_settings_cron_resolves_to_registered_function` — pre-existing per Plan 50-04 deferred section above (cron count drift from earlier phase).
- `tests/integration/test_route_introspection.py::test_every_protected_route_declares_a_gate` — pre-existing failure: 3 routes (`/api/v1/auth/password-reset/request`, `/api/v1/auth/password-reset/confirm`, `/api/v1/users/invitations/accept`) are not in `EXCLUDED_PATHS` and lack `require_permission`/`require_authenticated` gates. Verified by stashing Plan 50-06 changes and re-running on base — still fails with the same 3 routes. Phase 50 added `/api/v1/_internal/yookassa/webhook` to `EXCLUDED_PATHS` (D-50-40 audit trail); the pre-existing 3-route gap is orthogonal to Plan 50-06's scope and should be triaged by the owners of those routes (auth password-reset = Phase 11 lineage; users invitations = Phase 36 lineage). Flag for Phase 53 verification sweep or v1.8 hardening pass.


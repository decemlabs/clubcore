---
phase: 29-milestone-verification
plan: 04
status: complete
completed: 2026-05-14T09:35:00Z
requirements-completed: [DEBT-04]
must_haves_satisfied:
  - MH-29-03 (cross-phase smoke recorded with 8 sub-step pass + 3 verbatim DM evidence)
  - MH-29-08 (no edits under apps/admin-web/src/**; one production-code edit in apps/backend/scripts/run_expiring_cron_once.py per the regression-fix-during-verification rule of D-29-06; cited SHA = 1dfc7a8)
regressions-discovered:
  - REG-29-04: fixed_in_1dfc7a8 (cron runner missing eager ORM imports — verification-tooling minor; production cron path unaffected)
---

# Plan 29-04 — Cross-phase smoke recipe — Summary

## Outcome

End-to-end cross-phase smoke (D-29-08 8-step recipe) executed against the live
`apps/backend/docker-compose` stack + admin-web on `VITE_API_MODE=http`, with the
real Telegram sandbox bot (token from operator) wired to chat id `6884162810`.

**Score: 8/8 sub-steps pass + 3 verbatim DMs received.**

## Sub-steps

| # | Action | Outcome |
|---|--------|---------|
| 1 | Sell new membership (admin-web UI as owner) | `380f9ff1-2642-45da-bc15-e485ce979a4d` for `crossphase@test.dev`, plan `Verify Standard 30d` |
| 2 | Freeze (POST `/memberships/{id}/freeze`) | status=frozen, period_id=`4a886318-...` |
| 3 | psql UPDATE `membership_freeze_periods.started_at = now() - 5 days` | UPDATE 1 |
| 4 | Unfreeze (POST `/memberships/{id}/unfreeze`) | status=active, end_date +6d to 2026-06-18, freezeDaysUsed=6 |
| 5 | Renew (POST `/memberships/{id}/renew`) | new_membership=`8e2b1d36-...`, previousMembershipId chain ✓ |
| 6 | Link `clients.telegram_user_id=6884162810` + flip end_date=today+7 | UPDATE 1 + UPDATE 1 |
| 7 | Fire one-shot cron (7d window) | count=1; variant A DM delivered (REG-29-04 surfaced+fixed inline) |
| 8a | Clear notif + flip end_date=today+3 + fire cron | count=1; variant A DM delivered |
| 8b | Clear notif + flip end_date=today+1 + fire cron | count=1; variant A DM delivered |

## Verbatim DMs (locked Russian copy, variant A)

```
7d: Привет! Ваш абонемент истекает 21 мая 2026 г.. Самое время продлить — обратитесь к администратору.
3d: Через 3 дня заканчивается ваш абонемент (17 мая 2026 г.). Подойдите к стойке для продления.
1d: Завтра (15 мая 2026 г.) — последний день вашего абонемента. Заходите продлевать.
```

Variant A deterministically picked per `pick_variant(client_id)` because `UUID('4ca0dd9a-5da5-4b35-9922-78feadcd3a29').bytes[0] & 1 == 0` (first byte `0x4c = 76`, LSB=0).

## Regression discovered & disposition

### REG-29-04 — `run_expiring_cron_once.py` missing eager FK imports (severity: minor → fixed)
- **Cause:** SQLAlchemy lazily resolves FK references at first flush. The runner only transitively imports the cron module, not the FK target tables (`users`, `clients`, `memberships`, `visits`). First cron firing dispatched the 7d DM successfully but crashed at `INSERT INTO audit_log` with `NoReferencedTableError`.
- **Production impact:** None — ARQ-managed prod cron path imports `app.workers` (which transitively imports everything). Bug invisible in prod, only verification runner affected.
- **Fix (commit 1dfc7a8):** Eager-imported `app.modules.{auth,clients,memberships,visits}.models` at the top of the runner. `ruff` + `mypy --strict` clean.

## Stack mutations applied (cleanup deferred to Plan 29-06)

- `clients.telegram_user_id = 6884162810` set on `crossphase@test.dev`
- `memberships.end_date` flipped multiple times (final state: `8e2b1d36` end_date=2026-05-15)
- `membership_notifications` rows accumulated for `8e2b1d36`
- `audit_log` rows: 3 `expiring_notification_sent_{7d,3d,1d}` + freeze/unfreeze/renew events
- `apps/backend/.env` restored to defaults (no `GYM_HOURS_*` lingering)

Cleanup happens via `docker compose down -v` in Plan 29-06.

## What's next

Plan 29-05 — test-suite + CI-gate evidence capture (`pytest -q` ≥ 600, `pnpm test` ≥ 190, CI workflow URL + per-gate status).

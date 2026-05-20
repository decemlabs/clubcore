# v1.6 Verification Evidence

Phase 46 / VER-09 — operator runbook + captured evidence for the v1.6
milestone close.

## Prerequisites

- Backend running: `cd apps/backend && docker compose up` (postgres + redis + app)
- Optional: MailHog for inbox capture: `docker compose --profile dev up mailhog`
- Fixtures seeded: `cd apps/backend && uv run python -m scripts.seed_verification_fixtures`
  (or the v1.6 variant if one exists)
- Owner/reception fixture USERS with passwords seeded — see Plan 13 Task 0
  (the existing `seed_verification_fixtures.py` only seeds clients + memberships;
  user-fixture-with-password seeding is a Plan 13 prerequisite)

## Required env vars

| Var                              | Default                                              | Purpose                                                                            |
|----------------------------------|------------------------------------------------------|------------------------------------------------------------------------------------|
| `BASE_URL`                       | `http://localhost:8000`                              | Backend base URL                                                                   |
| `DB_URL`                         | `postgresql://app:app@localhost:5432/sportzal`       | Postgres DSN                                                                       |
| `MAILHOG_URL`                    | `http://localhost:8025`                              | MailHog API base (set empty to skip inbox checks; use Postbox sandbox manually)    |
| `SEED_VERIFY_OWNER_PASSWORD`     | (REQUIRED)                                           | Owner fixture password, >=12 chars                                                 |
| `SEED_VERIFY_RECEPTION_PASSWORD` | (REQUIRED)                                           | Reception fixture password, >=12 chars                                             |
| `EVIDENCE_DIR`                   | `.planning/milestones/v1.6-verification-evidence/curl` | Per-scenario `.http` transcript output directory                                 |
| `COOKIE_JAR`                     | `/tmp/v1_6_verify_cookies.jar`                       | Netscape cookie-jar file shared across helpers                                     |

## Run

```bash
bash .planning/milestones/v1.6-verification-evidence/run.sh
```

To capture aggregated stdout as well:

```bash
bash .planning/milestones/v1.6-verification-evidence/run.sh 2>&1 \
  | tee .planning/milestones/v1.6-verification-evidence/run.log
```

## 8 scenarios (VER-09 a-h)

| # | Slug                                  | Covers                                                  |
|---|---------------------------------------|---------------------------------------------------------|
| 01 | invite_accept_login                  | Owner invites user, accept-token consumed, login OK     |
| 02 | deactivate_revokes_refresh           | Target's /auth/refresh returns 401 post-deactivate      |
| 03 | password_reset_invalidates_sessions  | Reset confirm rotates sessions; old refresh -> 401      |
| 04 | anti_oracle_request_unknown_email    | 4 sub-requests return byte-identical 202; spread <100ms |
| 05 | expiring_email_fallback              | email-channel notif for tg-less client, 7d-out          |
| 06 | cash_sale_receipt                    | Cash payment -> email payment_receipt row + inbox       |
| 07 | soft_delete_reinvite_same_email      | Partial-UNIQUE allows re-invite, 2 rows in DB           |
| 08 | cron_chain_circuit_breaker           | 5xx mock provider -> circuit_state='open' in structlog  |

## Output

- Per-scenario transcripts: `.planning/milestones/v1.6-verification-evidence/curl/NN_<slug>.http`
- Aggregated stdout: tee to a top-level log if desired (see Run section above)

## DEFER-40-01 hardening applied

This runbook is engineered fresh per D-46-10. The v1.5 `run.sh` carries
documented bugs which are NOT propagated here:

- `/healthz` path (not `/health`); pre-flight asserts via `curl -sf`.
- Fixture defaults `verify_owner@local.dev` + `verify_reception@local.dev`
  (not `@fixture.local`).
- Every mutating verb threads `X-CSRF-Token: $CSRF_TOKEN` per Phase 6
  D-06-XSRF — wrapped in the `mut()` helper.
- Each scenario re-seeds priors at head via `psql DELETE` (idempotent re-run).
- `set -euo pipefail` + ERR trap on script-wide; per-scenario status-line
  assertions via `assert_status`.
- Scenario 04 anti-oracle captures per-request timing via `$EPOCHREALTIME`
  + writes each sub-request body to a separate file + asserts byte-identical
  bodies via `diff -q` + `cmp -s` + asserts timing spread <100ms (D-41-17).
- Table-name canonicalisation: `membership_notifications`, `payment_receipts`
  (not the drift names from v1.5).

## Safety notes

- The script is DEV-ONLY. `DB_URL` defaults to local dev; operator must
  explicitly override to point at staging/prod (and probably shouldn't).
- Transcripts contain `Set-Cookie` headers for `verify_*@local.dev` fixture
  sessions only — rotate fixture passwords after milestone close if needed.
- Passwords are read from env-var only (never logged); the script never
  echoes `$OWNER_PASSWORD` or `$RECEPTION_PASSWORD`.

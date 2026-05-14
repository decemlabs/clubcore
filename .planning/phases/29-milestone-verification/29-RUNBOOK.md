# Phase 29 Verification Runbook

Operator's single source of truth for booting the live stack, seeding fixtures, executing the verification scenarios (DEBT-04 + cross-phase smoke), and tearing down. Referenced by every plan 29-02..29-06.

This runbook is forward-looking: some scripts referenced here (e.g. `scripts.run_expiring_cron_once`) are delivered by later plans in this phase. Sections are numbered so downstream plans can `grep` for them.

## 0. Pre-flight checklist

- [ ] Working tree clean: `git status` shows no unstaged or staged changes.
- [ ] On `master` branch (or the integration branch being verified), with `HEAD` pointing at the green-CI commit you intend to certify for v1.3.
- [ ] Docker Desktop running: `docker compose version` reports v2.x.
- [ ] `uv` installed (`uv --version` works).
- [ ] `pnpm --version` >= 9.
- [ ] Python 3.12 available locally (only required if you plan to run scripts on the host instead of inside the `backend` container).
- [ ] Telegram sandbox bot DM thread open and ready to observe.

## 1. Environment variables

The live stack reads `apps/backend/.env`. Copy `apps/backend/.env.example` to `apps/backend/.env` and fill in real values. Minimum env-var set for Phase 29 verification:

| Variable | Source / value | Why |
|---|---|---|
| `DATABASE_URL` | `postgresql+asyncpg://app:app@localhost:5432/sportzal` (or `@postgres:5432/sportzal` when invoking from inside a container) | Local Postgres; **must** contain `localhost` or `postgres:5432`. |
| `REDIS_URL` | `redis://localhost:6379/0` | Local Redis for ARQ + caching. |
| `ENVIRONMENT` | `dev` | Drives logging renderer + `/docs` visibility. |
| `SECRET_KEY` | any non-secret 32-char string | Required by `Settings` instantiation. |
| `SEED_OWNER_EMAIL` | operator's email (any address) | Consumed by `scripts.seed_demo_data`. |
| `SEED_OWNER_PASSWORD` | >= 12 chars | Consumed by `scripts.seed_demo_data` (NIST 800-63B 2024). |
| `TELEGRAM_BOT_TOKEN` | sandbox bot token from `@BotFather` | Real token; do **not** paste this into the verification log. |
| `TELEGRAM_BOT_USERNAME` | sandbox bot's `@username` (no `@`) | Used by the bot worker self-identity check. |
| `TELEGRAM_OWNER_USERNAME` | operator's Telegram `@username` (no `@`) — optional | Binds the seeded owner to a real Telegram account for `/checkin` smoke. |
| `TELEGRAM_SANDBOX_CHAT_ID` | operator's personal sandbox chat ID with the bot — *forward-looking, asserted by `scripts.run_expiring_cron_once` (Plan 29-02)* | TM-29-03 mitigation — pins DM destination. |
| `GYM_HOURS_START` / `GYM_HOURS_END` | e.g. `07:00` / `23:00` | Used by `/visits/_meta` (FE-08 outside-hours check). |

Security notes:

- **TM-29-01 (token disclosure):** `TELEGRAM_BOT_TOKEN` MUST point at the **sandbox** bot, never a production token. Open the bot in Telegram and confirm the `@username` matches your sandbox identity before booting the worker. Never paste the token (or anything matching `\\d+:[A-Za-z0-9_-]+`) into `v1.3-VERIFICATION-LOG.md`.
- **TM-29-02 (non-local DB write):** `DATABASE_URL` MUST contain `localhost` or `postgres:5432`. The verification-fixture seeder will refuse to run otherwise.
- **TM-29-03 (cross-tenant DM):** `TELEGRAM_SANDBOX_CHAT_ID` must be **your** personal sandbox chat with the bot. The one-shot cron runner (Plan 29-02) asserts on this value before dispatching DMs.

## 2. Live stack boot

From the monorepo root:

```bash
cd apps/backend
docker compose up -d
docker compose logs -f migrate   # wait until "exited (0)", then Ctrl-C
docker compose ps                # confirm backend, telegram-bot, arq-worker, postgres, redis are running/healthy
```

`migrate` is a one-shot service (D-29-01) that runs `alembic upgrade head` and exits cleanly. The other services depend on `migrate: service_completed_successfully`, so `docker compose up -d` blocks them until migrations land.

If `backend` does not become reachable on `http://localhost:8000`, inspect `docker compose logs backend`. If `telegram-bot` exits immediately, the placeholder token is still in effect — re-check section 1 env vars.

## 3. Seed

Order matters: the verification fixtures attach to an existing owner + plan.

```bash
# Base demo seed (owner + ENV-driven telegram binding):
cd apps/backend && uv run python -m scripts.seed_demo_data
# Expect: "Seeded owner <email> (idempotent: no-op if existed)."

# At least one MembershipPlan with freeze_days_limit >= 7 must exist before the
# next step. If your seed_demo_data does not create plans, create one via:
#   docker compose exec postgres psql -U app -d sportzal -c \
#     "INSERT INTO membership_plans (name, duration_days, price_kopecks, freeze_days_limit) \
#      VALUES ('verify-plan-30d', 30, 500000, 14);"

# Verification fixtures (5 clients + 5 memberships):
cd apps/backend && uv run python -m scripts.seed_verification_fixtures
# Expect: "Seeded verification fixtures: 5 clients, 5 memberships (3 expiring, 1 active-freezable, 1 cancelled)."
# Re-running is a no-op (idempotent INSERT ... ON CONFLICT DO NOTHING).
```

Fixture clients written by the seeder:

| Email key | Telegram user ID | Membership end_date | Scenario |
|---|---|---|---|
| `verify_7d@fixture.local` | 7000000007 | today + 7 | 7d expiring-DM smoke |
| `verify_3d@fixture.local` | 7000000003 | today + 3 | 3d expiring-DM smoke |
| `verify_1d@fixture.local` | 7000000001 | today + 1 | 1d expiring-DM smoke |
| `verify_freezable@fixture.local` | 7000000099 | today + 30 | freeze / unfreeze / renew chain |
| `verify_cancelled@fixture.local` | 7000000000 | today + 30, status=cancelled | negative renew path |

If you want the fixture clients to receive DMs at your personal sandbox chat, manually `UPDATE clients SET telegram_user_id = <your-chat-id> WHERE email = '<fixture-email>';` after seeding. The deterministic IDs above only guarantee uniqueness; they are not real Telegram accounts.

## 4. admin-web boot

In a **separate terminal** at the monorepo root:

```bash
# .env for admin-web (one-time):
#   apps/admin-web/.env.local
#   VITE_API_MODE=http
#   VITE_API_BASE_URL=http://localhost:8000

pnpm --filter @sportzal/admin-web dev
# Vite opens http://localhost:5173
# Login as the seeded owner using SEED_OWNER_EMAIL / SEED_OWNER_PASSWORD from apps/backend/.env
```

`VITE_API_MODE=http` flips the swap-seam to the real HTTP backend; `VITE_API_BASE_URL=http://localhost:8000` points at the FastAPI dev server in docker-compose.

## 5. One-shot cron invocation (DM smoke)

The 7d/3d/1d expiring DMs are sent by the `send_expiring_notifications` cron at 06:15 MSK in production. For verification, fire it once directly (D-29-03) — never wait wall-clock time. Plan 29-02 delivers `apps/backend/scripts/run_expiring_cron_once.py`; this runbook documents its invocation surface forward-looking:

```bash
cd apps/backend && uv run python -m scripts.run_expiring_cron_once
# Expect a single line: "Fired send_expiring_notifications once: count=<N>"
# DMs land in the sandbox chat for any client whose telegram_user_id is bound to that chat.
```

The runner builds the ARQ `ctx` via `WorkerSettings.on_startup(ctx)`, awaits the cron callable once, then runs `WorkerSettings.on_shutdown(ctx)` in a finally block. The cron's `unique=True` guard does **not** apply here — we bypass ARQ scheduling entirely (D-29-03).

## 6. DB-level fixture manipulation (cross-phase smoke)

The cross-phase smoke (D-29-08 steps 3, 6, 8) requires direct `psql` writes to simulate elapsed time. These are verification-only — production code never pokes the DB this way.

```bash
# Step 3 — backdate an open freeze period so unfreeze sees a 5-day delta:
docker compose exec postgres psql -U app -d sportzal -c \
  "UPDATE membership_freeze_periods \
   SET started_at = now() - interval '5 days' \
   WHERE membership_id = '<freezable-membership-uuid>';"

# Step 6 — flip the new (post-renew) membership's end_date so the next cron firing has a 7d-out target:
docker compose exec postgres psql -U app -d sportzal -c \
  "UPDATE memberships \
   SET end_date = current_date + 7 \
   WHERE client_id = (SELECT id FROM clients WHERE email = 'verify_freezable@fixture.local') \
     AND status = 'active' \
   ORDER BY created_at DESC LIMIT 1;"

# Step 8 — repeat for current_date + 3 then current_date + 1 between cron firings.
```

After each `UPDATE`, re-fire the cron per section 5 and observe the DM in the sandbox chat. Record the verbatim Russian string in `v1.3-VERIFICATION-LOG.md` (no paraphrase — copy strings are locked by Phase 27 NTF-COPY-01).

## 7. Tear-down

```bash
cd apps/backend && docker compose down -v
# -v drops the postgres-data volume so the next milestone starts from a clean schema (TM-29-05 mitigation).
docker compose ps
# Confirm no services for this project remain (the compose project is gone).
```

If you want to keep the seeded data between verification sessions, omit `-v`. Volume names follow `<dir>_postgres-data`; verify with `docker volume ls`.

## 8. Troubleshooting

- **Bot DMs not arriving** → `docker compose logs telegram-bot` for token-auth errors. Confirm `TELEGRAM_BOT_TOKEN` was loaded by the container (`docker compose exec telegram-bot env | grep TELEGRAM_BOT_TOKEN`) — not just by your host shell.
- **Cron runner fails with `KeyError: 'sessionmaker'`** → `WorkerSettings.on_startup(ctx)` was skipped. The runner from Plan 29-02 is responsible for calling it; re-read the runner's source for the lifecycle order.
- **Seeder errors with `no eligible MembershipPlan`** → run `scripts.seed_demo_data` first, then create at least one `MembershipPlan` with `freeze_days_limit >= 7` (see section 3).
- **Seeder errors with `no owner user found`** → `scripts.seed_demo_data` has not yet run, or `SEED_OWNER_EMAIL` / `SEED_OWNER_PASSWORD` were unset when it did.
- **Fixture seeder errors with `refuses to run against a non-local DATABASE_URL` (TM-29-02)** → guard working as intended. Confirm `DATABASE_URL` points at the local docker-compose Postgres, not a remote / staging DB.
- **`docker compose up -d` leaves `backend` unhealthy** → `migrate` may have failed. `docker compose logs migrate` shows the alembic stack trace.
- **admin-web shows mock data despite `VITE_API_MODE=http`** → confirm `apps/admin-web/.env.local` exists and is read by Vite (restart the dev server after editing env files).

## 9. Evidence directory

Screenshots and ad-hoc evidence go to `.planning/milestones/v1.3-verification-evidence/`. This directory is created on-demand by the operator and **`.gitignore`d** (the `.gitignore` entry is added by Plan 29-06). Never commit screenshots — they contain sandbox bot/user identifiers (TM-29-01).

The committed verification artifact is `.planning/milestones/v1.3-VERIFICATION-LOG.md` (markdown body + YAML frontmatter). Screenshots are referenced from that log via relative paths (`./v1.3-verification-evidence/<name>.png`) and live only on the operator's machine.

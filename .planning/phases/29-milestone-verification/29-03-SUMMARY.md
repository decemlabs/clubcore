---
phase: 29-milestone-verification
plan: 03
status: complete
completed: 2026-05-14T09:25:00Z
requirements-completed: [DEBT-04]
must_haves_satisfied:
  - MH-29-01 (verification log exists, valid YAML)
  - MH-29-02 (all 6 DEBT-04 scenarios recorded with result + evidence)
  - MH-29-08 (no edits under apps/backend/app/** or apps/admin-web/src/** beyond regression fixes with cited SHAs)
regressions-discovered:
  - REG-29-01: fixed_in_aea55f3 (Vite dev-proxy for admin-web http mode)
  - REG-29-02: deferred_to_v1.4 (revoke-own-current-session no redirect — UX minor)
  - REG-29-03: fixed_in_f3cd01f+bf9fa3a (telegram-bot worker missing Protocol slot registrations — PRODUCTION BLOCKER)
---

# Plan 29-03 — Execute DEBT-04 scenarios 1–6 — Summary

## Outcome

All 6 inherited DEBT-04 smoke scenarios from v1.2 `22-VERIFICATION.md`
`human_verification:` block executed against the live `apps/backend/docker-compose`
stack + `pnpm dev` admin-web on `VITE_API_MODE=http` + real Telegram sandbox bot.

**Score: 6/6 pass.**

## Scenario results

| # | Scenario | Result | Notes |
|---|----------|--------|-------|
| 1 | `/memberships` expiring filter (`within=7`) | ✓ pass | 3 expiring fixtures visible, freezable + cancelled hidden |
| 2 | `/clients` row-click navigation | ✓ pass | row body → detail page; Pencil/Trash `stopPropagation` confirmed |
| 3 | `/profile` sessions as owner | ✓ pass | A/B/C all work; minor REG-29-02 incidental finding (revoke-own-current no redirect) |
| 4 | `/profile` sessions as reception | ✓ pass | both-roles routing + sidebar RBAC verified |
| 5 | `/visits` FE-08(a..d) | ✓ pass (all 4 sub-tests) | (a) phone-prefix disambiguation; (b) already-checked-in HH:MM; (c) expires-today informational badge; (d) outside-hours disable + tooltip + alert |
| 6 | Telegram self-checkin (N>0 + last-day) | ✓ pass | Both verbatim DMs received after REG-29-03 production fix |

## Regressions discovered & disposition

### REG-29-01 — admin-web http mode login broken in dev (severity: blocker → fixed)
- **Cause:** Backend has no CORS middleware; Vite config had no proxy; cookies `SameSite=lax`.
- **Fix:** Added `server.proxy` in `apps/admin-web/vite.config.ts` (commit `aea55f3`) — same-origin under `:5173` so cookies survive.
- **Production impact:** None (Vite proxy only runs in `vite dev`; prod assumes nginx single-origin).

### REG-29-02 — revoke-own-current-session no redirect (severity: minor → deferred_to_v1.4)
- **Cause:** UI doesn't detect when the revoked session family IS the current one.
- **Disposition:** Backlog item for v1.4 polish. Does not violate v1.2 test text.

### REG-29-03 — telegram-bot worker missing Protocol slot registrations (severity: blocker → fixed) [PRODUCTION BUG]
- **Cause:** Bot worker process is separate from FastAPI's `create_app()`. Two Protocol slot resolvers (`register_client_by_telegram_resolver` and `register_active_membership_resolver`) were never registered in the worker, so `/checkin` always answered "У вас нет активного абонемента" regardless of DB state.
- **Fix:** Added both resolver registrations in `apps/backend/app/workers/telegram_bot.py:main()` (commits `f3cd01f` + `bf9fa3a` follow-up).
- **Significance:** Without DEBT-04 human-smoke verification, this bug would have shipped to prod silently. Validates the milestone-verification phase as load-bearing.

## Verification-fixture infrastructure (notes)

- Owner credentials: `owner@local.dev` / `OwnerDev!2026` (seeded via `seed_demo_data` + `SEED_OWNER_*` env vars).
- Reception credentials: `reception@local.dev` / `ReceptionDev!2026` (provisioned mid-verification via `INSERT INTO users` with backend-generated argon2 hash — no public user-create endpoint exists; v1.4 backlog candidate).
- Membership plan: 1 dev plan `Verify Standard 30d` (30 days, 14 freeze days) — required because `seed_verification_fixtures` needs a plan with `freeze_days_limit >= 7`. `seed_demo_data` does not seed plans automatically.
- Verification fixtures: 5 clients + 5 memberships seeded via `seed_verification_fixtures` (Plan 29-01 deliverable).
- Telegram sandbox bot: real token + sandbox chat id (operator-provided, redacted in this log).

## Stack lifecycle

- Boot: `cd apps/backend && docker compose up -d` (after `--no-cache` rebuild of all 4 service images — initial run hit a stale image gap where `0010_notifications.py` was missing from `backend-migrate` image).
- Seed: `uv run python -m scripts.seed_demo_data` + manual plan INSERT + `uv run python -m scripts.seed_verification_fixtures`.
- Admin-web: `cd apps/admin-web && VITE_API_MODE=http pnpm dev` (with `.env.development.local` setting `VITE_API_BASE_URL=` empty so Vite proxy fronts the API).
- Tear-down: deferred to Plan 29-06.

## Files modified by this plan

- `.planning/milestones/v1.3-VERIFICATION-LOG.md` (new — primary deliverable)
- `apps/admin-web/vite.config.ts` (REG-29-01 fix — single 6-line `server.proxy` block)
- `apps/backend/app/workers/telegram_bot.py` (REG-29-03 fix — three imports + two register_* calls in main())
- `apps/admin-web/.env.development.local` (new, gitignored — empties `VITE_API_BASE_URL` for proxy mode)

## What's next

Plan 29-04 — cross-phase smoke (freeze → renewal → expiring-cron). The bot is now confirmed working end-to-end, which is a prerequisite for the cron→DM half of that scenario. The arq-worker service is still failing (`uv` not in runtime image; separate issue — does not block 29-04 because Plan 29-02 provides `run_expiring_cron_once.py` to bypass ARQ).

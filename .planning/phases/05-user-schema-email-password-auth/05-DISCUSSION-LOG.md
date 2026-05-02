# Phase 5: User Schema + Email/Password Auth - Discussion Log

> **Audit trail only.** Do not use as input to planning, research, or execution agents.
> Decisions are captured in CONTEXT.md — this log preserves the alternatives considered.

**Date:** 2026-05-02
**Phase:** 05-user-schema-email-password-auth
**Areas discussed:** User + OtpCode schema in 0001_auth, Redis session mirror lifecycle

---

## Gray-area selection

| Option | Description | Selected |
|--------|-------------|----------|
| Refresh rotation race window | Mechanism for AUTH-06 ~5s reuse-window | (deferred to Claude) |
| Rate-limit storage + algorithm | Fixed vs sliding window; key shape | (deferred to Claude) |
| Redis session mirror lifecycle | Value shape, logout-all enumeration, authority | ✓ |
| User + OtpCode schema in 0001_auth | Final shape of users + refresh_tokens + otp_codes | ✓ |

**User's choice:** Discuss schema + Redis mirror; Claude decides race-window + rate-limit.

---

## User + OtpCode schema in 0001_auth

### Q1 — User.full_name shape

| Option | Description | Selected |
|--------|-------------|----------|
| Single `full_name` (text) | One column; operators are 1-2 people | ✓ |
| Triple `last_name`/`first_name`/`middle_name?` | Mirrors `clients` schema | |
| Both — store triple, expose `fullName` | Persist triple, derive on response | |

**User's choice:** Single `full_name` text column.
**Notes:** Operators are a different domain from clients (who use the ФИО triple per CLIENTS-01). Captured in CONTEXT.md D-01.

### Q2 — User.telegram_chat_id and User.password_hash nullability

| Option | Description | Selected |
|--------|-------------|----------|
| telegram_chat_id NULLABLE+UNIQUE, password_hash NOT NULL | P5 invariant: every user has a password; P7 binds via UPDATE; P7 ships its own migration if Telegram-only signup ever lands | ✓ |
| Both NULLABLE in 0001_auth | Future-proofs for P7 upsert with no follow-up migration; cost: P5 enforces password invariant in code | |
| Defer entire telegram support to Phase 7 migration | Smallest P5 surface; cost: extra migration in P7 | |

**User's choice:** telegram_chat_id NULLABLE+UNIQUE from day 1; password_hash NOT NULL.
**Notes:** Lets `/auth/me` derive `hasTelegram` immediately (AUTH-LO-04) and Phase 7 just runs `UPDATE users SET telegram_chat_id = ...`. Captured in CONTEXT.md D-02.

### Q3 — OtpCode shape in 0001_auth

| Option | Description | Selected |
|--------|-------------|----------|
| Full Phase 7 shape now | Final columns shipped now; P7 = app code only | ✓ |
| Minimal columns only | Placeholder; defer real schema to Phase 7 migration | |
| Lean columns — start, expire, consumed only | Compromise; may need ALTER TABLE later anyway | |

**User's choice:** Full Phase 7 shape now.
**Notes:** INFRA-03 already obliges creating `otp_codes` in 0001_auth — final shape avoids a follow-up migration. Captured in CONTEXT.md D-03.

### Q4 — RefreshToken `replaced_by_id` + user soft-delete

| Option | Description | Selected |
|--------|-------------|----------|
| RefreshToken with replaced_by_id self-FK + replaced_at; users no soft-delete | DB-led race-window mechanism enabled; users hard-deletable (FKs RESTRICT block accidents) | ✓ |
| RefreshToken without replaced_by_id; race-window via Redis cache | Smaller schema; race-window decision shifts to Redis | |
| Both: replaced_by_id AND user SoftDeleteMixin | Future-proof; cost: every user query goes through list_alive | |

**User's choice:** RefreshToken with replaced_by_id self-FK + replaced_at; users no soft-delete.
**Notes:** Enables D-13 race-window via DB chain (Redis cache becomes optimization, not source of truth). Captured in CONTEXT.md D-04, D-05.

---

## Redis session mirror lifecycle

### Q1 — Redis value shape

| Option | Description | Selected |
|--------|-------------|----------|
| JSON `{family_id, last_seen_at, refresh_token_hash}` | Fast-path 401 short-circuit when hash mismatches; debug breadcrumbs | ✓ |
| Marker only (`1` or empty) | Smallest footprint; Postgres authoritative | |
| JSON with ip / user_agent for v1.2 Active-Sessions | Sets up future UI; cost: P5 captures unused fields | |

**User's choice:** JSON `{family_id, last_seen_at, refresh_token_hash}`.
**Notes:** Captured in CONTEXT.md D-09.

### Q2 — logout-all enumeration mechanism

| Option | Description | Selected |
|--------|-------------|----------|
| Sibling SET `auth:user_sessions:{user_id}` of family_ids | SADD on login/refresh; SMEMBERS + pipeline DEL on logout-all; O(n) bounded | ✓ |
| Redis SCAN MATCH `auth:session:{user_id}:*` | No sibling SET to maintain; SCAN is the only place we'd use it | |
| Postgres-led: SELECT family_ids then DEL | DB source of truth; extra roundtrip on infrequent op | |

**User's choice:** Sibling SET.
**Notes:** Captured in CONTEXT.md D-10.

### Q3 — Authority on /auth/refresh

| Option | Description | Selected |
|--------|-------------|----------|
| Redis-first fast path, Postgres authoritative for state changes | Cheap reads, correct writes | ✓ |
| Postgres-only authoritative; Redis is mirror | Simplest invariants; every refresh hits DB | |
| Redis-only fast path + async Postgres write | Highest throughput; rejected (correctness) | |

**User's choice:** Redis-first fast path, Postgres authoritative.
**Notes:** Captured in CONTEXT.md D-11. Combined with `replaced_by_id` chain (D-13), this gives correct race-window handling even on Redis flush.

### Q4 — Redis client introduction

| Option | Description | Selected |
|--------|-------------|----------|
| `redis_lifespan` + `app.state.redis` + `get_redis` Depends | Mirrors db_lifespan; single pool; pinned redis>=5,<6 | ✓ |
| Inline `redis.asyncio.from_url(...)` per service module | Smaller surface; cost: pool fragmentation, muddy lifespan | |

**User's choice:** Lifespan-managed Redis client.
**Notes:** Captured in CONTEXT.md D-08.

---

## Claude's Discretion

The user explicitly delegated these to Claude. Decisions captured in CONTEXT.md:

- **D-07** — `User.role` stored as TEXT + CHECK constraint, not native PG enum.
- **D-12** — Refresh token stays opaque (no embedded family_id/user_id); lookup by `token_hash` first.
- **D-13** — Refresh rotation race-window mechanism: DB `replaced_by_id` chain + 5s Redis cache `auth:rotate:{old_token_hash}` for parallel-caller idempotent same-pair return.
- **D-14** — `/auth/logout` flow detail.
- **D-15** — `register_user_loader(load_user_by_id)` placement inside `create_app()`.
- **D-16** — API prefix flip to `/api/v1`; `/healthz` stays at root.
- **D-17** — `clear_session_cookies` helper sibling to `issue_session_cookies`.
- **D-18** — Fixed-window per-email rate limit via Redis INCR+EXPIRE 900.
- **D-19** — Per-email key, NOT per-IP.
- **D-20** — Audit emission as structlog events with stable `event=` names; DB row writer added in Phase 8.
- **D-21** — `audit.emit(...)` helper signature locked in P5; P8 swaps in DB INSERT without changing call sites.
- **D-22** — `db_session` fixture upgraded to SAVEPOINT-based per-test rollback (TEST-01).
- **D-25** — Seed script `scripts/seed_demo_data.py` mechanics (env-driven, idempotent, manual one-shot).
- **D-26** — Cookie behavior on each /auth/* endpoint enumeration.

## Deferred Ideas

See CONTEXT.md `<deferred>` section. Highlights:
- Active-sessions UI + per-session revoke (v1.2)
- Password reset via Telegram bot (v1.2)
- HIBP check on password change (v1.2)
- Per-IP rate limit, sliding-window upgrade (v1.2+)
- Native PG enum for `User.role` (v2+)
- Admin-only password-change endpoint (deferred admin endpoint; call site exists)

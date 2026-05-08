# Phase 20: Telegram bot `/checkin` self check-in - Discussion Log

> **Audit trail only.** Do not use as input to planning, research, or execution agents.
> Decisions are captured in CONTEXT.md — this log preserves the alternatives considered.

**Date:** 2026-05-08
**Phase:** 20-telegram-bot-checkin-self-check-in
**Areas discussed:** Redis update_id dedup placement, Outside-hours `{hours}` interpolation, ClientNotLinkedError → DM + audit

---

## Area Selection

| Option | Description | Selected |
|--------|-------------|----------|
| Redis update_id dedup placement | Where SET-NX-EX lives; atomicity; Redis-outage behavior | ✓ |
| ClientNotLinkedError → DM + audit | Which Russian DM; new `telegram_unknown_checkin` event | ✓ |
| Outside-hours `{hours}` interpolation | Source for `{hours}`; format/dash style | ✓ |
| Replay-dedup behavior + audit event | Silent vs DM; new event vs reuse `telegram_replay_attempt` | (covered transitively under Area 1) |

---

## Area 1 — Redis update_id dedup placement

### Q1.1: Where should the SET-NX-EX dedup check live?

| Option | Description | Selected |
|--------|-------------|----------|
| Inside `checkin_handler` only | First lines of handler; `start_handler` unchanged; smallest blast radius | ✓ |
| Global ptb pre-handler middleware | Wraps every update including `/start`; broader audit-emit surface | |
| `dedup_then(handler)` decorator at registration | Composable wrapper; testable in isolation; v1.2-additive helper | |

**User's choice:** Inside `checkin_handler` only.
**Notes:** Captured as D-20-1. Future Phase 21+ handlers needing dedup will copy the 6-line pattern; refactor to a decorator if a third command joins.

### Q1.2a: How should `checkin_handler` get the Redis client?

| Option | Description | Selected |
|--------|-------------|----------|
| Add `redis: Redis` to `HandlerContext` | Mirror of `session_factory` pattern; preserves "everything via ctx" invariant | ✓ |
| Import `get_redis_client` helper in handlers.py | Avoids growing NamedTuple; second Redis lifecycle | |
| Pass via ptb `context.bot_data['redis']` | Uses ptb shared-state idiom; HandlerContext stays unchanged | |

**User's choice:** Add `redis: Redis` to HandlerContext.
**Notes:** Captured as D-20-2. Worker passes the existing `_redis` from `redis_lifespan_manager()`.

### Q1.2b: Behavior on Redis outage (e.g. `ConnectionError` from SET)?

| Option | Description | Selected |
|--------|-------------|----------|
| Fail-open + structlog WARN | Proceed to service call; DB UNIQUE is real anti-replay invariant | ✓ |
| Fail-closed silent | No DM, no DB call; bot silently breaks during Redis outage | |
| Fail-closed with generic 5th DM string | DM "Сервис временно недоступен..."; expands locked-string set | |

**User's choice:** Fail-open + structlog warning.
**Notes:** Captured as D-20-3. NO 5th locked DM string for outages.

### Q1.3: When dedup HIT (replay): silent or audit + DM?

| Option | Description | Selected |
|--------|-------------|----------|
| Silent (structlog DEBUG only) | No DM, no audit, no session opened; mirrors `start_handler` silent-drop branches | ✓ |
| Audit-emit `bot_replay_attempt` (new pair) | Adds `("bot_replay_attempt", "visit")` to LOCKED_AUDIT_EVENTS | |
| Reuse `telegram_replay_attempt` (resource=otp) | Cross-purpose; pollutes Phase 7 OTP audit stream | |

**User's choice:** Silent (structlog DEBUG only).
**Notes:** Captured as D-20-4. NO new frozenset entry for replays; replays are an internal worker-restart concern, not user-visible.

---

## Area 2 — Outside-hours `{hours}` interpolation

### Q2.1: Source for `{hours}` in the locked outside-hours DM string?

| Option | Description | Selected |
|--------|-------------|----------|
| Read from `OutsideGymHoursError.fields` | Phase 19 already populates `{'open': …, 'close': …}`; handler ignorant of Settings | ✓ |
| Import `Settings` in handler | `integrations→core` allowed; but two paths read same env var (drift risk) | |
| Pass via HandlerContext (`gym_hours: tuple[time, time]`) | Cleanest DI but expands HandlerContext for one use | |

**User's choice:** Read from `OutsideGymHoursError.fields`.
**Notes:** Captured as D-20-8. The Phase 19 fields contract (`'open'`/`'close'` as `time.isoformat()` strings) is now load-bearing; pinned by unit + integration tests.

### Q2.2: Dash style for the `'07:00–23:00'` formatted range?

| Option | Description | Selected |
|--------|-------------|----------|
| En-dash `–` (U+2013) | Russian typography convention for ranges | ✓ |
| Em-dash `—` with surrounding spaces | Heavier; some Russian style guides | |
| ASCII hyphen `-` | Simplest; less typographically Russian | |

**User's choice:** En-dash `–` → `'07:00–23:00'`.
**Notes:** Captured in D-20-8. Helper `_format_gym_hours(exc)` strips the trailing `:SS` from `time.isoformat()` output (Phase 19 emits `'07:00:00'`) — planner picks slice `[:5]` or `time.fromisoformat(...).strftime("%H:%M")`.

---

## Area 3 — ClientNotLinkedError handling

### Q3.1: Which DM goes out for `ClientNotLinkedError`?

| Option | Description | Selected |
|--------|-------------|----------|
| Reuse `_DM_NO_MEMBERSHIP` (anti-oracle) | Strangers + linked-but-no-membership clients see SAME response; defeats account enumeration | ✓ |
| Add 5th locked string `_DM_NOT_LINKED` | Honest UX ("Этот Telegram не привязан…") at cost of oracle leak per Pitfall 8 | |
| Silent (structlog + audit only) | Strongest anti-oracle; no UX feedback at all | |

**User's choice:** Reuse no-membership string (anti-oracle).
**Notes:** Captured as D-20-9. AUTH-TG-11's 4-string lock holds; no expansion.

### Q3.2: Audit event for ClientNotLinkedError on the bot path?

| Option | Description | Selected |
|--------|-------------|----------|
| Add `telegram_unknown_checkin` to LOCKED_AUDIT_EVENTS | New pair `("telegram_unknown_checkin", "visit")`; payload `{chat_id, telegram_user_id_hash}` | ✓ |
| Skip audit, structlog only | Saves frozenset entry + DB write; loses cross-correlation with `visit_*` events | |
| Reuse `telegram_unknown_start` (resource=otp) | Cross-purpose pollution rejected | |

**User's choice:** Add `telegram_unknown_checkin` to LOCKED_AUDIT_EVENTS.
**Notes:** Captured as D-20-10. Telegram_user_id is sha256-hashed in payload (PII minimization, mirror Phase 7 `_hash_token_for_log`). Resource_type=`'visit'` (NOT `'otp'`) so ops can filter the full visits anti-fraud picture in one query.

---

## Claude's Discretion

- **CD-01 — 3-plan layout** (handler+audit / worker / tests). Mirrors small-surface phases like Phase 18.
- **CD-02 — No BLOCKING-after-migration flag** (Phase 20 has no DB migration).
- **Helper names** — `_hash_telegram_user_id`, `_format_gym_hours` (private to `handlers.py`).
- **Test directory** — `tests/integration/telegram_bot/` + `tests/unit/telegram_bot/` (NEW; mirrors Phase 19's `tests/integration/visits/`).
- **Defensive `KeyError` raise from `_format_gym_hours`** (RuntimeError "Phase 19 regression") — tighter than a malformed DM.

## Deferred Ideas

- Per-chat-id rate limit (`sz:bot:rate:` token bucket, N=5/hour) — Pitfall 8 mitigation, v1.3+
- Webhook-based bot mode — PROJECT.md "Auth UX" deferred
- DM on Redis outage (5th locked string) — rejected per D-20-3
- Bot replay audit event (`bot_replay_attempt`) — rejected per D-20-4
- Additional bot commands (`/status`, `/help`) — re-introduce oracle leaks
- `dedup_then(handler)` decorator — YAGNI for v1.2 single bot command
- `_DM_*` i18n for non-Russian zals — out of scope (Russian-only product)
- Photo turnstile / NFC / geofence — v2+ per "accepted residual fraud risk"
- Pre-formatted hours field on `OutsideGymHoursError` — presentation belongs in handler

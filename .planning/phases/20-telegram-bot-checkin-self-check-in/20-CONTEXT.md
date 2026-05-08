# Phase 20: Telegram bot `/checkin` self check-in - Context

**Gathered:** 2026-05-08
**Status:** Ready for planning

<domain>
## Phase Boundary

Phase 20 ships the **Telegram bot `/checkin` self check-in handler** — the bot-facing call site for Phase 19's `create_visit_self_checkin` consumer. Until this phase, `/checkin` is undefined: the existing `app/integrations/telegram/handlers.py` only has `start_handler` (Phase 7 OTP deep-link). After this phase, a client can DM `/checkin` to the gym bot, the bot worker dedups the `update_id` against Redis, the handler calls `ctx.visits_service.create_visit_self_checkin(...)`, and the user gets exactly one of the four locked Russian DM strings — without leaking account-existence, membership-status, or end-date as oracle data (Pitfall 8).

In scope:
- **MODIFY** `app/integrations/telegram/handlers.py`:
  - Extend `HandlerContext` NamedTuple with TWO new fields: `visits_service: ModuleType` (D-10, parallel to `telegram_service` D-06) and `redis: Redis` (D-20-1; new — every handler dependency arrives via ctx, never via app.state). Existing `start_handler` keeps its current signature; the extra fields are unused there.
  - Add 4 module-level constants holding the LOCKED Russian DM strings (verbatim from REQUIREMENTS AUTH-TG-11):
    - `_DM_CHECKIN_OK = "✅ Отмечено"` (no interpolation, no oracle leak per D-20-7)
    - `_DM_NO_MEMBERSHIP = "У вас нет активного абонемента. Обратитесь к администратору."` (also used for `ClientNotLinkedError` per D-20-9 anti-oracle)
    - `_DM_DUPLICATE = "Вы уже отмечались сегодня."`
    - `_DM_OUTSIDE_HOURS = "Зал сейчас закрыт. Часы работы: {hours}."` (`{hours}` is the only runtime interpolation; format `'07:00–23:00'` with U+2013 EN DASH per D-20-8)
  - Add `_hash_telegram_user_id(tg_user_id: int) -> str` helper (sha256 hex, mirror of Phase 7 `_hash_token_for_log`) — used in audit + structlog payloads to keep raw telegram_user_id out of the audit_log table.
  - Add `async def checkin_handler(update, context, ctx: HandlerContext) -> None`:
    1. Extract `update.update_id`, `update.effective_user.id` (telegram_user_id), `update.effective_chat.id` (chat_id). Defensive return if any is None.
    2. **Redis dedup (in-handler, fail-open):** call `ctx.redis.set(f"sz:bot:update:{update_id}", "1", nx=True, ex=3600)`. Wrap in `try/except` → on Redis error log structlog WARN `bot_redis_dedup_unavailable` with `update_id`+`chat_id` and PROCEED to the service call (DB UNIQUE on (client_id, gym_date) is the real anti-replay invariant per Pitfall 5). On result `None` (key already existed → replay): log structlog DEBUG `bot_replay_skipped` with `update_id`+`chat_id` and `return` silently — no DM, no audit row, no DB session opened (D-20-3).
    3. Open `async with ctx.session_factory() as session:` (mirrors `start_handler`).
    4. `try: visit = await ctx.visits_service.create_visit_self_checkin(session, telegram_user_id=tg_user_id, chat_id=chat_id)` — service owns its own `await session.commit()` on success (Phase 19 D-05 + INFRA-13 commit gate); the handler MUST NOT call `session.commit()` after the service returns.
    5. On success → `await ctx.sender.send_text_dm(bot, chat_id, _DM_CHECKIN_OK)`. Ignore the `SendResult` (mirror Phase 7 `start_handler` DM-blocked semantics: a blocked-DM doesn't roll back the visit; the visit stands; structlog WARN if the send fails).
    6. On exception, dispatch by `type(exc).__name__` string-match (NOT `isinstance` — `integrations ⊥ modules` forbids importing the exception classes from `app.modules.visits`; mirror Phase 7 D-04/D-20 string-name dispatch in `start_handler`):
       - `"NoActiveMembershipError"` → DM `_DM_NO_MEMBERSHIP`. Service already audit-emitted `visit_rejected_no_membership` + committed (Phase 19 D-05). Handler emits NO additional audit. Return.
       - `"DuplicateCheckinError"` → DM `_DM_DUPLICATE`. Service already audit-emitted `visit_rejected_duplicate`. Return.
       - `"OutsideGymHoursError"` → format `_DM_OUTSIDE_HOURS.format(hours=_format_gym_hours(exc))`. The helper reads `exc.fields['open']` and `exc.fields['close']` (Phase 19 raises with these populated — `service.py:99-100, 142`), strips the `:SS` tail (Phase 19 uses `time.isoformat()` which yields `'07:00:00'`; we slice `[:5]` or strftime via `time.fromisoformat(...).strftime("%H:%M")`), joins with U+2013. Service already audit-emitted. Return.
       - `"ClientNotLinkedError"` → **handler owns the audit emit** (Phase 19 D-12 explicitly defers): open the session if not already open, call `audit.emit(session, "telegram_unknown_checkin", actor_user_id=None, resource_type="visit", resource_id=None, chat_id=chat_id, telegram_user_id_hash=_hash_telegram_user_id(tg_user_id))` → `await session.commit()` → DM `_DM_NO_MEMBERSHIP` (anti-oracle reuse per D-20-9). Return.
       - Any other exception → re-raise; ptb's `_global_error_handler` (`app/integrations/telegram/bot.py:32`) logs and the polling loop continues (resilience guarantee).
- **MODIFY** `app/workers/telegram_bot.py`:
  - Add `from app.modules.visits import service as visits_service` (D-10 relaxation — parallel to the existing `from app.modules.auth import telegram_service` D-06 line at `telegram_bot.py:29`). Document in the module docstring that "workers MAY import a single owning module's service layer" now applies to BOTH `auth.telegram_service` (D-06) and `visits.service` (D-10).
  - Construct `HandlerContext(session_factory=sessionmaker, telegram_service=telegram_service, visits_service=visits_service, sender=telegram_sender, redis=_redis)` — pass the existing `_redis` from `redis_lifespan_manager()` (already entered at `telegram_bot.py:56`; rename `_redis` → `redis` to make it non-private since it's now used).
  - Extend the handlers list: `handlers=[("start", start_handler), ("checkin", checkin_handler)]`.
- **MODIFY** `app/core/audit.py`:
  - Add `("telegram_unknown_checkin", "visit")` to `LOCKED_AUDIT_EVENTS` frozenset (line 74-117). Update the docstring inventory (around line 26-32) with a `## v1.2 (Phase 20 — bot self check-in unknown-tg)` block.
  - The other four `visit_*` events are already locked (Phase 15 INFRA-11) and emitted by Phase 19's service.
- **MODIFY** `apps/backend/.importlinter`:
  - The new `app.workers.telegram_bot → app.modules.visits.service` edge is a documented exception parallel to the existing `app.workers.telegram_bot → app.modules.auth.telegram_service` exception. Confirm the contract syntax in `.importlinter` allows a second exception or whether the `workers ⊥ modules` rule is already framed as "workers may import a single owning module" with both modules whitelisted. If the contract needs a second `ignore_imports:` line, add it; else the rule is shape-relaxed already. Planner verifies.
  - The `app.integrations.telegram.handlers → app.modules.visits.service` edge does NOT exist (handler reaches visits via `ctx.visits_service`, never imports the module). Contract `integrations ⊥ modules` stays clean.
- Tests:
  - **NEW** `tests/integration/telegram_bot/test_checkin_handler.py` — direct call to `checkin_handler(update, context, ctx)` with stubbed `update`/`context` (NamespaceSimple-style mocks; mirror existing Phase 7 `test_start_handler.py` if present). Uses real Postgres (db_session fixture or db_session_real_commit), real `audit.emit` (so the audit_log row is observable), stubbed `ctx.sender` (TEST-03 pattern — assert `send_text_dm` called with the expected DM string), real `fakeredis.aioredis.FakeRedis` for `ctx.redis` (so SET-NX-EX semantics are exercised). Cases:
    - happy path → 201-equivalent (visit row + `visit_created` audit + `_DM_CHECKIN_OK` sent)
    - `NoActiveMembershipError` → `_DM_NO_MEMBERSHIP` + `visit_rejected_no_membership` audit
    - `DuplicateCheckinError` → `_DM_DUPLICATE` + `visit_rejected_duplicate` audit
    - `OutsideGymHoursError` → `_DM_OUTSIDE_HOURS` formatted with the configured hours (en-dash) + `visit_rejected_outside_hours` audit
    - `ClientNotLinkedError` → `_DM_NO_MEMBERSHIP` (anti-oracle) + `telegram_unknown_checkin` audit row (handler-emitted; Phase 19 service does NOT audit)
    - **replay path** — call the handler twice with the same `update_id`; second call: no DM, no second visit row, structlog DEBUG `bot_replay_skipped`
    - **Redis-outage path** — monkeypatch `ctx.redis.set` to raise `redis.ConnectionError`; assert handler still proceeds, structlog WARN, visit row created (fail-open per D-20-2)
  - **NEW** `tests/integration/telegram_bot/test_handler_context_shape.py` — assert `HandlerContext._fields` includes `visits_service` and `redis` (regression guard against accidental field removal; cheap two-liner).
  - **NEW** `tests/integration/telegram_bot/test_worker_handlers_registered.py` — call `build_application(...)` with a stub ctx and assert the resulting `Application` has BOTH `("start", ...)` and `("checkin", ...)` `CommandHandler`s registered (introspection over `application.handlers`). Catches the "forgot to register checkin in the worker" regression.
  - **NEW** `tests/unit/telegram_bot/test_format_gym_hours.py` — `_format_gym_hours(exc)` helper boundary cases: `'07:00:00'/'23:00:00'` → `'07:00–23:00'`; `'07:30:00'/'22:45:00'` → `'07:30–22:45'`; missing fields raises (defensive — Phase 19 always populates).
  - **NEW** `tests/unit/telegram_bot/test_hash_telegram_user_id.py` — sha256 stable + non-truncating; same input → same output; different inputs → different outputs.
  - **EXTEND** `tests/unit/test_audit_taxonomy.py` (Phase 15 AST walker) — already passes verbatim because `("telegram_unknown_checkin", "visit")` is added to the frozenset. The walker just verifies callsite/frozenset parity.
- **MODIFY** `apps/backend/openapi.json` — NO changes (Phase 20 has no HTTP surface — it's a bot worker addition only). Phase 21 owns the FE-side codegen for the Phase 19 `/visits` endpoints.
- **MODIFY** `apps/backend/docker-compose.yml` — NO changes. Phase 20 piggy-backs on the existing `telegram-bot` service (Phase 7); the worker process now registers two handlers instead of one.
- **MODIFY** PROJECT.md `## Key Decisions` table — add D-20 (this phase): "Telegram `/checkin` handler dedups via Redis `sz:bot:update:{update_id}` (TTL 1h, fail-open); ClientNotLinkedError reuses no-membership DM (anti-oracle); 4 locked Russian strings per AUTH-TG-11." Mirror of Phase 18/19 entries. Captured as a planner action item, not a separate plan.

Out of scope (locked to later phases):
- **Phase 21** OpenAPI drift gate refresh + `packages/api-client` codegen for visits/memberships/plans. Phase 20 has no HTTP surface (bot worker only); openapi.json is unaffected.
- **Phase 22** admin-web `features/visits` UI, including the "Кто сейчас в зале" card (D-1) and per-user "сегодняшние посещения" log (D-6). Phase 20 has zero FE concerns.
- **Per-chat-id rate limit** ("N=5 attempts per hour per chat_id at the bot layer", PITFALLS Pitfall 8 mitigation #3). Single-zal scope; the gym-hours window + DB UNIQUE invariants already cover the abuse modes Phase 20 cares about. Defer to v1.3+.
- **Webhook-based bot mode** (PROJECT.md "Auth UX" deferred list). Phase 20 stays on long-polling.
- **Bot-level commands beyond `/start` and `/checkin`** (e.g., `/status`, `/help`). Out of scope; future phases only.
- **DM on Redis outage** (a 5th locked string `"Сервис временно недоступен..."`). Rejected per D-20-2 fail-open: outage is a wider operational concern, the visit still succeeds via DB UNIQUE invariant, no DM expansion needed.
- **Bot replay audit event** (`bot_replay_attempt` resource=visit). Rejected per D-20-3 silent-on-replay: replays are an internal worker-restart concern, not user-visible; structlog DEBUG is sufficient. No frozenset extension.
- **Reusing `telegram_replay_attempt` (resource=otp) for bot-checkin replays.** Rejected per D-20-3: cross-purpose reuse pollutes the OTP audit stream.
- **Extending `OutsideGymHoursError.fields` to include a pre-formatted `'07:00–23:00'` string.** Rejected per D-20-8: handler owns the format; service stays format-agnostic and continues to emit `time.isoformat()` for backend consumers (audit_log payload, openapi error schema). Format is presentation, not data.
- **Adding gym hours to `HandlerContext`.** Rejected per D-20-8: hours are exception-data, not a separate handler dependency. Single source of truth (`Settings`) flows: `Settings → service.py:_assert_within_gym_hours → OutsideGymHoursError.fields → handler.format`.
- **Photo turnstile / NFC / geofence** — explicitly v2+ per Pitfall 9 / PROJECT.md "accepted residual fraud risk".

</domain>

<decisions>
## Implementation Decisions

### Redis update_id dedup

- **D-20-1: Dedup lives inside `checkin_handler` only — NOT a global ptb pre-handler middleware, NOT a `dedup_then(...)` decorator.** First lines of the handler before the session is opened. `start_handler` keeps its current behavior unchanged (its replay defense is `OtpAlreadyConsumed` at the service layer; Redis dedup would be redundant for OTP). Smallest blast radius, no Phase 7 regression risk, no `bot.py` factory churn. The trade-off (no central middleware to inherit if a Phase 21+ handler is added) is accepted: future handlers that need dedup copy the 6-line pattern.
- **D-20-2: Redis client arrives via `HandlerContext.redis` (NamedTuple extension) — NOT via `app.state.redis` lookup, NOT via ptb `context.bot_data['redis']`.** Mirror of the existing `session_factory` pattern (`handlers.py:35`). Keeps the Phase 7 invariant that "handlers receive everything via ctx; integrations layer never reaches into app.state". The worker already enters `redis_lifespan_manager()` (`telegram_bot.py:56`) — pass the same client into the NamedTuple.
- **D-20-3: On Redis outage (`ConnectionError`/`TimeoutError`/etc. from `set(...)`), fail-OPEN — proceed to call the visits service.** Reasoning: the DB UNIQUE on `(client_id, gym_date)` is the real anti-replay invariant (Pitfall 5); Redis dedup is a polite optimization to avoid the wasted Postgres roundtrip + audit churn. structlog WARN `bot_redis_dedup_unavailable` for ops visibility. Single-zal scope: a Redis outage is a wider operational issue; making bot check-ins silently fail (vs. reception manual check-ins which still work via the HTTP path) is worse than accepting one duplicate-attempt's worth of DB work. NO 5th locked DM string for outages.
- **D-20-4: On dedup HIT (key already existed), behavior is silent — structlog DEBUG only, no DM, no audit row, no DB session opened.** Mirror of `start_handler`'s silent `TokenUnknown/OtpExpired` branch. Replays are an internal worker-restart concern, not user-visible; the legitimate user already saw their first DM. NO new `bot_replay_attempt` audit event added to LOCKED_AUDIT_EVENTS. NO reuse of `telegram_replay_attempt` (resource=otp) — cross-purpose pollution rejected.
- **D-20-5: Dedup atomicity is `SET key value NX EX 3600`** (single redis-py call, server-side atomic). NOT `GET → SET` (race window) and NOT `SET + EXPIRE` (two roundtrips, partial-failure window). The `nx=True, ex=3600` kwargs to `redis.asyncio.Redis.set()` are the standard async-redis idiom.
- **D-20-6: Keyspace `sz:bot:update:{update_id}` TTL 3600s (1h)** — verbatim per AUTH-TG-10. Coexists with `arq:*` and `sz:session:*` (Phase 7 D-08 + Phase 18); namespace prefix `sz:bot:update:` is reserved for this dedup; `sz:bot:replay:*` from PITFALLS Pitfall 9 is renamed to `sz:bot:update:` to match REQUIREMENTS wording.

### DM copy + interpolation

- **D-20-7: 4 locked Russian DM strings, code constants, NO i18n.** Verbatim from REQUIREMENTS AUTH-TG-11. NO `{gym_name}`/`{time_msk}` interpolation on success (research ARCHITECTURE.md line 218 had `"✅ Отмечено в {gym_name} в {time_msk}."` — that was research-spec drift; REQUIREMENTS is the lock and it says `"✅ Отмечено"` only). Single-language by design (Russian-only product; PROJECT.md L133). The strings live as module-level constants in `handlers.py` (mirror Phase 7 `_DM_STRANGER`/`_DM_REPLAY` at `handlers.py:50-54`). Owner sign-off on the copy is REQUIREMENTS AUTH-TG-11 acceptance criteria — the planner gates merge on the sign-off (see ROADMAP SC#3: "signed off by the project owner before merge").
- **D-20-8: `{hours}` for the outside-hours DM is sourced from `OutsideGymHoursError.fields['open']`/`['close']` — NOT from `Settings` directly, NOT via HandlerContext.** Phase 19 service already populates `fields={'open': settings.gym_hours_start.isoformat(), 'close': settings.gym_hours_end.isoformat()}` (`visits/service.py:99-100, 142`). The handler reads them, strips the trailing `':SS'` (Phase 19 uses `time.isoformat()` → `'07:00:00'`, NOT `'07:00'`; the planner picks slice `[:5]` or `time.fromisoformat(...).strftime("%H:%M")` — both correct), joins with U+2013 EN DASH. Format example: `'07:00–23:00'`. The dash is `–` (Russian typographic convention for ranges) NOT `—` em-dash and NOT ASCII `-`.
  - The contract that Phase 19 must keep populating those fields is now load-bearing for Phase 20 — locked here as a cross-phase invariant; the unit test `test_format_gym_hours.py` and the integration test `test_checkin_handler.py::test_outside_hours_dm` together pin it.
  - Helper name: `_format_gym_hours(exc) -> str` (private to `handlers.py`; takes the exception, returns the formatted range). Defensive `KeyError` raises a `RuntimeError` ("OutsideGymHoursError fields contract broken — Phase 19 regression") rather than fall through to a malformed DM.

### ClientNotLinkedError handling (anti-oracle)

- **D-20-9: `ClientNotLinkedError` → DM the existing `_DM_NO_MEMBERSHIP` string ("У вас нет активного абонемента. Обратитесь к администратору.").** Pitfall 8 anti-oracle mitigation: a stranger sending `/checkin` from a stolen device or an unbound chat-id receives the EXACT SAME response as a legitimately-linked client whose membership has expired. The bot becomes useless for account enumeration. Trade-off (legitimately not-yet-linked users get a slightly misleading message): acceptable; the admin-web onboarding flow + reception staff handle linking. NO new 5th locked string; AUTH-TG-11's 4-string lock holds.
- **D-20-10: New audit event pair `("telegram_unknown_checkin", "visit")` added to `LOCKED_AUDIT_EVENTS`.** Phase 19 D-12 explicitly deferred this. Payload: `{chat_id, telegram_user_id_hash}` — the raw `telegram_user_id` is sha256-hashed (mirror Phase 7 `_hash_token_for_log` at `handlers.py:74`) so the audit_log table never stores the raw Telegram identifier (PII minimization). `actor_user_id=None`, `resource_id=None`, `resource_type='visit'`. The handler owns the emit (NOT the service — Phase 19 service raises the exception cleanly without audit per D-12). The handler opens the session, emits, commits, then DMs.
  - Naming rationale: `telegram_unknown_checkin` parallel to `telegram_unknown_start` (Phase 7) — same prefix verb pattern. `resource_type='visit'` (NOT `'otp'` like Phase 7's pair) because the event semantically belongs to the visits surface; ops querying `audit_log WHERE resource_type='visit'` should see the full visits anti-fraud picture in one filter.
  - The Phase 15 AST taxonomy walker (`tests/unit/test_audit_taxonomy.py`) catches typos at the new callsite verbatim — no walker extension needed.

### Plan layout (Claude's discretion — finalise at `/gsd-plan-phase`)

- **CD-01 (default to apply):** **3 plans, mirroring the small-surface phases (e.g., Phase 18).**
  - `20-01-PLAN.md` — `app/integrations/telegram/handlers.py` extensions: HandlerContext NamedTuple growth (visits_service + redis fields), 4 locked Russian DM constants, `_hash_telegram_user_id` + `_format_gym_hours` helpers, `checkin_handler` body with the dedup→service-call→exception-dispatch shape. Plus `app/core/audit.py` frozenset extension (1 line + docstring update). (AUTH-TG-07, AUTH-TG-08, AUTH-TG-11 + audit taxonomy)
  - `20-02-PLAN.md` — `app/workers/telegram_bot.py` wiring: D-10 import line, HandlerContext construction with the new fields, handler list extension, `.importlinter` exception verification. (AUTH-TG-09, AUTH-TG-10)
  - `20-03-PLAN.md` — Tests (unit + integration): handler 7 cases + worker registration + HandlerContext shape regression + format_gym_hours boundaries + hash_telegram_user_id stability + audit taxonomy auto-pass. PROJECT.md Key Decisions D-20 row + REQUIREMENTS.md AUTH-TG-* check-off. Owner sign-off gate captured as a `[ ] Owner sign-off on locked Russian DM strings (AUTH-TG-11)` checkbox in the plan acceptance criteria — merge blocked until ticked.
- **CD-02 (default to apply):** **No BLOCKING-after-migration flag** (Phase 20 has no DB migration). Plans 20-01/20-02/20-03 are linearly orderable; 20-03 depends on 20-01+20-02 source code existing.

### Defaults if user says nothing at plan-phase review

All `D-20-*` decisions above are LOCKED by user answer in this discussion. `CD-*` are Claude's discretion at plan-phase. User overrides at plan-phase review by saying e.g. "actually, put dedup in a `dedup_then(...)` decorator (revert D-20-1)" — the planner reflects the change in `20-NN-PLAN.md` before execution.

### Locked-not-discussed (carried verbatim from REQUIREMENTS / Phase 15 / ROADMAP / Phase 19 / research)

- **`HandlerContext.visits_service: ModuleType` and the D-10 docstring** are AUTH-TG-07 verbatim; the parallel-to-D-06 framing is locked.
- **Worker registers `("checkin", checkin_handler)` alongside `("start", start_handler)`** — AUTH-TG-09 verbatim. Order is `[start, checkin]` for diff-stability; ptb's `Application.add_handler` is order-independent for `CommandHandler` so the cosmetic order doesn't affect routing.
- **`integrations ⊥ modules` import-linter contract is unchanged.** The handler reaches `visits_service` only via `ctx.visits_service.*` (NamedTuple field), never via direct import. The new `workers → modules.visits.service` edge is the documented D-10 exception, parallel to the existing D-06 `workers → modules.auth.telegram_service` edge.
- **`audit.emit` co-transactional contract** (Phase 5/15) — handler-side `telegram_unknown_checkin` emit follows the same shape as service-side emits: same session, no flush/commit inside `emit()`, the handler explicitly commits after the emit.
- **`_DM_*` strings are code constants (NOT a JSON i18n file, NOT a database table).** REQUIREMENTS AUTH-TG-11 explicit: "constants in code, not freeform i18n". Any future locale (post-v1.x) introduces an i18n framework — out of scope.
- **`channel='telegram_bot'` is what the visit row carries** — Phase 19 `create_visit_self_checkin` hardcodes this; Phase 20 has zero say in the channel value. The audit row's `channel` payload field carries the same value (Phase 19 D-16).
- **No new dependencies** — `redis.asyncio.Redis` is already pinned (Phase 5/7); `hashlib` is stdlib (Phase 7 already uses it via `_hash_token_for_log`); no python-telegram-bot version bump.
- **Container `TZ=UTC`** (Phase 15 lock) — Phase 20 doesn't compute MSK locally. The gym-hours boundary is computed in Phase 19's service (`ZoneInfo("Europe/Moscow")` at `service.py:118-126`); Phase 20 only RECEIVES the formatted hours via the exception fields.
- **CSRF / RBAC** — N/A. Phase 20 is bot-side; no HTTP request, no `require_permission`/`verify_csrf` Depends. The visits service Phase 19 D-04 splits public reception (HTTP/RBAC/CSRF) from public bot (no RBAC); Phase 20 stays on the bot half.
- **No new audit events beyond `telegram_unknown_checkin`** — the four `visit_*` events are Phase 15-locked and Phase 19-emitted; Phase 20 piggy-backs.

</decisions>

<canonical_refs>
## Canonical References

**Downstream agents MUST read these before planning or implementing.**

### Project context (read first)
- `.planning/PROJECT.md` — РФ/СНГ + Telegram-first; D-06 `workers/telegram_bot → modules.auth.telegram_service` (v1.1) and the upcoming D-10 `workers/telegram_bot → modules.visits.service` (v1.2 Phase 20). Russian-only product; locked DM copy + accepted residual friend-fraud risk Key Decisions.
- `.planning/REQUIREMENTS.md` — AUTH-TG-07..11 (Phase 20 ownership). AUTH-TG-11 lists the 4 locked Russian strings verbatim — the planner copies them as code constants without paraphrase.
- `.planning/ROADMAP.md` §"Phase 20: Telegram bot `/checkin` self check-in" — phase goal + Success Criteria 1-5 + dependency note ("Depends on: Phase 19").
- `.planning/STATE.md` §"Decisions" — accumulated v1.2 decisions; Phase 20's D-20-* will be appended on phase verification.

### Phase 19 outputs (direct precursor — service consumer)
- `.planning/phases/19-visits-db-reception-check-in-backend/19-CONTEXT.md` — D-04 reception+bot share private chain; D-05 reject paths emit+commit+raise; D-12 `ClientNotLinkedError` raised WITHOUT audit, Phase 20 owns the emit; D-16 audit payload schemas. Phase 20 is the consumer Phase 19 was designed to enable.
- `.planning/phases/19-visits-db-reception-check-in-backend/19-VERIFICATION.md` — confirms `create_visit_self_checkin(session, telegram_user_id, chat_id)` shipped + `ClientNotLinkedError` exception + 4 locked `visit_*` audit events emitted by service.
- `apps/backend/app/modules/visits/service.py:227-252` — `create_visit_self_checkin` public API. Phase 20 calls this verbatim via `ctx.visits_service.create_visit_self_checkin(...)`.
- `apps/backend/app/modules/visits/service.py:96-100, 138-145` — `_assert_within_gym_hours` raises `OutsideGymHoursError(fields={'open': settings.gym_hours_start.isoformat(), 'close': settings.gym_hours_end.isoformat()})`. The fields contract Phase 20 D-20-8 depends on.
- `apps/backend/app/core/exceptions.py:81-163` (extended in Phase 19) — `NoActiveMembershipError`/`DuplicateCheckinError`/`OutsideGymHoursError`/`ClientNotLinkedError` exception class names; Phase 20 dispatches by `type(exc).__name__` string-match (NOT isinstance — `integrations ⊥ modules` forbids the import).

### Phase 7 outputs (telegram bot foundation)
- `apps/backend/app/integrations/telegram/handlers.py:35-46` — `HandlerContext` NamedTuple shape; Phase 20 extends with `visits_service` + `redis` fields without breaking existing `start_handler` consumers.
- `apps/backend/app/integrations/telegram/handlers.py:50-54` — `_DM_STRANGER` / `_DM_REPLAY` constants pattern; Phase 20 mirrors with 4 new constants.
- `apps/backend/app/integrations/telegram/handlers.py:68-74` — `_hash_token_for_log` (sha256 hex); Phase 20 mirrors with `_hash_telegram_user_id`.
- `apps/backend/app/integrations/telegram/handlers.py:106-178` — `start_handler` body shape; Phase 20's `checkin_handler` mirrors the (open session → call service → exception-name dispatch → DM via sender) skeleton.
- `apps/backend/app/integrations/telegram/handlers.py:127-131` — string-name exception dispatch precedent (Phase 7 D-04/D-20: catches `cls_name == "OtpAlreadyConsumed"` etc. WITHOUT importing the class). Phase 20 reuses this pattern verbatim.
- `apps/backend/app/integrations/telegram/bot.py:43-82` — `build_application` factory + `_global_error_handler` resilience guarantee. Phase 20 doesn't modify this file.
- `apps/backend/app/integrations/telegram/sender.py:56-73` — `send_text_dm` API + `SendResult` shape; Phase 20 calls `send_text_dm` for all four DM paths.
- `apps/backend/app/workers/telegram_bot.py:29` — existing D-06 import `from app.modules.auth import telegram_service`; Phase 20 adds parallel D-10 import for `visits.service`.
- `apps/backend/app/workers/telegram_bot.py:56-67` — `redis_lifespan_manager()` entered + `HandlerContext` constructed + `build_application(handlers=[("start", start_handler)])`. Phase 20 modifies all three lines.

### Phase 15 outputs (audit taxonomy + commit gate)
- `.planning/phases/15-foundations-rbac-audit-taxonomy-helper-hoisting/15-CONTEXT.md` — INFRA-11 audit taxonomy frozenset + AST literal walker; Phase 20 adds one entry to the frozenset.
- `apps/backend/app/core/audit.py:74-117` — `LOCKED_AUDIT_EVENTS` frozenset; Phase 20 adds `("telegram_unknown_checkin", "visit")`.
- `apps/backend/app/core/audit.py:120-173` — `audit.emit` signature; Phase 20's handler-side emit uses the same shape, `actor_user_id=None`, `resource_type='visit'`, `resource_id=None`, payload `{chat_id, telegram_user_id_hash}`.
- `apps/backend/tests/unit/test_audit_taxonomy.py` — Phase 15 AST walker; auto-passes for Phase 20's new callsite once the frozenset entry is added (no walker extension needed).

### Pitfalls + research
- `.planning/research/PITFALLS.md` Pitfall 8 (lines 240-269) — bot oracle leak; Phase 20 D-20-7 (locked 4 strings, no oracle data in success message) + D-20-9 (ClientNotLinkedError reuses no-membership string) are the structural mitigations.
- `.planning/research/PITFALLS.md` Pitfall 9 (lines 273-299) — bot replay; Phase 20 D-20-1..6 (Redis update_id dedup with `sz:bot:update:` keyspace, fail-open, silent on hit) is the structural mitigation. The "accepted residual friend-fraud risk" Key Decision (PROJECT.md L167) covers what Phase 20 explicitly does NOT defend against.
- `.planning/research/PITFALLS.md` line 519 — Redis namespace prefix table; `sz:bot:update:*` slot is reserved here.
- `.planning/research/ARCHITECTURE.md` lines 193-269 (§"Telegram Bot `/checkin` Handler") — original handler design sketch; Phase 20 implements this with the corrections D-20-7 (no `{gym_name}/{time_msk}` interpolation on success — REQUIREMENTS lock supersedes the research draft) and D-20-9 (ClientNotLinkedError handling, not in research draft).
- `.planning/research/ARCHITECTURE.md` line 465 — phase 20 row of the phase-vs-files table.

### Backend codebase — wiring touch-points (read at plan time)
- `apps/backend/.importlinter` — `integrations ⊥ modules` and `workers ⊥ modules` contracts; Phase 20 verifies the `workers → modules.visits.service` exception is allowed (mirror of D-06 `workers → modules.auth.telegram_service`).
- `apps/backend/app/core/redis.py:21-38` — `redis_lifespan_manager` async-context yields the singleton client; Phase 20's worker passes the yielded client into `HandlerContext.redis`.
- `apps/backend/app/core/config.py` — `Settings.gym_hours_start`/`_end` are Phase 19-shipped (Pydantic `time` parsing). Phase 20 does NOT read these directly (D-20-8); they flow via the exception fields.
- `apps/backend/.env.example` — already has `GYM_HOURS_START=07:00` / `GYM_HOURS_END=23:00` (Phase 19). Phase 20 adds nothing.
- `apps/backend/docker-compose.yml` — `telegram-bot` service (Phase 7) is already declared; Phase 20 does NOT add a service.

### Tests (Phase 20 adds)
- `apps/backend/tests/unit/test_audit_taxonomy.py` — passes verbatim once frozenset is extended.
- (No existing `tests/integration/telegram_bot/` — Phase 20 creates the directory.) `tests/integration/conftest.py` `db_session` SAVEPOINT fixture (Phase 4 D-26) is reusable; Phase 19's `db_session_real_commit` (Phase 19 D-13) is NOT needed for Phase 20 (no concurrent test).
- `tests/integration/visits/conftest.py` (Phase 19) — fixtures for active client + active membership + clients-with-telegram_user_id; Phase 20 reuses these for the happy-path / no-membership / duplicate / outside-hours cases.

### Conventions
- `.planning/codebase/CONVENTIONS.md`, `STRUCTURE.md`, `TESTING.md`.
- `apps/backend/docs/conventions.md` — backend conventions.
- `apps/backend/docs/architecture.md` — modular monolith doc; D-10 narrative addendum (NOT a contract relaxation, NOT an ADR change) goes here at plan time.
- `apps/backend/docs/adr/0001-modular-monolith.md` — ADR for import-linter contracts; Phase 20 doesn't touch the ADR (D-10 is a narrative addendum to architecture.md per Phase 19 D-09 precedent).

### Third-party docs (read on demand)
- [redis-py — `Redis.set` async](https://redis.readthedocs.io/en/stable/commands.html#redis.commands.core.CoreCommands.set) — `nx`/`ex` kwargs; the standard atomic SET-NX-EX idiom.
- [python-telegram-bot 22 — Application + CommandHandler](https://docs.python-telegram-bot.org/en/v22.0/telegram.ext.application.html) — handlers list shape Phase 20 extends.
- [Pydantic v2 — `time` parsing](https://docs.pydantic.dev/latest/concepts/types/#datetime-types) — already used by Phase 19; Phase 20 reads `time.isoformat()` results from the exception fields.

</canonical_refs>

<code_context>
## Existing Code Insights

### Reusable Assets

- **`HandlerContext` NamedTuple (`handlers.py:35-46`)** — Phase 7 D-05 closure shape. Phase 20 extends with two fields (visits_service + redis) without breaking the existing `start_handler` (which only reads session_factory, telegram_service, sender — extra fields are inert).
- **`_hash_token_for_log` (`handlers.py:68-74`)** — sha256-hex helper Phase 7 uses for non-secret structlog correlators. Phase 20 mirrors with `_hash_telegram_user_id(int) -> str` for audit-payload PII minimization (D-20-10 hashes the raw telegram_user_id before writing the audit row).
- **`send_text_dm` (`sender.py:56-73`)** — sole outbound DM boundary (Phase 7 D-07). Phase 20 calls this for all 4 DM paths; tests stub the sender module (TEST-03 pattern).
- **`audit.emit` co-transactional emit (`audit.py:120-173`)** — Phase 5 contract. Phase 20's handler-side `telegram_unknown_checkin` emit follows the same shape; explicit `await session.commit()` after emit (handler-owned commit on the unknown-checkin path; service owns commits on the four `visit_*` paths).
- **`redis_lifespan_manager` (`core/redis.py:21-38`)** — Phase 7 D-08 async-context. Worker enters it, passes yielded client into `HandlerContext.redis`.
- **`build_application` (`bot.py:43-82`)** — Phase 7 D-09 factory. Phase 20 doesn't modify this file; the worker just passes a longer `handlers=[("start", start_handler), ("checkin", checkin_handler)]` list.
- **String-name exception dispatch (`handlers.py:127-152`, Phase 7 D-04/D-20)** — `cls_name = type(exc).__name__; if cls_name == "OtpAlreadyConsumed": …`. Phase 20 reuses for `NoActiveMembershipError`/`DuplicateCheckinError`/`OutsideGymHoursError`/`ClientNotLinkedError` because importing those classes from `app.modules.visits.exceptions` would break `integrations ⊥ modules`.
- **`_global_error_handler` (`bot.py:32-40`)** — Phase 7 D-09 resilience: any uncaught handler exception is logged, polling stays alive. Phase 20 relies on this for the "any other exception" branch — no try/except needed in `checkin_handler` for unexpected errors.

### Established Patterns

- **Handler receives everything via `HandlerContext`** — Phase 7 D-05 invariant. Phase 20 extends the NamedTuple instead of importing `app.state.redis` from inside `handlers.py` (would couple integrations to FastAPI app-state shape).
- **Service owns mutate + audit emit + commit; handler is thin** — Phase 19 INFRA-13 commit-gate pattern. Phase 20's handler does NOT call `session.commit()` after a successful service call (Phase 19 service already committed per D-05). Handler DOES commit only on the `telegram_unknown_checkin` path (handler-owned audit emit per D-20-10).
- **Locked code-constant DM strings** — Phase 7 `_DM_STRANGER`/`_DM_REPLAY` precedent. Phase 20 follows: 4 module-level constants in `handlers.py`, no i18n framework.
- **D-NN cross-phase exceptions to import-linter** — D-06 (Phase 7), D-10 (Phase 20). Both are narrative addenda to `apps/backend/docs/architecture.md`, NOT changes to `.importlinter` contracts beyond an explicit `ignore_imports:` line if the contract is whitelist-shaped.
- **AST audit taxonomy walker auto-validates new callsites** — Phase 15 INFRA-11. Adding `("telegram_unknown_checkin", "visit")` to the frozenset is sufficient; the walker enforces literal-string callsite parity.

### Integration Points

- **`app/integrations/telegram/handlers.py`** — extends NamedTuple (2 fields), adds 4 DM constants, adds 2 helpers (`_hash_telegram_user_id`, `_format_gym_hours`), adds `checkin_handler` (~50 lines).
- **`app/workers/telegram_bot.py`** — adds 1 import (D-10 `visits.service`), modifies HandlerContext construction (4 fields → 5 fields), extends handlers list (1 entry → 2 entries). Net ~5 lines.
- **`app/core/audit.py`** — adds 1 frozenset entry + 1 docstring line under a new `## v1.2 (Phase 20)` block. Net ~3 lines.
- **`app/main.py`** — NO changes. Phase 20 has no composition-root wiring (Phase 19 already registered `register_client_by_telegram_resolver` for the bot-path lookup).
- **`apps/backend/.importlinter`** — verify the `workers → modules.visits.service` edge is whitelisted (mirror of `workers → modules.auth.telegram_service`); add 1 line if needed.
- **`apps/backend/openapi.json`** — NO changes (no HTTP surface).
- **`apps/backend/docker-compose.yml`** — NO changes.
- **No `.env.example` changes** (Phase 19 already added `GYM_HOURS_*`).
- **No `apps/admin-web/*` changes** — Phase 22 owns FE wiring.

</code_context>

<specifics>
## Specific Ideas

- **The reuse of `_DM_NO_MEMBERSHIP` for `ClientNotLinkedError` (D-20-9) is the headline anti-oracle decision.** It is what makes the bot useless as an account-enumeration tool: a stranger sending `/checkin` sees the same response as a linked-but-no-membership client. The planner MUST add a docstring comment on the exception-dispatch block explaining this so a future contributor doesn't "fix" it back to a 5th honest-UX string.
- **In-handler dedup (D-20-1) keeps blast radius small but means a future Phase 21+ handler MUST copy the 6-line dedup pattern.** Acceptable for v1.2 (only `/checkin` needs it). If a third bot command joins in v1.3+, factor out `dedup_then(handler)` then; YAGNI for now.
- **`{hours}` formatting flowing exception-fields → handler (D-20-8) decouples Phase 19 from presentation but pins the field contract.** The `_format_gym_hours(exc)` helper's `KeyError` defensive raise (RuntimeError "Phase 19 regression") is the safety net.
- **`telegram_unknown_checkin` on `resource_type='visit'` (D-20-10), NOT `'otp'`** — matters for ops queries: `SELECT * FROM audit_log WHERE resource_type='visit'` should give the COMPLETE visits anti-fraud picture (5 events: 4 from Phase 19 + 1 from Phase 20). Cross-resource event names defeat that filter.
- **Owner sign-off on the locked Russian DM strings** is a REQUIREMENTS AUTH-TG-11 acceptance criterion, surfaced in `20-03-PLAN.md` as a checkbox in the plan's acceptance criteria. Merge is gated on the sign-off.

</specifics>

<deferred>
## Deferred Ideas

- **Per-chat-id rate limit (`sz:bot:rate:{chat_id}` token bucket, N=5/hour)** — PITFALLS Pitfall 8 mitigation #3. Single-zal v1.2 doesn't need it; revisit at v1.3+ if Telegram-side abuse rises.
- **Webhook-based bot mode** — PROJECT.md "Auth UX" deferred list. Long-polling is sufficient for single-zal.
- **DM on Redis outage (5th locked string)** — rejected per D-20-3 fail-open; revisit only if "bot check-ins silently process during Redis outage" turns out to be wrong in production.
- **Bot replay audit event (`bot_replay_attempt` resource=visit)** — rejected per D-20-4 silent-on-replay; revisit if ops needs visibility into replay frequency.
- **Bot-level commands beyond `/start` and `/checkin`** (`/status` "когда мой абонемент кончается?", `/help`) — would re-introduce oracle leaks (Pitfall 8). Defer to v1.3+ with a per-command oracle-leak review.
- **`dedup_then(handler)` decorator** — useful when a third bot command joins; YAGNI for v1.2.
- **`_DM_*` i18n for non-Russian zals** — out of scope; Russian-only product per PROJECT.md L133.
- **Photo turnstile / NFC / geofence** — explicitly v2+ per Pitfall 9 / PROJECT.md "accepted residual fraud risk". Phase 20 doesn't change this.
- **Daily one-time deep-link → bot button (Pitfall 9 mitigation #5)** — friction trade-off, deferred.
- **Pre-formatted `'07:00–23:00'` field on `OutsideGymHoursError`** — rejected per D-20-8 (presentation lives in handler); revisit if a second consumer (e.g., admin-web error renderer) wants the same format.

</deferred>

---

*Phase: 20-telegram-bot-checkin-self-check-in*
*Context gathered: 2026-05-08*

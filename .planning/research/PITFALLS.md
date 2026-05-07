# Pitfalls Research — v1.2 Memberships + Visits + ARQ + Bot /checkin

**Domain:** Gym CRM — time-based memberships, visit tracking, scheduled jobs, Telegram bot self-service
**Researched:** 2026-05-07
**Confidence:** HIGH (architectural / RU-context items grounded in v1.1 retrospective + repo audit; ARQ items validated against upstream docs/issues)

Scope: pitfalls **specific to** adding `memberships` + `visits` modules + the first real ARQ scheduled job + extending `app/workers/telegram_bot.py` with `/checkin` to the **existing** Sportzal modular monolith. Generic FastAPI / Postgres advice is out of scope unless v1.1 retrospective evidence shows it bites this team specifically.

Phase code shorthand used in this doc:
- **F** = Foundations (audit/service template hardening, TZ helper, Alembic helpers — pre-business work)
- **MB** = Memberships backend (plans + instances + lifecycle)
- **VB** = Visits backend (manual + bot check-in endpoints)
- **AQ** = ARQ scheduled job (`expire_memberships` daily)
- **BC** = Bot /checkin handler extension
- **FE** = admin-web wiring (memberships/visits routes + client-detail enhancements)
- **HG** = Hygiene / drift gates (audit naming, OpenAPI, contract tests)

Severity scale:
- **BLOCKER** — must be prevented or v1.2 ships with a real bug (PII / data corruption / silent data loss)
- **HIGH** — likely to cost a phase if not pre-empted; analogue of v1.1 Phase 12.1 / CR-01 / F-03
- **MEDIUM** — quality / UX hit, recoverable in a follow-up phase

---

## Critical Pitfalls

### Pitfall 1: Service write paths missing `await session.commit()` (Phase 12.1 reprise)

**Severity:** BLOCKER

**What goes wrong:**
A new `memberships/service.py` or `visits/service.py` mutates the session, awaits `audit.emit(...)`, calls `await session.flush()`, and returns. The 201 response is sent, structlog audit event fires, but the row never persists — `get_db` runs `await session.rollback()` at request exit (database.py:145) because no `commit()` was called. The bug is masked because audit events still appear in logs.

**Why it happens:**
`auth/service.py` and the v1.1 `clients/service.py` both originally shipped without explicit commits. Any new module written by an AI agent that copies "what auth did" or "what the discuss-phase pseudocode looked like" inherits the same gap. Unit tests don't catch it because the SAVEPOINT-mode `db_session` fixture rolls back regardless of commit/no-commit. Integration tests using `httpx ASGITransport` go through `get_db`, but if the test re-reads via the same session it sees the in-flight write before rollback. Only a multi-request live runbook (Phase 11 SC #4 was the v1.1 trigger) reveals it.

**How to avoid:**
1. **Establish a `BusinessService` template** in Phase F (foundations) before any business code: a checklist comment or a tiny helper `async def _commit_unit_of_work(session)` that all mutation paths terminate with. Doc-block must mirror `clients/service.py:1-38` block calling out the commit invariant.
2. **Add an integration test pattern** (one per mutation): write through endpoint, then issue a fresh GET in a separate `async_client.request(...)` call that gets a *new* `get_db` session. If commit is missing the GET returns 404 / stale data.
3. **Add a smoke E2E in CI** (or at minimum a Phase MB / VB SC item): create membership → fetch list → expect membership present. Same for visit creation.
4. **Mypy strict trick:** make every `service.create_*` return type explicitly `Awaitable[ResponseModel]` and have ruff/mypy enforce that the function body contains a literal `await session.commit()` via a custom AST grep test (`scripts/check_service_commits.py` — runs in CI).

**Warning signs:**
- Audit event present in `audit_log` query during dev but `memberships.list()` returns empty after restart.
- `pytest -k integration` green but `docker compose exec web` curl shows row missing after POST.
- Live demo to user: "I just created it, why isn't it there?"

**Phase to address:** **F** (write the template + AST gate before MB/VB/BC services are scaffolded).

---

### Pitfall 2: `Membership.end_date` calendar math wrong on month-boundary purchase dates

**Severity:** HIGH

**What goes wrong:**
A 30-day plan purchased on 2026-01-31 should end on 2026-03-02 (or 2026-03-01 — see exclusive/inclusive below). If the implementation uses `start_date + relativedelta(months=1)` it lands on 2026-02-28 (3 days short — customer overcharged). If it uses `+ timedelta(days=30)` for the 30-day plan and `+ relativedelta(months=12)` for the 365-day plan inconsistently, two clients with the "same" start date and "same" plan can have different expirations.

**Why it happens:**
- Two plausible mental models: "duration in days" (30/90/180/365) vs. "duration in months" (1/3/6/12). Mixing them is a classic mistake.
- `relativedelta` quietly clamps to the last day of the target month (Jan 31 + 1 month = Feb 28).
- Russian "месячный" (monthly) and "30-дневный" (30-day) are colloquially the same to users but mathematically different.
- The PROJECT.md spec lists `duration_days 30/90/180/365` — i.e. the schema is *days-based*. But the FE label "1 месяц" / "3 месяца" can drift if a future plan editor lets owner type "месяц" instead of `30`.

**How to avoid:**
1. **Lock the model to days only.** `MembershipPlan.duration_days INT NOT NULL CHECK (duration_days > 0)`. No `duration_months` column, no DateInterval, no `relativedelta`. End-date computed as `start_date + INTERVAL 'N day'` in SQL or `date + timedelta(days=N)` in Python.
2. **Pick exclusive end-of-day semantics and document it as a Key Decision.** Recommendation: `end_date` is **inclusive** (last valid day for check-in); `expired` means `today > end_date` (Europe/Moscow date). Add to `.planning/PROJECT.md` Key Decisions table.
3. **Compute end_date once at insert and store it.** Never derive on-read. This is also necessary for the snapshot (Pitfall 3).
4. **Add a property-based test** (`hypothesis`) that for any `start_date` in 2025-2030 and `duration_days ∈ {30, 90, 180, 365}`, `end_date - start_date == timedelta(days=duration_days - 1)` (or whatever the inclusive-end-day convention dictates).

**Warning signs:**
- Two memberships with identical plans + start dates but different `end_date` values (likely a `relativedelta` regression).
- "Why does my abonement expire 2 days early in February?" support ticket.
- `expired` count from the daily ARQ job is non-zero on a day where no plan should naturally expire.

**Phase to address:** **F** (decide inclusive/exclusive + days-only model) → **MB** (enforce in schema/service).

---

### Pitfall 3: Snapshot pricing not copied → plan edits retroactively rewrite history

**Severity:** BLOCKER (financial integrity)

**What goes wrong:**
`Membership` is stored as `(client_id, plan_id, start_date, end_date)`. Reception lists "истории абонементов" and the page joins through `MembershipPlan` to render the price. Owner edits the plan from 5000₽ → 6000₽ tomorrow. Every historical membership row instantly reads as if the client had paid 6000₽. Audit log shows a `plan_updated` event but no `membership_*_repriced` events because the model has no copy. Refund calculations, owner reports, and any future revenue reconciliation are corrupted.

**Why it happens:**
- The natural ORM relationship is `membership.plan.price_kopecks` — feels DRY.
- Rails-style "always join the catalogue" is the default mental model.
- The discuss-phase often skips the snapshot question because plans look "static enough" in v1.2.
- v1.1 had no domain with a price column, so there's no precedent to copy from.

**How to avoid:**
1. **Make `Membership` carry `price_kopecks_snapshot` and `duration_days_snapshot` as NOT NULL columns**, copied from `MembershipPlan` at insert time. The `plan_id` is kept only for analytics ("which plan was this?"); it must be `ON DELETE RESTRICT` (never lose the catalog row that the snapshot references for name/active flag). Better: `plan_name_snapshot VARCHAR NOT NULL` so renames don't surprise either.
2. **Add a service-level invariant test:** edit the plan price → re-fetch a previously-created membership → assert `price_kopecks` unchanged.
3. **Document in Key Decisions:** "Membership rows are immutable financial records once `paid_at` is set; only `status`/`cancelled_at` may mutate post-creation."
4. **For the future v1.3 billing milestone**, this snapshot is also what receipts (54-ФЗ) will reference — getting it right now saves a data-migration phase later.

**Warning signs:**
- `MembershipPlan` has a foreign-key relationship from `Membership` but `Membership` has no `price_*` column → bug present.
- Visit list page shows different price for "the same membership" before vs after a plan edit (Pitfall is live).
- Owner asks "why does last month's revenue change when I update prices?"

**Phase to address:** **MB** (must be in the first migration, not retrofitted).

---

### Pitfall 4: ARQ `expire_memberships` job not idempotent → double-marking + audit log spam

**Severity:** HIGH

**What goes wrong:**
The job runs at 03:05 Europe/Moscow daily. On the day a worker pod restarts mid-run, ARQ may re-enqueue. Or the worker crashes after the UPDATE but before `commit()`, then re-runs and emits a second `membership_expired` audit row for every still-affected client. Or the job runs once on monkey-patched test environment and twice in prod due to APScheduler vs ARQ cron decorator confusion. The audit log grows polluted, structlog rolls "expired" events twice, and any FE counter showing "expired today" is wrong.

**Why it happens:**
- **First real ARQ scheduled job** in this codebase. The `app/workers/scheduler.py` is a one-line TODO placeholder; `arq_app.py` has `functions: ClassVar[list[Any]] = []`. No precedent → no muscle memory.
- ARQ's `cron` decorator has a `unique=True` default and a `keep_cronjob_progress = 60` constant, but these only protect against same-instant duplicate enqueue, not against the "worker crashed and restarted" case ([arq issue #193](https://github.com/samuelcolvin/arq/issues/193)).
- Naive implementation: `UPDATE memberships SET status='expired' WHERE status='active' AND end_date < today`. Looks idempotent — but the audit-log emit is not. The second run finds zero rows to update but the first run's audit may have already partially committed before crash.
- Without integration with `request_id`, structlog events from the job are unstructured and indistinguishable across runs.

**How to avoid:**
1. **Make the SQL update truly conditional and atomic.** Use `UPDATE ... WHERE status='active' AND end_date < :today RETURNING id` — only newly-flipped rows return. Emit audit only for those returned IDs.
2. **Wrap the job body in a single transaction** (one `async with session.begin():`); commit at the end. If the worker dies mid-run, *nothing* committed. Re-run is fully safe.
3. **Add a `job_run` correlation id** generated at job entry (`job_id = uuid4()`) and propagated as a `structlog.contextvars.bind_contextvars(job_id=...)` so the structlog output has a request-id-equivalent. Document this in `app/workers/__init__.py` as the worker logging convention (parallel to the API's RequestIdMiddleware → structlog binding).
4. **Cap audit emission rate inside the job:** if more than N=200 memberships expire in a single run, emit one `memberships_bulk_expired {count: N}` row and the per-row events at structlog INFO only. Prevents audit table growth surprises.
5. **CI test with monkey-patched clock:** run the cron callable twice with the same fake `today`; assert the second invocation emits zero new rows and zero new audit log rows.
6. **Don't co-locate `cron_jobs` with `functions` and forget to add the function** — ARQ silently does nothing if the scheduler points at a non-registered function name. Add an `on_startup` assertion that all cron entries resolve.

**Warning signs:**
- Two `membership_expired` rows for the same `resource_id` within the same calendar day.
- `audit_log` row count for the day > 2× the count of memberships actually expiring.
- Worker restart in compose log immediately followed by a duplicate "expired N memberships" structlog line.

**Phase to address:** **AQ** (this entire phase; deserves a discuss-phase research artifact treating it like Phase 7 should have been).

Sources: [ARQ issue #193 — Cron job scheduling behaviour](https://github.com/samuelcolvin/arq/issues/193), [ARQ docs — index](https://arq-docs.helpmanual.io/), [The Inner Workings of: Arq](https://threeofwands.com/the-inner-workings-of-arq/).

---

### Pitfall 5: Visit `1/day` enforcement via app-layer check creates race window

**Severity:** BLOCKER (multi-checkin)

**What goes wrong:**
Reception terminal A and Telegram bot fire `POST /api/v1/visits` for the same `client_id` ~50ms apart. Both transactions read "no visit today" (SELECT in service layer), both INSERT, both succeed. Client gets two visits on the same day, audit log is fine, anti-fraud is bypassed. Worse: if the FE shows "you already checked in" only after a re-fetch, the client never knows their friend is using their account.

**Why it happens:**
- The "obvious" enforcement is `if exists(visit today): raise ConflictError`. That pattern works for soft-delete reuse (Pitfall N/A) but **fails under concurrency** because two transactions can both see "no visit" before either commits.
- `READ COMMITTED` (Postgres default) does not serialize this read — only a UNIQUE constraint or `SELECT ... FOR UPDATE` does.
- v1.1 didn't have any "1/day" semantics so there's no muscle memory.
- The two channels (reception manual, bot) are different code paths; reviewers may verify only one path.

**How to avoid:**
1. **DB-level UNIQUE INDEX is the ONLY correct enforcement:**
   ```sql
   CREATE UNIQUE INDEX uq_visits_one_per_gym_day
     ON visits (client_id, gym_date)
     WHERE deleted_at IS NULL;
   ```
   The `gym_date` column is computed server-side from `checked_in_at AT TIME ZONE 'Europe/Moscow'`'s date. Treat `gym_date date NOT NULL` as a stored generated column (Postgres `GENERATED ALWAYS AS (...) STORED`) so app code can't put a wrong value.
2. **Service layer catches `IntegrityError` on `uq_visits_one_per_gym_day` → translates to `VisitAlreadyTodayError` (409)**, mirroring the `clients` `_is_phone_conflict` pattern at `clients/service.py:99-104`. Add to `core/exceptions.py`.
3. **Decide the "day" semantics explicitly and write it in Key Decisions:**
   - **Gym day = calendar date in Europe/Moscow** (recommended; matches the user's mental model — "сегодня").
   - NOT "rolling 24h" (Telegram bot 23:59 + 00:01 should be allowed as 2 visits if the gym is open).
   - NOT UTC (a 02:30 Moscow visit is "yesterday" in UTC, would surprise users).
4. **Property test:** spawn 10 concurrent `httpx` requests against the test app for the same client; expect exactly 1 success + 9 × 409.
5. **DO NOT rely on `SELECT ... FOR UPDATE` on the client row** to serialise — the client row isn't conceptually locked, and a long-running update there blocks unrelated reception flows.

**Warning signs:**
- `visits` table has rows with the same `(client_id, DATE(checked_in_at AT TIME ZONE 'Europe/Moscow'))` → already broken.
- Reception sees "checked in" but bot also says "✅ Отмечено" within seconds.
- Anti-fraud audit log shows zero `visit_already_today` rejection events while the visit count is suspiciously high.

**Phase to address:** **VB** (must be in the first migration; cannot be retrofitted without a data-cleanup migration).

---

### Pitfall 6: ILIKE search on memberships/visits forgets the CR-01 LIKE-escape

**Severity:** HIGH (PII over-exposure regression)

**What goes wrong:**
`memberships/repository.py` adds a "search by client name on memberships history" filter, or `visits/repository.py` adds the same on the visits page, copying the pattern from `clients/repository.py` but **omitting `_escape_like_pattern`**. Reception user types `?q=%` and gets the full membership/visit roster — same PII over-exposure that CR-01 hit and Phase 14 closed.

**Why it happens:**
- The escape helper lives **in clients**, not in `core`. `modules-independent` contract forbids `memberships → clients` import. The natural copy-paste lifts the body but not the comment context, and an AI agent mid-discussion may "simplify" by removing what looks like Phase-specific commentary.
- v1.1 retrospective specifically lists this as the closing fix (Phase 14 / CR-01).
- The unit tests for clients exercised the escape; new modules' tests will not unless explicitly added.

**How to avoid:**
1. **Promote `_escape_like_pattern` into `app/core/sql.py`** (or `app/core/search.py`) and rewrite `clients/repository.py` to import it. This makes the helper available to any module without violating `modules-independent`. Mark this as a Phase F task before any new search lands.
2. **Add a project-wide pytest** (`tests/integration/test_search_pii_hardening.py`) parametrised over every module that exposes an ILIKE search endpoint. For each, hit `?q=%` and `?q=_` and `?q=\\` and assert the response item count is 0 (or filtered-as-literal), not "everything".
3. **Add a ruff custom rule or grep CI gate** that flags any new `.ilike(f"%{...}%")` in `app/modules/**/repository.py` that doesn't go through the helper. (Or import-linter `forbidden_modules` against `sqlalchemy.sql.operators` outside `core/sql.py` — heavy-handed but rock-solid.)
4. **In Phase MB / VB review checklist:** "Did this module add ILIKE? Did it use the central helper? Is the PII test parametrised?"

**Warning signs:**
- Grep for `.ilike(` in `apps/backend/app/modules/` returns hits outside `clients/`.
- A PR adds search to a new module without adding to the parametrised PII test.
- Reception support ticket: "I typed % into search and saw clients I shouldn't have."

**Phase to address:** **F** (move helper to core) → **HG** (add PII parametrised test that catches future modules).

---

### Pitfall 7: import-linter `modules-independent` broken via TYPE_CHECKING-only Protocol callbacks done wrong

**Severity:** HIGH (architectural drift)

**What goes wrong:**
Visits needs to validate "client has an active membership". The natural code is `from app.modules.memberships import service`. import-linter contract `modules-independent` rejects it (this is by design — see `.importlinter:13-25`). The fix is the v1.1 Protocol-callback pattern (D-24, registered in `app/main.py`). But mid-implementation an AI agent puts the import outside `TYPE_CHECKING` block, or uses `from app.modules.memberships.service import MembershipChecker as _ProtocolForType`, which technically imports the module body at startup → contract red.

**Why it happens:**
- Cross-module `Protocol` typing is genuinely subtle; v1.1 needed it twice (auth/clients via `register_user_loader`) and once for telegram-bot via the documented D-06 exception.
- AI agents tend to "fix" `ImportError` by importing eagerly.
- `import-linter` reports a single failure with cryptic output unless run locally — CI failure 30 min into a phase is a planning hit.

**How to avoid:**
1. **Establish the cross-module callback pattern as a code template in Phase F** before VB/MB land. File: `app/core/cross_module.py` (or extend `core/dependencies.py`). Pattern: declare `Protocol` in `core`, register from `main.py`, inject via `Depends(...)`. Document in `docs/conventions.md`.
2. **For Visits → Memberships specifically:** the check is `does_client_have_active_membership(session, client_id) -> Membership | None`. This is the exact shape that should live as a `Protocol` in `core`, with `memberships/service.py` registering an implementation from `app/main.py`'s lifespan (the `clients` `register_user_loader` from v1.1 is the precedent).
3. **`if TYPE_CHECKING:` imports go AT THE TOP, never inside function bodies for typing.** AI-agent hint in the file's docstring.
4. **Run `uv run lint-imports` BEFORE every commit in MB/VB phases** — not just CI. A pre-commit hook is cheap insurance.
5. **D-06 telegram exception extension:** the `/checkin` handler will need `app.modules.visits.service` access (to record the visit). Either:
   - **Recommended:** route via `HandlerContext` (extend the existing NamedTuple at `handlers.py:35-46`) — same pattern as `telegram_service`.
   - **Alternative:** widen the D-06 docstring exception to also list `app.modules.visits.service`. Less elegant; fewer code changes.
   Pick one in BC discuss-phase and document it in `app/workers/telegram_bot.py` docstring.

**Warning signs:**
- `uv run lint-imports` fails with `modules.visits → modules.memberships` or similar.
- A diff to `app/main.py` adds a `from app.modules.X import Y` at module top level (composition root only — fine) — but check if the same line snuck into an in-module file.
- `from typing import TYPE_CHECKING` appears in a runtime file but isn't actually used.

**Phase to address:** **F** (write the template + extend HandlerContext shape) → **VB** (use it for memberships check) → **BC** (extend HandlerContext for visits write).

---

### Pitfall 8: Telegram bot `/checkin` reveals too much in error messages → enumeration / fraud pre-flight

**Severity:** HIGH (PII / fraud)

**What goes wrong:**
The bot DM responds with rich, helpful errors:
- `"❌ У вас нет активного абонемента"` (no active membership)
- `"❌ Ваш абонемент истёк 12 марта"` (expired on date X)
- `"❌ Зал закрыт. Откройтесь в 8:00"` (gym closed)
- `"❌ Вы уже отметились сегодня"` (already checked in today)

The first two leak account state to anyone who has the chat-id. If a friend has captured a `telegram_chat_id` (or just sends `/checkin` from a stolen device), the bot becomes a free oracle: "is this account valid, does it have a membership, when does it expire?" Combined with v1.1's deep-link flow, an attacker can verify account existence without ever logging in.

**Why it happens:**
- Russian gym staff want helpful errors ("ваш абонемент истёк 12 марта" is genuinely useful for legit users).
- v1.1 had a similar tension (Telegram OTP) and chose `_DM_STRANGER` ("этот Telegram не привязан") — already-leaks-existence but no more, see `handlers.py:50-54`. That's a precedent to follow but a borderline one.
- The contrast: the email-password `/login` correctly returns "неверный email или пароль" (no enumeration). The bot path, being DM-only, feels safer than it is.

**How to avoid:**
1. **Two-tier message strategy:**
   - **Pre-flight (legitimate user):** "✅ Отмечено" on success. On any failure → single generic Russian message: `"❌ Не удалось отметить посещение. Обратитесь к администратору."`
   - **Audit log (server-side):** record the precise reason (`no_active_membership`, `membership_expired`, `outside_gym_hours`, `already_today`) with `actor_chat_id` for support follow-up.
2. **Reception UI gets the rich reason** because reception is authenticated; the bot does not.
3. **Rate-limit /checkin per chat_id:** 1 successful check-in per gym-day (server-enforced) + N=5 attempts per hour per chat_id at the bot layer (Redis token bucket). Prevents the oracle scenario.
4. **Audit event names should distinguish channel:** `visit_rejected_bot` vs `visit_rejected_reception` so the support workflow can detect "user keeps trying via bot, reception should call them" patterns.
5. **DO NOT include client name or membership end_date in any DM**, even on success. "✅ Отмечено" is enough; the rich confirmation lives in admin-web.
6. **Telegram DM blocked / user not found:** silent on bot side, audited server-side. Same pattern as v1.1 `telegram_dm_blocked` (`audit.py:23`).

**Warning signs:**
- Russian DM strings in `handlers.py` (or new `checkin_handler.py`) reference dynamic data: `f"истёк {date}"`, `f"откройтесь в {hour}"`.
- A test exercises the bot path and asserts the DM contains `"абонемент"` — likely already leaking.
- Support ticket: "Я знаю, что у моего бывшего нет абонемента, бот сказал."

**Phase to address:** **BC** (with explicit Russian copy review in discuss-phase).

---

### Pitfall 9: Bot replay — Telegram message can be re-sent, OR friend uses logged-in chat

**Severity:** HIGH (fraud)

**What goes wrong:**
- Scenario A: User shares a screenshot of their `/checkin` button press; friend forwards the message → server processes the same `update_id` again. (Mitigated by Telegram's update_id deduplication, but only if the worker tracks `update_id` — long-polling default does, but a worker restart can re-process.)
- Scenario B: Two clients share one Telegram account (e.g. spouse). Both physically come to the gym; only one logs the check-in via bot. The spouse gets a "free" visit because reception didn't see them.
- Scenario C: Telegram chat-id is bound to user A, user A gives phone to friend B at home, friend B types `/checkin`. Server has no way to know B isn't A.

**Why it happens:**
- The bot is convenient *because* there's no second factor. Adding one (camera, NFC, geofence) defeats the purpose for v1.2.
- v1.1's deep-link flow proved telegram_chat_id binding works for OTP, but OTP is a one-time event; check-in is daily.
- "1 visit per day" at the schema level (Pitfall 5) covers Scenario A but not B or C.

**How to avoid:**
1. **Accept the residual risk for v1.2 and document it.** Self check-in via bot is convenience; reception staff visually verifying the client is the v1 anti-fraud. Single-zal CRM, single-trainer ecosystem — fraud-by-friend is a bounded loss.
2. **Geo-fence via env-config gym hours window** (already in spec): `GYM_OPEN_HOUR=8`, `GYM_CLOSE_HOUR=23` Moscow time. Bot check-in outside window → 409 + audit event. Doesn't catch friend-fraud but catches "checked in from home overnight".
3. **Server-side update_id idempotency** (defence against bot worker restart replays): track last-processed `update.update_id` per chat_id in Redis with TTL=1h. Skip already-seen updates. ptb-22 has built-in dedup but only in-memory; a worker restart loses it. NB: this is also documented as Phase 7 D-20 pattern (`telegram_replay_attempt` audit event).
4. **Reception sees recent bot check-ins on the client-detail page** — gives reception a passive verification ("oh, this person already checked in via bot 5 min ago — good, no double-count needed").
5. **Future v1.3+ option (NOT v1.2):** require a daily one-time deep-link → bot button (similar to OTP). Friction trade-off; document as deferred.

**Warning signs:**
- Worker restarts followed by duplicate `visit_created` events for the same client+day (Pitfall 5 catches this on DB level, but the bot replay attempt should still be detected and audited).
- High ratio of `visit_rejected_bot {reason: outside_gym_hours}` from late-night check-ins → suggests bot abuse or wrong env config.
- One client has 30+ visits/month while their membership is "30 days" — hint that bot is doing the work alone.

**Phase to address:** **BC** (update_id dedup + gym-hours window + Russian copy) + Key Decisions entry on accepted residual risk.

---

### Pitfall 10: Audit log writes drift across modules → entity_type, action naming, missing user_id

**Severity:** HIGH (analytics + v1.1 known issue continuation)

**What goes wrong:**
Three independent modules now write to `audit_log`. v1.1's `audit.py` already documents 18 locked event names (`audit.py:11-29`). Phase MB adds `membership_created`, Phase VB adds `visit_created`, Phase AQ adds `membership_expired`. Without discipline:
- VB writes `visit.created` (dot-style) while MB writes `membership_created` (underscore-style) — query-time joins fail.
- AQ's bot job has no `actor_user_id` (correct: system event) but the column is NOT NULL because nobody updated the migration. → Job throws.
- Or: the column is nullable but every grep for "who created this membership" misses system events because the report assumes `actor_user_id IS NOT NULL`.
- `resource_type` drift: "membership" vs "memberships" vs "Membership". The known issue from v1.1 retrospective ("Phase 06 audit user_id plumbing" deferred to v1.3) suggests this is an unfinished area.

**How to avoid:**
1. **Lock the audit event taxonomy in `app/core/audit.py` docstring extension before MB starts.** Add a formal frozenset of allowed `(action, resource_type)` tuples; `audit.emit` validates against it and raises in dev (`AUDIT_STRICT=True` env), warns in prod. Like the v1.1 RBAC byte-paritet pattern.
2. **Naming convention as Key Decision:**
   - `action`: snake_case verb-past — `membership_created`, `membership_expired`, `membership_cancelled`, `visit_created`, `visit_rejected_bot`, `visit_rejected_reception`.
   - `resource_type`: singular snake_case — `membership`, `membership_plan`, `visit`. Match the URL last segment.
   - `actor_user_id`: nullable; system events use `NULL` and add `actor_kind: 'system' | 'user'` payload field.
3. **Add a parametrised test** that for each new event name, asserts the row inserts AND a SELECT by `(action, resource_type)` returns it.
4. **Do NOT swallow audit emit failures in the service layer** — let them propagate; the co-transactional pattern (`audit.py:43-87`) means a failed audit is a failed mutation. v1.1 already does this correctly; just don't regress in MB/VB.

**Warning signs:**
- `SELECT DISTINCT action, resource_type FROM audit_log` shows naming variations.
- ARQ job logs `actor_user_id NOT NULL` IntegrityError on first prod run.
- Reports query filters on `resource_type = 'memberships'` and gets zero rows because actual data has `'membership'`.

**Phase to address:** **F** (lock taxonomy + add validation) → **MB / VB / AQ / BC** (each adds events to the frozenset).

---

### Pitfall 11: OpenAPI drift gate fails on every Pydantic schema add (camelCase / Optional)

**Severity:** HIGH (v1.1 F-03 reprise)

**What goes wrong:**
v1.1 had `expiresAt` drift between FE-handwritten contracts and backend OpenAPI (F-03). Phase 13 added the FE-side check. v1.2 adds 6+ new endpoints (memberships CRUD + visits + lifecycle); each is a new fight with the gate. Common failure modes:
- New schema forgets `model_config = ConfigDict(alias_generator=to_camel, populate_by_name=True)` → wire format drifts to snake_case → FE typegen breaks AND backend tests pass (because Python tests use the alias-by-default).
- `Optional[X]` (`Union[X, None]`) and `X | None` produce subtly different OpenAPI schemas in Pydantic v2 (`anyOf` vs `nullable: true`); mixing styles produces churn diffs in `openapi.json`.
- A new field added to a response: `paid_at: datetime | None = None`. OK. But if added to a *request* schema with `= None`, it becomes optional in the spec — and the FE passes `null` thinking it's setting a value, while backend treats absent and null differently.
- Ordering: a `ResponseModel` reorders fields between Python edits (e.g., reorganized for readability). OpenAPI byte-stable export (`scripts/export_openapi.py`) reflects the change → CI red.

**How to avoid:**
1. **Establish a `BackendSchemaBase`** in Phase F: `class BackendSchemaBase(BaseModel): model_config = ConfigDict(alias_generator=to_camel, populate_by_name=True, from_attributes=True)`. Every new schema inherits. Audit at end of phase.
2. **Style guide in conventions:** ALWAYS `X | None`, NEVER `Optional[X]`. Add ruff rule `UP007` (already enforced — confirm it's on for new files).
3. **Schemas alphabetize fields in `model_dump`** order via a custom test (or just manually keep them sorted) — eliminates the "I reorganized for readability" churn.
4. **Run `uv run python apps/backend/scripts/export_openapi.py && git diff apps/backend/openapi.json` BEFORE every commit in MB/VB** — not just CI. (The v1.1 retrospective lesson #3 — "Verify-on-the-wire, not verify-by-types".)
5. **Document the request-vs-response asymmetry:** request bodies should NOT have optional-with-default-None for fields that aren't truly optional inputs; response bodies CAN.
6. **For the FE side (admin-web):** never hand-write a contract type. Always import from the generated `@sportzal/api-client`'s `schema.d.ts`. Add an ESLint rule banning new `interface` declarations under `apps/admin-web/src/shared/api/contracts/` for memberships/visits.

**Warning signs:**
- CI red on `git diff --exit-code apps/backend/openapi.json` and the diff is field reordering noise (not a real change).
- FE typegen produces unexpected `_` characters in generated types — wire format drift.
- A field appears in API response with `null` but type-gen says it's required (= no `| null`).

**Phase to address:** **F** (BackendSchemaBase + style rules) → **HG** (add the ESLint rule + audit before milestone close).

---

### Pitfall 12: admin-web client-detail composition causes waterfall queries / stale-while-revalidate cross-pollution

**Severity:** MEDIUM

**What goes wrong:**
Client-detail page now needs `getClient` + `listMemberships(clientId)` + `listVisits(clientId, limit=10)`. Naive code:
```ts
const client = useQuery(clientKeys.byId(id), () => api.clients.get(id))
const memberships = useQuery(membershipKeys.byClient(id), () => api.memberships.listByClient(id), { enabled: !!client.data })
const visits = useQuery(visitKeys.recentByClient(id), () => api.visits.recent(id), { enabled: !!memberships.data })
```
Three sequential round trips (700ms instead of 250ms). Worse: navigating from `/clients/A` → `/clients/B` shows A's memberships briefly under B's name due to stale-while-revalidate when keys aren't tightly scoped.

**Why it happens:**
- TanStack Query's default is parallel-by-default if all queries are mounted together — the bug above is `enabled: !!client.data` introducing an artificial dependency.
- v1.1 only had `clients` data on this page; multi-domain composition is new.
- query-key factories live per-feature. If `membershipKeys.byClient(id)` accidentally collides with `membershipKeys.list()` (e.g., wrong serialization of `id` to string) → cache pollution.

**How to avoid:**
1. **All three queries are independent: fire them in parallel.** Drop `enabled: ...` chains. The `client_id` is from the URL param, available immediately.
2. **Use `route.loader` to `Promise.all` the three `queryClient.ensureQueryData` calls** (per v1.1 convention `src/app/router.ts`). This pre-warms the cache before the route component renders → zero waterfall.
3. **Tight key factories:** `membershipKeys.byClient = (id: ClientId) => ['memberships', 'byClient', id] as const`. Don't reuse `membershipKeys.list()` for "all of one client".
4. **Route param invalidation:** when `id` changes, the queries unmount/remount with the new key. As long as keys are correct this prevents cross-pollination.
5. **Optimistic mutation fan-out:** if reception adds a membership, invalidate `[memberships, byClient, id]` AND `[clients, 'byId', id]` (in case the client object embeds counts). Don't blanket-invalidate `['memberships']`.

**Warning signs:**
- Network tab shows three sequential requests instead of three parallel.
- Quick navigation between clients flashes the wrong client's memberships.
- React Query devtools show cache entries with object keys instead of stable serialized keys.

**Phase to address:** **FE** (loader pattern + key factories review).

---

### Pitfall 13: Reception manual check-in UX edge cases (expired-today, multiple phone matches, already-checked-in)

**Severity:** MEDIUM

**What goes wrong:**
- Client's membership expires today (last day inclusive). Reception clicks "Check in" — does it 200 or 409? If 409 the client is angry ("у меня же сегодня последний день!"). If 200 but the daily ARQ job already ran and flipped them to `expired`, what does reception see?
- Reception types phone "+7903" (a prefix), three clients match. The list UI shows them, reception clicks one. But what if two clients have similar names and reception picks wrong?
- Bot already checked in this client 5 min ago. Reception clicks "Check in" — gets 409 "уже отметился сегодня". Confusing without context. Reception should see the existing visit (channel `telegram_bot`) and skip.

**Why it happens:**
- Time-zone of "today" (Pitfall 5) interacts with membership end_date (Pitfall 2). If end_date is inclusive (Pitfall 2 recommendation) and gym_date = end_date, check-in MUST succeed. Implementation must agree.
- Reception is a single-screen flow; no time for "did you mean..." lists.
- The 409 from Pitfall 5's UNIQUE constraint is correct backend behavior but bad UX without context.

**How to avoid:**
1. **Inclusive end_date semantics (Pitfall 2 decision) means: visit on `gym_date == end_date` is valid.** Backend test: create membership ending today, attempt check-in, expect 201.
2. **Reception search returns top 5 matches** with full name + phone last 4 digits + birthday. Click is unambiguous.
3. **Reception "check-in" page does a `GET /visits?clientId=X&gymDate=today` first** before showing the button. If a visit exists, show it (with channel badge "Telegram bot" / "Reception") and disable the button. No redundant 409.
4. **For "membership expired today via daily job":** the daily ARQ job runs at 03:05 local → at 04:00 the membership is already `expired`. If end_date is inclusive, it shouldn't have been expired. Re-read Pitfall 4: the SQL filter must be `end_date < CURRENT_DATE AT TIME ZONE 'Europe/Moscow'` (strict less-than, not `<=`).
5. **Russian error copy specific:**
   - 409 already today → `"Клиент уже отмечен сегодня в HH:MM (Telegram-бот / администратор Имя)"`.
   - 409 no active membership → `"Нет активного абонемента. Продайте новый или переоформите."` (with action button).
   - 409 outside hours (manual reception bypass option for owner only?) → owner can override; reception cannot.

**Warning signs:**
- Membership ending today flips to `expired` overnight and last-day check-in fails.
- Reception staff phone-call thread: "I keep getting 'already checked in', but I just searched the client".
- Multiple phone-prefix matches → wrong client gets the visit.

**Phase to address:** **VB** (backend semantics) + **FE** (reception UX flow review with single-screen demo).

---

### Pitfall 14: ARQ job has no structlog request_id correlation → observability gap

**Severity:** MEDIUM

**What goes wrong:**
The web tier uses `RequestIdMiddleware` to bind `request_id=<uuid4>` to structlog contextvars. Logs across one HTTP request share the id. The `expire_memberships` job has no such middleware, so its log lines are flat: 100 expired memberships → 100 `membership_expired` log events with no shared correlator. Debugging "which job emitted these?" requires timestamp guessing.

**Why it happens:**
- ARQ doesn't have a request-id concept (no requests).
- Engineers typically don't add a `job_id` because "it's just a cron".
- structlog `contextvars` is per-task; ARQ's worker reuses the asyncio task between jobs by default → contextvars can leak across runs.

**How to avoid:**
1. **`on_job_start` ARQ hook** binds `job_id=uuid4()`, `job_name=<func name>`, `cron_id=<short>` to structlog contextvars. `on_job_end` clears them. Document in `app/workers/arq_app.py` docstring.
2. **Mirror what `RequestIdMiddleware` does** for HTTP. Reference `core/middleware.py` for the pattern.
3. **All audit events emitted from a job carry the job_id in payload** (extra field).
4. **Add a CI test:** run job twice with patched clock, parse stdout JSON logs, assert all events from one run share a `job_id` and the two runs have different `job_id`s.

**Warning signs:**
- Structlog output for cron job has no `job_id` field.
- Two cron runs interleave in logs, indistinguishable.
- Audit log query "how many memberships expired in this run?" requires joining on timestamp window.

**Phase to address:** **AQ** (ARQ scaffolding phase).

---

### Pitfall 15: `membership.status` state machine has implicit holes (cancelled→active reactivation, expired→cancelled)

**Severity:** MEDIUM

**What goes wrong:**
v1.2 spec: `status active|expired|cancelled`. The transitions written are:
- `active → expired` (ARQ daily)
- `active → cancelled` (manual owner)

Implicit / missing:
- Can `expired → cancelled` happen? (Reception wants to mark a never-used expired membership as "voided" for refund accounting.)
- Can `cancelled → active`? (Reactivation after refund-reversal.) Probably no for v1.2 — but if not enforced, an UPDATE could do it silently.
- Can `expired → active`? (Membership extended.) Also probably no for v1.2.

Without enforcement, future bugs slip in via SQL or service typos.

**How to avoid:**
1. **Lock the state machine in Key Decisions:**
   - `active → expired` (system, ARQ): `end_date < today_msk`
   - `active → cancelled` (owner manual)
   - All other transitions: forbidden in v1.2. Document with examples.
2. **Service layer enforces:** `cancel_membership` checks current status `== 'active'` else raises `MembershipNotActiveError`. The ARQ update SQL filters `WHERE status = 'active'`. No path produces `expired → cancelled` etc.
3. **Add a state-transition unit test matrix:** for every `(from, to)` pair, assert allowed/denied.
4. **Postgres CHECK constraint** on `status IN ('active', 'expired', 'cancelled')` to prevent typo-corruption. Cheap.
5. **For audit clarity:** distinct events for `membership_expired` (system) vs `membership_cancelled` (owner); never collapse.

**Warning signs:**
- A SQL migration or hotfix manually flips status; no audit row.
- Owner asks "can I un-cancel?" — answer requires a Key Decision not a code dive.
- `audit_log` has a `membership_status_changed` event with no `from`/`to` — under-specified.

**Phase to address:** **MB** (model + service) + Key Decisions update.

---

## Technical Debt Patterns

| Shortcut | Immediate Benefit | Long-term Cost | When Acceptable |
|----------|-------------------|----------------|-----------------|
| Skip `BackendSchemaBase`, copy `model_config` per file | Less indirection | OpenAPI drift gate fights every new schema, F-03 reprise | Never — Phase F template work is < 1h |
| App-layer "1/day" check instead of UNIQUE INDEX | Faster Phase VB | Race-condition double-checkin in production | Never — the index is one Alembic line |
| ARQ job emits audit per row without correlation id | Less code | Unable to attribute events to a job run | Never — `job_id` is 5 lines |
| Embed `MembershipPlan.price` via join, no snapshot | Less migration churn | Plan edits rewrite history → financial integrity gone | Never — the snapshot column is one migration line |
| Hand-write FE memberships contract types instead of using generated `schema.d.ts` | Faster initial FE wiring | F-03 reprise — drift inevitable | Never — codegen is already wired in v1.1 |
| Skip `gym_date` generated column, compute in app | Simpler model | UNIQUE constraint can't enforce; race window real | Never — Postgres GENERATED is mature |
| Bot DM with rich error reasons | Better UX for legit user | Account-state oracle for attackers | When DM is gated behind a fresh OTP — out of v1.2 scope |
| Use `relativedelta(months=N)` for plan duration | Reads nicely | Jan 31 month boundary silently broken | Never — schema is days-only |
| Reception UI shows 409 toast on already-today | Easy implementation | Confusing — reception doesn't know bot already did it | Until VB+FE both ship; HG phase fixes |
| Defer audit event taxonomy lock to "we'll fix it later" | No blocking work in F | v1.1 retrospective explicitly listed this debt; will compound | Until next milestone (v1.3) — accept if v1.2 schedule pressure, document in retrospective |

---

## Integration Gotchas

| Integration | Common Mistake | Correct Approach |
|-------------|----------------|------------------|
| Telegram Bot API (ptb-22) | Adding `/checkin` handler with module-level Application or direct `app.modules.visits` import | Extend `HandlerContext` NamedTuple (handlers.py:35); register handler list in `telegram_bot.py:67` (`handlers=[("start", start_handler), ("checkin", checkin_handler)]`) |
| ptb-22 update dedup | Trusting in-memory `update_id` deduplication across worker restarts | Mirror v1.1 D-20 pattern: track recent `update_id` in Redis with TTL=1h; emit `bot_replay_attempt` audit on duplicate |
| ARQ cron on docker-compose restart | Assuming `unique=True` prevents all double-runs | Idempotent SQL (`UPDATE ... WHERE status='active' RETURNING id`) + single transaction wrapper; `unique=True` is necessary but not sufficient |
| Postgres `Europe/Moscow` TZ | Using `NOW()` (UTC) for `gym_date` calculation | `NOW() AT TIME ZONE 'Europe/Moscow'` and store generated column. Russia has had no DST since 26 Oct 2014 (UTC+3 stable) — but tzdata still encodes historical transitions, never use TZ-naive datetimes for gym_date |
| Pydantic v2 `Optional` vs `\| None` | Mixing styles produces `anyOf` vs `nullable: true` churn in OpenAPI | Always `X \| None`, never `Optional[X]`. ruff `UP007` enforces |
| Alembic migration with `gym_date` GENERATED ALWAYS | Generated columns sometimes need explicit cast | Use `(checked_in_at AT TIME ZONE 'Europe/Moscow')::date` and test the migration on real Postgres 16 (not just SQLite) |
| import-linter cross-module | `from app.modules.X import Y` at runtime in another module | Protocol in `core` + composition-root registration (D-24 / `register_user_loader` precedent) |
| TanStack Query loader for client-detail | `enabled: !!previousQuery.data` chain | `route.loader: async () => Promise.all([queryClient.ensureQueryData(...), ...])` |
| OpenAPI export | Field reordering between dev iterations | Stable field order; consider `model_config` ordered or test that asserts shape stable |
| Redis for ARQ + Redis for sessions + Redis for replay-dedup | Key collisions across uses | Document key prefixes: `arq:*`, `sz:session:*`, `sz:bot:replay:*` |

---

## Performance Traps

Single-zal scope means small numbers (< 1k clients, < 500 visits/day, < 100 memberships active). Most performance "traps" are actually correctness traps. Listed for completeness.

| Trap | Symptoms | Prevention | When It Breaks |
|------|----------|------------|----------------|
| ARQ job audit-log explosion (one row per affected membership) | `audit_log` table grows by 100s of rows on a single run; queries slow | Bulk-aggregate event for runs > 200; per-row only at structlog INFO | Never at single-zal scale; matters at 10+ zals |
| ILIKE search on memberships history without `pg_trgm` | Search takes > 1s on > 10k memberships | Reuse v1.1 `pg_trgm` GIN pattern from clients (`gin_trgm_ops` index on lower(plan_name_snapshot) if searched) | Never at v1.2 scale (single zal) — defer index until search shipped |
| Visits page fetches all visits, paginate in JS | Slow on > 1k visits | Server-side `?limit=20&offset=0` with same `{items,total,page,pageSize}` envelope | Around 500 visits per client — i.e., year-2 of operation |
| `expire_memberships` sequential UPDATE on each row | Job takes seconds-to-minutes if O(active memberships) is high | Single `UPDATE ... WHERE status='active' AND end_date < ... RETURNING id` | At 10+ zals scale |
| FE fan-out on client-detail (Pitfall 12) | Page TTI > 1s | Parallel queries via route.loader | Already broken if waterfall; user-perceived |

---

## Security Mistakes

| Mistake | Risk | Prevention |
|---------|------|------------|
| Bot DM leaks account state on /checkin failure | Account-existence + membership-state oracle for attackers | Generic Russian message + audit reason server-side (Pitfall 8) |
| Visits search ILIKE without escape | PII over-exposure (CR-01 reprise) | Use central `_escape_like_pattern`, parametrised PII test (Pitfall 6) |
| Bot replay (worker restart) | Double-checkin via update_id replay | Redis-backed update_id dedup (Pitfall 9) + DB UNIQUE constraint (Pitfall 5) |
| Telegram chat-id not re-validated per check-in | Chat-id transfer / shared device → friend checks in | Accept residual risk for v1.2; document; consider daily-OTP for v1.3 (Pitfall 9) |
| Owner-only manual cancel exposed to reception | Reception cancels memberships unauthorized | RBAC `OWNER_ONLY` table addition; route-introspection guard catches it (v1.1 pattern) |
| Audit event missing `actor_kind` distinguishing system/user | Forensics harder; can't filter "who did this" | Add `actor_kind: 'system' \| 'user'` payload field (Pitfall 10) |
| Plan edits not audited | Owner manipulates prices, no trail | `membership_plan_updated` audit event with `previous_*` fields, like clients pattern |
| ARQ job exception silently swallowed | Memberships fail to expire; no alarm | `on_job_end` hook checks for failure flag; structlog ERROR + audit event |
| `gym_date` race-condition allows midnight check-in | 23:59 + 00:01 → 2 visits same gym-day | DB-generated column + UNIQUE on `(client_id, gym_date)` (Pitfall 5) |

---

## UX Pitfalls

| Pitfall | User Impact | Better Approach |
|---------|-------------|-----------------|
| Reception 409 "already checked in today" without context | Reception confused, calls support | Pre-fetch today's visit; show existing check-in (channel badge); disable button |
| Bot success DM contains "Welcome!" + name + plan | PII exposure if friend has device | "✅ Отмечено" only; rich confirmation in admin-web |
| Bot failure DM: "membership expired on 12 Mar" | Account-state oracle | Generic "обратитесь к администратору" (Pitfall 8) |
| Membership end_date shown without timezone | Customer thinks expires midnight UTC ≠ midnight Moscow | "до 23:59 12 марта" copy + Europe/Moscow TZ assumption documented |
| Plan edit retroactively changes price on history page | "Why did my old membership cost change?" support | Snapshot column on Membership (Pitfall 3) |
| Last-day check-in rejected | "Сегодня же последний день!" anger | Inclusive end_date + ARQ filter `end_date < today` (strict) (Pitfall 13) |
| Phone-prefix search → wrong client picked | Wrong client gets the visit/membership | List view with full name + phone last 4 + birthday; click to confirm |
| Reception self-service for cancellation | Reception cancels without owner approval | `OWNER_ONLY` RBAC + UI hides button; consistent with v1.1 |
| Russian copy translated by AI agent without review | "Sounds wrong" / corporate-speak | Owner reviews all Russian copy; copy locked in REQUIREMENTS.md or Key Decisions |
| Memberships history page sorts by random key | "I can't find when I started" | Sort by `start_date DESC`, tie-break `created_at DESC` |

---

## "Looks Done But Isn't" Checklist

- [ ] **Membership creation:** Often missing `await session.commit()` — verify with multi-request live runbook (Phase 12.1 reprise prevention)
- [ ] **Visit creation:** Often missing UNIQUE INDEX on `(client_id, gym_date)` — verify by spawning 10 concurrent test requests for the same client; expect exactly 1×201 + 9×409
- [ ] **Membership snapshot:** Often missing `price_kopecks_snapshot` / `duration_days_snapshot` columns — verify by editing plan price and re-fetching old membership; price must NOT change
- [ ] **ARQ job idempotency:** Often missing — verify by running cron callable twice with patched clock; second run must emit zero new audit rows
- [ ] **ILIKE escape:** Often forgotten in new modules — verify with parametrised PII test (`?q=%`, `?q=_`, `?q=\\` → 0 leaked rows)
- [ ] **Bot /checkin error messages:** Often too revealing — verify all DMs go through one constant string; reasons live only server-side
- [ ] **import-linter:** Often broken silently — `uv run lint-imports` MUST be green at every commit
- [ ] **OpenAPI drift gate:** Often skipped locally — `uv run python apps/backend/scripts/export_openapi.py && git diff --exit-code` MUST be green at every commit
- [ ] **FE generated types:** Often replaced with hand-written contracts — grep `apps/admin-web/src/shared/api/contracts/` for new memberships/visits files; should not exist
- [ ] **Audit event taxonomy:** Often inconsistent — verify with `SELECT DISTINCT action, resource_type FROM audit_log` query; cross-check against locked frozenset
- [ ] **Russian copy:** Often AI-generated without human review — owner sign-off required for any user-visible string
- [ ] **State machine:** Often under-specified — every (status_from, status_to) pair must have an explicit allowed/denied test
- [ ] **Inclusive end_date semantics:** Often inconsistent between ARQ filter and visit-creation guard — backend test for "membership ending today, check-in succeeds, expires next day"
- [ ] **gym_date stored generated column:** Often replaced with app-computed value — verify Alembic migration uses `GENERATED ALWAYS AS (...) STORED`
- [ ] **HandlerContext extension:** Often replaced with direct module import — verify `telegram_bot.py:58-62` shape; `app.modules.visits` should not appear in any `from` line outside HandlerContext-construction
- [ ] **Reception "already today" UX:** Often shows raw 409 toast — verify pre-fetch + disabled button with channel badge
- [ ] **Cron job structlog correlation:** Often missing `job_id` — verify two cron runs with patched clock have distinct `job_id` and all events within one run share it

---

## Recovery Strategies

| Pitfall | Recovery Cost | Recovery Steps |
|---------|---------------|----------------|
| Service missing `await session.commit()` | LOW (1 line) | Add commit, redeploy, re-run failed ops manually if any. v1.1 Phase 12.1 took < 1h |
| Membership snapshot missing | HIGH | Backfill migration: copy current `MembershipPlan.price_kopecks` to `Membership.price_kopecks_snapshot` for existing rows (best-effort; loses any prior plan-edit history). Add NOT NULL after backfill. Document data-loss in retrospective |
| `1/day` UNIQUE missing, duplicates exist | MEDIUM | Migration: dedup by `(client_id, gym_date)` keeping earliest `checked_in_at`; add UNIQUE; soft-delete the dropped rows for audit trail |
| ARQ job double-emitted audit events | MEDIUM | Cleanup query: `DELETE FROM audit_log WHERE action='membership_expired' AND id NOT IN (SELECT MIN(id) FROM audit_log GROUP BY resource_id, payload->'gym_date')`. Reset job idempotency invariant |
| ILIKE escape forgotten in new module | LOW (1 import) | Add escape via `core/sql.py` helper; PII test catches it; deploy. Same as v1.1 CR-01 fix |
| import-linter broken | LOW | Refactor to HandlerContext / Protocol pattern; should never reach prod (CI gate) |
| OpenAPI drift in production | MEDIUM | Backend revert or FE codegen + redeploy; api-client version bump; admin-web rebuild |
| Bot leaks account state | MEDIUM | Replace DM strings with generic; redeploy bot worker; document in audit |
| Bot replay double-checkin | MEDIUM | Add Redis update_id dedup; DELETE duplicate visits keeping earliest; backfill audit; deploy |
| Membership state-machine corruption (illegal transition shipped) | HIGH | Manual SQL fix per case + audit row; add CHECK constraint; add state-machine tests retrospectively |
| `relativedelta` end_date drift | HIGH | Recompute end_date for all affected memberships (`start_date + duration_days_snapshot - 1`); customer notification if shortened |
| Russian copy embarrassment | LOW | Owner edits, redeploy. Frontend bundle + bot worker only |

---

## Pitfall-to-Phase Mapping

| Pitfall | Severity | Prevention Phase | Verification |
|---------|----------|------------------|--------------|
| 1. Service missing `await session.commit()` | BLOCKER | F | AST gate `scripts/check_service_commits.py` + multi-request live runbook + new-session integration test |
| 2. End_date calendar math | HIGH | F → MB | Property test (hypothesis) over `(start_date, duration_days)` matrix |
| 3. Snapshot pricing missing | BLOCKER | MB | Plan-edit + re-fetch test asserts price unchanged |
| 4. ARQ job not idempotent | HIGH | AQ | Patched-clock double-run test; assert second run has zero new audit rows |
| 5. Visit `1/day` race window | BLOCKER | F → VB | Concurrent-request test (10 parallel → 1×201 + 9×409); inspect Alembic migration for UNIQUE INDEX |
| 6. ILIKE escape forgotten | HIGH | F → HG | Parametrised PII test over every search endpoint |
| 7. import-linter Protocol drift | HIGH | F → VB → BC | `uv run lint-imports` green at every commit + pre-commit hook |
| 8. Bot reveals account state | HIGH | BC | Russian copy review by owner + DM-content unit test (no dynamic data) |
| 9. Bot replay / friend fraud | HIGH | BC | Redis update_id dedup + Key Decisions documenting accepted residual risk |
| 10. Audit log naming drift | HIGH | F → MB/VB/AQ/BC | Frozenset validation in `audit.py`; SELECT DISTINCT test |
| 11. OpenAPI drift on schema add | HIGH | F → HG | `BackendSchemaBase` template + pre-commit `openapi.json` diff check |
| 12. FE waterfall queries / cache cross-pollution | MEDIUM | FE | Network-tab parallel verification + key-factory review |
| 13. Reception manual check-in UX | MEDIUM | VB → FE | Edge-case integration tests: expired-today, already-today, multi-phone-match |
| 14. ARQ no request_id correlation | MEDIUM | AQ | Two-run structlog assertion: distinct `job_id`, all events within run share it |
| 15. State machine holes | MEDIUM | MB | Transition matrix unit test + Postgres CHECK constraint |

---

## Sources

**Repository evidence (HIGH confidence):**
- `.planning/RETROSPECTIVE.md` — v1.1 incidents (Phase 12.1 commit bug, CR-01 LIKE-escape, F-03 contract drift, Phase 7 underplanning, P05 ReUI 404)
- `.planning/PROJECT.md` — Key Decisions table (D-02, D-03, D-06, D-09, D-11, D-24); v1.2 spec
- `.planning/MILESTONES.md` — v1.1 known deferred items (audit `user_id` plumbing)
- `apps/backend/app/modules/clients/repository.py` — `_escape_like_pattern` precedent (CR-01)
- `apps/backend/app/modules/clients/service.py` — explicit `await session.commit()` pattern (Phase 12.1 closure)
- `apps/backend/app/workers/telegram_bot.py` — D-06 documented exception, HandlerContext shape
- `apps/backend/app/integrations/telegram/handlers.py` — Protocol-style indirection precedent for /checkin
- `apps/backend/app/core/audit.py` — locked event-name discipline + frozenset opportunity
- `apps/backend/app/workers/arq_app.py` + `scheduler.py` — empty-skeleton state of ARQ (no precedent)
- `apps/backend/.importlinter` — three contracts that v1.2 must not break

**External references (MEDIUM-HIGH confidence):**
- [ARQ docs — index](https://arq-docs.helpmanual.io/) — `cron_jobs`, `unique=True`, `keep_cronjob_progress`
- [ARQ issue #193 — Cron job scheduling behaviour](https://github.com/samuelcolvin/arq/issues/193) — overlap semantics
- [The Inner Workings of: Arq](https://threeofwands.com/the-inner-workings-of-arq/) — idempotency requirements
- [Wikipedia — Time in Russia](https://en.wikipedia.org/wiki/Time_in_Russia) — Russia abolished DST 26 Oct 2014; Europe/Moscow has been stable UTC+3 since
- [timeanddate.com — Russia returns to permanent Standard Time](https://www.timeanddate.com/news/time/russia-abandons-permanent-summer-time.html) — confirms no DST risk for `Europe/Moscow` post-2014

**Confidence note:** All v1.2-specific architectural pitfalls (Pitfalls 1, 5, 6, 7, 10, 11) are HIGH confidence — they are direct continuations of v1.1 documented incidents. ARQ-specific pitfalls (4, 14) are HIGH confidence on the patterns (idempotency, correlation id) but MEDIUM on exact ARQ API behaviours (e.g., precise behaviour of `keep_cronjob_progress` on docker restart was inferred from issue tracker, not validated end-to-end). Bot anti-fraud pitfalls (8, 9) are HIGH on the threat model and MEDIUM on the recommended mitigations (single-zal scope tolerates residual risk; v1.3 may revisit).

---
*Pitfalls research for: Sportzal v1.2 — Memberships + Visits + ARQ scheduled jobs + Telegram bot /checkin*
*Researched: 2026-05-07*

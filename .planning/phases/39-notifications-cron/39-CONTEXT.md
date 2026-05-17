# Phase 39: Notifications + Cron - Context

**Gathered:** 2026-05-17
**Status:** Ready for planning
**Mode:** `--auto` (Claude auto-selected recommended defaults for every gray area; user may override any D-39-NN before `/gsd-plan-phase 39` consumes this file)

<domain>
## Phase Boundary

Phase 39 lights up the **outbound notification surface** for v1.5 Bookings on top of the Phase 38 booking model. It does NOT change the booking FSM, the bookings/schedule HTTP contract, or the v1.4 PT-package/PT-session integration. Three concrete deliverables:

1. **Synchronous Telegram DMs** on booking-create + booking-cancel (in-request, fire-and-forget — failures log WARNING and do not affect the HTTP response).
2. **One new table** (`booking_notifications`, Alembic 0020) acting as the cron-idempotency ledger for 24h reminders only.
3. **Two new ARQ crons** registered on `WorkerSettings.cron_jobs` — `mark_no_show_bookings` (23:10 MSK, DB-only batch UPDATE) and `send_booking_reminders` (06:35 MSK, multi-session DM loop).

Deliverable scope is exactly the 10 v1.5 requirements `NOTIFY-01..05 + CRON-01..05`.

**What ships:**

1. **`apps/backend/app/modules/bookings/notifications.py`** — NEW module: 4 locked Russian DM templates (`BOOKING_CONFIRMED_DM`, `BOOKING_CANCELLED_BY_CLIENT_DM`, `BOOKING_CANCELLED_BY_OWNER_DM`, `BOOKING_REMINDER_24H_DM`) + 1 anti-oracle constant (`_BOT_BOOK_DENIED_DM`) + a `render_*_dm(client_name, trainer_name, slot_start_msk)` helper per template.
2. **Alembic 0020 `booking_notifications`** — single-table migration: `id UUID PK`, `booking_id UUID NOT NULL FK bookings(id) ON DELETE RESTRICT`, `kind TEXT NOT NULL CHECK IN ('reminder_24h')`, `sent_at TIMESTAMPTZ NOT NULL DEFAULT now()`. UNIQUE `(booking_id, kind)` — `uq_booking_notifications_booking_kind`. **No `telegram_chat_id` snapshot column** (D-39-03 below).
3. **`apps/backend/app/modules/bookings/models.py`** — APPEND `BookingNotification` ORM class mirroring `MembershipNotification` shape (NO `SoftDeleteMixin`; the UNIQUE is the source of truth).
4. **`apps/backend/app/modules/bookings/service.py`** — replace the two Phase 38 `TODO Phase 39` stubs in `create_booking` and `cancel_booking` with real fire-and-forget DM sends via `_dispatch_booking_dm(...)` helper (D-39-04 below). Also add a `_send_booking_reminders(session_factory, *, bot, sender, notifications_module) -> int` SVC001-exempt cron helper (mirror v1.3 `_send_expiring_notifications`).
5. **`apps/backend/app/modules/schedule/service.py`** — replace the Phase 38 slot-cancel-cascade no-op with a fire-and-forget `BOOKING_CANCELLED_BY_OWNER_DM` send for every cancelled booking in the cascade (NOTIFY-04 final clause).
6. **`apps/backend/app/workers/scheduled/mark_no_show_bookings.py`** — NEW worker file: pure DB-only batch UPDATE cron, single-session (mirror `expire_memberships.py`), no Telegram I/O.
7. **`apps/backend/app/workers/scheduled/send_booking_reminders.py`** — NEW worker file: multi-session DM loop (mirror `send_expiring_notifications.py`).
8. **`apps/backend/app/workers/__init__.py`** — APPEND both new callables to `WorkerSettings.functions` and append two `cron(...)` entries to `WorkerSettings.cron_jobs` in order: `expire_memberships(03:05) → send_expiring_notifications(03:15) → expire_pt_packages(03:25) → send_booking_reminders(03:35) → mark_no_show_bookings(20:10)` (CRON-02 explicit "after `expire_pt_packages` 06:25" + CRON-01 evening tick).
9. **`apps/backend/scripts/run_no_show_cron_once.py`** + **`apps/backend/scripts/run_booking_reminders_once.py`** — operator one-shot runners (mirror `run_expiring_cron_once.py` including TM-29-02 + TM-29-03 safety gates + the REG-29-04 eager-import block).
10. **Audit emit** — `booking_no_show` payload schema (`BookingNoShowPayload`) is **already locked from Phase 37 INFRA-24** (`app/core/audit_payloads.py:410-424` + registry line 462). Phase 39 does NOT add new audit events; it only adds callsites for the existing `booking_no_show` event from inside `mark_no_show_bookings`. `booking_reminder_sent` is NOT a separate audit event — the `booking_notifications` row IS the audit record (mirror v1.3 D-27 — `membership_notifications` is not double-emitted into `audit_log`).
11. **Tests** — unit tests for the 4 template renderers; service-level integration tests for `create_booking_sends_dm`, `cancel_booking_sends_correct_template_per_actor_role`, and `slot_cancel_cascade_sends_owner_dm`; cron tests `test_no_show_cron_marks_overdue_and_emits_audit`, `test_no_show_cron_idempotent`, `test_reminders_cron_inserts_idempotency_row`, `test_reminders_cron_skips_403_blocked`, `test_reminders_cron_skips_unlinked_client`; ARQ wiring tests `test_worker_settings_cron_resolution` (the existing test already enforces the invariant — Phase 39 just adds the two new function names to the assertion fixture).

**Explicitly out of scope for Phase 39** (lands in Phase 40+):

- Telegram bot `/book` command, `book_callback_handler`, InlineKeyboard with `BK:{slot_uuid}` callback_data (BOT-01..05 → Phase 40).
- `HandlerContext.bookings_service` field (BOT-05 → Phase 40).
- Redis update_id dedup `sz:bot:update:{update_id}` (BOT-04 → Phase 40).
- `_BOT_BOOK_DENIED_DM` **string is created here** (NOTIFY-02), but the **anti-oracle bot flow** that emits it is Phase 40. Phase 39 ships the constant + a smoke test that the constant exists and is non-empty; Phase 40 wires it into the callback handler.
- OpenAPI byte-stable regen + admin-web wiring (HANDOFF-01/02 → Phase 40).
- 6 operator curl scenarios + Telegram sandbox smoke (VER-05/06 → Phase 40).
- Milestone verification log entries (VER-08 → Phase 40).
- Manual `POST /bookings/{id}/no_show` admin endpoint — Phase 39 ships cron-only per C-10; no HTTP path.
- Reverse `no_show → confirmed` reopen flow — out of scope per PITFALLS Pitfall 9.

</domain>

<decisions>
## Implementation Decisions

All C-01..C-15 milestone-level decisions are locked in `.planning/REQUIREMENTS.md` and are NOT re-decided here. All D-37-NN Phase 37 bedrock decisions and all D-38-NN Phase 38 implementation decisions are locked in their respective CONTEXT.md files. The decisions below are Phase 39 implementation-level choices made during this auto-discuss pass.

### Module & Plan Structure

#### D-39-01 — Plan breakdown: 4 atomic plans grouped by deliverable type
Phase 39 ships as **4 commit-sized plans** (mirroring v1.3 Phase 27 cadence — fewer plans than Phase 38 because there is no parallel module work and the surface is narrower). Goal-back from the 4 ROADMAP success criteria:

1. **39-01 notifications-module-and-copy** — NEW `app/modules/bookings/notifications.py` (4 DM templates + `_BOT_BOOK_DENIED_DM` anti-oracle constant + 4 `render_*_dm(...)` helpers). Unit tests for every placeholder substitution. **Owner copy-lock sign-off** captured at plan close (mirror v1.3 D-27-OWNER-COPY-LOCK). No model / service / worker code in this plan — it is pure copy + render. Covers NOTIFY-01, NOTIFY-02.
2. **39-02 send-on-create-and-cancel** — extend `bookings/service.py:create_booking` + `bookings/service.py:cancel_booking` + `schedule/service.py:cancel_slot` (booked→cancelled cascade) with synchronous fire-and-forget DM sends via a new private `_dispatch_booking_dm(booking, *, template, bot, sender, copy_module)` helper. Failures (403/blocked/transport) WARNING-log + swallow — never surface to HTTP. No `booking_notifications` row inserted (confirmation + cancellation are once-off events per NOTIFY-03). Covers NOTIFY-03, NOTIFY-04.
3. **39-03 no-show-cron** — Alembic 0020 (NO — see D-39-12 below: 0020 ships with plan 39-04 because both crons depend on the table existing; no, revised — **0020 ships in 39-03 because no-show cron does NOT use `booking_notifications` but Alembic linear history requires we land 0020 once, and it's cleaner to land it alongside the model class which the reminder cron in 39-04 then consumes; see Plan-ordering note below**) + `BookingNotification` ORM model APPEND to `bookings/models.py` + NEW `app/workers/scheduled/mark_no_show_bookings.py` (single-session DB-only batch UPDATE per D-39-06) + APPEND `mark_no_show_bookings` to `WorkerSettings.functions` and `cron_jobs` + NEW `apps/backend/scripts/run_no_show_cron_once.py` (mirror `run_expiring_cron_once.py` including TM-29-02 + TM-29-03 + REG-29-04 eager-import). Integration tests `test_no_show_cron_marks_overdue_and_emits_audit` + `test_no_show_cron_idempotent`. Covers NOTIFY-05 (table only), CRON-01, CRON-04. (CRON-03 partially — only one of the two new cron entries lands here.)
4. **39-04 reminder-cron** — NEW `app/workers/scheduled/send_booking_reminders.py` (multi-session per-send DM loop per D-39-06; consumes a `_send_booking_reminders(session_factory, *, bot, sender, notifications_module)` SVC001-exempt helper added to `bookings/service.py`) + APPEND `send_booking_reminders` to `WorkerSettings.functions` and `cron_jobs` + NEW `apps/backend/scripts/run_booking_reminders_once.py` (mirror 39-03's runner). Integration tests `test_reminders_cron_inserts_idempotency_row`, `test_reminders_cron_idempotent`, `test_reminders_cron_skips_403_blocked`, `test_reminders_cron_skips_unlinked_client`. Covers CRON-02, CRON-03 (second cron entry + the `on_startup` resolution invariant test now sees both names), CRON-05.

**Why 4 plans (not 3, not 5):** plans 39-01 (copy lock) and 39-02 (synchronous send) have completely different surfaces — copy is text + unit tests; send is service-glue + integration tests with the existing booking flow. Plan 39-03 (no-show DB cron) is single-session and pure-DB; plan 39-04 (reminder DM cron) is multi-session with Telegram I/O. The two crons share no code beyond `WorkerSettings.cron_jobs` registration, so combining them would create a 4-deliverable plan twice the review burden. Splitting matches v1.3 Phase 27's plan rhythm (template plan + cron plan + send-wiring plan).

**Parallel-eligibility (recommended waves for `/gsd-execute-phase`):**
- **Wave 1 (alone):** 39-01 — copy lock must land before anything else can `from app.modules.bookings.notifications import BOOKING_CONFIRMED_DM`. Pure text, no DB.
- **Wave 2 (parallel after 39-01):** 39-02 (service-glue, no migration), 39-03 (Alembic 0020 + no-show cron, no Telegram). Different files entirely: 39-02 touches `bookings/service.py` + `schedule/service.py`; 39-03 touches `bookings/models.py` + new worker file + new script + `workers/__init__.py`. Both import from `bookings/notifications.py` (39-01 dep). 39-03 lands the `BookingNotification` ORM class which 39-04 consumes — see Wave 3.
- **Wave 3 (serial after 39-03):** 39-04 — reminder cron depends on `BookingNotification` ORM class + Alembic 0020 from 39-03. Touches `bookings/service.py` (39-02 conflict zone: BOTH 39-02 and 39-04 add code to `bookings/service.py`). To avoid the wave-2 / wave-3 file conflict on `bookings/service.py`, **plan 39-04 MUST land serially after both 39-02 AND 39-03** — i.e., 39-04 is alone in Wave 3.

| Wave | Plans | Reason |
|---|---|---|
| 1 | 39-01 | Copy templates must exist before any consumer |
| 2 | 39-02, 39-03 | Disjoint file sets (service.py vs models.py + workers/) |
| 3 | 39-04 | Needs 39-03's table + ORM + serialized append to service.py after 39-02 |

**Revision 2026-05-17:** the Wave-2 parallel claim above is WRONG and has been overridden by the corrected wave layout below. The original write missed that **plan 39-03's `_mark_no_show_bookings` helper edits `apps/backend/app/modules/bookings/service.py`** — the same file plan 39-02 modifies for `_dispatch_booking_dm` + the post-commit dispatch in `create_booking`/`cancel_booking`. Two plans cannot share `bookings/service.py` in the same wave; the orchestrator's same-wave file-overlap rule forces serial execution.

Corrected wave layout (all serial):

| Wave | Plans | Reason |
|---|---|---|
| 1 | 39-01 | Copy templates must exist before any consumer |
| 2 | 39-02 | Adds `_dispatch_booking_dm` + post-commit DM dispatch (sole writer of `bookings/service.py` in this wave) |
| 3 | 39-03 | Adds `_mark_no_show_bookings` to `bookings/service.py` (serial after 39-02 — same-file conflict) + Alembic 0020 + `BookingNotification` ORM + no-show worker + script + tests. Now also OWNS the conftest.py edit that extends `make_future_slot` to accept negative offsets (the factory itself lands in 39-02 Wave 2; 39-03 widens its contract in Wave 3) |
| 4 | 39-04 | Reminder cron (serial after 39-03 — depends on `BookingNotification` ORM + 0020, AND appends `_send_booking_reminders` to `bookings/service.py` which is now safe because 39-02 + 39-03 have both committed) |

Plan-set unchanged: still 4 commit-sized plans (39-01 / 39-02 / 39-03 / 39-04) covering the same 10 requirements. Only execution-wave parallelism is reduced — Phase 39 now runs as 4 serial waves instead of 3. The original "disjoint file sets" claim is preserved above for historical reference; this Revision block is the authoritative source of truth for any downstream agent reading the file.

#### D-39-02 — Notifications copy lives in `app/modules/bookings/notifications.py`, NOT in `app/integrations/telegram/copy.py`
REQUIREMENTS NOTIFY-01 explicitly locks the path `app/modules/bookings/notifications.py`. This **deviates from v1.3** where templates live in `app/integrations/telegram/copy.py` — the deviation is intentional and chosen at REQUIREMENTS lock time. Rationale (recorded here for downstream agents who may otherwise apply the v1.3 pattern):

- **Domain ownership:** booking DM copy is owned by the bookings module's business semantics (which event triggered which template; who is the addressee). It is not a generic Telegram integration concern.
- **Module-scoped import direction:** with templates inside `bookings/`, the cron worker file `workers/scheduled/send_booking_reminders.py` imports `app.modules.bookings.notifications` — already permitted by the Phase 18 D-09 single-owning-module-per-worker exception. No new import-linter relaxation needed.
- **`_BOT_BOOK_DENIED_DM` is also in this file** despite being consumed by the Telegram bot worker (Phase 40 BOT). The bot worker is permitted to import `app.modules.bookings.notifications` under the same D-09 rule. Keeps all 5 booking-related strings co-located with one owner-copy-lock review surface.

**Side effect:** `_BOT_BOOK_DENIED_DM` is ALSO referenced by Phase 40 BOT-02 to set up the anti-oracle reply. Phase 40's bot handler imports the same constant — single source of truth.

#### D-39-03 — `booking_notifications` table has NO `telegram_chat_id` snapshot column
REQUIREMENTS NOTIFY-05 specifies exactly 4 columns: `id, booking_id, kind, sent_at`. v1.3 `membership_notifications` (line 304 of `memberships/models.py`) **does** carry `telegram_chat_id: int` as a snapshot — **rejected for v1.5** because:

- NOTIFY-05 does not list it. The REQUIREMENTS lock is canonical.
- The cron resolves the chat_id at send time via `JOIN clients ON bookings.client_id = clients.id` and reads `clients.telegram_user_id`. The chat_id is therefore always current (a client who re-links their Telegram account between the booking and the reminder uses the new chat). v1.3 took the snapshot for audit-trail reconstruction; v1.5 prefers freshness for reminders.
- Saving a column we never read avoids a future schema-debt cleanup.

If a downstream operational need for the snapshot surfaces (e.g., support-side question "which chat got the reminder for booking X"), it can be added in a v1.5.1 patch — the row is append-only so backfill is trivial.

### Telegram DM Templates (NOTIFY-01)

#### D-39-04 — No A/B variants — single locked template per kind
v1.3 Phase 27 D-27-10 introduced anti-oracle A/B variants (`pick_variant(client_id)`) to prevent send-pattern fingerprinting on the 7d/3d/1d expiring DMs (6 templates: 3 windows × 2 variants). NOTIFY-01 specifies "4 locked Russian DM templates" — not 8 — so v1.5 ships **one template per kind** (no variants). Rationale:

- The threat model is different: expiring DMs are recurring per-client and observable over time; booking DMs are one-shot per booking and tied to a discrete operator action a client initiated. Fingerprinting is not a meaningful attack surface for booking confirmations.
- Single template makes the owner copy-lock sign-off in plan 39-01 a 4-string review rather than an 8-string review.
- If anti-oracle variants are needed later (v1.6+), the helper signature `render_booking_confirmed_dm(client_name, trainer_name, slot_start_msk)` can be extended to `(..., variant='A'|'B')` without changing callers (default 'A').

**Placeholder convention:** all 4 templates use exactly `{client_name}`, `{trainer_name}`, `{slot_start_msk}` placeholders. Renderer uses `str.format(**kwargs)` (NOT f-string) so unknown keys raise `KeyError` loud at test time. `slot_start_msk` is the ISO-like display string `"DD.MM.YYYY HH:MM"` in Europe/Moscow (matches v1.3 `end_date.strftime("%d.%m.%Y")` discipline).

#### D-39-05 — Cancel-template selection by `actor.role`, NOT by `cancel_reason`
NOTIFY-04 specifies:
- Client cancels their own booking → **NO DM** (the client just hit the cancel button).
- Reception cancels (acting on client's behalf) → `BOOKING_CANCELLED_BY_CLIENT_DM` to the client.
- Owner cancels → `BOOKING_CANCELLED_BY_OWNER_DM` to the client.
- Slot-cancelled cascade (SLOT-07) → `BOOKING_CANCELLED_BY_OWNER_DM` (the cascade is owner-only authorisation).

The discriminator is `actor.role` at the cancel-callsite, NOT the `cancel_reason` text. Implementation in `bookings/service.cancel_booking`:

```python
# After step 8 placeholder (current TODO Phase 39 NOTIFY-04):
if actor.role == "owner":
    _dispatch_booking_dm(booking, template=BOOKING_CANCELLED_BY_OWNER_DM, ...)
elif actor.role == "reception":
    _dispatch_booking_dm(booking, template=BOOKING_CANCELLED_BY_CLIENT_DM, ...)
# else: actor.role == "client" via self-service (NOT currently supported in v1.5
#       — there is no client-facing cancel endpoint; treated as defensive no-op).
```

The `else` branch is defensive: v1.5 has no client self-service cancel HTTP path (cancellation is owner+reception only per the locked RBAC). Phase 40's bot does NOT expose a `/cancel` command (out of scope). The branch is structurally unreachable but logged INFO if it ever fires (regression alarm).

**Slot-cascade callsite:** `schedule/service.cancel_slot` always passes `template=BOOKING_CANCELLED_BY_OWNER_DM` (cascade is owner-only — see `apps/backend/app/modules/schedule/service.py:492` — `cancel_reason="slot_cancelled_by_owner"`).

### Cron Patterns

#### D-39-06 — Cron-tick transaction mode per cron type
Mirroring the Phase 18 / Phase 27 split precisely:

- **`mark_no_show_bookings` (CRON-01)** — **single-session** (mirror `expire_memberships.py`). The cron is a pure batch SQL UPDATE with NO Telegram I/O. One session, one transaction, one commit. Holding a single DB connection across the batch is fine because there are no awaits on the network. Implementation outline:

```python
async def mark_no_show_bookings(ctx: dict[str, Any]) -> int:
    session_factory = ctx["sessionmaker"]
    async with session_factory() as session:
        count = await bookings_service._mark_no_show_bookings(session)
    return count
```

- **`send_booking_reminders` (CRON-02)** — **multi-session per-send** (mirror `send_expiring_notifications.py`). The cron iterates candidate bookings, sends one DM each (network I/O), then inserts one `booking_notifications` row on success. Holding a single DB connection across N HTTP-to-Telegram round-trips wastes the pool. The service helper opens a fresh per-send session per the v1.3 Phase 27 D-27-07 pattern (b). Bot construction uses `app.integrations.telegram.bot.build_bot(token=...)` (D-27-06 — Option B LOCKED).

#### D-39-07 — `SELECT FOR UPDATE` on the no-show cron candidate set
CRON-01 explicitly requires `SELECT FOR UPDATE` on the booking row to defeat the race against `pt_sessions.service.record_pt_session`'s booking-completion path (D-38-19 locked the lock-acquisition discipline in Phase 38). Implementation in `bookings/service._mark_no_show_bookings(session) -> int`:

```python
# Atomic select-then-update; FOR UPDATE blocks any concurrent
# record_pt_session UoW that holds the same row lock (D-38-19).
rows = await session.execute(
    sa.text(
        "SELECT b.id, b.slot_id, b.client_id "
        "FROM bookings b "
        "JOIN trainer_availability_slots s ON s.id = b.slot_id "
        "WHERE b.status = 'confirmed' "
        "AND s.end_time < now() "
        "FOR UPDATE OF b"  # lock booking row only; not the slot
    )
)
candidates = rows.fetchall()
if not candidates:
    return 0
# UPDATE in a single statement (atomicity: every selected row is locked).
await session.execute(
    sa.text(
        "UPDATE bookings SET status = 'no_show', no_show_at = now() "
        "WHERE id = ANY(:ids) AND status = 'confirmed'"
    ),
    {"ids": [c.id for c in candidates]},
)
for c in candidates:
    await audit.emit(
        session,
        "booking_no_show",  # LITERAL (INFRA-11 AST gate)
        actor_user_id=None,  # system actor
        resource_type="booking",
        resource_id=c.id,
        booking_id=str(c.id),
        slot_id=str(c.slot_id),
        client_id=str(c.client_id),
        no_show_at=datetime.now(MOSCOW_TZ).isoformat(),
    )
await session.commit()
return len(candidates)
```

**Important:** the WHERE-clause time comparison `s.end_time < now()` is in **UTC** because Postgres `now()` returns `TIMESTAMPTZ` (the cluster TZ does not matter for comparison between two TIMESTAMPTZ values). REQUIREMENTS CRON-01 phrasing `s.end_time < now() AT TIME ZONE 'Europe/Moscow'` is **semantically equivalent** because both sides are `TIMESTAMPTZ` and the `AT TIME ZONE` conversion does not change the underlying instant — the requirement phrasing is documentary, not enforcement. Implementation uses the plain `< now()` form to avoid the misleading-looking `AT TIME ZONE` shim. (PITFALLS Pitfall 6 — TIMESTAMPTZ comparison is TZ-independent.)

**No-show audit `actor_user_id` = NULL** — this is the existing convention for system-actor events (see `expire_pt_packages` audit emit). The audit_log column is nullable for cron-emitted rows.

#### D-39-08 — Reminder cron window: `BETWEEN now()+23h AND now()+25h`
CRON-02 specifies the 23h..25h window. With the cron firing once per day at 06:35 MSK, the 2-hour window guarantees every confirmed booking is reminded exactly once at ~24h prior — a booking at 07:35 today gets its reminder tomorrow at 06:35 (which is 25h before — at the right-edge), and a booking at 05:35 the next day gets its reminder tomorrow at 06:35 (which is 23h before — at the left-edge). Pinning the window to `[now()+23h, now()+25h]` (rather than `[now()+24h-1h, now()+24h+1h]`) matches the REQUIREMENTS phrasing literally.

Boundary-handling: bookings whose `slot.start_time` falls exactly on `now()+23h` or `now()+25h` are eligible (inclusive both sides — `BETWEEN` is inclusive in Postgres). The UNIQUE `(booking_id, kind)` constraint prevents a second send if the cron is manually re-run within the same 24h period.

Implementation outline in `bookings/service._send_booking_reminders(session_factory, *, bot, sender, notifications_module) -> int`:

```python
# Per-cron-tick:
async with session_factory() as read_session:
    candidates = await read_session.execute(
        sa.text(
            "SELECT b.id, b.client_id, b.slot_id, "
            "       c.telegram_user_id, c.first_name, "
            "       t.full_name AS trainer_name, "
            "       s.start_time "
            "FROM bookings b "
            "JOIN clients c ON c.id = b.client_id "
            "JOIN trainer_availability_slots s ON s.id = b.slot_id "
            "JOIN trainers t ON t.id = s.trainer_id "
            "LEFT JOIN booking_notifications n "
            "       ON n.booking_id = b.id AND n.kind = 'reminder_24h' "
            "WHERE b.status = 'confirmed' "
            "  AND s.start_time BETWEEN now() + interval '23 hours' "
            "                       AND now() + interval '25 hours' "
            "  AND c.telegram_user_id IS NOT NULL "
            "  AND n.id IS NULL"   # pre-filter rows already reminded
        )
    )
    rows = candidates.fetchall()
sent = 0
for r in rows:
    text = notifications_module.render_booking_reminder_24h_dm(
        client_name=r.first_name,
        trainer_name=r.trainer_name,
        slot_start_msk=r.start_time.astimezone(MOSCOW_TZ).strftime("%d.%m.%Y %H:%M"),
    )
    result = await sender.send_text_dm(bot, r.telegram_user_id, text)
    if not result.ok:
        _log.warning("booking_reminder_send_failed", booking_id=str(r.id), blocked=result.blocked)
        continue
    async with session_factory() as write_session:
        try:
            await notifications_module._insert_reminder_idempotency_row(write_session, booking_id=r.id)
            await write_session.commit()
            sent += 1
        except IntegrityError:
            # Concurrent tick or a manual one-shot run hit the same row first.
            await write_session.rollback()
            _log.info("booking_reminder_idempotency_collision", booking_id=str(r.id))
_log.info("send_booking_reminders_complete", count=sent)
return sent
```

Pre-filtering by `LEFT JOIN booking_notifications` keeps the candidate set tight; the IntegrityError catch covers the residual race window between SELECT and INSERT. Mirror of v1.3 D-27-15 discipline.

### Synchronous Send Pattern (NOTIFY-03/04)

#### D-39-09 — Confirmation + cancellation DMs are SYNCHRONOUS (in-request), fire-and-forget
Two implementation paths were considered:

| Option | Latency impact | Failure semantics | Complexity |
|---|---|---|---|
| A — sync in `create_booking` / `cancel_booking` (chosen) | +~150-400ms on 200/201 path | WARNING-log + swallow | Lowest — no queue |
| B — ARQ enqueue on commit | ~+5ms (just enqueue) | ARQ retries automatic | Medium — needs a new ARQ function + per-DM idempotency |

**Auto-select Option A.** Justifications:

- REQUIREMENTS NOTIFY-03 says "Failures (403/blocked) logged WARNING + no row in idempotency table — retried on next applicable cron (booking confirmation is once-off, so failures simply log)." → fire-and-forget on the confirmation path is explicitly the locked behaviour.
- Single-zal MVP at ~10-30 bookings/day means the +400ms worst case is invisible to operators (reception is not in a hot loop).
- Avoiding a new ARQ function keeps `WorkerSettings.functions` and `cron_jobs` lists exactly to the two CRON-01/02 additions, no implicit job-queue surface.
- The async-bot construction overhead (`build_bot(token=...)` returns a fresh `Bot` per call — line 96 `app/integrations/telegram/bot.py`) is acceptable per-request because each booking-confirmation is a discrete operator-initiated action, not a hot loop.
- If latency ever becomes a problem (e.g., during a Phase 40 bot-driven `/book` burst), the migration path is to introduce a single `enqueue_booking_dm` ARQ function in v1.6 — the helper interface `_dispatch_booking_dm(booking, *, template, ...)` is designed to be queue-target-swappable.

**Failure handling (matches v1.3 sender contract):** `send_text_dm` returns `SendResult(ok=False, blocked=True | error=str)` and NEVER raises. The helper just `_log.warning(...)` and returns. The HTTP response always succeeds.

#### D-39-10 — `_dispatch_booking_dm` is a private module function in `bookings/service.py`, NOT a Protocol slot
v1.4 / Phase 37 D-37-06 introduced Protocol slots to break cross-module dependencies. The DM dispatch helper does NOT need a slot because it only depends on `app.integrations.telegram.{bot, sender}` + `app.modules.bookings.notifications` — both inside the same module or in the integrations layer (where bookings/service.py is always allowed to import from per `app/workers/__init__.py:1-21` rationale and the import-linter `integrations-not-depend-on-modules` direction).

Signature:
```python
async def _dispatch_booking_dm(
    booking: Booking,       # in-memory ORM object with .client and .slot.trainer joinedloaded
    *,
    template: str,          # one of the 4 BOOKING_*_DM constants
    bot: Bot,
    sender: ModuleType,
) -> None:
    """Fire-and-forget Telegram DM send. WARNING-logs on every failure path; never raises."""
```

**Caller responsibility:** the booking ORM instance MUST have `client` and `slot.trainer` already loaded (joinedload from the existing create/cancel reads). If they are not, the helper logs an ERROR and returns without sending (defensive — no fallback `await session.refresh(...)` because that would extend the open transaction past commit-time).

**Bot construction:** the helper creates a fresh `Bot` via `build_bot(token=...)` per call. At ~10-30 bookings/day this is negligible. NOT cached at module scope to avoid the v1.3 D-27-06 anti-pattern (long-lived `aiohttp` session leak risk).

**Client linkage check:** if `booking.client.telegram_user_id is None`, log INFO `booking_dm_skipped_unlinked` + return. NOTIFY-03 phrasing "linked client" allows unlinked clients to silently skip.

#### D-39-11 — Trainer name + slot_start_msk display formatting locked
- `trainer_name = booking.slot.trainer.full_name` — `trainers.full_name` is a single Text column (`trainers/models.py:28`), so no first/last/middle composition is needed (parity with v1.3 client DMs that use `client.first_name` only).
- `client_name = booking.client.first_name` — first-name-only for warmth + privacy (mirrors v1.3 expiring DM tone). NOT `f"{first_name} {last_name}"` — last names in Russian context feel formal/legal.
- `slot_start_msk = booking.slot.start_time.astimezone(MOSCOW_TZ).strftime("%d.%m.%Y %H:%M")` — DD.MM.YYYY HH:MM in Moscow time. Russian-locale convention; matches v1.3 `end_date.strftime("%d.%m.%Y")` for date display + adds the HH:MM time portion booking DMs need.
- `MOSCOW_TZ` is the existing `app.core.timezone.MOSCOW_TZ` constant (`ZoneInfo("Europe/Moscow")`); already used by Phase 38 D-38-12 validity-window guard.

### Idempotency & Constraint Naming

#### D-39-12 — Alembic 0020 lands in plan 39-03 with the `BookingNotification` ORM model
Alembic linear-history discipline (v1.2 Phase 16 — already enforced) requires migrations land in numerical order. 0020 must follow 0019 (Phase 38 PKG-04). Two placement choices:

- (a) 0020 in plan 39-03 alongside the `mark_no_show_bookings` cron (which does NOT consume the table) — leaves 39-04 dependency-clean.
- (b) 0020 in plan 39-04 alongside the reminder cron that actually consumes it — keeps each plan's migration "owned" by its consumer.

**Auto-select (a) — 0020 in plan 39-03.** Rationale:
- Plan 39-04's wave depends on 39-03 anyway (per D-39-01 wave layout). Landing the table earlier costs nothing.
- The `BookingNotification` ORM class lives in `bookings/models.py` next to `Booking` — landing it with 39-03 means `bookings/models.py` is touched exactly twice (Phase 38 creates the file; Phase 39 plan 39-03 appends the BookingNotification class). Plan 39-04 only touches `bookings/service.py` + `workers/scheduled/send_booking_reminders.py` + `workers/__init__.py` + `scripts/run_booking_reminders_once.py`.
- Mirrors v1.3 Phase 27 where Alembic `0010_notifications.py` lands in the same plan as the model class, separately from the cron.

#### D-39-13 — Constraint naming follows the established convention
Per v1.3 / v1.4 / Phase 38 D-38-15 pattern:
- `uq_booking_notifications_booking_kind` — partial UNIQUE used as IntegrityError discriminator (the cron helper catches IntegrityError and matches `__cause__.diag.constraint_name`).
- `fk_booking_notifications_booking_id_bookings` — FK with `ON DELETE RESTRICT` (v1.3 used CASCADE; v1.5 prefers RESTRICT because bookings themselves are never hard-deleted per D-38-04 / Phase 38 `bookings` design — a CASCADE would mask any future accidental DELETE). `ON DELETE RESTRICT` is also consistent with Phase 38's `bookings.pt_package_id` and `bookings.slot_id` ON DELETE RESTRICT direction.
- `ck_booking_notifications_kind` — CHECK constraint `kind IN ('reminder_24h')` (single-element check today; mirrored on the SQLAlchemy CheckConstraint).
- `ix_booking_notifications_booking_id` — explicit index needed for `alembic check` cleanliness (mirror v1.3 line 318-323 of `memberships/models.py`).
- `pk_booking_notifications` — explicit PrimaryKey name (op.f convention auto-generated).

**Catch-or-not-catch IntegrityError on insert:** the reminder cron's race window is very narrow (LEFT JOIN pre-filter + bounded 06:35 daily firing + `unique=True` on cron registration). But the operator one-shot runner CAN race against the live cron. Catch + rollback + INFO-log (mirrors v1.3 D-27-15) — see D-39-08 implementation outline.

### Audit & Compliance

#### D-39-14 — Phase 37 already locked the audit schema for `booking_no_show`
`BookingNoShowPayload(booking_id, slot_id, client_id, no_show_at: str)` is locked at `app/core/audit_payloads.py:410-424` (extra='forbid') and registered at line 462. Phase 39 cron emit kwargs MUST match exactly — `no_show_at` is a string (ISO-8601 with TZ offset per the schema docstring), `booking_id` / `slot_id` / `client_id` are passed as UUID objects per the schema's type hints.

**Note on D-37-05 (UUID-as-str discipline):** Phase 37 D-37-05 said "all audit payload UUID fields typed as `str`" — but `BookingNoShowPayload` types them as `UUID` (lines 421-423). Phase 37 INFRA-25 evidently revised the convention to typed UUIDs after the original D-37-05 lock; the payload schemas accept both forms (Pydantic v2 coerces `str → UUID` automatically) so callsites may pass `str(uuid)` per the existing `bookings/service.py:549-551` style OR pass the raw `UUID` — either form validates. **Phase 39 callsites pass UUID objects (not `str(uuid)`)** for consistency with the schema type hints, matching the Phase 38 `cancel_booking` audit emit's `cancel_reason=data.reason` direct-pass discipline.

No new audit events. No new payload schemas. Phase 37 was deliberately conservative — `booking_reminder_sent` is NOT an audit event (the `booking_notifications` row IS the durable record); `booking_confirmed_dm_sent` / `booking_cancelled_dm_sent` are NOT audit events (the upstream `booking_created` / `booking_cancelled` events ARE the source-of-truth; DM dispatch is a side effect with no business value to audit).

#### D-39-15 — INFRA-11 AST gate already covers `booking_no_show` LITERAL emission
The Phase 37 `apps/backend/scripts/svc001_check.py` (or equivalent walker) already enforces LITERAL emission of `LOCKED_AUDIT_EVENTS`. Phase 39 callsite in `mark_no_show_bookings` worker uses `"booking_no_show"` as a string literal (NOT a variable). No new gate logic needed.

### Cron Worker Wiring

#### D-39-16 — Cron registration order preserves existing v1.3 / v1.4 wakeups + sequences correctly per CRON-02 "after expire_pt_packages 06:25"
After Phase 39 lands, the final `WorkerSettings.cron_jobs` list is:

```python
cron_jobs: ClassVar[list[Any]] = [
    cron(expire_memberships,         hour=3, minute=5,  unique=True, keep_result=60),  # 06:05 MSK
    cron(send_expiring_notifications, hour=3, minute=15, unique=True, keep_result=60), # 06:15 MSK
    cron(expire_pt_packages,         hour=3, minute=25, unique=True, keep_result=60),  # 06:25 MSK
    cron(send_booking_reminders,     hour=3, minute=35, unique=True, keep_result=60),  # 06:35 MSK — Phase 39 CRON-02
    cron(mark_no_show_bookings,      hour=20, minute=10, unique=True, keep_result=60), # 23:10 MSK — Phase 39 CRON-01
]
```

The morning sequence `5 → 15 → 25 → 35` is intentional: each cron is a near-disjoint workload, but list-order also serves as visual documentation of the daily flow. The evening tick (`mark_no_show_bookings` at 20:10 UTC = 23:10 MSK) is placed last to make container TZ-conversion (`hour=20, minute=10` UTC) audit-trivially the only "evening" entry.

**`functions` list ordering follows registration order:** append both new functions at the end (after `expire_pt_packages`):
```python
functions: ClassVar[list[Any]] = [
    expire_memberships,
    send_expiring_notifications,
    expire_pt_packages,
    send_booking_reminders,    # Phase 39 CRON-02
    mark_no_show_bookings,     # Phase 39 CRON-01
]
```

The `on_startup` resolution assertion (PITFALLS Pitfall 4 step 6 — `cron_function_names - function_names == set()`) will catch any typo. The existing test `tests/unit/test_worker_cron_resolution.py` covers this — Phase 39 just confirms the test stays green.

#### D-39-17 — One-shot operator runners mirror `run_expiring_cron_once.py` line-for-line
Both `apps/backend/scripts/run_no_show_cron_once.py` and `apps/backend/scripts/run_booking_reminders_once.py` are line-for-line ports of `apps/backend/scripts/run_expiring_cron_once.py`. Same TM-29-02 (DATABASE_URL must contain `localhost` or `postgres:5432`) + TM-29-03 (TELEGRAM_SANDBOX_CHAT_ID must be set in env — **only required for the reminder runner**; the no-show runner does NOT touch Telegram so TM-29-03 is omitted there but the docstring explicitly notes the omission). Same REG-29-04 eager-import block:

```python
# REG-29-04 (Phase 29 wave 3): SQLAlchemy resolves FK references lazily at
# first flush. Eager-import the four models touched by the cron + audit path
# so all tables are registered before the session opens.
from app.modules.auth import models as _auth_models  # noqa: F401
from app.modules.clients import models as _client_models  # noqa: F401
from app.modules.bookings import models as _bookings_models  # noqa: F401
from app.modules.schedule import models as _schedule_models  # noqa: F401
from app.modules.trainers import models as _trainers_models  # noqa: F401
```

The no-show runner adds `trainers` and `schedule` (the JOIN reads them) and `bookings` (the UPDATE writes them); the reminder runner adds all five. Output line on success: `Fired mark_no_show_bookings once: count=<N>` / `Fired send_booking_reminders once: count=<N>`.

### Test Discipline

#### D-39-18 — Real-Postgres race test for the no-show cron vs `record_pt_session` is OPTIONAL in Phase 39
PITFALLS Pitfall 12 + D-38-19 already established the `SELECT FOR UPDATE` guard in `record_pt_session`. Phase 39's no-show cron also uses `FOR UPDATE OF b` (D-39-07). The two paths are correctly serialized.

A real-Postgres `asyncio.gather` race test (mirror of `BOOK-TEST-01` from Phase 38) would prove the serialization end-to-end but adds significant complexity to plan 39-03 (real DB setup, two concurrent UoW dispatch, asserting one wins). **Auto-select: NO new race test in Phase 39.** Justifications:

- The lock discipline is unit-testable: assert the SQL contains `FOR UPDATE` (a `WHERE-clause grep` in the test). The race is structurally impossible if both sides hold the lock — at the FOR UPDATE layer this is a Postgres guarantee, not a Python assertion.
- The Phase 38 `BOOK-TEST-01` already exercises real-Postgres concurrent transactions on the bookings table.
- Phase 40 milestone verification (VER-07) explicitly runs the one-shot cron runner against a live stack — that IS the integration test for the cron's correctness.
- If a real-DB race test is needed, it lands in Phase 40 milestone verification rather than as a Phase 39 deliverable. (Documented here so plan-checker doesn't flag the omission as a gap.)

Phase 39 integration tests for the cron use the existing `db_session` fixture (savepoint-mode session) + ORM-level seeding + `await mark_no_show_bookings({"sessionmaker": session_factory})` — same pattern as `tests/integration/pt_packages/test_expire_pt_packages_cron.py`.

#### D-39-19 — DM send tests stub the `sender` module, NOT the live Telegram Bot
v1.3 Phase 27 pattern: tests pass a `sender_module_stub` with a `send_text_dm(bot, chat_id, text) -> SendResult` callable that records calls into a list. Phase 39 mirrors exactly — the integration test asserts the recorded call list contains exactly N entries with exactly the expected (chat_id, text) tuples per scenario.

**No mocked `Bot`** — pass `bot=None` (the stub does not use it). Avoids the `aiohttp` session-create cost at test time.

### Claude's Discretion
None — `--auto` mode picked every default with rationale logged above. The user can audit and override any D-39-NN before `/gsd-plan-phase 39` consumes this file.

### Folded Todos
None — `gsd-sdk query todo.match-phase 39` was not invoked in `--auto` mode for this discussion. The only pending STATE.md todo (`Run /gsd-plan-phase 37`) is obsolete after Phase 37 completion 2026-05-17 / Phase 38 completion 2026-05-17.

</decisions>

<canonical_refs>
## Canonical References

**Downstream agents (researcher, planner, executor) MUST read these before planning or implementing.**

### Milestone Decisions & Requirements (PRIMARY)
- `.planning/REQUIREMENTS.md` §C-06, C-10, C-11 — locked milestone bedrock decisions that directly drive Phase 39 (audit-event roster, no-show cron-only policy, 24h reminder cron + `booking_notifications` idempotency table)
- `.planning/REQUIREMENTS.md` §NOTIFY-01..05 — 5 notification requirements (Phase 39 scope)
- `.planning/REQUIREMENTS.md` §CRON-01..05 — 5 cron requirements (Phase 39 scope)
- `.planning/PROJECT.md` "Current Milestone: v1.5" + Key Decisions table — accumulated business-domain context (PT-vs-floor B-10 invariant remains canonical even though Phase 39 doesn't change `visits/`)
- `.planning/STATE.md` "v1.5 bedrock decisions" — C-01..C-15 summary + Phase 37/38 done-state

### Phase 37 Bedrock + Phase 38 Implementation (LOCKED — do NOT re-decide)
- `.planning/phases/37-foundations-bedrock/37-CONTEXT.md` — D-37-01..D-37-09 (RBAC, OWNER_ONLY, FSM constant location, Protocol slot semantics, audit payload UUID convention — see D-39-14 note above on the UUID-as-str-vs-UUID-typed reconciliation)
- `.planning/phases/37-foundations-bedrock/37-VERIFICATION.md` — Phase 37 acceptance log
- `.planning/phases/38-schedule-module-booking-core/38-CONTEXT.md` — D-38-01..D-38-19 (especially D-38-12 MOSCOW_TZ discipline, D-38-17 audit emit kwargs, D-38-19 SELECT FOR UPDATE in record_pt_session as the partner-side of D-39-07)
- `.planning/phases/38-schedule-module-booking-core/38-VERIFICATION.md` + `38-VERIFICATION-ADDENDUM.md` — Phase 38 acceptance log (Phase 39 builds on a verified booking surface)
- `.planning/phases/38-schedule-module-booking-core/38-PATTERNS.md` — the pattern-mapper output that informed Phase 38 structure also informs Phase 39's worker-file structure

### Research Outputs (still authoritative for Phase 39)
- `.planning/research/SUMMARY.md` — 4-dimension research synthesis
- `.planning/research/PITFALLS.md` §Pitfalls 4, 6, 9, 12, 14 — the 5 pitfalls Phase 39 must defuse (Pitfall 4 = ARQ cron-resolution invariant; Pitfall 6 = TIMESTAMPTZ comparison TZ-independence; Pitfall 9 = no-show reverse-transition is anti-feature; Pitfall 12 = no-show vs record_pt_session race; Pitfall 14 = structlog contextvars per cron tick)
- `.planning/research/PITFALLS.md` §"Looks Done But Isn't" Checklist — Phase 39 verification matrix subset
- `.planning/research/STACK.md` — ARQ, structlog contextvars, ZoneInfo, Postgres 16 idioms

### v1.3 Phase 27 Precedent (CANONICAL pattern source — mirror line-for-line)
- `apps/backend/app/integrations/telegram/copy.py` — owner-copy-lock pattern + render helper signature shape (Phase 39 deviates on file location per D-39-02 but mirrors the render helper API)
- `apps/backend/app/modules/memberships/models.py:267-324` — `MembershipNotification` ORM class shape (Phase 39 mirrors verbatim except no `telegram_chat_id` per D-39-03)
- `apps/backend/alembic/versions/0010_notifications.py` — Alembic 0020 template (Phase 39 mirrors verbatim except `ON DELETE RESTRICT` per D-39-13)
- `apps/backend/app/modules/memberships/service.py:1401-1500` — `_send_expiring_notifications` cron helper pattern (multi-session + IntegrityError handling + structlog summary)
- `apps/backend/app/workers/scheduled/send_expiring_notifications.py` — worker file shape mirror for `send_booking_reminders.py`
- `apps/backend/app/workers/scheduled/expire_memberships.py` — worker file shape mirror for `mark_no_show_bookings.py` (single-session DB-only batch UPDATE)
- `apps/backend/app/workers/scheduled/expire_pt_packages.py` — second precedent for single-session DB-only batch (Phase 33 / v1.4 — closer to v1.5 era than expire_memberships)
- `apps/backend/scripts/run_expiring_cron_once.py` — one-shot operator runner template (mirror for both `run_no_show_cron_once.py` + `run_booking_reminders_once.py`)
- `apps/backend/app/integrations/telegram/sender.py` — `SendResult` + `send_text_dm(bot, chat_id, text)` API (Phase 39 consumes verbatim)
- `apps/backend/app/integrations/telegram/bot.py:85-96` — `build_bot(*, token=...)` helper (Phase 39 consumes verbatim)

### Roadmap & Milestone Plans
- `.planning/ROADMAP.md` §Phase 39 — goal + 4 success criteria (goal-backward anchor for plan-checker)
- `.planning/MILESTONES.md` — REG-29-04 incident (eager-import block in one-shot runners — critical context for D-39-17)

### Codebase Maps
- `.planning/codebase/ARCHITECTURE.md` — modular-monolith conventions
- `.planning/codebase/STRUCTURE.md` — directory + module layout
- `.planning/codebase/INTEGRATIONS.md` — external boundaries (Telegram bot, ARQ cron — both lightly touched in Phase 39)
- `.planning/codebase/TESTING.md` — pytest + httpx ASGITransport conventions

### Audit Infrastructure (LOCKED at Phase 37)
- `apps/backend/app/core/audit.py:107` + `:226` — `booking_no_show` event registered in LOCKED_AUDIT_EVENTS
- `apps/backend/app/core/audit_payloads.py:410-424` — `BookingNoShowPayload` schema with `extra='forbid'`
- `apps/backend/app/core/audit_payloads.py:462` — registry entry mapping the event to the schema

### Source Files Phase 39 Will MODIFY (existing files)
- `apps/backend/app/modules/bookings/models.py` — APPEND `BookingNotification` ORM class (plan 39-03)
- `apps/backend/app/modules/bookings/service.py` — replace `# TODO Phase 39 NOTIFY-04` stub in `cancel_booking` (line 556), add `# TODO Phase 39 NOTIFY-03` (currently implicit in the Phase 38 create_booking SUMMARY comment line 555) DM-send in `create_booking`, and append new private `_dispatch_booking_dm` + `_send_booking_reminders` + `_mark_no_show_bookings` helpers (plans 39-02 + 39-03 + 39-04 — coordinated per D-39-01 wave layout)
- `apps/backend/app/modules/schedule/service.py` — extend the booked→cancelled cascade to fire `_dispatch_booking_dm(template=BOOKING_CANCELLED_BY_OWNER_DM, ...)` per cancelled booking (plan 39-02)
- `apps/backend/app/workers/__init__.py` — APPEND `mark_no_show_bookings` + `send_booking_reminders` to `functions` and 2 new `cron(...)` entries to `cron_jobs` (plans 39-03 + 39-04 — plan 39-04 must reconcile after 39-03 lands)
- `apps/backend/tests/unit/test_worker_cron_resolution.py` (or `tests/unit/workers/test_worker_settings.py`) — confirm the `on_startup` resolution assertion test still passes with the 2 new functions registered (no test code change expected; the test reads `WorkerSettings.functions` / `WorkerSettings.cron_jobs` reflectively)

### Source Files Phase 39 Will CREATE (new files)
- `apps/backend/app/modules/bookings/notifications.py` — 4 DM templates + `_BOT_BOOK_DENIED_DM` + 4 `render_*_dm(...)` helpers (plan 39-01)
- `apps/backend/alembic/versions/0020_booking_notifications.py` — single new table (plan 39-03)
- `apps/backend/app/workers/scheduled/mark_no_show_bookings.py` — single-session DB-only batch UPDATE cron (plan 39-03)
- `apps/backend/app/workers/scheduled/send_booking_reminders.py` — multi-session DM-send cron (plan 39-04)
- `apps/backend/scripts/run_no_show_cron_once.py` — one-shot operator runner (plan 39-03)
- `apps/backend/scripts/run_booking_reminders_once.py` — one-shot operator runner (plan 39-04)
- `apps/backend/tests/unit/test_booking_notifications_copy.py` — unit tests for 4 render helpers + placeholder substitution + `_BOT_BOOK_DENIED_DM` non-empty (plan 39-01)
- `apps/backend/tests/integration/bookings/test_create_sends_dm.py` — service-level integration test (plan 39-02)
- `apps/backend/tests/integration/bookings/test_cancel_sends_dm.py` — service-level integration test (plan 39-02, covers actor.role discriminator + slot-cascade)
- `apps/backend/tests/integration/bookings/test_no_show_cron.py` — cron integration test (plan 39-03)
- `apps/backend/tests/integration/bookings/test_reminder_cron.py` — cron integration test (plan 39-04, covers idempotency row insert + 403 skip + unlinked-client skip)

### Existing patterns to mirror (READ before writing)
- `apps/backend/app/modules/memberships/service.py:_send_expiring_notifications` — closest analog to `_send_booking_reminders` (multi-session per-send loop)
- `apps/backend/app/modules/pt_packages/service.py:expire_pt_packages_orchestrator` (or equivalent — verify exact name during plan-phase) — closest analog to `_mark_no_show_bookings` (single-session batch UPDATE + audit emit per row)
- `apps/backend/tests/integration/pt_packages/test_expire_pt_packages_cron.py` — closest analog cron integration test

### Architectural Contracts (CI-enforced; must stay green)
- `.importlinter` — Phase 39 does NOT change any contract. The bookings module gaining a `notifications.py` sibling does not affect `modules-independent` (still no cross-module imports). The new worker files in `app/workers/scheduled/` are already covered by the Phase 18 D-09 single-owning-module exception (each cron worker file MAY import its owning module's service)
- `apps/backend/scripts/svc001_check.py` (or equivalent walker) — the cron helpers `_mark_no_show_bookings` + `_send_booking_reminders` are SVC001-exempt with explicit `# noqa: SVC001 caller-owns-txn` comments (mirror `_send_expiring_notifications` line 1401 marker)
- `apps/backend/tests/test_audit_taxonomy.py` — already locked at 56 events after Phase 37; Phase 39 does NOT add new events
- `apps/backend/tests/test_audit_payloads.py` — already locked from Phase 37 (`BookingNoShowPayload` extra='forbid'); Phase 39 emit kwargs must match exactly
- `tests/unit/workers/test_worker_settings.py` + `tests/unit/test_worker_cron_resolution.py` — Phase 39 just confirms green with the 2 new functions appended

</canonical_refs>

<code_context>
## Existing Code Insights

### Reusable Assets
- **`app/integrations/telegram/bot.py:build_bot(*, token=...)`** — fresh-Bot-per-call helper (line 85-96). Phase 39 calls this in `_dispatch_booking_dm` and at the top of both cron workers — same usage as v1.3 `send_expiring_notifications.py:58`.
- **`app/integrations/telegram/sender.py:send_text_dm(bot, chat_id, text) -> SendResult`** — never-raises send helper. Phase 39 consumes verbatim; `SendResult.ok` / `SendResult.blocked` drive the WARNING-log / idempotency-row-skip decisions.
- **`app/core/timezone.MOSCOW_TZ`** (verify exact module path during plan-phase — Phase 38 D-38-12 already consumes this) — `ZoneInfo("Europe/Moscow")` constant for the `slot_start_msk` display + cron tick documentation.
- **`app/core/audit.emit(...)`** — Phase 37-locked audit kernel; `BookingNoShowPayload` already registered (`audit_payloads.py:462`). The mark_no_show_bookings worker calls `audit.emit("booking_no_show", ...)` per row.
- **`app/workers.WorkerSettings.on_startup`** — the cron-resolution invariant assertion (lines 132-140) catches typos in `cron_jobs` referencing function names absent from `functions`. Phase 39's 2 new entries pass through this assertion automatically.
- **`app/workers.WorkerSettings.on_job_start` / `on_job_end`** — `structlog.contextvars` `job_id` / `job_name` binding (lines 158-174). Phase 39 cron functions inherit this automatically; any `_log.info("...")` inside the cron carries `job_id` / `job_name` for trace correlation. CRON-03 explicitly cites this as the deliverable — already implemented; Phase 39 just confirms it covers the 2 new entries.
- **`app/modules/bookings/models.py:Booking`** — Phase 38 model with `client`, `slot`, `pt_package` relationships (verify joinedload availability during plan-phase). Phase 39's DM helpers expect these joinedloaded by the existing service-layer reads.

### Established Patterns
- **Per-worker-file single-owning-module import exception** — `app/workers/__init__.py:1-21` documents that each `app/workers/scheduled/<job>.py` file MAY import ONE owning module's service layer. Phase 39 follows: `mark_no_show_bookings.py` imports `bookings.service`; `send_booking_reminders.py` imports `bookings.service` + `bookings.notifications` + `app.integrations.telegram.{bot, sender}`.
- **Single-session vs multi-session cron pattern** — v1.3 / v1.4 locked. Phase 39's D-39-06 applies the split per-cron-type.
- **`SendResult` + WARNING-log + no-raise** — v1.3 D-27-15 pattern. Phase 39's confirmation/cancellation/reminder code all follow.
- **Owner-copy-lock review** — v1.3 D-27-OWNER-COPY-LOCK. Plan 39-01 captures sign-off in `39-01-SUMMARY.md`.
- **Anti-oracle single-string for negative bot outcomes** — v1.2 D-20-9 + Phase 27 D-27-10 lineage. `_BOT_BOOK_DENIED_DM` (NOTIFY-02) follows.
- **One-shot operator runner with TM-29-02 + TM-29-03 + REG-29-04 guards** — v1.3 Phase 29. Phase 39 mirrors for both new runners.

### Integration Points
- **`bookings/service.py:create_booking` step 7** — currently SVC001-final-commit; Phase 39 inserts a new step 7.5 (or step 8 depending on Phase 38 numbering) for `await _dispatch_booking_dm(...)` BEFORE `await session.commit()`. Rationale: the DM helper is never-raises (D-39-10) so this is safe ordering. Alternatively, the helper fires after commit so a DB-roll-back doesn't trigger a spurious DM. **AUTO-CHOICE: after commit** — booking is fully durable before any DM goes out; matches v1.3 `_send_expiring_notifications` post-INSERT discipline.
- **`bookings/service.py:cancel_booking` step 8** — currently the `# TODO Phase 39 NOTIFY-04` placeholder at line 555-557. Phase 39 plan 39-02 replaces with the actor-role-discriminated dispatch per D-39-05, AFTER `await session.commit()`.
- **`schedule/service.py:cancel_slot` booked→cancelled cascade** — Phase 38 emits both `slot_cancelled` and `booking_cancelled` audit events. Phase 39 plan 39-02 appends a per-cancelled-booking `_dispatch_booking_dm(template=BOOKING_CANCELLED_BY_OWNER_DM, ...)` call AFTER the commit. Iterates whichever in-memory list the cascade already holds; if not retained, a re-SELECT post-commit is acceptable (cancelled bookings are not racing).
- **`app/workers/__init__.py:functions` + `cron_jobs`** — append-only mutation; the existing tests reflectively read both lists so they auto-cover the new entries.
- **`app/main.py:create_app()` Phase 37 INFRA-32/33 wiring (lines 197, 214-216)** — Phase 39 does NOT touch this. The bookings module's `_dispatch_booking_dm` helper is private to the module; no new `register_*` slot needed.

</code_context>

<specifics>
## Specific Ideas

- **Plan ordering** (D-39-01): 39-01 → (39-02 ∥ 39-03) → 39-04. Total 4 plans across 3 waves. Plan 39-01 must land first (consumers depend on the templates). Plan 39-04 must land last (depends on 39-03's ORM + migration AND on 39-02's `bookings/service.py` edits — same-file conflict zone).

- **Migration naming**: `0020_booking_notifications.py`. `down_revision = "0019_pt_sessions_booking_id"`. Alembic linear-history discipline per v1.2 Phase 16. Verify the actual previous revision id during plan-phase by checking the head of `apps/backend/alembic/versions/`.

- **Constraint names** (D-39-13): `uq_booking_notifications_booking_kind`, `fk_booking_notifications_booking_id_bookings`, `ck_booking_notifications_kind`, `ix_booking_notifications_booking_id`, `pk_booking_notifications`. Mirror v1.3 Alembic 0010 naming exactly.

- **DM template placeholder set** (D-39-11): exactly `{client_name}`, `{trainer_name}`, `{slot_start_msk}` for all 4 templates. `_BOT_BOOK_DENIED_DM` has NO placeholders (one-shot anti-oracle text).

- **Owner-copy-lock sign-off**: plan 39-01 closes only after the user explicitly signs off on the 4 Russian strings + the `_BOT_BOOK_DENIED_DM` string. Sign-off recorded in `39-01-SUMMARY.md` (mirror v1.3 D-27 sign-off block).

- **Display formatting** (D-39-11): `slot_start_msk = booking.slot.start_time.astimezone(MOSCOW_TZ).strftime("%d.%m.%Y %H:%M")`. Russian-locale convention DD.MM.YYYY HH:MM. Pinned in the helper so callers can't accidentally pass a UTC-string.

- **Cron schedule reality check** (CRON-01/02): `hour=20, minute=10` UTC = 23:10 MSK (assuming container `TZ=UTC` per v1.0 Key Decisions). `hour=3, minute=35` UTC = 06:35 MSK. Plan 39-03 / 39-04 docstrings explicitly cite the conversion to prevent future "why 20:10?" confusion.

- **CRON-02 explicit "after expire_pt_packages 06:25" ordering**: 06:35 reminder fires 10 minutes after the 06:25 pt_packages-expiry cron. Rationale (recorded for plan-checker): a booking against an `active` PT-package at 06:34 could become an expired-package situation by 06:35 if `expire_pt_packages` flips it. The reminder still goes out (cron WHERE clause is `b.status = 'confirmed'`, not `pt_package.status='active'`) which is the correct UX — the booking is still confirmed; the client can still attend; only future bookings get blocked. Order documented but not load-bearing.

- **`booking_notifications` not joinedloaded** — the ORM class is read directly by SQL in the cron helper; no `Booking.notifications` relationship attribute is added (avoids back-populate confusion for a write-once side-table).

- **No-show cron audit `actor_user_id = NULL`** — the existing `audit_log.actor_user_id` column is nullable. v1.3 `expire_pt_packages` audit emits use the same pattern. Phase 39 documents this in the cron helper docstring so future readers don't add a fake "system user UUID".

- **Idempotency-row insert as POST-send action** — write the row IMMEDIATELY after a successful `SendResult(ok=True)`, before the next iteration. Do NOT batch inserts at end-of-loop (would lose idempotency on cron crash mid-batch). Mirror v1.3 `_send_expiring_notifications` line 1466 discipline.

</specifics>

<deferred>
## Deferred Ideas

### To Phase 40 (Telegram /book + OpenAPI + Verification)
- `/book` command handler + `CallbackQueryHandler` + InlineKeyboard with `BK:{slot_uuid}` callback_data (BOT-01..03)
- `HandlerContext.bookings_service` field (BOT-05)
- Redis update_id dedup `sz:bot:update:{update_id}` (BOT-04)
- Anti-oracle bot reply USING `_BOT_BOOK_DENIED_DM` (Phase 39 creates the constant; Phase 40 wires it into the callback handler)
- OpenAPI byte-stable regen for v1.5 paths (HANDOFF-01)
- `schema.contract.test.ts` `AssertNonNever` forward-guards (HANDOFF-02)
- 6 operator curl scenarios + 2 bot scenarios + cron scenarios (VER-05..07) — VER-07 explicitly runs `run_no_show_cron_once.py` + `run_booking_reminders_once.py` against the live stack
- Milestone verification log entries (VER-08)
- Real-Postgres `asyncio.gather` race test for `mark_no_show_bookings` vs `record_pt_session` — if a hard end-to-end proof is wanted (D-39-18 omits it from Phase 39 by design)

### To v1.5.1 / future patches
- Manual `POST /bookings/{id}/no_show` endpoint — v1.5.1 only if real operational need surfaces (C-10 says cron-only for v1.5; do not anticipate)
- Reverse `no_show → confirmed` reopen flow (PITFALLS Pitfall 9 Option A) — defer to v1.6 if late-arrival reversals become a request
- A/B variants for booking DMs (D-39-04 — single template per kind today)
- `telegram_chat_id` snapshot column on `booking_notifications` (D-39-03 — re-evaluate only if a real support-side question surfaces)
- ARQ enqueue for booking-create/cancel DM dispatch (D-39-09 Option B) — migrate from sync if Phase 40 bot-burst latency becomes a problem

### To Future Milestones
- `booking_confirmed_dm_sent` / `booking_cancelled_dm_sent` audit events — D-39-14 explicitly rejects these as out of scope; revisit if compliance ever requires per-DM audit
- DM-trainer notifications (separate from client DMs) — Phase 39 only DMs the client; trainer-side DMs deferred to v1.6
- Configurable cron schedule (env-driven `CRON_NO_SHOW_HOUR_MSK=23`) — out of scope for v1.5; locked schedule per CRON-01/02
- Multi-language DM templates — Russian-only per project scope

### Reviewed Todos (not folded)
None — no todos surfaced for Phase 39 in `--auto` mode.

</deferred>

---

*Phase: 39-notifications-cron*
*Context gathered: 2026-05-17*
*Mode: --auto (single-pass; downstream agents may override any D-39-NN before plan-phase)*

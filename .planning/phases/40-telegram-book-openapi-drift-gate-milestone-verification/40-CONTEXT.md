# Phase 40: Telegram /book + OpenAPI Drift Gate + Milestone Verification - Context

**Gathered:** 2026-05-18
**Status:** Ready for planning
**Mode:** `--auto` (Claude auto-selected recommended defaults for every gray area; user may override any D-40-NN before `/gsd-plan-phase 40` consumes this file)

<domain>
## Phase Boundary

Phase 40 is the **terminal phase of milestone v1.5**. It ships three orthogonal deliverables that together close the v1.5 contract and prove the milestone is production-ready:

1. **Telegram `/book` flow** — stateless `CommandHandler("book")` + `CallbackQueryHandler(pattern=r"^BK:")` that lets a Telegram-linked client with an active PT-package book one of their trainer's next 5 active slots in a single tap, with anti-oracle DM on every denial path (BOT-01..05).
2. **OpenAPI drift-gate refresh** — single byte-stable regen of `apps/backend/openapi.json` + `packages/api-client/src/schema.d.ts` capturing every v1.5 path landed in Phases 38/39 (`/trainer-slots/*`, `/bookings/*`, `/clients/{id}/bookings`, extended `/pt-packages`/`/pt-sessions`), plus +10 compile-time `AssertNonNever` forward-guards in `schema.contract.test.ts` (HANDOFF-01/02). **Both artifacts are currently frozen at v1.4 / Phase 35 state** — Phase 40 brings them current.
3. **Milestone verification gate** — 6 operator curl scenarios against live `docker compose up` + 2 Telegram sandbox scenarios + 2 cron one-shot scenarios + 4 backend + 1 frontend CI gate captures, recorded verbatim in `.planning/milestones/v1.5-VERIFICATION-LOG.md` with operator sign-off (VER-05..08).

Deliverable scope is exactly the 11 v1.5 requirements `BOT-01..05 + HANDOFF-01..02 + VER-05..08`.

**What ships:**

1. **`apps/backend/app/integrations/telegram/handlers.py`** — APPEND two new handlers:
   - `book_handler(update, context)` — `CommandHandler("book")`: resolves client → active PT-package → top-5 future active slots filtered by `pt_package.trainer_id` (if non-NULL) within next 14 days via `schedule_service.list_slots(...)`; renders `InlineKeyboardMarkup` with vertical button-per-row layout `[label="DD.MM HH:MM — {trainer_name}", callback_data=f"BK:{slot.id}"]`; anti-oracle `_BOT_BOOK_DENIED_DM` on missing-client / no-package / exhausted-package / no-slots.
   - `book_callback_handler(update, context)` — `CallbackQueryHandler(pattern=r"^BK:[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$")`: parses `BK:{slot_uuid}` → calls `bookings_service.create_booking_via_bot(...)` (D-40-04 new entry point) → edits the original message to `BOOKING_CONFIRMED_DM` on success or `_BOT_BOOK_DENIED_DM` on every error path (anti-oracle).
   - Both handlers reuse the existing **`_dedupe_update_id` helper / `sz:bot:update:{update_id}` SET-NX-EX TTL 1h fail-open pattern** (D-20-3) — D-40-08 extracts it to a module-level helper if currently inlined.
2. **`apps/backend/app/integrations/telegram/handlers.py:HandlerContext`** — extend the `NamedTuple` with **2 new fields**: `bookings_service: ModuleType` (for `create_booking_via_bot` dispatch), `schedule_service: ModuleType` (for `list_slots`). `clients_service` + `pt_packages_service` are NOT added — they are reached via the existing Protocol-slot resolvers (`register_client_by_telegram_resolver`, `register_active_pt_package_resolver`) wired in Phase 37 DEBT-06.
3. **`apps/backend/app/main.py`** + **`apps/backend/app/workers/telegram_bot.py:main()`** — both composition roots construct identical `HandlerContext` instances with the 2 new module references (REG-29-03 defensive double-construction lesson). Both files register `book_handler` + `book_callback_handler` on the PTB `Application`.
4. **`apps/backend/app/modules/bookings/service.py`** — APPEND **`create_booking_via_bot(session, *, client_id, slot_id, pt_package_id) -> BookingResponse`** SVC001-owning entry point. Mirrors `create_booking`'s 10-step UoW exactly but:
   - Takes no `CurrentUser` (client self-service path — no authenticated user).
   - Audit payload carries the locked `actor_role='telegram_bot'` literal (registered in `audit_payloads.py` as a new accepted value for `BookingCreatedPayload.actor_role`) so the audit row is traceable to the self-service path without inventing fake user_ids.
   - Same error classes (`SlotNotActiveError`, `BookingAlreadyExistsError`, `TrainerMismatchError`, `PtPackageExhaustedError`, `PtPackageExpiredBeforeSlotError`, `PtPackageNotActiveError`) — handler maps **every one** to `_BOT_BOOK_DENIED_DM` (anti-oracle).
5. **`apps/backend/openapi.json`** + **`packages/api-client/src/schema.d.ts`** — single atomic byte-stable regen (`uv run python -m scripts.export_openapi` + `pnpm --filter @sportzal/api-client codegen`) capturing every Phase 37/38/39 router. **Currently both artifacts are frozen at Phase 35 / v1.4 close (commit `511cbf1`)** — CI `git diff --exit-code` gates have been red for v1.5 paths since Phase 38; Phase 40 brings them back to green.
6. **`packages/api-client/src/schema.contract.test.ts`** — APPEND **+10 compile-time `AssertNonNever`** forward-guards covering: `/api/v1/trainer-slots` GET+POST, `/api/v1/trainer-slots/{slot_id}` GET, `/api/v1/trainer-slots/{slot_id}/cancel` POST, `/api/v1/bookings` POST, `/api/v1/bookings/{booking_id}/cancel` POST, `/api/v1/clients/{client_id}/bookings` GET, `/api/v1/pt-packages` POST extended body (with `trainer_id`), `/api/v1/pt-sessions` POST extended body (with `booking_id`), + body realisation probes for the two new POST request bodies. Running count grows from v1.4's 36 → **46**.
7. **`.planning/milestones/v1.5-VERIFICATION-LOG.md`** — YAML-fronted markdown (mirror v1.4 `v1.4-VERIFICATION-LOG.md` structure exactly): score + 6 curl scenarios with `id/title/via/expected/actual` (publish+list slot, book via reception, concurrent same-slot 201+409, 24h cancel window dual-role, PT-package refund with outstanding booking 409, PT-session record completes booking) + 2 Telegram sandbox scenarios (happy path / anti-oracle path) + 2 cron one-shot runner scenarios + 4 backend CI gate URLs + 1 frontend codegen drift gate URL + final operator sign-off.
8. **`.planning/milestones/v1.5-verification-evidence/`** — verbatim curl transcripts (`*.http`), Telegram screenshots (`telegram/*.png`, chat_ids redacted), cron stdout captures (`crons/*.log`), GHA run URLs in `ci-gates.md`.

**Explicitly out of scope for Phase 40:**

- Admin-web wiring for v1.5 paths — `apps/admin-web/` remains frozen-as-of-v1.3 per the 2026-05-15 pivot. Production frontends are built by the design team outside this repo against the regenerated `schema.d.ts`.
- Online payment at booking time — booking does not charge money; payment for the underlying PT-package is cash via v1.4 flow.
- Reverse `no_show → confirmed` reopen flow — out of scope per Pitfall 9 / locked since Phase 37.
- Manual `POST /bookings/{id}/no_show` admin endpoint — cron-only per C-10 / D-39-XX.
- Group classes / capacity > 1 — milestone-level out-of-scope per PROJECT.md.
- Postman v2.1 collection draft refresh — that belongs to the v1.9 API Handoff milestone (the v1.4 draft in `.planning/handoff/` is intentionally not touched).
- Booking reminders by email — depends on v1.6 email channel.
- The 11 residual DEFER-36-04-A pytest failures + DEFER-36-04-B `ruff format` red — both rolled to v1.9 unless cheap to sweep during 40-04 OpenAPI regen.

</domain>

<decisions>
## Implementation Decisions

All C-01..C-15 milestone-level decisions are locked in `.planning/REQUIREMENTS.md` and are NOT re-decided here. All D-37-NN / D-38-NN / D-39-NN decisions in prior phase CONTEXT.md files remain in force. The decisions below are Phase 40 implementation-level choices made during this auto-discuss pass.

### Module & Plan Structure

#### D-40-01 — Plan breakdown: 5 atomic plans grouped by deliverable type
Phase 40 ships as **5 commit-sized plans**, goal-back from the 4 ROADMAP success criteria. The deliverable cleaves into 3 orthogonal surfaces (bot handlers, OpenAPI artifacts, verification log) which can mostly land in parallel — but `bookings/service.py` and `telegram_bot.py` are shared by 40-01..03 forcing intra-bot serialization.

1. **40-01 handler-context-and-wiring** — extend `HandlerContext` NamedTuple with `bookings_service` + `schedule_service` module references; wire both composition roots (`app/main.py` + `app/workers/telegram_bot.py:main()`) identically (REG-29-03 defensive double-construction); extract `_dedupe_update_id(redis, update_id) -> bool` helper from the existing `checkin_handler` body to a module-level utility (D-40-08) so both `book_handler` and `book_callback_handler` reuse it. Add `pt_packages_service` import in `telegram_bot.py` if missing (DEBT-06 verifies it). NO handler code yet — just the infrastructure surface. Tests: `test_handler_context_double_construction` + `test_dedupe_helper_fail_open`. Covers BOT-04, BOT-05.
2. **40-02 book-command-handler** — NEW `book_handler` in `handlers.py` + `create_booking_via_bot` SVC001 entry point in `bookings/service.py` (D-40-04). Renders InlineKeyboard with up to 5 buttons per BOT-02 anti-oracle algorithm (D-40-05/06/07). Unit tests: `test_book_handler_renders_5_slot_keyboard`, `test_book_handler_anti_oracle_on_missing_pt_package`, `test_book_handler_anti_oracle_on_no_slots`, `test_book_callback_data_byte_length_under_64` (BOT-02 explicit assert), `test_book_handler_dedupe_update_id`. Covers BOT-01 (handler registration), BOT-02 (rendering).
3. **40-03 book-callback-handler** — NEW `book_callback_handler` in `handlers.py`; consumes the `bookings_service.create_booking_via_bot` entry point landed in 40-02. Validates callback_data regex (D-40-09), edits message to `BOOKING_CONFIRMED_DM` on success / `_BOT_BOOK_DENIED_DM` on every error (race-loss, package-issue, slot-already-booked). Tests: `test_callback_happy_path_edits_to_confirmed_dm`, `test_callback_race_loss_edits_to_denied_dm`, `test_callback_invalid_callback_data_silently_dropped`, `test_callback_emits_booking_created_audit_with_via_bot_role`. Covers BOT-03.
4. **40-04 openapi-handoff-refresh** — run `uv run python -m scripts.export_openapi` (regenerates `apps/backend/openapi.json` byte-stably) + `pnpm --filter @sportzal/api-client codegen` (regenerates `packages/api-client/src/schema.d.ts`) + APPEND +10 `AssertNonNever` forward-guards to `schema.contract.test.ts` per D-40-10. Single atomic commit containing all three artifacts (mirror Phase 35 commit `511cbf1` shape) so the drift gate flips green in one step. Integration check: `pnpm --filter @sportzal/api-client test` + `git diff --exit-code` on both artifacts locally. Covers HANDOFF-01, HANDOFF-02.
5. **40-05 milestone-verification** — write `v1.5-VERIFICATION-LOG.md` with operator sign-off; execute 6 curl + 2 Telegram + 2 cron + 5 CI-gate scenarios verbatim against live `docker compose up`; commit transcripts under `.planning/milestones/v1.5-verification-evidence/`. Covers VER-05, VER-06, VER-07, VER-08.

**Why 5 plans (not 4, not 6):** plans 40-01/02/03 share `telegram_bot.py` + `handlers.py` + `bookings/service.py` and must serialize. 40-04 (artifact regen) and 40-05 (verification) are orthogonal — 40-05 must run **last** because it verifies the live stack only after 40-04 commits a green openapi.json. Collapsing 40-02 + 40-03 into one plan would create a 7-deliverable plan (handler + service entry point + callback + 5 test files); splitting matches v1.2 Phase 20 cadence (command handler / callback handler each get their own plan in bot-feature phases).

**Wave layout** (4 waves, mostly serial due to file-overlap on `handlers.py` + `bookings/service.py`):

| Wave | Plans | Reason |
|---|---|---|
| 1 | 40-01 | Infrastructure (HandlerContext + dedup helper + DEBT-06 verify) must land before any handler can reference it |
| 2 | 40-02, 40-04 | 40-02 owns `handlers.py` (`book_handler` only) + `bookings/service.py` (`create_booking_via_bot`); 40-04 owns `openapi.json` + `schema.d.ts` + `schema.contract.test.ts` — disjoint file sets |
| 3 | 40-03 | Adds `book_callback_handler` to `handlers.py` (serial after 40-02 — same-file conflict); depends on `create_booking_via_bot` from 40-02 |
| 4 | 40-05 | Live-stack verification — requires every preceding plan committed + green CI |

Plan-set is **5 commit-sized plans** running across **4 execution waves**.

#### D-40-02 — Handlers live in `app/integrations/telegram/handlers.py` (extend, NOT new file)
The existing `handlers.py` already houses `start_handler` (Phase 7) and `checkin_handler` (Phase 20). `book_handler` + `book_callback_handler` extend the same file rather than a new `book_handlers.py` because:

- All 4 booking-related strings + 1 anti-oracle constant already live in `app/modules/bookings/notifications.py` (D-39-02) — handler file just imports them.
- The D-09 single-owning-module-per-worker exception is documented for the existing file; adding a new file would require a new import-linter relaxation entry.
- The HandlerContext-based wiring + Russian DM copy patterns are mirrored from `checkin_handler`; reading them side-by-side in the same file accelerates code review.
- Phase 20 D-10 narrative addendum (workers→modules edge) covers `bookings_service` + `schedule_service` access from this file without a new contract.

#### D-40-03 — `concurrent_updates=True` preserved — NO `ConversationHandler`
BOT-01 explicitly locks: **stateless** `CommandHandler` + `CallbackQueryHandler` only. NO `ConversationHandler`. Rationale (C-12 anti-oracle path):

- `ConversationHandler` introduces per-user in-process state which serializes updates for that user inside PTB and breaks `concurrent_updates=True` (PTB-22 docs §`ConversationHandler.block`).
- A second `/book` issued before a first callback tap should re-render the keyboard with **fresh** slots (the previous keyboard is now stale Telegram-side anyway). Stateless handlers achieve this for free.
- Race-loss between two clients tapping the same slot is resolved at the DB layer by the partial UNIQUE `(slot_id) WHERE status='confirmed'` constraint (C-02 / Phase 38) — handler-level state would only hide the race, not prevent it.
- Test discipline: `test_two_concurrent_book_callbacks_one_wins` will assert exactly one DB row + one anti-oracle DM.

### Bot Service Entry Point

#### D-40-04 — NEW `bookings_service.create_booking_via_bot(session, *, client_id, slot_id, pt_package_id)` — mirror v1.2 D-10 `create_visit_self_checkin` shape
The existing `bookings_service.create_booking(session, actor, data)` requires a `CurrentUser` (Protocol: `id: UUID + role: Role`). The Telegram bot has NO authenticated user — only a `client_id` resolved from `telegram_user_id` via the Phase 7 resolver. Decision: **add a parallel self-service entry point** rather than inventing fake `CurrentUser` instances or threading a `role='client'` value through the type system.

Pattern mirror: v1.2 Phase 20 D-10 split `visits_service.check_in(...)` (reception path, takes `CurrentUser`) from `visits_service.create_visit_self_checkin(...)` (bot self-service path, takes `client_id`). v1.5 mirrors that split for bookings.

Implementation:

```python
async def create_booking_via_bot(
    session: AsyncSession,
    *,
    client_id: UUID,
    slot_id: UUID,
    pt_package_id: UUID,
) -> BookingResponse:
    """Telegram /book self-service entry — D-40-04.

    Same 10-step UoW as create_booking. Audit payload carries
    actor_role='telegram_bot' (locked literal in audit_payloads.py).
    Raises the same domain errors as create_booking — the bot
    handler maps every error class to _BOT_BOOK_DENIED_DM
    (anti-oracle C-12).
    """
    # 1. resolve slot (SlotByIdResolver Protocol slot)
    # 2. resolve client's active pt_package — must match pt_package_id
    #    (defensive; the bot already gated on this when rendering the
    #    keyboard, but the row could have been cancelled / exhausted
    #    in the gap between render and tap).
    # 3-9. same checks as create_booking
    # 10. audit_emit("booking_created", actor_user_id=None,
    #                client_id=str(client_id), via='telegram_bot', ...)
    # 11. await session.commit() — SVC001 gate
```

The new path is **SVC001-owning** (commits its own UoW). Existing `create_booking` is unchanged.

#### D-40-05 — Audit payload carries `actor_role='telegram_bot'` (new locked literal); `actor_user_id=None` is acceptable
Phase 37 INFRA-24 locked `BookingCreatedPayload` shape. v1.5 D-40-04 needs an audit row for self-service bookings without inventing a fake `actor_user_id`. Mechanism:

- Extend `BookingCreatedPayload.actor_role: Literal['reception', 'owner']` → `Literal['reception', 'owner', 'telegram_bot']` (Phase 37 already uses `Literal` discriminants — see `audit_payloads.py:200-220` pattern).
- `actor_user_id: str | None` — currently `str` required; relax to `str | None` for `telegram_bot` rows only via a Pydantic validator. NULL `actor_user_id` distinguishes "no authenticated operator" from "system" rows.
- Existing `LOCKED_AUDIT_EVENTS` frozenset is **unchanged** — `booking_created` is already registered (Phase 37 / Phase 38). Only the payload schema relaxes.

If Phase 37's `BookingCreatedPayload` proves stricter than this (research finding for the planner), the alternative is a **separate** event `booking_self_booked_via_bot` — but that would expand `LOCKED_AUDIT_EVENTS` from 56 → 57 and require a new entry in `audit_payloads.py`. Default is the relaxation; the planner picks the alternative only if the relaxation triggers other constraint failures.

### Keyboard Rendering

#### D-40-06 — Slot list: reuse `schedule_service.list_slots(session, query)` — NO new resolver
The `SlotListQuery` schema (`apps/backend/app/modules/schedule/schemas.py:124`) already supports `trainer_id` + `from_time` + `to_time` + `status` filters with the right defaults (`from_time → now`, `to_time → now + 14d Europe/Moscow`, `status → SlotStatus.ACTIVE`). The bot handler calls `schedule_service.list_slots(...)` directly via `ctx.schedule_service` with `trainer_id=pt_package.trainer_id` (None means "any trainer" — pass `None`), `page=1`, `page_size=5`.

Rationale:

- No new Protocol-slot resolver needed — the existing `schedule_service` module reference in `HandlerContext` (D-40-08) covers it.
- The query already paginates; bot just consumes `.items[:5]` ordered by `start_time ASC` (existing repository order).
- v1.5 SLOT-08 explicitly states "the same endpoint feeds the Telegram bot `/book` discovery flow in Phase 40" — using the public service entry point is the locked path.

#### D-40-07 — InlineKeyboard layout: vertical, 1 button per row, label `"DD.MM HH:MM — {trainer_name}"`
BOT-02 specifies up to 5 buttons but does not lock the layout. Decision: **1 button per row** (5 rows total, max). Rationale:

- Telegram InlineKeyboard rows can hold multiple buttons but mobile rendering wraps labels — short labels are fine side-by-side, but `"DD.MM HH:MM — Иван Иванов"` is ~25 chars and pairing 2 per row truncates trainer names on common mobile widths.
- Vertical-only layout is unambiguous for screen-readers and matches the v1.3 freeze-section confirm-dialog button stack pattern in admin-web (consistent across the product).
- callback_data byte length is the limit, not row width: `BK:{36-char-uuid}` = **39 bytes** (BOT-02 explicit assert) — well under Telegram's 64-byte limit (24 bytes of headroom for future v1.6+ extensions if e.g. `BK:{slot}:{nonce}` becomes needed).

Label format: `f"{start_dt.astimezone(MOSCOW_TZ):%d.%m %H:%M} — {trainer.full_name}"` (Russian display style, MSK timezone). When `pt_package.trainer_id is not None` the trainer is fixed and the label could omit the name — but keep it for consistency across the package-has-trainer / package-any-trainer paths (the latter shows different trainers per row).

#### D-40-08 — `_dedupe_update_id` is a module-level helper, extracted in plan 40-01
Phase 20 inlined the dedup logic inside `checkin_handler` (`handlers.py:258-279`). Phase 40 has two new handlers that need the same logic. Decision: **extract to a module-level `async def _dedupe_update_id(redis: Redis, update_id: int) -> bool`** helper (returns `True` if this is the first time we see the id, `False` if dedup hit, also `True` on Redis error to preserve the **fail-open** D-20-3 invariant).

Single source of truth defeats drift: the v1.5 anti-oracle bot must not develop a different dedup behaviour than v1.2 self-checkin. Plan 40-01 lands this extraction as a pure refactor with a `test_dedupe_helper_fail_open` test before the new handlers consume it.

Key prefix `sz:bot:update:{update_id}` is unchanged.

#### D-40-09 — Callback data regex validated strictly; bad data silently dropped (no DM)
Pattern: `r"^BK:[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$"` (PTB's `CallbackQueryHandler(pattern=...)` already filters on regex match — invalid callback_data never reaches the handler). Anything that DOES reach `book_callback_handler` is structurally valid.

If the slot UUID is structurally valid but resolves to a non-existent / non-active slot, edit the message to `_BOT_BOOK_DENIED_DM` (anti-oracle — same DM as race-loss, same DM as package-exhausted).

NO error DM for parse failures: a callback_data shape mismatch indicates client tampering or a stale keyboard from a code revision — silently drop + structlog WARNING `book_callback_invalid_data` with `update_id` + `data_prefix=data[:10]`.

#### D-40-10 — Race-loss + every domain error → `_BOT_BOOK_DENIED_DM` (anti-oracle)
The `create_booking_via_bot` entry point can raise 7 domain errors: `SlotNotFoundError`, `SlotNotActiveError`, `BookingAlreadyExistsError` (partial UNIQUE race-loss), `TrainerMismatchError`, `PtPackageNotActiveError`, `PtPackageExhaustedError`, `PtPackageExpiredBeforeSlotError`. All 7 → `_BOT_BOOK_DENIED_DM` (single string, no discriminating info).

Anti-oracle rationale (C-12): a real attacker probing the bot must not be able to distinguish "your package expired" from "this slot was just taken by someone else". The DM string contains no placeholder substitution — every denial reads identically.

Logging is the operator escape hatch: structlog WARNING `book_callback_denied` carries the specific error class name (e.g., `error_class='BookingAlreadyExistsError'`) for support debugging without leaking to the user.

### OpenAPI Drift Gate

#### D-40-11 — Single atomic commit: regen both artifacts + extend contract test in one commit
Mirror Phase 35 commit `511cbf1` shape: one feature commit holding `apps/backend/openapi.json` + `packages/api-client/src/schema.d.ts` + `packages/api-client/src/schema.contract.test.ts` + the runner output proof. The drift gates in CI both check `git diff --exit-code` — splitting the regen across 2 commits would leave the intermediate commit red on one of the two gates.

**Confirmed prerequisite state** (from current main HEAD scan 2026-05-18):
- `apps/backend/openapi.json` — 5479 lines, **0 occurrences** of `trainer-slots` / `bookings` / booking-related schemas. Frozen at Phase 35 / commit `511cbf1`.
- `packages/api-client/src/schema.d.ts` — 4086 lines, same frozen state.
- `packages/api-client/src/schema.contract.test.ts` — 36 `AssertNonNever` assertions, all v1.0–v1.4 paths.

After Phase 40 regen:
- `openapi.json` expected to gain `/api/v1/trainer-slots` (4 ops), `/api/v1/bookings` (3+ ops), `/api/v1/clients/{client_id}/bookings` (1 op), extended `/api/v1/pt-packages` POST body (with `trainer_id`), extended `/api/v1/pt-sessions` POST body (with `booking_id`).
- `schema.d.ts` mirrors the same path additions.
- `schema.contract.test.ts` gains **+10** assertions per D-40-11 list below.

Both CI drift gates (`apps/backend/openapi.json` + `packages/api-client/src/schema.d.ts`) flip green in this single commit.

#### D-40-12 — Forward-guard list: +10 `AssertNonNever` (running count 36 → 46)
Exact list to append to `packages/api-client/src/schema.contract.test.ts`:

```ts
// v1.5 — Phase 40 HANDOFF-02
type _TrainerSlotsListGet = AssertNonNever<paths['/api/v1/trainer-slots']['get']>
type _TrainerSlotsCreate = AssertNonNever<paths['/api/v1/trainer-slots']['post']>
type _TrainerSlotItemGet = AssertNonNever<paths['/api/v1/trainer-slots/{slot_id}']['get']>
type _TrainerSlotCancel = AssertNonNever<
  paths['/api/v1/trainer-slots/{slot_id}/cancel']['post']
>
type _BookingsCreate = AssertNonNever<paths['/api/v1/bookings']['post']>
type _BookingCancel = AssertNonNever<
  paths['/api/v1/bookings/{booking_id}/cancel']['post']
>
type _ClientBookingsList = AssertNonNever<
  paths['/api/v1/clients/{client_id}/bookings']['get']
>
type _PtPackagesSalePostBody = AssertNonNever<
  paths['/api/v1/pt-packages']['post']['requestBody']
>
type _PtSessionsRecordPostBody = AssertNonNever<
  paths['/api/v1/pt-sessions']['post']['requestBody']
>
type _TrainerSlotsListOkRealised = AssertNonNever<
  paths['/api/v1/trainer-slots']['get']['responses']['200']
>
```

10 entries. If `GET /api/v1/bookings/{booking_id}` (single-item read) exists in the regenerated artifact — research finding for the planner — it gets an 11th line, but the locked count is +10 per HANDOFF-02 estimate. Planner may adjust ±1 based on router introspection in Phase 38 plans.

### Milestone Verification

#### D-40-13 — Verification log format mirrors `v1.4-VERIFICATION-LOG.md` byte-for-byte
The Phase 36 / v1.4 verification log is the locked template (`.planning/milestones/v1.4-VERIFICATION-LOG.md`). v1.5 mirrors it exactly:

- YAML frontmatter: `milestone`, `gathered`, `mode`, `score`, `gate_pass`, `signed_off_by`, `signed_off_at`.
- `## Operator scenarios` H2 with one block per scenario (`id`, `title`, `via`, `expected`, `actual`, `notes` keys; `via: curl|telegram|cron|ci`).
- `## Race tests`, `## CI gates`, `## Test suites`, `## Deferred items`, `## Handoff artifacts`, `## Hand-off`, `### Final disposition (operator <email>)` sections.
- 10 verification scenarios total (6 curl + 2 Telegram + 2 cron), numbered `01..10`.

Anything that breaks the v1.4 template shape requires an explicit decision in this CONTEXT.md — Phase 40 has none.

#### D-40-14 — 6 curl operator scenarios — locked list
From VER-05 verbatim, ordered for hermetic re-run (each scenario cleans up its own state):

| # | Scenario | Path(s) | Expected |
|---|---|---|---|
| 01 | Publish slot + list slots | POST /trainer-slots → 201; GET /trainer-slots?trainer_id=... → 200 with the published slot in items | New slot visible in list within 5s |
| 02 | Book slot via reception | POST /bookings (with Idempotency-Key) → 201 status=confirmed | Slot status flips to `booked`; pt_package.sessions_remaining unchanged |
| 03 | Concurrent same-slot booking | 2× parallel POST /bookings same slot_id different clients | exactly one 201, one 409 `slot_not_available` |
| 04 | 24h cancel window dual-role | reception POST /bookings/{id}/cancel <24h before slot → 409 `cancel_window_exceeded`; owner same call → 200 status=cancelled | Reception rejected, owner succeeds, audit row carries actor_role |
| 05 | Refund PT-package with outstanding booking | POST /pt-packages/{id}/refund while a confirmed booking exists → 409 `outstanding_booking_must_cancel_first` | Refund blocked; cancel booking first then refund succeeds |
| 06 | PT-session record completes booking | POST /pt-sessions with booking_id=... → 201; GET /bookings/{id} → status=completed | Booking transitions confirmed → completed atomically; sessions_remaining decremented by exactly 1 |

#### D-40-15 — Telegram sandbox: real BotFather sandbox bot + real test client account; chat IDs redacted in screenshots
VER-06 requires 2 Telegram scenarios run against a real bot (not stubs). Setup:

- `.env.compose.verification` (gitignored) holds the sandbox bot token + the operator's linked test client_id.
- Run `docker compose up` with that env file; execute `/book` from the test Telegram account.
- Capture screenshots: keyboard render, after-tap confirmation, anti-oracle DM. Redact chat IDs (any 9-10 digit number after `chat_id`).
- Commit under `.planning/milestones/v1.5-verification-evidence/telegram/01_happy_path_keyboard.png` + `02_happy_path_confirmed.png` + `03_anti_oracle_denied.png`.

If real-Telegram setup is blocked for the operator (rate-limit, sandbox quota), fallback is **scripted PTB integration test** — but the deliverable explicitly requires "Telegram sandbox smoke" (BOT-VER copy in REQUIREMENTS), so the scripted path requires an explicit operator deviation note in the verification log.

#### D-40-16 — Cron operator scenarios via one-shot runners (existing scripts from Phase 39)
Phase 39 already shipped `apps/backend/scripts/run_no_show_cron_once.py` + `apps/backend/scripts/run_booking_reminders_once.py`. Phase 40 just *runs* them as VER-07 verification:

- VER-07(a) `run_no_show_cron_once.py`: seed an overdue confirmed booking via direct SQL, run the script, assert booking.status='no_show' + 1 new `booking_no_show` audit row.
- VER-07(b) `run_booking_reminders_once.py`: seed a booking with start_time ≈ now+24h, run the script, assert 1 DM sent + 1 `booking_notifications(kind='reminder_24h')` row inserted; re-run immediately, assert 0 DMs sent + 0 new rows (idempotency proof).

Capture stdout + DB query outputs (`SELECT * FROM bookings WHERE id=...` before/after) as `.planning/milestones/v1.5-verification-evidence/crons/{run_no_show,run_reminders}.log`.

#### D-40-17 — CI gates: 4 backend + 1 frontend = 5 gates evidence-captured
VER-08 locks "all 4 backend CI gates" (ruff, mypy strict, pytest, OpenAPI drift). Add the frontend codegen drift gate (`schema.d.ts`) — also locked in CI per `.github/workflows/ci.yml:114-117`. Evidence shape (mirror v1.4 line 545):

- GHA run URL for the HEAD commit after 40-04 (regen) lands.
- 5 gate names + status: `backend/ruff`, `backend/mypy-strict`, `backend/pytest`, `backend/openapi-drift`, `frontend/schema-drift`.
- Operator confirms green at `https://github.com/<repo>/actions` for the captured commit hash.

Pytest count expected to grow: Phase 37 = 729 (pre-v1.5 baseline), + 9 Phase 38 booking-create tests + 6 Phase 38 race tests + 8 Phase 39 cron tests + 12 Phase 40 bot tests ≈ **764**. Exact count is captured at run time; the verification log records the delta.

#### D-40-18 — Deferred items rolled forward to v1.9 in the verification log
Phase 40 does NOT close DEFER-36-04-A (11 pytest failures) or DEFER-36-04-B (`ruff format` red on 123 files) unless the planner identifies a cheap inline sweep during 40-04. Both are explicitly tagged in v1.5-VERIFICATION-LOG.md as rolled to **v1.9 API Handoff + Production Hardening**. The score line acknowledges the carry-over (mirror v1.4 line 7 phrasing).

### Claude's Discretion

The following details are left to the planner's research and codebase-mapping phase — they don't change deliverable scope and don't need user pre-decision:

- Exact line number of the `_dedupe_update_id` extraction target in `handlers.py` (currently inlined ~`checkin_handler:258-279`).
- Whether `GET /api/v1/bookings/{booking_id}` exists in the regenerated openapi.json (research finding determines if D-40-12 adds 10 or 11 assertions).
- Whether `BookingCreatedPayload.actor_user_id` is currently `str` or `str | None` (Phase 37 INFRA-24 lock — research determines if D-40-05 needs a Pydantic validator change or just a Literal expansion).
- Whether `register_top_active_slots_resolver` style alternative to direct `schedule_service.list_slots` is preferred — D-40-06 picks the direct call but a Protocol resolver is acceptable if the planner finds an import-linter conflict.
- The exact set of audit_payload fields for `actor_role='telegram_bot'` rows (the locked literal change requires registry test fixture updates — research finds all consumer test sites).

</decisions>

<canonical_refs>
## Canonical References

**Downstream agents MUST read these before planning or implementing.**

### Milestone-Level Lock
- `.planning/REQUIREMENTS.md` lines 96-114 — BOT-01..05 + HANDOFF-01..02 + VER-05..08 verbatim spec.
- `.planning/ROADMAP.md` lines 165-174 — Phase 40 4 success criteria.
- `.planning/PROJECT.md` lines 60-75 — v1.5 milestone goal + out-of-scope.

### Prior Phase Decisions (still in force)
- `.planning/phases/37-foundations-bedrock/37-CONTEXT.md` — D-37-06 Protocol-slot pattern; `BookingCreatedPayload` audit lock (INFRA-24).
- `.planning/phases/38-schedule-module-booking-core/38-CONTEXT.md` — D-38-02..D-38-19 booking semantics, FSM guard, partial UNIQUE race, validity-window guard.
- `.planning/phases/39-notifications-cron/39-CONTEXT.md` — D-39-02 `notifications.py` co-location; D-39-04 single-template-per-kind; `_BOT_BOOK_DENIED_DM` constant location.

### Codebase (Phase 40 must read)
- `apps/backend/app/integrations/telegram/handlers.py` — existing `HandlerContext` NamedTuple, `start_handler` + `checkin_handler` precedent, `_dedupe_update_id` inlined block.
- `apps/backend/app/workers/telegram_bot.py` — composition root for the bot process; resolver registrations; `HandlerContext` construction site.
- `apps/backend/app/main.py` lines 159-214 — FastAPI composition root; second `HandlerContext` construction (REG-29-03 double-wiring).
- `apps/backend/app/modules/bookings/service.py` — `create_booking` (line 627) + `cancel_booking` (line 819) entry points; `_dispatch_booking_dm` helper (Phase 39); `_send_booking_reminders` cron helper.
- `apps/backend/app/modules/bookings/notifications.py` — 5 locked Russian DM templates + `_BOT_BOOK_DENIED_DM` anti-oracle constant.
- `apps/backend/app/modules/schedule/service.py` line 226 — `list_slots(session, query)` public entry; signature locked.
- `apps/backend/app/modules/schedule/schemas.py` line 124 — `SlotListQuery` (trainer_id + from_time + to_time + status + pagination).
- `apps/backend/app/core/dependencies.py` lines 33-50, 167+, 236+, 472+ — `CurrentUser` Protocol + 4 register_*_resolver entries needed by the bot.
- `apps/backend/app/core/audit_payloads.py` — `BookingCreatedPayload` schema + Literal discriminants for D-40-05 relaxation.
- `apps/backend/app/integrations/telegram/bot.py` — `build_application` factory (`concurrent_updates=True` config).

### Artifacts (drift-gate state)
- `apps/backend/openapi.json` (5479 lines, frozen at Phase 35 `511cbf1`) — pre-regen baseline.
- `packages/api-client/src/schema.d.ts` (4086 lines) — pre-regen baseline.
- `packages/api-client/src/schema.contract.test.ts` — 36 `AssertNonNever` baseline; +10 append target.
- `apps/backend/scripts/export_openapi.py` — byte-stable regen entry point.

### CI & Operator Runbook
- `.github/workflows/ci.yml` lines 38-117 — 4 backend + 1 frontend drift gate; pytest gate; ruff + mypy strict.
- `.planning/milestones/v1.4-VERIFICATION-LOG.md` — locked structural template for `v1.5-VERIFICATION-LOG.md`.
- `apps/backend/scripts/run_no_show_cron_once.py` — VER-07(a) one-shot runner.
- `apps/backend/scripts/run_booking_reminders_once.py` — VER-07(b) one-shot runner.

### Pattern Mirrors (precedent for new decisions)
- v1.2 Phase 20 `visits_service.create_visit_self_checkin` — pattern for D-40-04 self-service entry point.
- v1.4 Phase 35 commit `511cbf1` — pattern for D-40-11 single-atomic-artifact-commit.
- v1.4 Phase 36 verification log — pattern for D-40-13.

</canonical_refs>

<code_context>
## Existing Code Insights

### Reusable Assets

- **`HandlerContext` NamedTuple** (`integrations/telegram/handlers.py:51`) — 5 existing fields (`session_factory`, `telegram_service`, `sender`, `visits_service`, `redis`). Phase 40 extends with `bookings_service`, `schedule_service`. NamedTuple immutability means every consumer test fixture needs the 2 new positional args (~5-7 test fixture files).
- **`_dedupe_update_id` (inlined)** (`integrations/telegram/handlers.py:258-279`) — Redis SET-NX-EX `sz:bot:update:{update_id}` TTL 1h fail-open. Extract verbatim to a module-level helper in plan 40-01 — zero behaviour change.
- **`schedule_service.list_slots(session, query)`** (`modules/schedule/service.py:226`) — already returns `PaginatedData[SlotResponse]` with the right defaults; consume `.items[:5]` directly.
- **`register_active_pt_package_resolver`** — wired in both `app/main.py:197` AND `workers/telegram_bot.py:77` (Phase 37 DEBT-06 closed). Bot handler reads via the existing module-level slot.
- **`register_client_by_telegram_resolver`** — same double-wiring (`app/main.py:159` + `workers/telegram_bot.py:68`).
- **5 locked Russian DM strings** (`modules/bookings/notifications.py`) — Phase 39 OWNER-COPY-LOCK signed-off; Phase 40 imports `BOOKING_CONFIRMED_DM` + `_BOT_BOOK_DENIED_DM` only.
- **`render_booking_confirmed_dm(client_name, trainer_name, slot_start_msk)`** (`modules/bookings/notifications.py:38`) — Phase 40 callback handler calls this on success path.
- **PTB stub patterns** — `tests/integration/telegram_bot/` (Phase 7/20) uses `unittest.mock.AsyncMock` for `Bot` and constructs synthetic `Update` objects; bot handler tests in 40-02/03 follow the same pattern.

### Established Patterns

- **C-12 anti-oracle** — every bot denial DM is the same string; structlog WARNING carries the discriminating error class for support debugging.
- **REG-29-03 double-wiring** — every resolver and every HandlerContext construction lives in BOTH `app/main.py` AND `app/workers/telegram_bot.py:main()` with identical args. Phase 40 tests assert this for the 2 new HandlerContext fields.
- **D-09 worker→modules edge** — `workers/telegram_bot.py` and `integrations/telegram/handlers.py` may import `app.modules.bookings.service` + `app.modules.schedule.service` because the bot worker is a single-owning-module-per-worker exception (already documented in `app/workers/__init__.py:1-21`).
- **Self-service entry point split** — visits Phase 20 D-10 split `check_in` (reception, CurrentUser) from `create_visit_self_checkin` (bot, client_id). D-40-04 mirrors exactly.
- **Atomic-after-DM** (Phase 7 D-11) — bot handler patterns generally send the DM AFTER the DB commit; for `/book` callback the order is DB commit → message edit (Telegram render). On `editMessageText` failure the booking is already committed — log WARNING, no rollback (the booking is valid; the user just sees the stale keyboard).
- **Single atomic OpenAPI commit** — Phase 35 `511cbf1` shape: `openapi.json` + `schema.d.ts` + (optionally) `schema.contract.test.ts` in one commit; locks the drift gates green in one transition.
- **YAML-fronted verification log** — Phase 36 `v1.4-VERIFICATION-LOG.md` structure carries over verbatim.

### Integration Points

- **`HandlerContext` extension** — `app/main.py:159-214` + `app/workers/telegram_bot.py:99-105`. Add `bookings_service=bookings_service_module` + `schedule_service=schedule_service_module` at both sites.
- **Handler registration** — `app/workers/telegram_bot.py:106-110` (existing `build_application(handlers=[...])` call). Plan 40-02 appends `("book", book_handler)`; plan 40-03 appends a `CallbackQueryHandler(book_callback_handler, pattern=r"^BK:")` entry (the `handlers` arg in `build_application` accepts both shapes — research-confirm at plan time).
- **Audit emit** — `bookings/service.py:create_booking_via_bot` emits `booking_created` with `actor_role='telegram_bot'` literal. Existing `audit.emit` AST literal-string gate accepts this once the Literal in `audit_payloads.py` is expanded (D-40-05).
- **Test seam** — `tests/integration/telegram_bot/test_book_command.py` (NEW), `tests/integration/telegram_bot/test_book_callback.py` (NEW), `tests/unit/bookings/test_create_booking_via_bot.py` (NEW).
- **CI** — no changes; existing `.github/workflows/ci.yml` already exercises both drift gates and will flip green after 40-04 commits the regenerated artifacts.

</code_context>

<specifics>
## Specific Ideas

- **The 6 curl operator scenarios are locked verbatim from VER-05** — no reordering. Each scenario must be hermetic for re-run (40-05 plan ships an `apps/backend/Makefile` `verify` target or shell recipe that resets state between scenarios).
- **Telegram sandbox proof requires real Telegram screenshots** — no PTB-mock fallback unless the operator can't authenticate against BotFather sandbox (in which case explicit deviation note required).
- **Anti-oracle DMs must read identically** — `_BOT_BOOK_DENIED_DM` is one byte-stable string. The unit test `test_anti_oracle_dm_byte_stable` asserts no f-string-style placeholder ever lands in this constant.
- **`actor_role='telegram_bot'` is the chosen literal** — not `'client'`, not `'bot'`, not `'self_service'`. Locked here so the audit reader query (v1.8 future milestone) can filter by exact match.
- **Plan 40-05's verification log must include the SHA of the commit captured for CI evidence** — operator paste from `gh run view` output, mirror v1.4 line 545 pattern.

</specifics>

<deferred>
## Deferred Ideas

- **`POST /api/v1/bookings/{id}/no_show` admin endpoint** — out of scope per C-10; no manual no-show flag. Defer indefinitely unless cron proves unreliable.
- **Reverse `no_show → confirmed` reopen flow** — out of scope per Pitfall 9.
- **Postman v2.1 collection refresh** — belongs to v1.9 API Handoff milestone.
- **DEFER-36-04-A (11 pytest failures)** — rolled to v1.9 unless cheap inline sweep during 40-04.
- **DEFER-36-04-B (`ruff format` red on 123 files)** — rolled to v1.9.
- **Booking email reminders** — depends on v1.6 email channel.
- **`A/B` anti-oracle variants for booking DMs** — D-39-04 rejected for v1.5; revisit in v1.6+ if fingerprinting concern surfaces.
- **`register_top_active_slots_resolver` Protocol-slot alternative** — D-40-06 picks direct `schedule_service.list_slots` call; revisit if import-linter conflicts surface.
- **`GET /api/v1/bookings/{booking_id}` single-item read endpoint** — not in VER-05; if it doesn't exist in current code, the planner notes whether to add or skip (out of scope for Phase 40 per ROADMAP).
- **Trainer payroll / commission per session** — out of scope until ≥ v1.8.
- **Production frontend admin-web wiring for v1.5 paths** — frozen per the 2026-05-15 pivot; design-team integration in v2.0.

</deferred>

---

*Phase: 40-Telegram /book + OpenAPI Drift Gate + Milestone Verification*
*Context gathered: 2026-05-18*

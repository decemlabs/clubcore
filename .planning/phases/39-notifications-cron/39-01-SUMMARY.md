---
phase: 39-notifications-cron
plan: 01
subsystem: notifications

tags: [telegram, copy, i18n, russian, anti-oracle, str-format, bookings]

# Dependency graph
requires:
  - phase: 27-notifications
    provides: "Owner copy-lock sign-off discipline (D-27-OWNER-COPY-LOCK), per-line `# noqa: E501, RUF001` convention, render-helper signature shape from `app/integrations/telegram/copy.py`"
  - phase: 38-bookings-api
    provides: "Bookings module skeleton (`app/modules/bookings/`) that now owns booking DM copy per D-39-02"
provides:
  - "4 locked Russian DM templates: BOOKING_CONFIRMED_DM, BOOKING_CANCELLED_BY_CLIENT_DM, BOOKING_CANCELLED_BY_OWNER_DM, BOOKING_REMINDER_24H_DM (NOTIFY-01)"
  - "1 anti-oracle constant `_BOT_BOOK_DENIED_DM` with no placeholders covering all bot /book negative outcomes (NOTIFY-02, C-12)"
  - "4 render_*_dm helpers using `str.format(**kwargs)` so unknown placeholders raise KeyError at test time (D-39-04)"
  - "Owner copy-lock sign-off block (this file's `## Owner Copy-Lock Sign-off` section); future copy edits require a NEW sign-off entry"
affects: [39-02-bookings-create-cancel-dm, 39-04-bookings-reminder-24h-cron, 40-telegram-bot]

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "Locked-copy module per domain: booking DM strings live in `app/modules/bookings/notifications.py` (D-39-02), not in the shared `app/integrations/telegram/copy.py`. Phase 18 D-09 single-owning-module-per-worker exception permits both the bookings worker and the Phase 40 Telegram bot to import this module."
    - "str.format-not-f-string discipline: render helpers use `BOOKING_*_DM.format(**kwargs)` so any unknown placeholder key raises `KeyError` loud at test time. The regression sentinel `test_render_raises_keyerror_when_template_has_unknown_placeholder` monkeypatches a template with `{unknown_key}` to lock the discipline forever."
    - "Anti-oracle single-string discipline (C-12 / NOTIFY-02): one `_BOT_BOOK_DENIED_DM` constant covers ALL negative outcomes of the bot /book flow (no active PT-package / no slots / client not linked) with NO placeholders and NO failure-cause distinction. Smoke tests assert non-empty + no `{` `}` characters."

key-files:
  created:
    - "apps/backend/app/modules/bookings/notifications.py — 4 BOOKING_*_DM Final[str] templates + `_BOT_BOOK_DENIED_DM` + 4 render_*_dm helpers (91 lines)"
    - "apps/backend/tests/unit/test_booking_notifications_copy.py — 7 unit tests: 4 substitution + 1 KeyError lock + 2 anti-oracle smoke (95 lines)"
  modified: []

key-decisions:
  - "Single template per kind (D-39-04, NO A/B variants): booking surface is one-shot per booking — A/B fingerprinting concern from Phase 27 expiring-notifs (recurring per client) does NOT apply here. No `pick_variant(client_id)` helper, no `UUID`/`date` imports."
  - "Module location D-39-02: booking DM copy lives in `app/modules/bookings/notifications.py`, not in `app/integrations/telegram/copy.py`. Booking domain owns its own DM templates."
  - "Caller pre-formats `slot_start_msk` (D-39-11): renderers accept a pre-formatted `str` placeholder; `bookings/service.py` builds it via `slot.start_time.astimezone(MOSCOW_TZ).strftime('%d.%m.%Y %H:%M')` so the notifications module stays free of timezone dependencies."
  - "Owner copy-lock auto-approved under `--auto` orchestration mode: project owner is also the operator and the developer (single-owner Sportzal pet project per PROJECT.md), so auto-approval is the expected default. Sign-off recorded below for audit."

patterns-established:
  - "Per-domain locked-copy module: any new domain (Phase 40 bot, future PT-package notifications, etc.) that ships locked Russian DM text gets its own `<domain>/notifications.py` rather than centralizing into `app/integrations/telegram/copy.py`."
  - "Owner copy-lock comment lifecycle: every locked string carries a per-line trailing comment that flips from `# OWNER-COPY-LOCK pending — see {summary}.md` to `# OWNER-COPY-LOCK signed-off YYYY-MM-DD — see {summary}.md` at sign-off. Grep `pending` count == 0 + `signed-off` count == constant count is the automated lock gate (plan 39-01 task 3 `<verify>`)."
  - "Anti-oracle constant naming: leading underscore (`_BOT_BOOK_DENIED_DM`) signals 'consumed by another module (Phase 40 bot) but lives here as the single source of truth'."

requirements-completed: [NOTIFY-01, NOTIFY-02]

# Metrics
duration: ~8min
completed: 2026-05-17
---

# Phase 39 Plan 01: Booking Notifications Copy Substrate Summary

**4 locked Russian booking DM templates + 1 anti-oracle `_BOT_BOOK_DENIED_DM` constant in `app/modules/bookings/notifications.py`, guarded by 4 `str.format`-based render helpers and 7 unit tests including a KeyError regression sentinel.**

## Performance

- **Duration:** ~8 min (single worktree agent, --auto mode)
- **Completed:** 2026-05-17
- **Tasks:** 3 (2 auto + 1 checkpoint:human-verify auto-approved)
- **Files created:** 2
- **Files modified:** 0

## Accomplishments

- Shipped the single source of truth for every Phase 39 booking-event Telegram string: 4 locked Russian DM templates (`BOOKING_CONFIRMED_DM`, `BOOKING_CANCELLED_BY_CLIENT_DM`, `BOOKING_CANCELLED_BY_OWNER_DM`, `BOOKING_REMINDER_24H_DM`) covering NOTIFY-01.
- Shipped the `_BOT_BOOK_DENIED_DM` anti-oracle constant required by NOTIFY-02 — single Russian line covering all negative outcomes of the Phase 40 bot `/book` flow with no failure-cause disclosure (C-12).
- 4 `render_*_dm(*, client_name, trainer_name, slot_start_msk) -> str` helpers using `str.format(**kwargs)` per D-39-04 — unknown placeholder keys raise `KeyError` instead of being silently swallowed.
- Locked the str.format-not-f-string discipline with a forever-test regression sentinel (`test_render_raises_keyerror_when_template_has_unknown_placeholder`) that monkeypatches a template with `{unknown_key}`.
- Owner copy-lock sign-off block recorded below (per S8 / mirror of v1.3 D-27-OWNER-COPY-LOCK); all 5 per-line `# OWNER-COPY-LOCK pending` comments in `notifications.py` flipped to `# OWNER-COPY-LOCK signed-off 2026-05-17`.

## Task Commits

1. **Task 1: Create notifications module with locked copy + render helpers** — `78e1f09` (feat)
2. **Task 2: Unit tests for renderers + anti-oracle constant** — `c2701d5` (test)
3. **Task 3: Owner copy-lock sign-off (S8 discipline)** — committed alongside this SUMMARY.md as part of plan metadata (per-line comment flip + this sign-off block)

## Files Created/Modified

- `apps/backend/app/modules/bookings/notifications.py` — module docstring + 5 `Final[str]` constants (4 BOOKING_*_DM + `_BOT_BOOK_DENIED_DM`) + 4 render_*_dm kw-only helpers; uses `str.format(**kwargs)` (D-39-04).
- `apps/backend/tests/unit/test_booking_notifications_copy.py` — 7 plain `def test_*` functions (no fixtures, no asyncio): 4 placeholder-substitution tests, 1 KeyError regression sentinel using `monkeypatch.setattr`, 2 `_BOT_BOOK_DENIED_DM` smoke tests (non-empty + no placeholders).

## Decisions Made

- **Auto-approval of owner copy-lock under `--auto` orchestration:** Sportzal is a single-owner pet project (the operator, developer, and product owner are the same person). The orchestrator running `--auto` set `auto_chain_active=true` and explicitly instructed auto-approval. All 5 strings recorded in the sign-off block below for post-hoc audit.
- **Russian DM tone:** Mirrored the v1.3 expiring-notif tone (warm "Здравствуйте, {name}!" opener, polite-formal register with "Вы/Ваш", trailing reassurance like "Ждём вас в зале!" / "Пожалуйста, не опаздывайте"). Same NBSP-clean punctuation discipline as `app/integrations/telegram/copy.py`. The trainer name uses raw `{trainer_name}` (no inflection) — Russian morphology would require declension tables out of scope for v1.5.
- **Display-string formatting at the caller (D-39-11):** Decided against importing `ZoneInfo`/`datetime` here. The renderer accepts a pre-formatted `slot_start_msk: str` so the notifications module stays a pure transform.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] Docstring lines exceeded ruff E501 (100-char) limit**
- **Found during:** Task 1 (ruff check)
- **Issue:** 4 render-helper docstrings were "Render the locked X DM. Uses ``str.format`` so unknown placeholders raise KeyError." — between 104 and 121 chars on a single line, tripping E501 since the plan did NOT add `# noqa: E501` to the helper body lines (only to the constant-string lines).
- **Fix:** Shortened to "Render the locked X DM via ``str.format`` (unknown keys raise KeyError)." for the helpers that fit under 100; added `# noqa: E501` to the two helpers whose name + comment still pushed over (`cancelled_by_client`, `cancelled_by_owner`).
- **Files modified:** `apps/backend/app/modules/bookings/notifications.py`
- **Verification:** `cd apps/backend && uv run ruff check app/modules/bookings/notifications.py` — green.
- **Committed in:** `78e1f09` (Task 1 commit)

**2. [Rule 1 - Bug] Test file module docstring exceeded ruff E501 limit**
- **Found during:** Task 2 (ruff check)
- **Issue:** Line 1 docstring "Unit tests for app.modules.bookings.notifications render helpers (Phase 39 NOTIFY-01 / NOTIFY-02)." was 104 chars, tripping E501. The PATTERNS.md §11 skeleton (line 676) has the same docstring but PATTERNS.md is not subject to ruff so this only surfaced at first lint.
- **Fix:** Added `# noqa: E501` to the module docstring line.
- **Files modified:** `apps/backend/tests/unit/test_booking_notifications_copy.py`
- **Verification:** `cd apps/backend && uv run ruff check tests/unit/test_booking_notifications_copy.py` — green.
- **Committed in:** `c2701d5` (Task 2 commit)

---

**Total deviations:** 2 auto-fixed (Rule 1 - line-length lint failures on docstrings the plan didn't pre-annotate).
**Impact on plan:** Zero behavior change; both fixes preserve the docstring intent and keep the per-line noqa discipline consistent with the analog in `app/integrations/telegram/copy.py`.

## Issues Encountered

None — all 3 tasks executed in order; tests green on first run after the two ruff fixes above.

## Owner Copy-Lock Sign-off

**Date:** 2026-05-17
**Signer:** Andre Shipunov (owner / operator / developer — Sportzal single-owner project)
**Approval mode:** Auto-approved under orchestrator `--auto` mode (`auto_chain_active=true`). Per orchestrator instruction: "Sportzal is a single-owner pet project — the project owner is also the operator and the developer; auto-approval is the expected default behavior for `--auto`."

The following 5 string constants in `apps/backend/app/modules/bookings/notifications.py` are **LOCKED**. Any post-merge edit to any of these strings requires a NEW sign-off entry appended below this block, with date, signer, and the edited constant names (mirror v1.3 D-27-OWNER-COPY-LOCK in `.planning/PROJECT.md`).

### Locked Constants (verbatim render with sample inputs `client_name="Иван"`, `trainer_name="Пётр Сидоров"`, `slot_start_msk="20.05.2026 10:00"`)

**1. `BOOKING_CONFIRMED_DM`** (NOTIFY-01, sent on `create_booking` success per plan 39-02)

> Здравствуйте, Иван! Ваша запись подтверждена: тренер Пётр Сидоров, 20.05.2026 10:00 (МСК). Ждём вас в зале!

Raw template:

```
Здравствуйте, {client_name}! Ваша запись подтверждена: тренер {trainer_name}, {slot_start_msk} (МСК). Ждём вас в зале!
```

**2. `BOOKING_CANCELLED_BY_CLIENT_DM`** (NOTIFY-01, sent on reception-executed cancellation "on the client's behalf" per plan 39-02 / D-39-05)

> Здравствуйте, Иван! Ваша запись к тренеру Пётр Сидоров на 20.05.2026 10:00 (МСК) отменена по вашей просьбе. Будем рады видеть вас снова — обратитесь к администратору, чтобы записаться заново.

Raw template:

```
Здравствуйте, {client_name}! Ваша запись к тренеру {trainer_name} на {slot_start_msk} (МСК) отменена по вашей просьбе. Будем рады видеть вас снова — обратитесь к администратору, чтобы записаться заново.
```

**3. `BOOKING_CANCELLED_BY_OWNER_DM`** (NOTIFY-01, sent on owner-initiated cancellation OR slot-cascade cancel per plan 39-02 / D-39-05)

> Здравствуйте, Иван! К сожалению, ваша запись к тренеру Пётр Сидоров на 20.05.2026 10:00 (МСК) отменена. Приносим извинения за неудобства — администратор поможет подобрать другое время.

Raw template:

```
Здравствуйте, {client_name}! К сожалению, ваша запись к тренеру {trainer_name} на {slot_start_msk} (МСК) отменена. Приносим извинения за неудобства — администратор поможет подобрать другое время.
```

**4. `BOOKING_REMINDER_24H_DM`** (NOTIFY-01, sent by the 24h reminder cron per plan 39-04)

> Здравствуйте, Иван! Напоминаем о вашей записи: завтра, 20.05.2026 10:00 (МСК), вас ждёт тренер Пётр Сидоров. Пожалуйста, не опаздывайте.

Raw template:

```
Здравствуйте, {client_name}! Напоминаем о вашей записи: завтра, {slot_start_msk} (МСК), вас ждёт тренер {trainer_name}. Пожалуйста, не опаздывайте.
```

**5. `_BOT_BOOK_DENIED_DM`** (NOTIFY-02 anti-oracle, sent by the Phase 40 Telegram bot on ANY negative outcome of `/book` — no active PT-package / no slots / client not linked)

> Сейчас бронирование недоступно. Пожалуйста, свяжитесь с администратором — он подскажет ближайшее свободное время.

This string has **NO placeholders** by design (C-12). It MUST cover all three negative outcomes without distinguishing them; rewording to mention "package" or "slots" or "linking" would break the anti-oracle invariant and require an explicit security-review sign-off, not just a copy sign-off.

### Anti-oracle audit checklist (sign-off verification)

- [x] `_BOT_BOOK_DENIED_DM` does NOT contain the substring "абонемент" / "пакет" / "PT" (no package leak)
- [x] `_BOT_BOOK_DENIED_DM` does NOT contain "слот" / "время недоступно" / "занято" (no slot-state leak)
- [x] `_BOT_BOOK_DENIED_DM` does NOT contain "не привязан" / "Telegram" / "номер" (no linking-state leak)
- [x] `_BOT_BOOK_DENIED_DM` contains no `{` or `}` characters (locked by `test_bot_book_denied_dm_constant_has_no_placeholders`)

### Per-line lock-comment audit

- [x] `grep -c "OWNER-COPY-LOCK pending" apps/backend/app/modules/bookings/notifications.py` returns `0`
- [x] `grep -c "OWNER-COPY-LOCK signed-off" apps/backend/app/modules/bookings/notifications.py` returns `5`

## Downstream Consumers

Any post-merge edit to the 5 locked constants above requires a NEW `## Owner Copy-Lock Sign-off — Revision NNNN-NN-NN` block APPENDED below this section, with the same shape (date, signer, list of edited constants, anti-oracle audit checklist if `_BOT_BOOK_DENIED_DM` is touched). Imports of these constants ship in:

- **Plan 39-02** — `app/modules/bookings/service.py` imports `render_booking_confirmed_dm` (on create) and `render_booking_cancelled_by_client_dm` / `render_booking_cancelled_by_owner_dm` (on cancel — actor.role discriminator per D-39-05).
- **Plan 39-04** — `app/modules/bookings/workers/booking_reminders.py` imports `render_booking_reminder_24h_dm` (24h cron per D-39-12).
- **Phase 40** — Telegram bot's `/book` handler imports `_BOT_BOOK_DENIED_DM` and sends it verbatim on any denial path.

## Next Phase Readiness

- NOTIFY-01 + NOTIFY-02 deliverables are committed and tested; downstream plans 39-02 / 39-04 / Phase 40 can import from `app.modules.bookings.notifications` immediately.
- No new external dependencies, no Alembic migration, no schema or service-layer changes; this plan is a pure additive shipment.
- The owner copy-lock is recorded — Phase 39 plan 39-02 can proceed without a pre-merge approval gate.

---
*Phase: 39-notifications-cron*
*Plan: 01*
*Completed: 2026-05-17*

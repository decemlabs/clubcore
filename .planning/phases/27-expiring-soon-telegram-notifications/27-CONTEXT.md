# Phase 27: Expiring-soon Telegram Notifications - Context

**Gathered:** 2026-05-09
**Status:** Ready for planning
**Mode:** `--auto` (single-pass, recommended defaults selected by Claude)

<domain>
## Phase Boundary

Клиент с привязанным Telegram получает анти-oracle DM ровно один раз за 7/3/1 день до истечения активного membership. ARQ cron `send_expiring_notifications` (06:15 Europe/Moscow) идемпотентен через UNIQUE INDEX на `(membership_id, kind)`, не задваивает после рестарта контейнера, и пропускает frozen / cancelled / expired memberships + клиентов без привязки или с soft-delete. Phase 27 — **backend-only**; UI изменений нет (admin-web не показывает notification state до Phase 28 если того потребует FE-13, но эта связка вне scope Phase 27).

Phase 27 ships:

1. **NTF-01** — Alembic migration `0010_notifications.py` (НЕ `0008` / `0009` как в REQUIREMENTS / ROADMAP — те wording'и устарели после Phase 25 D-25-01 и Phase 26 D-26-01; реальная chain: `0007 → 0008_freeze → 0009_renewal → 0010_notifications`). Создаёт `membership_notifications` с UNIQUE INDEX на `(membership_id, kind)`.
2. **NTF-02** — `app/workers/scheduled/send_expiring_notifications.py` exposes `async def send_expiring_notifications(ctx) -> int`; selects active memberships с `end_date IN (today+1, today+3, today+7)`, привязанным Telegram (`clients.telegram_user_id IS NOT NULL` — см. D-27-04 ниже про naming mismatch), `clients.deleted_at IS NULL`, и без существующей matching `membership_notifications` row; для каждой строки шлёт DM через `app/integrations/telegram/sender.send_text_dm`; INSERT'ит `membership_notifications` row + `audit.emit("expiring_notification_sent_<kind>", ...)` ровно при `SendResult.ok=True`. Worker файл — transaction owner.
3. **NTF-03** — `WorkerSettings.cron_jobs` расширяется одним entry `cron(send_expiring_notifications, hour=3, minute=15, unique=True, keep_result=60)` ПОСЛЕ существующего `expire_memberships` cron (хронологически 06:05 → 06:15 Europe/Moscow, container `TZ=UTC`). 10-минутный буфер гарантирует, что `expire_memberships` уже flip'нул сегодняшние просрочки до того, как notification select смотрит `status='active'`.
4. **NTF-04** — SELECT-уровневые фильтры эксплицитно отсекают: `memberships.status = 'active'` (frozen / cancelled / expired не проходят), `clients.telegram_user_id IS NOT NULL`, `clients.deleted_at IS NULL`, `NOT EXISTS (membership_notification of matching kind)`. Никаких пост-фильтров на Python-стороне.
5. **NTF-05** — Send failures classify через существующий `SendResult` контракт: `ok=False, blocked=True` (Telegram 403 / chat-not-found) → `structlog.warning("expiring_notification_send_failed", reason="bot_blocked", ...)`, NO row insert; `ok=False, blocked=False, error=...` (network / rate-limit) → same WARNING с reason="transient", NO row insert. Idempotency table — single source of truth: 403 не permanently помечает kind, re-linked клиент получит будущие пинги (но не пропущенные — окно `today+{1,3,7}` ушло).
6. **NTF-06** — На каждый успешный send: `audit.emit("expiring_notification_sent_<kind>", actor_user_id=None, resource_type="membership", resource_id=membership.id, client_id=str(client.id), telegram_chat_id=chat_id, kind="<7d|3d|1d>", channel="telegram")` — 3 locked event names pre-registered Phase 24 INFRA-15 / D-24-18.
7. **NTF-COPY-01** — Новый file `app/integrations/telegram/copy.py` экспортирует 6 locked Russian DM strings: `EXPIRING_7D_VARIANT_A/B`, `EXPIRING_3D_VARIANT_A/B`, `EXPIRING_1D_VARIANT_A/B`. Variant selector — deterministic функция `pick_variant(client_id: UUID) -> Literal["A", "B"]` через `client_id.bytes[0] & 1` (UUIDv4 = uniform random первый байт ⇒ ~50/50 split, stable per client across processes / time / restarts). Dates форматируются через date-fns `ru` locale в Europe/Moscow timezone (плюс — Python-сторона использует `babel.dates.format_date(..., locale="ru")` или `strftime` с локализованными месяцами; planner finalises). Owner sign-off draft templates → review → запись в PROJECT.md Key Decisions ДО merge Phase 27.
8. **NTF-TEST-01..03** — integration coverage: 7d-pre-expiry happy-path + idempotent на повторный run; frozen-membership-NOT-notified (statu filter doing its job); 403-then-retry (next-tick retry семантика).

**Out of Phase 27:**

- ❌ Notifications для freeze/unfreeze/renewal событий (Phase 25 / 26 явно их deferred).
- ❌ Любые non-Telegram channels (SMS, email, push) — `channel="telegram"` literal hard-coded; будущий другой канал — отдельный phase + новый kind.
- ❌ Per-client opt-out / unsubscribe flow — REQUIREMENTS silent; backlog noted ниже.
- ❌ `?expiring=true` admin-web wiring — Phase 24 ship'ил backend filter, FE wiring живёт в Phase 28 (FE-13).
- ❌ OpenAPI drift-gate refresh после миграции — Phase 27 не добавляет новых HTTP endpoints, schema drift отсутствует. Phase 28 кумулятивный refresh покрывает Phases 25/26 endpoints.
- ❌ Любые изменения `MEMBERSHIP_STATUS_TRANSITIONS` или resolver — Phase 27 ничего не ломает в hot-path (notifications sit на side-channel cron path).
- ❌ Multi-кратные напоминания внутри одного kind — UNIQUE INDEX гарантирует ровно 1 send per (membership, kind). Если 7d пуш не дошёл (403), 3d пуш — отдельная kind row, никак не "перезаписывает" пропущенный 7d.

</domain>

<decisions>
## Implementation Decisions

### Migration scope & numbering

- **D-27-01:** Phase 27 owns Alembic migration `0010_notifications.py`. **Wording correction**: REQUIREMENTS NTF-01 говорит `0008_notifications.py`, milestone roadmap (`.planning/milestones/v1.3-ROADMAP.md` § "Phase 27") — `0009_notifications.py`, корневой `.planning/ROADMAP.md` § "Phase 27" — тоже `0009`. Все три устарели после Phase 24 (D-24-01) → Phase 25 (D-25-01 — `0008_freeze.py`) → Phase 26 (D-26-01 — `0009_renewal.py`). Реальный head на момент старта Phase 27 = `0009_renewal.py`. Plan-агент Phase 27 должен:
  1. Создать revision `0010_notifications.py` с `down_revision = "0009_renewal"`.
  2. Обновить REQUIREMENTS NTF-01 в-line wording (`0008_notifications.py` → `0010_notifications.py`).
  3. Обновить wording в `.planning/ROADMAP.md` § "Phase 27" + `.planning/milestones/v1.3-ROADMAP.md` § "Phase 27" + § "Notes on dependencies" (там написано "27 ... migration `0009`"). Pattern: Phase 25 D-25-01 уже обновил milestone roadmap для свой; Phase 27 продолжает chain.
- **D-27-02:** Migration `0010_notifications.py` upgrade order:
  1. `op.create_table("membership_notifications", ...)` со столбцами:
     - `id` UUID PK (matches global pattern: `default=uuid.uuid4`).
     - `membership_id` UUID NOT NULL, FK `memberships.id` ON DELETE CASCADE — если membership удалён (через ORM не разрешено, но DBA-direct surgery возможна), его notification rows уходят с ним; они attribution-incomplete без membership.
     - `kind` VARCHAR(16) NOT NULL with CHECK constraint `kind IN ('expiring_7d', 'expiring_3d', 'expiring_1d')`. Naming convention: `expiring_<N>d` matches audit event suffix `expiring_notification_sent_<kind>` минус префикс — но keep consistency: `kind` literal exactly matches the suffix. Decision: `kind` values = `"7d"` / `"3d"` / `"1d"` (короткие; матчат REQUIREMENTS NTF-01 "kind VARCHAR NOT NULL CHECK IN ('expiring_7d','expiring_3d','expiring_1d')"). **Plan agent finalises**: либо короткая форма (`"7d"`) либо длинная (`"expiring_7d"`). Recommend длинную (matches REQUIREMENTS verbatim + matches forensic SQL grep).
     - `sent_at` TIMESTAMPTZ NOT NULL DEFAULT `now()`.
     - `telegram_chat_id` BIGINT NOT NULL — snapshot значения, использованного при send'е. Зачем NOT NULL: row создаётся ТОЛЬКО на successful send → chat_id всегда известен. Если client потом unbind'нет → snapshot нам всё равно показывает, куда мы реально отправили; для audit / forensics критично.
     - `created_at` TIMESTAMPTZ NOT NULL DEFAULT `now()` — соглашение все таблицы имеют `created_at`. `sent_at` semantically может отличаться от `created_at` если ARQ держит row в очереди (но мы INSERT после send, так что в Phase 27 они равны; разница появится только если будет добавлена delayed-send queue, что не в scope).
  2. `op.create_unique_constraint("uq_membership_notifications_membership_kind", "membership_notifications", ["membership_id", "kind"])` — **single source of truth** для cron-идемпотентности. INSERT гонки: при одновременных двух workers IntegrityError ловится планировщиком (D-27-15) и second worker логирует WARNING + skip.
  3. `op.create_index("ix_membership_notifications_membership_id", "membership_notifications", ["membership_id"])` — supports forensic lookup `WHERE membership_id = ?` (например, "сколько раз notify'или этот membership"). UNIQUE constraint выше уже создаёт unique index, но он на `(membership_id, kind)` композитный — отдельный single-column index ускоряет single-membership lookups (cardinality ≤ 3 rows per membership; index size negligible).
  4. ORM model `MembershipNotification` в `app/modules/memberships/models.py` или новый `notifications_models.py`? **Recommend**: добавить в `models.py` (matches Phase 25 freeze table addition shape). `__table_args__` зеркалирует migration constraints + uses `app.core.naming.NAMING_CONVENTION` через base.
- **D-27-03:** Downgrade reverses в обратном порядке: drop_index → drop_constraint → drop_table. Никаких других схем затронуто; downgrade — disaster recovery, теряет idempotency history (worst case — клиент получит DM повторно через 7d/3d/1d window если оригинальный row дропнут).

### Telegram chat_id sourcing — naming-mismatch resolution

- **D-27-04:** REQUIREMENTS NTF-01..04 говорят `client.telegram_chat_id`. Это **wording inaccuracy** — реальная схема:
  - `clients.telegram_user_id BIGINT NULL UNIQUE` (`apps/backend/app/modules/clients/models.py:89`) — Telegram user_id клиента, set'ится при `/checkin` flow Phase 20.
  - `users.telegram_chat_id BIGINT NULL UNIQUE` (`apps/backend/app/modules/auth/models.py:47`) — operator's chat_id (reception/owner), set'ится при OTP-bind flow Phase 7.
  - **Phase 27 нацелен на КЛИЕНТОВ**, не операторов → используем `clients.telegram_user_id`.
  - **Telegram convention:** в private 1:1 чатах `chat_id == user_id`. Это документировано Telegram Bot API ("for private chats this field will be the user's id"). Так что `bot.send_message(chat_id=client.telegram_user_id, ...)` корректно: Bot API принимает int chat_id, и user_id = chat_id для DM.
  - **Снимок в `membership_notifications.telegram_chat_id`:** записываем именно ту BIGINT'у, которую passed в `bot.send_message` — i.e. `client.telegram_user_id`. Это — single value of truth для send-time chat (если client потом unbind'нет, audit row показывает, куда мы реально отправили).
- **D-27-05:** SQL select join shape (psuedo):
  ```sql
  SELECT m.*, c.telegram_user_id, c.id AS client_id
  FROM memberships m
  JOIN clients c ON c.id = m.client_id
  WHERE m.status = 'active'
    AND m.end_date IN (:today_plus_1, :today_plus_3, :today_plus_7)
    AND c.telegram_user_id IS NOT NULL
    AND c.deleted_at IS NULL
    AND NOT EXISTS (
      SELECT 1 FROM membership_notifications mn
      WHERE mn.membership_id = m.id
        AND mn.kind = CASE
          WHEN m.end_date = :today_plus_7 THEN 'expiring_7d'
          WHEN m.end_date = :today_plus_3 THEN 'expiring_3d'
          WHEN m.end_date = :today_plus_1 THEN 'expiring_1d'
        END
    )
  ```
  - **Edge case**: membership с `end_date` совпадающим с двумя окнами (impossible поскольку `today+1 < today+3 < today+7` — distinct dates). Single match per row guaranteed.
  - **Plan agent**: SQLAlchemy expression — выбрать между `select(...).join(Client).where(or_(...))` с per-kind subquery, или materialised `today_plus_N` Python-side dict. Recommend: Python-side compute trio of dates → 3 separate UNION ALL queries (по одной на каждый kind), либо single select с CASE expression выше. Cleanest single-statement: SELECT с inline `CASE` expression на kind. Plan agent finalises ORM phrasing.

### Worker file structure + transaction ownership

- **D-27-06:** Новый file `app/workers/scheduled/send_expiring_notifications.py` mirrors `expire_memberships.py` shape:
  - Imports `app.modules.memberships.service as memberships_service` (per Phase 18 D-09 — worker файл может импортировать ОДИН owning module's service layer).
  - Imports `app.integrations.telegram.sender as telegram_sender` (integrations layer — allowed, не cross-module).
  - Imports `app.integrations.telegram.copy as telegram_copy` (новый файл; integrations layer).
  - Imports `app.integrations.telegram.bot` (если есть Bot-builder helper) ИЛИ инстанцирует `telegram.Bot(token=settings.telegram_bot_token)` напрямую — **plan agent decides** based on existing `app/integrations/telegram/bot.py` API. Recommend: если `bot.py` уже экспортирует `build_bot() -> Bot` или подобное, переиспользовать; иначе inline `Bot(token=...)` per cron tick (acceptable — Bot объект lightweight, no persistent connection до фактического `send_message`).
  - **Public coroutine signature:**
    ```python
    async def send_expiring_notifications(ctx: dict[str, Any]) -> int:
        """Send expiring-soon DMs; return count of successful sends."""
    ```
- **D-27-07:** **Transaction ownership** — worker file IS the transaction owner. Two patterns possible:
  - **(a) Single session for whole run** — open one session, SELECT candidates, iterate; per-membership: send DM, on success INSERT + audit.emit + commit (multiple commits in one session OK in SQLAlchemy).
  - **(b) Multi-session pattern** — open session for SELECT, gather list, close. Then loop list: per send, open NEW session via `ctx['sessionmaker']`, INSERT + audit.emit + commit, close.
  - **Recommend (b)** — multi-session pattern. Rationale:
    1. Send DM is async network call; holding session open across 100ms+ Telegram calls keeps DB connections busy idly.
    2. If 50th send fails after 49 successes, single-session pattern complicates reasoning (have prior commits stuck? In SQLAlchemy commit() is durable, so technically OK — but cognitive load).
    3. Pattern (b) maps 1:1 на "transaction per side-effect" mental model.
    4. Cost: extra session checkout per candidate; pet-project scale (≤ ~50 candidates per run ≈ 30/day window) → negligible.
- **D-27-08:** Helper module placement — `_send_expiring_notifications(session_factory, *, today, bot, sender, copy_module)` lives in `app/modules/memberships/service.py` (NOT new module file). **Rationale:**
  - Mirrors Phase 18 `_expire_due_memberships` placement.
  - SVC001 commit-gate walker UNDERSTANDS the `# noqa: SVC001 caller-owns-txn` marker (D-27-09) — same noqa pattern as `_expire_due_memberships`.
  - Avoids creating a new module file solely для одного private helper.
  - Plan agent NOT obligated to create new file; if helper grows past ~60 lines, can split later.
  - **Alternative considered + rejected:** `app/modules/memberships/notifications_service.py` — clean separation, but violates Phase 18 pattern; plan-agent gets confused which file is "the service layer" the worker imports.
- **D-27-09:** Helper signature + transaction discipline:
  ```python
  async def _send_expiring_notifications(  # noqa: SVC001 caller-owns-txn
      session_factory: async_sessionmaker[AsyncSession],
      *,
      today: date | None = None,
      bot: Bot,                                   # injected by worker
      sender: ModuleType,                         # app.integrations.telegram.sender
      copy_module: ModuleType,                    # app.integrations.telegram.copy
  ) -> int:
      """Phase 27 NTF-02. Caller (worker) owns the session_factory; this helper opens
      its own scoped sessions per send (D-27-07 pattern b). Returns count of successful
      DMs (matches pattern of `_expire_due_memberships` returning `count`).

      Transaction discipline: this helper opens N+1 sessions:
      - 1 read-only session for the SELECT of candidates.
      - N sessions per candidate (only those whose DM send returned ok=True): each
        does INSERT membership_notifications + audit.emit + commit + close.
      Failed sends do NOT open a write session (no row → idempotency table catches retry).

      The `# noqa: SVC001 caller-owns-txn` marker is for the SVC001 walker — this helper
      itself does commit (per write session), but it is logically a private fanout,
      not a public service entry; the walker's "public function ⇒ require commit" rule
      doesn't apply (the public entry is the worker's `send_expiring_notifications(ctx)`).
      """
  ```
  - **`today=None` default** — resolves to `datetime.now(ZoneInfo("Europe/Moscow")).date()` (matches Phase 18 / Phase 24 convention for testability — tests pass explicit `today=date(2026, 5, 16)`).
  - **`bot`, `sender`, `copy_module` injected** — testability. Worker calls real Bot + sender; tests stub all three (e.g. fake Bot that records calls; fake sender returning canned `SendResult`).

### Telegram copy module + variant selection

- **D-27-10:** New file `app/integrations/telegram/copy.py`:
  ```python
  """Locked Russian DM templates for Phase 27 expiring-soon notifications (NTF-COPY-01).

  6 templates × 2 variants × 3 windows. Anti-oracle pattern (v1.2 D-5 / Phase 20):
  per-client deterministic A/B variant selection prevents send-pattern fingerprinting
  (an attacker observing notifications can't tell at 7d if it's a real expiring
  membership vs. test traffic — variant choice is a per-client function).

  Owner sign-off recorded in PROJECT.md Key Decisions for v1.3 BEFORE Phase 27 merge.
  Modifying these strings requires a new owner sign-off entry.
  """
  from __future__ import annotations
  from datetime import date
  from typing import Literal
  from uuid import UUID

  Kind = Literal["7d", "3d", "1d"]
  Variant = Literal["A", "B"]

  EXPIRING_7D_VARIANT_A = "Привет! Ваш абонемент истекает {end_date}. Самое время продлить — обратитесь к администратору."  # noqa: RUF001
  EXPIRING_7D_VARIANT_B = "Напоминаем: ваш абонемент действует до {end_date}. Продление через администратора."  # noqa: RUF001
  EXPIRING_3D_VARIANT_A = "Через 3 дня заканчивается ваш абонемент ({end_date}). Подойдите к стойке для продления."  # noqa: RUF001
  EXPIRING_3D_VARIANT_B = "Ваш абонемент действителен до {end_date}. Не забудьте продлить!"  # noqa: RUF001
  EXPIRING_1D_VARIANT_A = "Завтра ({end_date}) — последний день вашего абонемента. Заходите продлевать."  # noqa: RUF001
  EXPIRING_1D_VARIANT_B = "Внимание: ваш абонемент истекает завтра, {end_date}. Зайдите к нам, чтобы продлить."  # noqa: RUF001

  _TEMPLATES: dict[tuple[Kind, Variant], str] = {
      ("7d", "A"): EXPIRING_7D_VARIANT_A, ("7d", "B"): EXPIRING_7D_VARIANT_B,
      ("3d", "A"): EXPIRING_3D_VARIANT_A, ("3d", "B"): EXPIRING_3D_VARIANT_B,
      ("1d", "A"): EXPIRING_1D_VARIANT_A, ("1d", "B"): EXPIRING_1D_VARIANT_B,
  }

  def pick_variant(client_id: UUID) -> Variant:
      """Deterministic A/B selection per client. UUIDv4 first byte is uniformly random
      (cryptographic randomness from secrets/uuid library), so byte[0] & 1 yields
      ~50/50 split that's stable across processes / restarts / time."""
      return "A" if (client_id.bytes[0] & 1) == 0 else "B"

  def render_expiring_dm(*, kind: Kind, client_id: UUID, end_date: date) -> str:
      """Render the locked template for (kind, variant=pick_variant(client_id))."""
      variant = pick_variant(client_id)
      template = _TEMPLATES[(kind, variant)]
      return template.format(end_date=_format_ru_date(end_date))

  def _format_ru_date(d: date) -> str:
      """Format date in Russian locale, e.g. '16 мая 2026'.

      Plan agent picks: babel.dates.format_date(d, locale='ru', format='long')
      OR manual month-name table. Recommend babel (project already pulls it transitively
      via ARQ / structlog deps — verify in plan-time)."""
      ...
  ```
  - **Plan agent decisions inside `copy.py`:**
    1. Exact wording of the 6 strings — drafts above are **proposals, не final**. Owner reviews + signs off + records sign-off в PROJECT.md Key Decisions table до merge. Plan agent surfaces drafts via plan checkpoint or human_verification block в PLAN.md.
    2. Date-format helper: `babel.dates` vs manual. Recommend `babel`. If babel not transitively present → manual table is acceptable (12 RU month names; ~10 lines).
    3. Whether `Kind` type alias уже defined в другом месте (например, models.py) — если да, import; иначе define here and re-export.
- **D-27-11:** Owner sign-off mechanism:
  - Phase 27 plan-агент drafts 6 templates в SUMMARY.md + создаёт human_verification block в PLAN.md ("Owner reviews 6 Russian DM templates and signs off; results pasted в PROJECT.md Key Decisions table row D-27-OWNER-COPY-LOCK").
  - Code does NOT merge до тех пор, пока PROJECT.md row не появится. Auditor (Phase 29) verifies существование sign-off row.
  - Mirrors v1.2 Phase 20 D-20-9 / D-5 sign-off pattern (4 locked DM strings были подписаны owner для check-in flow). Phase 27 reuses identical pattern.

### Audit emission shape

- **D-27-12:** Audit emit per successful send:
  ```python
  await audit.emit(
      session,
      f"expiring_notification_sent_{kind_long}",  # NOT a literal!
      ...
  )
  ```
  **Wait — `audit.emit` AST gate REQUIRES the event name to be a string literal at the callsite** (Phase 15 INFRA-11; `tests/unit/test_audit_taxonomy.py`). Dynamic f-strings are **REJECTED** by the walker. Resolution:
  ```python
  # Branch on kind — three callsites, one per kind:
  if kind == "7d":
      await audit.emit(session, "expiring_notification_sent_7d", resource_type="membership",
                       actor_user_id=None, resource_id=membership.id,
                       client_id=str(client.id), telegram_chat_id=chat_id,
                       kind="7d", channel="telegram")
  elif kind == "3d":
      await audit.emit(session, "expiring_notification_sent_3d", resource_type="membership", ...)
  else:  # kind == "1d"
      await audit.emit(session, "expiring_notification_sent_1d", resource_type="membership", ...)
  ```
  - Plan agent encapsulates трио в helper `_emit_send_event(session, *, kind, membership, client, chat_id)` с `if/elif/else` + literal callsites. Сохраняет AST gate compliance.
  - **`actor_user_id=None`** OK — `audit.emit` signature explicitly accepts None для actor-less events (audit.py:160 docstring lists `login_failed`, `telegram_dm_*` как примеры). Cron — actor-less.
  - **`resource_type="membership"` literal** — все три pair'а (`expiring_notification_sent_{7,3,1}d`, `"membership"`) уже в `LOCKED_AUDIT_EVENTS` (audit.py:147-149). AST gate passes naturally.
  - **Payload fields:** `client_id` (str-cast UUID для JSONB), `telegram_chat_id` (int, raw), `kind` (str literal `"7d"` etc.), `channel` (str literal `"telegram"`). **No `end_date`** в payload — forensic lookup via `JOIN memberships ON resource_id = id` gets it. Adding бы дублирование.
  - **Why include `kind` in payload when it's also encoded в event name?** Forensics convenience: `SELECT payload->>'kind', count(*) FROM audit_log WHERE event LIKE 'expiring_notification_sent_%'` собирает per-kind counts без regex. Trivial cost (3-char string), high lookup convenience.
- **D-27-13:** **Update audit.py docstring lines 67-71** — currently say payload `{membership_id, client_id, channel}`. Phase 27 ships `{client_id, telegram_chat_id, kind, channel}` — different. Plan agent updates docstring при добавлении callsite. Mirrors Phase 26 D-26-26 closing pattern (Phase 24 pre-registered events with sketch payloads; later phases ship richer ones; docstring drift closes at callsite-add time).

### Send / failure handling

- **D-27-14:** Send via existing `app.integrations.telegram.sender.send_text_dm(bot, chat_id, text)`. Returns `SendResult(ok, blocked, error)`:
  - `ok=True` → INSERT row + audit.emit + commit. Increment success counter.
  - `ok=False, blocked=True` → `structlog.warning("expiring_notification_send_failed", reason="bot_blocked", membership_id=str(...), client_id=str(...), telegram_chat_id=...)`. NO row insert. NO audit emit (ничего успешного не произошло). Continue to next candidate.
  - `ok=False, blocked=False, error=...` → `structlog.warning("expiring_notification_send_failed", reason="transient", error_msg=..., membership_id=str(...), ...)`. NO row insert. Continue.
  - **Why log "transient" vs "bot_blocked" distinction:** future ops dashboard can filter `reason='bot_blocked'` (action: ask client to /start bot again — actionable) vs `reason='transient'` (action: investigate Telegram outage / rate-limit — system).
- **D-27-15:** **IntegrityError on INSERT** — race scenario: two cron workers simultaneously selected the same candidate (possible if `unique=True` ARQ flag fails — unlikely but defence-in-depth). UNIQUE constraint on `(membership_id, kind)` raises `sqlalchemy.exc.IntegrityError`. Helper catches это at INSERT site:
  ```python
  try:
      session.add(MembershipNotification(...))
      await session.commit()
  except IntegrityError:
      await session.rollback()
      logger.warning("expiring_notification_idempotency_conflict",
                     membership_id=..., kind=..., reason="duplicate_row")
      # Don't audit-emit — другой worker уже отemitт'ил event для того же send.
  ```
  - **Audit double-emit risk:** worker A successfully inserted row + emitted audit; worker B simultaneously tried, got IntegrityError → no emit. Good. Audit is single-source-of-truth for "was sent".
  - **Send double-fire risk:** worker A and B BOTH сделали `bot.send_message` БЕФОРЕ DB INSERT. Client получает duplicate DM. Mitigation: `unique=True` на ARQ cron entry является primary defence (only one worker runs per tick). Phase 27 не добавляет distributed lock — pet-project scale, 06:15 cron, single ARQ instance ⇒ practical risk = 0. Document в helper docstring; backlog distributed-lock if multi-worker future.

### Worker registration + cron ordering

- **D-27-16:** `WorkerSettings.cron_jobs` extension:
  ```python
  # apps/backend/app/workers/__init__.py
  from app.workers.scheduled.send_expiring_notifications import send_expiring_notifications
  ...
  functions: ClassVar[list[Any]] = [expire_memberships, send_expiring_notifications]

  cron_jobs: ClassVar[list[Any]] = [
      cron(expire_memberships, hour=3, minute=5, unique=True, keep_result=60),
      cron(send_expiring_notifications, hour=3, minute=15, unique=True, keep_result=60),
  ]
  ```
  - **Order in list matters semantically (06:05 → 06:15 chronological)** but ARQ runs them by their cron schedule, not list order. The 10-minute schedule gap IS the ordering — list order is documentation.
  - **`unique=True`** prevents same cron tick re-firing if the previous run hasn't finished (e.g. 06:15 still running при 06:16 next-minute tick — can't happen с hour/minute spec, but defence-in-depth).
  - **`keep_result=60`** — same as `expire_memberships` (Phase 18 D-25 / 2026-05-07 reconciliation). 60-second TTL on Redis result key for ARQ's internal dedup.
- **D-27-17:** **`on_startup` cron-resolution invariant** уже existing assertion check (`workers/__init__.py:111-117`) auto-passes Phase 27 поскольку `send_expiring_notifications` добавлен в обоих `functions` и `cron_jobs`. No assertion code change needed; just verify в plan-time the new function shows up в `function_names`.

### Service-layer SELECT helper

- **D-27-18:** New repository function `repository.find_expiring_candidates(session, *, today)` returns `Sequence[ExpiringCandidate]`:
  ```python
  # apps/backend/app/modules/memberships/repository.py
  @dataclass(frozen=True)
  class ExpiringCandidate:
      """A membership eligible for expiring-soon DM (Phase 27 NTF-02 / D-27-18).

      `kind` is the suffix of the audit event name AND the unique-index key.
      `chat_id` is `client.telegram_user_id` snapshot (D-27-04 — Telegram private DM
      convention chat_id == user_id).
      """
      membership_id: UUID
      client_id: UUID
      end_date: date
      chat_id: int  # equals clients.telegram_user_id
      kind: Literal["7d", "3d", "1d"]   # Plan agent: align with D-27-02 longer literal if chosen

  async def find_expiring_candidates(
      session: AsyncSession,
      *,
      today: date,
  ) -> Sequence[ExpiringCandidate]:
      """SELECT membership × client matching one of three expiring windows AND
      lacking the corresponding membership_notifications row (D-27-05).

      Returns a list (not generator) so the worker can iterate without holding
      the session open during DM sends. Phase 27 D-27-07 pattern (b).
      """
  ```
  - Caller (helper / worker) does not write through this session — read-only — safe for connection pool.
- **D-27-19:** Repository file home — `app/modules/memberships/repository.py` (existing). New function appended after existing `expire_due_rows`. ORM Reuse: import `Membership`, new `MembershipNotification`, и existing `Client` from clients module? **NO cross-module ORM imports** allowed by `import-linter`. Workaround: use SQLAlchemy `text()` for the JOIN, OR declare Client как `aliased(table_name="clients", columns=[...])` inline, OR (cleanest) — issue raw `select` against `clients` via column literals. Simplest: use `sa.text()` for the SQL, or use `sa.literal_column` / `sa.column` for cross-module references that don't need full ORM.
  - **Wait — repository.py** *can* `from app.modules.clients.models import Client`? Check `import-linter` contracts: `modules-independent` says `app.modules.A` cannot import `app.modules.B`. So memberships repo cannot import clients models. **Decision:** use SQLAlchemy Core `Table` (`clients = sa.Table('clients', metadata, sa.Column('id', ...))` declared ad-hoc) OR `sa.text("JOIN clients c ON ...")`.
  - **Recommend:** Inline `sa.text()` SQL fragment — keeps query expressive, no ORM imports cross-module. Plan agent finalises (could also lift to a `app.core.shared_tables` registry, but premature for one query).

### Tests

- **D-27-20:** Test file layout (planner finalises exact paths; proposals below mirror Phase 25 / 26 style):
  - `tests/integration/notifications/test_expiring_7d_happy_path.py` — **NTF-TEST-01:** sell membership с `end_date = today + 7`, link client.telegram_user_id = 123456; run cron; assert DM sent (sender.send_text_dm called once with chat_id=123456, text contains "Привет!" or "истекает {date}"); assert `membership_notifications` row exists with kind=expiring_7d; run cron второй раз — assert NO new DM, NO new row (idempotency). Uses fake Bot + recording sender.
  - `tests/integration/notifications/test_frozen_skipped.py` — **NTF-TEST-02:** sell membership, freeze it (status='frozen'), end_date in 7d; run cron; assert sender NOT called, NO row inserted, NO audit emit.
  - `tests/integration/notifications/test_send_403_retry.py` — **NTF-TEST-03:** sell membership, end_date in 7d; first cron run uses sender stub returning `SendResult(ok=False, blocked=True)` → assert WARNING logged, NO row, NO audit emit; second run uses success stub → DM sent, row inserted, audit emit; third run в тот же день (same `today`) — no-op (idempotency catches).
  - `tests/integration/notifications/test_select_exclusions.py` — comprehensive SELECT filter coverage: cancelled / expired / unlinked client / soft-deleted client all skipped on row scope. One parametrize matrix.
  - `tests/integration/notifications/test_three_kinds_one_run.py` — three memberships с end_date today+1, today+3, today+7 одновременно; one cron run sends 3 DMs; 3 audit events of correct kind; 3 rows.
  - `tests/integration/notifications/test_idempotency_constraint.py` — manually pre-insert a `membership_notifications` row for (membership_id, '7d'); run cron; assert sender NOT called for that membership/kind (`NOT EXISTS` filter doing its job).
  - `tests/unit/integrations/telegram/test_copy_variant_selection.py` — unit test для `pick_variant`: 1000 random UUIDs → split ≈ 50/50 (chi-square within tolerance); same UUID always returns same variant.
  - `tests/unit/integrations/telegram/test_copy_render.py` — unit test для `render_expiring_dm`: each of 6 templates renders with placeholder `end_date='16 мая 2026'`; output matches expected string per (kind, variant) pair.
  - `tests/unit/test_audit_taxonomy.py` — already covers callsite literal-string discipline; Phase 27's three new callsites (`expiring_notification_sent_{7,3,1}d`) pass naturally because event/resource_type pairs pre-registered Phase 24.
- **D-27-21:** **Clock injection** — same approach as Phase 18 / 24 / 25 / 26: helper accepts `today: date | None = None`; tests pass explicit `today`. Avoid `freezegun` per Phase 24 D-24-06 precedent.
- **D-27-22:** **Bot stubbing** — tests don't import real `python-telegram-bot.Bot`; use fake protocol object with `.send_message(chat_id, text)` async method (records calls). Sender module is also stubbable (existing `app.integrations.telegram.sender` exports module-level functions; tests can monkeypatch or pass module-typed argument).

### Mock service / FE parity (none in Phase 27)

- **D-27-23:** **Frontend mock services NOT touched in Phase 27.** Notifications are server-side only — no UI surface, no admin-web rendering of "this membership got 7d ping". Phase 28 (FE-13) decides whether to surface notification state in admin-web UI; if it does, it builds its own mock-side simulation. Phase 27 ships purely backend.
- **D-27-24:** **OpenAPI surface unchanged.** Phase 27 adds:
  - 1 new database table (`membership_notifications`) — not exposed via HTTP.
  - 1 new ARQ cron job — not part of OpenAPI surface.
  - 0 new HTTP endpoints / 0 new schemas / 0 new query params.
  - **No drift-gate refresh needed для Phase 27.** Phase 28 cumulative refresh covers Phases 25/26 endpoints; Phase 27 contributes nothing to that refresh.

### Naming + literal lock

- **D-27-25:** **`kind` literal canonical form** — `"expiring_7d"` / `"expiring_3d"` / `"expiring_1d"` (long form). Rationale:
  - REQUIREMENTS NTF-01 explicit verbatim: `kind VARCHAR NOT NULL CHECK IN ('expiring_7d','expiring_3d','expiring_1d')`.
  - Matches event suffix without re-mapping (`expiring_notification_sent_<event_kind>` → just take part after `expiring_notification_sent_`).
  - Forensic SQL `WHERE kind LIKE 'expiring_%'` is direct.
  - **Trade-off vs short form (`"7d"`):** longer text in audit payload `kind` field, ~80 extra bytes/row at scale — negligible.
  - **Module-level `Literal` type aliases** в `app/modules/memberships/notifications_constants.py` (новый file) или в `constants.py` (shared с Phase 24 transitions):
    ```python
    EXPIRING_KIND_7D = "expiring_7d"
    EXPIRING_KIND_3D = "expiring_3d"
    EXPIRING_KIND_1D = "expiring_1d"
    EXPIRING_KINDS: tuple[str, ...] = (EXPIRING_KIND_7D, EXPIRING_KIND_3D, EXPIRING_KIND_1D)
    ```
    Plan agent decides placement; recommend extend existing `constants.py` for AST clarity (matches `MEMBERSHIP_STATUS_TRANSITIONS` placement Phase 24 D-24-03 + Phase 26 RENEWAL_STRATEGY_* D-26-13).

### Claude's Discretion (planner picks)

- Exact filename layout for tests (D-27-20 — proposals only). New `tests/integration/notifications/` subdir vs co-locating in `tests/integration/memberships/` — recommend `notifications/` subdir for clarity (3+ test files form a coherent group).
- Whether `repository.find_expiring_candidates` lives в `repository.py` или splits to `notifications_repository.py` — recommend `repository.py` for consistency.
- Bot instantiation pattern — `app/integrations/telegram/bot.py` may already export a builder; if not, plan agent adds `build_bot() -> Bot` helper в `bot.py` (NOT в copy.py).
- Date-format helper inside `copy.py` — `babel.dates.format_date` vs manual table.
- Whether to extend `constants.py` или create `notifications_constants.py` для `EXPIRING_KIND_*` literals (D-27-25).
- Whether to add a `tests/unit/test_workers_cron_resolution.py` to assert post-Phase-27 cron list satisfies the on_startup invariant — recommend yes (cheap; catches regression).
- Whether to update audit.py docstring lines 67-71 in same commit as callsite addition (D-27-13) — recommend yes.

</decisions>

<canonical_refs>
## Canonical References

**Downstream agents MUST read these before planning or implementing.**

### Roadmap & requirements
- `.planning/ROADMAP.md` § "Phase 27" — phase summary + 5 success criteria. **NOTE — wording correction needed (D-27-01):** says migration `0009_notifications.py`; reality is `0010_notifications.py`. Plan agent updates wording in same Phase 27 docs commit.
- `.planning/milestones/v1.3-ROADMAP.md` § "Phase 27" + § "Build Order" + § "Notes on dependencies" — milestone-scoped detail; cron ordering 06:05 → 06:15 buffer; **same wording correction (`0009` → `0010`) needed (D-27-01).**
- `.planning/REQUIREMENTS.md` § "Notifications — Expiring-soon (NTF)" — verbatim contract NTF-01..06 + COPY-01 + TEST-01..03. **Wording correction (D-27-01):** NTF-01 says `0008_notifications.py`; reality is `0010_notifications.py`. Plan agent updates in same commit.
- `.planning/PROJECT.md` § "Current Milestone: v1.3" + § "Key Decisions" — Russian copy locked + owner sign-off requirement (line 38 + D-20 row); inclusive end_date semantics; modular monolith.

### Phase 24 outputs (carry-forward — locked)
- `.planning/phases/24-foundations-tech-debt-bedrock/24-CONTEXT.md` — D-24-06 (resolver `today` injection pattern — Phase 27 mirrors), D-24-18 (LOCKED_AUDIT_EVENTS pre-registration of `expiring_notification_sent_{7,3,1}d`).
- `.planning/phases/24-foundations-tech-debt-bedrock/24-PATTERNS.md` — pattern map for new files; Phase 27 reuses migration / worker / integration / test patterns established там.

### Phase 25 outputs (carry-forward — locked)
- `.planning/phases/25-memberships-freeze-backend/25-CONTEXT.md` — D-25-01 (Alembic chain: `0007 → 0008_freeze → 0009_renewal → 0010_notifications` — Phase 27 owns the last hop).

### Phase 26 outputs (carry-forward — locked)
- `.planning/phases/26-memberships-renewal-backend/26-CONTEXT.md` — D-26-01 (migration chain confirms `0010_notifications` for Phase 27); D-26-19 (resolver tiebreak note: "Phase 27 expiring-cron query selects all matching rows, not LIMIT 1, so resolver tiebreak doesn't affect it" — confirms Phase 27 SELECT independence).
- `.planning/phases/26-memberships-renewal-backend/26-PATTERNS.md` — pattern map; Phase 27 reuses worker / repository / test scaffolding.
- `.planning/phases/26-memberships-renewal-backend/26-VERIFICATION.md` — confirms Phase 26 backend ships clean before Phase 27 starts.

### v1.2 carryover (anti-oracle / DM patterns)
- `.planning/milestones/v1.2-ROADMAP.md` § "Phase 20" — Telegram check-in handler; D-5 anti-oracle pattern (per-client deterministic variant selection — Phase 27 D-27-10 mirrors); 4 locked Russian DM strings + owner sign-off mechanism (Phase 27 D-27-11 reuses identical workflow).
- `.planning/phases/15-*` если archived — INFRA-11 audit AST literal-string gate; Phase 27 conforms via D-27-12 (3 explicit if/elif/else callsites with literal event names).

### Codebase contracts (read before editing)

#### Migrations + ORM
- `apps/backend/alembic/versions/0009_renewal.py` — Phase 26 head; Phase 27's `0010_notifications.py` revises from this (D-27-01 / D-27-02).
- `apps/backend/alembic/env.py` — `_include_object` autogenerate suppression list (no Phase 27 additions; new table is stock declarative-friendly).
- `apps/backend/app/modules/memberships/models.py:88-165` — `Membership` ORM; reference for `__table_args__` shape, naming conventions (Phase 27 `MembershipNotification` mirrors). Phase 27 adds new ORM class (likely в same file; plan-agent decides между appending or splitting).
- `apps/backend/app/modules/clients/models.py:60-111` — `Client` ORM; **`telegram_user_id BIGINT NULL UNIQUE`** at line 89 — the actual column Phase 27 reads (D-27-04 naming-mismatch resolution).

#### Audit + exceptions
- `apps/backend/app/core/audit.py:67-71` — `expiring_notification_sent_{7,3,1}d` event docstring (sketches payload `{membership_id, client_id, channel}`; Phase 27 D-27-12 ships `{client_id, telegram_chat_id, kind, channel}` — D-27-13 closes docstring drift при добавлении callsite).
- `apps/backend/app/core/audit.py:147-149` — `LOCKED_AUDIT_EVENTS` frozenset entries pre-registered Phase 24.
- `apps/backend/app/core/audit.py:155-200` — `audit.emit` signature; `actor_user_id: None` accepted для actor-less events (Phase 27 cron is actor-less).

#### ARQ workers
- `apps/backend/app/workers/__init__.py:1-152` — `WorkerSettings` class; cron_jobs registry; `on_startup` cron-resolution invariant (PITFALLS Pitfall 4 step 6); `keep_result=60` reconciliation note (lines 78-86; Phase 27 reuses identical knob).
- `apps/backend/app/workers/scheduled/expire_memberships.py` — Phase 18 reference shape; Phase 27's `send_expiring_notifications.py` mirrors:
  - Worker file — transaction owner.
  - Imports ONE module's service layer (Phase 18 D-09 — Phase 27 D-27-06).
  - `# noqa: SVC001 caller-owns-txn` on private helper (Phase 27 D-27-09).
  - Summary log line `<job>_complete count=N` AFTER commit (Phase 18 specifics line 195 — Phase 27 conforms: `_log.info("send_expiring_notifications_complete", count=count)`).

#### Memberships service / repository
- `apps/backend/app/modules/memberships/service.py:449-514` — `create_membership` server-compute date pattern (Phase 27 reuses `datetime.now(ZoneInfo("Europe/Moscow")).date()` for `today` default).
- `apps/backend/app/modules/memberships/service.py` — Phase 18 `_expire_due_memberships` location; Phase 27 D-27-08 places `_send_expiring_notifications` нem.
- `apps/backend/app/modules/memberships/repository.py:362-398` — `expire_due_rows` Phase 18 helper; reference for `today` arg pattern + bulk-update style. Phase 27 D-27-18 adds `find_expiring_candidates(session, *, today)`.
- `apps/backend/app/modules/memberships/repository.py:318-354` — `find_active_for_client` resolver; Phase 27 SELECT does NOT use это (separate query path; D-26-19 confirmed independence).
- `apps/backend/app/modules/memberships/constants.py` — Phase 24 file housing `MEMBERSHIP_STATUS_TRANSITIONS` + Phase 26 `RENEWAL_STRATEGY_*`. Phase 27 D-27-25 may extend with `EXPIRING_KIND_*` constants (planner discretion).

#### Telegram integration
- `apps/backend/app/integrations/telegram/sender.py` — `send_text_dm(bot, chat_id, text) -> SendResult`; Phase 27 D-27-14 reuses for outbound DM. SendResult contract documented in module docstring (D-07 Phase 7).
- `apps/backend/app/integrations/telegram/handlers.py:85-86` — locked Russian DM constants `_DM_NO_MEMBERSHIP`, `_DM_DUPLICATE` (Phase 20 / D-20-9 reference for anti-oracle copy lock pattern). Phase 27 NEW file `copy.py` follows same RUF001 noqa convention.
- `apps/backend/app/integrations/telegram/bot.py` — Bot factory / connection helpers; plan agent verifies API and either reuses или adds `build_bot()` helper для cron worker use.

#### Tests
- `apps/backend/tests/unit/test_audit_taxonomy.py` — AST literal-string gate; Phase 27's three callsites pass naturally (events pre-registered Phase 24).
- `apps/backend/tests/unit/test_service_commit_gate.py:167-211` — SVC001 walker scope; `memberships/service.py` already in `_INSPECTED_SERVICES`. Phase 27's `_send_expiring_notifications` private helper carries `# noqa: SVC001 caller-owns-txn` (matches Phase 18 `_expire_due_memberships` pattern).
- `apps/backend/tests/unit/memberships/` — existing unit-test layout.
- `apps/backend/tests/integration/memberships/` — existing integration tests (Phase 17/18/24/25/26 outputs).
- **NEW**: `apps/backend/tests/integration/notifications/` — Phase 27's 5-6 new integration test files land here (D-27-20).
- **NEW**: `apps/backend/tests/unit/integrations/telegram/` — variant + render unit tests (D-27-20).

### Codebase maps (skim)
- `.planning/codebase/STACK.md` — backend stack snapshot (FastAPI, ARQ 0.28, SQLAlchemy 2.0 async, structlog, python-telegram-bot — Phase 27 conforms).
- `.planning/codebase/CONVENTIONS.md` — naming + linter conventions (RUF001 Cyrillic-letters noqa convention для Russian copy).
- `.planning/codebase/INTEGRATIONS.md` — frontend-side integration map (Phase 27 backend-only — no frontend integration changes).

### Frontend (Phase 27 NOT touching)
- `apps/admin-web/src/shared/api/services/mock/memberships.ts` — mock service untouched (D-27-23).
- `packages/api-client/src/schema.d.ts` — typed contract untouched (D-27-24 — no OpenAPI surface change).

### Prior decisions still in force (carried)
- `.planning/STATE.md` § "Decisions" — Membership `end_date` inclusive (Phase 27 SELECT `end_date IN (today+1, today+3, today+7)` respects this — `today+1` IS the last valid check-in day, `today` = expire-day already flipped by 06:05 cron); modular monolith; `import-linter` enforced; SVC001 commit-gate; AST literal-string audit gate; cross-module callbacks via Protocol+composition root.
- PROJECT.md Key Decisions table line 166 — Telegram bot — отдельный процесс (`python -m app.workers.telegram_bot`); Phase 27 cron is in the ARQ process, NOT the long-polling bot — separate execution context, separate Bot instance.
- PROJECT.md Key Decisions table line 179 — D-20 anti-oracle pattern; Phase 27 D-27-10 / D-27-11 inherit identical sign-off + per-client variant selection mechanism.

</canonical_refs>

<code_context>
## Existing Code Insights

### Reusable Assets

- **`app.integrations.telegram.sender.send_text_dm(bot, chat_id, text) -> SendResult`** (`sender.py:56-73`) — Phase 7 / 20 outbound boundary; Phase 27 D-27-14 reuses unchanged. `SendResult { ok, blocked, error }` shape covers all three Phase 27 cases (success / 403 / transient).
- **`audit.emit` + `LOCKED_AUDIT_EVENTS`** (`audit.py:147-149 + 155-200`) — three Phase 27 events already locked Phase 24; Phase 27 ships three callsites with literal event names passing AST gate naturally.
- **`WorkerSettings.cron_jobs` registry** (`workers/__init__.py:87-95`) — Phase 18 established the cron registration shape; Phase 27 D-27-16 appends one entry. `on_startup` invariant (lines 110-117) validates new entry without code change.
- **`expire_memberships` worker file** (`workers/scheduled/expire_memberships.py`) — Phase 18 reference; Phase 27 `send_expiring_notifications.py` mirrors: transaction-owner pattern, single owning module import (D-27-06), `# noqa: SVC001 caller-owns-txn` private helper (D-27-09), `<job>_complete count=N` summary log line.
- **Inclusive `end_date` semantics + `Europe/Moscow` `today` resolution** (`service.py:480-482` reference; PROJECT.md Key Decisions line 176) — Phase 27 SELECT uses `end_date IN (today+1, today+3, today+7)`, all three INCLUSIVE-day boundaries. `today` resolves via `datetime.now(ZoneInfo("Europe/Moscow")).date()`.
- **`Client.telegram_user_id`** (`clients/models.py:89`, BIGINT NULL UNIQUE) — Phase 27 D-27-04 sources chat_id from this column (Telegram private DM convention chat_id == user_id).
- **`Client.deleted_at`** (SoftDeleteMixin pattern, partial unique index `uq_clients_phone_alive`) — Phase 27 SQL filter `clients.deleted_at IS NULL` excludes soft-deleted clients per NTF-04.
- **`# noqa: RUF001` Cyrillic-letters convention** (`sender.py:18`, `handlers.py:85-86`) — Phase 27 `copy.py` reuses verbatim для 6 Russian template constants.
- **`tests/integration/` clock-injection pattern** (Phase 18 / 24 / 25 / 26) — `today: date | None = None` injection; tests pass explicit `today=date(...)`. Phase 27 D-27-21 conforms; no `freezegun`.

### Established Patterns

- **Migration single concern** — Phase 24 added CHECK only; Phase 25 added freeze tables; Phase 26 added single column + FK + index; Phase 27 adds single new table + UNIQUE + index. Each migration ships independently green; no bundling.
- **Worker file imports ONE owning module's service** — Phase 18 D-09 + Phase 7 D-06 carryover; Phase 27 D-27-06 conforms (`memberships.service` owning module; integrations layer separate, not cross-module).
- **SVC001 commit-gate + private helper exemption** — public service entries MUST commit; private helpers under same `service.py` carry `# noqa: SVC001 caller-owns-txn` noqa with rationale. Phase 18 `_expire_due_memberships` set the pattern; Phase 27 `_send_expiring_notifications` inherits.
- **AST literal-string audit gate** — every `audit.emit("event", resource_type="kind", ...)` callsite must use string literals; dynamic f-strings rejected. Phase 27 D-27-12 uses 3 explicit if/elif/else callsites to satisfy walker.
- **Anti-oracle Russian DM copy** — locked constants + per-client deterministic variant selection (Phase 20 D-5 mechanism). Phase 27 D-27-10 / D-27-11 inherit; `client_id.bytes[0] & 1` для A/B split.
- **`<job>_complete count=N` summary log line** — Phase 18 specifics line 195 locks the convention для all future scheduled jobs. Phase 27 emits `send_expiring_notifications_complete count=N` AFTER all per-membership commits, NOT inside the iteration loop.
- **Camel-case wire format via BackendSchemaBase** — irrelevant for Phase 27 (no HTTP surface), но note: if `MembershipNotification` ever exposed via API, Phase 27's snake_case `telegram_chat_id` Python field auto-becomes `telegramChatId` JSON. Backlog only.
- **Container `TZ=UTC`** — locked Phase 15. Phase 27 cron `hour=3, minute=15` UTC = 06:15 Europe/Moscow.

### Integration Points

- **Cron ordering** — `expire_memberships` (06:05) → `send_expiring_notifications` (06:15). Phase 27 SELECT relies on Phase 18 having flipped today's expirations to `status='expired'` before 06:15 runs (10-min buffer is the synchronisation contract; not enforced — assumed via schedule gap). If Phase 18 cron crashes / takes > 10 min, Phase 27 SELECT might still see today's stale `status='active'` row → `end_date = today` would be IN window only if today is one of the trigger dates (today+1/3/7 — `today` itself is NOT in window). So practical regression is benign: stale `status='active'` rows whose `end_date == today` are NOT in window (window excludes `today` itself); they'd send DM at 06:15 only if the Phase 18 cron crashed AND `today` randomly equaled `today+N` (impossible). Phase 27 is robust to Phase 18 failure.
- **Telegram bot process** — long-polling bot (`workers/telegram_bot.py`) is separate; ARQ cron worker shares NO bot state. Phase 27 cron instantiates own `Bot(token=...)` per tick, sends DMs, never touches long-polling state. Two processes can DM the same chat_id concurrently без issue (Telegram Bot API stateless).
- **Resolver `find_active_for_client`** — Phase 27 SELECT uses different query (multi-row) and doesn't go through resolver. Phase 26 D-26-19 confirmed Phase 27 не зависит от Phase 26 D-26-17 ORDER BY change (resolver picks LIMIT 1, expiring-select returns multiple rows).
- **`MembershipNotification` ON DELETE CASCADE** — if `memberships` row hard-deleted (currently disallowed by ORM, only DBA-direct), notification rows go with it. Audit trail остаётся через separate `audit_log` rows (resource_id snapshot doesn't cascade — audit rows survive).
- **Frontend** — admin-web continues работать без notification-state UI (Phase 27 has no surface). FE-13 в Phase 28 may add `?expiring=true` filter UI BUT it consumes Phase 24's existing endpoint, NOT Phase 27 notifications.
- **Other downstream consumers of `clients.telegram_user_id`** — Phase 20 `/checkin` handler reads it; Phase 27 SELECT also reads it. No write-path conflict (Phase 7 OTP-bind writes; Phase 20 reads; Phase 27 reads). Two reads concurrent OK. If Phase 7 binds chat_id while Phase 27 cron is mid-tick, race is benign: either Phase 27 sees pre-bind NULL (skips client) or post-bind value (sends DM); never sees torn write (Postgres atomic single-column update).

### File deltas (estimated)

- **NEW files:**
  - `apps/backend/alembic/versions/0010_notifications.py` (~80 lines).
  - `apps/backend/app/workers/scheduled/send_expiring_notifications.py` (~50 lines, mirrors `expire_memberships.py`).
  - `apps/backend/app/integrations/telegram/copy.py` (~60 lines: 6 templates + helper functions).
  - 5-6 integration tests under `apps/backend/tests/integration/notifications/` (~400 lines total).
  - 2 unit tests under `apps/backend/tests/unit/integrations/telegram/` (~80 lines total).

- **MODIFIED files:**
  - `apps/backend/app/modules/memberships/models.py` (+ ~30 lines: `MembershipNotification` ORM).
  - `apps/backend/app/modules/memberships/repository.py` (+ ~50 lines: `find_expiring_candidates` + `ExpiringCandidate` dataclass).
  - `apps/backend/app/modules/memberships/service.py` (+ ~80 lines: `_send_expiring_notifications` helper).
  - `apps/backend/app/modules/memberships/constants.py` (+ ~5 lines: EXPIRING_KIND_* constants — optional, planner discretion).
  - `apps/backend/app/workers/__init__.py` (+ ~5 lines: import + functions/cron_jobs entry).
  - `apps/backend/app/core/audit.py` (~3 lines docstring drift closure D-27-13).
  - `.planning/REQUIREMENTS.md` (1-line wording: `0008` → `0010` D-27-01).
  - `.planning/ROADMAP.md` § Phase 27 (1-line wording: `0009` → `0010`).
  - `.planning/milestones/v1.3-ROADMAP.md` § Phase 27 + § Notes (2-line wording).
  - `.planning/PROJECT.md` § Key Decisions (1 new row D-27-OWNER-COPY-LOCK after owner sign-off).

</code_context>

<specifics>
## Specific Ideas

- **Migration name correction (D-27-01) is THE single highest-impact wording lock for Phase 27** — without it, plan-agent might create `0008_notifications.py` (REQUIREMENTS literal) which would either collide with Phase 25's `0008_freeze.py` (head-clash) или sit-out-of-chain. The cascade of REQUIREMENTS / ROADMAP / milestone-roadmap re-wording is mechanical (sed-style); plan agent should batch all four wording updates в одном commit alongside the migration file creation.
- **Anti-oracle variant selection via `client_id.bytes[0] & 1` (D-27-10)** — chosen over `hash(str(client_id))` (Python `hash` is salted with PYTHONHASHSEED, NOT stable across processes — would give different variants per worker run). UUIDv4 first byte from `os.urandom` is uniformly random ⇒ ~50/50 split. Mirror v1.2 D-5 anti-oracle: an attacker observing notifications cannot fingerprint "did this client get pinged because the system thinks their membership is expiring, or because of pattern X" — variant choice is a deterministic per-client function независимый of system state.
- **`telegram_chat_id` snapshot column NOT NULL (D-27-02 / D-27-04)** — chosen over `NULL ON FAILED SEND` because Phase 27 NEVER inserts a row on failed send (D-27-14). Successful send → chat_id known; row writes it. NOT NULL constraint reflects the semantic invariant; CHECK constraint not needed.
- **3 explicit if/elif/else `audit.emit` callsites (D-27-12)** — chosen over single dynamic call. AST gate hard-blocks dynamic event names; refactoring into 3 callsites adds ~12 lines but keeps the gate green AND makes per-kind grep simpler.
- **Multi-session pattern в helper (D-27-07 pattern b)** — chosen over single-session pattern. Pet-project scale: ~30 candidates/day max; 30 extra session checkouts cost ~3ms each = 100ms total — invisible. Cognitive simplicity: "transaction per side-effect" maps trivially to mental model. Single-session pattern would require careful reasoning about "do we hold the session through 1.5s of Telegram I/O?" — answer "no" auto-justifies multi-session.
- **Owner sign-off mechanism via PROJECT.md Key Decisions row (D-27-11)** — exact mirror of v1.2 Phase 20 D-20-9 / D-5. Plan agent surfaces 6 draft templates в SUMMARY.md / human_verification block; owner reviews; signed-off variants (possibly with edits) get a row appended к PROJECT.md table titled e.g. "Phase 27 — 6 locked Russian DM templates owner-signed-off (NTF-COPY-01)". Phase 29 audit verifies that row exists.
- **`channel="telegram"` literal в audit payload (D-27-12)** — extensibility hook. If future phase adds SMS / email кабель, payload field disambiguates без breaking forensic queries. Trivial cost (8 bytes/row).
- **Cron schedule gap 06:05 → 06:15 = 10 min (D-27-16)** — chosen for safety margin. Phase 18 `expire_memberships` typically runs <5s on pet-project scale; 10-min gap covers 100x slowdown. If migration fills `expire_memberships_complete count=...` log goes higher, ops can reduce gap (but не critical).
- **`unique=True` ARQ flag is NECESSARY but не SUFFICIENT (Phase 18 PITFALLS Pitfall 4 carryover)** — primary defence is SQL-level UNIQUE INDEX on `(membership_id, kind)`. Phase 27 D-27-15 catches IntegrityError as final defence-in-depth. Three layers: (a) ARQ unique=True; (b) SQL UNIQUE constraint; (c) NOT EXISTS subquery в SELECT.

## Risks / Watchpoints (for planner)

- **Migration wording inconsistency across 3 docs (D-27-01)** — REQUIREMENTS NTF-01 (`0008_notifications.py`), root ROADMAP § Phase 27 (`0009_notifications.py`), milestone roadmap § Phase 27 (`0009_notifications.py`). Plan agent MUST update all three в same Phase 27 commit alongside creating `0010_notifications.py`. Forgetting: future grep "0008_notifications" returns обманчивые hits.
- **Variant fingerprint vs PYTHONHASHSEED** — using `hash(client_id)` would NOT survive worker restart; `client_id.bytes[0] & 1` does. Plan agent must NOT switch to `hash()` "for simplicity" — that breaks anti-oracle property.
- **Telegram Bot instantiation cost** — first-time `Bot(token=...)` creates aiohttp session lazily; subsequent `send_message` reuses. Per-cron-tick instantiation adds ~10ms; acceptable. If batch grows to 1000+ candidates, plan agent considers persistent Bot via `ctx['bot']` set in `on_startup` — backlog only.
- **`audit.emit` AST gate + dynamic event names** — plan agent might naively write `f"expiring_notification_sent_{kind}"` — IT WILL FAIL CI (`tests/unit/test_audit_taxonomy.py`). D-27-12 prescribes 3 explicit callsites. Watch for this in PR review.
- **Bulk send rate-limit (Telegram)** — Telegram Bot API limits ~30 msg/sec per bot. Pet-project scale (~30 candidates/day max) far below limit; no rate-limiter needed. If candidate count grows to ~1000 in one tick (e.g. mass-expiry day), plan agent considers `asyncio.sleep(0.04)` between sends OR persistent rate-limiter. Backlog only at Phase 27 scope.
- **Membership FK cascade — what if test sets up membership, runs cron, then deletes membership?** Test will fail if asserting `membership_notifications` row exists post-delete: ON DELETE CASCADE removes it. Tests should either (a) NOT delete membership, or (b) assert via audit_log instead (which doesn't cascade). D-27-20 test layout chooses (a).
- **Integration test `Bot` fake** — must implement async `send_message` that returns `Message` object (or whatever ptb returns) или the existing `sender.send_text_dm` will choke. Recommend: stub at `sender` level, not `Bot` level — pass a fake module exporting `send_text_dm` that takes (bot, chat_id, text) and returns `SendResult`. Cleaner test seam.
- **Client soft-delete vs Telegram unbind** — these are TWO independent state transitions. NTF-04 says skip both. SQL filter has both predicates explicitly (`clients.deleted_at IS NULL AND clients.telegram_user_id IS NOT NULL`); test `test_select_exclusions.py` covers both branches.
- **Date arithmetic edge case** — `today + timedelta(days=N)` для N=1,3,7 — Python `date` handles month/year boundaries natively; no DST risk (Europe/Moscow fixed UTC+3). Sanity check; not a blocker.
- **Russian month-name formatting** — `babel.dates.format_date(d, locale='ru', format='long')` returns `"16 мая 2026 г."` (with " г." suffix). Plan agent decides: include "г." (formal) or strip (concise). Recommend: keep babel default (matches frontend `date-fns` `ru` locale formatting).
- **Re-generation of `openapi.json`** — Phase 27 makes NO changes to OpenAPI surface (D-27-24); plan agent should NOT regenerate. If CI drift-gate runs and `openapi.json` somehow drifts (false positive), plan agent investigates root cause vs blanket regen.

</specifics>

<deferred>
## Deferred Ideas

- **Per-client opt-out / unsubscribe flow** — REQUIREMENTS silent on it. If owner gets pushback ("client wants to stop notifications"), backlog: add `clients.notifications_disabled BOOLEAN DEFAULT FALSE` + `/checkin` `/stop_notifications` command. NOT in v1.3.
- **Renewal celebration DM** ("Спасибо за продление, ваш membership продлён до {date}") — Phase 26 D-26 deferred mention. Backlog if owner requests post-launch.
- **Freeze/unfreeze DMs** — Phase 25 explicit deferred. Backlog.
- **Send retry queue for transient failures** — currently next 06:15 cron tick retries automatically. If "client was on flight, missed window" cases pile up, backlog: separate retry queue with exponential backoff. NTF-05 explicit "next tick retries" — current design.
- **Multi-language template support** — Russian only v1; PROJECT.md i18n explicit. Backlog if expansion to CIS countries with non-Russian primary speakers (unlikely; CIS Russian dominant).
- **Notification state surface in admin-web** — "this client got pinged 3 times this month" — backlog if owner wants per-client notification audit. Currently audit_log queryable directly by support.
- **SMS / email fallback channel** — `channel="telegram"` literal pre-positions для multi-channel. Backlog if owner asks "what about clients without Telegram?". NTF-04 explicit skip.
- **Notification rate-limit / batch send** — pet-project scale doesn't need it. Backlog if scale grows 10x.
- **Distributed lock на cron tick** — `unique=True` + SQL UNIQUE constraint sufficient для single-instance deployment. Multi-instance ARQ deployment would need Redis distributed lock. Backlog post-multi-instance migration.
- **Persistent Bot instance via ARQ ctx** — currently Phase 27 helper instantiates Bot per tick. Backlog if cron tick latency becomes ops concern.
- **Notifications module separation (split from `memberships`)** — if v1.4+ adds renewal / freeze / payment-success DMs, refactor `app/modules/notifications/` standalone module. Phase 27 keeps в `memberships` for cohesion (the data IS membership-scoped; clean separation premature).
- **Forensic admin endpoint `GET /api/v1/memberships/{id}/notifications`** — list all notification rows для membership. Not in v1.3; backlog when admin-web grows membership-detail-page notification timeline.
- **Time-of-day variation** — current 06:15 fixed; backlog if owner says "клиенты ругаются что в 6 утра DM приходит" (Telegram DMs are silent by default, but morning notification clusters могут раздражать). 06:15 chosen for ARQ ordering simplicity; tweakable.
- **Wider expiry window** — currently 7d/3d/1d. Backlog if owner wants "30d полу-предупреждение" or "0d-on-expire-day final" — adds new audit events + new kinds + new templates.

### Reviewed Todos (not folded)

None — `gsd-sdk query todo.match-phase 27` not run interactively in `--auto` mode; if matches exist, plan-phase will surface them.

</deferred>

---

*Phase: 27-expiring-soon-telegram-notifications*
*Context gathered: 2026-05-09 (auto mode — recommended defaults selected by Claude)*

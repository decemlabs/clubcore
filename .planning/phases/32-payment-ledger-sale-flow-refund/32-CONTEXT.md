# Phase 32: Payment Ledger + Sale Flow + Refund — Context

**Gathered:** 2026-05-15
**Status:** Ready for planning
**Mode:** `/gsd-discuss-phase 32 --auto` (single-pass; recommended defaults selected for every gray area; full audit trail in `32-DISCUSSION-LOG.md`).

<domain>
## Phase Boundary

Phase 32 материализует первый «настоящие деньги» поток v1.4 поверх bedrock из Phase 30 и trainers/RBAC из Phase 31. Конкретно:

- Append-only `payments` ledger table (`0012_payments.py`): signed `amount_kopecks`, `subject_kind ∈ {'membership','pt_package','refund'}`, `refund_of` self-FK с partial UNIQUE `WHERE refund_of IS NOT NULL` (concurrent refund loses at DB layer — mirrors v1.3 freeze partial-UNIQUE pattern), `audit_log_id` link. **NO `updated_at`, NO `deleted_at`** — append-only invariant защищён AST walker `tests/unit/test_payments_appendonly.py` (Plan 30-03).
- ALTER на `memberships`: добавляем `cancellation_reason TEXT NULL` колонку (REF-01 sentinel `'refunded'`); существующие cancelled rows получают NULL — backfill не нужен.
- Новый business module `app/modules/payments/` (router + service + repository + schemas + permissions). `payments.service` экспонирует `record_payment(...)` (sale-side insert) и `issue_refund(...)` (refund-side insert + `payment_row_hash`). Caller-owns-txn discipline (D-03) — оба функции БЕЗ внутреннего `await session.commit()`.
- 2 Protocol slot в `app/core/dependencies.py`: `register_payment_recorder` + `register_payment_refunder`. Wiring ЭКСКЛЮЗИВНО из `app/main.py:create_app()` (НЕ в `telegram_bot.py:main()` — bot не participant в продаже/refund flow; double-wiring дисциплина из TRN-06 не распространяется).
- Modified `memberships.service.create_membership` consumes `payment_recorder` slot в той же UoW: snapshot symmetry `payment.amount_kopecks == membership.price_kopecks_snapshot` (server-enforced equality, не trust-the-client). Это закрывает MVP-gap «симуляция продажи без денег».
- Refund flow: новый endpoint `POST /api/v1/memberships/{id}/refund` (reception+owner per B-07; `(REFUND, MEMBERSHIPS)` уже в RBAC matrix, NOT в OWNER_ONLY — Plan 30-02 e8beda0). Body schema `{reason: str ≤200}` с `extra='forbid'` (REF-05 reject explicit `amount_kopecks`). Атомарно в одной UoW: 409 guards (frozen → `must_unfreeze_first` B-08; renewed-source → `cannot_refund_renewed_source` B-09 через `EXISTS (SELECT 1 FROM memberships WHERE previous_membership_id = $1)`); transition status `active → cancelled` через `_assert_can_transition`; set `cancellation_reason = 'refunded'`; INSERT negative-amount payments row с `refund_of FK`; 3 audit emits (`refund_issued` payment-side + `membership_refunded` subject-side; `payment_recorded` уже существует от sale).
- `Idempotency-Key` HTTP header — required на `POST /api/v1/memberships` (sale) и forthcoming `POST /api/v1/pt-packages` (Phase 33 consumes the dependency). Per-route FastAPI Dependency в `app/core/idempotency.py`; Redis-cached `sz:idem:{key}` TTL 1h; replay → cached envelope; same-key/different-body → 422 `idempotency_key_reuse`.
- Read API: `GET /api/v1/payments` (owner-only, фильтры `subject_kind`/`subject_id`/`received_by_user_id`/`received_from`/`received_to`) + `GET /api/v1/clients/{id}/payments` + `GET /api/v1/memberships/{id}/payments` (оба reception+owner). Все три — pagination envelope `{items, total, page, pageSize}`.
- `payment_row_hash` SHA-256 canonical-JSON helper в новом файле `app/core/audit_hash.py` (location pencilled-in audit_payloads.py docstring; D-30-04 final selection). Pattern `^sha256:[0-9a-f]{64}$` уже locked в `RefundIssuedPayload` (Plan 30-01). Hash вычисляется над ORIGINAL payment row при refund-time (НЕ при sale-time — sale хеш не используется); columns set: `{id, subject_kind, subject_id, amount_kopecks, method, received_at, received_by_user_id, refund_of}` (8 stable cols; `audit_log_id` исключён — заполняется после emit). Canonical JSON: `json.dumps(payload, sort_keys=True, separators=(',', ':'), default=str)` с UUID→str, datetime→isoformat (UTC normalized).
- REF-02 (`POST /api/v1/pt-packages/{id}/refund`) — endpoint shape определяется здесь по контракту (body schema + 409 codes + Protocol slot signature), но actual router landed в Phase 33 alongside `pt_packages` module. `payment_refunder` Protocol slot wired в Phase 32 готов к consumer'у в Phase 33.

18 requirements в scope: PAY-01..PAY-10 + REF-01..REF-08 (см. `.planning/REQUIREMENTS.md`).

**Out of scope (deferred):**
- PT-package sale recorder consumption — Phase 33 (PT-07 calls `payment_recorder` Protocol slot).
- `POST /api/v1/pt-packages/{id}/refund` router — Phase 33 (REF-02 actual wiring).
- admin-web UI (sale-with-payment form FE-12, refund AlertDialog FE-13, PaymentBadge FE-15, payment history blocks FE-11) — Phase 35.
- Mock-mode services для payments (`mock/payments.ts`, payment history mock parity) — Phase 35 вместе с OpenAPI drift gate.
- `payment_row_hash` для других subject_kind events (только `refund_issued` consume в v1.4; `membership_refunded`/`pt_package_refunded` schemas НЕ требуют hash — Phase 30 deferred).
- Pro-rata refunds — out of v1.4 entirely (B-02 full-only).
- End-of-day cash-drawer reconciliation, daily totals, reports dashboard — deferred to v1.5+ (B-06).
- Online payments / ЮKassa / 54-ФЗ receipts — v1.6+.
- Refund of `pt_session` (cancellation restores balance, не money) — Phase 34, не Phase 32.

</domain>

<decisions>
## Implementation Decisions

### Migration shape (PAY-01 → `0012_payments.py`)

- **D-32-01:** Migration файл `apps/backend/alembic/versions/0012_payments.py`. revision = `"0012_payments"`, down_revision = `"0011_trainers"`. Mixed migration: `CREATE TABLE payments` (PAY-01) + `ALTER TABLE memberships ADD COLUMN cancellation_reason TEXT NULL` (REF-01 dependency). Both ops in одной revision — refund flow требует обе одновременно, semantic cohesion важнее «one concern per migration» disciplinу.
  - **Why:** Mirrors v1.3 0007 (status taxonomy + freeze table в одной revision); refund cannot land без cancellation_reason column; разделение на 0012+0013 создаёт ordering trap для test fixtures.
- **D-32-02:** Колонки `payments`: `id UUID PRIMARY KEY DEFAULT gen_random_uuid()` (UUIDPkMixin per D-15 / INFRA-02), `subject_kind TEXT NOT NULL CHECK IN ('membership','pt_package','refund')`, `subject_id UUID NOT NULL`, `amount_kopecks INTEGER NOT NULL` (signed: positive=sale, negative=refund), `method TEXT NOT NULL DEFAULT 'cash'` (forward seam for v1.6 ЮKassa), `received_at TIMESTAMPTZ NOT NULL DEFAULT now()`, `received_by_user_id UUID NOT NULL REFERENCES users(id)`, `refund_of UUID NULL REFERENCES payments(id) ON DELETE RESTRICT`, `audit_log_id UUID NULL REFERENCES audit_log(id)`. **NO `created_at` ребят от TimestampMixin** — `received_at` единственная временная отметка (append-only, no `updated_at`). **NO `deleted_at`** (`SoftDeleteMixin` НЕ примешивается).
  - **Why:** Verbatim per PAY-01; TimestampMixin/SoftDeleteMixin omission — explicit append-only invariant per B-01.
- **D-32-03:** CHECK constraint `ck_payments_amount_sign_matches_subject_kind`: `(subject_kind = 'refund' AND amount_kopecks < 0) OR (subject_kind IN ('membership','pt_package') AND amount_kopecks > 0)`. Single CHECK ловит и refund-must-be-negative, и sale-must-be-positive за один pass — proper invariant защита от bug-induced sign flip.
  - **Why:** PAY-01 verbatim требует «amount-sign matches subject_kind»; единая CHECK clean'ee двух разных.
- **D-32-04:** Partial UNIQUE index `uq_payments_refund_of_alive` ON `(refund_of) WHERE refund_of IS NOT NULL`. Concurrent refund-click loses at DB layer (REF-08). Mirrors v1.3 `uq_membership_freeze_periods_active_per_membership`.
  - **Why:** PAY-02 verbatim; serializability через partial UNIQUE — proven pattern.
- **D-32-05:** FK `received_by_user_id` — `ON DELETE RESTRICT` (нельзя удалить пользователя с привязанными платежами; soft-delete users остаётся возможен через `deleted_at`). FK `audit_log_id` — `ON DELETE SET NULL` (если когда-нибудь audit retention pruning landed, payments не падают). FK `refund_of` уже `ON DELETE RESTRICT` per PAY-01.
  - **Why:** Forensic integrity для received_by_user_id (cannot orphan a payment from its acceptor); audit_log link защищает от phantom-row нюанса при future retention.
- **D-32-06:** Index'ы для list endpoints: `ix_payments_subject (subject_kind, subject_id)` (used by `/memberships/{id}/payments` and `/clients/{id}/payments` через JOIN/subquery), `ix_payments_received_by_user_id`, `ix_payments_received_at DESC` (для default ORDER BY на `/payments` global list). Mirrors clients/memberships index conventions.

### memberships.cancellation_reason ALTER (REF-01)

- **D-32-07:** `ALTER TABLE memberships ADD COLUMN cancellation_reason TEXT NULL` без default. Существующие cancelled rows получают NULL — historical accuracy (мы НЕ можем сказать, refund ли это был; treating as legacy/unknown). CHECK constraint `ck_memberships_cancellation_reason_when_cancelled` НЕ добавляется (NULL означает «pre-refund-feature cancel» — legacy data backwards compat). Future cancels MAY populate `cancellation_reason` (refund uses literal `'refunded'`; admin cancel может оставлять NULL или вписать custom — `MembershipCancelRequest` уже принимает `reason` field, но в schemas хранится в `audit_log` payload, не в column; D-32-07 разрешает мигрировать значение в column в Phase 32 если planner посчитает уместным).
  - **Why:** Verbatim per REF-01 «using existing `_assert_can_transition` + new `cancellation_reason: 'refunded'` column». NOT NULL constraint создаёт backfill burden без бизнес-ценности; NULL ok.
- **D-32-08:** Sentinel constant `CANCELLATION_REASON_REFUNDED = 'refunded'` в `app/modules/memberships/constants.py`. Service вызывает `_set_cancellation_reason(membership, CANCELLATION_REASON_REFUNDED)` явно при refund — НЕ магическая строка inline.
  - **Why:** Mirror existing `MEMBERSHIP_STATUS_TRANSITIONS` constant pattern; tests на статус-transition могут проверять через символ, не строку.

### Module structure (PAY-03)

- **D-32-09:** Module shape `app/modules/payments/`: `__init__.py`, `router.py`, `service.py`, `repository.py`, `schemas.py`, `permissions.py` (optional, может быть пустой stub если permissions выражены через `require_permission(Action.X, Resource.PAYMENTS)` напрямую — следуем memberships pattern), `models.py` (extends existing stub из Plan 30-03 с финальными колонками + CHECK + UNIQUE — НЕ replace, а evolution через ALTER в migration; declarative class заполняется реальными `Mapped[]` attrs соответствующими migration columns), `constants.py` (subject_kind literals — `SUBJECT_KIND_MEMBERSHIP = 'membership'`, `SUBJECT_KIND_PT_PACKAGE = 'pt_package'`, `SUBJECT_KIND_REFUND = 'refund'`).
  - **Why:** Mirrors clients/memberships module shape (validated в Phase 8/16); reuse existing stubs из Plan 30-03 не replace.
- **D-32-10:** Service functions exposed:
  - `record_payment(session, *, subject_kind, subject_id, amount_kopecks, method='cash', received_by_user_id, audit_actor) → Payment` — sale-side; **CALLER-OWNS-TXN** (no internal `await session.commit()`). Calls `audit.emit('payment_recorded', ...)` с computed `payment_row_hash`. Returns ORM Payment instance.
  - `issue_refund(session, *, original_payment_id, refund_user_id, reason, audit_actor) → Payment` — refund-side; **CALLER-OWNS-TXN**. Loads original Payment (raises 404 if missing), computes `payment_row_hash` over ORIGINAL row's 8 stable columns, INSERTS negative-amount refund row с `refund_of=original_payment_id` (IntegrityError на `uq_payments_refund_of_alive` → maps в 409 `already_refunded`), emits `refund_issued`. Returns new refund Payment instance. **NOT** mutates subject (membership/pt_package status transition — caller's responsibility).
  - Both functions follow SVC001 commit-gate caller-owns-txn declaration: docstring-level `# caller-owns-txn` marker (mirrors existing pattern), AST walker accepts module-level functions без `commit()` если docstring/comment declares caller-owned (Plan 30-03 SVC001 walker scope включает `payments/service.py`).
  - **Why:** PAY-03 verbatim «caller-owns-txn discipline (D-03)»; refund flow требует орchestratorа который держит UoW (memberships.service.refund_membership) — payments.service must NOT commit самостоятельно.

### Refund orchestration (REF-01..REF-07)

- **D-32-11:** Refund orchestrator живёт в `memberships.service.refund_membership(session, *, membership_id, actor, reason) → MembershipResponse`. **Owns the transaction** (explicit `await session.commit()` at end). Sequence inside UoW:
  1. Load membership (404 `membership_not_found` if missing/soft-deleted).
  2. Status guard (REF-01 + `_assert_can_transition`): allowed source statuses `{'active','expired'}` → `'cancelled'`; status `'frozen'` → 409 `must_unfreeze_first` (B-08, before generic transition check — specific code wins); status `'cancelled'` → 409 `invalid_transition` (already cancelled, includes prior-refunded case).
  3. Renewed-source guard (REF-04 / B-09): `EXISTS (SELECT 1 FROM memberships WHERE previous_membership_id = membership_id AND deleted_at IS NULL)` → 409 `cannot_refund_renewed_source`. Detection в repository.py helper `has_renewal_descendants(session, membership_id)`.
  4. Load ORIGINAL `payments` row: `subject_kind='membership' AND subject_id=membership_id AND amount_kopecks > 0 ORDER BY received_at ASC LIMIT 1` (sales-side payment). 404 `original_payment_not_found` if missing (shouldn't happen after Phase 32 land — все memberships sold через recorder; legacy memberships без payment ставим под 409 `legacy_membership_no_payment` для observability в production data).
  5. Call `payments.service.issue_refund(...)` (Protocol slot consumer — НЕ direct import; goes через `core.dependencies.get_payment_refunder()`). Returns new refund Payment instance.
  6. Transition status `→ 'cancelled'` через `_assert_can_transition` + set `cancellation_reason = 'refunded'`.
  7. `audit.emit('membership_refunded', ...)` с payload `{membership_id, client_id, refund_payment_id, reason}`.
  8. `await session.flush()` → translate IntegrityError on `uq_payments_refund_of_alive` → 409 `already_refunded`.
  9. `await session.commit()`.
  10. Return `MembershipResponse` (refreshed).
  - **Why:** Symmetric с v1.3 freeze/unfreeze flow (single orchestrator в memberships.service consumes Protocol slot); status guard order (frozen-specific before generic) — invariant Phase 25 D-25-07.
- **D-32-12:** Order of audit events в refund UoW: `refund_issued` (внутри `issue_refund`, payment-side) → `membership_refunded` (внутри orchestrator, subject-side). `payment_recorded` уже existed от sale-time (Phase 32 modifies `create_membership` to emit it). Chain readable через `audit_log.created_at` ASC; ROADMAP SC #5 mention `payment_refunded` is a typo — actual locked event is `refund_issued` (Plan 30-01 `LOCKED_AUDIT_EVENTS` row 183).
  - **Why:** ROADMAP terminology drift (`payment_refunded` vs locked `refund_issued`) — locked frozenset wins; planner записывает в SUMMARY что использован `refund_issued`.
- **D-32-13:** Refund request schema `MembershipRefundRequest(BaseModel)`: `reason: str` с `Field(min_length=1, max_length=200)`. `model_config = ConfigDict(extra='forbid', alias_generator=to_camel, populate_by_name=True)` — extends `BackendSchemaBase` НО с `extra='forbid'` override (REF-05 explicit reject `amount_kopecks` + любых других extras). Test: POST с body `{"reason":"x","amountKopecks":1000}` → 422.
  - **Why:** REF-05 verbatim «backend rejects any request body containing an explicit `amount_kopecks` (forbidden field at schema layer)»; `extra='forbid'` proper enforcement.

### payment_recorder Protocol slot + sale-flow integration (PAY-04, PAY-05)

- **D-32-14:** Two Protocol slots в `app/core/dependencies.py`:
  ```python
  class PaymentRecorder(Protocol):
      async def __call__(
          self,
          session: AsyncSession,
          *,
          subject_kind: str,
          subject_id: UUID,
          amount_kopecks: int,
          method: str = "cash",
          received_by_user_id: UUID,
          audit_actor: CurrentUser,
      ) -> "Payment": ...

  class PaymentRefunder(Protocol):
      async def __call__(
          self,
          session: AsyncSession,
          *,
          original_payment_id: UUID,
          refund_user_id: UUID,
          reason: str,
          audit_actor: CurrentUser,
      ) -> "Payment": ...
  ```
  Plus `register_payment_recorder(...)` + `register_payment_refunder(...)` + module-level slot accessor helpers `get_payment_recorder()` / `get_payment_refunder()` (return registered callable or raise `RuntimeError("payment_recorder not registered")` — defensive raise, mirrors `_user_loader` pattern, NOT silent None like `_active_membership_resolver`).
  - **Why:** Payments — load-bearing; missing recorder при `create_membership` = silently selling без денег == bug. Defensive raise per Phase 5 `_user_loader` precedent (line 60).
- **D-32-15:** Protocol slot wiring location: ЭКСКЛЮЗИВНО `app/main.py:create_app()`, после `register_active_membership_resolver(...)` и перед `register_client_by_telegram_resolver(...)` (alphabetic by feature). НЕ wired в `app/workers/telegram_bot.py:main()` — bot не sells (только `/checkin`) и не refunds (reception-only flow); defensive double-wiring discipline TRN-06/REG-29-03 не применяется к payments.
  - **Why:** PAY-04 verbatim «registered exclusively from `app/main.py:create_app()`»; bot scope не включает payments в v1.4.
- **D-32-16:** `memberships.service.create_membership` modification (PAY-05): после `repository.insert_membership(...)` + `await session.flush()` (surface FK violations первыми) и ПЕРЕД `audit.emit('membership_sold', ...)`:
  ```python
  payment = await get_payment_recorder()(
      session,
      subject_kind=SUBJECT_KIND_MEMBERSHIP,
      subject_id=membership.id,
      amount_kopecks=membership.price_kopecks_snapshot,  # MANDATORY symmetry
      method="cash",
      received_by_user_id=actor.id,
      audit_actor=actor,
  )
  ```
  `audit.emit('membership_sold')` payload gains `payment_id: payment.id` field (NB: `membership_sold` event payload schema is FREE-FORM per D-30-02 backfill scope, не в `AUDIT_PAYLOAD_SCHEMAS` registry; добавление поля не ломает existing validation). Server-enforced equality `payment.amount_kopecks == membership.price_kopecks_snapshot` — НЕ принимаем `amount_kopecks` от клиента, derive от server-side snapshot.
  - **Why:** PAY-05 verbatim «sale must record `payment.amount == membership.price_kopecks_snapshot` (mandatory snapshot symmetry); CHECK enforced server-side»; client cannot lie about cash received because server uses snapshot, not request body.
- **D-32-17:** Sale endpoint `POST /api/v1/memberships` schema (`MembershipCreateRequest`) — никаких новых полей. `amount_kopecks` НЕ принимается в body (server derives). Эта точка subtle: FE-12 показывает «Получено наличными» input по UX, но wire format сохраняет server-authoritative semantic. Frontend defaults `amount` к `plan.price_kopecks` и ENFORCES equality client-side; server игнорирует/rejects если client попытается передать иначе.
  - **Why:** Server cannot trust client-supplied amount при cash sale (anti-fraud); server-snapshot symmetry — единственный безопасный invariant.

### Idempotency-Key dependency (PAY-09)

- **D-32-18:** Implementation как FastAPI per-route Dependency `verify_idempotency` в новом файле `app/core/idempotency.py`:
  ```python
  async def verify_idempotency(
      request: Request,
      redis: Redis = Depends(get_redis),
  ) -> str:
      key = request.headers.get("idempotency-key")
      if not key:
          raise HTTPException(400, detail={"code": "idempotency_key_required"})
      if not _is_valid_idempotency_key(key):  # ≤128 chars, [A-Za-z0-9_-:]
          raise HTTPException(400, detail={"code": "idempotency_key_invalid_format"})
      return key
  ```
  Wire: `Depends(verify_idempotency)` declares в route signature ПОСЛЕ `Depends(require_permission)` и `Depends(verify_csrf)` (RBAC-04 ordering: auth → rbac → csrf → idempotency).
  - **Why:** Per-route dependency mirrors `verify_csrf` discipline (Phase 4); middleware вариант отвергнут — too broad blast radius, harder testing.
- **D-32-19:** Replay/cache mechanic — second-layer wrapper Dependency `idempotent_response` (returns context manager):
  - First call: `SET sz:idem:{key} <placeholder> NX EX 3600`. If NX wins → run route, capture response (status + body), `SET sz:idem:{key} <serialized envelope> EX 3600` (overwrite placeholder), return response.
  - If NX loses (key exists): load stored value. If still placeholder → 409 `idempotency_in_flight` (concurrent submission, second call retries later). If serialized envelope → return cached response status+body verbatim.
  - Body equality check: include SHA-256 body hash в stored envelope; if second-call body hash differs от stored → 422 `idempotency_key_reuse` (RFC 8594 draft semantic).
  - **Why:** Standard idempotency-key pattern; placeholder phase prevents thundering-herd на flush-during-flight; body-hash diff detects key reuse with different intent.
- **D-32-20:** Scope (PAY-09): `verify_idempotency` + `idempotent_response` mounted на `POST /api/v1/memberships` (sale) в Phase 32. `POST /api/v1/pt-packages` (Phase 33 PT-07) consumes the dependency без изменений. `POST /api/v1/memberships/{id}/refund` НЕ требует idempotency-key (DB partial UNIQUE `uq_payments_refund_of_alive` уже даёт idempotency-equivalent через 409 `already_refunded`). `POST /api/v1/memberships/{id}/freeze`/`unfreeze`/`renew` — НЕ требуют (status transitions guarded by `_assert_can_transition` — second call gets 409 invalid_transition naturally).
  - **Why:** Idempotency-Key — для операций где double-submit создаёт duplicate state (sale → duplicate payment row), не для state-machine transitions где natural guards уже есть. Scope minimal.

### `payment_row_hash` helper (D-30-04 final selection)

- **D-32-21:** Helper file `apps/backend/app/core/audit_hash.py`. Exports:
  ```python
  def payment_row_hash(row: Mapping[str, Any]) -> str:
      """SHA-256 canonical-JSON of payment row; pattern '^sha256:[0-9a-f]{64}$'."""
  ```
  Architectural boundary: `core/audit_hash.py` MUST NOT import `app.modules.*`. Принимает `Mapping[str, Any]` (dict) — caller сериализует ORM row в dict с фиксированным набором колонок.
  - **Why:** core ⊥ modules contract per .importlinter; helper internal-only, не consumed downstream.
- **D-32-22:** Hash inputs — 8 stable columns: `{id, subject_kind, subject_id, amount_kopecks, method, received_at, received_by_user_id, refund_of}`. EXCLUDED: `audit_log_id` (заполняется после hash compute — иначе circular dependency). Serialization: UUID → `str(uuid)`, datetime → `dt.astimezone(UTC).isoformat()` (UTC normalized — host TZ irrelevant; tests run в любой TZ дают тот же hash), int → as-is, str → as-is, None → JSON `null`.
  - **Why:** UTC normalization — host TZ irrelevant для определения equality; `audit_log_id` exclusion — chicken-and-egg (audit row id назначается после hash сериализуется в payload).
- **D-32-23:** Algorithm: `hashlib.sha256(json.dumps(canonicalized_dict, sort_keys=True, separators=(',', ':'), ensure_ascii=False, default=str).encode('utf-8')).hexdigest()` prefixed `'sha256:'`. NOT RFC 8785 JCS — overkill для internal forensic hash; Python `json.dumps(sort_keys=True, separators=(',', ':'))` deterministic для primitive types (string/int/null/UUID-as-string/datetime-as-isoformat). Unit test locks: одинаковый row в любой TZ/locale → same hash; flip любой column → different hash.
  - **Why:** Pragmatic — reproducible determinism достаточен; RFC 8785 добавляет сложность without benefit для single-process Python hash.

### List endpoints (PAY-06, PAY-07, PAY-08)

- **D-32-24:** `GET /api/v1/payments` (owner-only — `(VIEW, PAYMENTS)` в OWNER_ONLY per Plan 30-02). Query params: `subjectKind` (enum), `subjectId` (UUID), `receivedByUserId` (UUID), `receivedFrom` (date), `receivedTo` (date), `page` (default 1), `pageSize` (default 50, max 200). Date range inclusive: `received_at >= receivedFrom 00:00 Europe/Moscow AND received_at < (receivedTo + 1 day) 00:00 Europe/Moscow` — half-open semantic правильнее inclusive ::date cast (TZ-safe).
  - **Why:** PAY-06 verbatim filter set; Europe/Moscow TZ — project convention (v1.2 gym_date STORED column pattern); half-open range avoids edge boundary bugs (last-second sale на дне receivedTo не теряется).
- **D-32-25:** `GET /api/v1/clients/{id}/payments` (reception+owner — `(VIEW, PAYMENTS)` outside OWNER_ONLY? No — `(VIEW, PAYMENTS)` уже locked в OWNER_ONLY Plan 30-02. Per-client view использует `Action.VIEW, Resource.CLIENT_PAYMENTS` virtual через client-scoped permission? **Actually NO** — per Plan 30-02 commit e8beda0 не было `CLIENT_PAYMENTS` resource added; решение: использовать существующий `(VIEW, CLIENTS)` + cross-resource check в router. Альтернатива: добавить `(VIEW, PAYMENTS)` в reception scope для client-scoped endpoint только. Planner finalizes — D-32-25 ставит decision на: использовать **route-level custom guard** в роутере `clients/{id}/payments` который admits reception ТОЛЬКО если client `id == request.user.id`? Нет — reception видит чужих клиентов (это их работа). Recommended path: per PAY-07 verbatim «reception+owner» — добавить exception `(VIEW, PAYMENTS, scope='client')` через router-level custom Depends `require_client_scoped_payment_view`. Planner может выбрать (a) custom Depends, (b) split `Resource.CLIENT_PAYMENTS` enum addition (BUT этот ушёл из scope Plan 30-02 — добавление в Phase 32 nontrivial), или (c) overload existing permission matrix.
  - **Why:** Verbatim per PAY-07 «reception+owner» — но Plan 30-02 локнул `(VIEW, PAYMENTS)` как owner-only global view. Cleanest: split (a) — отдельный router-level Depends `require_payments_view_for_client`/`for_membership` admits reception when scope-bound (mirrors v1.1 clients module которая имеет `(VIEW, CLIENTS)` reception+owner). Detailed РBAC matrix decision — planner D-32-25 disambiguation point.
- **D-32-26:** `GET /api/v1/memberships/{id}/payments` (reception+owner) — same scoped-view treatment как PAY-07. Returns payment history of one membership (sale + optional refund). Pagination envelope (rare more than 2 entries, но format consistency wins).

### Plan splitting

- **D-32-27:** Phase 32 разбивается на **3 plans** (mirrors v1.3 Phase 25 freeze foundations → action → tests cadence):
  - **Plan 32-01 — Foundations: migration + payments module + Protocol slots + audit_hash helper + idempotency**: `0012_payments.py` (CREATE TABLE payments + ALTER memberships cancellation_reason), `app/modules/payments/{models,schemas,repository,router,service,permissions,constants,__init__}.py` (real bodies replace Plan 30-03 stubs), `app/core/dependencies.py` extension (2 Protocol slots + 2 register fns + 2 get accessor helpers), `app/main.py:create_app()` 2 register calls, `app/core/audit_hash.py` (payment_row_hash helper), `app/core/idempotency.py` (verify_idempotency + idempotent_response dependencies), 3 GET endpoints (`/api/v1/payments` global + `/clients/{id}/payments` + `/memberships/{id}/payments`), permissions matrix extension for scoped-view guards if needed, unit tests on audit_hash determinism + idempotency happy/replay/conflict paths. Requirements: PAY-01..04, PAY-06..09, REF-02 endpoint shape (schemas + Protocol slot, NO router landing).
  - **Plan 32-02 — Sale-flow integration + audit emission**: modify `memberships.service.create_membership` to consume `payment_recorder` in same UoW (PAY-05), extend `audit.emit('membership_sold')` payload to include `payment_id`, emit `payment_recorded` event with computed `payment_row_hash` for sale row, integration tests covering: sale records payment with snapshot symmetry, snapshot mismatch impossible (server derives), idempotency replay returns identical envelope, idempotency same-key/different-body → 422, audit chain `membership_sold + payment_recorded` traceable. Requirements: PAY-05, PAY-10.
  - **Plan 32-03 — Refund flow + 409 guards + tests**: `POST /api/v1/memberships/{id}/refund` endpoint + `memberships.service.refund_membership(...)` orchestrator + `repository.has_renewal_descendants` helper + `MembershipRefundRequest` schema with `extra='forbid'`, 409 mapping for frozen/renewed-source/already-cancelled/already-refunded, REF-TEST-01 concurrent refund (PG integration test), audit chain test (`payment_recorded → refund_issued → membership_refunded`), REF-05 forbidden-field test (`amountKopecks` in body → 422), end-to-end test sale → refund → balance check. Requirements: REF-01, REF-03..08.
  - **Parallelization:** Plan 32-01 must land first (migration + module shape gate the others). Plans 32-02 and 32-03 parallel-eligible after Plan 32-01 stable (no overlapping files: 32-02 touches `memberships/service.py:create_membership` + tests; 32-03 touches `memberships/service.py:refund_membership` (new function) + `memberships/router.py` + tests — same files но disjoint sections; Phase 25/26 продемонстрировал что это works).
  - **Why:** 3-plan split — discrete UoW per concern, atomic rollback per concern; mirrors v1.3 Phase 25/26/27 cadence; tests live alongside owners feature (NOT standalone «test plan»).

### Claude's Discretion

- **PAY-07/PAY-08 RBAC modeling** — choice between (a) router-level scoped-view Depends, (b) new `Resource.CLIENT_PAYMENTS`/`Resource.MEMBERSHIP_PAYMENTS` enum entries (would require admin-web parity update), or (c) overload — planner picks при имплементации Plan 32-01. Constraint: must keep three-way parity test green (backend ↔ admin-web `can.ts` ↔ `registry.ts`). Recommendation: (a) router-level Depends `require_payments_view_for_subject(...)` — local enforcement, no enum churn.
- **Migration consolidation 0012 vs 0012+0013** — bundled CREATE TABLE payments + ALTER memberships in 0012 is recommended (D-32-01), but planner may split if Alembic autogenerate emits warnings about mixing concerns. Constraint: refund flow tests require both ops; ordering must satisfy fixture build.
- **`MembershipCancelRequest.reason` → `cancellation_reason` column migration** — existing cancel endpoint accepts `reason` but stores в audit only (not column). D-32-07 leaves column populate behaviour to planner: simplest = ONLY refund populates `'refunded'`, admin cancel leaves NULL. Alternative: admin cancel populates column with provided reason. Planner picks; recommendation = leave admin cancel NULL для v1.4 (column scope is sentinel only).
- **`payment_row_hash` calling convention** — service helper signature `payment_row_hash(row: Mapping[str, Any]) -> str` accepts dict. Planner may add typed `payment_row_hash_from_orm(payment: Payment) -> str` wrapper which extracts the 8 fields. Recommended: provide both — primitive helper for tests/audit, ORM helper for sale-flow callsite.
- **Idempotency-Key key character set + max length** — recommended `^[A-Za-z0-9_:-]{1,128}$`. RFC 8594 draft allows longer; project limit conservative. Planner finalizes regex constant `IDEMPOTENCY_KEY_PATTERN` in `core/idempotency.py`.
- **`refund_issued` payload `reason` field** — REF-07 not explicit, but `RefundIssuedPayload` Plan 30-01 has `reason: str` (line 121). Planner reuses; no schema mutation needed.
- **In-flight idempotency placeholder TTL** — D-32-19 uses single TTL=3600 for both placeholder and final envelope. Planner may shorten placeholder to 60s (timeout safety) — recommendation: keep 3600 для simplicity; in-flight placeholder rare и max-90s pessimistic for sale flow.

</decisions>

<canonical_refs>
## Canonical References

**Downstream agents MUST read these before planning or implementing.**

### v1.4 Milestone-level Contracts (CRITICAL)
- `.planning/REQUIREMENTS.md` §PAY + §REF — PAY-01..10 + REF-01..08 verbatim requirements (lines 50–72); B-01..B-12 bedrock decisions listed in header.
- `.planning/ROADMAP.md` §Phase 32 — phase goal + 5 success criteria; depends on Phase 30 (delivered) + Phase 31 (delivered).
- `.planning/PROJECT.md` §Key Decisions — B-01 append-only payments, B-02 full-refund-only, B-07 uniform reception refund + H-13 AlertDialog mitigation, B-08 frozen-refund 409, B-09 renewed-source 409; v1.4 milestone scope; CLAUDE.md project constraints.
- `.planning/STATE.md` §Accumulated Context — Phase 30/31 implementation log (audit_payloads + RBAC parity + architectural gates + trainers module).
- `.planning/phases/30-foundations-tech-debt-bedrock/30-CONTEXT.md` §Implementation Decisions — D-30-01..D-30-12 (audit payload registry, append-only walker, RBAC matrix, plan splitting); D-30-04 `payment_row_hash` canonicalization pencilled to Phase 32.
- `.planning/phases/31-trainers-module/31-CONTEXT.md` §Code Insights — Phase 31 patterns (caller-owns-txn vs explicit-commit, Protocol slot registration shape, repository IntegrityError mapping, owner-only route guards) reused verbatim здесь.

### Phase 30 Deliverables (CONSUME from Phase 32)
- `apps/backend/app/core/audit_payloads.py` lines 76–135 — locked Pydantic schemas: `PaymentRecordedPayload`, `RefundIssuedPayload`, `MembershipRefundedPayload`. Service emit-callsites pass kwargs verbatim; `payment_row_hash` field pattern `^sha256:[0-9a-f]{64}$` locked.
- `apps/backend/app/core/audit_payloads.py` line 284 §`AUDIT_PAYLOAD_SCHEMAS` registry — 3 payment-side entries locked (`payment_recorded`/`refund_issued`/`membership_refunded`). `audit.emit()` validates payload через `Schema.model_validate(...)` после `LOCKED_AUDIT_EVENTS` check.
- `apps/backend/app/core/audit.py` §`LOCKED_AUDIT_EVENTS` lines 181–184 — 3 v1.4 payment events locked: `('payment_recorded','payment')`, `('refund_issued','payment')`, `('membership_refunded','membership')`. Note: NO `('payment_refunded',...)` — ROADMAP SC #5 mention is terminology drift; actual locked event is `refund_issued`.
- `apps/backend/app/core/permissions.py` §`Resource.PAYMENTS` + `OWNER_ONLY` (lines 47+74) — `Resource.PAYMENTS = "payments"`; reception scopes: `(CREATE, PAYMENTS)` (internal — recorder consumer; not user-facing), `(REFUND, MEMBERSHIPS)`; owner-only: `(VIEW, PAYMENTS)` global, `(LIST, PAYMENTS)`. `(REFUND, MEMBERSHIPS)` outside OWNER_ONLY (B-07).
- `apps/backend/.importlinter` §`[importlinter:contract:modules-independent]` — `payments` already в modules list (Plan 30-03). Plan 32-01 fills the placeholder; no contract changes.
- `apps/backend/tests/unit/test_service_commit_gate.py` §`_LIVE_MODULES` — `payments/service.py` уже в scope (Plan 30-03). Plan 32-01 service functions MUST either explicitly `await session.commit()` или явно declare caller-owned-tx via docstring marker (D-32-10).
- `apps/backend/tests/unit/test_payments_appendonly.py` — append-only AST walker live-bound против `app/modules/**/service.py`. Plan 32-01 service.py MUST pass: only plain `INSERT`/`session.add(Payment(...))`/`session.execute(insert(Payment))`; FORBIDDEN: `update(Payment)`, `delete(Payment)`, `session.delete(<Payment>)`, `on_conflict_do_update()`. 5 negative fixtures already exist в `tests/unit/fixtures/payments_violation_*.py`.
- `apps/backend/app/modules/payments/__init__.py` + `models.py` + `service.py` — placeholder stubs (commit be962d7); Plan 32-01 REPLACES content (NOT recreate file). Model evolution: stub `Payment(UUIDPkMixin, Base)` → real ORM with columns/CHECK/UNIQUE.
- `apps/admin-web/src/shared/session/can.ts` + `registry.ts` — `Resource.PAYMENTS` + entries уже locked (Plan 30-02 e8beda0); admin-web byte-parity test зелёный без изменений в Phase 32 (UI lands Phase 35).

### Reusable Backend Patterns
- `apps/backend/app/modules/memberships/service.py` §`create_membership` (line 480) — sale entry point Plan 32-02 modifies. Closest analog для payment_recorder consumer call.
- `apps/backend/app/modules/memberships/service.py` §`freeze_membership` / `unfreeze_membership` / `cancel_membership` (Phase 25 D-25-07..09) — orchestrator pattern reused для `refund_membership` (D-32-11): single UoW + status guard + repository helper + audit emit + explicit commit.
- `apps/backend/app/modules/memberships/constants.py` §`MEMBERSHIP_STATUS_TRANSITIONS` + `_assert_can_transition` (Phase 24 INFRA-16) — refund flow uses existing guard ('active'→'cancelled', 'expired'→'cancelled'); frozen-specific 409 fires BEFORE generic check.
- `apps/backend/app/modules/memberships/repository.py` — IntegrityError → 409 mapping pattern (phone_exists, already_frozen); refund flow adds `_is_refund_of_uniqueness_conflict()` mirror for `uq_payments_refund_of_alive`.
- `apps/backend/app/modules/memberships/repository.py` §query for active/non-soft-deleted rows — pattern для `has_renewal_descendants(session, membership_id)` helper.
- `apps/backend/app/core/dependencies.py` lines 55 (`register_user_loader` defensive raise pattern), 93 (`register_active_membership_resolver` silent-None pattern) — payment slots use DEFENSIVE RAISE (D-32-14) per load-bearing nature.
- `apps/backend/app/core/dependencies.py` §`verify_csrf` — per-route Dependency shape mirrored by `verify_idempotency` (D-32-18).
- `apps/backend/app/core/redis.py` §`get_redis` per-request dependency — consumed by `verify_idempotency` (D-32-18).
- `apps/backend/app/modules/clients/repository.py` §`escape_like_pattern` LIKE-escape — N/A для payments (no free-text search); pagination cursor pattern reused.
- `apps/backend/app/modules/memberships/router.py` §`@memberships_router.post(".../freeze", dependencies=[Depends(require_permission(...)), Depends(verify_csrf)])` — RBAC-04 ordering (auth → rbac → csrf) extended to (auth → rbac → csrf → idempotency) in Plan 32-01 sale endpoint.
- `apps/backend/app/core/schemas.py` §`BackendSchemaBase` + `ResponseEnvelope` + `PaginatedData` + `envelope()` — universal wire-format pieces; `MembershipRefundRequest` extends с `extra='forbid'` override per D-32-13.

### Prior-Phase Patterns to Mirror
- **v1.2 Phase 16 (membership_plans) — partial UNIQUE + IntegrityError → 409 translation**. Direct precedent для `uq_payments_refund_of_alive` 409 `already_refunded` mapping.
- **v1.2 Phase 19 (visits) — DB-level race-proof UNIQUE на STORED column**. Phase 32 partial UNIQUE на `refund_of WHERE NOT NULL` is the same discipline: DB wins the race, не app-layer.
- **v1.3 Phase 25 (freeze) — partial UNIQUE on `(membership_id) WHERE ended_at IS NULL`, concurrent test MEM-FRZ-TEST-03**. REF-TEST-01 (concurrent refund) mirrors verbatim — 2 parallel POST refunds → IntegrityError on partial UNIQUE → second 409.
- **v1.3 Phase 25 — orchestrator pattern: single service function (freeze_membership) holds the UoW, calls repository helpers, emits audit, explicit commit**. `refund_membership` (D-32-11) mirrors structurally.
- **v1.3 Phase 26 (renewal) — `previous_membership_id` self-FK query for renewed-source detection**. `has_renewal_descendants(session, membership_id)` repository helper directly extends.
- **v1.3 Phase 27 (expiring-soon) — Redis-cached state с UNIQUE table-level idempotency**. Pattern для `sz:idem:{key}` Redis cache: TTL-based, atomic SET-NX, fail-open on Redis transient failure (Phase 27 D-20-3 fail-open precedent).

### Phase 30 Outputs (Verified Available)
- 3 payment-side audit events locked in `LOCKED_AUDIT_EVENTS` frozenset (51 total).
- 3 payment payload schemas in `AUDIT_PAYLOAD_SCHEMAS` with `extra='forbid'`.
- `Resource.PAYMENTS` + OWNER_ONLY matrix entries (admin-web byte-parity locked).
- `payments/__init__.py` + `models.py` (stub `Payment(UUIDPkMixin, Base)`) + `service.py` (empty docstring placeholder) — ready to extend.
- `.importlinter` modules-independent contract includes `payments`.
- SVC001 walker scope includes `payments/service.py`.
- Append-only AST walker live against `app/modules/**/service.py` with 5 negative fixtures.
- D-30-04 `payment_row_hash` pattern `^sha256:[0-9a-f]{64}$` locked в `RefundIssuedPayload`.

</canonical_refs>

<code_context>
## Existing Code Insights

### Reusable Assets
- `app/core/database.py` `Base + UUIDPkMixin` — `payments` use ONLY these 2; NO TimestampMixin (no `created_at`/`updated_at`), NO SoftDeleteMixin (no `deleted_at`). `received_at` is the single temporal column.
- `app/core/dependencies.py` `register_*_resolver` triplet — 4th and 5th slots (`register_payment_recorder` + `register_payment_refunder`) mirror shape; defensive-raise variant (mirror `_user_loader` line 60 not `_active_membership_resolver` line 122) per load-bearing semantic.
- `app/core/schemas.py` `BackendSchemaBase` + `ResponseEnvelope` + `PaginatedData` + `envelope()` — universal wire-format pieces; `MembershipRefundRequest` extends с `extra='forbid'` override (REF-05).
- `app/core/audit.py` `audit.emit()` with payload validation (Plan 30-01) — payment events already LOCKED + schemas registered. Service calls `audit.emit('payment_recorded', resource_type='payment', actor_user_id=actor.id, resource_id=payment.id, **kwargs)` verbatim per schema fields.
- `app/core/redis.py` `get_redis` per-request dependency — consumed by `verify_idempotency` (PAY-09).
- `apps/backend/app/modules/memberships/service.py:freeze_membership` — orchestrator template для `refund_membership`: load → status guard → preventive check → repo mutation → flush+409 translation → emit → commit.
- `apps/backend/app/modules/memberships/repository.py` — IntegrityError → 409 mapping pattern reused для `uq_payments_refund_of_alive` → 409 `already_refunded`.
- `apps/backend/app/modules/memberships/router.py:@memberships_router.post(".../freeze")` — endpoint shape для `/{id}/refund`: RBAC-04 ordering (Depends order: require_permission → verify_csrf), `dependencies=[]` list, `MembershipResponse` envelope return.

### Established Patterns
- **Append-only invariant (B-01 / INFRA-22):** payments service MUST NOT call `update(Payment)`, `delete(Payment)`, `on_conflict_do_update(...)`, `session.delete(<Payment instance>)`. Walker fixtures Plan 30-03 — 5 negative tests live.
- **Caller-owns-txn (D-03) for recorder/refunder:** `payments.service.record_payment` and `payments.service.issue_refund` do NOT internally commit — outer orchestrator (memberships.service.create_membership / refund_membership) owns UoW. SVC001 walker accepts module-level functions без commit() when docstring/comment marker declares caller-owned (Phase 19 D-10 precedent).
- **Mandatory snapshot symmetry (PAY-05):** sale records `payment.amount_kopecks == membership.price_kopecks_snapshot` server-derived; client cannot supply amount. Mirrors v1.2 Phase 17 mandatory snapshot pricing on initial sale.
- **Partial UNIQUE for concurrency (PAY-02):** `uq_payments_refund_of_alive` WHERE `refund_of IS NOT NULL` — DB wins the race; IntegrityError → 409 `already_refunded`. Direct mirror of v1.3 Phase 25 `uq_membership_freeze_periods_active_per_membership`.
- **Pre-emptive 409 mapping (Phase 31 precedent):** `_is_refund_of_uniqueness_conflict()` helper in `payments/repository.py` written до first integration test, not as TODO. SVC001 lesson — 409 codes belong to the schema, not to the bug fix.
- **RBAC-04 ordering** extended: auth → rbac → csrf → idempotency. `verify_idempotency` Depends declared AFTER `verify_csrf` so 403 (rbac) and 419 (csrf) fire first; idempotency 400 (missing header) fires last.
- **D-09 hard-fail discipline** — invalid audit payload raises `pydantic.ValidationError` (programmer error). `payment_row_hash` pattern mismatch → ValidationError caught at integration boundary.
- **Defensive-raise vs silent-None Protocol slot accessor:** payment slots use DEFENSIVE RAISE (D-32-14) because missing slot at runtime = silently selling without money = invariant violation. Mirrors `_user_loader` line 60 defensive raise, NOT `_active_membership_resolver` silent-None.

### Integration Points
- New `apps/backend/alembic/versions/0012_payments.py` — линейная цепочка после `0011_trainers`. CREATE TABLE payments + ALTER TABLE memberships ADD cancellation_reason TEXT NULL. `alembic/env.py` ORM-modules list must add `import app.modules.payments.models` for autogenerate parity (Plan 30-03 INVARIANT: this was MANUAL omission in Phase 30; Phase 32 includes it).
- `apps/backend/app/main.py:create_app()` adds `register_payment_recorder(payments.service.record_payment)` and `register_payment_refunder(payments.service.issue_refund)` lines after Phase 31 trainer-slot wiring. NOT added к `app/workers/telegram_bot.py:main()` — bot не sales/refund participant.
- `apps/backend/app/api/v1/__init__.py` — `app.include_router(payments.router, prefix='/payments', tags=['payments'])`. Position: after memberships, before visits (alphabetic; planner confirms in plan).
- `apps/backend/app/modules/memberships/service.py:create_membership` — Plan 32-02 modification: 1 callsite addition after repository.insert + flush, before audit.emit. Test coverage: snapshot symmetry, recorder failure rollback (whole UoW rolls back via SAVEPOINT).
- `apps/backend/app/modules/memberships/router.py` — Plan 32-03 adds `@memberships_router.post("/{membership_id}/refund", status_code=200, dependencies=[require_permission(Action.REFUND, Resource.MEMBERSHIPS), verify_csrf], response_model=ResponseEnvelope[MembershipResponse])` endpoint.
- `apps/backend/app/modules/clients/router.py` — Plan 32-01 adds `@router.get("/{client_id}/payments", ...)` returning `ResponseEnvelope[PaginatedData[PaymentResponse]]`. Architectural: `clients/router.py` MUST NOT import `payments.models` (cross-module forbidden); router imports `payments.service.list_payments_for_client(session, client_id, ...)`. **Wait** — modules-independent contract forbids cross-module imports too. **Resolution**: list endpoint lives в `payments.router` mounted as `/api/v1/clients/{id}/payments` via FastAPI sub-prefix OR a thin client-scoped endpoint lives in `payments.router` (`@router.get("/clients/{client_id}/payments")`). **Recommended**: define ALL 3 list endpoints в `payments/router.py`:
  - `GET /api/v1/payments` (owner-only global)
  - `GET /api/v1/payments/by-client/{client_id}` (reception+owner)
  - `GET /api/v1/payments/by-membership/{membership_id}` (reception+owner)
  Naming convention `/payments/by-X/{id}` keeps all endpoints в payments module; admin-web fetches via these paths. URL shape choice — planner refines (alternative: nest under `/clients/{id}/payments` via FastAPI APIRouter `include_router(prefix=...)` clever wiring without importing clients ORM — feasible но complicates path discovery).
- `apps/backend/openapi.json` — Plan 32-01 regenerates snapshot; drift gate в Phase 35 финализирует с admin-web codegen.
- `apps/admin-web/*` — NO admin-web changes в Phase 32. Mock service, HTTP wiring, UI components — Phase 35 entirely.

### Phase 30 Outputs (Verified Available — see Canonical Refs)
- 3 payment audit events locked + 3 schemas registered.
- `Resource.PAYMENTS` + RBAC matrix entries.
- `payments/__init__.py` + `models.py` (stub) + `service.py` (empty placeholder) — ready to extend.
- Append-only walker + SVC001 walker scope включает `payments/service.py`.

### Phase 31 Outputs (Verified Available)
- Migration chain: 0011_trainers — Phase 32 0012 follows linearly.
- Protocol slot pattern (4th slot register_trainer_by_id_resolver) — payment slots are 5th + 6th.
- `cancellation_reason` on memberships does NOT exist yet (Phase 31 did not touch memberships); Plan 32-01 ALTER adds it.

</code_context>

<specifics>
## Specific Ideas

- **Migration consolidation**: One `0012_payments.py` containing CREATE TABLE payments + ALTER TABLE memberships ADD COLUMN cancellation_reason. Avoids ordering trap при тестировании refund flow (требует обе таблицы одновременно).
- **`payment_row_hash` over the ORIGINAL payment row при refund-time** — not при sale-time. Sale event payload `payment_recorded` MUST include hash, но hash recomputed at refund-time from the loaded original row, not stored on the original. Stateless форма — каждый emit-call вычисляет fresh hash from row state at that moment. Idempotent given append-only invariant: row immutable → hash deterministic.
- **Defensive-raise Protocol slots для payments** (D-32-14) — НЕ silent-None like `_active_membership_resolver`. Missing slot = invariant violation, не «no active membership». Mirrors `_user_loader` line 60.
- **`MembershipRefundRequest` extra='forbid'** override на BackendSchemaBase — REF-05 reject explicit `amountKopecks` (или любое другое extras). Test fixture: POST `/refund` с `{"reason":"x","amountKopecks":1000}` → 422.
- **Status guard ordering в refund_membership**: (1) frozen check first (specific 409 `must_unfreeze_first` B-08); (2) renewed-source check (specific 409 `cannot_refund_renewed_source` B-09); (3) generic `_assert_can_transition` (catches already-cancelled). Specific-first preserves error-message quality for operator UI surfaces.
- **`refund_issued` vs `payment_refunded` terminology** — ROADMAP SC #5 typo; locked frozenset is `refund_issued`. Planner uses `refund_issued` everywhere; SUMMARY notes the drift.
- **payment_refunder slot NOT wired в telegram_bot.py** — bot is не a participant в refund (reception-driven UI flow only). Defensive double-wiring (TRN-06 / REG-29-03 precedent) не distributes to payments — Phase 31 lesson scope-bounded.
- **3 GET endpoints in payments/router.py** — keeps cross-module discipline (clients/memberships routers НЕ import payments). URL shape `/api/v1/payments/by-client/{id}` choice — planner final refines (alternative: nested mount via FastAPI sub-prefix).
- **`Idempotency-Key` scope minimal** (D-32-20): sale only. Refund uses DB partial UNIQUE для natural idempotency; freeze/unfreeze/renew use status transitions для natural idempotency. Don't over-apply idempotency-key to operations where natural guards already exist.
- **Server-authoritative `amount_kopecks` на sale** (D-32-16/17): client UI shows «Получено наличными» input по UX (FE-12 в Phase 35), но wire payload не carries amount. Server derives from snapshot. Anti-fraud invariant — client cannot lie about cash received.
- **3 plans, not 5**: Foundations → Sale-flow → Refund-flow. Mirror v1.3 Phase 25 cadence. Tests live alongside owners (not a separate test plan).

</specifics>

<deferred>
## Deferred Ideas

- **PT-package sale recorder consumption (PT-07)** — Phase 33; `payment_recorder` Protocol slot ready in Phase 32 for consumer.
- **`POST /api/v1/pt-packages/{id}/refund` router (REF-02 wiring)** — Phase 33; payment_refunder slot ready, endpoint shape (body schema, 409 codes) documented here for symmetry.
- **admin-web UI for sale-with-payment (FE-12), refund AlertDialog (FE-13), PaymentBadge (FE-15), payment history blocks (FE-11)** — Phase 35.
- **Mock-mode service `mock/payments.ts`** + payment history mock parity — Phase 35.
- **`payment_row_hash` for `membership_refunded` / `pt_package_refunded` events** — отвергнут в Phase 30 deferred bucket. Only `refund_issued` carries hash в v1.4. Future phase may extend if forensic audit needs subject-side hash.
- **Pro-rata refunds** — out of v1.4 entirely (B-02). Defer to v1.5+.
- **End-of-day cash-drawer reconciliation / daily totals** — B-06 / v1.5+.
- **`GET /api/v1/audit-log` read API** — v1.5 (Reports + Audit Log milestone).
- **Online payments via ЮKassa + 54-ФЗ receipts** — v1.6.
- **Partial refunds / multi-payment refund flow** — out of v1.4 (B-02). Future если multi-payment per membership supported.
- **Soft-delete on payments** — explicitly forbidden by B-01 append-only invariant. Append-correction-row pattern if ever needed (v1.5+).
- **Cancellation `reason` migration from audit payload to `cancellation_reason` column for admin cancels (non-refund)** — D-32-07 leaves column NULL for admin cancels in v1.4. Future enrichment if reports need structured query.
- **Idempotency-Key for refund/freeze/unfreeze/renew** — отвергнут (D-32-20). Natural guards already provide idempotency-equivalent.
- **`Resource.CLIENT_PAYMENTS` / `Resource.MEMBERSHIP_PAYMENTS` enum entries** — отвергнут в favor of router-level scoped Depends (D-32-25). Future если broader scope-based RBAC matrix emerges.

### Reviewed Todos (not folded)
None — `gsd-sdk query todo.match-phase 32` returned 0 matches.

</deferred>

---

*Phase: 32-Payment Ledger + Sale Flow + Refund*
*Context gathered: 2026-05-15*
*Mode: --auto (single-pass; recommended defaults; no AskUserQuestion prompts)*

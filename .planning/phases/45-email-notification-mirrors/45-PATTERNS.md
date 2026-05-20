# Phase 45: Email Notification Mirrors — Pattern Map

**Mapped:** 2026-05-20
**Files classified:** 27 (7 new + 13 modified + 7 new tests)
**Analogs found:** 27 / 27 (every file has a strong in-tree analog)

---

## CRITICAL PRE-PLANNING CORRECTIONS TO CONTEXT.md

The planner MUST apply these 4 corrections — CONTEXT.md was drafted before the codebase was scouted at this depth, and these items are wrong or incomplete:

### 1. Migration filename is `0031`, not `0029`

CONTEXT.md D-45-11 / D-45-20 / canonical_refs list the migration as `0029_payment_receipts.py`, but the current Alembic head is **`0030_users_lifecycle_columns`** (verify via `grep -n "^revision\|^down_revision" apps/backend/alembic/versions/*.py | sort`). Slot 0029 is `email_send_log_hygiene` (already shipped at Phase 42 follow-up).

**Correct values:**
- File: `apps/backend/alembic/versions/0031_payment_receipts.py`
- `revision: str = "0031_payment_receipts"`
- `down_revision: str | None = "0030_users_lifecycle_columns"`

### 2. `ExpiringNotificationSentPayload` does NOT exist yet — Phase 45 must CREATE it

CONTEXT.md D-45-26 says "extend `ExpiringNotificationSentPayload` with `channel`". Verified via `grep -n "ExpiringNotification" apps/backend/app/core/audit_payloads.py` — **zero matches**. The Phase 27 `expiring_notification_sent_{7d,3d,1d}` events emit via `audit.emit` with raw kwargs and have NO registered Pydantic schema in `AUDIT_PAYLOAD_SCHEMAS`.

**Action for Phase 45:** Create `ExpiringNotificationSentPayload(BaseModel)` with `extra="forbid"` and fields: `client_id: UUID`, `telegram_chat_id: int | None`, `kind: Literal["expiring_7d", "expiring_3d", "expiring_1d"]`, `channel: Literal["telegram", "email"]`. Register all 3 tuples in `AUDIT_PAYLOAD_SCHEMAS` (around audit_payloads.py:704).

### 3. Dispatcher walker `_resolve_template` requires extension (NOT in CONTEXT.md files-modified list)

`app/integrations/email/dispatcher.py:75-87 _resolve_template` raises `KeyError` for any non-auth/users template ID. Phase 45 ships 3 new template files. Without extending the walker, every Phase 45 callsite raises `KeyError` at runtime.

**Action for Phase 45:**
- Extend `_resolve_template` with 3 new function-scoped imports (`MEMBERSHIPS_TEMPLATES`, `BOOKINGS_TEMPLATES`, `PAYMENTS_TEMPLATES`) + 3 new `if template_id in X_TEMPLATES: return X_TEMPLATES[template_id]` blocks above the `raise KeyError`.
- Add 3 corresponding `ignore_imports` entries in `apps/backend/.importlinter` (whitelist `integrations.email → modules.{memberships,bookings,payments}`). This contradicts D-45-24's "zero .importlinter changes" claim — but it's necessary.

### 4. Receipt-fanout block lands at the ORCHESTRATOR sites, not in `payments/service.py`

CONTEXT.md D-45-08 says "after `await session.commit()` in `record_payment` / `issue_refund`". But `record_payment` and `issue_refund` are `# noqa: SVC001 caller-owns-txn` — they do NOT commit. The orchestrators (sale flows in `memberships/service.py:create_membership` + `pt_packages/service.py:create_pt_package`, refund flows in `memberships/service.py:refund_membership` + `pt_packages/service.py:refund_pt_package`) commit.

**Action for Phase 45:** Add the post-commit fanout block at every orchestrator callsite of `record_payment` / `issue_refund` — wherever `session.commit()` runs after one of those returns. There are 4 such sites in v1.6.

---

## File Classification + Pattern Assignments

| File | Role | Data Flow | Closest Analog | Match Quality |
|------|------|-----------|----------------|---------------|
| `alembic/versions/0031_payment_receipts.py` | migration | DDL | `0025_password_reset_tokens.py` | exact |
| `app/modules/payments/models.py` (extend) | model | DB-write | `password_reset_token_model.py` + `MembershipNotification` | exact |
| `app/modules/payments/email_templates.py` (NEW) | template-registry | render | `app/modules/auth/email_templates.py` | exact |
| `app/modules/memberships/email_templates.py` (NEW) | template-registry | render | `app/modules/auth/email_templates.py` | exact |
| `app/modules/bookings/email_templates.py` (NEW) | template-registry | render | `app/modules/auth/email_templates.py` | exact |
| `app/modules/users/display.py` (NEW) | helper (pure-fn) | transform | `app/integrations/telegram/copy.py:pick_variant` | role-match |
| `app/integrations/email/dispatcher.py` (MOD) | dispatcher | template-lookup | self lines 75-87 `_resolve_template` | self-extend |
| `apps/backend/.importlinter` (MOD) | architecture | import-rules | existing `ignore_imports` for auth/users | self-extend |
| `app/modules/memberships/models.py` (MOD) | model | DB-write | `MembershipNotification` lines 287-324 | self-extend |
| `app/modules/bookings/models.py` (MOD) | model | DB-write | `BookingNotification` lines 175-242 | self-extend |
| `app/modules/memberships/repository.py` (MOD) | repository | DB-read | `find_expiring_candidates` lines 475-557 | self-extend |
| `app/modules/memberships/notifications.py` (NEW) | service-helper | render+enqueue | `telegram/copy.py:pick_variant` + dispatcher | exact |
| `app/modules/memberships/service.py` (MOD) | service | ARQ-enqueue+audit | `_send_expiring_notifications` lines 1457-1509 | self-extend |
| `app/modules/bookings/notifications.py` (MOD) | service-helper | render+enqueue | self lines 31-90 (Telegram-side) | self-extend |
| `app/modules/bookings/service.py` (MOD) | service | ARQ-enqueue+audit | Phase 39 FSM hooks | self-extend |
| `app/modules/bookings/repository.py` (MOD) | repository | DB-read | `find_booking_reminder_candidates` | self-extend |
| `app/modules/payments/service.py` (MOD — minor) | service | no direct change | self (commit boundary unchanged) | self |
| `app/modules/memberships/service.py` (MOD — orchestrator) | service | post-commit fanout | self `create_membership` + `refund_membership` | self-extend |
| `app/modules/pt_packages/service.py` (MOD — orchestrator) | service | post-commit fanout | analogous to memberships orchestrators | role-match |
| `app/workers/__init__.py` (MOD) | composition | eager-import | self lines 92-97 | self-extend |
| `app/core/audit_payloads.py` (MOD) | model | validation | `PaymentReceiptEmailedPayload` lines 651-666 | self-extend |
| `tests/unit/test_workers_eager_import.py` (MOD) | test | static | self lines 23-53 | self-extend |
| `tests/integration/test_expiring_email_fallback.py` (NEW) | test | integration | `tests/integration/notifications/test_idempotency_constraint.py` | exact |
| `tests/integration/test_booking_email_fallback.py` (NEW) | test | integration | same | exact |
| `tests/integration/test_payment_receipt_email.py` (NEW) | test | integration | `tests/integration/auth/test_invitation_accept.py:168-186 sandbox_email_client` | exact |
| `tests/integration/test_payment_receipt_race.py` (NEW) | test | race | `tests/integration/payments/test_payments_refund_race.py` | exact |
| `tests/unit/test_actor_display_format.py` (NEW) | test | unit | trivial pure-fn test | trivial |
| `tests/unit/test_select_expiring_variant.py` (NEW) | test | unit | determinism test | role-match |
| `tests/unit/test_locked_email_templates_phase45.py` (NEW) | test | static | `tests/unit/test_locked_email_templates_ast.py` | exact |

---

## Per-File Pattern Details

### `alembic/versions/0031_payment_receipts.py` (NEW)

**Analog:** `apps/backend/alembic/versions/0025_password_reset_tokens.py`.

**Excerpt to mirror:**
```python
revision: str = "0031_payment_receipts"
down_revision: str | None = "0030_users_lifecycle_columns"

def upgrade() -> None:
    op.create_table(
        "payment_receipts",
        sa.Column("id", sa.UUID(), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("payment_id", sa.UUID(), nullable=False),
        sa.Column("channel", sa.Text(), nullable=False),
        sa.Column("audit_correlation_id", sa.UUID(), nullable=False),
        sa.Column("to_address", sa.Text(), nullable=False),
        sa.Column("enqueued_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.CheckConstraint("channel IN ('telegram','email')", name=op.f("ck_payment_receipts_channel")),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_payment_receipts")),
        sa.ForeignKeyConstraint(["payment_id"], ["payments.id"],
            name=op.f("fk_payment_receipts_payment_id_payments"), ondelete="RESTRICT"),
        sa.UniqueConstraint("payment_id", "channel",
            name=op.f("uq_payment_receipts_payment_channel")),
    )
    op.create_index("ix_payment_receipts_audit_corr", "payment_receipts",
        ["audit_correlation_id"])
```

**Acceptance signal:** `alembic upgrade head` exits 0; `\dt payment_receipts` returns the table; `\d+ payment_receipts` lists `uq_payment_receipts_payment_channel`.

---

### `app/modules/payments/models.py` (MOD — add `PaymentReceipt`)

**Analog 1 (sibling class shape):** `app/modules/auth/password_reset_token_model.py:41-110`.
**Analog 2 (notification-table shape inside `__table_args__`):** `app/modules/memberships/models.py:287-324 MembershipNotification`.

**Excerpt to mirror:**
```python
class PaymentReceipt(Base, UUIDPkMixin):
    __tablename__ = "payment_receipts"

    payment_id: Mapped[UUIDType] = mapped_column(
        PgUUID(as_uuid=True),
        ForeignKey("payments.id", ondelete="RESTRICT",
                   name="fk_payment_receipts_payment_id_payments"),
        nullable=False,
    )
    channel: Mapped[Literal["telegram", "email"]] = mapped_column(Text, nullable=False)
    audit_correlation_id: Mapped[UUIDType] = mapped_column(
        PgUUID(as_uuid=True), nullable=False,
    )
    to_address: Mapped[str] = mapped_column(Text, nullable=False)
    enqueued_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=text("now()"), nullable=False,
    )

    __table_args__ = (
        CheckConstraint("channel IN ('telegram','email')", name="channel"),
        UniqueConstraint("payment_id", "channel",
            name="uq_payment_receipts_payment_channel"),
        Index("ix_payment_receipts_audit_corr", "audit_correlation_id"),
    )
```

**Differences vs analog:** drop `TimestampMixin` (mirror `Payment` model — only `enqueued_at` carried).

**Acceptance signal:** `grep -n "class PaymentReceipt" app/modules/payments/models.py` returns 1; `python -c "from app.modules.payments.models import PaymentReceipt; print(PaymentReceipt.__tablename__)"` prints `payment_receipts`.

---

### Email template files (3 NEW)

`memberships/email_templates.py` (6 templates), `bookings/email_templates.py` (4 templates), `payments/email_templates.py` (2 templates).

**Analog (identical for all 3):** `app/modules/auth/email_templates.py:1-112` — copy module structure byte-for-byte: dual `SandboxedEnvironment(autoescape=True/False)` + frozen `EmailTemplate` dataclass + `TEMPLATES: Final[dict[str, EmailTemplate]]` registry. Every value `# noqa: RUF001` for Cyrillic.

**Excerpt to mirror (auth/email_templates.py:51-90):**
```python
_ENV: Final[SandboxedEnvironment] = SandboxedEnvironment(autoescape=True)
_ENV_TEXT: Final[SandboxedEnvironment] = SandboxedEnvironment(autoescape=False)

@dataclass(frozen=True)
class EmailTemplate:
    subject: str
    html: Template
    text: Template

TEMPLATES: Final[dict[str, EmailTemplate]] = {
    "EMAIL_OTP_LOGIN": EmailTemplate(  # noqa: RUF001
        subject="Код входа в Sportzal",
        html=_ENV.from_string(
            "<h1>Код входа в Sportzal</h1>"
            "<p>Ваш код для входа: <strong>{{ otp_code }}</strong></p>"
            "<p>Sportzal · noreply@mail.sportzal.ru</p>"
        ),
        text=_ENV_TEXT.from_string(
            "Код входа в Sportzal\n\n"
            "Ваш код для входа: {{ otp_code }}\n\n"
            "Sportzal · noreply@mail.sportzal.ru"
        ),
    ),
}
```

**Differences per file:**
- `memberships/email_templates.py`: 6 keys `EMAIL_EXPIRING_{7D,3D,1D}_VARIANT_{A,B}`. Subjects: literal `"Ваш абонемент скоро истекает"` (all 6). Body interpolates `{{ end_date }}` Russian long-form (`16 мая 2026 г.` with NBSP between digit/`г.`). Voice mirrors Telegram analogs at `app/integrations/telegram/copy.py:40-45 EXPIRING_*_VARIANT_*`.
- `bookings/email_templates.py`: 4 keys `EMAIL_BOOKING_{CONFIRMED, CANCELLED_BY_CLIENT, CANCELLED_BY_OWNER, REMINDER_24H}`. Kind-specific subjects per CONTEXT.md specifics. Voice mirrors `app/modules/bookings/notifications.py:31-34 BOOKING_*_DM`.
- `payments/email_templates.py`: 2 keys `EMAIL_PAYMENT_RECEIPT_{SALE, REFUND}`. Pure-literal subjects `"Чек: оплата"` / `"Чек: возврат"`. Body interpolates `{{ amount }}`, `{{ paid_at }}`, `{{ plan_snapshot }}`, `{{ actor_display_name }}`. NBSPs in amount per D-45-17.

**Acceptance signal:** `python -c "from app.modules.memberships.email_templates import TEMPLATES; assert len(TEMPLATES)==6"` (and 4 for bookings, 2 for payments).

---

### `app/integrations/email/dispatcher.py` (MOD) — extend `_resolve_template`

**Analog:** self, lines 75-87.

**Excerpt to extend:**
```python
def _resolve_template(template_id: str) -> Any:
    from app.modules.auth.email_templates import TEMPLATES as AUTH_TEMPLATES
    from app.modules.users.email_templates import TEMPLATES as USERS_TEMPLATES

    if template_id in AUTH_TEMPLATES:
        return AUTH_TEMPLATES[template_id]
    if template_id in USERS_TEMPLATES:
        return USERS_TEMPLATES[template_id]
    raise KeyError(...)
```

**Differences for Phase 45:** Add 3 function-scoped imports + 3 if-blocks above the `raise KeyError`, in this order: `MEMBERSHIPS_TEMPLATES`, `BOOKINGS_TEMPLATES`, `PAYMENTS_TEMPLATES`. The docstring lines 47-51 already hint at this ("Phase 42 only registers ... Phases 44/45 extend this walker"). Plus 3 `.importlinter` `ignore_imports` entries.

**Acceptance signal:** `python -c "from app.integrations.email.dispatcher import _resolve_template; _resolve_template('EMAIL_PAYMENT_RECEIPT_SALE')"` does NOT raise KeyError.

---

### `app/modules/users/display.py` (NEW)

**Analog:** `app/integrations/telegram/copy.py:58-67 pick_variant` (pure-fn module).

**Excerpt to mirror:**
```python
def pick_variant(client_id: UUID) -> Variant:
    """Deterministic per-client A/B variant selection (Phase 27 D-27-10 anti-oracle)."""
    return "A" if (client_id.bytes[0] & 1) == 0 else "B"
```

**Phase 45 function:**
```python
def format_actor_display(full_name: str) -> str:
    """First-name + last-initial (privacy-conservative)."""
    parts = full_name.split()
    if not parts:
        return "Сотрудник"
    if len(parts) == 1:
        return parts[0]
    return f"{parts[0]} {parts[1][0]}."
```

**Acceptance signal:** `format_actor_display("Анна Петрова") == "Анна П."`.

---

### `app/modules/memberships/models.py` + `bookings/models.py` (MOD — add `channel`)

**Analog:** self (existing Mapped columns).

**Excerpt to extend (memberships/models.py:289-303):**
```python
membership_id: Mapped[UUIDType] = mapped_column(...)
kind: Mapped[str] = mapped_column(String(16), nullable=False)
sent_at: Mapped[datetime] = mapped_column(DateTime(timezone=True),
    server_default=text("now()"), nullable=False)
telegram_chat_id: Mapped[int] = mapped_column(BigInteger, nullable=False)
```

**Differences for Phase 45 (D-45-13):** Insert after `telegram_chat_id`:
```python
channel: Mapped[Literal["telegram", "email"]] = mapped_column(
    Text, nullable=False, server_default=text("'telegram'"),
)
```
Update existing `UniqueConstraint` name to `uq_membership_notifications_membership_kind_channel` (matches migration 0024 name verbatim at `alembic/versions/0024:40-41`) — add `"channel"` to the column list. Same for bookings (`BookingNotification`).

**Note about `telegram_chat_id`:** for email-channel rows, `telegram_chat_id` is nullable-in-spirit but column is NOT NULL. Pragmatic options: (a) widen column to NULLABLE in 0031 migration; (b) store `0` sentinel value on email rows. Recommendation: **option (a)** — Alembic `0031` migration ALSO alters `membership_notifications.telegram_chat_id` and `booking_notifications.telegram_chat_id` to NULLABLE. Update the ORM column declarations accordingly.

**Acceptance signal:** `alembic check` returns no drift; UniqueConstraint name in `__table_args__` ends with `_channel`.

---

### `app/modules/memberships/repository.py` (MOD)

**Analog:** self lines 52-71 (`ExpiringCandidate`) + 475-557 (`find_expiring_candidates`).

**Excerpt to extend:**
```python
@dataclass(frozen=True)
class ExpiringCandidate:
    membership_id: UUID
    client_id: UUID
    end_date: date
    chat_id: int
    kind: str
```

**Differences for Phase 45:**
- Add `client_email: str | None`, `client_full_name: str` fields.
- Widen `chat_id: int | None` (email-only clients have NULL telegram_user_id).
- SELECT: add `c.email AS client_email, c.full_name AS client_full_name`.
- WHERE: relax `c.telegram_user_id IS NOT NULL` to `(c.telegram_user_id IS NOT NULL OR c.email IS NOT NULL)` per D-45-01.
- NOT EXISTS subquery stays channel-agnostic per D-45-14 (no `mn.channel = 'telegram'` predicate).

**Acceptance signal:** `ExpiringCandidate.__dataclass_fields__` contains `client_email` and `client_full_name`; integration tests pass.

---

### `app/modules/memberships/notifications.py` (NEW file)

**Analog 1 (variant chooser):** `app/integrations/telegram/copy.py:58-67 pick_variant`. Hoist into `memberships/notifications.py:select_expiring_variant` per D-45-16. Keep `pick_variant` as a thin re-export shim in `telegram/copy.py` OR update its single caller (telegram/copy.py:82).

**Analog 2 (enqueue helper):** `app/integrations/email/dispatcher.py:enqueue_email_dispatch` — Phase 45 helper does NOT replace it, it WRAPS it through `get_email_dispatcher()`.

**CRITICAL — AST gate constraint:** Phase 41 `tests/unit/test_locked_email_templates_ast.py:42-46` requires `template_id` MUST be `ast.Constant(str)` — NO f-strings, NO variable interpolation. The helper MUST branch through 6 explicit `if/elif/else` literal-string callsites:

```python
async def enqueue_expiring_email_fallback(
    *, kind: str, client_id: UUID, client_email: str, end_date: date,
) -> UUID:
    variant = select_expiring_variant(client_id)
    audit_correlation_id = uuid4()
    end_date_ru = _format_ru_date(end_date)
    dispatcher = get_email_dispatcher()
    if kind == "expiring_7d" and variant == "A":
        await dispatcher(template_id="EMAIL_EXPIRING_7D_VARIANT_A",
                         to=client_email, audit_correlation_id=audit_correlation_id,
                         end_date=end_date_ru)
    elif kind == "expiring_7d" and variant == "B":
        await dispatcher(template_id="EMAIL_EXPIRING_7D_VARIANT_B", ...)
    elif kind == "expiring_3d" and variant == "A":
        await dispatcher(template_id="EMAIL_EXPIRING_3D_VARIANT_A", ...)
    elif kind == "expiring_3d" and variant == "B":
        ...
    elif kind == "expiring_1d" and variant == "A":
        ...
    elif kind == "expiring_1d" and variant == "B":
        ...
    else:
        raise ValueError(f"unknown kind/variant: {kind}/{variant}")
    return audit_correlation_id
```

**Acceptance signal:** `grep -c 'template_id="EMAIL_EXPIRING_' app/modules/memberships/notifications.py` >= 6; AST gate test green.

---

### `app/modules/memberships/service.py` (MOD) — extend `_send_expiring_notifications`

**Analog:** self lines 1444-1511.

**Excerpt to extend:**
```python
for cand in candidates:
    text_body = copy_module.render_expiring_dm(...)
    result = await sender.send_text_dm(bot, cand.chat_id, text_body)
    if not result.ok:
        reason = "bot_blocked" if result.blocked else "transient"
        log.warning("expiring_notification_send_failed", ...)
        continue                                                    # <-- INSERTION POINT
    async with session_factory() as write_session:                  # Telegram success branch
        try:
            write_session.add(MembershipNotification(membership_id=...,
                                                    kind=..., telegram_chat_id=...))
            await _emit_send_event(write_session, ...)
            await write_session.commit()
            sent += 1
        except IntegrityError: ...
```

**Differences for Phase 45 (D-45-02 / D-45-26):**

REPLACE the bare `continue` on line 1479 with a `if result.blocked and cand.client_email is not None:` sub-branch followed by `continue`. The sub-branch:
1. Opens a NEW write session (mirror lines 1482-1509 shape).
2. `INSERT MembershipNotification(membership_id=..., kind=..., telegram_chat_id=None, channel='email')` — requires `telegram_chat_id` to be nullable on the column (see note in memberships/models.py section above).
3. Calls `await enqueue_expiring_email_fallback(...)` — captures returned `audit_correlation_id`.
4. Calls `await _emit_send_event(write_session, ..., channel='email', audit_correlation_id=audit_correlation_id)` — REQUIRES extending `_emit_send_event` signature (lines 1339-1346) to accept `channel: Literal['telegram','email']` and pass it through to the 3 `audit.emit` calls instead of the hardcoded `channel="telegram"` at lines 1368/1380/1392.
5. Commits.
6. `IntegrityError` race-catch identical to existing branch.

ALSO add explicit `channel='telegram'` kwarg to the Telegram success branch (lines 1484-1490) when adding `MembershipNotification(...)`.

**Acceptance signal:** `grep -n "result.blocked" app/modules/memberships/service.py` matches the new sub-branch; `test_expiring_email_fallback.py` shows `channel='email'` row inserted.

---

### `app/modules/bookings/*` (MOD — mirror memberships fanout)

Same triple-file fanout pattern lands in bookings:
- `bookings/email_templates.py` (NEW) — 4 locked templates per D-45-15.
- `bookings/notifications.py` (MOD — extend with email-side render+enqueue, mirror Telegram-side at lines 31-90).
- `bookings/service.py` (MOD — Phase 39 FSM transition hooks: 3 sites for confirmed/cancelled_by_client/cancelled_by_owner) — wrap existing `send_booking_dm` call to inspect `SendResult.blocked` and call `enqueue_booking_email_fallback(...)`.
- `bookings/repository.py` (MOD — `find_booking_reminder_candidates` augment JOIN to surface `client.email + client.full_name`).
- 4 LITERAL `template_id` callsites in `if/elif/else` branches dispatching to the 4 templates.

**Acceptance signal:** `grep -c 'template_id="EMAIL_BOOKING_' app/modules/bookings/notifications.py` >= 4.

---

### `app/modules/memberships/service.py` + `pt_packages/service.py` (MOD — orchestrator post-commit fanout for payment receipts)

**Critical:** `record_payment` / `issue_refund` do NOT commit (`# noqa: SVC001 caller-owns-txn`). The fanout block lands at the ORCHESTRATOR sites:

1. `app/modules/memberships/service.py:create_membership` (sale path — calls `record_payment` then commits).
2. `app/modules/memberships/service.py:refund_membership` (refund path — calls `issue_refund` then commits).
3. `app/modules/pt_packages/service.py:create_pt_package` (sale path).
4. `app/modules/pt_packages/service.py:refund_pt_package` (refund path).

**Excerpt (orchestrator post-commit fanout, applies to all 4 sites):**
```python
# ... after await session.commit() ...

if client.email is not None:
    audit_correlation_id = uuid4()
    async with session_factory() as fanout_session:
        try:
            fanout_session.add(PaymentReceipt(
                payment_id=payment.id,
                channel='email',
                audit_correlation_id=audit_correlation_id,
                to_address=client.email,
            ))
            await audit.emit(
                fanout_session,
                "payment_receipt_emailed",
                actor_user_id=actor_user_id,
                resource_type="payment",
                resource_id=payment.id,
                payment_id=str(payment.id),
                to_email=client.email,
                receipt_kind="sale",  # or "refund"
                audit_correlation_id=audit_correlation_id,
            )
            await fanout_session.commit()
        except IntegrityError:
            await fanout_session.rollback()
            log.warning("payment_receipt_idempotency_conflict", payment_id=str(payment.id))
            return payment

    try:
        await get_email_dispatcher()(
            template_id="EMAIL_PAYMENT_RECEIPT_SALE",  # or "_REFUND"
            to=client.email,
            audit_correlation_id=audit_correlation_id,
            amount=format_money(payment.amount_kopecks),
            paid_at=_format_ru_datetime(payment.recorded_at),
            plan_snapshot=payment.subject_description_snapshot,
            actor_display_name=format_actor_display(actor.full_name),
        )
    except Exception as exc:  # noqa: BLE001
        log.warning("payment_receipt_enqueue_failed",
                    payment_id=str(payment.id), error=str(exc))
else:
    log.info("payment_receipt_skipped", reason="no_email", payment_id=str(payment.id))
```

**Acceptance signal:** `grep -n "payment_receipt_emailed" app/modules/memberships/service.py app/modules/pt_packages/service.py | wc -l` ≥ 4; integration tests `test_payment_receipt_email.py` green.

---

### `app/workers/__init__.py` (MOD)

**Analog:** self lines 92-97.

**Excerpt to extend:**
```python
from app.integrations.email.models import (  # noqa: F401
    EmailSendLog,  # Phase 42 D-42-33 — email_send_log eager-import (REG-29-04)
)
from app.modules.auth.password_reset_token_model import (  # noqa: F401
    PasswordResetToken,  # Phase 41 INFRA-38 / D-41-29 — password_reset_tokens
)
```

**Differences:** Add a third import block:
```python
from app.modules.payments.models import (  # noqa: F401
    PaymentReceipt,  # Phase 45 D-45-20 — payment_receipts eager-import (REG-29-04)
)
```

**Acceptance signal:** `python -c "import app.workers; from app.core.database import Base; assert 'payment_receipts' in Base.metadata.tables"` passes.

---

### `app/core/audit_payloads.py` (MOD) — CREATE `ExpiringNotificationSentPayload`

**Analog:** lines 651-666 `PaymentReceiptEmailedPayload` (model shape) + line ~704 registry.

**Phase 45 addition:**
```python
class ExpiringNotificationSentPayload(BaseModel):
    """Payload schema for ('expiring_notification_sent_{7d,3d,1d}', 'membership') — Phase 45 D-45-26."""
    model_config = ConfigDict(extra="forbid")
    client_id: UUID
    telegram_chat_id: int | None
    kind: Literal["expiring_7d", "expiring_3d", "expiring_1d"]
    channel: Literal["telegram", "email"]
```

Register 3 entries in `AUDIT_PAYLOAD_SCHEMAS`:
```python
("expiring_notification_sent_7d", "membership"): ExpiringNotificationSentPayload,
("expiring_notification_sent_3d", "membership"): ExpiringNotificationSentPayload,
("expiring_notification_sent_1d", "membership"): ExpiringNotificationSentPayload,
```

**Acceptance signal:** `from app.core.audit_payloads import AUDIT_PAYLOAD_SCHEMAS; assert ('expiring_notification_sent_7d', 'membership') in AUDIT_PAYLOAD_SCHEMAS`.

---

### Test files

#### `tests/unit/test_workers_eager_import.py` (MOD)

**Analog:** self lines 38-53.

**Add:**
```python
def test_payment_receipts_eager_imported() -> None:
    import app.workers  # noqa: F401
    from app.core.database import Base
    assert "payment_receipts" in Base.metadata.tables, sorted(Base.metadata.tables.keys())
```

#### `tests/integration/test_expiring_email_fallback.py` (NEW)

**Analog:** `tests/integration/notifications/test_idempotency_constraint.py:30-90`.

**Pattern:**
- Use `sender_stub` returning `SendResult(ok=False, blocked=True, error="forbidden")`.
- Register `_RecordingEmailDispatcher` via `register_email_dispatcher(...)` per `test_invitation_accept.py:168-186`.
- Use `make_client_with_telegram_and_email` factory — create or extend conftest.
- Assertions: (a) `count == 1`; (b) `membership_notifications` row exists with `channel='email'`; (c) recorder.calls has one call with `template_id="EMAIL_EXPIRING_*_VARIANT_*"`; (d) `audit_log` has `expiring_notification_sent_7d` row with `channel='email'` payload.

#### `tests/integration/test_payment_receipt_email.py` (NEW)

**Analog:** `tests/integration/auth/test_invitation_accept.py:168-186 sandbox_email_client` fixture.

**Tests:**
1. **Sale:** POST `/api/v1/memberships` for client with `email IS NOT NULL` → assert `payment_receipts (payment_id, channel='email')` row + `payment_receipt_emailed` audit row + recorder call with `template_id="EMAIL_PAYMENT_RECEIPT_SALE"`.
2. **Refund:** POST `/api/v1/memberships/{id}/refund` → same with `template_id="EMAIL_PAYMENT_RECEIPT_REFUND"`.
3. **Skip NULL email:** client.email IS NULL → no row, no audit, no recorder call, no exception.

#### `tests/integration/test_payment_receipt_race.py` (NEW)

**Analog:** `tests/integration/payments/test_payments_refund_race.py:42-72`.

**Pattern:** 2 concurrent `record_payment` fanout invocations for same `(payment_id, channel='email')` → exactly 1 `payment_receipts` row (UNIQUE catches the second). Use `db_session_real_commit`. Catch `IntegrityError` on `uq_payment_receipts_payment_channel`.

#### `tests/unit/test_actor_display_format.py` (NEW)

Cases: `("Анна Петрова", "Анна П.")`, `("Иван", "Иван")`, `("", "Сотрудник")`, `("Анна Мария Петрова", "Анна М.")`, Cyrillic NFC sanity.

#### `tests/unit/test_select_expiring_variant.py` (NEW)

Cases: determinism (same UUID → same variant), bit-0 evens → 'A', odds → 'B', distribution ~50/50 over N=1000 random UUIDs.

#### `tests/unit/test_locked_email_templates_phase45.py` (NEW)

**Analog:** `tests/unit/test_locked_email_templates_ast.py:1-60`.

**Tests:** Assert each of the 12 Phase 45 template IDs is a member of `LOCKED_EMAIL_TEMPLATES` (already pre-registered per `app/core/audit.py:273-289`). Optionally extend AST walker scope to traverse the 3 new modules.

---

## Shared Patterns

### Per-tick multi-session fanout
**Source:** `app/modules/memberships/service.py:1444-1511 _send_expiring_notifications`.
**Apply to:** ALL fanout helpers in Phase 45 (expiring email-fallback, booking-reminder email-fallback, payment-receipt fanout).
**Pattern:** Open read session → close → per-candidate (or post-commit): NEW write session → `try: write_session.add(...); await audit.emit(...); await write_session.commit(); except IntegrityError: rollback + WARN`. Enqueue email AFTER commit (best-effort).

### Literal-string audit/template IDs
**Source:** `app/modules/memberships/service.py:1339-1398 _emit_send_event` (`if/elif/else` branching).
**Apply to:** Every `audit.emit(event=...)` and every `get_email_dispatcher()(template_id=...)` callsite.
**Pattern:** event name + resource_type + template_id MUST be `ast.Constant(str)` literals. Branch through `if/elif/else` to N literal-call sites.

### Best-effort email enqueue
**Apply to:** All 3 email-fanout helpers + the payment-receipt block.
**Pattern:** `try: await get_email_dispatcher()(...); except Exception as exc: log.warning("email_fanout_failed", ...)` — never re-raise, never roll back the outer business transaction.

### EmailDispatcher stub for tests
**Source:** `tests/integration/auth/test_invitation_accept.py:168-186 sandbox_email_client`.
**Apply to:** ALL Phase 45 integration tests.
**Pattern:** `_RecordingEmailDispatcher` callable async object → `register_email_dispatcher(recorder)` in pytest fixture → restore prior dispatcher on teardown.

---

*Phase: 45-email-notification-mirrors*
*Pattern map written: 2026-05-20*

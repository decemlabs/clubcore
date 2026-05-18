# Architecture Research — v1.6 Email Channel + Multi-User Admin

**Domain:** Modular-monolith extension (FastAPI / SQLAlchemy 2.0 async / ARQ)
**Researched:** 2026-05-18
**Confidence:** HIGH — entirely grounded in the existing v1.0–v1.5 codebase patterns; no speculative external research required.

---

## TL;DR — Five Architectural Decisions

1. **Email transport** lives in `app/integrations/email/` (mirrors `app/integrations/telegram/`). Single thin outbound boundary `send_email(...)` returns a typed `EmailSendResult` (mirror of `SendResult` in `app/integrations/telegram/sender.py:17`). **No new import-linter contract needed** — `integrations-not-depend-on-modules` already covers this.
2. **Email send is always async via ARQ**, never inline in the request handler. A new task `dispatch_email` is added to `WorkerSettings.functions`; the existing `arq-worker` container runs it. **No 6th docker-compose service.**
3. **`app/modules/notifications/` stays a placeholder.** Per-domain template ownership wins (the v1.5 D-39-02 precedent: `app/modules/bookings/notifications.py` owns booking DM copy). Email templates for each domain live next to their Telegram counterparts (`app/modules/{auth,memberships,bookings,payments}/email_templates.py`). The `integrations/email/` layer is **channel-agnostic transport only** — it knows nothing about Russian copy or business events.
4. **New `app/modules/users/` module** (not an extension of `auth`). Auth keeps login/refresh/OTP/sessions; users gets CRUD + invitation + reset-password. **One new edge in `modules-independent` contract** (users joins the list); cross-module wiring via composition-root Protocol slots only.
5. **Reset-password tokens** live in a new DB table `password_reset_tokens` (NOT Redis). Mirrors the `refresh_tokens` discipline: hash-at-rest, server-side single-use, with auditability. Single-use enforcement is a partial unique on `(user_id, purpose) WHERE consumed_at IS NULL`. (Note: the STACK research recommends `itsdangerous`-signed stateless tokens — this is an open question for the spec phase; both approaches preserve the audit invariant.) Redis is wrong here because we need post-mortem auditability for any password-reset abuse.

---

## Standard Architecture (Existing — confirmed via inspection)

```
                                  ┌─────────────────────────────────────┐
                                  │       app/api/v1/router.py          │
                                  │       (HTTP entry — FastAPI)        │
                                  └──────────────────┬──────────────────┘
                                                     │
                            ┌────────────────────────┼────────────────────────┐
                            │                        │                        │
                            ▼                        ▼                        ▼
        ┌────────────────────────────┐  ┌───────────────────────┐  ┌───────────────────────┐
        │  app/modules/<domain>/      │  │  app/core/            │  │  app/api/v1/          │
        │  router / service / models  │◄─┤  dependencies.py      │◄─┤  endpoint glue        │
        │  schemas / repository       │  │  (Protocol slots —    │  │                       │
        │                             │  │  register_*)          │  │                       │
        └─────────────────────────────┘  └───────────────────────┘  └───────────────────────┘
                                                     │
                                                     ▼
                                         ┌───────────────────────┐
                                         │  app/main.py          │
                                         │  create_app()         │
                                         │  ─── composition ───  │
                                         │  register_user_loader │
                                         │  register_*resolver*  │
                                         │  register_payment_*   │
                                         │  register_booking_*   │
                                         └──────────┬────────────┘
                                                    │
                                                    ▼
                        ┌─────────────────────────────────────────────────────────┐
                        │  app/integrations/  (transport — channel-specific)      │
                        │   telegram/  email/  (← currently placeholder)          │
                        └───────────────────┬─────────────────────────────────────┘
                                            │
                                            ▼
                        ┌─────────────────────────────────────────────────────────┐
                        │  app/workers/  (separate processes)                     │
                        │   telegram_bot.py  (4th compose service — long-polling) │
                        │   __init__.py:WorkerSettings  (5th compose service —    │
                        │                                 ARQ scheduled jobs)     │
                        └─────────────────────────────────────────────────────────┘
```

**import-linter contracts:**

1. `core-not-depend-on-modules` — `app.core` ⊥ `app.modules.*`
2. `modules-independent` — listed modules cannot import each other (currently 12 modules: auth, clients, memberships, visits, trainers, schedule, bookings, billing, notifications, payments, pt_packages, pt_sessions)
3. `integrations-not-depend-on-modules` — `app.integrations` ⊥ `app.modules.*`

Documented narrative exceptions:
- **D-06** (Phase 7) — `app/workers/telegram_bot.py` may import `app.modules.auth.telegram_service`
- **D-09** (Phase 18) — each `app/workers/scheduled/<job>.py` may import ONE owning module's service
- **D-10** (Phase 20) — workers may consume cross-module slots via `HandlerContext`
- **D-39-02** (Phase 39) — `app/modules/bookings/notifications.py` may be imported by both bookings/workers AND the telegram bot worker (locked DM copy lives in the owning module, not in `integrations/telegram/copy.py`)

---

## Recommended v1.6 Structure (Additions in **bold**)

```
apps/backend/app/
├── core/
│   ├── audit.py                              # LOCKED_AUDIT_EVENTS 56 → 56 + ~11 (add up-front per v1.3 INFRA-15 lesson)
│   ├── audit_payloads.py                     # extra='forbid' Pydantic registry (extend per new event)
│   └── dependencies.py                       # + register_email_dispatcher, + register_user_session_invalidator (Protocol slots)
├── integrations/
│   ├── telegram/                             # unchanged
│   └── email/                                # ALREADY EXISTS as placeholder
│       ├── __init__.py                       # module docstring (mirror telegram/__init__.py shape)
│       ├── client.py                         # **REPLACE placeholder** → async provider adapter (see STACK.md for provider)
│       ├── factory.py                        # **NEW** — `build_email_client(*, api_key, from_addr)` mirrors `telegram/bot.py:build_bot`
│       └── templates/                        # **KEEP EMPTY.** No business copy here (D-39-02 lesson — copy lives in modules).
├── modules/
│   ├── auth/                                 # **EXTEND** (not split)
│   │   ├── service.py                        # + `invalidate_all_families_for_user(user_id)` — exported via Protocol slot
│   │   ├── email_templates.py                # **NEW** — locked Russian email copy for OTP-fallback (when Telegram blocked)
│   │   ├── password_reset_service.py         # **NEW** — issue + consume reset token + audit chain
│   │   ├── password_reset_email_templates.py # **NEW** — locked Russian copy for reset-link email
│   │   └── models.py                         # + `PasswordResetToken` ORM model (or — per STACK.md — skip table if itsdangerous-stateless)
│   ├── users/                                # **NEW MODULE** — owner-managed admin onboarding
│   │   ├── __init__.py
│   │   ├── router.py                         # POST /api/v1/users, PATCH /api/v1/users/{id}, DELETE, GET
│   │   ├── service.py                        # create_user, deactivate_user, soft_delete_user, list_users, send_invitation_email
│   │   ├── invitation_service.py             # invitation-token issuance + consumption
│   │   ├── email_templates.py                # **NEW** — locked Russian copy: USER_INVITATION_EMAIL_*
│   │   ├── repository.py                     # User CRUD (does NOT touch refresh_tokens — auth's domain via slot)
│   │   ├── schemas.py
│   │   ├── permissions.py                    # owner-only via existing `require_permission` + new (CREATE, USERS) etc.
│   │   └── constants.py                      # USER_STATUS_TRANSITIONS (active ↔ deactivated; → soft-deleted absorbing)
│   ├── memberships/
│   │   └── email_templates.py                # **NEW** — locked Russian email copy for EXPIRING_{7D,3D,1D} email variant
│   ├── bookings/
│   │   └── email_templates.py                # **NEW** — locked Russian email copy for booking confirm + reminder
│   ├── payments/
│   │   └── email_templates.py                # **NEW** — locked Russian email copy for cash payment receipt
│   └── notifications/                        # **STAYS A PLACEHOLDER.** Per-domain template ownership is the rule.
├── workers/
│   ├── __init__.py                           # + `dispatch_email` in `WorkerSettings.functions`
│   ├── scheduled/
│   │   ├── send_expiring_notifications.py    # **EXTEND** — after Telegram-DM branch, enqueue email fallback if user has email + Telegram blocked
│   │   └── send_booking_reminders.py         # **EXTEND** — same dual-channel pattern
│   ├── tasks/
│   │   └── dispatch_email.py                 # **NEW** — ARQ task; consumes `EmailEnvelope`; calls integrations/email/client.send_email
│   └── telegram_bot.py                       # unchanged
└── main.py                                   # + register_email_dispatcher
                                              # + register_user_session_invalidator
                                              # Double-wire to BOTH create_app() AND WorkerSettings.on_startup (v1.3 REG-29-03 lesson)
```

**Why this shape:**
- **`integrations/email/` parallels `integrations/telegram/` exactly** — D-39-02 confirmed channels are transport-only; business copy lives in modules. No cycle risk because `integrations` cannot import `modules` per contract 3.
- **No new `notifications` module.** v1.3 Phase 27 (`send_expiring_notifications`) and v1.5 Phase 39 (booking DMs) both prove per-domain template ownership is the working pattern. (Note: the FEATURES research suggests creating one — this is an open conflict resolved in favour of the v1.5 D-39-02 precedent.)
- **`users` is a new module, not an `auth` extension.** Auth's responsibility is "credential verification + session lifecycle." Users' responsibility is "operator roster + invitation + role assignment." These are different lifecycles.

---

## New Protocol Slots (composition-root registrations in `app/main.py`)

```python
# In app/core/dependencies.py — add new Protocol slots:

class EmailDispatcher(Protocol):
    """Enqueue an email-send for async fanout via ARQ.

    Implementation lives in app.workers.tasks.dispatch_email (queue helper).
    Synchronous return: just schedules the job; returns immediately.
    """
    async def __call__(
        self,
        *,
        to: str,
        subject: str,
        html: str,
        text: str,
        audit_correlation_id: str,
    ) -> None: ...


class UserSessionInvalidator(Protocol):
    """Invalidate all refresh-token families for a user.

    Used by users.service.deactivate_user — must kill all active sessions.
    Reaches into auth.service.invalidate_all_families_for_user via this slot
    so users module never imports auth.
    """
    async def __call__(
        self, session: AsyncSession, *, user_id: UUID, actor_user_id: UUID, reason: str,
    ) -> None: ...
```

**Composition-root wiring in `app/main.py:create_app()`** AND **`app/workers/__init__.py:WorkerSettings.on_startup`** (double-wire per REG-29-03 lesson):

```python
from app.workers.tasks.dispatch_email import enqueue_email_dispatch
register_email_dispatcher(enqueue_email_dispatch)

from app.modules.auth.service import invalidate_all_families_for_user
register_user_session_invalidator(invalidate_all_families_for_user)
```

**Key invariant:** `users.service` never has `import app.modules.auth` anywhere. It calls `get_user_session_invalidator()(session, user_id=...)` exactly as `memberships.service` calls `get_payment_recorder()` today (proven pattern from v1.4 Phase 32).

---

## import-linter Impact

### Contract 2 (`modules-independent`) — ONE mechanical addition

Add `app.modules.users` to the `modules` list in `.importlinter`. The contract is `type = independence`, so users automatically becomes mutually-forbidden with all other 12 listed modules. **No exceptions needed** — all cross-module interactions go through the composition-root slots.

### Contract 3 (`integrations-not-depend-on-modules`) — NO change

`app/integrations/email/` only imports stdlib + chosen provider SDK + `app.core.config`. The ARQ task (`app/workers/tasks/dispatch_email.py`) is the gluing layer — and workers are NOT in any forbidden-imports contract.

### Documented narrative exceptions

- **D-41-01** — `send_expiring_notifications.py` extension to call email-fallback branch via composition-root `email_dispatcher` slot (no new module import).
- **D-41-02** — `send_booking_reminders.py` extension, same reasoning.
- **D-41-03** — `app/workers/tasks/dispatch_email.py` must NOT import any `app.modules.*` — by design. Receives pre-rendered `EmailEnvelope` (HTML/text already substituted by the calling service before enqueue). **Modules render templates; workers transport bytes.**

---

## Email-Sending Path — Data Flow

### Sync request paths (signup invitation, password reset request)

```
1. Owner: POST /api/v1/users   (admin-web HTTP)
            │
            ▼
2. app/modules/users/router.py → users.service.create_user(...)
            │
            ▼
3. users.service:
   - INSERT into users (status='pending_invitation')
   - INSERT into password_reset_tokens (purpose='invitation', user_id, token_hash, expires_at, consumed_at=NULL)
     [OR — per STACK.md — issue itsdangerous-signed token, no DB row]
   - audit.emit("user_invited", actor_user_id=current_owner.id, resource_type="user", ...)
   - await session.commit()  # SVC001 commit-gate
   - get_email_dispatcher()(  # ← composition-root slot
        to=new_user.email,
        subject=...,           # from app/modules/users/email_templates.py
        html=...,
        text=...,
        audit_correlation_id=<UUID of users.user_invited audit row>,
     )
            │
            ▼
4. dispatch_email.enqueue_email_dispatch:
   - arq.create_pool().enqueue_job("dispatch_email", EmailEnvelope(...))
            │
            ▼
5. ARQ worker picks up job → app/workers/tasks/dispatch_email.py:
   - get email client from worker ctx (built by on_startup)
   - await integrations.email.client.send_email(...)
   - On EmailSendResult.ok → audit.emit("email_sent", resource_type="email", correlation_id=...)
   - On EmailSendResult.blocked → audit.emit("email_send_failed", ...)
            │
            ▼
6. HTTP response to owner returns 201 created (does NOT block on email send)
```

**Why async even for "request-time" emails:** Blocking the HTTP request on a third-party API call costs us a request worker for the duration AND couples our 200-OK semantics to the email provider's uptime. The ARQ-task pattern means email-provider-down is a delivery delay (retried via ARQ's `max_tries`), not a 500.

### Async / scheduled paths (expiring-soon, booking reminder)

Mirror v1.3 Phase 27 and v1.5 Phase 39 exactly. The cron job already enumerates affected rows; we add a per-row Telegram-first attempt; on `SendResult.blocked` AND the user has `email_verified=True`, enqueue the email dispatch.

---

## Idempotency Table Shape (Decision)

**Recommendation: extend existing per-domain tables with a `channel` column rather than create a new `email_notifications` table.**

Current state:
- `membership_notifications` — `UNIQUE (membership_id, kind)` where `kind ∈ {expiring_7d, expiring_3d, expiring_1d}`
- `booking_notifications` — `UNIQUE (booking_id, kind)` where `kind ∈ {reminder_24h}`

**Proposed extension:**
- Add `channel TEXT NOT NULL DEFAULT 'telegram'` column with CHECK `channel IN ('telegram','email')`
- Change UNIQUE to `(membership_id, kind, channel)` — a 7-day expiry can fire once on Telegram AND once on email
- Backfill existing rows to `channel='telegram'` (zero-row migration since data is reproducible by next cron run)

**Why per-domain not per-channel:**
- Audit-correlation is naturally per-business-event ("did we tell client X about their expiring membership Y?", not "what's in our email log?")
- Mirrors v1.5 D-39-02 module-ownership decision
- New event tracking added without inventing a new table — every existing query pattern keeps working with an added `WHERE channel='telegram'` filter

**Exception:** owner-targeted ops emails (user-invitation, password-reset) are NOT business-event-keyed — they belong on the token row itself (`sent_at` populated by worker on success), OR in a separate generic `email_send_attempts` table per STACK.md.

---

## Multi-User Admin Module — Detailed Shape

### `app/modules/users/` — directory layout

```
users/
├── __init__.py
├── router.py                  # POST /users, PATCH /users/{id}, DELETE /users/{id}, GET /users
├── service.py                 # business logic; calls Protocol slots only
├── invitation_service.py      # invitation-token issuance + acceptance
├── repository.py              # User CRUD; partial unique on email WHERE deleted_at IS NULL
├── schemas.py                 # camelCase aliasing
├── models.py                  # IMPORTANT: do NOT redefine `User` — see "who owns the table" below
├── permissions.py             # local actions if needed
├── constants.py               # USER_STATUS_TRANSITIONS, locked role-set
├── email_templates.py         # locked Russian copy
└── _negative_importlinter_fixture.py
```

### Critical: who owns the `users` table?

**Two viable paths (resolve in spec phase):**

**Path A (cleaner) — hoist `User` ORM from `auth/models.py` to `app/core/models.py`:**
- Pro: Eliminates the cross-module-import question entirely.
- Con: No direct ORM-hoist precedent; touches all 729 tests' imports.
- Mirrors v1.2 Phase 15 hoist of `escape_like_pattern` (but that was a function, not an ORM model).

**Path B (lighter) — leave `User` in `auth/models.py`; `users` accesses via `UserLookup` Protocol slot:**
- Pro: No mass test rewrites; smaller blast radius.
- Con: One extra Protocol slot for trivial reads.
- Mirrors existing `register_user_loader` pattern.

### RBAC additions

- `Resource.USERS` — new
- `OWNER_ONLY` frozenset adds: `(CREATE, USERS)`, `(UPDATE, USERS)`, `(DELETE, USERS)`, `(LIST, USERS)` — all four owner-locked
- Three-way byte-parity test (backend `RBAC` ↔ admin-web `can.ts` ↔ `registry.ts`) extended

### Audit events (extend LOCKED_AUDIT_EVENTS frozenset 56 → ~67)

New `(event, resource_type)` pairs (final set TBD in Phase 41 — could narrow to ~7-8 per FEATURES.md):
- `("user_invited", "user")`
- `("user_invitation_accepted", "user")`
- `("user_invitation_expired", "user")` / `("user_invitation_revoked", "user")`
- `("user_deactivated", "user")`
- `("user_reactivated", "user")`
- `("user_soft_deleted", "user")`
- `("password_reset_requested", "user")` — emitted on BOTH branches (known + unknown email) per anti-oracle invariant
- `("password_reset_completed", "user")`
- `("email_sent", "email")` — generic; correlation_id points to triggering audit row
- `("email_send_failed", "email")` — transient/blocked classification in payload

Each pair gets a corresponding Pydantic model in `app/core/audit_payloads.py` with `extra='forbid'`. Add to `LOCKED_AUDIT_EVENTS` in **Phase 41 INFRA up-front** before any callsite lands.

---

## Reset-Password Token Storage (Decision — TWO PATHS)

**Path A (this researcher's recommendation): DB table `password_reset_tokens`.**

```sql
CREATE TABLE password_reset_tokens (
    id UUID PRIMARY KEY,
    user_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    token_hash VARCHAR(64) NOT NULL,
    purpose VARCHAR(20) NOT NULL CHECK (purpose IN ('reset','invitation')),
    issued_at TIMESTAMPTZ NOT NULL,
    expires_at TIMESTAMPTZ NOT NULL,
    consumed_at TIMESTAMPTZ NULL,
    sent_at TIMESTAMPTZ NULL,
    audit_correlation_id UUID NULL REFERENCES audit_log(id),
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE UNIQUE INDEX uq_password_reset_tokens_user_id_active
    ON password_reset_tokens(user_id, purpose) WHERE consumed_at IS NULL;
```

Single-use partial unique mirrors `membership_freeze_periods` discipline. Auditable forever.

**Path B (STACK.md researcher's recommendation): itsdangerous stateless signed tokens.**

Embed `password_changed_at` in the signed payload; single-use enforced because any password change bumps that timestamp and invalidates older signed tokens. No DB row, no cleanup cron.

**Resolution:** Spec phase decides. Path B is simpler infra but loses immutable audit-trail of token issuance. Path A is heavier but matches `refresh_tokens` discipline byte-for-byte. **Both preserve the anti-oracle invariant.**

---

## Deployment Shape (Decision)

**Recommendation: NO 6th docker-compose service. Email-fanout runs inside the existing ARQ worker (5th service).**

- New ARQ task `dispatch_email` registered in `app/workers/__init__.py:WorkerSettings.functions`
- Existing `arq-worker` container also runs it
- On startup, `WorkerSettings.on_startup` builds the email client via `app/integrations/email/factory.py:build_email_client(...)` and stashes in `ctx['email_client']` — mirror of how the DB engine is stashed
- ARQ's `max_tries` + retry-with-backoff handles transient provider failures for free

**Why not a 6th service:** Email is not long-polling. Sending is one-shot HTTPS calls. A separate service adds operational complexity. ARQ already does fire-and-forget with retries.

---

## Architectural Patterns to Follow

### Pattern 1: Module-owned locked-copy templates

Locked Russian email subject/html/text strings live in `app/modules/<domain>/email_templates.py`. Single source of truth per business event (matches D-39-02 lesson). Owner sign-off lives next to the code that triggers it.

### Pattern 2: Pre-rendered envelopes cross the integration boundary

The ARQ `dispatch_email` task receives an already-rendered `EmailEnvelope(to, subject, html, text, audit_correlation_id)` and is forbidden from importing anything in `app.modules.*`. Substitution happens at the calling service. Worker stays generic.

### Pattern 3: Audit-correlation via `audit_correlation_id` foreign key

Every email-send audit row carries an FK to the **business** audit row that triggered it. Mirrors `payment_row_hash` SHA-256 traceability locked in v1.4 Phase 32.

### Pattern 4: SVC001 commit-gate applies to new users.service

The AST commit-gate walker (currently scope=6 services) extends to 7. Add `app/modules/users/service.py` to the tracked-services list.

### Pattern 5: Double-wire Protocol slot registrations

Per v1.3 REG-29-03 lesson: any new resolver/dispatcher slot must be registered in BOTH `app/main.py:create_app()` AND `app/workers/__init__.py:WorkerSettings.on_startup`. ARQ worker is a separate process; it does NOT see registrations from `create_app()`.

### Anti-Pattern to AVOID: a "real" notifications module

D-39-02 (Phase 39) is the canonical rejection. Resurrecting `app/modules/notifications/` as a channel-multiplexer would create cross-module fan-in and tempt ad-hoc magic-string event names, breaking the AST LOCKED-events gate.

---

## Build Order for v1.6 Phases (suggested)

Mirrors v1.3 (Phase 24 INFRA bedrock → 25/26/27 feature phases → 28 OpenAPI drift → 29 verification) and v1.5 (Phase 37 INFRA bedrock → 38/39/40 feature phases).

| Phase | Theme | Why this order |
|---|---|---|
| **Phase 41 — Foundations bedrock** | Extend `LOCKED_AUDIT_EVENTS` 56 → ~67 up-front; hoist `User` ORM (or add `UserLookup` slot); extend `Action`/`Resource`/`OWNER_ONLY` for `Resource.USERS`; declare new Protocol slots; add `app.modules.users` to `.importlinter`; extend SVC001 commit-gate; resolve reset-token-store decision (Path A vs B) | Up-front infrastructure prevents per-phase churn (v1.3 INFRA-15 lesson). |
| **Phase 42 — Email integration layer** | Replace `app/integrations/email/client.py` placeholder with real provider adapter; add `factory.py`; add `app/workers/tasks/dispatch_email.py` ARQ task; wire dispatcher slot double-wired; LOCKED audit pair `email_sent`/`email_send_failed` first callsites; DNS/SPF/DKIM/DMARC owner-runbook | Transport must exist before any module can call it. |
| **Phase 43 — Users module (CRUD + RBAC)** | New `app/modules/users/`; users-table schema additions; `UserSessionInvalidator` slot wired; audit events | Depends on Phase 41. Independent of email. |
| **Phase 44 — Invitation + password-reset flow** | `password_reset_tokens` table (or itsdangerous stateless); `password_reset_service.py`; `invitation_service.py`; endpoints; locked Russian email copy with owner sign-off (D-27 lineage); cron expiry job | Depends on Phase 42 + 43. |
| **Phase 45 — Email fallback for expiring/booking notifications** | Extend `send_expiring_notifications.py` and `send_booking_reminders.py`; extend idempotency tables with `channel` column; locked email copy | Depends on Phases 41 + 42. Mirrors v1.3 Phase 27. |
| **Phase 46 — Payment-receipt email** | `payments/service.py` hook on `record_payment` success; locked email copy; LOCKED `payment_receipt_emailed` event | Standalone — only depends on Phase 42. Can be parallel with Phase 45. |
| **Phase 47 — OpenAPI drift gate refresh** | Atomic byte-stable regen + `AssertNonNever` forward-guards (61 → ~73) | After all feature phases land. Mirrors v1.3 Phase 28 + v1.5 Phase 36. |
| **Phase 48 — Milestone verification** | Operator scenarios via curl + sandbox email; race tests; CI gates | Mirrors v1.3 Phase 29 + v1.4 Phase 36 + v1.5 Phase 40 verification discipline. |

**Critical ordering invariant:** Phase 41 unblocks Phases 42 + 43 in parallel. Phase 44 has hard dependencies on both. Phases 45 + 46 are then parallel. Phase 47 is a serialization point. Phase 48 is the gate.

---

## Open Questions to Resolve in Spec Phase

1. **Email provider selection** — owned by STACK.md (recommendation: Yandex Cloud Postbox primary, Unisender Go fallback).
2. **Email rendering library** — STACK.md recommends Jinja2 SandboxedEnvironment; this researcher leans toward f-string-locked templates per D-39-04 anti-magic. Spec phase decides.
3. **Reset-token store** — Path A (DB table) vs Path B (itsdangerous stateless). Both preserve anti-oracle.
4. **`User` ORM hoist** — Path A (hoist to core) vs Path B (UserLookup Protocol slot).
5. **Email verification flow for owner-added operator accounts** — trust owner-entered addresses, or click-to-verify? Recommendation: trust (single zal, owner knows their staff).
6. **Bounce/complaint webhook handling** — Recommendation: defer to v1.7. v1.6 records send-attempt outcomes only.
7. **`actor_display_name` formatting** in email copy (multi-user audit) — full name vs first-name-last-initial.

---

## Confidence Assessment

| Area | Confidence | Rationale |
|---|---|---|
| Module placement (integrations/email mirror integrations/telegram) | HIGH | Direct precedent — `app/integrations/email/` already exists as placeholder; D-39-02 |
| Per-domain template ownership | HIGH | v1.5 Phase 39 D-39-02 |
| Async-via-ARQ for email send (no 6th docker service) | HIGH | Pattern matches v1.3 Phase 27 expiring-soon DM dispatch and v1.5 Phase 39/40 booking reminder |
| New `users` module vs auth extension | HIGH | Auth module size already at upper bound; separation matches v1.4 splitting payments from memberships |
| `User` model hoist vs `UserLookup` slot | MEDIUM | Both viable. Hoist is cleaner; slot is lower-risk. |
| Reset-token DB table vs itsdangerous stateless | MEDIUM | DB matches `refresh_tokens` discipline; itsdangerous is simpler infra. Spec phase resolves. |
| Idempotency table extension via `channel` column | HIGH | Minimum-invasive; backfill is trivial; matches v1.5 `booking_notifications` shape |
| import-linter contracts preserved | HIGH | No new contract needed; only one mechanical change (add `users` to `modules-independent`); narrative D-41-XX exceptions documented |

---

## Roadmap Implications (Summary for SUMMARY.md)

**Phases:** 8 phases (41–48), suggested order above
**Critical invariants preserved:** anti-oracle (no email leaks user-existence information; `password_reset_requested` emitted in both branches; constant-time response floor), audit-AST-gate (all ~11 new events added to LOCKED_AUDIT_EVENTS in Phase 41 up-front), SVC001 commit-gate (extended to `users/service.py` and `auth/password_reset_service.py`), `modules-independent` contract (one mechanical addition, zero new edges), Protocol-slot double-wiring (REG-29-03)
**Risk flags for deeper research:** Phase 42 (provider selection + DNS/SPF/DKIM/DMARC owner-runbook) and Phase 44 (locked Russian email copy — needs owner sign-off mechanism mirrored from D-27-OWNER-COPY-LOCK)
**Open conflicts surfaced for spec phase:**
- FEATURES.md suggests creating a "real" `app/modules/notifications/`; ARCHITECTURE.md rejects (D-39-02 precedent)
- STACK.md recommends itsdangerous stateless tokens; ARCHITECTURE.md recommends DB table — spec phase chooses

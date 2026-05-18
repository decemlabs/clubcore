# Phase 41: INFRA Bedrock + Anti-Oracle Scaffold — Context

**Gathered:** 2026-05-18
**Status:** Ready for planning

<domain>
## Phase Boundary

Pre-register **every** v1.6 contract surface — 11 new `LOCKED_AUDIT_EVENTS` pairs + matching Pydantic payload schemas, `Resource.USERS` + 4 new `OWNER_ONLY` entries, 4 Alembic migrations (users soft-delete partial-UNIQUE, audit `actor_email_snapshot`, cross-channel notification discriminator, `password_reset_tokens` unified table), 2 Protocol slots (`EmailDispatcher`, `UserSessionInvalidator`), the new `LOCKED_EMAIL_TEMPLATES` AST gate with all 14 v1.6 template identifiers, SVC001 + import-linter scope extensions, and the RED `test_password_reset_no_oracle.py` — BEFORE any feature callsite lands. This phase closes the AST-gate-churn class (v1.3 INFRA-15 lesson) and the Pitfall 1 anti-oracle regression class up-front. Zero user-visible API surface; pure infra commit.

Requirements in scope: **INFRA-34, INFRA-35, INFRA-36, INFRA-37, INFRA-38, INFRA-39, INFRA-40, RESET-06** (8 requirements per `.planning/REQUIREMENTS.md` traceability table).

</domain>

<decisions>
## Implementation Decisions

### User ORM ownership (open conflict #5 — RESOLVED)

- **D-41-01 (Path A with shim):** Hoist `User` ORM model from `apps/backend/app/modules/auth/models.py` to **new file** `apps/backend/app/core/models.py` (User only, one file per cohesive concern; `audit_models.py` stays audit-specific). Both `auth` and `users` modules co-own User reads/writes and may import directly from `core` — no Protocol indirection. `app/modules/auth/models.py` keeps a `from app.core.models import User` re-export shim for one full milestone; **v1.7 removes the shim** (queue as DEFER-41-shim entry in next milestone backlog). Mechanical sed pass updates app code; test imports settle gradually through deprecation aisle instead of one mechanical 729-test commit. Sets precedent for any future cross-module ORM hoist (closest prior: v1.2 Phase 15 `escape_like_pattern` function hoist).
- **D-41-02 (auth import-linter contract update):** `app.modules.auth → app.core.models` is already a permitted edge (core ⊥ modules forbids the reverse, not this direction). No new contract; mechanical addition only.

### Reset-token storage scaffolding (open conflict #2 — RESOLVED at Phase 41)

- **D-41-03 (DB-table, decided NOW):** Phase 41 ships Alembic migration **`0025_password_reset_tokens`** as part of the bedrock bundle. Mirrors v1.1 `refresh_tokens` discipline byte-for-byte; atomic-consume via `UPDATE ... WHERE consumed_at IS NULL RETURNING`; partial-UNIQUE prevents stale active tokens; SVC001 commit-gate works as-is; `audit_correlation_id` natively attaches at INSERT. Phase 44 ships **zero migrations** — only callsite code. itsdangerous-stateless path is explicitly rejected at Phase 41 (couples reset-token revocation to `password_changed_at` globally, would collide with USERS-03 invitation flow).
- **D-41-04 (Unified table shape with `purpose` column):** Single table `password_reset_tokens` (name retained for grep continuity, not renamed to `auth_tokens`) holds BOTH password-reset tokens AND invitation tokens:
  - `id UUID PK` (UUIDPkMixin)
  - `user_id UUID NOT NULL FK users.id ON DELETE CASCADE` (token dies with user; soft-delete leaves token consumed/expired naturally)
  - `purpose TEXT NOT NULL CHECK (purpose IN ('password_reset','invitation'))`
  - `token_hash TEXT NOT NULL` (hash-at-rest — sha256 of the issued opaque token; raw token only ever exists in the URL fragment and bounce-survivable email body)
  - `expires_at TIMESTAMPTZ NOT NULL` (TTL per purpose enforced at SELECT layer: 1h reset, 7d invitation — RESET-03)
  - `consumed_at TIMESTAMPTZ NULL` (atomic-consume marker; revocation also writes here — `revoked_at` is NOT a separate column, semantics carried by audit event payload `reason`)
  - `audit_correlation_id UUID NOT NULL` (links token → original `password_reset_requested` / `user_invited` audit row → eventual consume audit row)
  - `created_at` / TimestampMixin
- **D-41-05 (partial-UNIQUE):** `UNIQUE (user_id, purpose) WHERE consumed_at IS NULL` — one active token per (user, purpose). Reuse pattern of `refresh_tokens` and `membership_freeze_periods`.
- **D-41-06 (cleanup cron):** Light. Daily ARQ job (lands in Phase 44, NOT Phase 41) deletes rows where `expires_at < NOW() - INTERVAL '30 days'` to keep the table bounded. Phase 41 ships the table only.
- **D-41-07 (RESET-04 INSERT-only invariant):** Phase 41 does NOT enforce the "invite-accept INSERTS new users row" rule — that lives in `users.service` at Phase 43/44. Phase 41 only provides the schema enabling it (`users.deleted_at` partial-UNIQUE + `password_reset_tokens.user_id → users.id` FK).

### `actor_email_snapshot` capture mechanism (INFRA-39 — RESOLVED)

- **D-41-08 (Hybrid: ContextVar + explicit override):** Primary mechanism is a request-scoped `ActorContext` ContextVar:
  - New `apps/backend/app/core/actor_context.py` declares `actor_context_var: ContextVar[ActorIdentity | None]` (ActorIdentity = TypedDict `{user_id: UUID, email: str}`).
  - New `ActorContextMiddleware` placed **after** `RequestIdMiddleware` (mirrors Phase 14 / v1.2 RequestIdMiddleware shape) reads the resolved current_user from request state and sets the contextvar; resets on response exit (try/finally with `actor_context_var.reset(token)` per existing structlog `bind_contextvars` pattern).
  - ARQ worker integration: extend `app/workers/__init__.py:WorkerSettings.on_job_start` hook (already binds `job_id`/`job_name` to structlog — Phase 18 D-18) to additionally `set(...)` the actor_context_var from job kwargs when `actor_user_id` and `actor_email_snapshot` are passed at enqueue time. on_job_end resets.
  - `audit.emit()` body reads `actor_context_var.get()` when `actor_email_snapshot` kwarg is None — single source of truth.
  - **Override path:** `audit.emit(..., actor_email_snapshot="explicit@value")` wins over the ContextVar — for batch reconciliation jobs that emit on behalf of someone else, or for retroactively logged events. Documented in `audit.py` docstring with one example.
- **D-41-09 (Pydantic payload schemas don't carry actor_email_snapshot):** `actor_email_snapshot` is a **column on `audit_log`**, not a payload field. It writes via the `audit.emit()` boundary, not via per-event payload Pydantic models (which already use `extra='forbid'`). Keeps the 11 new payload schemas (INFRA-35) free of cross-cutting actor noise.
- **D-41-10 (System emits — actor_user_id=None):** Audit rows from ARQ cron jobs and unauthenticated paths (e.g. `password_reset_requested` for unknown email — both branches per RESET-01 anti-oracle) emit with `actor_user_id=None` and `actor_email_snapshot=NULL`. Population is **conditional on non-NULL `actor_user_id`** — same rule as INFRA-39 spec.

### `LOCKED_EMAIL_TEMPLATES` shape + initial content (INFRA-36 — RESOLVED)

- **D-41-11 (Single template-id, frozenset[str]):** Shape mirrors `LOCKED_AUDIT_EVENTS` exactly — `LOCKED_EMAIL_TEMPLATES: frozenset[str]` holding template identifier strings. Each id resolves to a `(subject, html, text)` record inside the per-domain `email_templates.py` registry (D-39-02 module ownership preserved — templates live next to their owning module, not in `integrations/email/copy.py`). Dispatcher signature: `send_email(template_id: TemplateId, **template_vars) -> None`. AST walker asserts the first positional / `template_id=` keyword argument at every `get_email_dispatcher()(...)` callsite is a literal name resolving to a member of `LOCKED_EMAIL_TEMPLATES`. Rejected: triple-shape `(subject_const, html_const, text_const)` — the cohesion is already structurally enforced by the per-domain registry pattern.
- **D-41-12 (Pre-register all 14 v1.6 templates up-front in Phase 41):** Mirrors INFRA-34 / INFRA-15 discipline (pre-register events 56 → 67 before callsites). Downstream phases 42/44/45 ship template **content** with constant names already locked — zero AST-gate churn. Initial frozenset members:
  1. `EMAIL_OTP_LOGIN` (Phase 42, AUTH-EM-03)
  2. `USER_INVITATION_EMAIL` (Phase 44, RESET-03 / USERS-03)
  3. `PASSWORD_RESET_EMAIL` (Phase 44, RESET-03)
  4. `EMAIL_EXPIRING_7D_VARIANT_A` (Phase 45, NOTIFY-08)
  5. `EMAIL_EXPIRING_7D_VARIANT_B`
  6. `EMAIL_EXPIRING_3D_VARIANT_A`
  7. `EMAIL_EXPIRING_3D_VARIANT_B`
  8. `EMAIL_EXPIRING_1D_VARIANT_A`
  9. `EMAIL_EXPIRING_1D_VARIANT_B`
  10. `EMAIL_BOOKING_CONFIRMED` (Phase 45, NOTIFY-10)
  11. `EMAIL_BOOKING_CANCELLED_BY_CLIENT`
  12. `EMAIL_BOOKING_CANCELLED_BY_OWNER`
  13. `EMAIL_BOOKING_REMINDER_24H`
  14. `EMAIL_PAYMENT_RECEIPT_SALE` (Phase 45, NOTIFY-12)
  15. `EMAIL_PAYMENT_RECEIPT_REFUND`

  (15 entries total — `USER_INVITATION_EMAIL` + `PASSWORD_RESET_EMAIL` count as one template each since the (subject, html, text) triple lives inside a single registry record per D-41-11.)
- **D-41-13 (Synthetic-violation fixture):** Phase 41 commits a synthetic-violation test (`tests/test_locked_email_templates_ast.py`) that asserts a fixture file calling `get_email_dispatcher()(template_id="BOGUS_NOT_LOCKED", ...)` AND a separate fixture calling `get_email_dispatcher()(...)` with a raw subject string literal both fail the AST walker with a clear error message. Mirrors the existing `audit.emit` literal-string gate fixture from Phase 15.
- **D-41-14 (Owner sign-off mechanism unchanged):** Owner sign-off enumerates every locked email template constant name at VER-14 (v1.6 verification phase) — same D-27-OWNER-COPY-LOCK / D-39-02 lineage. Phase 41 does NOT carry copy yet; only identifiers.

### Migration packaging (mechanical — derives from decisions above)

- **D-41-15 (4 sequential migrations, not omnibus):** Phase 41 ships Alembic migrations **0022 → 0025** in dependency order, one logical change per file (mirrors v1.0–v1.5 convention):
  - `0022_users_soft_delete_partial_unique` — INFRA-38: `users.deleted_at TIMESTAMPTZ NULL` + DROP global `UNIQUE (lower(email))` + recreate as partial `UNIQUE (lower(email)) WHERE deleted_at IS NULL`
  - `0023_audit_actor_snapshot` — INFRA-39: `audit_log.actor_email_snapshot TEXT NULL` + explicit `actor_user_id ON DELETE SET NULL` (alter existing FK constraint)
  - `0024_notification_channel_discriminator` — NOTIFY-06: `channel TEXT NOT NULL DEFAULT 'telegram' CHECK channel IN ('telegram','email')` on BOTH `membership_notifications` AND `booking_notifications`; drop existing `UNIQUE (subject_id, kind)` and recreate as `UNIQUE (subject_id, kind, channel)`. Zero-row backfill (production data reproducible by next cron tick — D-41-03 v1.3 NTF-05 precedent)
  - `0025_password_reset_tokens` — D-41-04 unified table shape with `purpose` column + partial-UNIQUE
- **D-41-16 (Migration order matters):** 0022 must precede 0025 because `password_reset_tokens.user_id FK users.id` references `users` post-soft-delete-schema. 0023 is independent of 0022/0024/0025 but ordered second for chronology. 0024 is independent and can run any time but sits before 0025 to keep notifications cluster together.

### RESET-06 anti-oracle test scaffolding

- **D-41-17 (RED-then-keep-RED until Phase 44):** `tests/integration/test_password_reset_no_oracle.py` lands in Phase 41 asserting the 4-case identical-202 + identical-body + bounded-equal-timing-within-100ms contract against `POST /api/v1/auth/password-reset/request`. The endpoint **does not exist yet** in Phase 41 — test is expected to fail with HTTP 404 at the request layer. Test is marked `@pytest.mark.xfail(strict=True, reason="endpoint lands in Phase 44 RESET-01")` so it documents the contract as code BUT does not break CI. When Phase 44 lands RESET-01, the `xfail` marker is removed in the same commit that ships the endpoint — `strict=True` ensures the suite breaks loudly if anyone removes the marker without the endpoint actually passing.
- **D-41-18 (Test uses real Postgres via SAVEPOINT per-test isolation):** Mirrors v1.2 existing integration test discipline. The 4 fixture users (existing-active / existing-deactivated / owner-account / non-existent — last one is a never-existed email) are seeded per test, NOT in module-scope, to keep tests deterministic. Bounded-timing assertion uses `time.perf_counter()` deltas with a 100ms tolerance window (per RESET-06 spec).

### LOCKED_AUDIT_EVENTS + payload schemas (INFRA-34 + INFRA-35 — mechanical)

- **D-41-19 (Pairs locked verbatim from INFRA-34):** All 11 pairs land verbatim per REQUIREMENTS.md:
  - `('email_sent', 'email_send_log')` — resource_type = the new email_send_log table (Phase 42 lands the table itself, but the audit-events-must-precede-callsite discipline means Phase 41 pre-registers the pair using the eventual table name)
  - `('email_send_failed', 'email_send_log')`
  - `('user_invited', 'user')`
  - `('user_invitation_accepted', 'user')`
  - `('user_invitation_revoked', 'user')`
  - `('user_deactivated', 'user')`
  - `('user_reactivated', 'user')`
  - `('user_soft_deleted', 'user')`
  - `('password_reset_requested', 'user')` — actor_user_id=None branch always emits with the resolved-or-NULL target user_id (RESET-01 anti-oracle: emitted in BOTH known and unknown branches; unknown branch uses NULL resource_id)
  - `('password_reset_completed', 'user')`
  - `('payment_receipt_emailed', 'payment')`

  Final frozenset size grows **56 → 67**. Synthetic-violation fixture asserts `audit.emit('bogus_v16_event', resource_type='user', ...)` rejected (mirrors existing Phase 15 fixture).
- **D-41-20 (Pydantic payload schemas in `audit_payloads.py`):** Each of the 11 new events gets a matching `Final` Pydantic model with `extra='forbid'`, UUIDs serialised as `str(uuid)` (REG-36-03 lesson), and an `audit_correlation_id: UUID | None` field for the asynchronous email-event-correlation pattern (links `email_sent` audit row back to the triggering business audit row via shared UUID). The `audit_correlation_id` is NOT auto-generated by `emit()` — callers explicitly pass it when continuing a correlation chain, leave None for chain-starters.

### Resource.USERS + OWNER_ONLY extension (INFRA-37 — mechanical)

- **D-41-21 (4 entries):** `Resource.USERS = "users"` added to `apps/backend/app/core/permissions.py:Resource` StrEnum. `OWNER_ONLY` frozenset grows 26 → 30 with `(CREATE, USERS), (UPDATE, USERS), (DELETE, USERS), (LIST, USERS)`. Reception keeps **zero** USERS permissions in v1.6. Three-way parity test (backend ↔ admin-web `can.ts` ↔ `registry.ts`) extended by adding the matching entries to the two admin-web files in the same commit; `tests/test_rbac_parity.py` already iterates the cartesian and asserts byte-equality — extension is mechanical.
- **D-41-22 (No new Action verbs):** v1.6 reuses existing `Action.{CREATE, UPDATE, DELETE, LIST}` — no new actions needed (deactivate/reactivate use `Action.UPDATE`; soft-delete uses `Action.DELETE`; invitation-revoke uses `Action.UPDATE`).
- **D-41-23 (Admin-web `can.ts` + `registry.ts` change scope):** Pure additive — `users: 'users'` resource key + 4 `(action, resource)` pairs added to `OWNER_ONLY` array. No new routes, no new sidebar entries (those land when v2.0 production admin app integrates). admin-web is frozen-as-of-v1.3 mock-reference; Phase 41 changes are RBAC-contract-only.

### Protocol slots (INFRA-40 — mechanical)

- **D-41-24 (`EmailDispatcher`):** Declared in `apps/backend/app/core/dependencies.py` mirroring existing 6-slot pattern (`UserLoader`, `ActiveMembershipResolver`, `ClientByTelegram`, `TrainerById`, `ActivePtPackage`, `PaymentRecorder`/`PaymentRefunder`). Type: `class EmailDispatcher(Protocol): async def __call__(self, *, template_id: str, to: str, audit_correlation_id: UUID | None, **template_vars: Any) -> None`. Accessors `register_email_dispatcher(impl)` + `get_email_dispatcher() -> EmailDispatcher`. Idempotent registration (re-register raises if already registered — same discipline as existing slots). Phase 42 wires the real implementation (enqueues the `dispatch_email` ARQ task); Phase 41 ships only the slot declaration. No callsites in Phase 41 — gate is exercised first in Phase 42.
- **D-41-25 (`UserSessionInvalidator`):** `class UserSessionInvalidator(Protocol): async def __call__(self, session: AsyncSession, *, user_id: UUID, reason: Literal['deactivated','password_reset','soft_deleted']) -> int` (returns count of refresh-token families revoked, for audit payload). Accessors `register_user_session_invalidator(impl)` + `get_user_session_invalidator()`. Phase 43 wires `auth.service.invalidate_all_families_for_user`; Phase 41 ships only the slot declaration.
- **D-41-26 (Double-wire discipline carried by 42/43):** Phase 41 does NOT yet exercise the REG-29-03 double-wire test (slot has no registration callsite). Phase 42 introduces the first real `register_email_dispatcher(...)` call in BOTH `app/main.py:create_app()` AND `app/workers/__init__.py:WorkerSettings.on_startup` and the parity test asserting both registrations land. Phase 41 just declares the slot types and accessors.

### import-linter + SVC001 scope extension (INFRA-40 — mechanical)

- **D-41-27 (`.importlinter` modules-independent — additive):** Add `app.modules.users` to the `modules-independent` contract list. Mechanical one-line addition. Contract 3 (`integrations ⊥ modules`) and contract 1 (`core ⊥ modules`) unchanged. No new contract — same mechanism as v1.2 Phase 15 added `memberships`, `visits`, `bookings`.
- **D-41-28 (SVC001 AST commit-gate scope):** Existing SVC001 walker (`tests/test_svc001_commit_gate.py` or similar — Phase 15 INFRA-11) currently covers `auth/service.py` (Phase 12.1 lesson: not just `service.py` per module, ALL service files). Phase 41 extends the walker's target file list to additionally check **`app/modules/users/service.py`** AND **`app/modules/auth/password_reset_service.py`**. The targets are referenced by path string; the files don't exist yet at Phase 41 commit time — walker treats "expected target file absent" as a hard fail to prevent silent-drop. Synthetic-violation fixture covers the new files.

### Eager-import discipline (REG-29-04 / NOTIFY-14 — preventative)

- **D-41-29 (Phase 41 does NOT touch `app/workers/__init__.py` eager-imports YET):** New ORM models (`password_reset_tokens` + downstream `email_send_log` from Phase 42 + `payment_receipts` from Phase 45) need eager-import for the cron one-shot scripts to see them at boot time. Phase 41 introduces only `password_reset_tokens`; its eager-import line lands in Phase 41 alongside the migration so the next cron tick post-Phase-41 sees the table. Phases 42/45 add their own eager-imports in their respective commits. `tests/test_workers_eager_import.py` is extended in Phase 41 to assert `password_reset_tokens` appears in `Base.metadata.tables.keys()` from the worker import root (mirrors REG-29-04 existing test for v1.3 expiring notifications).

### Claude's Discretion

- Exact Pydantic field types/names inside each of the 11 new payload schemas (INFRA-35 leaves field shape to implementor as long as `extra='forbid'` + `audit_correlation_id: UUID | None` are present).
- Internal ARQ task signature for the future `dispatch_email` job — Phase 42 owns this; Phase 41 only declares the Protocol slot.
- Migration file docstring wording.
- Exact `xfail` reason string in `test_password_reset_no_oracle.py`.
- Whether `users.deleted_at` has an index (recommend: no — partial-UNIQUE on `(lower(email)) WHERE deleted_at IS NULL` already gives the predicate-relevant index).

</decisions>

<canonical_refs>
## Canonical References

**Downstream agents MUST read these before planning or implementing.**

### Phase 41 source-of-truth specs (locked)
- `.planning/REQUIREMENTS.md` §§ INFRA-34..40 + RESET-06 — locked requirements; non-negotiable acceptance criteria
- `.planning/ROADMAP.md` §§ Phase 41 — goal + 6 success criteria + dependency declaration
- `.planning/PROJECT.md` — current state (v1.5 shipped 2026-05-18, 56 LOCKED_AUDIT_EVENTS, 26-entry OWNER_ONLY, 6 Protocol slots, 6 docker services, 10 + Phase 41 → 11 business tables); Key Decisions table; D-XX-YY decision lineage

### v1.6 research (HIGH confidence — must read for Phase 41 trade-off rationale)
- `.planning/research/SUMMARY.md` — 7 open conflicts (Phase 41 resolves #2 + #5; flags #1/#4 for Phase 42/45), critical-invariant ordering, work items A (INFRA bedrock) ordered list
- `.planning/research/PITFALLS.md` — 16-pitfall taxonomy; Pitfalls 1 (anti-oracle), 2 (cross-channel double-pings), 3 (token replay / account hijack), 4 (actor_user_id historical interpretation), 5 (locked Russian copy), 7 (REG-29-04 mirror) are all Phase 41 surface
- `.planning/research/ARCHITECTURE.md` — modular monolith additions, Protocol slot pattern, per-domain template ownership precedent
- `.planning/research/STACK.md` — provider/SDK/template-engine scorecards (Phase 41 doesn't pick provider, but reads STACK.md to understand what slot signatures must accommodate)
- `.planning/research/FEATURES.md` — 11 anti-features (esp. plaintext password email, dual-email-per-user, multi-channel OTP race) — Phase 41 schema must not enable these

### v1.0–v1.5 codebase landmarks (Phase 41 extends or mirrors)
- `apps/backend/app/core/audit.py` — `LOCKED_AUDIT_EVENTS` frozenset (56 entries today) + `audit.emit` literal-string AST walker; Phase 41 extends to 67
- `apps/backend/app/core/audit_payloads.py` — Pydantic payload registry with `extra='forbid'`; Phase 41 adds 11 new payload models
- `apps/backend/app/core/permissions.py` — `Resource` StrEnum + `OWNER_ONLY` frozenset (26 entries today); Phase 41 extends to 30
- `apps/backend/app/core/dependencies.py` — Protocol slot registry (6 slots today); Phase 41 adds 2 declarations
- `apps/backend/app/core/middleware.py` — Phase 14 RequestIdMiddleware ContextVar pattern; Phase 41 mirrors for ActorContext
- `apps/backend/app/modules/auth/models.py` — current home of `User`; Phase 41 hoists to `app/core/models.py` + leaves shim
- `apps/backend/alembic/versions/0021_bookings_created_by_user_id_nullable.py` — latest migration; Phase 41 lands 0022 → 0025
- `apps/backend/.importlinter` — modules-independent contract; Phase 41 adds `app.modules.users`
- `apps/admin-web/src/shared/session/can.ts` + `registry.ts` — three-way RBAC parity targets; Phase 41 adds `users` resource + 4 OWNER_ONLY entries

### Verification + governance lineage
- `.planning/milestones/v1.5-VERIFICATION-LOG.md` — REG-29-01/03/04 regressions + DEFER-40-01 runbook scaffolding lesson; Phase 41 preventative discipline derives from these
- `.planning/milestones/v1.1-MILESTONE-AUDIT.md` — Phase 12.1 SVC001 scope-extension lesson (must include ALL service files per module)
- `.planning/audits/v1.1-MILESTONE-AUDIT.md` — same content; cross-reference if needed

### Key D-XX-YY decision lineage carried forward
- **D-20-9** (v1.2): `/checkin` anti-oracle — same DM for stranger and expired-membership. Phase 41 RESET-06 test enforces email-channel parallel.
- **D-27-OWNER-COPY-LOCK** (v1.3): per-template owner sign-off enumerated by constant name. Phase 41 LOCKED_EMAIL_TEMPLATES preserves the pattern.
- **D-39-02** (v1.5): per-domain template ownership (booking DMs in `bookings/notifications.py`, NOT in shared `telegram/copy.py`). Phase 41 confirms same for email: per-domain `email_templates.py`.
- **REG-29-03** (v1.3): double-wired Protocol slot registration (composition root + worker on_startup). Phase 41 declares new slots; Phase 42/43 exercise the double-wire.
- **REG-29-04** (v1.3): eager-import discipline for new ORM tables. Phase 41 adds `password_reset_tokens` eager-import to `app/workers/__init__.py`.
- **REG-36-03** (v1.4): UUIDs in audit payloads serialise as `str(uuid)`. Phase 41 INFRA-35 new payloads inherit.
- **DEFER-40-01** (v1.5): budget runbook-scaffolding hardening explicitly. Phase 41 has no runbook surface — this lineage applies to Phase 46.

</canonical_refs>

<code_context>
## Existing Code Insights

### Reusable Assets

- **`apps/backend/app/core/audit.py` LOCKED_AUDIT_EVENTS pattern** — Phase 41 INFRA-36 mirrors this exact shape for `LOCKED_EMAIL_TEMPLATES`. Reuse the AST walker scaffolding (`apps/backend/app/core/audit.py` AST gate) when authoring the new `LOCKED_EMAIL_TEMPLATES` walker — same `ast.walk` + `Call` node inspection logic, different target frozenset and call-target name.
- **`apps/backend/app/core/audit_payloads.py`** — 56 existing Pydantic payload models with `extra='forbid'` and UUID `str(uuid)` serialization. Copy the shape verbatim for the 11 new INFRA-35 payloads.
- **`apps/backend/app/core/dependencies.py`** — 6-slot Protocol pattern (Phase 5 / 17 / 19 / 31 / 32). Phase 41's `EmailDispatcher` + `UserSessionInvalidator` declarations slot in mechanically.
- **`apps/backend/app/core/middleware.py:RequestIdMiddleware`** — ContextVar set-and-reset pattern with structlog `bind_contextvars` integration. Phase 41's `ActorContextMiddleware` mirrors line-for-line; only the contextvar identity changes.
- **`apps/backend/app/workers/__init__.py:WorkerSettings.on_job_start/on_job_end`** — Phase 18 D-18 ContextVar bind/reset for `job_id`/`job_name`. Phase 41 D-41-08 adds parallel `actor_context_var.set()` / `.reset()` for actor identity.
- **`apps/backend/alembic/versions/0008_membership_freeze_periods.py`** — partial-UNIQUE pattern. Phase 41's 0022 (users) + 0025 (password_reset_tokens) mirror exactly.
- **`apps/backend/alembic/versions/0009_membership_notifications.py`** — `membership_notifications` table shape that 0024 ALTERs to add `channel` column. Read this first before authoring 0024 so the existing UNIQUE constraint name is known for the DROP.
- **`apps/backend/alembic/versions/0020_booking_notifications.py`** — `booking_notifications` table shape (same as above, 0024 alters this too).
- **`tests/test_rbac_parity.py`** — three-way RBAC parity test. Phase 41 extension is data-only (add USERS entries to backend `OWNER_ONLY` + admin-web `can.ts`/`registry.ts`); test logic is unchanged.
- **`tests/test_workers_eager_import.py`** — AST introspection that asserts ORM models are eager-imported in workers. Phase 41 extends with one new assertion for `password_reset_tokens`.

### Established Patterns

- **Pre-register before callsite (INFRA-15 / INFRA-24 / INFRA-27 lineage):** Frozen sets (`LOCKED_AUDIT_EVENTS`, now `LOCKED_EMAIL_TEMPLATES`) and OWNER_ONLY entries are extended in a single bedrock commit at the milestone's first phase, NOT incrementally across feature phases. Phase 41 carries the full v1.6 expansion.
- **Migration order = dependency order:** Within Phase 41, 0022 (users.deleted_at) precedes 0025 (password_reset_tokens.user_id FK). Cross-phase, all v1.6 schema changes live in Phase 41 so Phases 42–46 ship zero migrations.
- **Protocol slot double-wire (REG-29-03):** Compose-root + worker-startup both register the implementation; parity test asserts byte-equality. Phase 41 declares slots only; first double-wire arrives in Phase 42.
- **Per-domain template ownership (D-39-02):** Templates live next to their owning module (`auth/email_templates.py`, `users/email_templates.py`, `memberships/email_templates.py`, `bookings/email_templates.py` → `notifications.py`, `payments/email_templates.py`). NOT in `integrations/email/copy.py`. Phase 41 LOCKED_EMAIL_TEMPLATES references identifiers; templates physically land in their modules at Phases 42/44/45.
- **Module structure boilerplate (Phase 8 / 16 / 31 / 38):** `app/modules/<x>/{router,service,repository,schemas,permissions,constants}.py` + per-module `email_templates.py` for v1.6. Phase 41 does NOT create the `app/modules/users/` tree (that's Phase 43); it only adds `app.modules.users` to the import-linter contract list.
- **xfail-strict for forward-declared tests:** `pytest.mark.xfail(strict=True, reason=...)` documents intended contract as code without breaking CI when implementation is in a later phase. Phase 41 uses this for `test_password_reset_no_oracle.py`.

### Integration Points

- **Phase 42 entry seam:** Will `register_email_dispatcher(enqueue_email_dispatch_via_arq)` in `app/main.py:create_app()` + `app/workers/__init__.py:WorkerSettings.on_startup`. Phase 41's Protocol slot type signature must accommodate Phase 42's eventual ARQ-task-enqueueing implementation (keyword args: `template_id`, `to`, `audit_correlation_id`, `**template_vars`).
- **Phase 43 entry seam:** Will create `app/modules/users/` package and `register_user_session_invalidator(auth.service.invalidate_all_families_for_user)`. Phase 41's slot type must accommodate the eventual signature (`session: AsyncSession`, `user_id: UUID`, `reason: Literal[...]` → `int` count).
- **Phase 44 entry seam:** Will ship `POST /api/v1/auth/password-reset/request|confirm` which queries `password_reset_tokens` directly (no Protocol slot — it's a within-auth concern). Phase 41's 0025 schema + the `password_reset_tokens` ORM model must be in place at Phase 44 commit time.
- **Phase 45 entry seam:** Will read `channel` column on `membership_notifications` + `booking_notifications` for idempotency-per-channel. Phase 41's 0024 migration provides the schema.
- **Phase 46 entry seam:** OpenAPI drift gate. Phase 41 adds NO new API paths (pure infra); the openapi.json byte-diff should be empty after Phase 41 lands. CI gate `export_openapi.py && git diff --exit-code` must stay green.

</code_context>

<specifics>
## Specific Ideas

- **Hybrid actor-snapshot capture (D-41-08) explicitly motivated by ContextVar precedent** — user prefers reusing the existing RequestIdMiddleware / structlog `bind_contextvars` pattern over either a 70-callsite mechanical edit or an extra DB roundtrip per audit row. The override path matters for batch jobs.
- **DB-table tokens, not itsdangerous (D-41-03)** — user explicitly aligns with SVC001 + atomic-consume `RETURNING` SQL invariant. Stateless tokens rejected because of the password_changed_at coupling collision with invitation flow.
- **Shim deprecation aisle for User hoist (D-41-01)** — user explicitly chose the staged migration over the one-commit mechanical sed pass. Indicates appetite for low-blast-radius refactors on shared foundations.
- **Single template-id, not triple (D-41-11)** — user explicitly prefers symmetry with `LOCKED_AUDIT_EVENTS` over the marginally-stronger triple-cohesion guarantee. Registry per-domain pattern already gives the cohesion structurally.
- **Pre-register everything up-front (D-41-12)** — user explicitly chose the v1.3 INFRA-15 discipline over the per-phase extension. Confirms the bedrock-first project philosophy is load-bearing.

</specifics>

<deferred>
## Deferred Ideas

- **`email_send_log` table schema** — Phase 41 pre-registers the `(email_sent, email_send_log)` audit pair, but the actual table creation lives in Phase 42 (EMAIL-07 bounce webhook). Migration number reserved is 0026 (Phase 42).
- **`payment_receipts` idempotency table** — Phase 45 (NOTIFY-11). Migration number tentatively 0027.
- **`shim removal for User import path** — Queue as DEFER-41-shim for v1.7 milestone backlog. Single mechanical sed pass removing `from app.modules.auth.models import User` re-exports + updating callers to `from app.core.models import User`.
- **Cleanup cron for `password_reset_tokens`** — Phase 44 (D-41-06). Daily ARQ job deletes rows where `expires_at < NOW() - INTERVAL '30 days'`.
- **`actor_display_name` formatting** (first-name + last-initial vs full name) — USERS-07, deferred to Phase 43 discuss-phase. Phase 41 only commits the `actor_email_snapshot` column; display-name formatting is a Phase 43 concern.
- **Owner sign-off rows for email templates** — Phase 41 enumerates the 15 identifiers; actual owner sign-off rows recorded at VER-14 (Phase 46). The constant names are locked here so VER-14 has stable targets.
- **DMARC subdomain layout** (`mail.sportzal.ru` vs alternate) — Phase 42 EMAIL-05 discuss-phase concern.
- **Email-verify flow policy** (trust-owner-entered vs click-to-verify) — Open conflict #7, resolved at Phase 43 discuss-phase. Phase 41 schema is policy-agnostic.
- **`notifications` module placeholder vs resurrect** — Open conflict #3, resolved at Phase 45 discuss-phase. Phase 41 imposes no constraint either way.
- **Template engine** (Jinja2 SandboxedEnvironment vs `Final[str]` f-strings) — Open conflict #4, resolved at Phase 42 discuss-phase. Phase 41 LOCKED_EMAIL_TEMPLATES is shape-agnostic (just identifier strings).

</deferred>

---

*Phase: 41-infra-bedrock-anti-oracle-scaffold*
*Context gathered: 2026-05-18*

"""FastAPI dependencies: CurrentUser Protocol, loader registration, RBAC gate (D-24).

Architectural responsibility (PROJECT.md + .importlinter):
  `app.core` MUST NOT import from `app.modules.*` — but `get_current_user` lives in core
  and must load a User from `app.modules.auth`. The fix: a Protocol slot in core that the
  composition root (`app.main.create_app`) fills at startup with a concrete loader.

Phase 4 ships the slot + dependency factories. Phase 5 `create_app()` will call
`register_user_loader(app.modules.auth.service.load_user_by_id)` inside the factory
body (`app.main` is exempt from `core-not-depend-on-modules` because that contract has
`source_modules = app.core`, not `app`).

`Depends(require_permission(...))` lands on actual routes in Phase 6 (RBAC-02..05);
Phase 4 ships only the factory.
"""

import secrets
from collections.abc import Awaitable, Callable
from datetime import date, datetime
from typing import Annotated, Any, Literal, Protocol
from uuid import UUID

from fastapi import Depends, Request
from sqlalchemy.ext.asyncio import AsyncSession

from app.core import audit
from app.core.database import get_db
from app.core.exceptions import CsrfMismatch, ForbiddenError, InvalidAccessToken, InvalidSession
from app.core.permissions import Action, Resource, Role, can
from app.core.security import decode_access_token


class CurrentUser(Protocol):
    """Structural type for the authenticated user (D-24).

    Phase 5's `app.core.models.User` satisfies this protocol because it
    declares `id: Mapped[UUID]`, `role: Mapped[Role]`, and `email: Mapped[str]`.
    Nothing in `app.core` imports the SA model — the Protocol is the boundary.

    Phase 41 INFRA-39 / D-41-08 added ``email`` so ``get_current_user`` can
    populate ``actor_context_var`` with the resolved actor's email; the
    audit_log INSERT path reads it via ``get_current_actor()`` when the
    explicit ``actor_email_snapshot`` kwarg is omitted.
    """

    id: UUID
    role: Role
    email: str


UserLoader = Callable[[AsyncSession, UUID], Awaitable[CurrentUser | None]]
"""Async callable: (session, user_id) -> CurrentUser | None.

Returns None if no user with that id exists (or is soft-deleted) so the dependency can
surface `InvalidAccessToken('user_not_found')`.
"""

_user_loader: UserLoader | None = None


def register_user_loader(loader: UserLoader) -> None:
    """Composition-root setter — called once by `app.main.create_app` in Phase 5.

    Idempotent: re-registering replaces the slot (useful in tests that want to inject a
    stub loader). Phase 4 has no caller; Phase 5 wires `load_user_by_id`.
    """
    global _user_loader
    _user_loader = loader


class ActiveMembership(Protocol):
    """Structural type for the active-membership row (MEM-05).

    Per D-18: only the 4 attributes consumed by Phase 19 visits service.
    Snapshot fields, plan_id, dates other than end_date, audit timestamps are
    NOT in the Protocol (visits doesn't need them). The SA `Membership` ORM
    structurally satisfies this Protocol because all 4 attributes are mapped
    — no DTO conversion at the resolver boundary.
    """

    id: UUID
    client_id: UUID
    end_date: date
    status: str


ActiveMembershipResolver = Callable[[AsyncSession, UUID], Awaitable[ActiveMembership | None]]
"""Async callable: (session, client_id) -> ActiveMembership | None.

Returns None when the client has no active membership (the canonical case the
visits service treats as 'no membership'). Tiebreak when multiple active rows
exist is the implementation's responsibility (MEM-04 locks: latest end_date,
then created_at DESC).
"""

_active_membership_resolver: ActiveMembershipResolver | None = None


def register_active_membership_resolver(resolver: ActiveMembershipResolver) -> None:
    """Composition-root setter — called once by `app.main.create_app` in Phase 17.

    Second loader slot after `register_user_loader` (Phase 5 D-15). Idempotent:
    re-registering replaces the slot, useful for tests that inject a stub
    resolver via `create_app()`. Phase 17 wires
    `app.modules.memberships.service.resolve_active_membership_by_client`.
    """
    global _active_membership_resolver
    _active_membership_resolver = resolver


async def resolve_active_membership(
    session: AsyncSession, client_id: UUID
) -> ActiveMembership | None:
    """Consumer entry point — used by `app.modules.visits.service` in Phase 19.

    Per CONTEXT.md `<code_context>` line 224: returns None when the slot is
    unset (production code always registers in `create_app()`; tests can
    register a stub or rely on the default-None behaviour). Differs from
    `_user_loader` defensive raise because the visits service cannot
    distinguish 'no resolver registered' from 'no active membership' — and
    that's the correct semantic for the consumer.
    """
    if _active_membership_resolver is None:
        return None
    return await _active_membership_resolver(session, client_id)


# ─────────────────────────────────────────────────────────────────────────────
# Phase 33 D-33-12 — ActivePtPackage resolver slot.
#
# Second active-subject slot pair (after Phase 17 ActiveMembership). Phase 34
# pt_sessions service will call ``get_active_pt_package`` through this slot
# to validate that the client owns a live PT-package before recording a
# session. Like ActiveMembership, the consumer's failure mode for
# "no resolver registered" cannot be distinguished from "no active package"
# at the call site — silent-None semantics are the documented contract
# (D-33-12; mirrors line 117). The defensive-raise pattern is reserved for
# payment recorder/refunder (D-32-14) where a missing slot is hard
# misconfiguration.
#
# Wired EXCLUSIVELY from ``app.main.create_app`` (NOT from
# ``app.workers.telegram_bot.main`` — bot is not a PT-session participant
# in v1.4; mirrors D-32-14 discipline).
# ─────────────────────────────────────────────────────────────────────────────


class ActivePtPackage(Protocol):
    """Structural type for the active-PT-package row (Phase 33 D-33-12).

    Per D-33-12: only the attributes Phase 34 pt_sessions service consumes
    are declared (id, client_id, status, sessions_remaining, end_date).
    The SA ``PtPackage`` ORM structurally satisfies this Protocol — no DTO
    conversion at the resolver boundary (mirrors ``ActiveMembership``).
    """

    id: UUID
    client_id: UUID
    status: str
    sessions_remaining: int
    end_date: date | None


ActivePtPackageResolver = Callable[[AsyncSession, UUID], Awaitable[ActivePtPackage | None]]
"""Async callable: (session, client_id) -> ActivePtPackage | None.

Returns None when the client has no active PT-package (the canonical case
Phase 34 pt_sessions service treats as 'no package').
"""

_active_pt_package_resolver: ActivePtPackageResolver | None = None


def register_active_pt_package_resolver(resolver: ActivePtPackageResolver) -> None:
    """Composition-root setter — called once by ``app.main.create_app`` in Phase 33.

    Sixth+ loader slot after register_user_loader (Phase 5),
    register_active_membership_resolver (Phase 17),
    register_client_by_telegram_resolver (Phase 19),
    register_trainer_by_id_resolver (Phase 31),
    register_payment_recorder + register_payment_refunder (Phase 32).
    Idempotent: re-registering replaces the slot (mirrors WR-05 reasoning).
    """
    global _active_pt_package_resolver
    _active_pt_package_resolver = resolver


async def get_active_pt_package(session: AsyncSession, client_id: UUID) -> ActivePtPackage | None:
    """Consumer entry point — used by ``app.modules.pt_sessions.service`` in Phase 34.

    Silent-None when the slot is unset (production code always registers in
    ``create_app()``; tests can register a stub or rely on the default-None
    behaviour). Mirrors ``resolve_active_membership`` (line 117) — D-33-12
    explicit choice: "no active package" is an expected state, not a
    misconfiguration.
    """
    if _active_pt_package_resolver is None:
        return None
    return await _active_pt_package_resolver(session, client_id)


# ─────────────────────────────────────────────────────────────────────────────
# Phase 19 D-02 — ClientByTelegram resolver slot.
#
# Third composition-root carve-out after `register_user_loader` (Phase 5 D-15)
# and `register_active_membership_resolver` (Phase 17 D-18). Phase 19's visits
# service self-checkin path needs to look up Client by `telegram_user_id`, but
# the importlinter `modules-independent` contract forbids
# `app.modules.visits → app.modules.clients`. The Protocol-callback pattern is
# the validated escape: visits.service depends only on `core.dependencies`,
# which is allowed.
#
# Production wiring lives in `app.main.create_app()` —
# `register_client_by_telegram_resolver(clients.service.resolve_client_by_telegram_user_id)`.
# Tests can override the slot via `create_app(...)` to inject a stub resolver
# (idempotent: re-registering replaces the slot).
# ─────────────────────────────────────────────────────────────────────────────


class ClientByTelegram(Protocol):
    """Structural type for the alive-Client lookup result (Phase 19 D-02).

    Phase 19 visits service consumes ONLY `id` (passes `client.id` to the
    private anti-fraud chain). Adding more attributes here is a deliberate
    expansion of the cross-module surface — keep this Protocol narrow.
    """

    id: UUID


ClientByTelegramResolver = Callable[[AsyncSession, int], Awaitable[ClientByTelegram | None]]
"""Async callable: (session, telegram_user_id) -> ClientByTelegram | None.

Returns None when no alive Client matches the given Telegram user id (the
canonical case Phase 19 visits service treats as 'unknown caller', raising
`ClientNotLinkedError`). Phase 20's bot handler will catch the typed
exception and reply with a generic Russian DM (no oracle leak — Pitfall 8).
"""

_client_by_telegram_resolver: ClientByTelegramResolver | None = None


def register_client_by_telegram_resolver(
    resolver: ClientByTelegramResolver,
) -> None:
    """Composition-root setter — called once by `app.main.create_app` in Phase 19.

    Third loader slot after `register_user_loader` (Phase 5 D-15) and
    `register_active_membership_resolver` (Phase 17 D-18). Idempotent:
    re-registering replaces the slot, useful for tests injecting a stub
    resolver via `create_app()`. Phase 19 wires
    `app.modules.clients.service.resolve_client_by_telegram_user_id`.
    """
    global _client_by_telegram_resolver
    _client_by_telegram_resolver = resolver


async def resolve_client_by_telegram_user_id(
    session: AsyncSession, telegram_user_id: int
) -> ClientByTelegram | None:
    """Consumer entry point — used by `app.modules.visits.service` in Phase 19.

    Returns None when the slot is unset (production code always registers in
    `create_app()`; tests can register a stub or rely on the default-None
    behaviour, e.g. unit tests that don't go through the bot path at all).
    """
    if _client_by_telegram_resolver is None:
        return None
    return await _client_by_telegram_resolver(session, telegram_user_id)


# ─────────────────────────────────────────────────────────────────────────────
# Phase 31 D-31-13/D-31-14 — TrainerById resolver slot.
#
# Fourth composition-root carve-out after register_user_loader (Phase 5),
# register_active_membership_resolver (Phase 17), and
# register_client_by_telegram_resolver (Phase 19). Phase 34's pt_sessions
# service needs to validate trainer existence + is_active status without
# crossing the modules-independent importlinter contract.
# ─────────────────────────────────────────────────────────────────────────────


class TrainerById(Protocol):
    """Structural type for alive Trainer lookup result (Phase 31 D-31-13).

    Phase 34 D-34-12a adds `full_name: str` for B-05 `trainer_name_snapshot`
    capture. Trainer ORM satisfies structurally — zero resolver-wiring change
    (the existing `register_trainer_by_id_resolver` returns the SA Trainer row
    which already exposes `full_name: Mapped[str]` per Phase 31 model line 28).
    """

    id: UUID
    is_active: bool
    full_name: str  # Phase 34 D-34-12a — B-05 trainer_name_snapshot capture


TrainerByIdResolver = Callable[[AsyncSession, UUID], Awaitable[TrainerById | None]]

_trainer_by_id_resolver: TrainerByIdResolver | None = None


def register_trainer_by_id_resolver(resolver: TrainerByIdResolver) -> None:
    """Composition-root setter — called by app.main.create_app() AND
    app.workers.telegram_bot.main() (defensive double-wiring per REG-29-03)."""
    global _trainer_by_id_resolver
    _trainer_by_id_resolver = resolver


async def resolve_trainer_by_id(session: AsyncSession, trainer_id: UUID) -> TrainerById | None:
    """Consumer entry point — Phase 34 pt_sessions service will call this."""
    if _trainer_by_id_resolver is None:
        return None
    return await _trainer_by_id_resolver(session, trainer_id)


# ─────────────────────────────────────────────────────────────────────────────
# Phase 32 D-32-14 — PaymentRecorder + PaymentRefunder Protocol slots.
#
# Fifth + sixth composition-root carve-outs. The sale orchestrator
# (memberships.service.create_membership, Plan 32-02) consumes
# PaymentRecorder; the refund orchestrator (memberships.service.refund_membership,
# Plan 32-03) consumes PaymentRefunder. Both are wired EXCLUSIVELY from
# app.main.create_app() — NOT from app.workers.telegram_bot.main(), because
# the bot is not a sale/refund participant in v1.4.
#
# Defensive-raise accessors (mirrors _user_loader defensive raise at line ~253;
# NOT the silent-None pattern of _active_membership_resolver). A missing
# registration is a misconfiguration, not a recoverable state — surfacing it
# as RuntimeError at the consumer site fails the call instead of silently
# proceeding without recording the payment.
#
# PaymentRefunder signature accepts (subject_kind, subject_id) NOT
# original_payment_id (D-32-14 amended per PATTERNS.md §14). This keeps the
# memberships orchestrator from importing payments.repository — the refunder
# internally loads the original sale row via subject_kind/subject_id with
# amount > 0 filter.
# ─────────────────────────────────────────────────────────────────────────────


class PaymentRecorder(Protocol):
    """Structural type for the sale-side payment recorder (Phase 32 D-32-14).

    Return type ``Any`` is intentional: the concrete return is
    ``app.modules.payments.models.Payment``, but this Protocol lives in
    ``app.core`` which is forbidden from importing ``app.modules.*``
    (importlinter `core-not-depend-on-modules` contract). Callers in the
    modules layer that need typed access cast the result locally.
    """

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
    ) -> Any: ...


class PaymentRefunder(Protocol):
    """Structural type for the refund-side payment issuer (Phase 32 D-32-14).

    Takes ``(subject_kind, subject_id)`` so cross-module callers
    (memberships.service.refund_membership) never need to import
    ``app.modules.payments.repository`` — preserves the
    modules-independent importlinter contract. The refunder internally
    loads the original sale-side row via subject_kind/subject_id with
    amount > 0 filter.

    Return type rationale matches :class:`PaymentRecorder` — ``Any``
    because app.core may not name ``app.modules.payments.models.Payment``.
    """

    async def __call__(
        self,
        session: AsyncSession,
        *,
        subject_kind: str,
        subject_id: UUID,
        refund_user_id: UUID,
        reason: str,
        audit_actor: CurrentUser,
    ) -> Any: ...


_payment_recorder: PaymentRecorder | None = None
_payment_refunder: PaymentRefunder | None = None


def register_payment_recorder(recorder: PaymentRecorder) -> None:
    """Composition-root setter — called by app.main.create_app() (NOT bot)."""
    global _payment_recorder
    _payment_recorder = recorder


def register_payment_refunder(refunder: PaymentRefunder) -> None:
    """Composition-root setter — called by app.main.create_app() (NOT bot)."""
    global _payment_refunder
    _payment_refunder = refunder


def get_payment_recorder() -> PaymentRecorder:
    """Defensive accessor (D-32-14) — raises if slot not registered.

    Mirrors ``_user_loader`` defensive raise (line ~253), NOT
    ``_active_membership_resolver`` silent-None (line ~117). The sale flow
    cannot proceed without a recorder, so this branch is a hard failure.
    """
    if _payment_recorder is None:
        raise RuntimeError("payment_recorder not registered")
    return _payment_recorder


def get_payment_refunder() -> PaymentRefunder:
    """Defensive accessor (D-32-14) — raises if slot not registered.

    Mirrors ``_user_loader`` defensive raise (line ~253), NOT
    ``_active_membership_resolver`` silent-None (line ~117). The refund flow
    cannot proceed without a refunder, so this branch is a hard failure.
    """
    if _payment_refunder is None:
        raise RuntimeError("payment_refunder not registered")
    return _payment_refunder


# ─────────────────────────────────────────────────────────────────────────────
# Phase 37 INFRA-32 / D-37-06 — SlotById resolver slot (v1.5 schedule).
#
# Eighth composition-root carve-out (after register_user_loader Phase 5,
# register_active_membership_resolver Phase 17, register_client_by_telegram_resolver
# Phase 19, register_trainer_by_id_resolver Phase 31, register_payment_recorder +
# register_payment_refunder Phase 32, register_active_pt_package_resolver
# Phase 33). Phase 38 bookings.service.create_booking will call
# ``resolve_slot_by_id`` through this slot to validate that the requested
# schedule slot exists and is in the expected status before transitioning
# it (Booking FSM dependency). The consumer's failure mode for
# "no resolver registered" cannot be distinguished from "no such slot"
# at the call site — silent-None semantics are the documented contract
# (D-37-06; mirrors ActivePtPackageResolver at line 117).
#
# Wired from ``app.main.create_app`` AND from
# ``app.workers.telegram_bot.main`` (defensive double-wiring per REG-29-03 —
# the bot's Phase 40 /book handler consumes the resolver via
# bookings.service).
# ─────────────────────────────────────────────────────────────────────────────


class SlotById(Protocol):
    """Structural type for the schedule-slot lookup result (Phase 37 D-37-06).

    Per D-37-06: only the attributes Phase 38 bookings.service.create_booking
    consumes are declared (id, status, trainer_id, start_time, end_time).
    The SA ``ScheduleSlot`` ORM (Phase 38 deliverable) will structurally
    satisfy this Protocol — no DTO conversion at the resolver boundary
    (mirrors ``ActivePtPackage`` / ``ActiveMembership``).
    """

    id: UUID
    status: str
    trainer_id: UUID
    start_time: datetime
    end_time: datetime


SlotByIdResolver = Callable[[AsyncSession, UUID], Awaitable[SlotById | None]]
"""Async callable: (session, slot_id) -> SlotById | None.

Returns None when the slot does not exist (the canonical case Phase 38
bookings.service treats as 'unknown slot' — surfaces as a domain error
to the /book handler).
"""

_slot_by_id_resolver: SlotByIdResolver | None = None


def register_slot_by_id_resolver(resolver: SlotByIdResolver) -> None:
    """Composition-root setter — called by app.main.create_app() AND
    app.workers.telegram_bot.main() (defensive double-wiring per REG-29-03).

    Eighth loader slot. Idempotent: re-registering replaces the slot
    (mirrors WR-05 reasoning).
    """
    global _slot_by_id_resolver
    _slot_by_id_resolver = resolver


async def resolve_slot_by_id(session: AsyncSession, slot_id: UUID) -> SlotById | None:
    """Consumer entry point — used by ``app.modules.bookings.service`` in Phase 38.

    Silent-None when the slot is unset (D-37-06; mirrors
    ``resolve_active_membership`` at line 117). Production wiring lives in
    ``app.main.create_app()`` AND ``app.workers.telegram_bot.main()`` —
    tests can register a stub or rely on the default-None behaviour.
    """
    if _slot_by_id_resolver is None:
        return None
    return await _slot_by_id_resolver(session, slot_id)


# ─────────────────────────────────────────────────────────────────────────────
# Phase 37 INFRA-32 / D-37-06 — BookingSlotRestorer slot (v1.5 bookings).
#
# Ninth composition-root carve-out. Phase 38
# bookings.service.cancel_booking will call ``restore_booking_slot``
# through this slot to flip ``slot.status`` from "booked" back to "active"
# inside the caller's UoW (no separate transaction). Side-effect-only
# (Awaitable[None]) — no Protocol class needed.
#
# Silent-None per D-37-06 (CONTEXT.md `<code_context>` explicit choice;
# deviates from ARCHITECTURE.md restore_slot_on_cancel defensive-raise —
# CONTEXT.md is authoritative).
#
# Wired EXCLUSIVELY from ``app.main.create_app`` (NOT from
# ``app.workers.telegram_bot.main`` — bot does not cancel bookings;
# mirrors D-32-14 / D-33-12 discipline for API-only slots).
# ─────────────────────────────────────────────────────────────────────────────


BookingSlotRestorerCallable = Callable[[AsyncSession, UUID], Awaitable[None]]
"""Async callable: (session, slot_id) -> None.

Side-effect: flips the schedule slot's status from "booked" back to "active"
inside the caller's UoW. No return value — the caller commits the outer
transaction.
"""

_booking_slot_restorer: BookingSlotRestorerCallable | None = None


def register_booking_slot_restorer(restorer: BookingSlotRestorerCallable) -> None:
    """Composition-root setter — called once by ``app.main.create_app`` in Phase 37.

    Ninth loader slot. Idempotent: re-registering replaces the slot
    (mirrors WR-05 reasoning).
    """
    global _booking_slot_restorer
    _booking_slot_restorer = restorer


async def restore_booking_slot(session: AsyncSession, slot_id: UUID) -> None:
    """Consumer entry point — used by ``app.modules.bookings.service`` in Phase 38.

    Silent-None when the slot is unset (D-37-06; mirrors
    ``resolve_active_membership`` at line 117). Returns None either way —
    callers don't branch on the return value, the side-effect either
    happened (registered + applied) or it didn't (unregistered) and the
    test surface owns that contract.
    """
    if _booking_slot_restorer is None:
        return None
    return await _booking_slot_restorer(session, slot_id)


# ─────────────────────────────────────────────────────────────────────────────
# Phase 37 INFRA-32 / D-37-06 / C-03 — BookingCompleter slot (v1.5 bookings).
#
# Tenth composition-root carve-out. Phase 38
# pt_sessions.service.record_pt_session will call
# ``complete_booking_by_pt_session`` through this slot when a recorded
# PT-session carries a non-None ``booking_id`` — transitioning the linked
# booking from "confirmed" to "completed" inside the caller's UoW
# (C-03 / D-37-05 link between PT-session record and booking FSM).
# Side-effect-only (Awaitable[None]) — no Protocol class needed.
#
# Silent-None per D-37-06 (CONTEXT.md `<code_context>` explicit choice).
#
# Wired EXCLUSIVELY from ``app.main.create_app`` (NOT from
# ``app.workers.telegram_bot.main`` — bot does not record PT-sessions;
# mirrors D-32-14 / D-33-12 discipline for API-only slots).
# ─────────────────────────────────────────────────────────────────────────────


BookingCompleterCallable = Callable[[AsyncSession, UUID], Awaitable[None]]
"""Async callable: (session, booking_id) -> None.

Side-effect: transitions the booking row from "confirmed" to "completed"
inside the caller's UoW. No return value — the pt_sessions orchestrator
commits the outer transaction.
"""

_booking_completer: BookingCompleterCallable | None = None


def register_booking_completer(completer: BookingCompleterCallable) -> None:
    """Composition-root setter — called once by ``app.main.create_app`` in Phase 37.

    Tenth loader slot. Idempotent: re-registering replaces the slot
    (mirrors WR-05 reasoning).
    """
    global _booking_completer
    _booking_completer = completer


async def complete_booking_by_pt_session(session: AsyncSession, booking_id: UUID) -> None:
    """Consumer entry point — used by ``app.modules.pt_sessions.service`` in Phase 38.

    Silent-None when the slot is unset (D-37-06; mirrors
    ``resolve_active_membership`` at line 117). Returns None either way —
    callers don't branch on the return value.
    """
    if _booking_completer is None:
        return None
    return await _booking_completer(session, booking_id)


# ─────────────────────────────────────────────────────────────────────────────
# Phase 41 INFRA-40 / D-41-24 — EmailDispatcher Protocol slot (v1.6 email).
#
# Eleventh composition-root carve-out. Phase 42 wires the real implementation
# (enqueues ``dispatch_email`` ARQ task) in BOTH ``app.main.create_app()`` AND
# ``app.workers.__init__.WorkerSettings.on_startup`` (REG-29-03 double-wire
# parity — mirrors register_trainer_by_id_resolver / register_slot_by_id_resolver).
# Phase 41 ships only the slot declaration; no callsite yet.
#
# Defensive-raise accessor (mirrors get_payment_recorder at line ~398;
# NOT the silent-None pattern of resolve_active_membership at line 117) —
# a missing email dispatcher in the email-issuing flow is a hard
# misconfiguration, not an expected state.
# ─────────────────────────────────────────────────────────────────────────────


class EmailDispatcher(Protocol):
    """Structural type for the email-dispatch callable (Phase 41 D-41-24).

    Signature locked at Phase 41 to accommodate Phase 42's eventual
    ARQ-enqueueing implementation. ``template_id`` is a literal string
    member of ``LOCKED_EMAIL_TEMPLATES`` (Phase 41 INFRA-36 / D-41-11) —
    enforced statically at every callsite by the AST gate at
    ``tests/unit/test_locked_email_templates_ast.py``.

    ``audit_correlation_id`` carries the link to the triggering audit row
    for asynchronous email-event correlation (D-41-20). It is nullable so
    bootstrap / system-emitted email flows (no actor audit row) can pass
    ``None`` without fabricating a synthetic audit id.
    """

    async def __call__(
        self,
        *,
        template_id: str,
        to: str,
        audit_correlation_id: UUID | None,
        **template_vars: Any,
    ) -> None: ...


_email_dispatcher: EmailDispatcher | None = None


def register_email_dispatcher(impl: EmailDispatcher) -> None:
    """Composition-root setter (Phase 41 D-41-24).

    Phase 42 calls this from BOTH the FastAPI composition root
    (``app.main.create_app``) AND ARQ ``WorkerSettings.on_startup``
    (REG-29-03 double-wire parity). Idempotent: re-registering replaces
    the slot (mirrors WR-05 reasoning; useful for tests that inject a
    stub dispatcher via ``create_app(...)``).
    """
    global _email_dispatcher
    _email_dispatcher = impl


def get_email_dispatcher() -> EmailDispatcher:
    """Defensive accessor (Phase 41 D-41-24) — raises if slot not registered.

    Mirrors ``get_payment_recorder`` defensive-raise pattern (line ~398);
    a missing email dispatcher in an email-issuing flow is a hard
    misconfiguration, not a recoverable state.
    """
    if _email_dispatcher is None:
        raise RuntimeError(
            "EmailDispatcher slot not registered — register via "
            "app.core.dependencies.register_email_dispatcher() in "
            "app/main.py:create_app() AND app/workers/__init__.py "
            "WorkerSettings.on_startup (REG-29-03 double-wire)."
        )
    return _email_dispatcher


# ─────────────────────────────────────────────────────────────────────────────
# Phase 41 INFRA-40 / D-41-25 — UserSessionInvalidator Protocol slot.
#
# Twelfth composition-root carve-out. Phase 43 wires
# ``app.modules.auth.service.invalidate_all_families_for_user``. Returns
# count of refresh-token families revoked, surfaced in the audit payload
# ``sessions_revoked_count`` (Plan 02 UserDeactivatedPayload /
# PasswordResetCompletedPayload). Phase 44 reuses the same slot from
# password-reset/confirm.
#
# Defensive-raise accessor (mirrors get_payment_recorder at line ~398) —
# a missing invalidator at the deactivation / password-reset call site is
# a hard misconfiguration, not an expected state.
# ─────────────────────────────────────────────────────────────────────────────


class UserSessionInvalidator(Protocol):
    """Revoke every active refresh-token family for a user (Phase 41 D-41-25).

    Phase 43 wires the real implementation (multi-user admin deactivate).
    Phase 44 reuses the same slot from password-reset/confirm. Returns
    the count of refresh-token families revoked so the calling
    orchestrator can include ``sessions_revoked_count`` in its audit
    payload (UserDeactivatedPayload / PasswordResetCompletedPayload).

    Phase 43 WR-01 (review) — ``actor_user_id`` is the user who initiated
    the action (the owner deactivating a reception operator), used as the
    ``actor_user_id`` field on the ``session_revoked_all`` audit row.
    ``user_id`` is the TARGET being revoked (stays as ``resource_id``).
    ``None`` is acceptable when the invalidator is invoked from a context
    with no human actor (e.g. Phase 44 self-initiated password reset where
    actor == target — that flow passes actor_user_id=user_id explicitly).
    """

    async def __call__(
        self,
        session: AsyncSession,
        *,
        user_id: UUID,
        actor_user_id: UUID | None,
        reason: Literal["deactivated", "password_reset", "soft_deleted"],
    ) -> int: ...


_user_session_invalidator: UserSessionInvalidator | None = None


def register_user_session_invalidator(impl: UserSessionInvalidator) -> None:
    """Composition-root setter (Phase 41 D-41-25).

    Phase 43 calls this from ``app.main.create_app``. Idempotent:
    re-registering replaces the slot (mirrors WR-05 reasoning; useful for
    tests that inject a stub invalidator via ``create_app(...)``).
    """
    global _user_session_invalidator
    _user_session_invalidator = impl


def get_user_session_invalidator() -> UserSessionInvalidator:
    """Defensive accessor (Phase 41 D-41-25) — raises if slot not registered.

    Mirrors ``get_payment_recorder`` defensive-raise pattern (line ~398);
    a missing invalidator in the deactivation / password-reset call site
    is a hard misconfiguration, not a recoverable state.
    """
    if _user_session_invalidator is None:
        raise RuntimeError(
            "UserSessionInvalidator slot not registered — Phase 43 wires "
            "auth.service.invalidate_all_families_for_user from "
            "app/main.py:create_app()."
        )
    return _user_session_invalidator


async def get_current_user(
    request: Request,
    session: Annotated[AsyncSession, Depends(get_db)],
) -> CurrentUser:
    """Resolve the authenticated user from the `sz_access` cookie.

    Failure modes (all → 401 InvalidAccessToken with a specific message):
      - missing cookie → 'missing_access_cookie'
      - decode failure (delegated to decode_access_token) → 'token_expired' or 'invalid_token'
      - composition root forgot to register a loader → 'user_loader_not_registered'
      - loader returned None (user deleted / unknown id) → 'user_not_found'
    """
    token = request.cookies.get("sz_access")
    if token is None:
        raise InvalidAccessToken("missing_access_cookie")

    # decode_access_token raises InvalidAccessToken on its own failure paths
    # (token_expired / invalid_token / wrong_token_type / unknown_role) — we don't
    # need to wrap here.
    claims = decode_access_token(token)

    if _user_loader is None:
        # Defensive: composition root MUST register before the request flow starts.
        # This branch surfaces a misconfiguration (Phase 5 forgot to call register_user_loader)
        # as a 401 instead of a 500 — same shape the client already handles.
        raise InvalidAccessToken("user_loader_not_registered")

    try:
        uid = UUID(claims.sub)
    except ValueError as e:
        raise InvalidSession("invalid_session") from e
    user = await _user_loader(session, uid)
    if user is None:
        raise InvalidAccessToken("user_not_found")
    # Phase 41 INFRA-39 / D-41-08 — populate the request-scoped actor
    # ContextVar so audit.emit() can pick up the email snapshot without
    # every callsite threading it explicitly. ActorContextMiddleware sets
    # the baseline None and owns the try/finally reset envelope; this is
    # the canonical write site for the authenticated identity.
    from app.core.actor_context import set_actor

    set_actor({"user_id": user.id, "email": user.email})
    return user


def require_permission(
    action: Action,
    resource: Resource,
) -> Callable[..., Awaitable[CurrentUser]]:
    """Return a FastAPI dependency that resolves CurrentUser AND enforces RBAC.

    Phase 6 wires this onto every business route signature (RBAC-03):

        @router.delete("/clients/{id}", response_model=ResponseEnvelope[None])
        async def delete_client(
            user: Annotated[
                CurrentUser, Depends(require_permission(Action.DELETE, Resource.CLIENTS))
            ],
            ...
        ): ...

    Emits structlog `event=rbac_forbidden` with the locked key set
    (`user_id, role, action, resource, path, ip`) BEFORE raising `ForbiddenError`,
    so the Phase 8 audit_log DB writer (INFRA-04) latches on without renaming (D-23).

    The `request: Request` parameter is auto-injected by FastAPI; route-level callers
    declare only `Depends(require_permission(Action.X, Resource.Y))` — the dependency
    graph fills `request` and `user` automatically.

    Raises:
      ForbiddenError (403, code='forbidden') if `can(user.role, action, resource)` is False.
      (Whatever get_current_user raises — 401 paths — propagates upward unchanged.)
    """

    async def _checker(
        request: Request,
        user: Annotated[CurrentUser, Depends(get_current_user)],
        session: Annotated[AsyncSession, Depends(get_db)],
    ) -> CurrentUser:
        if not can(user.role, action, resource):
            # Phase 15 INFRA-11 / D-11: `resource_type` MUST be a literal at every
            # callsite (the AST literal-only gate in tests/unit/test_audit_taxonomy.py
            # cannot prove staticness if it is `resource.value`). The target
            # resource moves into the structlog/payload as `target_resource`.
            await audit.emit(
                session,
                "rbac_forbidden",
                actor_user_id=user.id,
                resource_type="rbac",
                target_resource=resource.value,
                role=user.role.value,
                action=action.value,
                path=request.url.path,
                ip=request.client.host if request.client is not None else None,
            )
            raise ForbiddenError(f"forbidden:{action.value}:{resource.value}")
        return user

    return _checker


def require_authenticated() -> Callable[..., Awaitable[CurrentUser]]:
    """Return a FastAPI dependency that resolves CurrentUser without a role gate.

    Sibling of `require_permission(...)` (D-01). Used by routes that need an
    authenticated caller but no RBAC check (`/auth/me`, `/auth/logout`,
    `/auth/logout-all`). The introspection test (TEST-07, Plan 06-05)
    identifies this factory via `__qualname__.startswith('require_authenticated.')`,
    so the closure name MUST be `_checker` and the function MUST be a single
    wrapping layer over `get_current_user` (do NOT nest inside another factory).
    """

    async def _checker(
        user: Annotated[CurrentUser, Depends(get_current_user)],
    ) -> CurrentUser:
        return user

    return _checker


_SAFE_METHODS: frozenset[str] = frozenset({"GET", "HEAD", "OPTIONS", "TRACE"})


async def verify_csrf(
    request: Request,
    session: Annotated[AsyncSession, Depends(get_db)],
) -> None:
    """Double-submit CSRF check (D-07). Short-circuits on safe methods (D-06).

    Validation:
      1. If method is in {GET, HEAD, OPTIONS, TRACE}, return None (read-only —
         no CSRF check; T-06-07 accept).
      2. Otherwise, read `sportzal_csrf` cookie + `X-CSRF-Token` header.
      3. If either is missing OR they don't match (`secrets.compare_digest`,
         constant-time per T-06-05 mitigation), emit `event=csrf_mismatch` and
         raise `CsrfMismatch`.

    `verify_csrf` runs BEFORE `get_current_user` per FastAPI's `dependencies=[...]`
    execution order, so `user_id` is best-effort `None` (D-23). Emit kwargs include
    only `has_cookie` / `has_header` booleans — never the raw token strings
    (T-06-09 mitigation).

    Raises:
      CsrfMismatch (403, code='csrf_mismatch') with locked envelope per D-21.
    """
    if request.method in _SAFE_METHODS:
        return
    cookie_val = request.cookies.get("sportzal_csrf")
    header_val = request.headers.get("x-csrf-token")
    if (
        cookie_val is None
        or header_val is None
        or not secrets.compare_digest(cookie_val, header_val)
    ):
        await audit.emit(
            session,
            "csrf_mismatch",
            actor_user_id=None,
            resource_type="csrf",
            path=request.url.path,
            method=request.method,
            ip=request.client.host if request.client is not None else None,
            has_cookie=cookie_val is not None,
            has_header=header_val is not None,
        )
        raise CsrfMismatch("csrf_mismatch")


# ─────────────────────────────────────────────────────────────────────────────
# Phase 47 INFRA-38 / D-47-01 — YooKassaClientProvider Protocol slot (v1.7 online payments).
#
# Thirteenth composition-root carve-out. Phase 48 ADAPTER-02 wires the real
# implementation (returns the configured ``YooKassaClient`` instance) in BOTH
# ``app.main.create_app()`` AND
# ``app.workers.__init__.WorkerSettings.on_startup`` (REG-29-03 double-wire
# parity — mirrors the v1.6 ``register_email_dispatcher`` precedent).
# Phase 47 ships the slot declaration + a no-op stub wiring; no callsite yet.
#
# Defensive-raise accessor (mirrors get_email_dispatcher at line ~665) — a
# missing YooKassa client provider in the online-payment-create flow is a hard
# misconfiguration, not an expected state.
# ─────────────────────────────────────────────────────────────────────────────


class YooKassaClientProvider(Protocol):
    """Structural type for the ЮKassa client accessor (Phase 47 D-47-01).

    Return type ``Any`` is intentional: the concrete return is
    ``app.integrations.yookassa.client.YooKassaClient``, but pinning the
    concrete type here would force an ``app.integrations.*`` import inside
    ``app.core`` which is forbidden by the
    ``core-not-depend-on-integrations`` importlinter contract (mirrors
    ``PaymentRecorder``'s Any-return reasoning at line ~339).

    Phase 48 ADAPTER-02 wires the real implementation; Phase 47 wires only a
    no-op stub that raises ``NotImplementedError`` at call time so the
    defensive accessor returns non-None during request handling.
    """

    async def __call__(self) -> Any: ...


_yookassa_client_provider: YooKassaClientProvider | None = None


def register_yookassa_client_provider(impl: YooKassaClientProvider) -> None:
    """Composition-root setter (Phase 47 D-47-01).

    Phase 47 wires a no-op stub from BOTH the FastAPI composition root
    (``app.main.create_app``) AND ARQ ``WorkerSettings.on_startup``
    (REG-29-03 double-wire parity). Idempotent: re-registering replaces
    the slot (mirrors WR-05 reasoning; useful for tests that inject a
    stub provider via ``create_app(...)``).
    """
    global _yookassa_client_provider
    _yookassa_client_provider = impl


def get_yookassa_client_provider() -> YooKassaClientProvider:
    """Defensive accessor (Phase 47 D-47-01) — raises if slot not registered.

    Mirrors ``get_email_dispatcher`` defensive-raise pattern (line ~665);
    a missing YooKassa client provider in an online-payment flow is a hard
    misconfiguration, not a recoverable state.
    """
    if _yookassa_client_provider is None:
        raise RuntimeError(
            "YooKassaClientProvider slot not registered — register via "
            "app.core.dependencies.register_yookassa_client_provider() in "
            "app/main.py:create_app() AND app/workers/__init__.py "
            "WorkerSettings.on_startup (REG-29-03 double-wire)."
        )
    return _yookassa_client_provider


# ─────────────────────────────────────────────────────────────────────────────
# Phase 47 INFRA-38 / D-47-01 — FiscalReceiptDispatcher Protocol slot (v1.7 54-ФЗ).
#
# Fourteenth composition-root carve-out. Phase 50 FISCAL-01 / Phase 51 FISCAL-05
# wire the real implementation (enqueues ``dispatch_fiscal_receipt`` ARQ task
# post-commit) in BOTH ``app.main.create_app()`` AND
# ``app.workers.__init__.WorkerSettings.on_startup`` (REG-29-03 double-wire
# parity — the enqueue happens FastAPI-side via ArqRedis but the worker also
# needs the slot for the consumer-side guard).
# Phase 47 ships the slot declaration + a no-op stub wiring; no callsite yet.
#
# Defensive-raise accessor — a missing fiscal-receipt dispatcher in the
# fiscal-receipt-enqueue flow is a hard misconfiguration, not an expected
# state.
# ─────────────────────────────────────────────────────────────────────────────


class FiscalReceiptDispatcher(Protocol):
    """Structural type for the fiscal-receipt dispatch callable (Phase 47 D-47-01).

    Phase 50 FISCAL-01 / Phase 51 FISCAL-05 wire the real implementation
    (enqueues ``dispatch_fiscal_receipt`` ARQ task post-commit). The
    callsite passes ``fiscal_receipt_id`` (DB row PK) and an optional
    ``audit_correlation_id`` for cross-event correlation in the audit_log
    table — same pattern as ``EmailDispatcher.audit_correlation_id``.
    """

    async def __call__(
        self,
        *,
        fiscal_receipt_id: UUID,
        audit_correlation_id: UUID | None,
    ) -> None: ...


_fiscal_receipt_dispatcher: FiscalReceiptDispatcher | None = None


def register_fiscal_receipt_dispatcher(impl: FiscalReceiptDispatcher) -> None:
    """Composition-root setter (Phase 47 D-47-01).

    Phase 50/51 wires the real implementation from BOTH the FastAPI
    composition root (``app.main.create_app``) AND ARQ
    ``WorkerSettings.on_startup`` (REG-29-03 double-wire parity).
    Idempotent: re-registering replaces the slot.
    """
    global _fiscal_receipt_dispatcher
    _fiscal_receipt_dispatcher = impl


def get_fiscal_receipt_dispatcher() -> FiscalReceiptDispatcher:
    """Defensive accessor (Phase 47 D-47-01) — raises if slot not registered.

    Mirrors ``get_email_dispatcher`` defensive-raise pattern (line ~665);
    a missing fiscal-receipt dispatcher in a 54-ФЗ-enqueue flow is a hard
    misconfiguration, not a recoverable state.
    """
    if _fiscal_receipt_dispatcher is None:
        raise RuntimeError(
            "FiscalReceiptDispatcher slot not registered — register via "
            "app.core.dependencies.register_fiscal_receipt_dispatcher() in "
            "app/main.py:create_app() AND app/workers/__init__.py "
            "WorkerSettings.on_startup (REG-29-03 double-wire)."
        )
    return _fiscal_receipt_dispatcher


# ─────────────────────────────────────────────────────────────────────────────
# Phase 47 INFRA-38 / D-47-01 — MembershipActivator Protocol slot (v1.7 online payments).
#
# Fifteenth composition-root carve-out. Phase 50 WH-05 wires the real
# implementation (activates a membership atomically inside the YooKassa
# webhook unit-of-work) in ``app.main.create_app()`` ONLY — HTTP-only
# single-wire, no ARQ entry path (the webhook handler is HTTP and the
# activation must run inside the request session's transaction).
# Phase 47 ships the slot declaration + a no-op stub wiring; no callsite yet.
#
# Defensive-raise accessor — a missing membership activator in the
# webhook-handling flow is a hard misconfiguration, not an expected state.
# ─────────────────────────────────────────────────────────────────────────────


class MembershipActivator(Protocol):
    """Structural type for the membership-activation callable (Phase 47 D-47-01).

    Return type ``Any`` is intentional: the concrete return is
    ``app.modules.memberships.models.Membership``, but pinning the
    concrete type here would force an ``app.modules.*`` import inside
    ``app.core`` which is forbidden by the
    ``core-not-depend-on-modules`` importlinter contract (mirrors
    ``PaymentRecorder``'s Any-return reasoning at line ~339).

    Phase 50 WH-05 wires the real implementation; the call site is the
    YooKassa webhook handler running inside an HTTP request session — the
    activator MUST run inside the SAME ``AsyncSession`` so the activation
    + audit row commit atomically.
    """

    async def __call__(
        self,
        session: AsyncSession,
        *,
        membership_id: UUID,
        audit_correlation_id: UUID | None,
    ) -> Any: ...


_membership_activator: MembershipActivator | None = None


def register_membership_activator(impl: MembershipActivator) -> None:
    """Composition-root setter (Phase 47 D-47-01).

    Phase 50 calls this from ``app.main.create_app`` ONLY (HTTP-only
    single-wire — no ARQ entry path). Idempotent: re-registering replaces
    the slot.
    """
    global _membership_activator
    _membership_activator = impl


def get_membership_activator() -> MembershipActivator:
    """Defensive accessor (Phase 47 D-47-01) — raises if slot not registered.

    Mirrors ``get_email_dispatcher`` defensive-raise pattern (line ~665);
    a missing membership activator in the webhook-activation flow is a
    hard misconfiguration, not a recoverable state.
    """
    if _membership_activator is None:
        raise RuntimeError(
            "MembershipActivator slot not registered — register via "
            "app.core.dependencies.register_membership_activator() in "
            "app/main.py:create_app() (HTTP-only single-wire — no ARQ entry path)."
        )
    return _membership_activator


# ─────────────────────────────────────────────────────────────────────────────
# Phase 47 INFRA-38 / D-47-01 — PtPackageActivator Protocol slot (v1.7 online payments).
#
# Sixteenth composition-root carve-out. Phase 50 WH-05 wires the real
# implementation (activates a PT-package atomically inside the YooKassa
# webhook unit-of-work) in ``app.main.create_app()`` ONLY — HTTP-only
# single-wire, no ARQ entry path (same reasoning as MembershipActivator).
# Phase 47 ships the slot declaration + a no-op stub wiring; no callsite yet.
#
# Defensive-raise accessor — a missing PT-package activator in the
# webhook-handling flow is a hard misconfiguration, not an expected state.
# ─────────────────────────────────────────────────────────────────────────────


class PtPackageActivator(Protocol):
    """Structural type for the PT-package-activation callable (Phase 47 D-47-01).

    Return type ``Any`` is intentional: the concrete return is
    ``app.modules.pt_packages.models.PtPackage``, but pinning the concrete
    type here would force an ``app.modules.*`` import inside ``app.core``
    which is forbidden by the ``core-not-depend-on-modules`` importlinter
    contract (mirrors ``PaymentRecorder``'s Any-return reasoning at line
    ~339).

    Phase 50 WH-05 wires the real implementation; the call site is the
    YooKassa webhook handler running inside an HTTP request session — the
    activator MUST run inside the SAME ``AsyncSession`` so the activation
    + audit row commit atomically.
    """

    async def __call__(
        self,
        session: AsyncSession,
        *,
        pt_package_id: UUID,
        audit_correlation_id: UUID | None,
    ) -> Any: ...


_pt_package_activator: PtPackageActivator | None = None


def register_pt_package_activator(impl: PtPackageActivator) -> None:
    """Composition-root setter (Phase 47 D-47-01).

    Phase 50 calls this from ``app.main.create_app`` ONLY (HTTP-only
    single-wire — no ARQ entry path). Idempotent: re-registering replaces
    the slot.
    """
    global _pt_package_activator
    _pt_package_activator = impl


def get_pt_package_activator() -> PtPackageActivator:
    """Defensive accessor (Phase 47 D-47-01) — raises if slot not registered.

    Mirrors ``get_email_dispatcher`` defensive-raise pattern (line ~665);
    a missing PT-package activator in the webhook-activation flow is a
    hard misconfiguration, not a recoverable state.
    """
    if _pt_package_activator is None:
        raise RuntimeError(
            "PtPackageActivator slot not registered — register via "
            "app.core.dependencies.register_pt_package_activator() in "
            "app/main.py:create_app() (HTTP-only single-wire — no ARQ entry path)."
        )
    return _pt_package_activator

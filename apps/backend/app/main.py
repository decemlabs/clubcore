"""Application factory (Phase 5 — composition root for auth wiring).

Run with `uvicorn app.main:create_app --factory`. Each call creates a fresh
FastAPI instance.

DO NOT add a module-level `app = create_app()` here. That breaks the factory
contract.

Phase 5 additions:
- combined_lifespan chains db_lifespan + redis_lifespan (D-08).
- register_user_loader(load_user_by_id) fills the Phase 4 D-24 slot (D-15).
   app.main is exempt from core-not-depend-on-modules because that contract
   scopes source_modules = app.core, not app.
- Prod startup assertion: cookie_secure MUST be True when environment=='prod'
   (Phase 4 D-25 — fail-fast at startup, not at first login).

Phase 17 additions:
- register_active_membership_resolver(resolve_active_membership_by_client) fills
   the second loader slot (MEM-05). Same composition-root carve-out as the Phase 5
   user-loader: app.main is intentionally outside the core-not-depend-on-modules
   importlinter scope, so reaching into `app.modules.memberships.service` is allowed
   here and ONLY here. Idempotent re-registration mirrors WR-05 reasoning — tests
   inject stub resolvers via `create_app()`.

Phase 19 additions:
- register_client_by_telegram_resolver(clients_service.resolve_client_by_telegram_user_id)
   fills the third loader slot (D-02). Visits self-checkin path looks up Client by
   telegram_user_id without crossing the modules-independent importlinter contract.
   Local import of `app.modules.clients.service` is used to keep the import
   inside `create_app()` body (composition root carve-out, same pattern as Phase 17).

Phase 38 additions:
- The schedule + bookings module routers (`app.modules.schedule.router.schedule_router`
   and `app.modules.bookings.router.bookings_router`) are mounted inside the v1
   aggregator at `app/api/v1/router.py` alongside every other v1 business router.
   The Phase 38 wiring intentionally does NOT add separate `app.include_router(...)`
   calls in this file — the existing `app.include_router(api)` call at the end of
   `create_app()` already brings in the v1 aggregator (and therefore /api/v1/trainer-slots
   + /api/v1/bookings). See `apps/backend/app/api/v1/router.py:54-55` for the literal
   `v1.include_router(schedule_router, prefix="/trainer-slots", ...)` and
   `v1.include_router(bookings_router, prefix="/bookings", ...)` mounts. This file
   still imports `bookings_service` and `schedule_service` (below) for the Phase 37
   composition-root register_* calls that wire the cross-module Protocol slots.
"""

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from arq.connections import RedisSettings, create_pool
from fastapi import FastAPI

from app.api.router import api
from app.core.config import get_settings
from app.core.database import db_lifespan
from app.core.dependencies import (
    register_active_membership_resolver,
    register_active_pt_package_resolver,
    register_booking_completer,
    register_booking_slot_restorer,
    register_client_by_telegram_resolver,
    register_email_dispatcher,
    register_fiscal_receipt_dispatcher,  # Phase 47 D-47-01 — double-wire.
    register_membership_activator,  # Phase 47 D-47-01 — HTTP-only single-wire.
    register_payment_recorder,
    register_payment_refunder,
    register_pt_package_activator,  # Phase 47 D-47-01 — HTTP-only single-wire.
    register_slot_by_id_resolver,
    register_trainer_by_id_resolver,
    register_user_loader,
    register_user_session_invalidator,  # Phase 43 D-43-26/27 — single-wire.
    register_yookassa_client_provider,  # Phase 47 D-47-01 — double-wire.
)
from app.core.exceptions import register_exception_handlers
from app.core.logging import configure_logging
from app.core.middleware import register_middleware
from app.core.redis import redis_lifespan
from app.integrations.email.dispatcher import (
    enqueue_email_dispatch,
    register_arq_pool,
)
from app.integrations.yookassa._stubs import (
    fiscal_receipt_dispatcher_noop_stub,
    membership_activator_noop_stub,
    pt_package_activator_noop_stub,
)
from app.integrations.yookassa.client import YooKassaClient
from app.integrations.yookassa.factory import build_yookassa_client
from app.integrations.yookassa.settings import YooKassaSettings
from app.modules.auth.service import (
    invalidate_all_families_for_user,
    load_user_by_id,
)
from app.modules.auth.service import (
    set_redis_factory as set_auth_redis_factory,
)
from app.modules.memberships.service import resolve_active_membership_by_client


@asynccontextmanager
async def combined_lifespan(app: FastAPI) -> AsyncIterator[None]:
    """Chain db_lifespan + redis_lifespan adapters (Phase 5 D-08, refactored Phase 7 D-08).

    The adapters internally open db_lifespan_manager() / redis_lifespan_manager()
    so the bot worker (app/workers/telegram_bot.py) can reuse the managers
    without FastAPI app.state coupling.

    Phase 42 D-42-26 / EMAIL-04 — REG-29-03 ArqRedis pool slot:
    Create the ArqRedis pool used by ``enqueue_email_dispatch`` to hand
    email-send jobs to the worker process. Lives in the lifespan (not in
    ``create_app``) because ``arq.create_pool`` is an async coroutine and
    each FastAPI process owns exactly one pool reference. The dispatcher
    slot itself (the function reference) is registered synchronously in
    ``create_app`` so the REG-29-03 parity test sees a literal identical
    symbol reference in both processes — the per-process pool is a
    separate concern.

    Phase 48 D-48-25 — YooKassaClient slot:
        The long-lived httpx.AsyncClient inside YooKassaClient (D-48-06)
        is created HERE so the FastAPI lifespan teardown can close it via
        ``client.aclose()``. The provider closure registered in create_app()
        reads ``app.state.yookassa_client`` lazily, mirroring the
        ``set_auth_redis_factory(lambda: app.state.redis)`` pattern
        established at Phase 43 D-43-26. The worker process owns its own
        client instance (REG-29-03 mirror in app/workers/__init__.py); the
        parity test (Plan 48-07 Task 3) now asserts STRUCTURAL parity
        between the two composition roots rather than byte-equal object
        identity (each process owns its own httpx pool).
    """
    async with db_lifespan(app), redis_lifespan(app):
        settings = get_settings()
        arq_pool = await create_pool(RedisSettings.from_dsn(str(settings.redis_url)))
        register_arq_pool(arq_pool)
        # Phase 48 D-48-25 — construct the long-lived YooKassaClient.
        yookassa_settings = YooKassaSettings()
        app.state.yookassa_client = await build_yookassa_client(settings=yookassa_settings)
        try:
            yield
        finally:
            # Reverse-order teardown — yookassa client first, then arq pool.
            await app.state.yookassa_client.aclose()
            await arq_pool.aclose()


def create_app() -> FastAPI:
    """Compose and return a FastAPI application instance.

    Composition order matters:
      1. configure_logging (must precede any structlog calls).
      2. Prod-mode assertion: cookie_secure must be True (Phase 4 D-25).
      3. FastAPI(lifespan=combined_lifespan) registers DB + Redis lifecycles.
      4. register_middleware adds Timing, ActorContext, then RequestId
         (REVERSED add order — RequestId outermost, ActorContext middle,
         Timing innermost). Phase 41 INFRA-39 / D-41-08 inserted
         ActorContextMiddleware so audit.emit() reads actor_context_var
         within the request lifetime envelope.
      5. register_exception_handlers attaches AppError → JSONResponse handler.
      6. register_user_loader(load_user_by_id) fills the Phase 4 D-24 slot.
      7. register_active_membership_resolver(resolve_active_membership_by_client)
         fills the Phase 17 MEM-05 slot — second composition-root carve-out
         (after register_user_loader, Phase 5 D-15).
      8. register_client_by_telegram_resolver(clients_service.resolve_client_by_telegram_user_id)
         fills the Phase 19 D-02 slot — third composition-root carve-out.
      9. Phase 38 INFRA-32 / D-37-06: register_slot_by_id_resolver,
         register_booking_slot_restorer, and register_booking_completer fill the
         three v1.5 schedule + bookings cross-module Protocol slots. The schedule
         and bookings module routers themselves (`schedule_router`,
         `bookings_router`) are mounted in the v1 aggregator at
         `app/api/v1/router.py` (Phase 38 module-router convention; see this
         module's top-doc for the rationale).
     10. include_router(api) mounts /healthz at root + /api/v1/* (including the
         schedule + bookings routers via the v1 aggregator).
    """
    settings = get_settings()
    configure_logging(settings)

    if settings.environment == "prod" and not settings.cookie_secure:
        raise RuntimeError(
            "COOKIE_SECURE must be true in prod (Phase 4 D-25). "
            "Set COOKIE_SECURE=true in the environment."
        )

    app = FastAPI(
        title="Sportzal API",
        version="1.1.0",
        lifespan=combined_lifespan,
        docs_url="/docs" if settings.environment == "dev" else None,
        redoc_url=None,
    )
    register_middleware(app)
    register_exception_handlers(app)

    # D-15: composition root fills the Phase 4 loader slot. This is the ONLY
    # place where app.main reaches into app.modules.*. The importlinter
    # contract scopes source_modules=app.core, so app.main is intentionally
    # outside the scope.
    #
    # WR-05 (Phase 9 review): register_user_loader is idempotent by design —
    # see app/core/dependencies.py:54-61. Re-registering replaces the slot,
    # which is intentional so tests can inject a stub loader through
    # create_app(). Calling it on every create_app() (per-test, per-export)
    # is therefore safe; the export script never enters lifespan and tests
    # use the slot to swap in fakes deterministically.
    register_user_loader(load_user_by_id)

    # Phase 17 MEM-05: second composition-root carve-out (after register_user_loader,
    # Phase 5 D-15). Same architectural exception — app.main is NOT in the
    # core-not-depend-on-modules importlinter scope. The visits service (Phase 19)
    # will call resolve_active_membership() through the slot; production wires the
    # real resolver here, tests can override via create_app() because the slot is
    # idempotent (mirrors WR-05 reasoning for register_user_loader).
    register_active_membership_resolver(resolve_active_membership_by_client)

    # Phase 19 D-02: third composition-root carve-out — visits self-checkin
    # path needs to look up Client by telegram_user_id without crossing the
    # modules-independent contract. Same idempotent slot pattern; tests can
    # override via create_app().
    from app.modules.clients import (
        service as clients_service,
    )

    register_client_by_telegram_resolver(
        clients_service.resolve_client_by_telegram_user_id,
    )

    # Phase 31 D-31-14: fourth composition-root carve-out — pt_sessions service
    # (Phase 34) will validate trainer existence via this Protocol slot.
    # Defensive: bot worker also registers (see telegram_bot.py). Idempotent.
    from app.modules.trainers import (
        service as trainers_service,
    )

    register_trainer_by_id_resolver(trainers_service.resolve_trainer_by_id)

    # Phase 32 D-32-15: fifth + sixth composition-root carve-outs — sale flow
    # (memberships.service.create_membership, Plan 32-02) consumes
    # payment_recorder; refund flow (memberships.service.refund_membership,
    # Plan 32-03) consumes payment_refunder. Exclusively wired here (NOT in
    # telegram_bot.py — the bot is not a sale/refund participant in v1.4).
    # Defensive raise on missing slot (D-32-14) surfaces misconfiguration as
    # RuntimeError, not silent no-op.
    from app.modules.payments import (
        service as payments_service,
    )

    register_payment_recorder(payments_service.record_payment)
    register_payment_refunder(payments_service.issue_refund)

    # Phase 33 D-33-12: seventh composition-root carve-out — pt_sessions
    # service (Phase 34) will validate active-PT-package existence via this
    # Protocol slot. Wired EXCLUSIVELY here (NOT in telegram_bot.py — the
    # bot is not a PT-session participant in v1.4; mirrors D-32-14
    # payment-recorder discipline). Silent-None accessor (D-33-12) — a
    # missing slot is NOT a hard error like payment_recorder; absence is
    # indistinguishable from "no active package" at the consumer site.
    from app.modules.pt_packages import (
        service as pt_packages_service,
    )

    register_active_pt_package_resolver(pt_packages_service.resolve_active_pt_package)

    # Phase 37 INFRA-33 / D-37-06: eighth-tenth composition-root carve-outs —
    # v1.5 schedule + bookings cross-module Protocol slots. Schedule slot
    # resolver wired BOTH here AND in app/workers/telegram_bot.py (defensive
    # double-wiring per REG-29-03 — the bot's Phase 40 /book handler consumes
    # the resolver via bookings.service). BookingSlotRestorer and
    # BookingCompleter wired EXCLUSIVELY here (bot is not a participant —
    # mirrors D-32-14 / D-33-12 discipline). All three are silent-None
    # accessors (D-37-06).
    from app.modules.bookings import (
        service as bookings_service,
    )
    from app.modules.schedule import (
        service as schedule_service,
    )

    register_slot_by_id_resolver(schedule_service.resolve_slot_by_id)
    register_booking_slot_restorer(schedule_service.restore_slot_to_active)
    register_booking_completer(bookings_service.complete_booking)

    # Phase 42 D-42-26 / EMAIL-04 — REG-29-03 double-wire of the EmailDispatcher
    # slot. The IDENTICAL symbol reference ``enqueue_email_dispatch`` is also
    # passed at ``app/workers/__init__.py:WorkerSettings.on_startup`` so the
    # Phase 42 parity test (plan 42-11) sees a byte-equal callable in both
    # processes. The ArqRedis pool itself is registered in the lifespan above
    # because it requires an awaitable factory (``arq.create_pool``).
    register_email_dispatcher(enqueue_email_dispatch)

    # Phase 43 D-43-26/27 — UserSessionInvalidator SINGLE-wire (no ARQ consumer).
    # ``set_auth_redis_factory`` lambda closes over ``app`` and reads
    # ``app.state.redis`` lazily, so the factory resolves the Redis client
    # AFTER the lifespan has populated it (the lifespan sets app.state.redis
    # AFTER create_app() returns). ``invalidate_all_families_for_user`` wraps
    # ``revoke_all_sessions`` to match the Phase 41 UserSessionInvalidator
    # Protocol signature exactly. NOT wired in app/workers/__init__.py —
    # the worker has zero ``get_user_session_invalidator()`` callsites in
    # Phase 43 scope (D-43-27 single-wire asymmetric vs the EmailDispatcher
    # double-wire above).
    set_auth_redis_factory(lambda: app.state.redis)
    register_user_session_invalidator(invalidate_all_families_for_user)

    # Phase 47 INFRA-38 / D-47-01 — v1.7 ЮKassa + fiscal + activator slots.
    # YooKassaClientProvider + FiscalReceiptDispatcher are REG-29-03 double-wired
    # (the worker registers a parallel provider in
    # app/workers/__init__.py:WorkerSettings.on_startup). MembershipActivator +
    # PtPackageActivator are HTTP-only single-wire (D-47-02 — webhook handler
    # runs in an HTTP request session; no ARQ entry path).
    #
    # Phase 48 D-48-25 swaps the YooKassaClientProvider stub for the real
    # client; the other three stubs stay no-op (D-48-26) — wired in Phase 49
    # (activators) and Phase 50 (fiscal dispatcher).
    #
    # Phase 48 D-48-25 — YooKassaClientProvider swap.
    # The closure resolves the client lazily from app.state (populated by
    # combined_lifespan above). Mirrors set_auth_redis_factory(lambda: app.state.redis)
    # at Phase 43 D-43-26. NOT the same byte-equal symbol reference as the worker's
    # closure (each process owns its own httpx.AsyncClient instance) — the parity
    # test (Plan 48-07 update) now asserts "real wiring in both processes",
    # not object identity.
    async def _yookassa_client_provider() -> YooKassaClient:
        return app.state.yookassa_client  # type: ignore[no-any-return]

    register_yookassa_client_provider(_yookassa_client_provider)

    # Phase 47 wiring preserved (D-48-26 — only YooKassaClientProvider swaps in Phase 48).
    register_fiscal_receipt_dispatcher(fiscal_receipt_dispatcher_noop_stub)
    register_membership_activator(membership_activator_noop_stub)
    register_pt_package_activator(pt_package_activator_noop_stub)

    app.include_router(api)
    return app

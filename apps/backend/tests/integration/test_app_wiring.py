"""Startup integration test — create_app() wires every Protocol slot (INFRA-33).

Phase 37 D-37-06 / DEBT-06: pins two contracts the bot worker has historically
drifted from (REG-29-03 lesson + Phase 29 verification):

  (A) After ``create_app()`` returns, EVERY module-private slot variable in
      ``app.core.dependencies`` is non-None. Any future register_* added to
      dependencies.py without a corresponding wire-up in create_app() fails
      this test loudly.

  (B) AST-walk parity: the set of ``register_*`` calls inside
      ``app/workers/telegram_bot.py:main()`` is a SUBSET of the set inside
      ``app/main.py:create_app()``. The bot worker is a separate process
      from the FastAPI app — it never goes through ``create_app()``. Missing
      double-wires silently mis-fire (e.g., DEBT-06: the v1.4
      ``register_active_pt_package_resolver`` was missed in the bot at REG-29-03,
      causing /book to always hit the no-active-package oracle-safe DM).

The AST test additionally asserts:
  - ``register_active_pt_package_resolver`` ∈ bot_calls  (DEBT-06 fix)
  - ``register_slot_by_id_resolver``        ∈ bot_calls  (INFRA-33 defensive)
  - ``register_booking_slot_restorer``      ∉ bot_calls  (API-only per D-37-06)
  - ``register_booking_completer``          ∉ bot_calls  (API-only per D-37-06)
"""

from __future__ import annotations

import ast
from pathlib import Path

import app.core.dependencies as deps
from app.main import create_app

# tests/integration/test_app_wiring.py → parents[2] = apps/backend
_BACKEND_ROOT = Path(__file__).resolve().parents[2]
_MAIN_PY = _BACKEND_ROOT / "app" / "main.py"
_BOT_PY = _BACKEND_ROOT / "app" / "workers" / "telegram_bot.py"
# Phase 42 D-42-26 — ARQ worker entrypoint (REG-29-03 EmailDispatcher
# double-wire). WorkerSettings.on_startup is a sibling-process composition
# root that must re-register every dispatcher slot create_app() registers.
_WORKERS_PY = _BACKEND_ROOT / "app" / "workers" / "__init__.py"


def _register_call_names(path: Path) -> set[str]:
    """Walk the module AST and return every ``register_*`` function-call name."""
    tree = ast.parse(path.read_text(encoding="utf-8"))
    names: set[str] = set()
    for node in ast.walk(tree):
        if (
            isinstance(node, ast.Call)
            and isinstance(node.func, ast.Name)
            and node.func.id.startswith("register_")
        ):
            names.add(node.func.id)
    return names


def test_create_app_registers_all_protocol_slots() -> None:
    """After create_app(), all module-private slot variables are non-None.

    Phase 37 INFRA-33 / D-37-06: deterministic registration order, all slots
    wired BEFORE app.include_router(api). This test pins the contract — any
    future register_* added to dependencies.py without a corresponding wire-up
    in create_app() will fail here loudly.
    """
    create_app()

    # Phase 4-34 slots (pre-existing — must not regress).
    assert deps._user_loader is not None, "Phase 5 register_user_loader missing"
    assert deps._active_membership_resolver is not None, (
        "Phase 17 register_active_membership_resolver missing"
    )
    assert deps._client_by_telegram_resolver is not None, (
        "Phase 19 register_client_by_telegram_resolver missing"
    )
    assert deps._trainer_by_id_resolver is not None, (
        "Phase 31 register_trainer_by_id_resolver missing"
    )
    assert deps._payment_recorder is not None, "Phase 32 register_payment_recorder missing"
    assert deps._payment_refunder is not None, "Phase 32 register_payment_refunder missing"
    assert deps._active_pt_package_resolver is not None, (
        "Phase 33 register_active_pt_package_resolver missing"
    )

    # Phase 37 INFRA-33 slots (new — D-37-06).
    assert deps._slot_by_id_resolver is not None, (
        "Phase 37 register_slot_by_id_resolver missing"
    )
    assert deps._booking_slot_restorer is not None, (
        "Phase 37 register_booking_slot_restorer missing"
    )
    assert deps._booking_completer is not None, (
        "Phase 37 register_booking_completer missing"
    )

    # Phase 42 D-42-26 slot — EmailDispatcher (REG-29-03 double-wire).
    # create_app() registers the FastAPI-side dispatcher; the ARQ worker
    # process registers the same callable inside WorkerSettings.on_startup
    # (asserted structurally by ``test_worker_on_startup_double_wires_email_dispatcher``).
    assert deps._email_dispatcher is not None, (
        "Phase 42 register_email_dispatcher missing in create_app()"
    )

    # Phase 43 D-43-26/27 slot — UserSessionInvalidator (single-wire — NOT
    # double-wired in the worker because no ARQ consumer exists in Phase 43
    # scope). The anti-double-wire half is asserted separately by
    # ``test_user_session_invalidator_registered_single_wire``.
    assert deps._user_session_invalidator is not None, (
        "Phase 43 register_user_session_invalidator missing in create_app() — "
        "expected closure-injected impl after register_email_dispatcher call."
    )


def test_user_session_invalidator_registered_single_wire() -> None:
    """Phase 43 D-43-27 — UserSessionInvalidator is SINGLE-wired (FastAPI only).

    Unlike EmailDispatcher (double-wired per REG-29-03), the
    UserSessionInvalidator has zero ARQ consumers — the worker MUST NOT
    register it. This test enforces the asymmetry on BOTH halves:

      (A) Positive: after create_app(), deps._user_session_invalidator is
          non-None (also covered by the all-slots test above; pinned here
          again so this single test is self-contained for the D-43-27
          parity assertion).
      (B) Negative anti-double-wire: ``app/workers/__init__.py`` MUST NOT
          contain a ``register_user_session_invalidator(...)`` call. An
          accidental future addition would violate D-43-27 single-wire
          discipline (the slot has no ARQ consumer; double-wiring it would
          create an idle registration that REG-29-03 parity would flag as
          drift if anyone ever consumes it from a cron without a parallel
          main.py update).
    """
    # Reset slot so the test is order-independent.
    deps._user_session_invalidator = None

    create_app()
    assert deps._user_session_invalidator is not None, (
        "Phase 43 register_user_session_invalidator missing in create_app() — "
        "expected closure-injected impl after register_email_dispatcher call."
    )

    # Anti-double-wire assertion: worker module MUST NOT call
    # register_user_session_invalidator (D-43-27 single-wire discipline).
    worker_calls = _register_call_names(_WORKERS_PY)
    assert "register_user_session_invalidator" not in worker_calls, (
        "Phase 43 D-43-27 single-wire violated — worker/__init__.py must NOT "
        "register UserSessionInvalidator (no ARQ consumers in Phase 43 scope)."
    )


def test_bot_main_register_set_is_subset_of_api_main_register_set() -> None:
    """Parity test (INFRA-33 / D-37-06): bot wires a subset of slots create_app() wires.

    AST-walk every ``register_*`` call in both modules; assert
    ``bot_calls <= main_calls``. Membership assertions cover:
      - DEBT-06: register_active_pt_package_resolver MUST be in the bot
        (Phase 40 /book consumes it via bookings.service).
      - INFRA-33: register_slot_by_id_resolver MUST be in the bot (defensive
        double-wire for /book; D-37-06).
      - register_booking_slot_restorer / register_booking_completer MUST NOT
        be in the bot (API-only per D-37-06; mirrors D-32-14 / D-33-12
        discipline for non-bot-participant slots).
    """
    main_calls = _register_call_names(_MAIN_PY)
    bot_calls = _register_call_names(_BOT_PY)

    assert bot_calls <= main_calls, (
        f"bot_main_parity violation: bot wires register_* not in create_app(): "
        f"{sorted(bot_calls - main_calls)}"
    )

    # DEBT-06: bot must wire active_pt_package_resolver (REG-29-03 omission fix).
    assert "register_active_pt_package_resolver" in bot_calls, (
        "DEBT-06 regression: bot worker missing register_active_pt_package_resolver"
    )

    # INFRA-33: bot must wire slot_by_id_resolver (defensive double-wire for /book).
    assert "register_slot_by_id_resolver" in bot_calls, (
        "INFRA-33 regression: bot worker missing register_slot_by_id_resolver"
    )

    # API-only slots must NOT leak into bot wiring.
    assert "register_booking_slot_restorer" not in bot_calls, (
        "D-37-06 violation: register_booking_slot_restorer is API-only (bot does "
        "not cancel bookings)"
    )
    assert "register_booking_completer" not in bot_calls, (
        "D-37-06 violation: register_booking_completer is API-only (bot does not "
        "record PT-sessions)"
    )


def test_worker_on_startup_double_wires_email_dispatcher() -> None:
    """REG-29-03 (D-42-26): ARQ ``WorkerSettings.on_startup`` MUST register
    EmailDispatcher with the same callable that ``app.main.create_app()`` does.

    The AST-walk parity is structural — it verifies BOTH ``app/main.py`` AND
    ``app/workers/__init__.py`` call ``register_email_dispatcher``. Byte-equality
    of the symbol reference is implicit because both files import the same
    ``enqueue_email_dispatch`` from ``app.integrations.email.dispatcher``
    (asserted indirectly by the runtime slot-fills test above plus per-process
    smoke tests in plan 42-09).

    Why structural and not runtime: ``WorkerSettings.on_startup`` runs inside
    an ARQ worker process — the integration test runs inside the FastAPI ASGI
    process, so there is no way to call ``on_startup`` here without
    instantiating the worker side-effect tree (Redis pool, EmailClient, etc.)
    that this test deliberately avoids.
    """
    main_calls = _register_call_names(_MAIN_PY)
    workers_calls = _register_call_names(_WORKERS_PY)

    assert "register_email_dispatcher" in main_calls, (
        "REG-29-03 violation: create_app() does NOT register EmailDispatcher "
        "(Phase 42 D-42-26 mandates the FastAPI-side wire)."
    )
    assert "register_email_dispatcher" in workers_calls, (
        "REG-29-03 violation: WorkerSettings.on_startup does NOT register "
        "EmailDispatcher (Phase 42 D-42-26 mandates the worker-side wire). "
        "Without the double-wire the ARQ dispatch_email task cannot resolve "
        "the dispatcher slot and the email-OTP fallback silently fails."
    )

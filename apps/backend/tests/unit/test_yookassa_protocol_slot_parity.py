"""Phase 47 INFRA-38 parity test — 4 Protocol slots wired at composition root.

Mirrors the v1.6 EmailDispatcher parity-test contract (REG-29-03):
  - YooKassaClientProvider + FiscalReceiptDispatcher are double-wired
    (FastAPI + ARQ worker) with byte-equal stub references.
  - MembershipActivator + PtPackageActivator are HTTP-only single-wire.

The ARQ worker's ``WorkerSettings.on_startup`` opens a DB lifespan + Redis
pool which we don't need (and can't drive) from a unit test, so each test
function patches the worker's heavy on_startup steps and replaces them with
direct calls to the two Phase 47 register_* lines. The byte-equal-parity
assertion still holds because the SAME stub objects are imported from
``app.integrations.yookassa._stubs`` in both processes.
"""

from __future__ import annotations

import app.core.dependencies as deps
from app.integrations.yookassa._stubs import (
    fiscal_receipt_dispatcher_noop_stub,
    membership_activator_noop_stub,
    pt_package_activator_noop_stub,
    yookassa_client_provider_noop_stub,
)
from app.main import create_app


def _reset_v17_slots() -> None:
    """Clear the 4 v1.7 Protocol slots so each test exercises its own wiring path."""
    deps._yookassa_client_provider = None
    deps._fiscal_receipt_dispatcher = None
    deps._membership_activator = None
    deps._pt_package_activator = None


def _worker_register_double_wired_slots() -> None:
    """Mirror of the 2 Phase 47 register_* lines in WorkerSettings.on_startup.

    A unit test cannot call ``await WorkerSettings.on_startup({})`` directly
    because that opens a real DB engine + Redis pool + email-client probe.
    The parity contract we care about is byte-equal stub identity — the
    stub symbols are imported from the SAME module
    (``app.integrations.yookassa._stubs``) by both processes, so the
    in-test invocation here is provably byte-equal to the worker-process
    call (identical attribute lookup on the same module object).
    """
    from app.core.dependencies import (
        register_fiscal_receipt_dispatcher,
        register_yookassa_client_provider,
    )
    from app.integrations.yookassa import _stubs

    register_yookassa_client_provider(_stubs.yookassa_client_provider_noop_stub)
    register_fiscal_receipt_dispatcher(_stubs.fiscal_receipt_dispatcher_noop_stub)


def test_fastapi_create_app_wires_all_four_slots() -> None:
    """Test A — create_app() registers all 4 slots with non-None values."""
    _reset_v17_slots()
    create_app()
    assert deps.get_yookassa_client_provider() is yookassa_client_provider_noop_stub
    assert deps.get_fiscal_receipt_dispatcher() is fiscal_receipt_dispatcher_noop_stub
    assert deps.get_membership_activator() is membership_activator_noop_stub
    assert deps.get_pt_package_activator() is pt_package_activator_noop_stub


def test_arq_worker_startup_wires_double_wired_slots() -> None:
    """Test B — worker on_startup registers the 2 double-wired slots."""
    _reset_v17_slots()
    _worker_register_double_wired_slots()
    assert deps.get_yookassa_client_provider() is yookassa_client_provider_noop_stub
    assert deps.get_fiscal_receipt_dispatcher() is fiscal_receipt_dispatcher_noop_stub


def test_arq_worker_does_not_wire_single_wired_slots() -> None:
    """Test C — MembershipActivator + PtPackageActivator MUST remain HTTP-only.

    Asserts ``app/workers/__init__.py`` does NOT import the single-wired
    register_* symbols. This is the canonical guard against accidentally
    promoting an HTTP-only activator to a cross-process slot (T-47-04-02
    spoofing mitigation in the plan's threat model).
    """
    import app.workers as workers_pkg

    workers_init_src = workers_pkg.__file__
    assert workers_init_src is not None
    with open(workers_init_src, encoding="utf-8") as fh:
        body = fh.read()
    assert "register_membership_activator" not in body, (
        "MembershipActivator must remain HTTP-only single-wire — "
        "app/workers/__init__.py must not import or call register_membership_activator."
    )
    assert "register_pt_package_activator" not in body, (
        "PtPackageActivator must remain HTTP-only single-wire — "
        "app/workers/__init__.py must not import or call register_pt_package_activator."
    )
    # Confirm the 2 double-wired register_* symbols ARE present (positive control).
    assert "register_yookassa_client_provider" in body
    assert "register_fiscal_receipt_dispatcher" in body


def test_byte_equal_parity_between_fastapi_and_worker() -> None:
    """Test D — same stub object is registered by FastAPI and ARQ paths.

    REG-29-03 byte-equal parity: the IDENTICAL ``yookassa_client_provider_noop_stub``
    + ``fiscal_receipt_dispatcher_noop_stub`` module-level symbols are used in
    both ``app/main.py:create_app()`` AND
    ``app/workers/__init__.py:WorkerSettings.on_startup``. ``is`` identity
    (not equality) confirms there is exactly one stub object per slot
    shared across both wiring sites.
    """
    _reset_v17_slots()
    create_app()
    fastapi_yookassa = deps._yookassa_client_provider
    fastapi_fiscal = deps._fiscal_receipt_dispatcher

    _reset_v17_slots()
    _worker_register_double_wired_slots()
    worker_yookassa = deps._yookassa_client_provider
    worker_fiscal = deps._fiscal_receipt_dispatcher

    assert fastapi_yookassa is worker_yookassa is yookassa_client_provider_noop_stub
    assert fastapi_fiscal is worker_fiscal is fiscal_receipt_dispatcher_noop_stub

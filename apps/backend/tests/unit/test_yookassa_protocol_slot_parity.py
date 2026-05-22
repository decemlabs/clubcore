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

Phase 48 D-48-25 — YooKassaClientProvider parity is RELAXED from
object-identity to structural (each process owns its own httpx.AsyncClient
closure, so the closures cannot be the same object). The parity check is
now: both sites import the real ``build_yookassa_client`` factory AND both
sites register a closure named ``_yookassa_client_provider`` (NOT
``yookassa_client_provider_noop_stub``). The other 3 stubs
(FiscalReceiptDispatcher, MembershipActivator, PtPackageActivator) retain
Phase 47 byte-equal parity per D-48-26.
"""

from __future__ import annotations

from pathlib import Path

import pytest

import app.core.dependencies as deps
from app.integrations.yookassa._stubs import (
    fiscal_receipt_dispatcher_noop_stub,
    membership_activator_noop_stub,
    pt_package_activator_noop_stub,
)
from app.main import create_app

# Resolve source files relative to this test module so pytest cwd does not
# matter (project convention is `cd apps/backend && uv run pytest`, but the
# Path is computed from __file__ to stay robust).
_BACKEND_ROOT = Path(__file__).resolve().parents[2]
_MAIN_PY = _BACKEND_ROOT / "app" / "main.py"
_WORKERS_INIT_PY = _BACKEND_ROOT / "app" / "workers" / "__init__.py"


def _reset_v17_slots() -> None:
    """Clear the 4 v1.7 Protocol slots so each test exercises its own wiring path."""
    deps._yookassa_client_provider = None
    deps._fiscal_receipt_dispatcher = None
    deps._membership_activator = None
    deps._pt_package_activator = None


def _worker_register_double_wired_slots() -> None:
    """Phase 48 D-48-25: structural parity replaces runtime byte-equal.

    Phase 47 simulated the worker by registering the no-op stub directly so the
    parity test could assert ``provider is yookassa_client_provider_noop_stub``.
    Phase 48 swaps to a real closure that reads from ``ctx["yookassa_client"]``
    — driving that closure from a unit test would require a real httpx client.
    Test B now validates the wiring STRUCTURALLY by reading
    ``app/workers/__init__.py`` source instead. This helper only registers the
    surviving Phase 47 byte-equal stub (fiscal_receipt_dispatcher) for Test C's
    reference.
    """
    from app.core.dependencies import register_fiscal_receipt_dispatcher
    from app.integrations.yookassa import _stubs

    register_fiscal_receipt_dispatcher(_stubs.fiscal_receipt_dispatcher_noop_stub)


def test_fastapi_create_app_wires_all_four_slots() -> None:
    """Test A — create_app() wires all 4 slots; Phase 48 swaps YooKassaClientProvider only.

    D-48-25: structural source-grep check for the YooKassaClientProvider wiring
    (each process owns its own httpx.AsyncClient closure — runtime byte-equal is
    impossible). D-48-26: the other 3 stubs stay Phase-47 byte-equal — runtime
    identity check preserved for fiscal / membership / pt_package.
    """
    _reset_v17_slots()
    create_app()

    # YooKassaClientProvider — STRUCTURAL check (Phase 48 D-48-25).
    main_src = _MAIN_PY.read_text(encoding="utf-8")
    assert "from app.integrations.yookassa.factory import build_yookassa_client" in main_src, (
        "main.py must import build_yookassa_client (Phase 48 D-48-25)."
    )
    assert "register_yookassa_client_provider(_yookassa_client_provider)" in main_src, (
        "main.py must register the lazy _yookassa_client_provider closure (D-48-25)."
    )
    _noop_main = "register_yookassa_client_provider(yookassa_client_provider_noop_stub)"
    assert _noop_main not in main_src, (
        "Phase 47 no-op stub registration MUST be removed from main.py (D-48-25)."
    )

    # Other 3 stubs — Phase 47 byte-equal preserved (D-48-26).
    assert deps.get_fiscal_receipt_dispatcher() is fiscal_receipt_dispatcher_noop_stub
    assert deps.get_membership_activator() is membership_activator_noop_stub
    assert deps.get_pt_package_activator() is pt_package_activator_noop_stub


def test_arq_worker_startup_wires_double_wired_slots() -> None:
    """Test B — worker on_startup wires the 2 double-wired slots.

    D-48-25: structural source-grep check for the YooKassaClientProvider wiring
    on the worker side. D-48-26: fiscal_receipt_dispatcher stays Phase-47 byte-equal.
    """
    _reset_v17_slots()
    _worker_register_double_wired_slots()  # registers fiscal stub only (see helper)

    # YooKassaClientProvider — STRUCTURAL check (Phase 48 D-48-25).
    worker_src = _WORKERS_INIT_PY.read_text(encoding="utf-8")
    assert "build_yookassa_client" in worker_src, (
        "workers/__init__.py must import build_yookassa_client (D-48-25)."
    )
    assert "register_yookassa_client_provider(_yookassa_client_provider)" in worker_src, (
        "workers/__init__.py must register the lazy _yookassa_client_provider closure (D-48-25)."
    )
    _noop_worker = "register_yookassa_client_provider(yookassa_client_provider_noop_stub)"
    assert _noop_worker not in worker_src, (
        "Phase 47 no-op stub registration MUST be removed from workers/__init__.py (D-48-25)."
    )

    # fiscal_receipt_dispatcher — Phase 47 byte-equal preserved (D-48-26).
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
    """Test D — Phase 48 D-48-25: rewritten in Plan 48-07 Task 3b.

    Phase 48 Task 3a (this file): the Phase 47 import of
    ``yookassa_client_provider_noop_stub`` is removed because Tests A + B
    no longer assert identity against it. The original Test D body asserted
    ``fastapi_yookassa is worker_yookassa is yookassa_client_provider_noop_stub``
    — that assertion is fundamentally incompatible with the closure-per-process
    wiring shipped in Tasks 1 + 2. Task 3b replaces this body with the new
    closure-name + structural parity check.

    Skipped here so the test module remains lint + type clean between 3a and 3b.
    """
    pytest.skip("Rewritten in Plan 48-07 Task 3b — closure-name parity check.")

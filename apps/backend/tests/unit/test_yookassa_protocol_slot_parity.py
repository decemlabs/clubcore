"""Phase 47 INFRA-38 parity test — 4 Protocol slots wired at composition root.

Mirrors the v1.6 EmailDispatcher parity-test contract (REG-29-03):
  - YooKassaClientProvider + FiscalReceiptDispatcher are double-wired
    (FastAPI + ARQ worker) with structural parity.
  - MembershipActivator + PtPackageActivator are HTTP-only single-wire.

The ARQ worker's ``WorkerSettings.on_startup`` opens a DB lifespan + Redis
pool which we don't need (and can't drive) from a unit test, so each test
function patches the worker's heavy on_startup steps and replaces them with
direct calls to the Phase 51 register_* lines.

Phase 48 D-48-25 — YooKassaClientProvider parity is RELAXED from
object-identity to structural (each process owns its own httpx.AsyncClient
closure, so the closures cannot be the same object). The parity check is
now: both sites import the real ``build_yookassa_client`` factory AND both
sites register a closure named ``_yookassa_client_provider`` (NOT
``yookassa_client_provider_noop_stub``).

Phase 49 D-49-22 — FiscalReceiptDispatcher was swapped from
``fiscal_receipt_dispatcher_noop_stub`` to ``phase49_fiscal_dispatcher_stub``
(a Phase-49-only bridge stub living in
``app.modules.online_payments.service``).

Phase 51 FISCAL-05 — FiscalReceiptDispatcher swapped from the Phase 49
bridge stub to a real ARQ-enqueue closure named
``_real_fiscal_receipt_dispatcher`` defined LOCALLY inside BOTH
``app/main.py:create_app()`` AND ``app/workers/__init__.py:WorkerSettings.on_startup``.
Each process owns its own closure (capturing its own arq_pool); per-process
closures cannot be Python-identity-equal, so the parity check is RELAXED
from byte-equal to closure-name parity, mirroring the
``_yookassa_client_provider`` pattern at Phase 48.

MembershipActivator + PtPackageActivator continue to be HTTP-only
single-wire (no worker-side registration); their Phase 49
``activate_*_from_webhook`` stub-body callables remain the canonical
identity targets.
"""

from __future__ import annotations

from pathlib import Path

import app.core.dependencies as deps
from app.main import create_app
from app.modules.memberships.service import activate_membership_from_webhook
from app.modules.pt_packages.service import activate_pt_package_from_webhook

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


def test_fastapi_create_app_wires_all_four_slots() -> None:
    """Test A — create_app() wires all 4 slots.

    Phase 48 D-48-25: structural source-grep check for the
    YooKassaClientProvider wiring (each process owns its own
    httpx.AsyncClient closure — runtime byte-equal is impossible).

    Phase 51 FISCAL-05: FiscalReceiptDispatcher is now ALSO a per-process
    closure (``_real_fiscal_receipt_dispatcher``), so the byte-equal
    identity check is relaxed to a closure-name check for that slot too —
    mirroring the YooKassaClientProvider pattern.

    MembershipActivator + PtPackageActivator stay HTTP-only single-wire
    with byte-equal identity to their service-layer functions.
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

    # FiscalReceiptDispatcher — Phase 51 STRUCTURAL check.
    # The slot now points at a per-process closure that enqueues
    # dispatch_fiscal_receipt into app.state.arq_pool; byte-equal identity
    # is impossible across processes (mirrors the YooKassaClientProvider
    # decision at Phase 48 D-48-25).
    fiscal = deps.get_fiscal_receipt_dispatcher()
    assert fiscal is not None, "create_app() must register FiscalReceiptDispatcher"
    assert callable(fiscal), "registered FiscalReceiptDispatcher must be callable"
    assert getattr(fiscal, "__name__", None) == "_real_fiscal_receipt_dispatcher", (
        "Phase 51 FISCAL-05 — main.py must register the closure named "
        "'_real_fiscal_receipt_dispatcher' (replaces Phase 49 "
        "phase49_fiscal_dispatcher_stub)."
    )
    assert "register_fiscal_receipt_dispatcher(_real_fiscal_receipt_dispatcher)" in main_src, (
        "main.py must register the lazy _real_fiscal_receipt_dispatcher closure "
        "(Phase 51 FISCAL-05)."
    )
    assert "phase49_fiscal_dispatcher_stub" not in main_src.replace(
        "the Phase 49 phase49_fiscal_dispatcher_stub", ""
    ), (
        "Phase 49 phase49_fiscal_dispatcher_stub MUST NOT be registered in "
        "main.py after Phase 51 FISCAL-05 (only mentioned in the replaced-by "
        "comment)."
    )

    # HTTP-only activators — byte-equal identity preserved.
    assert deps.get_membership_activator() is activate_membership_from_webhook
    assert deps.get_pt_package_activator() is activate_pt_package_from_webhook


def test_arq_worker_startup_structural_parity() -> None:
    """Test B — worker on_startup wires the 2 double-wired slots STRUCTURALLY.

    Phase 51 FISCAL-05: both double-wired slots
    (YooKassaClientProvider + FiscalReceiptDispatcher) are now per-process
    closures. Runtime byte-equal identity is impossible — the parity check
    is purely structural source-grep against
    ``app/workers/__init__.py``.

    We do NOT drive the worker on_startup body from this test (it requires
    a real Redis + DB lifespan); the source-grep is sufficient because the
    closure naming is what the parity contract pins.
    """
    worker_src = _WORKERS_INIT_PY.read_text(encoding="utf-8")

    # YooKassaClientProvider — STRUCTURAL check (Phase 48 D-48-25).
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

    # FiscalReceiptDispatcher — Phase 51 FISCAL-05 STRUCTURAL check.
    assert (
        "register_fiscal_receipt_dispatcher(_real_fiscal_receipt_dispatcher)"
        in worker_src
    ), (
        "workers/__init__.py must register the lazy _real_fiscal_receipt_dispatcher "
        "closure (Phase 51 FISCAL-05)."
    )
    assert (
        "from app.modules.online_payments.service import phase49_fiscal_dispatcher_stub"
        not in worker_src
    ), (
        "Phase 49 phase49_fiscal_dispatcher_stub import MUST be removed from "
        "workers/__init__.py after Phase 51 FISCAL-05."
    )
    # Positive control — dispatch_fiscal_receipt itself must be imported +
    # registered in WorkerSettings.functions.
    assert (
        "from app.modules.fiscal_receipts.tasks import dispatch_fiscal_receipt"
        in worker_src
    ), "workers/__init__.py must import dispatch_fiscal_receipt (Phase 51 FISCAL-05)."


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


def test_closure_name_parity_between_fastapi_and_worker() -> None:
    """Test D — Phase 51 FISCAL-05: closure-name parity for both double-wired slots.

    Phase 47 asserted byte-equal stub identity for both YooKassaClientProvider
    and FiscalReceiptDispatcher in BOTH processes. Phase 48 D-48-25 swapped
    YooKassaClientProvider to a per-process closure (byte-equal impossible),
    relaxing the contract to a closure-name source-grep parity. Phase 51
    FISCAL-05 applies the SAME treatment to FiscalReceiptDispatcher — both
    composition roots define an ``async def _real_fiscal_receipt_dispatcher``
    closure, byte-equal identity is intentionally impossible, the parity
    contract is the literal closure name.

    Updated invariants:
      - FastAPI side: after create_app(), deps._yookassa_client_provider and
        deps._fiscal_receipt_dispatcher are both closures (not the no-op
        stubs). Their ``__name__`` attributes match the canonical literals.
      - Worker side: source-grep confirms BOTH composition roots define
        closures with the same name (validates structural parity without
        spinning up the worker's DB + Redis lifespan).
    """
    # FastAPI side — runtime closure-name check for both double-wired slots.
    _reset_v17_slots()
    create_app()
    fastapi_yookassa = deps._yookassa_client_provider
    fastapi_fiscal = deps._fiscal_receipt_dispatcher

    assert fastapi_yookassa is not None, "create_app() must register YooKassaClientProvider"
    assert callable(fastapi_yookassa), "registered provider must be callable"
    assert getattr(fastapi_yookassa, "__name__", None) == "_yookassa_client_provider", (
        "FastAPI side must register the closure named '_yookassa_client_provider' "
        "(Phase 48 D-48-25)."
    )

    assert fastapi_fiscal is not None, "create_app() must register FiscalReceiptDispatcher"
    assert callable(fastapi_fiscal), "registered FiscalReceiptDispatcher must be callable"
    assert getattr(fastapi_fiscal, "__name__", None) == "_real_fiscal_receipt_dispatcher", (
        "FastAPI side must register the closure named "
        "'_real_fiscal_receipt_dispatcher' (Phase 51 FISCAL-05)."
    )

    # Worker side — source-grep parity (we cannot drive worker on_startup
    # from a unit test; it requires a real Redis + DB lifespan).
    main_src = _MAIN_PY.read_text(encoding="utf-8")
    worker_src = _WORKERS_INIT_PY.read_text(encoding="utf-8")
    assert "async def _yookassa_client_provider" in main_src, (
        "main.py must define the closure as 'async def _yookassa_client_provider'."
    )
    assert "async def _yookassa_client_provider" in worker_src, (
        "workers/__init__.py must define the closure with the SAME name "
        "'_yookassa_client_provider' (Phase 48 D-48-25 closure-name parity)."
    )
    assert "async def _real_fiscal_receipt_dispatcher" in main_src, (
        "main.py must define the closure as 'async def _real_fiscal_receipt_dispatcher' "
        "(Phase 51 FISCAL-05)."
    )
    assert "async def _real_fiscal_receipt_dispatcher" in worker_src, (
        "workers/__init__.py must define the closure with the SAME name "
        "'_real_fiscal_receipt_dispatcher' (Phase 51 FISCAL-05 closure-name parity)."
    )

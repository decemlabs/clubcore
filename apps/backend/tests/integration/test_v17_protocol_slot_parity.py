"""Phase 49 D-49-23 — v1.7 Protocol slot parity test (Roadmap success-criterion #6).

After create_app(), all 4 v1.7 Protocol slot accessors return non-None
objects WITHOUT raising RuntimeError. Mirrors the v1.6 EmailDispatcher /
PaymentRecorder parity tests in tests/integration/test_app_wiring.py.

Phase 49 D-49-22: FiscalReceiptDispatcher is wired to a stub-body callable
(phase49_fiscal_dispatcher_stub), NOT the Phase 47 noop_stub. The second
test guards against accidental rollback to the Phase 47 noop.
"""

from __future__ import annotations

import app.core.dependencies as deps
from app.core.dependencies import (
    get_fiscal_receipt_dispatcher,
    get_membership_activator,
    get_pt_package_activator,
    get_yookassa_client_provider,
)
from app.integrations.yookassa._stubs import fiscal_receipt_dispatcher_noop_stub
from app.main import create_app


def _reset_v17_slots() -> None:
    deps._yookassa_client_provider = None
    deps._fiscal_receipt_dispatcher = None
    deps._membership_activator = None
    deps._pt_package_activator = None


def test_v17_protocol_slots_non_none_after_app_startup() -> None:
    """Success-criterion #6 — all 4 slots non-None after create_app()."""
    _reset_v17_slots()
    create_app()
    assert get_yookassa_client_provider() is not None
    assert get_fiscal_receipt_dispatcher() is not None
    assert get_membership_activator() is not None
    assert get_pt_package_activator() is not None


def test_fiscal_receipt_dispatcher_is_not_phase47_noop_stub_after_phase49() -> None:
    """D-49-22 regression guard — Phase 49 swap kept.

    If a future refactor accidentally reverts to the Phase 47 noop stub,
    this test fails. Phase 50 FISCAL-01 will swap to the real ARQ-enqueue
    body — at that point, update this test's positive identity assertion.
    """
    _reset_v17_slots()
    create_app()
    assert get_fiscal_receipt_dispatcher() is not fiscal_receipt_dispatcher_noop_stub

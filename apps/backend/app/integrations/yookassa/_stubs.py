"""Phase 47 no-op Protocol-slot stubs (D-47-01 Option A — empty wiring at composition root).

Each stub satisfies the corresponding Protocol signature in
``app.core.dependencies`` so the defensive-raise accessors do not fire
during request handling. Calling any stub raises NotImplementedError —
the real implementations land in Phases 48 (YooKassaClient) and 50
(MembershipActivator, PtPackageActivator, FiscalReceiptDispatcher).

Layer invariant: lives at integrations layer — MUST NOT import from
app.modules.* (importlinter contract integrations-not-depend-on-modules).
"""

from __future__ import annotations

from typing import Any
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession


async def yookassa_client_provider_noop_stub() -> Any:
    raise NotImplementedError(
        "YooKassaClient lands in Phase 48 ADAPTER-02 — Phase 47 ships only "
        "the Protocol slot + no-op wiring stub."
    )


async def fiscal_receipt_dispatcher_noop_stub(
    *,
    fiscal_receipt_id: UUID,
    audit_correlation_id: UUID | None,
) -> None:
    raise NotImplementedError(
        "FiscalReceiptDispatcher lands in Phase 50 FISCAL-01 / Phase 51 "
        "FISCAL-05 — Phase 47 ships only the Protocol slot + no-op wiring stub."
    )


async def membership_activator_noop_stub(
    session: AsyncSession,
    *,
    membership_id: UUID,
    audit_correlation_id: UUID | None,
) -> Any:
    raise NotImplementedError(
        "MembershipActivator lands in Phase 50 WH-05 — Phase 47 ships only "
        "the Protocol slot + no-op wiring stub."
    )


async def pt_package_activator_noop_stub(
    session: AsyncSession,
    *,
    pt_package_id: UUID,
    audit_correlation_id: UUID | None,
) -> Any:
    raise NotImplementedError(
        "PtPackageActivator lands in Phase 50 WH-05 — Phase 47 ships only "
        "the Protocol slot + no-op wiring stub."
    )

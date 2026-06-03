"""Payment method service (Phase 79 PAYM-02..04).

get_payment_method: returns active card for client (200/null if absent, D-69-03).
unlink_payment_method: soft-delete (idempotent 204 no-op if absent, D-decision).
patch_autopay: enable/disable autopay; enable gates on ФЗ-376 consent (PAYM-04).

Error discipline: distinct AppError subclasses with stable code= attribute.
No try/except — AppError bubbles to _app_error_handler.
No session.commit() — caller-owns-txn (D-32-10/D-49-19).
"""

from __future__ import annotations

from uuid import UUID

import structlog
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import ConflictError
from app.modules.payment_methods import repository
from app.modules.payment_methods.schemas import (
    ClientAutopayPatchRequest,
    ClientPaymentMethodResponse,
)

_log = structlog.get_logger("modules.payment_methods.service")


async def get_payment_method(
    session: AsyncSession,
    client_id: UUID,
) -> ClientPaymentMethodResponse | None:
    """Return active card for client, or None when no card exists (200/null, D-69-03).

    No session.commit() — read-only path.
    """
    row = await repository.fetch_active_payment_method(session, client_id)
    if row is None:
        return None
    return ClientPaymentMethodResponse.model_validate(row)


async def unlink_payment_method(
    session: AsyncSession,
    client_id: UUID,
) -> None:
    """Soft-delete the active card (idempotent: no-op when no active card exists).

    The bool return from repository is intentionally discarded — router returns 204
    regardless (idempotent unlink discipline).
    No session.commit() — caller-owns-txn.
    """
    await repository.unlink_payment_method(session, client_id)


async def patch_autopay(
    session: AsyncSession,
    client_id: UUID,
    payload: ClientAutopayPatchRequest,
) -> ClientPaymentMethodResponse:
    """Enable/disable autopay for the client's active card (PAYM-04 / ФЗ-376).

    Enable path: requires active card AND consent_acknowledged=True in the same
    request → server stamps consent_recorded_at=now(). Missing either → 409.
    Disable path: ungated — always succeeds if an active card exists.

    Raises:
        ConflictError("no_active_payment_method"): no active card for enable or disable.
        ConflictError("consent_required"): enabling without consent_acknowledged=True.

    No session.commit() — caller-owns-txn.
    """
    row = await repository.fetch_active_payment_method(session, client_id)
    if row is None:
        raise ConflictError("no_active_payment_method")
    if payload.enabled and not payload.consent_acknowledged:
        raise ConflictError("consent_required")
    await repository.set_autopay(
        session,
        client_id,
        enabled=payload.enabled,
        stamp_consent=(payload.enabled and payload.consent_acknowledged),
    )
    refreshed = await repository.fetch_active_payment_method(session, client_id)
    if refreshed is None:
        # Defensive: card was unlinked concurrently; treat as no-op error.
        raise ConflictError("no_active_payment_method")
    _log.info(
        "autopay_patched",
        client_id=str(client_id),
        enabled=payload.enabled,
        consent_acknowledged=payload.consent_acknowledged,
    )
    return ClientPaymentMethodResponse.model_validate(refreshed)

"""ЮKassa integration package (Phase 47 skeleton; Phase 48 wires the real adapter).

Phase 47: settings + AST-gated constants + Protocol-slot wiring only.
Phase 48: async httpx client, IP-allowlist webhook verifier, receipt builder.
"""

from app.integrations.yookassa.types import (
    YooKassaPaymentResult,
    YooKassaReceiptResult,
    YooKassaRefundResult,
    YooKassaWebhookEvent,
)

__all__ = [
    "YooKassaPaymentResult",
    "YooKassaReceiptResult",
    "YooKassaRefundResult",
    "YooKassaWebhookEvent",
]

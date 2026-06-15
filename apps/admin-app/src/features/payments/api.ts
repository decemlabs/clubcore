/**
 * Payments domain TanStack Query hooks (Phase 101-04, extended Phase 103-01, 112-03).
 *
 * Phase 101: usePaymentsByClient (scoped by-client path, reception+owner)
 * Phase 103: usePaymentsLedger (global /payments ledger, OWNER_ONLY via can() gate)
 * Phase 112: useRefundPayment (POST /payments/{id}/refund — owner-only REF-01)
 *
 * Transport: staffRequest(...) → Schema.parse(raw).data
 *
 * IMPORTANT: by-client path is /by-client/{client_id} (path param, NOT ?clientId= query).
 * The backend require_payments_view_for_subject() scopes access to that client's
 * payments — the global /payments route 403s for non-privileged staff (T-101-12-IDOR).
 *
 * ApiError re-exported (D-100-03-APIERROR-REEXPORT) so page/tab layers can
 * `instanceof ApiError` without importing @/api/client directly (ESLint boundary).
 */
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { staffRequest, ApiError } from '@/api/client';
import { can } from '@/shared/session/can';
import type { Role } from '@/shared/session/types';
import { PaymentsListResponseSchema, type PaymentsLedgerQuery } from './schemas';

// ---------------------------------------------------------------------------
// Key factory
// ---------------------------------------------------------------------------

export const paymentsKeys = {
  all: ['payments'] as const,
  byClient: (clientId: string) => [...paymentsKeys.all, 'byClient', clientId] as const,
  // NEW Phase 103
  lists: () => [...paymentsKeys.all, 'list'] as const,
  list: (filter: PaymentsLedgerQuery) => [...paymentsKeys.lists(), filter] as const,
};

// ---------------------------------------------------------------------------
// Queries
// ---------------------------------------------------------------------------

/**
 * Fetch payments for a client via the scoped path:
 * GET /api/v1/payments/by-client/{client_id}
 *
 * Uses `params` (path interpolation), NOT `query` — the path has a {client_id}
 * placeholder, not a ?clientId= query string (per CONTEXT §Payments + PATTERNS §Backend Path Corrections).
 * Enabled only when clientId is truthy.
 */
export function usePaymentsByClient(clientId: string) {
  return useQuery({
    queryKey: paymentsKeys.byClient(clientId),
    queryFn: async () => {
      const raw = await staffRequest('get', '/api/v1/payments/by-client/{client_id}', {
        params: { client_id: clientId },
      });
      return PaymentsListResponseSchema.parse(raw).data;
    },
    enabled: !!clientId,
    staleTime: 30_000,
  });
}

/**
 * Global payments ledger (GET /api/v1/payments — OWNER_ONLY).
 *
 * Enabled only for owner role (can(role,'view','payments') per OWNER_ONLY matrix).
 * Reception makes ZERO API calls — enabled:false when can() returns false.
 * Returns PaymentsListResponse; caller computes daily totals client-side.
 */
export function usePaymentsLedger(filter: PaymentsLedgerQuery, role: Role) {
  return useQuery({
    queryKey: paymentsKeys.list(filter),
    queryFn: async () => {
      const query: Record<string, string | number> = {};
      if (filter.receivedFrom) query['receivedFrom'] = filter.receivedFrom;
      if (filter.receivedTo) query['receivedTo'] = filter.receivedTo;
      if (filter.method) query['method'] = filter.method;
      if (filter.page != null) query['page'] = filter.page;
      if (filter.pageSize != null) query['pageSize'] = filter.pageSize;
      const raw = await staffRequest('get', '/api/v1/payments', { query });
      return PaymentsListResponseSchema.parse(raw).data;
    },
    enabled: can(role, 'view', 'payments'), // OWNER_ONLY — reception makes zero API calls
    staleTime: 30_000,
  });
}

// ---------------------------------------------------------------------------
// Mutations
// ---------------------------------------------------------------------------

/**
 * Refund a payment by payment id (owner-only, REFUND + FINANCE permission).
 * POST /api/v1/payments/{payment_id}/refund
 * Returns new refund Payment row (ResponseEnvelope[PaymentResponse] — 201 Created).
 * Invalidates paymentsKeys.lists() — covers both cashbox (usePaymentsLedger)
 * and the finance online-payments table (broad invalidation, per 112-CONTEXT).
 *
 * NOTE: ApiError is NOT swallowed here — callers (modals) map err.code to toasts.
 * May throw ApiError with code: over_refund | already_refunded | cannot_refund_refund
 */
export function useRefundPayment() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: async ({
      paymentId,
      amountKopecks,
      reason,
    }: {
      paymentId: string;
      amountKopecks: number;
      reason: string;
    }) => {
      const raw = await staffRequest('post', '/api/v1/payments/{payment_id}/refund', {
        params: { payment_id: paymentId },
        body: { amountKopecks, reason },
      });
      // Backend returns ResponseEnvelope[PaymentResponse] with 201 Created.
      // Parse the inner data item using the existing PaymentSchema.
      return PaymentsListResponseSchema.shape.data.shape.items.element.parse(
        (raw as { data: unknown }).data,
      );
    },
    onSettled: () => {
      void qc.invalidateQueries({ queryKey: paymentsKeys.lists() });
    },
  });
}

// ---------------------------------------------------------------------------
// Re-export for page/tab layers (ESLint import-boundary)
// ---------------------------------------------------------------------------

export { ApiError };

/**
 * Client PWA query hooks (Phase 71 D-71-06).
 *
 * Per-feature key factory + typed query/mutation hooks over clientFetcher.ts.
 * Mirrors admin-web query conventions: staleTime 30_000, refetchOnWindowFocus: false
 * (set globally on queryClient), onSettled invalidation for mutations.
 *
 * All hooks call through clientRequest from clientFetcher.ts (Phase 69 typed transport).
 * The <QueryClientProvider> root wrap is performed in Plan 71-05 Task 2 — NOT here.
 */
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { ApiError } from '@clubcore/api-client'
import { clientRequest } from './clientFetcher'

// ---------------------------------------------------------------------------
// Re-export ApiError so consumers can do `instanceof ApiError` checks
// ---------------------------------------------------------------------------
export { ApiError }

// ---------------------------------------------------------------------------
// Per-feature key factory (D-71-06 mirror admin-web convention)
// ---------------------------------------------------------------------------
export const clientPortalKeys = {
  all: ['client-portal'] as const,
  home: () => [...clientPortalKeys.all, 'home'] as const,
  membership: () => [...clientPortalKeys.all, 'membership'] as const,
  plans: () => [...clientPortalKeys.all, 'plans'] as const,
  ptPackages: () => [...clientPortalKeys.all, 'pt-packages'] as const,
  bookings: () => [...clientPortalKeys.all, 'bookings'] as const,
  visitHistory: (page: number) => [...clientPortalKeys.all, 'visits', page] as const,
  ptHistory: (page: number) => [...clientPortalKeys.all, 'pt-sessions', page] as const,
  paymentHistory: (page: number) => [...clientPortalKeys.all, 'payments', page] as const,
  paymentStatus: (id: string) => [...clientPortalKeys.all, 'payment-status', id] as const,
} as const

// ---------------------------------------------------------------------------
// Type helpers
// ---------------------------------------------------------------------------

interface PaginatedResult<T> {
  items: T[]
  total: number
  page: number
  pageSize: number
}

interface HomeData {
  membership: unknown
  next_booking: unknown
  expiring_soon: boolean
}

interface PaymentStatusData {
  id: string
  status: 'pending' | 'succeeded' | 'canceled'
}

interface CheckoutResult {
  onlinePaymentId: string
  confirmationUrl: string
}

// ---------------------------------------------------------------------------
// Read hooks
// ---------------------------------------------------------------------------

/** GET /api/v1/client/home — home screen data (membership + next booking) */
export function useClientHome() {
  return useQuery({
    queryKey: clientPortalKeys.home(),
    queryFn: async () => {
      const res = await clientRequest('get', '/api/v1/client/home')
      return (res as { data: HomeData }).data
    },
    staleTime: 30_000,
  })
}

/** GET /api/v1/client/plans — membership plans catalog */
export function useClientPlans() {
  return useQuery({
    queryKey: clientPortalKeys.plans(),
    queryFn: async () => {
      const res = await clientRequest('get', '/api/v1/client/plans')
      return (res as { data: unknown[] }).data
    },
    staleTime: 30_000,
  })
}

/** GET /api/v1/client/pt-packages — PT-package plans catalog */
export function useClientPtPackages() {
  return useQuery({
    queryKey: clientPortalKeys.ptPackages(),
    queryFn: async () => {
      const res = await clientRequest('get', '/api/v1/client/pt-packages')
      return (res as { data: unknown[] }).data
    },
    staleTime: 30_000,
  })
}

// ---------------------------------------------------------------------------
// History hooks (Phase-69 endpoints — ProfileScreen tabs)
// ---------------------------------------------------------------------------

/** GET /api/v1/client/history/visits — visit history tab (CHIST-01) */
export function useClientVisitHistory(page = 1) {
  return useQuery({
    queryKey: clientPortalKeys.visitHistory(page),
    queryFn: async () => {
      const res = await clientRequest('get', '/api/v1/client/history/visits', {
        query: { page },
      })
      return (res as { data: PaginatedResult<unknown> }).data
    },
    staleTime: 30_000,
  })
}

/** GET /api/v1/client/history/pt-sessions — PT training history tab (CHIST-02) */
export function useClientPtHistory(page = 1) {
  return useQuery({
    queryKey: clientPortalKeys.ptHistory(page),
    queryFn: async () => {
      const res = await clientRequest('get', '/api/v1/client/history/pt-sessions', {
        query: { page },
      })
      return (res as { data: PaginatedResult<unknown> }).data
    },
    staleTime: 30_000,
  })
}

/** GET /api/v1/client/history/payments — payment history tab (CHIST-03) */
export function useClientPaymentHistory(page = 1) {
  return useQuery({
    queryKey: clientPortalKeys.paymentHistory(page),
    queryFn: async () => {
      const res = await clientRequest('get', '/api/v1/client/history/payments', {
        query: { page },
      })
      return (res as { data: PaginatedResult<unknown> }).data
    },
    staleTime: 30_000,
  })
}

// ---------------------------------------------------------------------------
// Payment status polling hook (D-71-05 return-route polling)
// ---------------------------------------------------------------------------

/**
 * GET /api/v1/client/payments/{payment_id}/status — coarse anti-oracle status.
 *
 * Polls every 3 s while status is 'pending'; stops when settled.
 * staleTime: 0 so the polling screen always re-fetches from the network.
 * enabled guard: only fires when enabled=true and paymentId is non-empty.
 */
export function useClientPaymentStatus(paymentId: string | null, enabled: boolean) {
  return useQuery({
    queryKey: clientPortalKeys.paymentStatus(paymentId ?? ''),
    queryFn: async () => {
      const res = await clientRequest(
        'get',
        '/api/v1/client/payments/{payment_id}/status',
        { params: { payment_id: paymentId! } },
      )
      return (res as { data: PaymentStatusData }).data
    },
    enabled: enabled && !!paymentId,
    refetchInterval: (query) => (query.state.data?.status === 'pending' ? 3_000 : false),
    staleTime: 0,
  })
}

// ---------------------------------------------------------------------------
// Checkout mutation hooks (Plan-02 client checkout endpoints)
// ---------------------------------------------------------------------------

/**
 * POST /api/v1/client/checkout/memberships/{plan_id}
 * Server-derived idempotency key (D-71-04 — per-day sha256, no client header needed).
 * onSettled invalidates clientPortalKeys.membership() so home + profile refresh.
 */
export function useClientCheckoutMembership() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: async ({ planId }: { planId: string }) => {
      const res = await clientRequest(
        'post',
        '/api/v1/client/checkout/memberships/{plan_id}',
        {
          params: { plan_id: planId },
          body: {},
        },
      )
      return (res as { data: CheckoutResult }).data
    },
    onSettled: () => {
      void qc.invalidateQueries({ queryKey: clientPortalKeys.membership() })
    },
  })
}

/**
 * POST /api/v1/client/checkout/pt-packages/{plan_id}
 * Client-supplied Idempotency-Key header (D-71-04 — PT allows same-day repurchase).
 * PWA generates a UUID per checkout intent and passes it here; reuses on retry.
 * onSettled invalidates clientPortalKeys.membership() so membership cache refreshes.
 */
export function useClientCheckoutPtPackage() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: async ({ planId, idempotencyKey }: { planId: string; idempotencyKey: string }) => {
      const res = await clientRequest(
        'post',
        '/api/v1/client/checkout/pt-packages/{plan_id}',
        {
          params: { plan_id: planId },
          body: {},
          headers: { 'Idempotency-Key': idempotencyKey },
        },
      )
      return (res as { data: CheckoutResult }).data
    },
    onSettled: () => {
      void qc.invalidateQueries({ queryKey: clientPortalKeys.membership() })
    },
  })
}

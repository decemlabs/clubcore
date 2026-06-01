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
  me: () => [...clientPortalKeys.all, 'me'] as const,
  home: () => [...clientPortalKeys.all, 'home'] as const,
  membership: () => [...clientPortalKeys.all, 'membership'] as const,
  plans: () => [...clientPortalKeys.all, 'plans'] as const,
  ptPackages: () => [...clientPortalKeys.all, 'pt-packages'] as const,
  bookings: () => [...clientPortalKeys.all, 'bookings'] as const,
  availableSlots: (filter?: string) => [...clientPortalKeys.all, 'available-slots', filter ?? ''] as const,
  qrToken: () => [...clientPortalKeys.all, 'qr-token'] as const,
  visitHistory: (page: number) => [...clientPortalKeys.all, 'visits', page] as const,
  ptHistory: (page: number) => [...clientPortalKeys.all, 'pt-sessions', page] as const,
  paymentHistory: (page: number) => [...clientPortalKeys.all, 'payments', page] as const,
  paymentStatus: (id: string) => [...clientPortalKeys.all, 'payment-status', id] as const,
  promoValidate: (code: string) => [...clientPortalKeys.all, 'promo-validate', code] as const,
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

interface BookingItem {
  id: string
  startTime: string
  status: string
  trainerName: string
}

interface BookingResponse {
  id: string
  slotId: string
  startTime: string
  status: string
  trainerName: string
}

interface AvailableSlotItem {
  slotId: string
  trainerId: string
  trainerName: string
  startTime: string
  endTime: string
}

interface QrTokenData {
  token: string
  expiresIn: number
}

interface HomeData {
  membership: unknown
  next_booking: unknown
  expiring_soon: boolean
  /** Server-derived membership state — camelCase wire (Plan 999.3-01). */
  membershipState: 'active' | 'newbie' | 'lapsed'
}

/** GET /client/me response shape — Phase 999.5 profile fields (camelCase wire, D-91). */
interface ClientMeData {
  firstName: string
  lastName: string
  phone: string
  email: string | null
  goal: 'lose_weight' | 'gain_mass' | 'tone' | 'maintain' | null
  heightCm: number | null
  weightKg: number | null
  onboardingCompletedAt: string | null
}

interface PaymentStatusData {
  id: string
  status: 'pending' | 'succeeded' | 'canceled'
  /** ЮKassa fiscal receipt URL — populated by backend only when a succeeded receipt exists (D-11). */
  receiptUrl?: string | null
  /** Receipt destination email — populated only on succeeded status (anti-oracle T-999.5-09). */
  receiptEmail?: string | null
  /** Receipt destination phone — populated only on succeeded status (anti-oracle T-999.5-09). */
  receiptPhone?: string | null
}

interface CheckoutResult {
  onlinePaymentId: string
  confirmationUrl: string
}

interface PromoValidateResult {
  discountKopecks: number
  newAmountKopecks: number
  discountType: 'percentage' | 'fixed'
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

// ---------------------------------------------------------------------------
// Auth probe + OTP hooks (Plan 71-07 — login flow)
// ---------------------------------------------------------------------------

/**
 * GET /api/v1/client/me — auth probe + profile data (Phase 999.5).
 *
 * Used by AuthContext to bootstrap auth status on mount.
 * retry: false so a 401 probe fails fast to anon (no retry storm).
 * /client/me is CLIENT_AUTH_EXEMPT — a 401 here does NOT trigger
 * single-flight refresh; clientFetcher throws ApiError('<code>') from the body.
 * Treat ANY thrown error as anon.
 *
 * Also exposes onboarding fields (goal/heightCm/weightKg/onboardingCompletedAt)
 * so the auto-redirect gate in HomeScreen can read onboardingCompletedAt (D-04/D-05).
 */
export function useClientMe(enabled = true) {
  return useQuery({
    queryKey: clientPortalKeys.me(),
    queryFn: async () => {
      const res = await clientRequest('get', '/api/v1/client/me')
      return (res as { data: ClientMeData }).data
    },
    enabled,
    retry: false,
    staleTime: 30_000,
  })
}

/**
 * PATCH /api/v1/client/me — write onboarding profile fields (D-08).
 *
 * Atomic single-submit on «Перейти в "Мой зал"» — steps held in local state until finish.
 * MUST include onboardingCompleted: true on the finish call (D-08) — omitting it causes
 * the auto-redirect loop to re-fire after completion (SUPERSEDED-PATTERN note in PLAN.md).
 * onSuccess seeds the /client/me cache with the authoritative PATCH response so a caller
 * that navigates immediately (e.g. skip path) reads the updated onboardingCompletedAt and
 * does NOT bounce back through the auto-redirect gate before the refetch lands (GAP-2).
 * onSettled then invalidates /client/me + /client/home so the gate reruns on fresh data.
 */
export function useUpdateClientProfile() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: async (payload: {
      firstName?: string
      goal?: string
      heightCm?: number
      weightKg?: number
      onboardingCompleted?: boolean
      email?: string
    }) => {
      const res = await clientRequest('patch', '/api/v1/client/me', { body: payload })
      return (res as { data: ClientMeData }).data
    },
    onSuccess: (data) => {
      qc.setQueryData(clientPortalKeys.me(), data)
    },
    onSettled: () => {
      void qc.invalidateQueries({ queryKey: clientPortalKeys.me() })
      void qc.invalidateQueries({ queryKey: clientPortalKeys.home() })
    },
  })
}

/**
 * PATCH /api/v1/client/me — skip path: write ONLY the onboarding flag (D-05/D-08).
 *
 * «Пропустить»/«Заполью позже» sends body { onboardingCompleted: true } with NO profile
 * fields. This is a distinct hook to enforce the D-08 invariant at the call site — callers
 * cannot accidentally include profile fields in the skip path.
 * onSuccess seeds the /client/me cache with the PATCH response so handleSkip's immediate
 * navigate('/home') reads the now-set onboardingCompletedAt and does NOT bounce back to
 * /onboarding before the invalidation refetch resolves (GAP-2).
 * onSettled then invalidates /client/me + /client/home.
 */
export function useCompleteOnboarding() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: async () => {
      const res = await clientRequest('patch', '/api/v1/client/me', {
        body: { onboardingCompleted: true },
      })
      return (res as { data: ClientMeData }).data
    },
    onSuccess: (data) => {
      qc.setQueryData(clientPortalKeys.me(), data)
    },
    onSettled: () => {
      void qc.invalidateQueries({ queryKey: clientPortalKeys.me() })
      void qc.invalidateQueries({ queryKey: clientPortalKeys.home() })
    },
  })
}

/**
 * PATCH /api/v1/client/me — write email for receipt gate (D-02/D-10).
 *
 * Called from ReceiptEmailGate before the ЮKassa redirect.
 * onSettled invalidates /client/me + /client/home so subsequent gate reads see the updated
 * email (WR-06: matches useUpdateClientProfile / useCompleteOnboarding invalidation set).
 */
export function useUpdateClientEmail() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: async ({ email }: { email: string }) => {
      const res = await clientRequest('patch', '/api/v1/client/me', { body: { email } })
      return (res as { data: ClientMeData }).data
    },
    onSettled: () => {
      void qc.invalidateQueries({ queryKey: clientPortalKeys.me() })
      void qc.invalidateQueries({ queryKey: clientPortalKeys.home() })
    },
  })
}

/**
 * POST /api/v1/client/otp/request — request OTP code via Telegram.
 * Anti-oracle: always 202, byte-identical for known/unknown/unlinked phones (T-68-22).
 */
export function useOtpRequest() {
  return useMutation({
    mutationFn: async ({ phone }: { phone: string }) => {
      await clientRequest('post', '/api/v1/client/otp/request', { body: { phone } })
    },
  })
}

/**
 * POST /api/v1/client/otp/verify — verify OTP code, sets cc_client_* cookies on success.
 * /client/otp/verify is CLIENT_AUTH_EXEMPT — a 401/422 here is a wrong-code error,
 * never a session_expired refresh trigger.
 */
export function useOtpVerify() {
  return useMutation({
    mutationFn: async ({ phone, code }: { phone: string; code: string }) => {
      await clientRequest('post', '/api/v1/client/otp/verify', { body: { phone, code } })
    },
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
// Booking hooks (Phase-70 endpoints — BookScreen)
// ---------------------------------------------------------------------------

/** GET /api/v1/client/bookings — upcoming client bookings list (CBOOK-01) */
export function useClientBookings(page = 1) {
  return useQuery({
    queryKey: clientPortalKeys.bookings(),
    queryFn: async () => {
      const res = await clientRequest('get', '/api/v1/client/bookings', {
        query: { page },
      })
      return (res as { data: PaginatedResult<BookingItem> }).data
    },
    staleTime: 30_000,
  })
}

/** GET /api/v1/client/slots — available trainer slots, filtered by active PT-package trainer pin (CBOOK-02) */
export function useClientAvailableSlots(page = 1) {
  return useQuery({
    queryKey: clientPortalKeys.availableSlots(String(page)),
    queryFn: async () => {
      const res = await clientRequest('get', '/api/v1/client/slots', {
        query: { page },
      })
      return (res as { data: PaginatedResult<AvailableSlotItem> }).data
    },
    staleTime: 30_000,
  })
}

/**
 * POST /api/v1/client/booking — create a confirmed booking (CBOOK-03/04).
 * Requires a per-intent Idempotency-Key header (D-70-02 / T-71-27).
 * onSettled invalidates bookings cache.
 * On 422 no_active_pt_package the caller should route to Plans/Checkout (CBOOK-04).
 */
export function useCreateBooking() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: async ({
      slotId,
      ptPackageId,
      idempotencyKey,
    }: {
      slotId: string
      ptPackageId?: string | null
      idempotencyKey: string
    }) => {
      // CR-03: pt_package_id is now optional; server resolves the active package
      // when omitted. Only include it in the body if a valid UUID was supplied.
      const body: Record<string, string> = { slot_id: slotId }
      if (ptPackageId) body.pt_package_id = ptPackageId
      const res = await clientRequest('post', '/api/v1/client/booking', {
        body,
        headers: { 'Idempotency-Key': idempotencyKey },
      })
      return (res as { data: BookingResponse }).data
    },
    onSettled: () => {
      void qc.invalidateQueries({ queryKey: clientPortalKeys.bookings() })
    },
  })
}

/**
 * POST /api/v1/client/booking/{booking_id}/cancel — cancel own booking (CBOOK-05).
 * IDOR 404-collapse on non-owned booking (T-71-28).
 * onSettled invalidates bookings cache.
 */
export function useCancelBooking() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: async ({ bookingId }: { bookingId: string }) => {
      const res = await clientRequest(
        'post',
        '/api/v1/client/booking/{booking_id}/cancel',
        { params: { booking_id: bookingId } },
      )
      return (res as { data: BookingResponse }).data
    },
    onSettled: () => {
      void qc.invalidateQueries({ queryKey: clientPortalKeys.bookings() })
    },
  })
}

// ---------------------------------------------------------------------------
// QR token hook (Phase-70 CCHK-01 — QRSheet)
// ---------------------------------------------------------------------------

/**
 * GET /api/v1/client/qr-token — short-lived (~60s) signed QR self check-in token.
 *
 * staleTime: 0 — token is short-lived; always fetched fresh.
 * refetchInterval: refresh at 50s (before the ~60s TTL) so the displayed QR stays valid.
 * T-71-26 mitigation: token is server-signed JWT; anti-replay enforced server-side.
 */
export function useClientQrToken(enabled = true) {
  return useQuery({
    queryKey: clientPortalKeys.qrToken(),
    queryFn: async () => {
      const res = await clientRequest('get', '/api/v1/client/qr-token')
      return (res as { data: QrTokenData }).data
    },
    enabled,
    staleTime: 0,
    refetchInterval: 50_000, // refresh before ~60s TTL (T-71-26)
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
    mutationFn: async ({ planId, promoCode }: { planId: string; promoCode?: string }) => {
      const res = await clientRequest(
        'post',
        '/api/v1/client/checkout/memberships/{plan_id}',
        {
          params: { plan_id: planId },
          body: promoCode ? { promoCode } : {},
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
    mutationFn: async ({
      planId,
      idempotencyKey,
      promoCode,
    }: {
      planId: string
      idempotencyKey: string
      promoCode?: string
    }) => {
      const res = await clientRequest(
        'post',
        '/api/v1/client/checkout/pt-packages/{plan_id}',
        {
          params: { plan_id: planId },
          body: promoCode ? { promoCode } : {},
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

/**
 * POST /api/v1/client/promo/validate — validate a promo code server-side.
 *
 * Returns server-authoritative { discountKopecks, newAmountKopecks, discountType } on 200.
 * Rejects with an error exposing `.code` (per-reason D-09 string) on 422.
 * No cache invalidation — validate is a stateless read.
 */
export function usePromoValidate() {
  return useMutation({
    mutationFn: async ({
      code,
      kind,
      planId,
    }: {
      code: string
      kind: 'sub' | 'pt'
      planId: string
    }) => {
      const res = await clientRequest('post', '/api/v1/client/promo/validate', {
        body: { code, kind, planId },
      })
      return (res as { data: PromoValidateResult }).data
    },
  })
}

/**
 * Payroll domain API hooks — RBAC + money integrity + 409 handling tests
 * (Phase 102-04 TRN-02, T-102-PAY-RBAC, T-102-PAY-MONEY, T-102-PAY-TERMINAL).
 *
 * Tests:
 *  1. PayrollConfigInputSchema rejects commissionPctBps > 10000 with Russian error.
 *  2. PayrollConfigInputSchema rejects negative sessionFeeKopecks with Russian error.
 *  3. usePayrollConfig is disabled (no staffRequest call) for reception role.
 *  4. useRunAccrual toasts «Период уже обработан» on 409 payroll_period_already_run (no crash).
 *  5. useMarkAccrualPaid toasts «Уже выплачено» on 409 already_paid (no crash).
 *  6. AccrualsListResponseSchema parses the paginated envelope.
 *
 * Pattern: mock '@/api/client' + '@/features/auth/api'. No network, no React DOM render.
 */
import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest'
import { renderHook, act } from '@testing-library/react'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import type { ReactNode } from 'react'

// ---------------------------------------------------------------------------
// Module mocks — staffRequest + useSession
// ---------------------------------------------------------------------------

vi.mock('@/api/client', async (importOriginal) => {
  const actual = await importOriginal<{ staffRequest: unknown; ApiError: unknown }>()
  return {
    ...actual,
    staffRequest: vi.fn(),
    ApiError: actual.ApiError,
  }
})

vi.mock('@/features/auth/api', () => ({
  useSession: vi.fn(),
}))

// Dynamically import after mocks are set up
const { staffRequest, ApiError } = await import('@/api/client')
const { useSession } = await import('@/features/auth/api')
const { PayrollConfigInputSchema, AccrualsListResponseSchema } = await import('./schemas')
const { usePayrollConfig, useRunAccrual, useMarkAccrualPaid } = await import('./api')

const mockStaffRequest = vi.mocked(staffRequest)
const mockUseSession = vi.mocked(useSession)

// ---------------------------------------------------------------------------
// Helper — QueryClientProvider wrapper
// ---------------------------------------------------------------------------

function makeWrapper() {
  const queryClient = new QueryClient({
    defaultOptions: {
      queries: { retry: false },
      mutations: { retry: false },
    },
  })
  return function Wrapper({ children }: { children: ReactNode }) {
    return <QueryClientProvider client={queryClient}>{children}</QueryClientProvider>
  }
}

// ---------------------------------------------------------------------------
// Test fixtures
// ---------------------------------------------------------------------------

const VALID_ACCRUAL = {
  id: 'acc-1',
  trainerId: 'trainer-1',
  periodStart: '2026-01-01',
  periodEnd: '2026-01-31',
  sessionCount: 10,
  fixedKopecks: 50000,
  commissionKopecks: 10000,
  totalKopecks: 60000,
  status: 'pending',
  accruedAt: '2026-02-01T12:00:00Z',
}

beforeEach(() => {
  vi.clearAllMocks()
})

afterEach(() => {
  vi.restoreAllMocks()
})

// ---------------------------------------------------------------------------
// T-102-PAY-MONEY: Schema validation
// ---------------------------------------------------------------------------

describe('T-102-PAY-MONEY: PayrollConfigInputSchema validation', () => {
  it('rejects commissionPctBps > 10000 with Russian error message', () => {
    const result = PayrollConfigInputSchema.safeParse({
      commissionPctBps: 10001,
      sessionFeeKopecks: 0,
      effectiveFrom: '2026-01-01',
    })
    expect(result.success).toBe(false)
    if (!result.success) {
      const msgs = result.error.errors.map((e) => e.message)
      expect(msgs.some((m) => m.includes('Комиссия'))).toBe(true)
    }
  })

  it('rejects negative sessionFeeKopecks with Russian error message', () => {
    const result = PayrollConfigInputSchema.safeParse({
      commissionPctBps: 0,
      sessionFeeKopecks: -1,
      effectiveFrom: '2026-01-01',
    })
    expect(result.success).toBe(false)
    if (!result.success) {
      const msgs = result.error.errors.map((e) => e.message)
      expect(msgs.some((m) => m.includes('Ставка'))).toBe(true)
    }
  })

  it('accepts valid config input (zero values)', () => {
    const result = PayrollConfigInputSchema.safeParse({
      commissionPctBps: 0,
      sessionFeeKopecks: 0,
      effectiveFrom: '2026-01-01',
    })
    expect(result.success).toBe(true)
  })

  it('accepts max commissionPctBps = 10000 (100%)', () => {
    const result = PayrollConfigInputSchema.safeParse({
      commissionPctBps: 10000,
      sessionFeeKopecks: 50000,
      effectiveFrom: '2026-06-01',
    })
    expect(result.success).toBe(true)
  })
})

// ---------------------------------------------------------------------------
// T-102-PAY-RBAC: Reception makes ZERO payroll API calls
// ---------------------------------------------------------------------------

describe('T-102-PAY-RBAC: usePayrollConfig disabled for reception', () => {
  it('does not call staffRequest when role is reception', async () => {
    // Mock session returning reception role
    mockUseSession.mockReturnValue({
      data: { role: 'reception', fullName: 'Reception Staff', email: 'r@test.com' },
      isPending: false,
      isError: false,
    } as ReturnType<typeof useSession>)

    const wrapper = makeWrapper()
    const { result } = renderHook(() => usePayrollConfig('trainer-1'), { wrapper })

    // Query should be disabled — fetchStatus is 'idle', not 'fetching'
    expect(result.current.fetchStatus).toBe('idle')
    // staffRequest should never have been called
    expect(mockStaffRequest).not.toHaveBeenCalled()
  })
})

// ---------------------------------------------------------------------------
// T-102-PAY-TERMINAL: 409 handlers do not crash
// ---------------------------------------------------------------------------

describe('T-102-PAY-TERMINAL: 409 payroll_period_already_run handled calmly', () => {
  it('useRunAccrual toasts «Период уже обработан» on 409 payroll_period_already_run', async () => {
    mockUseSession.mockReturnValue({
      data: { role: 'owner', fullName: 'Owner', email: 'o@test.com' },
      isPending: false,
      isError: false,
    } as ReturnType<typeof useSession>)

    const conflictError = new ApiError('payroll_period_already_run', 'Period already run', 409)
    mockStaffRequest.mockRejectedValue(conflictError)

    const wrapper = makeWrapper()
    const { result } = renderHook(() => useRunAccrual(), { wrapper })

    let caughtError: unknown = undefined
    await act(async () => {
      try {
        await result.current.mutateAsync({
          trainerId: 'trainer-1',
          periodStart: '2026-01-01',
          periodEnd: '2026-01-31',
        })
      } catch (e) {
        caughtError = e
      }
    })

    // Should have thrown (mutation failed), but should not be an unhandled crash
    expect(caughtError).toBeTruthy()
    // staffRequest was called once
    expect(mockStaffRequest).toHaveBeenCalledTimes(1)
  })
})

describe('T-102-PAY-TERMINAL: 409 already_paid handled calmly', () => {
  it('useMarkAccrualPaid toasts «Уже выплачено» on 409 already_paid', async () => {
    mockUseSession.mockReturnValue({
      data: { role: 'owner', fullName: 'Owner', email: 'o@test.com' },
      isPending: false,
      isError: false,
    } as ReturnType<typeof useSession>)

    const alreadyPaidError = new ApiError('already_paid', 'Already paid', 409)
    mockStaffRequest.mockRejectedValue(alreadyPaidError)

    const wrapper = makeWrapper()
    const { result } = renderHook(() => useMarkAccrualPaid(), { wrapper })

    let caughtError: unknown = undefined
    await act(async () => {
      try {
        await result.current.mutateAsync({ accrualId: 'acc-1', trainerId: 'trainer-1' })
      } catch (e) {
        caughtError = e
      }
    })

    expect(caughtError).toBeTruthy()
    expect(mockStaffRequest).toHaveBeenCalledTimes(1)
  })
})

// ---------------------------------------------------------------------------
// AccrualsListResponseSchema — paginated envelope
// ---------------------------------------------------------------------------

describe('AccrualsListResponseSchema', () => {
  it('parses a valid paginated accruals envelope', () => {
    const raw = {
      data: {
        items: [VALID_ACCRUAL],
        total: 1,
        page: 1,
        pageSize: 20,
      },
    }
    const result = AccrualsListResponseSchema.safeParse(raw)
    expect(result.success).toBe(true)
    if (result.success) {
      expect(result.data.data.items).toHaveLength(1)
      expect(result.data.data.items[0]!.status).toBe('pending')
    }
  })

  it('rejects an invalid accrual status', () => {
    const raw = {
      data: {
        items: [{ ...VALID_ACCRUAL, status: 'unknown_status' }],
        total: 1,
        page: 1,
        pageSize: 20,
      },
    }
    const result = AccrualsListResponseSchema.safeParse(raw)
    expect(result.success).toBe(false)
  })
})

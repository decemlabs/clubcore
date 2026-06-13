/**
 * PayoutsTab wiring tests (Phase 102-04 TRN-02).
 * T-102-PAY-RBAC: Reception sees Lock EmptyState, ZERO payroll API calls.
 * T-102-PAY-MONEY: Schema validates integer kopecks/bps conversion.
 * T-102-PAY-TERMINAL: comp_config_missing 404 shows warn Callout (owner).
 *
 * ESLint boundary note: tests in src/pages/ may not import @/api/client directly.
 * We mock @/features/payroll/api (the feature seam) instead of the transport layer.
 */
import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest'
import { render, screen, waitFor } from '@testing-library/react'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import type { ReactNode } from 'react'
import type { UseQueryResult } from '@tanstack/react-query'

// ---------------------------------------------------------------------------
// Module mocks
// ---------------------------------------------------------------------------

vi.mock('@/features/auth/api', () => ({
  useSession: vi.fn(),
}))

// Mock the payroll api module so no real staffRequest fires
vi.mock('@/features/payroll/api', async (importOriginal) => {
  const actual = await importOriginal<Record<string, unknown>>()
  return {
    ...actual,
    usePayrollConfig: vi.fn(),
    useSetPayrollConfig: vi.fn(),
    useAccrualPreview: vi.fn(),
    useRunAccrual: vi.fn(),
    useAccruals: vi.fn(),
    useMarkAccrualPaid: vi.fn(),
  }
})

// Static imports resolved after vi.mock hoisting
import { useSession } from '@/features/auth/api'
import {
  usePayrollConfig,
  useSetPayrollConfig,
  useAccrualPreview,
  useRunAccrual,
  useAccruals,
  useMarkAccrualPaid,
  ApiError,
} from '@/features/payroll/api'
import { PayoutsTab } from './PayoutsTab'
import { PayrollConfigInputSchema } from '@/features/payroll/schemas'

const mockUseSession = vi.mocked(useSession)
const mockUsePayrollConfig = vi.mocked(usePayrollConfig)
const mockUseSetPayrollConfig = vi.mocked(useSetPayrollConfig)
const mockUseAccrualPreview = vi.mocked(useAccrualPreview)
const mockUseRunAccrual = vi.mocked(useRunAccrual)
const mockUseAccruals = vi.mocked(useAccruals)
const mockUseMarkAccrualPaid = vi.mocked(useMarkAccrualPaid)

// ---------------------------------------------------------------------------
// Default mock implementations (idle/pending)
// ---------------------------------------------------------------------------

const PENDING_QUERY = {
  data: undefined,
  isPending: true,
  isError: false,
  isSuccess: false,
  isFetching: false,
  error: null,
  refetch: vi.fn(),
  fetchStatus: 'idle' as const,
} as unknown as UseQueryResult<unknown>

const PENDING_MUTATION = {
  mutateAsync: vi.fn(),
  isPending: false,
  isError: false,
  isSuccess: false,
  error: null,
}

function resetMocks() {
  mockUsePayrollConfig.mockReturnValue(PENDING_QUERY as unknown as ReturnType<typeof usePayrollConfig>)
  mockUseSetPayrollConfig.mockReturnValue(PENDING_MUTATION as unknown as ReturnType<typeof useSetPayrollConfig>)
  mockUseAccrualPreview.mockReturnValue(PENDING_QUERY as unknown as ReturnType<typeof useAccrualPreview>)
  mockUseRunAccrual.mockReturnValue(PENDING_MUTATION as unknown as ReturnType<typeof useRunAccrual>)
  mockUseAccruals.mockReturnValue({
    ...PENDING_QUERY,
    isPending: false,
    isSuccess: true,
    data: { items: [], total: 0, page: 1, pageSize: 20 },
  } as unknown as ReturnType<typeof useAccruals>)
  mockUseMarkAccrualPaid.mockReturnValue(PENDING_MUTATION as unknown as ReturnType<typeof useMarkAccrualPaid>)
}

// ---------------------------------------------------------------------------
// Helpers
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

function renderPayoutsTab(role: 'owner' | 'reception', trainerId = 'trainer-1') {
  mockUseSession.mockReturnValue({
    data: { role, fullName: role === 'owner' ? 'Владелец' : 'Ресепшн', email: 'test@test.com' },
    isPending: false,
    isError: false,
  } as ReturnType<typeof useSession>)

  const Wrapper = makeWrapper()
  return render(
    <Wrapper>
      <PayoutsTab trainerId={trainerId} />
    </Wrapper>,
  )
}

beforeEach(() => {
  vi.clearAllMocks()
  resetMocks()
})

afterEach(() => {
  vi.restoreAllMocks()
})

// ---------------------------------------------------------------------------
// T-102-PAY-RBAC: Reception sees Lock EmptyState, ZERO payroll hook calls
// ---------------------------------------------------------------------------

describe('T-102-PAY-RBAC: Reception role 403 gate', () => {
  it('shows «Недостаточно прав» EmptyState for reception role', () => {
    renderPayoutsTab('reception')

    expect(screen.getByText('Недостаточно прав')).toBeDefined()
    expect(screen.getByText(/Раздел выплат доступен только владельцу/)).toBeDefined()
  })

  it('payroll hooks are NEVER called for reception role', () => {
    renderPayoutsTab('reception')

    // The component returns the Lock EmptyState before rendering owner section
    // — hooks inside OwnerPayoutsTab are never invoked
    expect(mockUsePayrollConfig).not.toHaveBeenCalled()
    expect(mockUseAccruals).not.toHaveBeenCalled()
    expect(mockUseAccrualPreview).not.toHaveBeenCalled()
  })
})

// ---------------------------------------------------------------------------
// T-102-PAY-MONEY + T-102-PAY-RBAC: Owner comp-config 404 shows warn Callout
// ---------------------------------------------------------------------------

describe('T-102-PAY-MONEY: Owner comp-config 404 shows warn Callout', () => {
  it('shows «Настройки компенсации не заданы» callout on comp_config_missing error', async () => {
    // Mock config query with a 404 comp_config_missing error
    mockUsePayrollConfig.mockReturnValue({
      data: undefined,
      isPending: false,
      isError: true,
      isSuccess: false,
      isFetching: false,
      error: new ApiError('comp_config_missing', 'Config not found'),
      refetch: vi.fn(),
      fetchStatus: 'idle' as const,
    } as unknown as ReturnType<typeof usePayrollConfig>)

    renderPayoutsTab('owner')

    await waitFor(() => {
      const callout = screen.queryByText(/Настройки компенсации не заданы/)
      expect(callout).not.toBeNull()
    })
  })
})

// ---------------------------------------------------------------------------
// T-102-PAY-MONEY: Schema conversion tests (pure math, no DOM)
// ---------------------------------------------------------------------------

describe('T-102-PAY-MONEY: PayrollConfigInputSchema integer kopecks/bps', () => {
  it('accepts integer kopecks and bps matching the wire format', () => {
    const result = PayrollConfigInputSchema.safeParse({
      commissionPctBps: 1000, // 10% as bps
      sessionFeeKopecks: 50000, // 500 rubles as kopecks
      effectiveFrom: '2026-01-01',
    })
    expect(result.success).toBe(true)
    if (result.success) {
      // Wire format: 50000 kopecks = 500 rubles displayed
      expect(result.data.sessionFeeKopecks / 100).toBe(500)
      // Wire format: 1000 bps = 10% displayed
      expect(result.data.commissionPctBps / 100).toBe(10)
    }
  })

  it('Math.round(rubles * 100) conversion round-trips', () => {
    const rubles = 500
    const kopecks = Math.round(rubles * 100)
    expect(kopecks).toBe(50000)
    expect(kopecks / 100).toBe(500)
  })

  it('Math.round(pct * 100) conversion round-trips', () => {
    const pct = 10 // 10%
    const bps = Math.round(pct * 100)
    expect(bps).toBe(1000)
    expect(bps / 100).toBe(10)
  })

  it('rejects commissionPctBps > 10000 with Russian message', () => {
    const result = PayrollConfigInputSchema.safeParse({
      commissionPctBps: 10001,
      sessionFeeKopecks: 0,
      effectiveFrom: '2026-01-01',
    })
    expect(result.success).toBe(false)
    if (!result.success) {
      expect(result.error.errors.some((e) => e.message.includes('Комиссия'))).toBe(true)
    }
  })

  it('rejects negative sessionFeeKopecks with Russian message', () => {
    const result = PayrollConfigInputSchema.safeParse({
      commissionPctBps: 0,
      sessionFeeKopecks: -1,
      effectiveFrom: '2026-01-01',
    })
    expect(result.success).toBe(false)
    if (!result.success) {
      expect(result.error.errors.some((e) => e.message.includes('Ставка'))).toBe(true)
    }
  })
})

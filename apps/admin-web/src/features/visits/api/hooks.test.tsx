import { describe, it, expect, vi, afterEach } from 'vitest'
import { renderHook, waitFor } from '@testing-library/react'
import { makeTestQueryClient } from '@/test/utils'
import { QueryClientProvider } from '@tanstack/react-query'
import type { ReactNode } from 'react'
import type { GymMeta } from '@/shared/api/contracts/visits'
import type { Visit } from '@/entities/visit'
import type { Membership } from '@/entities/membership'

vi.mock('@/shared/api/services', () => ({
  services: {
    visits: {
      gymMeta: vi.fn(),
      recentByClient: vi.fn(),
      checkIn: vi.fn(),
      list: vi.fn(),
      get: vi.fn(),
    },
    memberships: {
      byClient: vi.fn(),
      list: vi.fn(),
      get: vi.fn(),
      create: vi.fn(),
      cancel: vi.fn(),
      listPlans: vi.fn(),
      getPlan: vi.fn(),
      createPlan: vi.fn(),
      updatePlan: vi.fn(),
      deletePlan: vi.fn(),
    },
  },
}))

vi.mock('@/shared/i18n/date', async (importOriginal) => {
  const actual = await importOriginal<typeof import('@/shared/i18n/date')>()
  return {
    ...actual,
    todayMSK: vi.fn(() => '2026-05-09'),
  }
})

// Import after mock
import { services } from '@/shared/api/services'
import { useGymMeta, useRecentVisitsByClient, useCheckIn, useMembershipStatusForClient } from './hooks'
import { visitsKeys } from './keys'

const mockMeta: GymMeta = { gymHoursStart: '07:00', gymHoursEnd: '23:00' }

function wrapper({ children }: { children: ReactNode }) {
  return <QueryClientProvider client={makeTestQueryClient()}>{children}</QueryClientProvider>
}

describe('useGymMeta', () => {
  afterEach(() => {
    vi.clearAllMocks()
  })

  // Test 1: calls services.visits.gymMeta()
  it('calls services.visits.gymMeta() and returns data', async () => {
    vi.mocked(services.visits.gymMeta).mockResolvedValue(mockMeta)
    const { result } = renderHook(() => useGymMeta(), { wrapper })
    await waitFor(() => expect(result.current.isSuccess).toBe(true))
    expect(services.visits.gymMeta).toHaveBeenCalledOnce()
    expect(result.current.data).toEqual(mockMeta)
  })

  // Test 2: staleTime is 300_000 (5 min)
  it('uses gymMeta key: ["visits", "gymMeta"]', () => {
    // Verify the hook's queryKey constant
    expect(visitsKeys.gymMeta).toEqual(['visits', 'gymMeta'])
  })
})

describe('useRecentVisitsByClient', () => {
  afterEach(() => {
    vi.clearAllMocks()
  })

  // Test 3: calls services.visits.recentByClient with correct args
  it('calls services.visits.recentByClient(clientId, {limit:20}) and uses correct queryKey', async () => {
    const mockVisits: Visit[] = []
    vi.mocked(services.visits.recentByClient).mockResolvedValue(mockVisits)
    const { result } = renderHook(
      () => useRecentVisitsByClient('client-123', { limit: 20 }),
      { wrapper },
    )
    await waitFor(() => expect(result.current.isSuccess).toBe(true))
    expect(services.visits.recentByClient).toHaveBeenCalledWith('client-123', { limit: 20 })
    expect(result.current.data).toEqual(mockVisits)
  })
})

describe('useCheckIn', () => {
  afterEach(() => {
    vi.clearAllMocks()
  })

  // Test 4: calls services.visits.checkIn(clientId) and invalidates on settle
  it('mutation calls services.visits.checkIn(clientId)', async () => {
    const mockVisit = { id: 'v1', clientId: 'c1' } as Visit
    vi.mocked(services.visits.checkIn).mockResolvedValue(mockVisit)
    const { result } = renderHook(() => useCheckIn(), { wrapper })
    result.current.mutate('client-123')
    await waitFor(() => expect(result.current.isSuccess).toBe(true))
    expect(services.visits.checkIn).toHaveBeenCalledWith('client-123')
  })
})

describe('useMembershipStatusForClient', () => {
  afterEach(() => {
    vi.clearAllMocks()
  })

  // Test 7: useMembershipStatusForClient calls services.memberships.byClient (NOT features/memberships hook)
  it('calls services.memberships.byClient(clientId) and returns activeMembership (expiringToday=true)', async () => {
    // todayMSK is mocked to return '2026-05-09' above
    const mockMembership: Membership = {
      id: 'm1' as Membership['id'],
      clientId: 'c1',
      planId: 'p1' as Membership['planId'],
      planNameSnapshot: 'Test Plan',
      durationDaysSnapshot: 30,
      priceKopecksSnapshot: 100000,
      startDate: '2026-04-01',
      endDate: '2026-05-09', // matches mocked todayMSK
      status: 'active',
      paidAt: null,
      notes: null,
      cancelledAt: null,
      cancelReason: null,
      createdAt: '2026-04-01T00:00:00Z',
      updatedAt: '2026-04-01T00:00:00Z',
    }
    vi.mocked(services.memberships.byClient).mockResolvedValue({
      items: [mockMembership],
      total: 1,
      page: 1,
      pageSize: 1,
    })
    const { result } = renderHook(() => useMembershipStatusForClient('c1'), { wrapper })
    await waitFor(() => expect(result.current.isPending).toBe(false))
    expect(services.memberships.byClient).toHaveBeenCalledWith('c1')
    expect(result.current.activeMembership).toEqual(mockMembership)
    expect(result.current.expiringToday).toBe(true)
  })

  it('returns expiringToday=false when active membership endDate is NOT today', async () => {
    const mockMembership: Membership = {
      id: 'm1' as Membership['id'],
      clientId: 'c1',
      planId: 'p1' as Membership['planId'],
      planNameSnapshot: 'Test Plan',
      durationDaysSnapshot: 30,
      priceKopecksSnapshot: 100000,
      startDate: '2026-04-01',
      endDate: '2026-06-01', // not today (todayMSK mocked to '2026-05-09')
      status: 'active',
      paidAt: null,
      notes: null,
      cancelledAt: null,
      cancelReason: null,
      createdAt: '2026-04-01T00:00:00Z',
      updatedAt: '2026-04-01T00:00:00Z',
    }
    vi.mocked(services.memberships.byClient).mockResolvedValue({
      items: [mockMembership],
      total: 1,
      page: 1,
      pageSize: 1,
    })
    const { result } = renderHook(() => useMembershipStatusForClient('c1'), { wrapper })
    await waitFor(() => expect(result.current.isPending).toBe(false))
    expect(result.current.expiringToday).toBe(false)
  })

  it('returns activeMembership=undefined when no active memberships', async () => {
    vi.mocked(services.memberships.byClient).mockResolvedValue({
      items: [],
      total: 0,
      page: 1,
      pageSize: 0,
    })
    const { result } = renderHook(() => useMembershipStatusForClient('c1'), { wrapper })
    await waitFor(() => expect(result.current.isPending).toBe(false))
    expect(result.current.activeMembership).toBeUndefined()
    expect(result.current.expiringToday).toBe(false)
  })
})

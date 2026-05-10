import { describe, it, expect, beforeEach, vi } from 'vitest'
import { screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { renderWithProviders } from '@/test/utils'
import type { Membership, MembershipId, MembershipPlanId, Pagination } from '@/entities/membership'
import type { UseQueryResult } from '@tanstack/react-query'

// --- navigate mock -----------------------------------------------------------
const navigateMock = vi.fn()

vi.mock('@tanstack/react-router', async () => {
  const actual = await vi.importActual<typeof import('@tanstack/react-router')>('@tanstack/react-router')
  return {
    ...actual,
    useNavigate: () => navigateMock,
  }
})

// --- route search mock -------------------------------------------------------
// MembershipsListPage calls MembershipsRoute.useSearch() — mock the route module
// to return a controllable search object.
type SearchState = { page: number; pageSize: number; expiring: boolean; status?: string }
const useSearchMock = vi.fn((): SearchState => ({
  page: 1,
  pageSize: 20,
  expiring: false,
  status: undefined,
}))

vi.mock('@/routes/_protected/memberships', () => ({
  Route: {
    useSearch: () => useSearchMock(),
    fullPath: '/_protected/memberships',
  },
}))

// --- useMembershipsList mock -------------------------------------------------
vi.mock('../api/hooks', () => ({
  useMembershipsList: vi.fn(),
}))
import { useMembershipsList } from '../api/hooks'

// useQueries for client name lookup — return empty so client column shows ID
vi.mock('@tanstack/react-query', async () => {
  const actual = await vi.importActual<typeof import('@tanstack/react-query')>('@tanstack/react-query')
  return {
    ...actual,
    useQueries: () => [],
  }
})

// -----------------------------------------------------------------------------

function makeListQuery(items: Membership[]): UseQueryResult<Pagination<Membership>> {
  return {
    data: { items, total: items.length, page: 1, pageSize: 20 },
    isError: false,
    isLoading: false,
    isPending: false,
    isSuccess: true,
    refetch: () => Promise.resolve(undefined),
  } as unknown as UseQueryResult<Pagination<Membership>>
}

function makeMembership(overrides: Partial<Membership> = {}): Membership {
  return {
    id: 'm-frozen-1' as MembershipId,
    clientId: 'c-1',
    planId: 'p-1' as MembershipPlanId,
    planNameSnapshot: 'Стандарт',
    durationDaysSnapshot: 30,
    priceKopecksSnapshot: 100000,
    startDate: '2026-01-01',
    endDate: '2026-01-30',
    status: 'frozen',
    paidAt: null,
    notes: null,
    cancelledAt: null,
    cancelReason: null,
    freezeDaysLimitSnapshot: 14,
    freezeDaysUsed: 5,
    freezeDaysRemaining: 9,
    currentFreezePeriod: {
      id: 'fp-1',
      startedAt: '2026-01-15T00:00:00Z',
      startedBy: 'owner',
      endedAt: null,
      endedBy: null,
    },
    previousMembershipId: null,
    createdAt: '2026-01-01T00:00:00Z',
    updatedAt: '2026-01-15T00:00:00Z',
    ...overrides,
  }
}

import { MembershipsListPage } from './MembershipsListPage'

describe('MembershipsListPage frozen integration', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    navigateMock.mockReset()
    useSearchMock.mockReturnValue({ page: 1, pageSize: 20, expiring: false, status: undefined })
    vi.mocked(useMembershipsList).mockReturnValue(
      makeListQuery([]),
    )
  })

  it('renders the Заморожен pill', async () => {
    renderWithProviders(<MembershipsListPage />, { role: 'owner' })
    await waitFor(() => expect(screen.getByRole('button', { name: 'Заморожен' })).toBeInTheDocument())
  })

  it('clicking Заморожен pill calls navigate with status=frozen and expiring=false', async () => {
    renderWithProviders(<MembershipsListPage />, { role: 'owner' })
    await waitFor(() => expect(screen.getByRole('button', { name: 'Заморожен' })).toBeInTheDocument())
    await userEvent.click(screen.getByRole('button', { name: 'Заморожен' }))
    expect(navigateMock).toHaveBeenCalled()
    const lastCall = navigateMock.mock.calls.at(-1)?.[0] as { search: (prev: object) => {
      status: string | undefined
      expiring: boolean
      page: number
    } } | undefined
    const searchFn = lastCall?.search
    const next = typeof searchFn === 'function'
      ? searchFn({ page: 2, pageSize: 20, expiring: true, status: undefined })
      : searchFn
    expect(next?.status).toBe('frozen')
    expect(next?.expiring).toBe(false)
    expect(next?.page).toBe(1)
  })

  it('row with status=frozen renders Заморожен badge in table', async () => {
    vi.mocked(useMembershipsList).mockReturnValue(makeListQuery([makeMembership()]))
    renderWithProviders(<MembershipsListPage />, { role: 'owner' })
    await waitFor(() => {
      // The pill in the toolbar AND the badge in the table row both say "Заморожен"
      const matches = screen.getAllByText('Заморожен')
      expect(matches.length).toBeGreaterThanOrEqual(2)
    })
  })

  it('clicking pill while already active toggles status off (sends undefined)', async () => {
    useSearchMock.mockReturnValue({ page: 1, pageSize: 20, expiring: false, status: 'frozen' })
    renderWithProviders(<MembershipsListPage />, { role: 'owner' })
    await waitFor(() => expect(screen.getByRole('button', { name: 'Заморожен' })).toBeInTheDocument())
    await userEvent.click(screen.getByRole('button', { name: 'Заморожен' }))
    const lastCall = navigateMock.mock.calls.at(-1)?.[0] as { search: (prev: object) => {
      status: string | undefined
    } } | undefined
    const searchFn = lastCall?.search
    const next = typeof searchFn === 'function'
      ? searchFn({ page: 1, pageSize: 20, expiring: false, status: 'frozen' })
      : searchFn
    expect(next?.status).toBeUndefined()
  })
})

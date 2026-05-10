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
type SearchState = { page: number; pageSize: number; expiring: boolean; status?: string; within?: number }
const useSearchMock = vi.fn((): SearchState => ({
  page: 1,
  pageSize: 20,
  expiring: false,
  status: undefined,
  within: 7,
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
    id: 'm-1' as MembershipId,
    clientId: 'c-1',
    planId: 'p-1' as MembershipPlanId,
    planNameSnapshot: 'Стандарт',
    durationDaysSnapshot: 30,
    priceKopecksSnapshot: 100000,
    startDate: '2026-01-01',
    endDate: '2026-01-30',
    status: 'active',
    paidAt: null,
    notes: null,
    cancelledAt: null,
    cancelReason: null,
    freezeDaysLimitSnapshot: 14,
    freezeDaysUsed: 0,
    freezeDaysRemaining: 14,
    currentFreezePeriod: null,
    previousMembershipId: null,
    createdAt: '2026-01-01T00:00:00Z',
    updatedAt: '2026-01-01T00:00:00Z',
    ...overrides,
  }
}

import { MembershipsListPage } from './MembershipsListPage'

describe('MembershipsListPage within selector', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    navigateMock.mockReset()
    useSearchMock.mockReturnValue({ page: 1, pageSize: 20, expiring: false, status: undefined, within: 7 })
    vi.mocked(useMembershipsList).mockReturnValue(makeListQuery([]))
  })

  it('does NOT render the within selector when expiring=false', async () => {
    useSearchMock.mockReturnValue({ page: 1, pageSize: 20, expiring: false, status: undefined, within: 7 })
    renderWithProviders(<MembershipsListPage />, { role: 'owner' })
    await waitFor(() => expect(screen.queryByText('Истекает в течение')).toBeNull())
  })

  it('renders the within selector with label when expiring=true', async () => {
    useSearchMock.mockReturnValue({ page: 1, pageSize: 20, expiring: true, status: undefined, within: 7 })
    vi.mocked(useMembershipsList).mockReturnValue(makeListQuery([makeMembership()]))
    renderWithProviders(<MembershipsListPage />, { role: 'owner' })
    await waitFor(() => expect(screen.getByText('Истекает в течение')).toBeInTheDocument())
  })

  it('selecting 14 дн. calls navigate with within=14 and page=1', async () => {
    useSearchMock.mockReturnValue({ page: 3, pageSize: 20, expiring: true, status: undefined, within: 7 })
    vi.mocked(useMembershipsList).mockReturnValue(makeListQuery([makeMembership()]))
    renderWithProviders(<MembershipsListPage />, { role: 'owner' })
    await waitFor(() => expect(screen.getByText('Истекает в течение')).toBeInTheDocument())
    // Open the select trigger — base-ui renders a button with data-slot="select-trigger"
    // The accessible name is not reliably set in jsdom; query by data-slot attribute instead
    const trigger = document.querySelector('[data-slot="select-trigger"]') as HTMLElement
    expect(trigger).not.toBeNull()
    await userEvent.click(trigger)
    // Click the option labelled "14 дн."
    const option = await screen.findByText(/^14 дн\.$/)
    await userEvent.click(option)
    const lastCall = navigateMock.mock.calls.at(-1)?.[0] as
      | { search: (prev: SearchState) => SearchState }
      | undefined
    const searchFn = lastCall?.search
    const next =
      typeof searchFn === 'function'
        ? searchFn({ page: 3, pageSize: 20, expiring: true, status: undefined, within: 7 })
        : searchFn
    expect(next?.within).toBe(14)
    expect(next?.page).toBe(1)
  })

  it('options list includes exactly 1, 3, 7, 14, 30 дн.', async () => {
    useSearchMock.mockReturnValue({ page: 1, pageSize: 20, expiring: true, status: undefined, within: 7 })
    vi.mocked(useMembershipsList).mockReturnValue(makeListQuery([makeMembership()]))
    renderWithProviders(<MembershipsListPage />, { role: 'owner' })
    await waitFor(() => expect(screen.getByText('Истекает в течение')).toBeInTheDocument())
    // Open the dropdown via the select trigger button
    const trigger = document.querySelector('[data-slot="select-trigger"]') as HTMLElement
    expect(trigger).not.toBeNull()
    await userEvent.click(trigger)
    for (const n of [1, 3, 7, 14, 30]) {
      const re = new RegExp(`^${n} дн\\.$`)
      expect(await screen.findByText(re)).toBeInTheDocument()
    }
  })
})

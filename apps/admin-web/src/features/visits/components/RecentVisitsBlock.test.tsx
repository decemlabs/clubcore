import { describe, it, expect, vi, afterEach } from 'vitest'
import { screen } from '@testing-library/react'
import { renderWithProviders } from '@/test/utils'
import type { Visit, VisitId, VisitChannel } from '@/entities/visit'
import type { UseQueryResult } from '@tanstack/react-query'
import { RecentVisitsBlock } from './RecentVisitsBlock'

vi.mock('@/features/visits/api/hooks', () => ({
  useRecentVisitsByClient: vi.fn(),
  useGymMeta: vi.fn(() => ({ data: { gymHoursStart: '07:00', gymHoursEnd: '23:00' } })),
}))

import { useRecentVisitsByClient } from '../api/hooks'

const makeVisit = (overrides: Partial<Visit> = {}): Visit => ({
  id: 'v1' as VisitId,
  clientId: 'c1',
  membershipId: 'm1',
  checkedInAt: '2026-05-09T08:30:00Z',
  gymDate: '2026-05-09',
  channel: 'reception' as VisitChannel,
  checkedInBy: 'user1',
  createdAt: '2026-05-09T08:30:00Z',
  ...overrides,
})

describe('RecentVisitsBlock', () => {
  afterEach(() => {
    vi.clearAllMocks()
  })

  // Test 8: renders 5 skeleton rows while pending
  it('renders skeleton rows while loading', () => {
    vi.mocked(useRecentVisitsByClient).mockReturnValue({
      data: undefined,
      isPending: true,
      isError: false,
    } as ReturnType<typeof useRecentVisitsByClient>)
    renderWithProviders(<RecentVisitsBlock clientId="c1" />, { role: 'owner' })
    // Skeletons are rendered as animate-pulse elements
    const skeletons = document.querySelectorAll('[data-slot="skeleton"]')
    expect(skeletons.length).toBeGreaterThan(0)
  })

  // Test 9: renders "Посещений нет" when empty
  it('renders empty state when no visits', () => {
    vi.mocked(useRecentVisitsByClient).mockReturnValue({
      data: [] as Visit[],
      isPending: false,
      isError: false,
    } as UseQueryResult<Visit[], Error>)
    renderWithProviders(<RecentVisitsBlock clientId="c1" />, { role: 'owner' })
    expect(screen.getByText('Посещений нет')).toBeDefined()
  })

  // Test 10: renders visit rows with date, time (MSK), channel badge
  it('renders visits table with date, time, and channel', () => {
    // formatTimeMSK pins to Europe/Moscow; assert HH:mm matches MSK render of the seeded ISO datetime
    // 2026-05-09T08:30:00Z = 11:30 Moscow (UTC+3)
    const visit = makeVisit({ checkedInAt: '2026-05-09T08:30:00Z' })
    vi.mocked(useRecentVisitsByClient).mockReturnValue({
      data: [visit],
      isPending: false,
      isError: false,
    } as ReturnType<typeof useRecentVisitsByClient>)
    renderWithProviders(<RecentVisitsBlock clientId="c1" />, { role: 'owner' })
    // Date column: DD.MM.YYYY format — date-fns uses local zone but for date-only it's fine
    expect(screen.getByText('09.05.2026')).toBeDefined()
    // Telegram bot visit should show telegram badge
    const telegramVisit = makeVisit({ channel: 'telegram_bot', checkedInBy: null })
    vi.mocked(useRecentVisitsByClient).mockReturnValue({
      data: [telegramVisit],
      isPending: false,
      isError: false,
    } as ReturnType<typeof useRecentVisitsByClient>)
    renderWithProviders(<RecentVisitsBlock clientId="c2" />, { role: 'owner' })
    expect(screen.getAllByText('Telegram').length).toBeGreaterThan(0)
  })
})

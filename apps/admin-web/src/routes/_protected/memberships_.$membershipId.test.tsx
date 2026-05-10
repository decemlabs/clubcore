import { describe, it, expect, beforeEach, vi } from 'vitest'
import { screen, waitFor } from '@testing-library/react'
import { renderWithProviders } from '@/test/utils'
import type { Membership, MembershipId } from '@/entities/membership'

vi.mock('@/shared/api/services', () => ({
  services: { memberships: { get: vi.fn() } },
  API_MODE: 'mock',
}))

vi.mock('@tanstack/react-router', async (importOriginal) => {
  const actual = await importOriginal<typeof import('@tanstack/react-router')>()
  return {
    ...actual,
    useParams: () => ({ membershipId: 'm-1' }),
    Link: ({ children, ...props }: { children: React.ReactNode; [key: string]: unknown }) => (
      <a {...props}>{children}</a>
    ),
  }
})

import { services } from '@/shared/api/services'
import { MembershipDetailPage } from './memberships_.$membershipId'

function makeMembership(overrides: Partial<Membership> = {}): Membership {
  return {
    id: 'm-1' as MembershipId,
    clientId: 'c-1',
    planId: 'p-1' as Membership['planId'],
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

describe('MembershipDetailPage', () => {
  beforeEach(() => {
    vi.clearAllMocks()
  })

  it('owner sees Freeze + Renew sections for an active membership', async () => {
    ;(services.memberships.get as ReturnType<typeof vi.fn>).mockResolvedValue(makeMembership())
    renderWithProviders(<MembershipDetailPage />, { role: 'owner' })
    await waitFor(() => expect(screen.getByText('Заморозить')).toBeInTheDocument())
    expect(screen.getByText('Продлить')).toBeInTheDocument()
  })

  it('reception also sees Freeze + Renew (CREATE MEMBERSHIPS is not owner-only)', async () => {
    ;(services.memberships.get as ReturnType<typeof vi.fn>).mockResolvedValue(makeMembership())
    renderWithProviders(<MembershipDetailPage />, { role: 'reception' })
    await waitFor(() => expect(screen.getByText('Заморозить')).toBeInTheDocument())
    expect(screen.getByText('Продлить')).toBeInTheDocument()
  })

  it('frozen membership shows Снять заморозку instead of Заморозить', async () => {
    ;(services.memberships.get as ReturnType<typeof vi.fn>).mockResolvedValue(
      makeMembership({
        status: 'frozen',
        currentFreezePeriod: {
          id: 'p',
          startedAt: '2026-01-15T00:00:00Z',
          startedBy: 'owner',
          endedAt: null,
          endedBy: null,
        },
      }),
    )
    renderWithProviders(<MembershipDetailPage />, { role: 'owner' })
    await waitFor(() => expect(screen.getByText('Снять заморозку')).toBeInTheDocument())
    expect(screen.queryByText('Заморозить')).toBeNull()
  })

  it('cancelled membership hides Renew', async () => {
    ;(services.memberships.get as ReturnType<typeof vi.fn>).mockResolvedValue(
      makeMembership({ status: 'cancelled' }),
    )
    renderWithProviders(<MembershipDetailPage />, { role: 'owner' })
    await waitFor(() => expect(screen.getByText('Отменён')).toBeInTheDocument())
    expect(screen.queryByText('Продлить')).toBeNull()
  })

  it('disabled freeze button when freezeDaysRemaining=0 (tooltip text in DOM)', async () => {
    ;(services.memberships.get as ReturnType<typeof vi.fn>).mockResolvedValue(
      makeMembership({ freezeDaysRemaining: 0, freezeDaysUsed: 14 }),
    )
    renderWithProviders(<MembershipDetailPage />, { role: 'owner' })
    await waitFor(() => {
      const btn = screen.getByText('Заморозить').closest('button')
      expect(btn?.disabled).toBe(true)
    })
  })
})

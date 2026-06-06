/**
 * HomeScreen identity binding tests (Plan 71-10, Task 1).
 * Extended in Plan 999.3-02 Task 3: shared mock + 3 render-gate tests.
 * Extended in Plan 76-01 Task 3: mock useClientTrainers/useClientPlans + NHOME-01/02 assertions.
 *
 * Asserts the wired Home screen reflects the real /client/me principal and the
 * genuine empty-membership state — not the mock 'Саша' / demo active card:
 *  (a) /client/me { firstName: 'Иван' } → header avatar initial shows "И"
 *      (Phase 73: classic HomeHeroCard is a gym card, not a greeting line).
 *  (b) /client/home membership=null → "Нет абонемента" empty state + "Выбрать тариф"
 *      CTA renders (toSubInfo(null) danger path), NOT a fake active card.
 *  (c) membershipState==='newbie' → newbie onboarding renders (D-01/D-02).
 *  (d) membershipState==='lapsed' → existing flow, no newbie copy.
 *  (e) membershipState==='active' → existing flow, no newbie CTA.
 *  (f) NHOME-01: avatar strip renders initials from live useClientTrainers data (D-76-01).
 *  (g) NHOME-02: plan chip text derived from live useClientPlans data (D-76-06).
 */
import React from 'react'
import { describe, it, expect, vi, beforeEach } from 'vitest'
import { render, screen } from '@testing-library/react'
import { MemoryRouter } from 'react-router-dom'

// Mock the swap-seam data hooks so the render reflects controlled API truth.
const useClientMe = vi.fn()
const useClientHome = vi.fn()
const useClientBookings = vi.fn()
const useClientTrainers = vi.fn()
const useClientPlans = vi.fn()
const useClientNotifications = vi.fn()
vi.mock('@/data', () => ({
  useClientMe: (...args) => useClientMe(...args),
  useClientHome: (...args) => useClientHome(...args),
  useClientBookings: (...args) => useClientBookings(...args),
  useClientTrainers: (...args) => useClientTrainers(...args),
  useClientPlans: (...args) => useClientPlans(...args),
  useClientNotifications: (...args) => useClientNotifications(...args),
}))

// Mock the direct @/data/trainers.js import used for STATIC_TRAINERS_FALLBACK (D-76-05)
vi.mock('@/data/trainers.js', () => ({
  TRAINERS: [
    { id: 's1', name: 'Аня Соколова' },
    { id: 's2', name: 'Марк Левин' },
    { id: 's3', name: 'Лиза Орлова' },
  ],
}))

// Mock formatMoney so plan chip assertions are deterministic (no NBSP locale surprises)
vi.mock('@/utils/format.js', () => ({
  formatMoney: (kopecks) => String(kopecks / 100),
}))

import { HomeScreen } from './HomeScreen.jsx'

const noop = () => {}
const baseProps = {
  tweaks: {},
  onOpenQR: noop,
  onOpenPlans: noop,
  onOpenManage: noop,
  onOpenReferral: noop,
  onOpenGymInfo: noop,
  onOpenNotifications: noop,
  onTab: noop,
  setTweak: noop,
}

// HomeScreen calls useNavigate() (the newbie → /onboarding redirect, Phase 999.5),
// so it must render inside a Router.
const renderHome = () => render(
  <MemoryRouter>
    <HomeScreen {...baseProps} />
  </MemoryRouter>,
)

beforeEach(() => {
  useClientMe.mockReset()
  useClientHome.mockReset()
  useClientBookings.mockReset()
  useClientTrainers.mockReset()
  useClientPlans.mockReset()
  useClientNotifications.mockReset()
  // Safe default so pre-existing tests (which never set bookings) keep passing
  useClientBookings.mockReturnValue({ data: { items: [], total: 0 } })
  // Safe defaults: empty/no-loading so HomeNewbie renders without crashing
  useClientTrainers.mockReturnValue({ data: [], isLoading: false })
  useClientPlans.mockReturnValue({ data: [] })
  // Phase 87: useClientNotifications used in HomeScreen for badge count
  useClientNotifications.mockReturnValue({ data: { items: [], total: 0 } })
})

describe('HomeScreen identity + empty-membership (real /client/me)', () => {
  it('reflects the real /client/me principal in the header avatar initial', () => {
    // Phase 73 restyle: the classic HomeHeroCard header is a gym card (title +
    // status + occupancy), not a greeting line — the real principal now surfaces
    // via the avatar initial derived from me.firstName, not full-name text.
    // The mock 'Саша' (initial 'С') still fails this, guarding the same regression.
    useClientMe.mockReturnValue({ data: { firstName: 'Иван', lastName: 'Петров' } })
    useClientHome.mockReturnValue({
      data: { membership: null, nextBooking: null },
      isLoading: false,
      isError: false,
      refetch: noop,
    })

    renderHome()
    expect(screen.getByText('И')).toBeInTheDocument()
    expect(screen.queryByText('Саша')).not.toBeInTheDocument()
  })

  it('renders the real "Нет абонемента" empty state when membership is null', () => {
    useClientMe.mockReturnValue({ data: { firstName: 'Иван' } })
    useClientHome.mockReturnValue({
      data: { membership: null, nextBooking: null },
      isLoading: false,
      isError: false,
      refetch: noop,
    })

    renderHome()
    expect(screen.getByText('Нет абонемента')).toBeInTheDocument()
    expect(screen.getByText('Выбрать тариф')).toBeInTheDocument()
    expect(screen.queryByText('Годовой')).not.toBeInTheDocument()
  })
})

// ─── Render-gate tests — Plan 999.3-02 (D-01/D-02) ───────────────────────────
describe('HomeScreen render gate (membershipState newbie vs lapsed vs active)', () => {
  it('renders newbie onboarding when membershipState === "newbie"', () => {
    useClientMe.mockReturnValue({ data: { firstName: 'Иван', lastName: 'Петров' } })
    useClientHome.mockReturnValue({
      data: { membershipState: 'newbie', membership: null, nextBooking: null },
      isLoading: false,
      isError: false,
      refetch: noop,
    })
    useClientBookings.mockReturnValue({ data: { items: [], total: 0 } })

    renderHome()

    // Newbie copy must be present (v2 plan-card title + CTA)
    expect(screen.getByText('Выбери свой абонемент')).toBeInTheDocument()
    expect(screen.getByText('Оформить абонемент')).toBeInTheDocument()
    // Non-newbie copy must NOT be present
    expect(screen.queryByText('Нет абонемента')).not.toBeInTheDocument()
    expect(screen.queryByText('Годовой')).not.toBeInTheDocument()
  })

  it('does NOT render newbie copy when membershipState === "lapsed"', () => {
    useClientMe.mockReturnValue({ data: { firstName: 'Иван' } })
    useClientHome.mockReturnValue({
      data: { membershipState: 'lapsed', membership: null, nextBooking: null },
      isLoading: false,
      isError: false,
      refetch: noop,
    })
    useClientBookings.mockReturnValue({ data: { items: [], total: 0 } })

    renderHome()

    // Newbie onboarding hero must NOT appear for lapsed members
    expect(screen.queryByText('Выбери свой абонемент')).not.toBeInTheDocument()
  })

  it('does NOT render newbie CTA when membershipState === "active"', () => {
    useClientMe.mockReturnValue({ data: { firstName: 'Иван' } })
    useClientHome.mockReturnValue({
      data: {
        membershipState: 'active',
        membership: {
          id: 'm1', planNameSnapshot: 'Годовой', daysUntilEnd: 100,
          startDate: '2026-01-01', endDate: '2026-12-31', expiringSoon: false, status: 'active',
        },
        nextBooking: null,
      },
      isLoading: false,
      isError: false,
      refetch: noop,
    })
    useClientBookings.mockReturnValue({ data: { items: [], total: 0 } })

    renderHome()

    // Newbie CTA must NOT appear for active members
    expect(screen.queryByText('Оформить абонемент')).not.toBeInTheDocument()
  })
})

// ─── Live wiring assertions — Plan 76-01 (NHOME-01 / NHOME-02) ───────────────
describe('HomeScreen newbie live data wiring', () => {
  const newbieBase = () => {
    useClientMe.mockReturnValue({ data: { firstName: 'Иван', lastName: 'Петров' } })
    useClientHome.mockReturnValue({
      data: { membershipState: 'newbie', membership: null, nextBooking: null },
      isLoading: false,
      isError: false,
      refetch: noop,
    })
    useClientBookings.mockReturnValue({ data: { items: [], total: 0 } })
  }

  it('NHOME-01: avatar strip shows initials from live useClientTrainers data, not static fallback', () => {
    newbieBase()
    // Live trainers with fullName (camelCase wire — ClientCatalogTrainerResponse)
    // different from the static TRAINERS mock (which has 'Аня' → 'А')
    useClientTrainers.mockReturnValue({
      data: [
        { id: 'lt1', fullName: 'Олег Борисов' },
        { id: 'lt2', fullName: 'Нина Козлова' },
      ],
      isLoading: false,
    })

    renderHome()

    // Live trainer initials must appear
    expect(screen.getByText('О')).toBeInTheDocument()
    // Static fallback initial 'А' (Аня) must NOT appear — confirms live data wins
    expect(screen.queryByText('А')).not.toBeInTheDocument()
  })

  it('NHOME-02: plan buttons render from live useClientPlans data with prices', () => {
    newbieBase()
    // camelCase wire (priceKopecks per ClientCatalogPlanResponse).
    // formatMoney is mocked: (kopecks) => String(kopecks / 100)
    // So 150000 kopecks → "1500", 600000 kopecks → "6000".
    useClientPlans.mockReturnValue({
      data: [
        { id: 'p1', name: 'Месяц', priceKopecks: 150000, durationDays: 30 },
        { id: 'p2', name: 'Полгода', priceKopecks: 600000, durationDays: 180 },
      ],
    })

    renderHome()

    // Both plan names must appear as tariff buttons.
    expect(screen.getByText('Месяц')).toBeInTheDocument()
    expect(screen.getByText('Полгода')).toBeInTheDocument()
    // Prices must appear via formatMoney (mocked to kopecks/100 string).
    expect(screen.getByText('1500')).toBeInTheDocument()
    expect(screen.getByText('6000')).toBeInTheDocument()
    // Regression guard (CR-76-01): snake_case misread → NaN → formatMoney prints NaN sentinel.
    expect(screen.queryByText(/не число/)).not.toBeInTheDocument()
    // The old plan-info chip must NOT appear (replaced by per-button prices).
    expect(screen.queryByText(/тариф\S* · от .+\/мес/)).not.toBeInTheDocument()
  })
})

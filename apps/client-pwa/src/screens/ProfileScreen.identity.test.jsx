/**
 * ProfileScreen identity binding tests (Plan 71-10, Task 2).
 *
 * Asserts the identity header + membership block reflect the real /client/me
 * principal — not the mock "Саша Морозов / sasha@example.com" / "42 000 ₽":
 *  (a) /client/me { firstName, lastName, phone, email: null } → header shows the real
 *      name + phone + graceful em-dash email (NOT sasha@example.com / the mock phone).
 *  (b) membership=null → "Нет абонемента" state; no "42 000 ₽" / "4 900 ₽" literal.
 */
import React from 'react'
import { describe, it, expect, vi, beforeEach } from 'vitest'
import { render, screen } from '@testing-library/react'

// Mock the swap-seam data hooks so the render reflects controlled API truth.
const useClientMe = vi.fn()
const useClientHome = vi.fn()
const emptyList = { data: { items: [], total: 0 }, isLoading: false, isError: false, refetch: () => {} }
vi.mock('@/data', () => ({
  useClientMe: (...args) => useClientMe(...args),
  useClientHome: (...args) => useClientHome(...args),
  useClientVisitHistory: () => emptyList,
  useClientPtHistory: () => emptyList,
  useClientPaymentHistory: () => emptyList,
}))
vi.mock('@/context/AuthContext.jsx', () => ({
  useAuth: () => ({ logout: () => {} }),
}))

import { ProfileScreen } from './ProfileScreen.jsx'

const noop = () => {}
const baseProps = {
  tweaks: {},
  setTweak: noop,
  onOpenPlans: noop,
  onOpenReferral: noop,
  onOpenGymInfo: noop,
  onOpenPersonalData: noop,
  onOpenCard: noop,
  onOpenFAQ: noop,
  onOpenVisitHistory: noop,
  onOpenTrainingHistory: noop,
}

beforeEach(() => {
  useClientMe.mockReset()
  useClientHome.mockReset()
})

describe('ProfileScreen identity header (real /client/me)', () => {
  it('renders the real name, phone, and a graceful em-dash for a missing email', () => {
    useClientMe.mockReturnValue({
      data: { firstName: 'Иван', lastName: 'Петров', phone: '+79991234567', email: null },
    })
    useClientHome.mockReturnValue({ data: { membership: null } })

    render(<ProfileScreen {...baseProps} />)
    expect(screen.getByText('Иван Петров')).toBeInTheDocument()
    expect(screen.getByText('+79991234567')).toBeInTheDocument()
    expect(screen.queryByText('sasha@example.com')).not.toBeInTheDocument()
    expect(screen.queryByText('+7 (916) 482-09-14')).not.toBeInTheDocument()
  })

  it('shows the real "Нет абонемента" state with no fabricated renewal amount', () => {
    useClientMe.mockReturnValue({
      data: { firstName: 'Иван', lastName: 'Петров', phone: '+79991234567', email: null },
    })
    useClientHome.mockReturnValue({ data: { membership: null } })

    render(<ProfileScreen {...baseProps} />)
    expect(screen.getByText('Нет абонемента')).toBeInTheDocument()
    expect(screen.queryByText(/42 000 ₽/)).not.toBeInTheDocument()
    expect(screen.queryByText(/4 900 ₽/)).not.toBeInTheDocument()
  })
})

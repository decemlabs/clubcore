/**
 * PaymentReturnScreen anti-oracle Vitest test (Plan 999.4-04 Task 2, W5 behavioral gate).
 *
 * Anti-oracle criterion #1: the success copy ("Ты в команде" / "Оплата подтверждена.")
 * must NEVER render while status === 'pending'. It must render when status === 'succeeded'.
 *
 * Updated in Plan 260601-vxr to cover the new PaymentSucceededView (useClientMe +
 * useClientMembership) while preserving all existing anti-oracle assertions.
 */
import React from 'react'
import { describe, it, expect, vi, beforeEach } from 'vitest'
import { render, screen } from '@testing-library/react'

// Mock the swap-seam hooks so we drive status without a real API.
const useClientPaymentStatus = vi.fn()
const useClientMe = vi.fn()
const useClientMembership = vi.fn()
vi.mock('@/data', () => ({
  useClientPaymentStatus: (...args) => useClientPaymentStatus(...args),
  useClientMe: (...args) => useClientMe(...args),
  useClientMembership: (...args) => useClientMembership(...args),
}))

// react-router-dom: stub useSearchParams, useNavigate so the component can render in jsdom.
vi.mock('react-router-dom', () => ({
  useSearchParams: () => [new URLSearchParams('payment_id=test-id')],
  useNavigate: () => vi.fn(),
}))

import { PaymentReturnScreen } from './PaymentReturnScreen.jsx'

beforeEach(() => {
  useClientPaymentStatus.mockReset()
  // Default: no profile data, no membership
  useClientMe.mockReturnValue({ data: undefined })
  useClientMembership.mockReturnValue({ data: undefined })
})

describe('PaymentReturnScreen anti-oracle gate', () => {
  it('pending state: shows "Ожидаем подтверждение" and does NOT show success copy', () => {
    useClientPaymentStatus.mockReturnValue({
      data: { id: 'test-id', status: 'pending' },
      isLoading: false,
    })

    render(<PaymentReturnScreen />)

    // Pending copy must be present
    expect(screen.getByText('Ожидаем подтверждение')).toBeInTheDocument()

    // Success copy must NOT be present (anti-oracle criterion #1)
    expect(screen.queryByText(/Ты в команде/)).not.toBeInTheDocument()
    expect(screen.queryByText(/Оплата подтверждена/)).not.toBeInTheDocument()
  })

  it('succeeded state: shows personalized greeting and success copy', () => {
    useClientPaymentStatus.mockReturnValue({
      data: { id: 'test-id', status: 'succeeded', receiptUrl: null },
      isLoading: false,
    })
    useClientMe.mockReturnValue({ data: { firstName: 'Саша' } })
    useClientMembership.mockReturnValue({ data: null })

    render(<PaymentReturnScreen />)

    // Success copy must be present (new design)
    expect(screen.getByText('Ты в команде, Саша')).toBeInTheDocument()
    expect(screen.getByText('Оплата подтверждена. Доступ активен.')).toBeInTheDocument()

    // Pending copy must NOT be present
    expect(screen.queryByText('Ожидаем подтверждение')).not.toBeInTheDocument()
  })

  it('succeeded state without firstName: shows fallback greeting', () => {
    useClientPaymentStatus.mockReturnValue({
      data: { id: 'test-id', status: 'succeeded', receiptUrl: null },
      isLoading: false,
    })
    useClientMe.mockReturnValue({ data: { firstName: '' } })
    useClientMembership.mockReturnValue({ data: null })

    render(<PaymentReturnScreen />)

    expect(screen.getByText('Ты в команде!')).toBeInTheDocument()
  })

  // D-10 anti-oracle: no membership or activation details rendered while pending.
  // The UI-level assertion: the succeeded view is entirely absent during pending.
  it('pending state: no activation state or membership data renders (anti-oracle D-10)', () => {
    useClientPaymentStatus.mockReturnValue({
      data: { id: 'test-id', status: 'pending' },
      isLoading: false,
    })

    render(<PaymentReturnScreen />)

    // Succeeded view content must be entirely absent during pending
    expect(screen.queryByText(/Ты в команде/)).not.toBeInTheDocument()
    expect(screen.queryByText(/Оплата подтверждена/)).not.toBeInTheDocument()
    expect(screen.queryByText('Активен')).not.toBeInTheDocument()
    // Pending spinner is shown
    expect(screen.getByText('Ожидаем подтверждение')).toBeInTheDocument()
  })

  // WR-04: D-11 receipt URL conditional — "Открыть чек" must appear only when receiptUrl is non-null.
  it('succeeded state with receiptUrl: shows "Открыть чек" link with correct href', () => {
    useClientPaymentStatus.mockReturnValue({
      data: { id: 'test-id', status: 'succeeded', receiptUrl: 'https://yookassa.ru/my/receipt/abc' },
      isLoading: false,
    })
    useClientMe.mockReturnValue({ data: { firstName: 'Вася' } })
    useClientMembership.mockReturnValue({ data: null })

    render(<PaymentReturnScreen />)

    const link = screen.getByText('Открыть чек')
    expect(link).toBeInTheDocument()
    expect(link.getAttribute('href')).toBe('https://yookassa.ru/my/receipt/abc')
  })

  it('succeeded state without receiptUrl: "Открыть чек" is absent', () => {
    useClientPaymentStatus.mockReturnValue({
      data: { id: 'test-id', status: 'succeeded', receiptUrl: null },
      isLoading: false,
    })
    useClientMe.mockReturnValue({ data: { firstName: '' } })
    useClientMembership.mockReturnValue({ data: null })

    render(<PaymentReturnScreen />)

    expect(screen.queryByText('Открыть чек')).not.toBeInTheDocument()
  })

  it('succeeded state with membership: shows plan card with real data', () => {
    useClientPaymentStatus.mockReturnValue({
      data: { id: 'test-id', status: 'succeeded', receiptUrl: null },
      isLoading: false,
    })
    useClientMe.mockReturnValue({ data: { firstName: '' } })
    useClientMembership.mockReturnValue({
      data: {
        id: 'mem-1',
        planNameSnapshot: 'Полугодовой',
        startDate: '2026-06-01',
        endDate: '2026-11-27',
        status: 'active',
        daysUntilEnd: 180,
        expiringSoon: false,
      },
    })

    render(<PaymentReturnScreen />)

    expect(screen.getByText('Полугодовой')).toBeInTheDocument()
    expect(screen.getByText('Активен')).toBeInTheDocument()
    expect(screen.getByText(/27 ноября 2026/)).toBeInTheDocument()
    expect(screen.getByText(/180 дней/)).toBeInTheDocument()
  })

  it('succeeded state with null membership: plan card is absent, rest renders', () => {
    useClientPaymentStatus.mockReturnValue({
      data: { id: 'test-id', status: 'succeeded', receiptUrl: null },
      isLoading: false,
    })
    useClientMe.mockReturnValue({ data: { firstName: 'Аня' } })
    useClientMembership.mockReturnValue({ data: null })

    render(<PaymentReturnScreen />)

    // No plan card
    expect(screen.queryByText('Активен')).not.toBeInTheDocument()
    // But greeting is present
    expect(screen.getByText('Ты в команде, Аня')).toBeInTheDocument()
  })
})

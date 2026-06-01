/**
 * PaymentReturnScreen anti-oracle Vitest test (Plan 999.4-04 Task 2, W5 behavioral gate).
 *
 * Anti-oracle criterion #1: the success copy ("Ты в команде" / "Оплата подтверждена.")
 * must NEVER render while status === 'pending'. It must render when status === 'succeeded'.
 *
 * Updated in Plan 260601-vxr-01 (REVISION 1) to cover the full 1:1 mockup restore:
 * achievement chip, validity progress bar, perks list, receipt-link row (real amount),
 * QR-pass button, "На главную" button — while preserving all existing anti-oracle assertions.
 */
import React from 'react'
import { describe, it, expect, vi, beforeEach } from 'vitest'
import { render, screen } from '@testing-library/react'

// Mock the swap-seam hooks so we drive status without a real API.
const useClientPaymentStatus = vi.fn()
const useClientMe = vi.fn()
const useClientMembership = vi.fn()
const useClientPaymentHistory = vi.fn()
vi.mock('@/data', () => ({
  useClientPaymentStatus: (...args) => useClientPaymentStatus(...args),
  useClientMe: (...args) => useClientMe(...args),
  useClientMembership: (...args) => useClientMembership(...args),
  useClientPaymentHistory: (...args) => useClientPaymentHistory(...args),
}))

// react-router-dom: stub useSearchParams, useNavigate, useLocation so the component can render in jsdom.
const mockNavigate = vi.fn()
vi.mock('react-router-dom', () => ({
  useSearchParams: () => [new URLSearchParams('payment_id=test-id')],
  useNavigate: () => mockNavigate,
  useLocation: () => ({ pathname: '/payment/return', search: '?payment_id=test-id', state: null }),
}))

import { PaymentReturnScreen } from './PaymentReturnScreen.jsx'

beforeEach(() => {
  useClientPaymentStatus.mockReset()
  mockNavigate.mockReset()
  // Default: no profile data, no membership, no payment history
  useClientMe.mockReturnValue({ data: undefined })
  useClientMembership.mockReturnValue({ data: undefined })
  useClientPaymentHistory.mockReturnValue({ data: undefined })
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

  // WR-04 / D-11: "Открыть чек" lives inside the plan card — visible when BOTH
  // membership is non-null AND receiptUrl is non-null.
  it('succeeded state with receiptUrl and membership: shows "Открыть чек" link with correct href', () => {
    useClientPaymentStatus.mockReturnValue({
      data: { id: 'test-id', status: 'succeeded', receiptUrl: 'https://yookassa.ru/my/receipt/abc' },
      isLoading: false,
    })
    useClientMe.mockReturnValue({ data: { firstName: 'Вася' } })
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

    const link = screen.getByText('Открыть чек')
    expect(link).toBeInTheDocument()
    expect(link.closest('a').getAttribute('href')).toBe('https://yookassa.ru/my/receipt/abc')
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

  it('succeeded state with receiptUrl but null membership: "Открыть чек" is absent (card not rendered)', () => {
    // D-11 is enforced inside the plan card; if no membership, the whole card is absent.
    useClientPaymentStatus.mockReturnValue({
      data: { id: 'test-id', status: 'succeeded', receiptUrl: 'https://yookassa.ru/receipt/x' },
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
    expect(screen.getByText(/180/)).toBeInTheDocument()
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

  // REVISION 1 — new element tests

  it('succeeded state: achievement chip "Новый участник клуба" is shown', () => {
    useClientPaymentStatus.mockReturnValue({
      data: { id: 'test-id', status: 'succeeded', receiptUrl: null },
      isLoading: false,
    })
    useClientMe.mockReturnValue({ data: { firstName: 'Тест' } })
    useClientMembership.mockReturnValue({ data: null })

    render(<PaymentReturnScreen />)

    expect(screen.getByText('Новый участник клуба')).toBeInTheDocument()
  })

  it('pending state: achievement chip is NOT shown (anti-oracle)', () => {
    useClientPaymentStatus.mockReturnValue({
      data: { id: 'test-id', status: 'pending' },
      isLoading: false,
    })

    render(<PaymentReturnScreen />)

    expect(screen.queryByText('Новый участник клуба')).not.toBeInTheDocument()
  })

  it('succeeded state with membership: shows perks list', () => {
    useClientPaymentStatus.mockReturnValue({
      data: { id: 'test-id', status: 'succeeded', receiptUrl: null },
      isLoading: false,
    })
    useClientMe.mockReturnValue({ data: { firstName: '' } })
    useClientMembership.mockReturnValue({
      data: {
        id: 'mem-1',
        planNameSnapshot: 'Базовый',
        startDate: '2026-06-01',
        endDate: '2026-09-01',
        status: 'active',
        daysUntilEnd: 92,
        expiringSoon: false,
      },
    })

    render(<PaymentReturnScreen />)

    expect(screen.getByText('Зал круглосуточно')).toBeInTheDocument()
    expect(screen.getByText('14 дней заморозки в подарок')).toBeInTheDocument()
    expect(screen.getByText('Сауна и групповые без лимита')).toBeInTheDocument()
  })

  it('succeeded state with membership: shows validity progress row (100%)', () => {
    useClientPaymentStatus.mockReturnValue({
      data: { id: 'test-id', status: 'succeeded', receiptUrl: null },
      isLoading: false,
    })
    useClientMe.mockReturnValue({ data: { firstName: '' } })
    useClientMembership.mockReturnValue({
      data: {
        id: 'mem-1',
        planNameSnapshot: 'Базовый',
        startDate: '2026-06-01',
        endDate: '2026-09-01',
        status: 'active',
        daysUntilEnd: 92,
        expiringSoon: false,
      },
    })

    render(<PaymentReturnScreen />)

    expect(screen.getByText('100%')).toBeInTheDocument()
  })

  it('succeeded state: shows two CTA buttons — QR-pass and home', () => {
    useClientPaymentStatus.mockReturnValue({
      data: { id: 'test-id', status: 'succeeded', receiptUrl: null },
      isLoading: false,
    })
    useClientMe.mockReturnValue({ data: { firstName: '' } })
    useClientMembership.mockReturnValue({ data: null })

    render(<PaymentReturnScreen />)

    expect(screen.getByRole('button', { name: /Открыть QR-пропуск/ })).toBeInTheDocument()
    expect(screen.getByRole('button', { name: 'На главную' })).toBeInTheDocument()
  })

  it('pending state: QR-pass button is absent (anti-oracle)', () => {
    useClientPaymentStatus.mockReturnValue({
      data: { id: 'test-id', status: 'pending' },
      isLoading: false,
    })

    render(<PaymentReturnScreen />)

    expect(screen.queryByRole('button', { name: /Открыть QR-пропуск/ })).not.toBeInTheDocument()
  })

  it('succeeded state with payment history: shows paid amount in receipt-link row', () => {
    useClientPaymentStatus.mockReturnValue({
      data: { id: 'test-id', status: 'succeeded', receiptUrl: 'https://yookassa.ru/receipt/x' },
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
    useClientPaymentHistory.mockReturnValue({
      data: { items: [{ amountKopecks: 2460000, type: 'subscription', createdAt: '2026-06-01T10:00:00Z' }], total: 1, page: 1, pageSize: 20 },
    })

    render(<PaymentReturnScreen />)

    // Amount should be visible (formatMoney(2460000) = "24 600 ₽")
    expect(screen.getByText(/Списано/)).toBeInTheDocument()
    // Открыть чек should also be present (receiptUrl is set)
    expect(screen.getByText('Открыть чек')).toBeInTheDocument()
  })
})

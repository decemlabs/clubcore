/**
 * PaymentReturnScreen anti-oracle Vitest test (Plan 999.4-04 Task 2, W5 behavioral gate).
 *
 * Anti-oracle criterion #1: the success copy ("Готово!" / "Оплата подтверждена.") must
 * NEVER render while status === 'pending'. It must render when status === 'succeeded'.
 *
 * Harness mirrors HomeScreen.identity.test.jsx (render + mock useClientPaymentStatus from @/data).
 */
import React from 'react'
import { describe, it, expect, vi, beforeEach } from 'vitest'
import { render, screen } from '@testing-library/react'

// Mock the swap-seam payment status hook so we drive status without a real API.
const useClientPaymentStatus = vi.fn()
vi.mock('@/data', () => ({
  useClientPaymentStatus: (...args) => useClientPaymentStatus(...args),
}))

// react-router-dom: stub useSearchParams, useNavigate so the component can render in jsdom.
vi.mock('react-router-dom', () => ({
  useSearchParams: () => [new URLSearchParams('payment_id=test-id')],
  useNavigate: () => vi.fn(),
}))

import { PaymentReturnScreen } from './PaymentReturnScreen.jsx'

beforeEach(() => {
  useClientPaymentStatus.mockReset()
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
    expect(screen.queryByText('Готово!')).not.toBeInTheDocument()
    expect(screen.queryByText('Оплата подтверждена.')).not.toBeInTheDocument()
  })

  it('succeeded state: shows "Готово!" and success copy', () => {
    useClientPaymentStatus.mockReturnValue({
      data: { id: 'test-id', status: 'succeeded', receiptUrl: null },
      isLoading: false,
    })

    render(<PaymentReturnScreen />)

    // Success copy must be present
    expect(screen.getByText('Готово!')).toBeInTheDocument()
    expect(screen.getByText('Оплата подтверждена.')).toBeInTheDocument()

    // Pending copy must NOT be present
    expect(screen.queryByText('Ожидаем подтверждение')).not.toBeInTheDocument()
  })
})

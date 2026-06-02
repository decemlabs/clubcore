/**
 * BookingManageSheet cancel-wiring tests (Plan 77-01 / FIX-01).
 *
 * Covers D-77-01..04:
 *   1. Cancel-confirm button calls useCancelBooking().mutateAsync({ bookingId })
 *   2. While isPending=true the confirm button is disabled and shows "Отмена…"
 *   3. After mutateAsync resolves the done-cancel view renders ("Запись отменена")
 *   4. On rejection the view stays on cancel-confirm; generic fallback shown
 *   5. 409 cancel_window_expired → "Окно отмены истекло — обратитесь на ресепшн"
 */
import React from 'react'
import { describe, it, expect, vi, beforeEach } from 'vitest'
import { render, screen, fireEvent, act } from '@testing-library/react'

// ─── Stub only useCancelBooking; keep real calendar/booking mock data ────────
const useCancelBooking = vi.fn()
vi.mock('@/data', async () => {
  const actual = await vi.importActual('@/data')
  return {
    ...actual,
    useCancelBooking: (...args) => useCancelBooking(...args),
  }
})

import { BookingManageSheet } from './BookingManageSheet.jsx'

// Minimal booking fixture with all fields the cancel view reads
const TEST_BOOKING = {
  id: 'bk-123',
  trainer: 'Аня Соколова',
  trainerShort: 'Аня',
  trainerInitials: 'АС',
  trainerColor: '#f59e0b',
  trainerBg: '#fef3c7',
  focus: 'Ноги + спина',
  date: 'Сегодня',
  time: '18:00',
  duration: 60,
  hoursTo: 9,   // ≥ 6 → freeCancel: no "Лучше перенесу" button
  price: 2200,
}

const noop = () => {}
const baseProps = {
  booking: TEST_BOOKING,
  onClose: noop,
  onCancelled: noop,
  onRescheduled: noop,
  onChat: noop,
  onRules: noop,
}

// Default: idle mutation stub
const idleMutation = {
  mutateAsync: vi.fn().mockResolvedValue({}),
  isPending: false,
}

beforeEach(() => {
  useCancelBooking.mockReset()
  useCancelBooking.mockReturnValue(idleMutation)
})

/** Drive the sheet into the cancel-confirm view by clicking the overview ActionRow. */
async function enterCancelView() {
  // The overview has an ActionRow with title "Отменить запись". There may be
  // multiple elements with that text once we enter the cancel view, so we
  // grab all and click the first (the overview button).
  const cancelRows = screen.getAllByText('Отменить запись')
  await act(async () => {
    fireEvent.click(cancelRows[0])
  })
}

// ─── Tests ────────────────────────────────────────────────────────────────────

describe('BookingManageSheet cancel wiring (FIX-01 / D-77-01)', () => {
  it('clicking the cancel-confirm button calls mutateAsync with { bookingId } from booking prop', async () => {
    const mutateAsync = vi.fn().mockResolvedValue({})
    useCancelBooking.mockReturnValue({ mutateAsync, isPending: false })

    render(<BookingManageSheet {...baseProps} />)
    await enterCancelView()

    // In the cancel view the confirm button also reads "Отменить запись"
    const confirmBtn = screen.getByRole('button', { name: 'Отменить запись' })
    await act(async () => {
      fireEvent.click(confirmBtn)
    })

    expect(mutateAsync).toHaveBeenCalledTimes(1)
    expect(mutateAsync).toHaveBeenCalledWith({ bookingId: 'bk-123' })
  })

  it('shows "Отмена…" label and disabled confirm button while isPending=true (D-77-02)', () => {
    useCancelBooking.mockReturnValue({ mutateAsync: vi.fn(), isPending: true })

    render(<BookingManageSheet {...baseProps} />)
    // Directly set view to cancel by rendering in overview and clicking
    const cancelRows = screen.getAllByText('Отменить запись')
    fireEvent.click(cancelRows[0])

    const pendingBtn = screen.getByRole('button', { name: 'Отмена…' })
    expect(pendingBtn).toBeDisabled()
  })

  it('transitions to done-cancel view after mutateAsync resolves (D-77-04)', async () => {
    const mutateAsync = vi.fn().mockResolvedValue({})
    useCancelBooking.mockReturnValue({ mutateAsync, isPending: false })

    render(<BookingManageSheet {...baseProps} />)
    await enterCancelView()

    const confirmBtn = screen.getByRole('button', { name: 'Отменить запись' })
    await act(async () => {
      fireEvent.click(confirmBtn)
    })

    expect(screen.getByText('Запись отменена')).toBeInTheDocument()
    expect(screen.queryByText('Точно отменить?')).not.toBeInTheDocument()
  })

  it('stays on cancel-confirm and shows generic error on rejection (D-77-03)', async () => {
    const mutateAsync = vi.fn().mockRejectedValue(new Error('network error'))
    useCancelBooking.mockReturnValue({ mutateAsync, isPending: false })

    render(<BookingManageSheet {...baseProps} />)
    await enterCancelView()

    const confirmBtn = screen.getByRole('button', { name: 'Отменить запись' })
    await act(async () => {
      fireEvent.click(confirmBtn)
    })

    expect(
      screen.getByText('Не удалось отменить запись. Попробуйте ещё раз.')
    ).toBeInTheDocument()
    expect(screen.queryByText('Запись отменена')).not.toBeInTheDocument()
    // View stays on cancel-confirm
    expect(screen.getByText('Точно отменить?')).toBeInTheDocument()
  })

  it('maps 409 cancel_window_expired to window-expired copy (D-77-03)', async () => {
    const windowExpiredError = Object.assign(new Error('Cancel window expired'), {
      code: 'cancel_window_expired',
    })
    const mutateAsync = vi.fn().mockRejectedValue(windowExpiredError)
    useCancelBooking.mockReturnValue({ mutateAsync, isPending: false })

    render(<BookingManageSheet {...baseProps} />)
    await enterCancelView()

    const confirmBtn = screen.getByRole('button', { name: 'Отменить запись' })
    await act(async () => {
      fireEvent.click(confirmBtn)
    })

    expect(
      screen.getByText('Окно отмены истекло — обратитесь на ресепшн')
    ).toBeInTheDocument()
    expect(screen.queryByText('Запись отменена')).not.toBeInTheDocument()
  })
})

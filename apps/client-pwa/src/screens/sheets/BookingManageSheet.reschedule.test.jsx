/**
 * BookingManageSheet reschedule-wiring tests (Plan 80-03 / RESCH-03).
 *
 * Covers:
 *   1. Selecting a real slot + confirming calls useRescheduleBooking().mutateAsync
 *      with { bookingId, newSlotId } (idempotencyKey may be any string)
 *   2. While isPending=true the confirm button is disabled
 *   3. After mutateAsync resolves the done-reschedule view renders ("Перенесли")
 *   4. On rejection with code 'reschedule_window_expired' window-expired copy shown
 *      and the view stays on reschedule
 *   5. On rejection with code 'slot_already_booked' slot-taken copy shown
 *   6. On rejection with code 'slot_trainer_mismatch' cross-trainer copy shown
 *   7. Slot list comes from stubbed useClientAvailableSlots; mock CALENDAR not used
 */
import React from 'react'
import { describe, it, expect, vi, beforeEach } from 'vitest'
import { render, screen, fireEvent, act } from '@testing-library/react'

// ─── Stub all TanStack hooks used in the component ──────────────────────────
const useRescheduleBooking = vi.fn()
const useClientAvailableSlots = vi.fn()
const useCancelBooking = vi.fn()
vi.mock('@/data', async () => {
  const actual = await vi.importActual('@/data')
  return {
    ...actual,
    useCancelBooking: (...args) => useCancelBooking(...args),
    useRescheduleBooking: (...args) => useRescheduleBooking(...args),
    useClientAvailableSlots: (...args) => useClientAvailableSlots(...args),
  }
})

import { BookingManageSheet } from './BookingManageSheet.jsx'

// Trainer name used in both booking fixture and stubbed slots
const TRAINER_NAME = 'Аня Соколова'

// Minimal booking fixture with all fields the reschedule view reads.
// trainerName is the camelCase field on BookingResponse used for slot filtering.
const TEST_BOOKING = {
  id: 'bk-456',
  trainer: TRAINER_NAME,
  trainerName: TRAINER_NAME,
  trainerShort: 'Аня',
  trainerInitials: 'АС',
  trainerColor: '#f59e0b',
  trainerBg: '#fef3c7',
  focus: 'Ноги + спина',
  date: 'Сегодня',
  time: '18:00',
  duration: 60,
  hoursTo: 9, // ≥ 6 → freeCancel
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

// Two real same-trainer slots returned by the stubbed query
const FUTURE_TIME_1 = new Date(Date.now() + 2 * 24 * 60 * 60 * 1000).toISOString()
const FUTURE_TIME_2 = new Date(Date.now() + 3 * 24 * 60 * 60 * 1000).toISOString()
const STUB_SLOTS_PAGE = {
  items: [
    {
      slotId: 'slot-001',
      trainerId: 'trainer-1',
      trainerName: TRAINER_NAME,
      startTime: FUTURE_TIME_1,
      endTime: FUTURE_TIME_1,
    },
    {
      slotId: 'slot-002',
      trainerId: 'trainer-1',
      trainerName: TRAINER_NAME,
      startTime: FUTURE_TIME_2,
      endTime: FUTURE_TIME_2,
    },
  ],
  total: 2,
  page: 1,
  pageSize: 20,
}

// Default: idle mutation stub
const idleMutation = {
  mutateAsync: vi.fn().mockResolvedValue({}),
  isPending: false,
}

const idleCancelMutation = {
  mutateAsync: vi.fn().mockResolvedValue({}),
  isPending: false,
}

beforeEach(() => {
  useCancelBooking.mockReset()
  useCancelBooking.mockReturnValue(idleCancelMutation)
  useRescheduleBooking.mockReset()
  useRescheduleBooking.mockReturnValue(idleMutation)
  useClientAvailableSlots.mockReset()
  useClientAvailableSlots.mockReturnValue({ data: STUB_SLOTS_PAGE })
})

/** Drive the sheet into the reschedule view by clicking the overview ActionRow. */
async function enterRescheduleView() {
  const rescheduleRow = screen.getByText('Перенести')
  await act(async () => {
    fireEvent.click(rescheduleRow)
  })
}

/** Pick the first available slot in the reschedule view. */
async function pickFirstSlot() {
  // Wait for slot buttons to appear; each slot renders as a button containing the formatted time.
  // We pick any button that is not the action bar (not "Перенести запись").
  const slotButtons = screen.getAllByRole('button').filter(
    btn => btn.textContent && !btn.textContent.includes('Перенести запись') && !btn.textContent.includes('Перенести'),
  )
  const firstSlot = slotButtons.find(btn => btn.closest('.slot-chip') || btn.style?.borderRadius === '12px')
  // Fall back to finding a button that doesn't have a known non-slot label
  const slotBtn = firstSlot ?? slotButtons[slotButtons.length - 1]
  await act(async () => {
    fireEvent.click(slotBtn)
  })
}

// ─── Tests ────────────────────────────────────────────────────────────────────

describe('BookingManageSheet reschedule wiring (RESCH-03 / Plan 80-03)', () => {
  it('slot list is rendered from stubbed useClientAvailableSlots (mock CALENDAR not used)', async () => {
    render(<BookingManageSheet {...baseProps} />)
    await enterRescheduleView()

    // The reschedule view shows "Перенос" in the top bar
    expect(screen.getByText('Перенос')).toBeInTheDocument()
    // Two slot buttons visible (from stubbed slotsPage.items)
    const slotButtons = screen.getAllByRole('button')
    // At least 2 slot items rendered (plus nav button)
    expect(slotButtons.length).toBeGreaterThanOrEqual(3)
  })

  it('selecting a slot and confirming calls mutateAsync with { bookingId, newSlotId }', async () => {
    const mutateAsync = vi.fn().mockResolvedValue({})
    useRescheduleBooking.mockReturnValue({ mutateAsync, isPending: false })

    render(<BookingManageSheet {...baseProps} />)
    await enterRescheduleView()
    await pickFirstSlot()

    const confirmBtn = screen.getByRole('button', { name: /Перенести запись/ })
    await act(async () => {
      fireEvent.click(confirmBtn)
    })

    expect(mutateAsync).toHaveBeenCalledTimes(1)
    const callArgs = mutateAsync.mock.calls[0][0]
    expect(callArgs.bookingId).toBe('bk-456')
    expect(callArgs.newSlotId).toBe('slot-001')
    expect(typeof callArgs.idempotencyKey).toBe('string')
    expect(callArgs.idempotencyKey.length).toBeGreaterThan(0)
  })

  it('disables the confirm button while rescheduleMutation.isPending=true', async () => {
    useRescheduleBooking.mockReturnValue({ mutateAsync: vi.fn(), isPending: true })

    render(<BookingManageSheet {...baseProps} />)
    await enterRescheduleView()
    await pickFirstSlot()

    const confirmBtn = screen.getByRole('button', { name: /Переносим/ })
    expect(confirmBtn).toBeDisabled()
  })

  it('transitions to done-reschedule view after mutateAsync resolves', async () => {
    const mutateAsync = vi.fn().mockResolvedValue({})
    useRescheduleBooking.mockReturnValue({ mutateAsync, isPending: false })

    render(<BookingManageSheet {...baseProps} />)
    await enterRescheduleView()
    await pickFirstSlot()

    const confirmBtn = screen.getByRole('button', { name: /Перенести запись/ })
    await act(async () => {
      fireEvent.click(confirmBtn)
    })

    expect(screen.getByText('Перенесли')).toBeInTheDocument()
    expect(screen.queryByText('Перенос')).not.toBeInTheDocument()
  })

  it('stays on reschedule view and shows window-expired copy on reschedule_window_expired', async () => {
    const err = Object.assign(new Error('window expired'), { code: 'reschedule_window_expired' })
    const mutateAsync = vi.fn().mockRejectedValue(err)
    useRescheduleBooking.mockReturnValue({ mutateAsync, isPending: false })

    render(<BookingManageSheet {...baseProps} />)
    await enterRescheduleView()
    await pickFirstSlot()

    const confirmBtn = screen.getByRole('button', { name: /Перенести запись/ })
    await act(async () => {
      fireEvent.click(confirmBtn)
    })

    expect(
      screen.getByText('Окно переноса истекло — обратитесь на ресепшн'),
    ).toBeInTheDocument()
    expect(screen.queryByText('Перенесли')).not.toBeInTheDocument()
    // View stays on reschedule (top bar still shows)
    expect(screen.getByText('Перенос')).toBeInTheDocument()
  })

  it('shows slot-already-booked copy on slot_already_booked rejection', async () => {
    const err = Object.assign(new Error('slot taken'), { code: 'slot_already_booked' })
    const mutateAsync = vi.fn().mockRejectedValue(err)
    useRescheduleBooking.mockReturnValue({ mutateAsync, isPending: false })

    render(<BookingManageSheet {...baseProps} />)
    await enterRescheduleView()
    await pickFirstSlot()

    const confirmBtn = screen.getByRole('button', { name: /Перенести запись/ })
    await act(async () => {
      fireEvent.click(confirmBtn)
    })

    expect(
      screen.getByText('Этот слот уже занят. Выберите другое время.'),
    ).toBeInTheDocument()
    expect(screen.queryByText('Перенесли')).not.toBeInTheDocument()
    expect(screen.getByText('Перенос')).toBeInTheDocument()
  })

  it('shows cross-trainer copy on slot_trainer_mismatch rejection', async () => {
    const err = Object.assign(new Error('trainer mismatch'), { code: 'slot_trainer_mismatch' })
    const mutateAsync = vi.fn().mockRejectedValue(err)
    useRescheduleBooking.mockReturnValue({ mutateAsync, isPending: false })

    render(<BookingManageSheet {...baseProps} />)
    await enterRescheduleView()
    await pickFirstSlot()

    const confirmBtn = screen.getByRole('button', { name: /Перенести запись/ })
    await act(async () => {
      fireEvent.click(confirmBtn)
    })

    expect(
      screen.getByText('Слот другого тренера — перенос только к тому же тренеру.'),
    ).toBeInTheDocument()
    expect(screen.queryByText('Перенесли')).not.toBeInTheDocument()
    expect(screen.getByText('Перенос')).toBeInTheDocument()
  })

  // WR-80-06 regression: real backend bookings (and the UPCOMING_BOOKING mock)
  // may carry only `trainer`, NOT `trainerName`. Keying the same-trainer slot
  // filter off `b.trainerName` alone compared against `undefined` and silently
  // returned an EMPTY list ("Нет доступных слотов") even when same-trainer slots
  // existed. The filter now normalises to `b.trainerName ?? b.trainer`.
  it('renders same-trainer slots when the booking carries only `trainer` (no trainerName)', async () => {
    // Booking shaped like a real backend booking: `trainer` set, `trainerName` absent.
    const trainerOnlyBooking = { ...TEST_BOOKING, trainerName: undefined }

    render(<BookingManageSheet {...baseProps} booking={trainerOnlyBooking} />)
    await enterRescheduleView()

    // Reschedule view active.
    expect(screen.getByText('Перенос')).toBeInTheDocument()
    // The same-trainer slots are NOT silently filtered out — the empty-state
    // copy must be absent and the slot buttons present.
    expect(
      screen.queryByText('Нет доступных слотов. Попробуйте позже или обратитесь на ресепшн.'),
    ).not.toBeInTheDocument()
    const slotButtons = screen.getAllByRole('button')
    expect(slotButtons.length).toBeGreaterThanOrEqual(3)

    // And the slot is actually selectable + reschedulable (filter matched).
    const mutateAsync = idleMutation.mutateAsync
    await pickFirstSlot()
    const confirmBtn = screen.getByRole('button', { name: /Перенести запись/ })
    await act(async () => {
      fireEvent.click(confirmBtn)
    })
    expect(mutateAsync).toHaveBeenCalledTimes(1)
    expect(mutateAsync.mock.calls[0][0].newSlotId).toBe('slot-001')
  })
})

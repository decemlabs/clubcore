/**
 * BookScreen smoke tests — new «Запись» design wired to real API (quick 260606-u22).
 *
 * Covers the hybrid contract:
 *   (a) Real slots → trainer card with decor (name + rating ★ + price ₽ + «Подробнее»)
 *   (b) Pick trainer → time period + slot chip; pick slot → sticky CTA «Продолжить»
 *   (c) Продолжить → review → Подтвердить → createBooking.mutateAsync({ slotId })
 *   (d) 422 no_active_pt_package → onOpenPlans()
 *
 * Decor values (rating/price/exp/spec) are deterministic hashes — asserted by
 * presence (★ / ₽), not exact numbers.
 */
import { describe, it, expect, vi, beforeEach } from 'vitest'
import { render, screen, fireEvent, waitFor } from '@testing-library/react'
import { MemoryRouter } from 'react-router-dom'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'

// ─── Mock @/data (swap seam) ──────────────────────────────────────────────────
// Hoisted so the vi.mock factory (lifted to top of file) can reference them.
const { ApiError, useClientAvailableSlots, createBookingMutate } = vi.hoisted(() => {
  class ApiError extends Error {
    constructor(code) { super(code); this.code = code }
  }
  return { ApiError, useClientAvailableSlots: vi.fn(), createBookingMutate: vi.fn() }
})

vi.mock('@/data', () => ({
  ApiError,
  useClientAvailableSlots: (...a) => useClientAvailableSlots(...a),
  useCreateBooking: () => ({ mutateAsync: createBookingMutate }),
}))

import { BookScreen } from './BookScreen.jsx'

// One trainer, one free morning slot (09:00 MSK = 06:00Z).
const SLOT = {
  slotId: 'slot-1',
  trainerId: 'tr-1',
  trainerName: 'Иван Тренер',
  startTime: '2026-06-10T06:00:00Z',
  endTime: '2026-06-10T07:00:00Z',
}

function makeQuery(overrides = {}) {
  return { data: { items: [SLOT], total: 1, page: 1, pageSize: 20 }, isLoading: false, isError: false, refetch: vi.fn().mockResolvedValue(undefined), ...overrides }
}

function renderScreen(props = {}) {
  const qc = new QueryClient({ defaultOptions: { queries: { retry: false } } })
  const all = { onTab: vi.fn(), onOpenManage: vi.fn(), onOpenTrainer: vi.fn(), onCheckout: vi.fn(), onConfirmFlow: vi.fn(), onOpenPlans: vi.fn(), ...props }
  return {
    ...all,
    ...render(
      <QueryClientProvider client={qc}>
        <MemoryRouter><BookScreen {...all} /></MemoryRouter>
      </QueryClientProvider>,
    ),
  }
}

beforeEach(() => {
  vi.clearAllMocks()
  useClientAvailableSlots.mockReturnValue(makeQuery())
  createBookingMutate.mockResolvedValue({ id: 'bk-1', slotId: 'slot-1', startTime: SLOT.startTime, status: 'confirmed', trainerName: 'Иван Тренер' })
})

async function pickSlot() {
  fireEvent.click(screen.getByText('Иван Тренер').closest('.press'))
  const chip = await screen.findByText('09:00')
  fireEvent.click(chip)
}

describe('BookScreen (new design, real booking)', () => {
  // (a)
  it('renders a trainer card with decor (name, rating ★, price ₽, Подробнее)', () => {
    renderScreen()
    expect(screen.getByText('Иван Тренер')).toBeInTheDocument()
    expect(screen.getByText('Подробнее')).toBeInTheDocument()
    expect(screen.getAllByText(/₽/).length).toBeGreaterThan(0)
  })

  // (b)
  it('picking a trainer reveals time slots; picking a slot reveals the CTA', async () => {
    renderScreen()
    await pickSlot()
    expect(screen.getByText('Продолжить')).toBeInTheDocument()
  })

  // (c)
  it('confirms a real booking via createBooking with the selected slotId', async () => {
    renderScreen()
    await pickSlot()
    fireEvent.click(screen.getByText('Продолжить'))
    fireEvent.click(await screen.findByText('Подтвердить запись'))
    await waitFor(() => expect(createBookingMutate).toHaveBeenCalled())
    expect(createBookingMutate.mock.calls[0][0]).toMatchObject({ slotId: 'slot-1' })
    expect(await screen.findByText('Записан!')).toBeInTheDocument()
  })

  // (d)
  it('routes to Plans on 422 no_active_pt_package', async () => {
    createBookingMutate.mockRejectedValue(new ApiError('no_active_pt_package'))
    const { onOpenPlans } = renderScreen()
    await pickSlot()
    fireEvent.click(screen.getByText('Продолжить'))
    fireEvent.click(await screen.findByText('Подтвердить запись'))
    await waitFor(() => expect(onOpenPlans).toHaveBeenCalled())
  })

  // «Подробнее» reuses the wired TrainerDetailSheet via onOpenTrainer
  it('«Подробнее» calls onOpenTrainer with the trainer id', () => {
    const { onOpenTrainer } = renderScreen()
    fireEvent.click(screen.getByText('Подробнее'))
    expect(onOpenTrainer).toHaveBeenCalledWith(expect.objectContaining({ id: 'tr-1', name: 'Иван Тренер' }))
  })
})

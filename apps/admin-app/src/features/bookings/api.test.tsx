/**
 * Bookings domain API hooks — Idempotency-Key, IDOR, and slot-conflict tests
 * (Phase 102-03 SCH-02, T-102-BK-IDEM, T-102-BK-IDOR, T-102-BK-RACE).
 *
 * Tests:
 *  1. useCreateBooking: fresh per-attempt Idempotency-Key (NOT hoisted at hook init).
 *  2. useCreateBooking: slot_already_booked is NOT toasted (caller handles inline).
 *  3. useCancelBooking: fresh per-attempt Idempotency-Key.
 *  4. useCompleteBooking: fresh per-attempt Idempotency-Key.
 *  5. useCompleteBooking: sends exactly {ptPackageId,trainerId,performedAt,bookingId} — no clientId.
 */
import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest'
import { renderHook, act } from '@testing-library/react'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import type { ReactNode } from 'react'

// ---------------------------------------------------------------------------
// Module mock — staffRequest
// ---------------------------------------------------------------------------

vi.mock('@/api/client', async (importOriginal) => {
  const actual = await importOriginal<{ staffRequest: unknown; ApiError: unknown }>()
  return {
    ...actual,
    staffRequest: vi.fn(),
    ApiError: actual.ApiError,
  }
})

// Mock sonner toast to detect if it was called
vi.mock('sonner', () => ({
  toast: Object.assign(vi.fn(), {
    success: vi.fn(),
    error: vi.fn(),
  }),
}))

// Dynamically import after mock is set up
const { staffRequest } = await import('@/api/client')
const { useCreateBooking, useCancelBooking, useCompleteBooking } = await import('./api')
const { ApiError } = await import('@/api/client')
const { toast } = await import('sonner')

const mockStaffRequest = vi.mocked(staffRequest)
const mockToastError = vi.mocked(toast.error)

// ---------------------------------------------------------------------------
// Helper — QueryClientProvider wrapper for renderHook
// ---------------------------------------------------------------------------

function makeWrapper() {
  const queryClient = new QueryClient({
    defaultOptions: {
      queries: { retry: false },
      mutations: { retry: false },
    },
  })
  return function Wrapper({ children }: { children: ReactNode }) {
    return <QueryClientProvider client={queryClient}>{children}</QueryClientProvider>
  }
}

// ---------------------------------------------------------------------------
// Tests
// ---------------------------------------------------------------------------

beforeEach(() => {
  vi.clearAllMocks()
})

afterEach(() => {
  vi.restoreAllMocks()
})

describe('T-102-BK-IDEM: useCreateBooking — fresh Idempotency-Key per attempt', () => {
  it('generates a different Idempotency-Key on each mutate call', async () => {
    mockStaffRequest.mockResolvedValue({
      data: {
        id: 'booking-1',
        slotId: 'slot-1',
        clientId: 'client-1',
        ptPackageId: 'pkg-1',
        status: 'confirmed',
        createdAt: '2026-06-13T00:00:00Z',
      },
    })

    const wrapper = makeWrapper()
    const { result } = renderHook(() => useCreateBooking(), { wrapper })
    const body = { slotId: 'slot-1', clientId: 'client-1', ptPackageId: 'pkg-1' }

    await act(async () => { await result.current.mutateAsync(body) })
    await act(async () => { await result.current.mutateAsync(body) })

    expect(mockStaffRequest).toHaveBeenCalledTimes(2)
    const h1 = (mockStaffRequest.mock.calls[0]?.[2]?.headers as Record<string, string> | undefined)?.['Idempotency-Key']
    const h2 = (mockStaffRequest.mock.calls[1]?.[2]?.headers as Record<string, string> | undefined)?.['Idempotency-Key']
    expect(h1).toBeTruthy()
    expect(h2).toBeTruthy()
    expect(h1).not.toBe(h2)
  })
})

describe('T-102-BK-RACE: useCreateBooking — slot_already_booked NOT toasted', () => {
  it('does NOT call toast.error on 409 slot_already_booked (caller handles inline)', async () => {
    const conflictErr = new ApiError('slot_already_booked', 'Слот уже занят')
    mockStaffRequest.mockRejectedValueOnce(conflictErr)

    const wrapper = makeWrapper()
    const { result } = renderHook(() => useCreateBooking(), { wrapper })

    let thrownErr: unknown
    await act(async () => {
      try {
        await result.current.mutateAsync({ slotId: 'slot-1', clientId: 'client-1', ptPackageId: 'pkg-1' })
      } catch (err) {
        thrownErr = err
      }
    })

    // The error must propagate
    expect(thrownErr).toBeInstanceOf(ApiError)
    expect((thrownErr as InstanceType<typeof ApiError>).code).toBe('slot_already_booked')
    // toast.error must NOT be called for this code
    expect(mockToastError).not.toHaveBeenCalled()
  })

  it('does NOT call toast.error on 409 slot_not_available (caller handles inline)', async () => {
    const conflictErr = new ApiError('slot_not_available', 'Слот недоступен')
    mockStaffRequest.mockRejectedValueOnce(conflictErr)

    const wrapper = makeWrapper()
    const { result } = renderHook(() => useCreateBooking(), { wrapper })

    let thrownErr: unknown
    await act(async () => {
      try {
        await result.current.mutateAsync({ slotId: 'slot-1', clientId: 'client-1', ptPackageId: 'pkg-1' })
      } catch (err) {
        thrownErr = err
      }
    })

    expect(thrownErr).toBeInstanceOf(ApiError)
    expect(mockToastError).not.toHaveBeenCalled()
  })
})

describe('T-102-BK-IDEM: useCancelBooking — fresh Idempotency-Key per attempt', () => {
  it('generates a different Idempotency-Key on each cancel call', async () => {
    mockStaffRequest.mockResolvedValue(undefined)

    const wrapper = makeWrapper()
    const { result } = renderHook(() => useCancelBooking(), { wrapper })
    const vars = { bookingId: 'booking-1', body: { reason: 'Отменено администратором' } }

    await act(async () => { await result.current.mutateAsync(vars) })
    await act(async () => { await result.current.mutateAsync(vars) })

    expect(mockStaffRequest).toHaveBeenCalledTimes(2)
    const h1 = (mockStaffRequest.mock.calls[0]?.[2]?.headers as Record<string, string> | undefined)?.['Idempotency-Key']
    const h2 = (mockStaffRequest.mock.calls[1]?.[2]?.headers as Record<string, string> | undefined)?.['Idempotency-Key']
    expect(h1).toBeTruthy()
    expect(h2).toBeTruthy()
    expect(h1).not.toBe(h2)
  })
})

describe('T-102-BK-IDEM: useCompleteBooking — fresh Idempotency-Key per attempt', () => {
  it('generates a different Idempotency-Key on each complete call', async () => {
    mockStaffRequest.mockResolvedValue({
      data: {
        id: 'session-1',
        ptPackageId: 'pkg-1',
        trainerId: 'trainer-1',
        performedAt: '2026-06-13T10:00:00Z',
        bookingId: 'booking-1',
        createdAt: '2026-06-13T10:00:00Z',
        sessionsUsed: 1,
      },
    })

    const wrapper = makeWrapper()
    const { result } = renderHook(() => useCompleteBooking(), { wrapper })
    const vars = { ptPackageId: 'pkg-1', trainerId: 'trainer-1', bookingId: 'booking-1' }

    await act(async () => { await result.current.mutateAsync(vars) })
    await act(async () => { await result.current.mutateAsync(vars) })

    expect(mockStaffRequest).toHaveBeenCalledTimes(2)
    const h1 = (mockStaffRequest.mock.calls[0]?.[2]?.headers as Record<string, string> | undefined)?.['Idempotency-Key']
    const h2 = (mockStaffRequest.mock.calls[1]?.[2]?.headers as Record<string, string> | undefined)?.['Idempotency-Key']
    expect(h1).toBeTruthy()
    expect(h2).toBeTruthy()
    expect(h1).not.toBe(h2)
  })
})

describe('T-102-BK-COMPLETE: useCompleteBooking — exact body, no clientId', () => {
  it('sends exactly {ptPackageId, trainerId, performedAt, bookingId} — no clientId', async () => {
    mockStaffRequest.mockResolvedValue({
      data: {
        id: 'session-1',
        ptPackageId: 'pkg-1',
        trainerId: 'trainer-1',
        performedAt: '2026-06-13T10:00:00Z',
        bookingId: 'booking-1',
        createdAt: '2026-06-13T10:00:00Z',
        sessionsUsed: 1,
      },
    })

    const wrapper = makeWrapper()
    const { result } = renderHook(() => useCompleteBooking(), { wrapper })

    await act(async () => {
      await result.current.mutateAsync({
        ptPackageId: 'pkg-1',
        trainerId: 'trainer-1',
        bookingId: 'booking-1',
      })
    })

    expect(mockStaffRequest).toHaveBeenCalledTimes(1)
    const sentBody = mockStaffRequest.mock.calls[0]?.[2]?.body as Record<string, unknown> | undefined

    // Must have required fields
    expect(sentBody?.ptPackageId).toBe('pkg-1')
    expect(sentBody?.trainerId).toBe('trainer-1')
    expect(sentBody?.bookingId).toBe('booking-1')
    expect(typeof sentBody?.performedAt).toBe('string')

    // Must NOT have clientId (backend extra='forbid')
    expect(sentBody).not.toHaveProperty('clientId')
  })
})

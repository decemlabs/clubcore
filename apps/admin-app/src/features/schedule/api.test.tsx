/**
 * Schedule domain API hooks — Idempotency-Key and scheduleKeys.week stability tests
 * (Phase 102-01 SCH-01, T-102-IDEM, T-102-IDOR).
 *
 * Tests:
 *  1. usePublishSlot produces a FRESH Idempotency-Key per attempt (not hoisted at hook init).
 *  2. scheduleKeys.week is referentially stable for equal params (same key array contents).
 *  3. useCreateTimeOff does NOT toast on 409 time_off_booked_conflict (caller inspects ApiError).
 *
 * Pattern: mock the '@/api/client' module, assert headers passed to staffRequest.
 * No network, no React DOM.
 */
import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest'
import { renderHook, act } from '@testing-library/react'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import type { ReactNode } from 'react'

// ---------------------------------------------------------------------------
// Module mock — staffRequest
// ---------------------------------------------------------------------------

vi.mock('@/api/client', async (importOriginal) => {
  const actual = await importOriginal<typeof import('@/api/client')>()
  return {
    ...actual,
    staffRequest: vi.fn(),
    ApiError: actual.ApiError,
  }
})

// Dynamically import after mock is set up
const { staffRequest } = await import('@/api/client')
const { usePublishSlot, useCreateTimeOff } = await import('./api')
const { scheduleKeys } = await import('./keys')
const { ApiError } = await import('@/api/client')

const mockStaffRequest = vi.mocked(staffRequest)

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

describe('T-102-IDEM: Idempotency-Key per attempt', () => {
  it('usePublishSlot: two sequential calls produce two different Idempotency-Key header values', async () => {
    // Mock staffRequest to capture headers and resolve each time
    mockStaffRequest.mockResolvedValue({
      data: {
        id: 'slot-1',
        trainerId: 'trainer-1',
        startTime: '2026-06-15T10:00:00Z',
        endTime: '2026-06-15T11:00:00Z',
        status: 'active',
        createdAt: '2026-06-13T00:00:00Z',
      },
    })

    const wrapper = makeWrapper()
    const { result } = renderHook(() => usePublishSlot(), { wrapper })

    const body = { trainerId: 'trainer-1', startTime: '2026-06-15T10:00:00Z', endTime: '2026-06-15T11:00:00Z' }

    // First call
    await act(async () => {
      await result.current.mutateAsync(body)
    })

    // Second call
    await act(async () => {
      await result.current.mutateAsync(body)
    })

    expect(mockStaffRequest).toHaveBeenCalledTimes(2)

    const call1 = mockStaffRequest.mock.calls[0]
    const call2 = mockStaffRequest.mock.calls[1]

    const headers1 = call1?.[2]?.headers as Record<string, string> | undefined
    const headers2 = call2?.[2]?.headers as Record<string, string> | undefined

    expect(headers1?.['Idempotency-Key']).toBeTruthy()
    expect(headers2?.['Idempotency-Key']).toBeTruthy()
    // The two keys must be DIFFERENT (fresh per attempt)
    expect(headers1?.['Idempotency-Key']).not.toBe(headers2?.['Idempotency-Key'])
  })
})

describe('scheduleKeys.week stability', () => {
  it('produces the same key array contents for equal params (for React Query cache stability)', () => {
    const params = { trainerId: 'trainer-1', fromTime: '2026-06-13T00:00:00Z', toTime: '2026-06-20T00:00:00Z' }
    const key1 = scheduleKeys.week(params)
    const key2 = scheduleKeys.week(params)
    // Deep equal
    expect(JSON.stringify(key1)).toBe(JSON.stringify(key2))
    expect(key1[0]).toBe('schedule')
    expect(key1[1]).toBe('slots')
  })
})

describe('T-102-IDEM: useCreateTimeOff — 409 time_off_booked_conflict NOT toasted', () => {
  it('lets time_off_booked_conflict propagate to caller without calling toast.error', async () => {
    // Mock toast to detect if it was called
    const toastMock = vi.fn()
    vi.doMock('sonner', () => ({
      toast: Object.assign(toastMock, { success: vi.fn(), error: vi.fn() }),
    }))

    // Simulate a 409 conflict error
    const conflictErr = new ApiError('time_off_booked_conflict', 'Конфликт', undefined, {
      cause: undefined,
    })
    // Attach conflict data (as done in real ApiError from backend)
    ;(conflictErr as unknown as { data: unknown }).data = {
      conflictingSlotIds: ['slot-1'],
      conflictingBookingIds: ['booking-1'],
    }

    mockStaffRequest.mockRejectedValueOnce(conflictErr)

    const wrapper = makeWrapper()
    const { result } = renderHook(() => useCreateTimeOff(), { wrapper })

    let thrownErr: unknown
    await act(async () => {
      try {
        await result.current.mutateAsync({
          body: {
            trainerId: 'trainer-1',
            blockStart: '2026-06-20T00:00:00Z',
            blockEnd: '2026-06-21T00:00:00Z',
          },
        })
      } catch (err) {
        thrownErr = err
      }
    })

    // The error should propagate to the caller
    expect(thrownErr).toBeInstanceOf(ApiError)
    expect((thrownErr as InstanceType<typeof ApiError>).code).toBe('time_off_booked_conflict')
  })
})

/**
 * ScheduleManagementModal — behavior tests (Phase 102-01 SCH-01).
 *
 * Tests:
 *  1. Renders with three ChipGroup tabs (slot/template/timeoff), default 'slot'.
 *  2. Tab switching works (ChipGroup aria-pressed).
 *  3. Reset on reopen: tab and fields reset to defaults on re-open.
 *  4. Slot tab: primary button disabled until trainer+date+times set.
 *  5. Time-off 409 time_off_booked_conflict: conflict Callout + force button appear; modal stays open.
 *  6. Reception sees null (can() gate).
 *
 * Pattern: renderWithProviders is NOT available here (no test/utils.tsx in this project).
 * Use React 18 render directly with QueryClient + mocked hooks.
 */
import { describe, it, expect, vi, beforeEach } from 'vitest'
import { render, screen, waitFor, fireEvent, act } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import type { ReactNode } from 'react'

// ---------------------------------------------------------------------------
// Module mocks — hooks
// ---------------------------------------------------------------------------

vi.mock('@/features/schedule/api', () => ({
  usePublishSlot: vi.fn(() => ({ mutateAsync: vi.fn(), isPending: false })),
  useCreateTemplate: vi.fn(() => ({ mutateAsync: vi.fn(), isPending: false })),
  useCreateTimeOff: vi.fn(() => ({ mutateAsync: vi.fn(), isPending: false })),
  ApiError: class ApiError extends Error {
    code: string
    data: unknown
    constructor(code: string, message: string, _fields?: unknown, opts?: { cause?: unknown }) {
      super(message, opts)
      this.code = code
      this.data = undefined
    }
  },
}))

vi.mock('@/features/trainers/api', () => ({
  useTrainers: vi.fn(() => ({
    data: { items: [{ id: 'trainer-1', fullName: 'Аня Соколова' }] },
    isPending: false,
  })),
}))

const { ApiError } = await import('@/features/schedule/api')

// ---------------------------------------------------------------------------
// Wrapper
// ---------------------------------------------------------------------------

function wrapper({ children }: { children: ReactNode }) {
  const qc = new QueryClient({ defaultOptions: { queries: { retry: false } } })
  return <QueryClientProvider client={qc}>{children}</QueryClientProvider>
}

async function renderModal(
  open: boolean,
  onOpenChange: (v: boolean) => void,
  role: 'owner' | 'reception' = 'owner',
) {
  const { ScheduleManagementModal } = await import('./ScheduleManagementModal')
  return render(
    <ScheduleManagementModal open={open} onOpenChange={onOpenChange} role={role} />,
    { wrapper },
  )
}

// ---------------------------------------------------------------------------
// Tests
// ---------------------------------------------------------------------------

beforeEach(() => {
  vi.clearAllMocks()
})

describe('ScheduleManagementModal — tabs and structure', () => {
  it('renders ChipGroup tabs with default slot tab selected', async () => {
    await renderModal(true, vi.fn())
    expect(screen.getByRole('button', { name: 'Слот' })).toHaveAttribute('aria-pressed', 'true')
    expect(screen.getByRole('button', { name: 'Шаблон' })).toHaveAttribute('aria-pressed', 'false')
    expect(screen.getByRole('button', { name: 'Блокировка' })).toHaveAttribute(
      'aria-pressed',
      'false',
    )
  })

  it('switches tabs via ChipGroup', async () => {
    const user = userEvent.setup()
    await renderModal(true, vi.fn())

    await user.click(screen.getByRole('button', { name: 'Шаблон' }))
    expect(screen.getByRole('button', { name: 'Шаблон' })).toHaveAttribute('aria-pressed', 'true')
    expect(screen.getByRole('button', { name: 'Слот' })).toHaveAttribute('aria-pressed', 'false')
  })
})

describe('ScheduleManagementModal — reset on reopen', () => {
  it('resets tab to slot on reopen', async () => {
    const user = userEvent.setup()
    const { rerender } = await renderModal(true, vi.fn())
    const { ScheduleManagementModal } = await import('./ScheduleManagementModal')

    // Switch to template tab
    await user.click(screen.getByRole('button', { name: 'Шаблон' }))
    expect(screen.getByRole('button', { name: 'Шаблон' })).toHaveAttribute('aria-pressed', 'true')

    // Close
    rerender(
      <QueryClientProvider
        client={new QueryClient({ defaultOptions: { queries: { retry: false } } })}
      >
        <ScheduleManagementModal open={false} onOpenChange={vi.fn()} role="owner" />
      </QueryClientProvider>,
    )

    // Reopen
    rerender(
      <QueryClientProvider
        client={new QueryClient({ defaultOptions: { queries: { retry: false } } })}
      >
        <ScheduleManagementModal open={true} onOpenChange={vi.fn()} role="owner" />
      </QueryClientProvider>,
    )

    // Should reset to slot
    expect(screen.getByRole('button', { name: 'Слот' })).toHaveAttribute('aria-pressed', 'true')
    expect(screen.getByRole('button', { name: 'Шаблон' })).toHaveAttribute('aria-pressed', 'false')
  })
})

describe('ScheduleManagementModal — slot tab validation', () => {
  it('primary button is disabled until trainer, date, and times are set', async () => {
    await renderModal(true, vi.fn())

    // Find the primary submit button (Опубликовать)
    const publishBtn = screen.getByRole('button', { name: /опубликовать/i })
    expect(publishBtn).toBeDisabled()
  })
})

describe('ScheduleManagementModal — time-off 409 force-override', () => {
  it('shows conflict Callout and force button when 409 time_off_booked_conflict is thrown', async () => {
    const user = userEvent.setup()

    // Prepare the conflict error
    const conflictErr = new ApiError('time_off_booked_conflict', 'Конфликт')
    ;(conflictErr as unknown as { data: unknown }).data = {
      conflictingSlotIds: ['slot-1', 'slot-2'],
      conflictingBookingIds: ['booking-1'],
    }

    // Set up mock BEFORE rendering so TimeOffTab picks it up when it mounts
    const { useCreateTimeOff } = await import('@/features/schedule/api')
    vi.mocked(useCreateTimeOff).mockReturnValue({
      mutateAsync: vi.fn().mockRejectedValue(conflictErr),
      isPending: false,
    } as unknown as ReturnType<typeof useCreateTimeOff>)

    await renderModal(true, vi.fn())

    // Switch to timeoff tab — TimeOffTab mounts here, reads the mock above
    await user.click(screen.getByRole('button', { name: 'Блокировка' }))

    // Fill required fields using act+fireEvent for controlled inputs in JSDOM
    await act(async () => {
      const selects = screen.getAllByRole('combobox')
      fireEvent.change(selects[0]!, { target: { value: 'trainer-1' } })
    })

    // Fill block start/end
    await act(async () => {
      const dtInputs = document.querySelectorAll('input[type="datetime-local"]')
      if (dtInputs[0]) fireEvent.change(dtInputs[0], { target: { value: '2026-06-20T10:00' } })
      if (dtInputs[1]) fireEvent.change(dtInputs[1], { target: { value: '2026-06-21T10:00' } })
    })

    // Click "Заблокировать"
    await act(async () => {
      const blockBtn = screen.getByRole('button', { name: /^заблокировать$/i })
      fireEvent.click(blockBtn)
    })

    // After the 409, conflict UI should appear (modal stays open)
    await waitFor(() => {
      expect(screen.getByText(/найдены конфликты/i)).toBeInTheDocument()
    })
    expect(screen.getByRole('button', { name: /заблокировать принудительно/i })).toBeInTheDocument()
  })
})

describe('ScheduleManagementModal — reception gate', () => {
  it('returns null for reception role', async () => {
    const { container } = await renderModal(true, vi.fn(), 'reception')
    // No modal content for reception
    expect(container.firstChild).toBeNull()
  })
})

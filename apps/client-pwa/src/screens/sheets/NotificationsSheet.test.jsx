/**
 * NotificationsSheet tests (Phase 87 INBOX-05).
 *
 * Covers:
 *   (a) Rows render title/body/timestamp
 *   (b) Unread dot present for readAt===null, absent when readAt is set
 *   (c) Empty state when items === 0
 *   (d) "Всё прочитано" hidden when unreadCount===0, shown when unreadCount>0
 *   (e) Mark-all click triggers mutation + optimistic dot removal
 *   (f) Mark-single-on-open fires for first-page unread after 800ms debounce
 *   (g) Error state copy renders on isError
 */
import React from 'react'
import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest'
import { render, screen, fireEvent, act, waitFor } from '@testing-library/react'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'

// ─── Wrap with QueryClientProvider ───────────────────────────────────────────
function renderSheet(ui) {
  const queryClient = new QueryClient({ defaultOptions: { queries: { retry: false } } })
  return render(<QueryClientProvider client={queryClient}>{ui}</QueryClientProvider>)
}

// ─── Mock @/data hooks ────────────────────────────────────────────────────────
const useClientNotifications = vi.fn()
const markReadMutate = vi.fn()
const markAllReadMutate = vi.fn()

const useMarkNotificationRead = vi.fn()
const useMarkAllNotificationsRead = vi.fn()

vi.mock('@/data', async () => {
  const actual = await vi.importActual('@/data')
  return {
    ...actual,
    useClientNotifications: (...args) => useClientNotifications(...args),
    useMarkNotificationRead: (...args) => useMarkNotificationRead(...args),
    useMarkAllNotificationsRead: (...args) => useMarkAllNotificationsRead(...args),
  }
})

// ─── Stub sub-components not under test ──────────────────────────────────────
vi.mock('@/components/Icon.jsx', () => ({
  Icon: ({ name }) => <span data-testid={`icon-${name}`} />,
}))
vi.mock('@/components/StatusBar.jsx', () => ({
  StatusBar: () => null,
}))
vi.mock('@/components/PullToRefresh.jsx', () => ({
  PullToRefresh: ({ children }) => <div>{children}</div>,
}))
vi.mock('@/screens/sheets/ProfileExtraSheets.jsx', async () => {
  const actual = await vi.importActual('@/screens/sheets/ProfileExtraSheets.jsx')
  return {
    ...actual,
    SubSheetHeader: ({ title, onClose }) => (
      <div>
        <span>{title}</span>
        <button onClick={onClose}>Закрыть</button>
      </div>
    ),
  }
})
// No sonner mock needed — PWA uses local in-sheet toast state

import { NotificationsSheet } from './NotificationsSheet.jsx'

// ─── Sample data ──────────────────────────────────────────────────────────────
const UNREAD_ITEM = {
  id: 'notif-1',
  kind: 'booking_confirmed',
  title: 'Бронь подтверждена',
  body: '10 июня, 10:00 — Иван Тренер',
  readAt: null,
  createdAt: new Date(Date.now() - 3600_000).toISOString(), // 1 hour ago
}

const READ_ITEM = {
  id: 'notif-2',
  kind: 'payment_succeeded',
  title: 'Оплата прошла',
  body: 'Абонемент Базовый, 3000 ₽',
  readAt: '2026-06-01T10:00:00Z',
  createdAt: new Date(Date.now() - 86400_000).toISOString(), // 1 day ago
}

function makeQuery(overrides = {}) {
  return {
    data: undefined,
    isFetching: false,
    isError: false,
    refetch: vi.fn().mockResolvedValue(undefined),
    ...overrides,
  }
}

function makeMutation(mutateFn = vi.fn()) {
  return { mutate: mutateFn }
}

// ─── Setup / teardown ─────────────────────────────────────────────────────────
beforeEach(() => {
  vi.clearAllMocks()
  vi.useFakeTimers()

  // Default mutation mocks
  useMarkNotificationRead.mockReturnValue(makeMutation(markReadMutate))
  useMarkAllNotificationsRead.mockReturnValue(makeMutation(markAllReadMutate))
})

afterEach(() => {
  vi.useRealTimers()
})

// ─── Tests ────────────────────────────────────────────────────────────────────
describe('NotificationsSheet', () => {

  // (a) Rows render title/body/timestamp
  it('renders notification title, body, and timestamp', () => {
    useClientNotifications.mockReturnValue(makeQuery({
      data: { items: [UNREAD_ITEM], total: 1, page: 1, pageSize: 10, unreadCount: 1 },
    }))

    renderSheet(<NotificationsSheet onClose={vi.fn()} />)

    expect(screen.getByText('Бронь подтверждена')).toBeInTheDocument()
    expect(screen.getByText('10 июня, 10:00 — Иван Тренер')).toBeInTheDocument()
    // Timestamp: 1 hour ago → "1 ч. назад"
    expect(screen.getByText('1 ч. назад')).toBeInTheDocument()
  })

  // (b) Unread dot present for readAt===null, absent when readAt is set
  it('renders unread dot for readAt===null and no dot for read items', () => {
    useClientNotifications.mockReturnValue(makeQuery({
      data: {
        items: [UNREAD_ITEM, READ_ITEM],
        total: 2, page: 1, pageSize: 10, unreadCount: 1,
      },
    }))

    renderSheet(<NotificationsSheet onClose={vi.fn()} />)

    const dots = screen.queryAllByLabelText('непрочитано')
    // Only the unread item should have the dot
    expect(dots).toHaveLength(1)
  })

  // (c) Empty state when items === 0
  it('renders empty state heading and hint when no items', () => {
    useClientNotifications.mockReturnValue(makeQuery({
      data: { items: [], total: 0, page: 1, pageSize: 10, unreadCount: 0 },
    }))

    renderSheet(<NotificationsSheet onClose={vi.fn()} />)

    expect(screen.getByText('Нет уведомлений')).toBeInTheDocument()
    expect(screen.getByText(/Здесь будут появляться уведомления/)).toBeInTheDocument()
  })

  // (d) "Всё прочитано" hidden when unreadCount===0
  it('does not render "Всё прочитано" when unreadCount is 0', () => {
    useClientNotifications.mockReturnValue(makeQuery({
      data: { items: [READ_ITEM], total: 1, page: 1, pageSize: 10, unreadCount: 0 },
    }))

    renderSheet(<NotificationsSheet onClose={vi.fn()} />)

    expect(screen.queryByText('Всё прочитано')).not.toBeInTheDocument()
  })

  // (d) "Всё прочитано" shown when unreadCount > 0
  it('renders "Всё прочитано" button when unreadCount > 0', () => {
    useClientNotifications.mockReturnValue(makeQuery({
      data: { items: [UNREAD_ITEM], total: 1, page: 1, pageSize: 10, unreadCount: 1 },
    }))

    renderSheet(<NotificationsSheet onClose={vi.fn()} />)

    expect(screen.getByText('Всё прочитано')).toBeInTheDocument()
  })

  // (e) Mark-all click triggers mutation + optimistic dot removal
  it('clicking "Всё прочитано" calls mutation and removes unread dots optimistically', async () => {
    useClientNotifications.mockReturnValue(makeQuery({
      data: { items: [UNREAD_ITEM], total: 1, page: 1, pageSize: 10, unreadCount: 1 },
    }))

    renderSheet(<NotificationsSheet onClose={vi.fn()} />)

    // Dot is visible before clicking
    expect(screen.getByLabelText('непрочитано')).toBeInTheDocument()

    const markAllBtn = screen.getByText('Всё прочитано')
    fireEvent.click(markAllBtn)

    // Mutation was called
    expect(markAllReadMutate).toHaveBeenCalled()

    // Optimistic: dot removed immediately
    expect(screen.queryByLabelText('непрочитано')).not.toBeInTheDocument()
  })

  // (f) Mark-single-on-open fires for first-page unread after 800ms
  it('fires mark-single-read after 800ms for first-page unread items', async () => {
    useClientNotifications.mockReturnValue(makeQuery({
      data: { items: [UNREAD_ITEM], total: 1, page: 1, pageSize: 10, unreadCount: 1 },
    }))

    renderSheet(<NotificationsSheet onClose={vi.fn()} />)

    // Not yet called (within debounce window)
    expect(markReadMutate).not.toHaveBeenCalled()

    // Advance timer past 800ms
    act(() => {
      vi.advanceTimersByTime(800)
    })

    expect(markReadMutate).toHaveBeenCalledWith(UNREAD_ITEM.id)
  })

  // (f) Already-read items are NOT marked on open
  it('does not fire mark-read for items that are already read', () => {
    useClientNotifications.mockReturnValue(makeQuery({
      data: { items: [READ_ITEM], total: 1, page: 1, pageSize: 10, unreadCount: 0 },
    }))

    renderSheet(<NotificationsSheet onClose={vi.fn()} />)

    act(() => {
      vi.advanceTimersByTime(800)
    })

    expect(markReadMutate).not.toHaveBeenCalled()
  })

  // (e-rollback) CR-01: mark-all error rollback does NOT over-count already-read items
  it('CR-01: onError rollback restores only items that were unread before mark-all, not already-read ones', async () => {
    // Setup: one unread item and one already-read item
    const onErrorCallback = { fn: null }
    markAllReadMutate.mockImplementation((_, { onError } = {}) => {
      // Capture onError for manual invocation
      onErrorCallback.fn = onError
    })

    useClientNotifications.mockReturnValue(makeQuery({
      data: {
        items: [UNREAD_ITEM, READ_ITEM],
        total: 2, page: 1, pageSize: 10, unreadCount: 1,
      },
    }))

    renderSheet(<NotificationsSheet onClose={vi.fn()} />)

    // Verify initial state: 1 unread dot
    expect(screen.queryAllByLabelText('непрочитано')).toHaveLength(1)

    // Click mark-all — triggers optimistic update
    fireEvent.click(screen.getByText('Всё прочитано'))

    // After optimistic update: 0 unread dots
    expect(screen.queryAllByLabelText('непрочитано')).toHaveLength(0)

    // Trigger onError rollback
    act(() => {
      onErrorCallback.fn?.()
    })

    // After rollback: the original unread dot should be restored
    expect(screen.queryAllByLabelText('непрочитано')).toHaveLength(1)

    // The already-read item (READ_ITEM) must NOT have an unread dot after rollback
    // (CR-01: old code inflated optimisticReadIds by adding all IDs including already-read)
    const dots = screen.queryAllByLabelText('непрочитано')
    expect(dots).toHaveLength(1)
  })

  // (g) Error state copy renders on isError
  it('renders error copy when query fails', () => {
    useClientNotifications.mockReturnValue(makeQuery({
      isError: true,
      data: undefined,
    }))

    renderSheet(<NotificationsSheet onClose={vi.fn()} />)

    expect(screen.getByText(/Не удалось загрузить уведомления/)).toBeInTheDocument()
    expect(screen.getByText(/Потяните вниз, чтобы повторить/)).toBeInTheDocument()
  })

})

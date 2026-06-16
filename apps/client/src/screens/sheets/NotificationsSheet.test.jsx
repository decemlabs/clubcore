/**
 * NotificationsSheet tests (Phase 87 INBOX-05) — integrated design (quick 260606-szy).
 *
 * Covers:
 *   (a) Rows render title/body + a timestamp
 *   (b) Unread dot present for readAt===null, absent when readAt is set
 *   (c) Empty state ("Всё прочитано" heading + hint)
 *   (d) Header "Прочитать" disabled when unreadCount===0, enabled when >0
 *   (e) Mark-all click triggers mutation + optimistic dot removal
 *   (e-rollback) onError rollback restores the unread dot
 *   (f) Segmented filter "Новые" shows only unread items
 *   (g) Error state copy renders on isError
 *
 * Gestures (swipe / long-press) are exercised in the browser, not jsdom.
 */
import { describe, it, expect, vi, beforeEach } from 'vitest'
import { render, screen, fireEvent, act } from '@testing-library/react'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'

function renderSheet(ui) {
  const queryClient = new QueryClient({ defaultOptions: { queries: { retry: false } } })
  return render(<QueryClientProvider client={queryClient}>{ui}</QueryClientProvider>)
}

// ─── Mock @/data hooks (swap seam) ───────────────────────────────────────────
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

import { NotificationsSheet } from './NotificationsSheet.jsx'

// ─── Sample data ──────────────────────────────────────────────────────────────
const UNREAD_ITEM = {
  id: 'notif-1',
  kind: 'booking_confirmed',
  title: 'Бронь подтверждена',
  body: '10 июня, 10:00 — Иван Тренер',
  readAt: null,
  createdAt: new Date(Date.now() - 3600_000).toISOString(),
}
const READ_ITEM = {
  id: 'notif-2',
  kind: 'payment_succeeded',
  title: 'Оплата прошла',
  body: 'Абонемент Базовый, 3000 ₽',
  readAt: '2026-06-01T10:00:00Z',
  createdAt: new Date(Date.now() - 86400_000).toISOString(),
}

function makeQuery(overrides = {}) {
  return {
    data: undefined,
    isLoading: false,
    isFetching: false,
    isError: false,
    refetch: vi.fn().mockResolvedValue(undefined),
    ...overrides,
  }
}
const makeMutation = (mutateFn = vi.fn()) => ({ mutate: mutateFn })

// Header "Прочитать" button (role disambiguates it from the per-card swipe-action text).
const markAllButton = () => screen.getByRole('button', { name: 'Прочитать' })

beforeEach(() => {
  vi.clearAllMocks()
  // Suppress the one-time swipe-hint timer so it doesn't fire after a test unmounts.
  sessionStorage.setItem('notif_swipe_hint', '1')
  useMarkNotificationRead.mockReturnValue(makeMutation(markReadMutate))
  useMarkAllNotificationsRead.mockReturnValue(makeMutation(markAllReadMutate))
})

describe('NotificationsSheet', () => {
  // (a)
  it('renders notification title, body, and a timestamp', () => {
    useClientNotifications.mockReturnValue(makeQuery({
      data: { items: [UNREAD_ITEM], total: 1, page: 1, pageSize: 10, unreadCount: 1 },
    }))
    const { container } = renderSheet(<NotificationsSheet onClose={vi.fn()} />)
    expect(screen.getByText('Бронь подтверждена')).toBeInTheDocument()
    expect(screen.getByText('10 июня, 10:00 — Иван Тренер')).toBeInTheDocument()
    expect(container.querySelector('.n-time')?.textContent).toMatch(/\d/)
  })

  // (b)
  it('renders unread dot for readAt===null and no dot for read items', () => {
    useClientNotifications.mockReturnValue(makeQuery({
      data: { items: [UNREAD_ITEM, READ_ITEM], total: 2, page: 1, pageSize: 10, unreadCount: 1 },
    }))
    renderSheet(<NotificationsSheet onClose={vi.fn()} />)
    expect(screen.queryAllByLabelText('непрочитано')).toHaveLength(1)
  })

  // (c)
  it('renders empty state heading and hint when no items', () => {
    useClientNotifications.mockReturnValue(makeQuery({
      data: { items: [], total: 0, page: 1, pageSize: 10, unreadCount: 0 },
    }))
    renderSheet(<NotificationsSheet onClose={vi.fn()} />)
    expect(screen.getByText('Всё прочитано')).toBeInTheDocument()
    expect(screen.getByText(/Когда появятся новые уведомления/)).toBeInTheDocument()
  })

  // (d) disabled when no unread
  it('disables "Прочитать" when unreadCount is 0', () => {
    useClientNotifications.mockReturnValue(makeQuery({
      data: { items: [READ_ITEM], total: 1, page: 1, pageSize: 10, unreadCount: 0 },
    }))
    renderSheet(<NotificationsSheet onClose={vi.fn()} />)
    expect(markAllButton()).toBeDisabled()
  })

  // (d) enabled when unread
  it('enables "Прочитать" when unreadCount > 0', () => {
    useClientNotifications.mockReturnValue(makeQuery({
      data: { items: [UNREAD_ITEM], total: 1, page: 1, pageSize: 10, unreadCount: 1 },
    }))
    renderSheet(<NotificationsSheet onClose={vi.fn()} />)
    expect(markAllButton()).not.toBeDisabled()
  })

  // (e)
  it('clicking "Прочитать" calls mark-all and removes unread dots optimistically', () => {
    useClientNotifications.mockReturnValue(makeQuery({
      data: { items: [UNREAD_ITEM], total: 1, page: 1, pageSize: 10, unreadCount: 1 },
    }))
    renderSheet(<NotificationsSheet onClose={vi.fn()} />)
    expect(screen.getByLabelText('непрочитано')).toBeInTheDocument()
    fireEvent.click(markAllButton())
    expect(markAllReadMutate).toHaveBeenCalled()
    expect(screen.queryByLabelText('непрочитано')).not.toBeInTheDocument()
  })

  // (e-rollback)
  it('onError rollback restores the unread dot (already-read item stays dotless)', () => {
    const cap = { fn: null }
    markAllReadMutate.mockImplementation((_, opts = {}) => { cap.fn = opts.onError })
    useClientNotifications.mockReturnValue(makeQuery({
      data: { items: [UNREAD_ITEM, READ_ITEM], total: 2, page: 1, pageSize: 10, unreadCount: 1 },
    }))
    renderSheet(<NotificationsSheet onClose={vi.fn()} />)
    expect(screen.queryAllByLabelText('непрочитано')).toHaveLength(1)
    fireEvent.click(markAllButton())
    expect(screen.queryAllByLabelText('непрочитано')).toHaveLength(0)
    act(() => { cap.fn?.() })
    expect(screen.queryAllByLabelText('непрочитано')).toHaveLength(1)
  })

  // (f) segmented filter
  it('"Новые" filter shows only unread items', () => {
    useClientNotifications.mockReturnValue(makeQuery({
      data: { items: [UNREAD_ITEM, READ_ITEM], total: 2, page: 1, pageSize: 10, unreadCount: 1 },
    }))
    renderSheet(<NotificationsSheet onClose={vi.fn()} />)
    // both visible under "Все"
    expect(screen.getByText('Бронь подтверждена')).toBeInTheDocument()
    expect(screen.getByText('Оплата прошла')).toBeInTheDocument()
    // switch to "Новые"
    fireEvent.click(screen.getByRole('button', { name: /Новые/ }))
    expect(screen.getByText('Бронь подтверждена')).toBeInTheDocument()
    expect(screen.queryByText('Оплата прошла')).not.toBeInTheDocument()
  })

  // (g)
  it('renders error copy when query fails', () => {
    useClientNotifications.mockReturnValue(makeQuery({ isError: true, data: undefined }))
    renderSheet(<NotificationsSheet onClose={vi.fn()} />)
    expect(screen.getByText(/Не удалось загрузить/)).toBeInTheDocument()
    expect(screen.getByText(/Потяните вниз, чтобы повторить/)).toBeInTheDocument()
  })
})

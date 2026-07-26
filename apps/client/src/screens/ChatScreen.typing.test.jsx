/**
 * Phase-94 RCPT-02 follow-up repro: the typing indicator.
 *
 * Standing bug (browser verify 2026-06-08, sharpened in 97dcf02e): a WS `typing`
 * frame reaches `window.__chatTyping`, `setTyping(true)` runs and the React render
 * is reportedly correct — yet neither the `.typing-dots` bubble nor the «печатает…»
 * status text was observed in `document.body` in the live dev browser.
 *
 * These tests pin the CONSUMER contract in jsdom so the React/CSS half of the path
 * is no longer a matter of speculation:
 *   (a) `window.__chatTyping` is installed while ChatScreen is mounted
 *   (b) calling it surfaces the `.typing-dots` bubble in the open thread
 *   (c) calling it flips the thread-header status text to «печатает…»
 *   (d) the indicator auto-dismisses after the 5s timer
 *   (e) the ownership guard (WR-06) restores the previous handler on unmount
 *
 * If these pass, the remaining defect is confined to the live environment (stale
 * service worker, a console probe that REPLACED `window.__chatTyping` with its own
 * counting wrapper and thereby suppressed the real handler, or a dev double-mount)
 * — NOT to the component's render logic.
 *
 * Note: there is still no typing PRODUCER in production (Telegram exposes no typing
 * API and the staff frontend never got one), so this path is dormant end-to-end.
 */
import React from 'react'
import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest'
import { render, screen, fireEvent, act } from '@testing-library/react'

// ─── Mock @/data messaging hooks (swap seam) ─────────────────────────────────
const useClientMessages = vi.fn()
vi.mock('@/data', async () => {
  const actual = await vi.importActual('@/data')
  return {
    ...actual,
    useClientMessages: (...args) => useClientMessages(...args),
    useSendMessage: () => ({ mutateAsync: vi.fn(), isPending: false }),
    useUploadAttachment: () => ({ mutateAsync: vi.fn(), isPending: false }),
    useMarkMessagesRead: () => ({ mutate: vi.fn(), mutateAsync: vi.fn() }),
  }
})

// ─── Mock UIContext — ChatScreen only needs the unread setter ────────────────
vi.mock('@/context/UIContext.jsx', () => ({
  useUI: () => ({ setUnreadChat: vi.fn() }),
}))

import { ChatScreen } from './ChatScreen.jsx'

const SENT_AT = '2026-06-08T09:00:00Z'

function makeMessagesQuery(overrides = {}) {
  return {
    data: {
      items: [
        { id: 'm1', role: 'staff', body: 'Здравствуйте!', sentAt: SENT_AT, readAt: null, attachment: null },
      ],
      unreadCount: 0,
    },
    isLoading: false,
    isError: false,
    isFetching: false,
    refetch: vi.fn().mockResolvedValue(undefined),
    ...overrides,
  }
}

/**
 * Render ChatScreen and open the single «Администрация» thread.
 *
 * The conv card opens on a pointerdown→pointerup TAP (a 450ms long-press instead
 * opens the mute sheet), and the pointerup listener lives on `document` — so a
 * plain `click` does nothing. Drive the real gesture.
 */
function renderChatWithOpenThread() {
  const utils = render(<ChatScreen tweaks={{ theme: 'light' }} />)
  const card = utils.container.querySelector('.conv-card')
  act(() => {
    fireEvent.pointerDown(card, { button: 0, clientX: 10, clientY: 10 })
    fireEvent.pointerUp(document, { button: 0, clientX: 10, clientY: 10 })
  })
  return utils
}

beforeEach(() => {
  useClientMessages.mockReturnValue(makeMessagesQuery())
  delete window.__chatTyping
})

afterEach(() => {
  vi.useRealTimers()
  delete window.__chatTyping
})

describe('Phase-94 typing indicator — consumer path', () => {
  it('installs the window.__chatTyping bridge handler while mounted', () => {
    render(<ChatScreen tweaks={{ theme: 'light' }} />)
    expect(typeof window.__chatTyping).toBe('function')
  })

  it('surfaces the .typing-dots bubble in the open thread when a typing frame arrives', () => {
    const { container } = renderChatWithOpenThread()

    expect(container.querySelector('.typing-dots')).toBeNull()

    act(() => {
      window.__chatTyping()
    })

    const dots = container.querySelector('.typing-dots')
    expect(dots).not.toBeNull()
    // Three bouncing spans, per the reference markup.
    expect(dots.querySelectorAll('span')).toHaveLength(3)
  })

  it('flips the thread-header status text to «печатает…»', () => {
    renderChatWithOpenThread()

    expect(screen.queryByText('печатает…')).toBeNull()

    act(() => {
      window.__chatTyping()
    })

    expect(screen.getByText('печатает…')).toBeInTheDocument()
  })

  it('auto-dismisses the indicator after the 5s timer', () => {
    vi.useFakeTimers({ shouldAdvanceTime: true })
    const { container } = renderChatWithOpenThread()

    act(() => {
      window.__chatTyping()
    })
    expect(container.querySelector('.typing-dots')).not.toBeNull()

    act(() => {
      vi.advanceTimersByTime(5000)
    })

    expect(container.querySelector('.typing-dots')).toBeNull()
    expect(screen.queryByText('печатает…')).toBeNull()
  })

  it('WR-06: restores the previous handler on unmount instead of clobbering it', () => {
    const previous = vi.fn()
    window.__chatTyping = previous

    const { unmount } = render(<ChatScreen tweaks={{ theme: 'light' }} />)
    expect(window.__chatTyping).not.toBe(previous)

    unmount()
    expect(window.__chatTyping).toBe(previous)
  })
})

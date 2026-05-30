/**
 * Tests for authBus pub/sub (Plan 71-07).
 *
 * Verifies:
 *  (a) publishSessionExpired invokes all subscribers
 *  (b) unsubscribe stops the callback from being invoked
 *  (c) multiple subscribers each receive the event
 */
import { describe, it, expect, vi, beforeEach } from 'vitest'
import { subscribeSessionExpired, publishSessionExpired } from './authBus'

// Reset subscriber set between tests by calling all unsubscribes
const _unsubscribers: Array<() => void> = []

beforeEach(() => {
  // Clean up any lingering subscriptions from previous tests
  for (const unsub of _unsubscribers) unsub()
  _unsubscribers.length = 0
})

describe('authBus', () => {
  it('publish invokes a subscriber', () => {
    const cb = vi.fn()
    const unsub = subscribeSessionExpired(cb)
    _unsubscribers.push(unsub)

    publishSessionExpired()

    expect(cb).toHaveBeenCalledTimes(1)
  })

  it('unsubscribe stops the callback from being invoked', () => {
    const cb = vi.fn()
    const unsub = subscribeSessionExpired(cb)

    unsub()

    publishSessionExpired()

    expect(cb).not.toHaveBeenCalled()
  })

  it('multiple subscribers each receive the event', () => {
    const cb1 = vi.fn()
    const cb2 = vi.fn()
    const unsub1 = subscribeSessionExpired(cb1)
    const unsub2 = subscribeSessionExpired(cb2)
    _unsubscribers.push(unsub1, unsub2)

    publishSessionExpired()

    expect(cb1).toHaveBeenCalledTimes(1)
    expect(cb2).toHaveBeenCalledTimes(1)
  })

  it('publish with no subscribers does not throw', () => {
    // All subscribers removed in beforeEach
    expect(() => publishSessionExpired()).not.toThrow()
  })
})

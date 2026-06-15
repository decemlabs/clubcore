/**
 * Unit tests for mapAuditToActivityFeed (Phase 115-04 ANL-04).
 *
 * Tests cover:
 *   - Each known action → correct ActivityType + title pattern
 *   - Unknown/unrecognized action → type 'alert', does not throw
 *   - Empty audit input → events: []
 *   - timeLabel is a non-empty string
 */
import { describe, it, expect } from 'vitest'
import { mapAuditToActivityFeed } from './audit-activity'
import type { AuditLogData, AuditEvent } from '@/features/audit/schemas'

// ---------------------------------------------------------------------------
// Test fixtures
// ---------------------------------------------------------------------------

function makeEvent(overrides: Partial<AuditEvent> = {}): AuditEvent {
  return {
    id: 'evt-1',
    createdAt: new Date(Date.now() - 4 * 60 * 1000).toISOString(), // 4 min ago
    actorUserId: 'user-1',
    actorEmailSnapshot: 'trainer@club.ru',
    action: 'visit.checked_in',
    resourceType: 'visit',
    resourceId: 'visit-1',
    payload: null,
    ...overrides,
  }
}

function makeAuditData(events: AuditEvent[]): AuditLogData {
  return {
    items: events,
    total: events.length,
    page: 1,
    pageSize: 20,
  }
}

// ---------------------------------------------------------------------------
// Known action mappings
// ---------------------------------------------------------------------------

describe('mapAuditToActivityFeed — known actions', () => {
  it('visit.checked_in → type checkin', () => {
    const data = makeAuditData([makeEvent({ action: 'visit.checked_in', resourceType: 'visit' })])
    const result = mapAuditToActivityFeed(data)
    expect(result.events).toHaveLength(1)
    expect(result.events[0]?.type).toBe('checkin')
    expect(result.events[0]?.title).toContain('чек-ин')
  })

  it('payment.created → type payment', () => {
    const data = makeAuditData([makeEvent({ action: 'payment.created', resourceType: 'payment' })])
    const result = mapAuditToActivityFeed(data)
    expect(result.events[0]?.type).toBe('payment')
    expect(result.events[0]?.title).toContain('оплата')
  })

  it('payment.* (other payment action) → type payment', () => {
    const data = makeAuditData([makeEvent({ action: 'payment.updated', resourceType: 'payment' })])
    const result = mapAuditToActivityFeed(data)
    expect(result.events[0]?.type).toBe('payment')
  })

  it('booking.confirmed → type training', () => {
    const data = makeAuditData([makeEvent({ action: 'booking.confirmed', resourceType: 'booking' })])
    const result = mapAuditToActivityFeed(data)
    expect(result.events[0]?.type).toBe('training')
    expect(result.events[0]?.title).toContain('запись подтверждена')
  })

  it('booking.cancelled → type cancel', () => {
    const data = makeAuditData([makeEvent({ action: 'booking.cancelled', resourceType: 'booking' })])
    const result = mapAuditToActivityFeed(data)
    expect(result.events[0]?.type).toBe('cancel')
    expect(result.events[0]?.title).toContain('отмена записи')
  })

  it('membership.expired → type expire', () => {
    const data = makeAuditData([makeEvent({ action: 'membership.expired', resourceType: 'membership' })])
    const result = mapAuditToActivityFeed(data)
    expect(result.events[0]?.type).toBe('expire')
    expect(result.events[0]?.title).toContain('абонемент истёк')
  })

  it('client.registered → type signup', () => {
    const data = makeAuditData([makeEvent({ action: 'client.registered', resourceType: 'client' })])
    const result = mapAuditToActivityFeed(data)
    expect(result.events[0]?.type).toBe('signup')
    expect(result.events[0]?.title).toContain('новый клиент')
  })
})

// ---------------------------------------------------------------------------
// Unknown / unrecognized action → alert fallback (never throws)
// ---------------------------------------------------------------------------

describe('mapAuditToActivityFeed — unknown action', () => {
  it('unrecognized action → type alert, does not throw', () => {
    const data = makeAuditData([makeEvent({ action: 'some.future_action', resourceType: 'unknown' })])
    expect(() => mapAuditToActivityFeed(data)).not.toThrow()
    const result = mapAuditToActivityFeed(data)
    expect(result.events[0]?.type).toBe('alert')
    // title is the raw action string (non-empty)
    expect(result.events[0]?.title).toBeTruthy()
  })

  it('completely unknown action → title contains the raw action', () => {
    const action = 'xyz.totally_unknown'
    const data = makeAuditData([makeEvent({ action })])
    const result = mapAuditToActivityFeed(data)
    expect(result.events[0]?.title).toContain(action)
  })
})

// ---------------------------------------------------------------------------
// Empty audit → empty result
// ---------------------------------------------------------------------------

describe('mapAuditToActivityFeed — empty audit', () => {
  it('empty items → events: []', () => {
    const data = makeAuditData([])
    const result = mapAuditToActivityFeed(data)
    expect(result.events).toEqual([])
  })

  it('empty items → subtitle is non-empty string', () => {
    const data = makeAuditData([])
    const result = mapAuditToActivityFeed(data)
    expect(typeof result.subtitle).toBe('string')
    expect(result.subtitle.length).toBeGreaterThan(0)
  })

  it('empty items → repliedToday is 0', () => {
    const data = makeAuditData([])
    const result = mapAuditToActivityFeed(data)
    expect(result.repliedToday).toBe(0)
  })
})

// ---------------------------------------------------------------------------
// timeLabel is a non-empty string
// ---------------------------------------------------------------------------

describe('mapAuditToActivityFeed — timeLabel', () => {
  it('timeLabel is a non-empty string', () => {
    const data = makeAuditData([makeEvent()])
    const result = mapAuditToActivityFeed(data)
    expect(typeof result.events[0]?.timeLabel).toBe('string')
    expect((result.events[0]?.timeLabel ?? '').length).toBeGreaterThan(0)
  })
})

// ---------------------------------------------------------------------------
// Actor email fallback
// ---------------------------------------------------------------------------

describe('mapAuditToActivityFeed — actor/display name', () => {
  it('uses actor email local-part as subLead when no payload name', () => {
    const data = makeAuditData([
      makeEvent({ actorEmailSnapshot: 'ivan@club.ru', payload: null }),
    ])
    const result = mapAuditToActivityFeed(data)
    expect(result.events[0]?.subLead).toContain('ivan')
  })

  it('null actorEmailSnapshot falls back to generic label', () => {
    const data = makeAuditData([
      makeEvent({ actorEmailSnapshot: null, payload: null }),
    ])
    expect(() => mapAuditToActivityFeed(data)).not.toThrow()
    const result = mapAuditToActivityFeed(data)
    expect(typeof result.events[0]?.subLead).toBe('string')
  })
})

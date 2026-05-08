import { afterEach, describe, expect, it, vi } from 'vitest'
import { formatDate, formatDateTime, formatTime, MOSCOW_TZ, WEEK_STARTS_ON, todayMSK } from './date'

describe('i18n/date', () => {
  it('formats ISO date as DD.MM.YYYY', () => {
    expect(formatDate('2026-04-21T10:30:00.000Z')).toBe('21.04.2026')
  })

  it('formats ISO datetime as DD.MM.YYYY HH:mm', () => {
    expect(formatDateTime('2026-04-21T10:30:00.000Z')).toMatch(/^21\.04\.2026 \d{2}:\d{2}$/)
  })

  it('formats time as HH:mm (24h)', () => {
    expect(formatTime('2026-04-21T13:07:00.000Z')).toMatch(/^\d{2}:\d{2}$/)
  })

  it('pins MOSCOW_TZ and WEEK_STARTS_ON=1 (Monday)', () => {
    expect(MOSCOW_TZ).toBe('Europe/Moscow')
    expect(WEEK_STARTS_ON).toBe(1)
  })

  it('accepts a Date instance', () => {
    expect(formatDate(new Date('2026-01-05T00:00:00.000Z'))).toMatch(/^\d{2}\.\d{2}\.2026$/)
  })
})

describe('todayMSK', () => {
  afterEach(() => {
    vi.useRealTimers()
  })

  it('returns YYYY-MM-DD format', () => {
    const result = todayMSK()
    expect(result).toMatch(/^\d{4}-\d{2}-\d{2}$/)
  })

  it('returns Moscow date when UTC is still previous day (boundary case)', () => {
    // 2026-05-08T22:30:00Z = 2026-05-09 01:30 Moscow (UTC+3)
    vi.useFakeTimers()
    vi.setSystemTime(new Date('2026-05-08T22:30:00Z'))
    expect(todayMSK()).toBe('2026-05-09')
  })

  it('returns UTC date when Moscow has not yet crossed midnight', () => {
    // 2026-05-08T18:00:00Z = 2026-05-08 21:00 Moscow (UTC+3) — still same day
    vi.useFakeTimers()
    vi.setSystemTime(new Date('2026-05-08T18:00:00Z'))
    expect(todayMSK()).toBe('2026-05-08')
  })

  it('returns correct date at exactly 00:00 Moscow (21:00 UTC prev day)', () => {
    // 2026-05-08T21:00:00Z = 2026-05-09 00:00 Moscow (UTC+3)
    vi.useFakeTimers()
    vi.setSystemTime(new Date('2026-05-08T21:00:00Z'))
    expect(todayMSK()).toBe('2026-05-09')
  })
})

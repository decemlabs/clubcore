import { describe, expect, it } from 'vitest'
import { formatDate, formatDateTime, formatTime, MOSCOW_TZ, WEEK_STARTS_ON } from './date'

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

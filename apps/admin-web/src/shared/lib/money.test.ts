import { describe, expect, it } from 'vitest'
import { formatMoney } from './money'

// NBSP literal for readability
const NBSP = '\u00A0'

describe('formatMoney', () => {
  it('formats kopecks as "1 234,56 ₽" with NBSPs', () => {
    const out = formatMoney(123456)
    // Core shape
    expect(out).toContain('1')
    expect(out).toContain('234')
    expect(out).toContain(',56')
    expect(out).toContain('₽')
    // NBSP separators (ru-RU uses NBSP as both group separator and before ₽)
    expect(out).toMatch(new RegExp(`1${NBSP}234,56${NBSP}₽`))
  })

  it('formats 0 kopecks as "0,00 ₽"', () => {
    expect(formatMoney(0)).toBe(`0,00${NBSP}₽`)
  })

  it('formats sub-ruble amounts (50 kopecks)', () => {
    expect(formatMoney(50)).toBe(`0,50${NBSP}₽`)
  })

  it('formats negative amounts', () => {
    const out = formatMoney(-10000)
    expect(out).toContain('100,00')
    expect(out).toMatch(/-/)
  })
})

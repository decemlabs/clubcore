/**
 * PlansSheet adapter tests (Plan 71-09, Task 1).
 *
 * The backend serializes camelCase (Pydantic alias_generator=to_camel), so the
 * in-file adapters must read priceKopecks / durationDays / sessionCount — never
 * snake_case. A snake_case read yields NaN ("не число") / "undefined дней".
 */
import { describe, it, expect } from 'vitest'
import { toMembershipCard, toPtCard } from './PlansSheet.jsx'

describe('toMembershipCard (camelCase ClientCatalogPlanResponse)', () => {
  it('maps priceKopecks/durationDays to finite numbers', () => {
    const card = toMembershipCard({
      id: 'p1',
      name: 'Месяц',
      priceKopecks: 500000,
      durationDays: 30,
    })
    expect(card.priceTotal).toBe(5000)
    expect(card.tagline).toBe('30 дней')
    expect(Number.isFinite(card.priceMonth)).toBe(true)
    expect(card.tagline).not.toContain('undefined')
    expect(Number.isNaN(card.priceTotal)).toBe(false)
  })
})

describe('toPtCard (camelCase ClientCatalogPtPackageResponse)', () => {
  it('maps sessionCount/priceKopecks to finite numbers', () => {
    const card = toPtCard({
      id: 'pt1',
      name: 'Пакет',
      sessionCount: 10,
      priceKopecks: 300000,
    })
    expect(card.priceTotal).toBe(3000)
    expect(card.tagline).toBe('10 занятий')
    expect(card.priceMonth).toBe(300)
    expect(Number.isFinite(card.priceMonth)).toBe(true)
  })
})

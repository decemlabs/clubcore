/**
 * ProfileScreen membership adapter tests (Plan 71-09, Task 3).
 *
 * Mirrors HomeScreen toSubInfo — must read camelCase ClientMembershipResponse
 * (daysUntilEnd/planNameSnapshot/startDate/endDate/expiringSoon), never snake_case.
 */
import { describe, it, expect } from 'vitest'
import { toSubInfo } from './ProfileScreen.jsx'

describe('ProfileScreen toSubInfo (camelCase ClientMembershipResponse)', () => {
  it('maps an active membership to a finite render shape', () => {
    const info = toSubInfo({
      id: 'm1',
      daysUntilEnd: 47,
      planNameSnapshot: 'Годовой',
      startDate: '2026-01-01',
      endDate: '2026-12-31',
      expiringSoon: false,
      status: 'active',
    })
    expect(info.daysLeft).toBe(47)
    expect(info.label).toBe('Годовой')
    expect(info.until).toBe('2026-12-31')
    expect(info.total).toBeGreaterThan(0)
    expect(info.tone).toBe('ok')
  })

  it('maps null membership to the empty-state shape', () => {
    const info = toSubInfo(null)
    expect(info.daysLeft).toBe(0)
    expect(info.total).toBe(0)
    expect(info.until).toBe('—')
    expect(info.label).toBe('Нет абонемента')
    expect(info.tone).toBe('danger')
  })
})

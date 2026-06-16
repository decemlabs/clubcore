/**
 * HomeScreen membership adapter tests (Plan 71-09, Task 2).
 * deriveOnboardingSteps tests added in Plan 999.3-02.
 *
 * The backend serializes camelCase; toSubInfo must read daysUntilEnd /
 * planNameSnapshot / startDate / endDate / expiringSoon — never snake_case.
 */
import { describe, it, expect } from 'vitest'
import { toSubInfo, deriveOnboardingSteps } from './HomeScreen.jsx'

describe('toSubInfo (camelCase ClientMembershipResponse)', () => {
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

// ─── deriveOnboardingSteps — Plan 999.3-02 (D-05/D-06) ───────────────────────
describe('deriveOnboardingSteps (live data-driven onboarding)', () => {
  // Test 1: Step 1 «Аккаунт» is always done
  it('Step 1 «Аккаунт» state is always "done"', () => {
    const { steps } = deriveOnboardingSteps(null, null, null)
    const account = steps.find((s) => s.key === 'account')
    expect(account).toBeDefined()
    expect(account.state).toBe('done')
  })

  // Test 2: Step 2 «Абонемент» state is always 'next'
  it('Step 2 «Абонемент» state is always "next"', () => {
    const { steps } = deriveOnboardingSteps(null, null, null)
    const plan = steps.find((s) => s.key === 'plan')
    expect(plan).toBeDefined()
    expect(plan.state).toBe('next')
  })

  // Test 3: Step 3 «Профиль» is done when me.birthday AND me.gender are truthy
  it('Step 3 «Профиль» is "done" when birthday AND gender are set', () => {
    const me = { birthday: '1990-01-01', gender: 'male' }
    const { steps } = deriveOnboardingSteps(me, null, null)
    const profile = steps.find((s) => s.key === 'profile')
    expect(profile.state).toBe('done')
  })

  it('Step 3 «Профиль» is "pending" when birthday is missing', () => {
    const me = { birthday: null, gender: 'male' }
    const { steps } = deriveOnboardingSteps(me, null, null)
    const profile = steps.find((s) => s.key === 'profile')
    expect(profile.state).toBe('pending')
  })

  it('Step 3 «Профиль» is "pending" when gender is missing', () => {
    const me = { birthday: '1990-01-01', gender: null }
    const { steps } = deriveOnboardingSteps(me, null, null)
    const profile = steps.find((s) => s.key === 'profile')
    expect(profile.state).toBe('pending')
  })

  // Test 4: Step 4 «Первый визит» is done when client has any booking
  it('Step 4 «Первый визит» is "done" when bookings.total > 0', () => {
    const bookings = { items: [], total: 1 }
    const { steps } = deriveOnboardingSteps(null, null, bookings)
    const visit = steps.find((s) => s.key === 'visit')
    expect(visit.state).toBe('done')
  })

  it('Step 4 «Первый визит» is "done" when bookings.items is non-empty', () => {
    const bookings = { items: [{ id: 'b1' }], total: 0 }
    const { steps } = deriveOnboardingSteps(null, null, bookings)
    const visit = steps.find((s) => s.key === 'visit')
    expect(visit.state).toBe('done')
  })

  it('Step 4 «Первый визит» is "done" when homeData.nextBooking is not null', () => {
    const homeData = { nextBooking: { id: 'nb1' } }
    const { steps } = deriveOnboardingSteps(null, homeData, null)
    const visit = steps.find((s) => s.key === 'visit')
    expect(visit.state).toBe('done')
  })

  it('Step 4 «Первый визит» is "pending" when no booking', () => {
    const { steps } = deriveOnboardingSteps(null, null, null)
    const visit = steps.find((s) => s.key === 'visit')
    expect(visit.state).toBe('pending')
  })

  // Test 5: exactly one step has state === 'next' (Step 2), and no 'done' step is also 'next'
  it('exactly one step has state "next", and no done step is also next', () => {
    const me = { birthday: '1990-01-01', gender: 'male' }
    const bookings = { items: [{ id: 'b1' }], total: 1 }
    const { steps } = deriveOnboardingSteps(me, null, bookings)
    const nextSteps = steps.filter((s) => s.state === 'next')
    expect(nextSteps).toHaveLength(1)
    expect(nextSteps[0].key).toBe('plan')
    // No done step is also next
    const doneSteps = steps.filter((s) => s.state === 'done')
    doneSteps.forEach((s) => expect(s.state).not.toBe('next'))
  })

  // Test 6: doneCount and badge/title for a fresh newbie
  it('fresh newbie (no profile, no booking) has doneCount 1, badge "1 / 4"', () => {
    const { doneCount, badge, title } = deriveOnboardingSteps(
      { birthday: null, gender: null },
      { nextBooking: null },
      { items: [], total: 0 },
    )
    expect(doneCount).toBe(1)
    expect(badge).toBe('1 / 4')
    expect(title).toContain('3')
  })

  it('doneCount with profile + booking is 3 (Step 1 + 3 + 4), Step 2 still "next"', () => {
    const me = { birthday: '1990-01-01', gender: 'male' }
    const bookings = { items: [{ id: 'b1' }], total: 1 }
    const { doneCount, steps } = deriveOnboardingSteps(me, null, bookings)
    expect(doneCount).toBe(3)
    const plan = steps.find((s) => s.key === 'plan')
    expect(plan.state).toBe('next')
  })

  // Test 7: handles null/undefined me and bookings without throwing
  it('handles null me and null bookings without throwing', () => {
    expect(() => deriveOnboardingSteps(null, null, null)).not.toThrow()
    expect(() => deriveOnboardingSteps(undefined, undefined, undefined)).not.toThrow()
  })

  it('Step 2 is still "next" when me and bookings are undefined', () => {
    const { steps } = deriveOnboardingSteps(undefined, undefined, undefined)
    const plan = steps.find((s) => s.key === 'plan')
    expect(plan.state).toBe('next')
  })
})

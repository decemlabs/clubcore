import { describe, it, expect, beforeEach } from 'vitest'
import { useSessionStore } from '@/shared/session/store'
import { memberships } from './memberships'
import { resetDB, loadDB, saveDB } from './_db'
import type { Membership, MembershipId } from '@/entities/membership'

/**
 * Phase 28 mock service renew parity tests.
 * Backend semantics: Phase 26 router renew endpoint (201 + new resource).
 */

function injectMembership(partial: Partial<Membership> & Pick<Membership, 'id' | 'status'>) {
  const db = loadDB()
  const seed = db.memberships[0]
  if (!seed) throw new Error('mock DB has no memberships seed')
  const fixture: Membership = { ...seed, ...partial }
  db.memberships.push(fixture)
  saveDB(db)
}

describe('mock/memberships renew parity', () => {
  beforeEach(() => {
    resetDB()
    useSessionStore.setState({ role: 'owner' })
  })

  it('renew creates a new membership with previousMembershipId pointing to source', async () => {
    const id = 'fixture-renew-1' as MembershipId
    injectMembership({ id, status: 'active', endDate: '2030-01-01' })
    const newRow = await memberships.renew(id)
    expect(newRow.id).not.toBe(id)
    expect(newRow.previousMembershipId).toBe(id)
  })

  it('renew newStartDate = sourceEndDate + 1 when source endDate is in the future', async () => {
    const id = 'fixture-renew-2' as MembershipId
    injectMembership({ id, status: 'active', endDate: '2099-12-31', durationDaysSnapshot: 30 })
    const newRow = await memberships.renew(id)
    expect(newRow.startDate).toBe('2100-01-01')
  })

  it('renew newEndDate = newStartDate + durationDaysSnapshot - 1 (inclusive)', async () => {
    const id = 'fixture-renew-3' as MembershipId
    injectMembership({ id, status: 'active', endDate: '2099-12-31', durationDaysSnapshot: 30 })
    const newRow = await memberships.renew(id)
    // start 2100-01-01, +29 days = 2100-01-30 (inclusive)
    expect(newRow.endDate).toBe('2100-01-30')
  })

  it('renew throws cannot_renew_cancelled when source is cancelled', async () => {
    const id = 'fixture-renew-cancelled' as MembershipId
    injectMembership({ id, status: 'cancelled' })
    await expect(memberships.renew(id)).rejects.toMatchObject({ code: 'cannot_renew_cancelled' })
  })

  it('renew throws plan_archived when source plan is not active', async () => {
    // Inject a plan with active=false, then a membership pointing to it.
    const db = loadDB()
    const archivedPlan = { ...db.plans[0]!, id: 'archived-plan-id', active: false }
    db.plans.push(archivedPlan)
    saveDB(db)
    const id = 'fixture-renew-archived' as MembershipId
    injectMembership({ id, status: 'active', planId: 'archived-plan-id' as Membership['planId'] })
    await expect(memberships.renew(id)).rejects.toMatchObject({ code: 'plan_archived' })
  })

  it('renew resets freeze counters on the new membership', async () => {
    const id = 'fixture-renew-counters' as MembershipId
    injectMembership({
      id,
      status: 'active',
      endDate: '2099-12-31',
      freezeDaysLimitSnapshot: 14,
      freezeDaysUsed: 7,
      freezeDaysRemaining: 7,
    })
    const newRow = await memberships.renew(id)
    expect(newRow.freezeDaysUsed).toBe(0)
    expect(newRow.freezeDaysRemaining).toBe(14)
    expect(newRow.currentFreezePeriod).toBeNull()
  })

  it('renew status is active on the new row even if source was frozen', async () => {
    const id = 'fixture-renew-frozen-src' as MembershipId
    injectMembership({
      id,
      status: 'frozen',
      endDate: '2099-12-31',
      currentFreezePeriod: {
        id: 'p',
        startedAt: new Date().toISOString(),
        startedBy: 'owner',
        endedAt: null,
        endedBy: null,
      },
    })
    const newRow = await memberships.renew(id)
    expect(newRow.status).toBe('active')
  })

  it('renew throws not_found for unknown source id', async () => {
    await expect(
      memberships.renew('does-not-exist' as MembershipId),
    ).rejects.toMatchObject({ code: 'not_found' })
  })
})

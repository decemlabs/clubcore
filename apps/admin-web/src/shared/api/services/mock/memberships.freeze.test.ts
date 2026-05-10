import { describe, it, expect, beforeEach } from 'vitest'
import { useSessionStore } from '@/shared/session/store'
import { memberships } from './memberships'
import { resetDB, loadDB, saveDB } from './_db'
import type { Membership, MembershipId } from '@/entities/membership'

/**
 * Phase 28 mock service freeze/unfreeze parity tests.
 * Backend error codes mirror Phase 25 router.py lines 354-355.
 */

function injectMembership(partial: Partial<Membership> & Pick<Membership, 'id' | 'status'>) {
  const db = loadDB()
  const seed = db.memberships[0]
  if (!seed) throw new Error('mock DB has no memberships seed — cannot fabricate fixture')
  const fixture: Membership = { ...seed, ...partial }
  db.memberships.push(fixture)
  saveDB(db)
}

describe('mock/memberships freeze parity', () => {
  beforeEach(() => {
    resetDB()
    useSessionStore.setState({ role: 'owner' })
  })

  it('freeze transitions active → frozen and sets currentFreezePeriod', async () => {
    const id = 'fixture-freeze-1' as MembershipId
    injectMembership({
      id,
      status: 'active',
      freezeDaysLimitSnapshot: 14,
      freezeDaysUsed: 0,
      freezeDaysRemaining: 14,
      currentFreezePeriod: null,
    })
    const result = await memberships.freeze(id)
    expect(result.status).toBe('frozen')
    expect(result.currentFreezePeriod).not.toBeNull()
    expect(result.currentFreezePeriod?.id).toBeTruthy()
    expect(result.currentFreezePeriod?.startedAt).toBeTruthy()
    expect(result.currentFreezePeriod?.endedAt).toBeNull()
    expect(result.currentFreezePeriod?.endedBy).toBeNull()
  })

  it('freeze throws already_frozen when status=frozen', async () => {
    const id = 'fixture-freeze-2' as MembershipId
    injectMembership({
      id,
      status: 'frozen',
      freezeDaysLimitSnapshot: 14,
      freezeDaysUsed: 0,
      freezeDaysRemaining: 14,
      currentFreezePeriod: {
        id: 'p',
        startedAt: new Date().toISOString(),
        startedBy: 'owner',
        endedAt: null,
        endedBy: null,
      },
    })
    await expect(memberships.freeze(id)).rejects.toMatchObject({ code: 'already_frozen' })
  })

  it('freeze throws invalid_transition when status=expired', async () => {
    const id = 'fixture-freeze-3' as MembershipId
    injectMembership({
      id,
      status: 'expired',
      freezeDaysLimitSnapshot: 14,
      freezeDaysUsed: 0,
      freezeDaysRemaining: 14,
      currentFreezePeriod: null,
    })
    await expect(memberships.freeze(id)).rejects.toMatchObject({ code: 'invalid_transition' })
  })

  it('freeze throws freeze_limit_exceeded when freezeDaysRemaining === 0', async () => {
    const id = 'fixture-freeze-4' as MembershipId
    injectMembership({
      id,
      status: 'active',
      freezeDaysLimitSnapshot: 14,
      freezeDaysUsed: 14,
      freezeDaysRemaining: 0,
      currentFreezePeriod: null,
    })
    await expect(memberships.freeze(id)).rejects.toMatchObject({ code: 'freeze_limit_exceeded' })
  })

  it('freeze throws not_found for unknown id', async () => {
    await expect(
      memberships.freeze('does-not-exist' as MembershipId),
    ).rejects.toMatchObject({ code: 'not_found' })
  })

  it('unfreeze transitions frozen → active and extends endDate', async () => {
    const id = 'fixture-unfreeze-1' as MembershipId
    const startedAt = new Date(Date.now() - 4 * 86_400_000).toISOString() // 4 days ago (margin for clock skew)
    injectMembership({
      id,
      status: 'frozen',
      endDate: '2026-06-01',
      freezeDaysLimitSnapshot: 14,
      freezeDaysUsed: 0,
      freezeDaysRemaining: 14,
      currentFreezePeriod: {
        id: 'p',
        startedAt,
        startedBy: 'owner',
        endedAt: null,
        endedBy: null,
      },
    })
    const result = await memberships.unfreeze(id)
    expect(result.status).toBe('active')
    expect(result.endDate > '2026-06-01').toBe(true)
    expect(result.freezeDaysUsed).toBeGreaterThanOrEqual(3)
    expect(result.currentFreezePeriod).toBeNull()
  })

  it('unfreeze throws invalid_transition when status=active', async () => {
    const id = 'fixture-unfreeze-2' as MembershipId
    injectMembership({
      id,
      status: 'active',
      freezeDaysLimitSnapshot: 14,
      freezeDaysUsed: 0,
      freezeDaysRemaining: 14,
      currentFreezePeriod: null,
    })
    await expect(memberships.unfreeze(id)).rejects.toMatchObject({ code: 'invalid_transition' })
  })

  it('reception can freeze (CREATE MEMBERSHIPS is not owner-only)', async () => {
    useSessionStore.setState({ role: 'reception' })
    const id = 'fixture-freeze-rec' as MembershipId
    injectMembership({
      id,
      status: 'active',
      freezeDaysLimitSnapshot: 14,
      freezeDaysUsed: 0,
      freezeDaysRemaining: 14,
      currentFreezePeriod: null,
    })
    const result = await memberships.freeze(id)
    expect(result.status).toBe('frozen')
  })

  it('freeze mutation persists across loadDB calls', async () => {
    const id = 'fixture-freeze-persist' as MembershipId
    injectMembership({
      id,
      status: 'active',
      freezeDaysLimitSnapshot: 14,
      freezeDaysUsed: 0,
      freezeDaysRemaining: 14,
      currentFreezePeriod: null,
    })
    await memberships.freeze(id)
    const db = loadDB()
    const persisted = db.memberships.find((m) => m.id === id)
    expect(persisted?.status).toBe('frozen')
  })
})

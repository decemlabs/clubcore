import { describe, it, expect, beforeEach } from 'vitest'
import { useSessionStore } from '@/shared/session/store'
import { memberships } from './memberships'
import { resetDB, loadDB } from './_db'
import { isDomainError } from '@/shared/api/errors'
import type { MembershipPlanId } from '@/entities/membership'

describe('mock/memberships RBAC + shape', () => {
  beforeEach(() => {
    resetDB()
  })

  // Test 1: listPlans forbidden for reception
  it('forbids reception from calling listPlans (owner-only)', async () => {
    useSessionStore.setState({ role: 'reception' })
    let caught: unknown
    try {
      await memberships.listPlans({})
    } catch (e) {
      caught = e
    }
    expect(isDomainError(caught)).toBe(true)
    if (isDomainError(caught)) {
      expect(caught.code).toBe('forbidden')
    }
  })

  // Test 2: listPlans returns paginated envelope for owner
  it('allows owner to call listPlans and returns paginated envelope', async () => {
    useSessionStore.setState({ role: 'owner' })
    const result = await memberships.listPlans({})
    expect(Array.isArray(result.items)).toBe(true)
    expect(typeof result.total).toBe('number')
    expect(typeof result.page).toBe('number')
    expect(typeof result.pageSize).toBe('number')
    expect(result.items.length).toBeGreaterThan(0)
  })

  // Test 3: list accessible to both roles — reception
  it('allows reception to call list and returns paginated envelope', async () => {
    useSessionStore.setState({ role: 'reception' })
    const result = await memberships.list({ page: 1, pageSize: 20 })
    expect(Array.isArray(result.items)).toBe(true)
    expect(typeof result.total).toBe('number')
    expect(result.pageSize).toBe(20)
  })

  // Test 3b: list accessible to owner
  it('allows owner to call list and returns paginated envelope', async () => {
    useSessionStore.setState({ role: 'owner' })
    const result = await memberships.list({ page: 1, pageSize: 20 })
    expect(Array.isArray(result.items)).toBe(true)
    expect(result.pageSize).toBe(20)
  })

  // Test 4: byClient accessible to both roles — reception
  it('allows reception to call byClient and returns paginated envelope', async () => {
    useSessionStore.setState({ role: 'reception' })
    const db = loadDB()
    const someClientId = db.clients[0]!.id
    const result = await memberships.byClient(someClientId)
    expect(Array.isArray(result.items)).toBe(true)
    expect(typeof result.total).toBe('number')
    expect(typeof result.page).toBe('number')
    expect(typeof result.pageSize).toBe('number')
  })

  // Test 4b: byClient accessible to owner
  it('allows owner to call byClient and returns paginated envelope', async () => {
    useSessionStore.setState({ role: 'owner' })
    const db = loadDB()
    const someClientId = db.clients[0]!.id
    const result = await memberships.byClient(someClientId)
    expect(Array.isArray(result.items)).toBe(true)
  })

  // Test 5: create throws mock_not_implemented regardless of role
  it('throws mock_not_implemented on create for owner', async () => {
    useSessionStore.setState({ role: 'owner' })
    let caught: unknown
    try {
      await memberships.create({
        clientId: 'some-uuid',
        planId: 'plan-uuid' as MembershipPlanId,
      })
    } catch (e) {
      caught = e
    }
    expect(isDomainError(caught)).toBe(true)
    if (isDomainError(caught)) {
      expect(caught.code).toBe('mock_not_implemented')
    }
  })

  it('throws mock_not_implemented on create for reception', async () => {
    useSessionStore.setState({ role: 'reception' })
    let caught: unknown
    try {
      await memberships.create({
        clientId: 'some-uuid',
        planId: 'plan-uuid' as MembershipPlanId,
      })
    } catch (e) {
      caught = e
    }
    expect(isDomainError(caught)).toBe(true)
    if (isDomainError(caught)) {
      expect(caught.code).toBe('mock_not_implemented')
    }
  })

  // Test 6: cancel throws mock_not_implemented regardless of role
  it('throws mock_not_implemented on cancel for owner', async () => {
    useSessionStore.setState({ role: 'owner' })
    let caught: unknown
    try {
      await memberships.cancel('some-id' as import('@/entities/membership').MembershipId, 'reason')
    } catch (e) {
      caught = e
    }
    expect(isDomainError(caught)).toBe(true)
    if (isDomainError(caught)) {
      expect(caught.code).toBe('mock_not_implemented')
    }
  })

  it('throws mock_not_implemented on cancel for reception', async () => {
    useSessionStore.setState({ role: 'reception' })
    let caught: unknown
    try {
      await memberships.cancel('some-id' as import('@/entities/membership').MembershipId)
    } catch (e) {
      caught = e
    }
    expect(isDomainError(caught)).toBe(true)
    if (isDomainError(caught)) {
      expect(caught.code).toBe('mock_not_implemented')
    }
  })

  // Test 7: byClient items have correct shape matching MembershipResponse
  it('byClient items have the expected Membership shape', async () => {
    useSessionStore.setState({ role: 'owner' })
    const db = loadDB()
    // Find a client that has memberships
    const clientId = db.memberships[0]?.clientId
    if (!clientId) return // skip if no memberships seeded
    const result = await memberships.byClient(clientId)
    if (result.items.length > 0) {
      const item = result.items[0]!
      expect(typeof item.id).toBe('string')
      expect(typeof item.clientId).toBe('string')
      expect(typeof item.planId).toBe('string')
      expect(typeof item.planNameSnapshot).toBe('string')
      expect(typeof item.durationDaysSnapshot).toBe('number')
      expect(typeof item.priceKopecksSnapshot).toBe('number')
      expect(typeof item.startDate).toBe('string')
      expect(typeof item.endDate).toBe('string')
      expect(['active', 'expired', 'cancelled']).toContain(item.status)
      expect(typeof item.createdAt).toBe('string')
      expect(typeof item.updatedAt).toBe('string')
    }
  })

  // Test 8: mock latency — all methods await delay (~120-300ms)
  it('list completes with simulated latency (>= 50ms)', async () => {
    useSessionStore.setState({ role: 'owner' })
    const start = Date.now()
    await memberships.list({ page: 1, pageSize: 5 })
    expect(Date.now() - start).toBeGreaterThanOrEqual(50) // delay() is 120-300ms but test env is fast
  })

  // createPlan, updatePlan, deletePlan all throw mock_not_implemented
  it('throws mock_not_implemented on createPlan', async () => {
    useSessionStore.setState({ role: 'owner' })
    let caught: unknown
    try {
      await memberships.createPlan({ name: 'Test', durationDays: 30, priceKopecks: 100000, freezeDaysLimit: 4 })
    } catch (e) {
      caught = e
    }
    expect(isDomainError(caught)).toBe(true)
    if (isDomainError(caught)) expect(caught.code).toBe('mock_not_implemented')
  })

  it('throws mock_not_implemented on updatePlan', async () => {
    useSessionStore.setState({ role: 'owner' })
    let caught: unknown
    try {
      await memberships.updatePlan('some-id' as MembershipPlanId, { name: 'Updated' })
    } catch (e) {
      caught = e
    }
    expect(isDomainError(caught)).toBe(true)
    if (isDomainError(caught)) expect(caught.code).toBe('mock_not_implemented')
  })

  it('throws mock_not_implemented on deletePlan', async () => {
    useSessionStore.setState({ role: 'owner' })
    let caught: unknown
    try {
      await memberships.deletePlan('some-id' as MembershipPlanId)
    } catch (e) {
      caught = e
    }
    expect(isDomainError(caught)).toBe(true)
    if (isDomainError(caught)) expect(caught.code).toBe('mock_not_implemented')
  })

  // Phase 28 FE-11: status filter parity with http (verifier gap close)
  it('list filters by status when query.status is provided (FE-11 mock parity)', async () => {
    useSessionStore.setState({ role: 'owner' })
    const all = await memberships.list({ page: 1, pageSize: 1000 })
    const frozen = await memberships.list({ page: 1, pageSize: 1000, status: 'frozen' })
    expect(frozen.items.every((m) => m.status === 'frozen')).toBe(true)
    expect(frozen.total).toBeLessThanOrEqual(all.total)
    const active = await memberships.list({ page: 1, pageSize: 1000, status: 'active' })
    expect(active.items.every((m) => m.status === 'active')).toBe(true)
    expect(frozen.items.length + active.items.length).toBeLessThanOrEqual(all.total)
  })
})

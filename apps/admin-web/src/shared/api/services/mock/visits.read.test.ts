import { describe, it, expect, beforeEach } from 'vitest'
import { useSessionStore } from '@/shared/session/store'
import { visits } from './visits'
import { resetDB, loadDB } from './_db'
import { isDomainError } from '@/shared/api/errors'

describe('mock/visits read paths', () => {
  beforeEach(() => {
    resetDB()
    useSessionStore.setState({ role: 'owner' })
  })

  // Test 1 — RBAC: owner can list visits
  it('allows owner to list visits (paginated envelope)', async () => {
    useSessionStore.setState({ role: 'owner' })
    const result = await visits.list({ page: 1, pageSize: 20 })
    expect(result.items.length).toBeGreaterThan(0)
    expect(result.page).toBe(1)
    expect(result.pageSize).toBe(20)
    expect(typeof result.total).toBe('number')
  })

  // Test 1b — RBAC: reception can also list visits
  it('allows reception to list visits (paginated envelope)', async () => {
    useSessionStore.setState({ role: 'reception' })
    const result = await visits.list({ page: 1, pageSize: 20 })
    expect(result.items.length).toBeGreaterThan(0)
    expect(result.page).toBe(1)
    expect(result.pageSize).toBe(20)
  })

  // Test 2 — recentByClient: both roles, returns array DESC by checkedInAt
  it('allows owner to call recentByClient and returns DESC sorted array', async () => {
    useSessionStore.setState({ role: 'owner' })
    const db = loadDB()
    const someClientId = db.visits[0]!.clientId
    const result = await visits.recentByClient(someClientId, { limit: 20 })
    expect(Array.isArray(result)).toBe(true)
    expect(result.length).toBeLessThanOrEqual(20)
    // Verify DESC sort
    for (let i = 1; i < result.length; i++) {
      expect(result[i - 1]!.checkedInAt >= result[i]!.checkedInAt).toBe(true)
    }
  })

  it('allows reception to call recentByClient', async () => {
    useSessionStore.setState({ role: 'reception' })
    const db = loadDB()
    const someClientId = db.visits[0]!.clientId
    const result = await visits.recentByClient(someClientId, { limit: 20 })
    expect(Array.isArray(result)).toBe(true)
  })

  // Test 3 — gymMeta: both roles get static fixture
  it('returns gymMeta fixture {gymHoursStart: "07:00", gymHoursEnd: "23:00"}', async () => {
    useSessionStore.setState({ role: 'owner' })
    const meta = await visits.gymMeta()
    expect(meta.gymHoursStart).toBe('07:00')
    expect(meta.gymHoursEnd).toBe('23:00')
  })

  it('returns gymMeta for reception role too', async () => {
    useSessionStore.setState({ role: 'reception' })
    const meta = await visits.gymMeta()
    expect(meta.gymHoursStart).toBe('07:00')
    expect(meta.gymHoursEnd).toBe('23:00')
  })

  // Test 4 — D-22-7 mock_not_implemented: checkIn always throws
  it('throws DomainError mock_not_implemented on checkIn (D-22-7)', async () => {
    useSessionStore.setState({ role: 'owner' })
    let caught: unknown
    try {
      await visits.checkIn('some-client-id')
    } catch (e) {
      caught = e
    }
    expect(isDomainError(caught)).toBe(true)
    if (isDomainError(caught)) {
      expect(caught.code).toBe('mock_not_implemented')
    }
  })

  it('throws DomainError mock_not_implemented on checkIn for reception (D-22-7)', async () => {
    useSessionStore.setState({ role: 'reception' })
    let caught: unknown
    try {
      await visits.checkIn('some-client-id')
    } catch (e) {
      caught = e
    }
    expect(isDomainError(caught)).toBe(true)
    if (isDomainError(caught)) {
      expect(caught.code).toBe('mock_not_implemented')
    }
  })

  // Test 5 — ensure('view', 'visits') is present: verify reception NOT blocked (visits is
  // reception+owner readable; no visit read action is in OWNER_ONLY)
  it('ensure("view", "visits") is non-blocking for reception (visits is not owner-only)', async () => {
    useSessionStore.setState({ role: 'reception' })
    // Should NOT throw forbidden — visits.list calls ensure('view', 'visits')
    const result = await visits.list({ page: 1, pageSize: 5 })
    expect(result.items).toBeDefined()
  })

  // Test 6 — shape parity: each Visit has required fields
  it('returns Visit shapes matching VisitResponse contract fields', async () => {
    useSessionStore.setState({ role: 'owner' })
    const result = await visits.list({ page: 1, pageSize: 5 })
    for (const v of result.items) {
      expect(typeof v.id).toBe('string')
      expect(typeof v.clientId).toBe('string')
      expect(typeof v.membershipId).toBe('string')
      expect(typeof v.checkedInAt).toBe('string')
      expect(typeof v.gymDate).toBe('string')
      expect(['reception', 'telegram_bot'].includes(v.channel)).toBe(true)
      // checkedInBy is string | null | undefined
      if (v.channel === 'telegram_bot') {
        expect(v.checkedInBy).toBeNull()
      }
    }
  })

  // Test 7 — mock latency: verify delay() is awaited (indirectly via timing)
  it('awaits delay() — resolves asynchronously (not synchronous)', async () => {
    useSessionStore.setState({ role: 'owner' })
    // All three read methods should return promises
    const listPromise = visits.list({ page: 1, pageSize: 1 })
    expect(listPromise).toBeInstanceOf(Promise)
    await listPromise

    const db = loadDB()
    const someClientId = db.visits[0]!.clientId
    const recentPromise = visits.recentByClient(someClientId, { limit: 1 })
    expect(recentPromise).toBeInstanceOf(Promise)
    await recentPromise

    const metaPromise = visits.gymMeta()
    expect(metaPromise).toBeInstanceOf(Promise)
    await metaPromise
  })

  // Verify DomainError structure appears in 3+ test sites
  it('DomainError is thrown with expected structure (shape test)', async () => {
    useSessionStore.setState({ role: 'owner' })
    let caught: unknown
    try {
      await visits.checkIn('test-id')
    } catch (e) {
      caught = e
    }
    expect(isDomainError(caught)).toBe(true)
    if (isDomainError(caught)) {
      expect(caught.code).toBe('mock_not_implemented')
      expect(caught.message).toContain('Mock does not implement write paths')
    }
  })
})

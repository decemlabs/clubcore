import { describe, it, expect, beforeEach } from 'vitest'
import { useSessionStore } from '@/shared/session/store'
import { clients } from './clients'
import { resetDB, loadDB } from './_db'
import { isDomainError } from '@/shared/api/errors'

describe('mock/clients RBAC', () => {
  beforeEach(() => {
    resetDB()
  })

  it('allows owner to delete a client', async () => {
    useSessionStore.setState({ role: 'owner' })
    const db = loadDB()
    const target = db.clients[0]!
    await clients.remove(target.id)
    const after = loadDB()
    expect(after.clients.find((c) => c.id === target.id)).toBeUndefined()
  })

  it('forbids reception from deleting a client (DomainError forbidden)', async () => {
    useSessionStore.setState({ role: 'reception' })
    const db = loadDB()
    const target = db.clients[0]!
    let caught: unknown
    try {
      await clients.remove(target.id)
    } catch (e) {
      caught = e
    }
    expect(isDomainError(caught)).toBe(true)
    if (isDomainError(caught)) {
      expect(caught.code).toBe('forbidden')
    }
    const after = loadDB()
    expect(after.clients.find((c) => c.id === target.id)).toBeDefined()
  })

  it('allows reception to view the clients list', async () => {
    useSessionStore.setState({ role: 'reception' })
    const result = await clients.list({ page: 1, pageSize: 20 })
    expect(result.items.length).toBeGreaterThan(0)
    expect(result.pageSize).toBe(20)
  })
})

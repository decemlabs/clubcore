import { describe, it, expect, beforeEach } from 'vitest'
import { useSessionStore } from '@/shared/session/store'
import { trainers } from './trainers'
import { resetDB } from './_db'
import { isDomainError } from '@/shared/api/errors'

describe('mock/trainers RBAC', () => {
  beforeEach(() => {
    resetDB()
  })

  it('reception can list trainers with active=true (VIEW is not OWNER_ONLY)', async () => {
    useSessionStore.setState({ role: 'reception' })
    const result = await trainers.list({ active: true, page: 1, pageSize: 50 })
    expect(Array.isArray(result.items)).toBe(true)
    expect(result.items.every((t) => t.isActive === true)).toBe(true)
  })

  it('reception create throws DomainError forbidden', async () => {
    useSessionStore.setState({ role: 'reception' })
    let caught: unknown
    try {
      await trainers.create({ fullName: 'Тренер Тест' })
    } catch (e) {
      caught = e
    }
    expect(isDomainError(caught)).toBe(true)
    if (isDomainError(caught)) {
      expect(caught.code).toBe('forbidden')
    }
  })

  it('reception update throws DomainError forbidden', async () => {
    // First create as owner
    useSessionStore.setState({ role: 'owner' })
    const all = await trainers.list({ page: 1, pageSize: 50 })
    const target = all.items[0]!
    // Now try to update as reception
    useSessionStore.setState({ role: 'reception' })
    let caught: unknown
    try {
      await trainers.update(target.id, { fullName: target.fullName, isActive: false })
    } catch (e) {
      caught = e
    }
    expect(isDomainError(caught)).toBe(true)
    if (isDomainError(caught)) {
      expect(caught.code).toBe('forbidden')
    }
  })

  it('reception delete throws DomainError forbidden', async () => {
    useSessionStore.setState({ role: 'owner' })
    const all = await trainers.list({ page: 1, pageSize: 50 })
    const target = all.items[0]!
    useSessionStore.setState({ role: 'reception' })
    let caught: unknown
    try {
      await trainers.delete(target.id)
    } catch (e) {
      caught = e
    }
    expect(isDomainError(caught)).toBe(true)
    if (isDomainError(caught)) {
      expect(caught.code).toBe('forbidden')
    }
  })

  it('owner can successfully create, update, and delete trainers', async () => {
    useSessionStore.setState({ role: 'owner' })
    const created = await trainers.create({ fullName: 'Новый тренер', phone: '+79991112233' })
    expect(created.isActive).toBe(true)
    const updated = await trainers.update(created.id, { fullName: 'Обновлённый тренер', isActive: false })
    expect(updated.isActive).toBe(false)
    await trainers.delete(updated.id)
    const found = await trainers.get(updated.id)
    expect(found).toBeUndefined()
  })
})

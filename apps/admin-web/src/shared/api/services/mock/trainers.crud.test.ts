import { describe, it, expect, beforeEach } from 'vitest'
import { useSessionStore } from '@/shared/session/store'
import { trainers } from './trainers'
import { resetDB, loadDB } from './_db'
import { isDomainError } from '@/shared/api/errors'
describe('mock/trainers CRUD', () => {
  beforeEach(() => {
    resetDB()
    useSessionStore.setState({ role: 'owner' })
  })

  it('list returns 8 seeded trainers on first call (lazy seed)', async () => {
    const result = await trainers.list({ page: 1, pageSize: 50 })
    expect(result.total).toBe(8)
    expect(result.items.length).toBe(8)
    expect(result.page).toBe(1)
    expect(result.pageSize).toBe(50)
  })

  it('list with active=true returns only the 5 active trainers', async () => {
    const result = await trainers.list({ active: true, page: 1, pageSize: 50 })
    expect(result.total).toBe(5)
    expect(result.items.every((t) => t.isActive === true)).toBe(true)
  })

  it('list with active=false returns only the 3 inactive trainers', async () => {
    const result = await trainers.list({ active: false, page: 1, pageSize: 50 })
    expect(result.total).toBe(3)
    expect(result.items.every((t) => t.isActive === false)).toBe(true)
  })

  it('create returns a new trainer with isActive=true and persists it', async () => {
    const created = await trainers.create({ fullName: 'Иванов Иван', phone: '+79990000001' })
    expect(created.isActive).toBe(true)
    expect(created.fullName).toBe('Иванов Иван')
    expect(created.phone).toBe('+79990000001')
    expect(typeof created.id).toBe('string')
    const db = loadDB()
    expect(db.trainers.find((t) => t.id === created.id)).toBeDefined()
  })

  it('create with duplicate phone throws DomainError code=validation_failed with field phone', async () => {
    await trainers.create({ fullName: 'Тренер А', phone: '+79990000002' })
    let caught: unknown
    try {
      await trainers.create({ fullName: 'Тренер Б', phone: '+79990000002' })
    } catch (e) {
      caught = e
    }
    expect(isDomainError(caught)).toBe(true)
    if (isDomainError(caught)) {
      expect(caught.code).toBe('validation_failed')
      expect(caught.fields).toBeDefined()
      expect(Array.isArray((caught.fields as Record<string, unknown>)['phone'])).toBe(true)
    }
  })

  it('create with empty fullName throws DomainError with validation_failed', async () => {
    let caught: unknown
    try {
      await trainers.create({ fullName: '' })
    } catch (e) {
      caught = e
    }
    expect(isDomainError(caught)).toBe(true)
    if (isDomainError(caught)) {
      expect(caught.code).toBe('validation_failed')
    }
  })

  it('update isActive=false then list with active=false includes updated trainer', async () => {
    // Get first active trainer from seed
    const all = await trainers.list({ active: true, page: 1, pageSize: 50 })
    const target = all.items[0]!
    const updated = await trainers.update(target.id, {
      fullName: target.fullName,
      isActive: false,
    })
    expect(updated.isActive).toBe(false)
    const inactiveList = await trainers.list({ active: false, page: 1, pageSize: 50 })
    expect(inactiveList.items.some((t) => t.id === target.id)).toBe(true)
  })

  it('get returns trainer by id', async () => {
    const all = await trainers.list({ page: 1, pageSize: 50 })
    const target = all.items[0]!
    const found = await trainers.get(target.id)
    expect(found).toBeDefined()
    expect(found?.id).toBe(target.id)
  })

  it('delete removes trainer from list', async () => {
    const all = await trainers.list({ page: 1, pageSize: 50 })
    const target = all.items[0]!
    await trainers.delete(target.id)
    const after = await trainers.list({ page: 1, pageSize: 50 })
    expect(after.items.find((t) => t.id === target.id)).toBeUndefined()
  })

  it('loadDB returns object with trainers key initialized to [] when fresh', () => {
    // Already reset in beforeEach, but force fresh state
    resetDB()
    // Before any list() call, db.trainers should be [] (seeded on loadDB call in seed())
    const db = loadDB()
    // After resetDB, a fresh loadDB triggers seed() which sets trainers: []
    expect(Array.isArray(db.trainers)).toBe(true)
  })

  it('saveDB/loadDB roundtrip preserves trainers array', async () => {
    // Trigger seed by calling list
    const result = await trainers.list({ page: 1, pageSize: 50 })
    const firstId = result.items[0]!.id
    // Reload from storage
    const db = loadDB()
    expect(db.trainers.find((t) => t.id === firstId)).toBeDefined()
  })
})

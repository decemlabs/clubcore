import { describe, it, expect, beforeEach } from 'vitest'
import { useSessionStore } from '@/shared/session/store'
import { clients } from './clients'
import { resetDB, loadDB } from './_db'
import { isDomainError } from '@/shared/api/errors'

describe('mock/clients CRUD', () => {
  beforeEach(() => {
    resetDB()
    useSessionStore.setState({ role: 'owner' })
  })

  it('paginates list results to {items,total,page,pageSize} shape', async () => {
    const result = await clients.list({ page: 1, pageSize: 10 })
    expect(result).toMatchObject({
      page: 1,
      pageSize: 10,
    })
    expect(Array.isArray(result.items)).toBe(true)
    expect(result.items.length).toBeLessThanOrEqual(10)
    expect(typeof result.total).toBe('number')
  })

  it('filters by q via case-insensitive substring on fullName + phone', async () => {
    const all = await clients.list({ page: 1, pageSize: 100 })
    const sample = all.items[0]!
    const needle = sample.fullName.split(' ')[0]!.slice(0, 3).toLowerCase()
    const result = await clients.list({ q: needle, page: 1, pageSize: 100 })
    expect(result.items.length).toBeGreaterThan(0)
    expect(result.items.some((c) => c.fullName.toLowerCase().includes(needle))).toBe(true)
  })

  it('returns empty page for q with no matches', async () => {
    const result = await clients.list({ q: 'zzznobody123', page: 1, pageSize: 20 })
    expect(result.items).toEqual([])
    expect(result.total).toBe(0)
  })

  it('creates a client with valid input', async () => {
    const created = await clients.create({
      lastName: 'Иванов',
      firstName: 'Иван',
      phone: '+79991234567',
    })
    expect(created.fullName).toBe('Иванов Иван')
    expect(created.phone).toBe('+79991234567')
    const db = loadDB()
    expect(db.clients.find((c) => c.id === created.id)).toBeDefined()
  })

  it('rejects create with invalid phone (DomainError validation_failed)', async () => {
    let caught: unknown
    try {
      await clients.create({ lastName: 'И', firstName: 'И', phone: '12' })
    } catch (e) {
      caught = e
    }
    expect(isDomainError(caught)).toBe(true)
    if (isDomainError(caught)) {
      expect(caught.code).toBe('validation_failed')
      expect(caught.fields).toBeDefined()
    }
  })

  it('rejects create with duplicate phone', async () => {
    const phone = '+79990001122'
    await clients.create({ lastName: 'А', firstName: 'А', phone })
    let caught: unknown
    try {
      await clients.create({ lastName: 'Б', firstName: 'Б', phone })
    } catch (e) {
      caught = e
    }
    expect(isDomainError(caught)).toBe(true)
  })

  it('updates a client (partial diff)', async () => {
    const all = await clients.list({ page: 1, pageSize: 1 })
    const target = all.items[0]!
    const updated = await clients.update(target.id, { notes: 'тестовая заметка' })
    expect(updated.notes).toBe('тестовая заметка')
    expect(updated.id).toBe(target.id)
  })

  it('preserves split-by-space behavior on partial name update of a 4-token full name (mock-only contract)', async () => {
    // Lock current mock behavior: backend Phase 8 stores three columns; this test guards
    // the current split-by-space heuristic so we notice if behavior shifts.
    const created = await clients.create({
      lastName: 'Иванов',
      firstName: 'Петров',
      middleName: 'Иван',
      phone: '+79995554433',
    })
    const updated = await clients.update(created.id, { firstName: 'Сергей' })
    // Current heuristic: split current.fullName by space when caller did not pass all parts.
    expect(updated.fullName.split(' ').length).toBeGreaterThanOrEqual(3)
    expect(updated.fullName).toContain('Сергей')
  })

  it('throws not_found on update of missing id', async () => {
    let caught: unknown
    try {
      await clients.update('11111111-1111-4111-8111-111111111111' as never, { notes: 'x' })
    } catch (e) {
      caught = e
    }
    expect(isDomainError(caught)).toBe(true)
    if (isDomainError(caught)) expect(caught.code).toBe('not_found')
  })
})

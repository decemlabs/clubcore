import { faker } from '@faker-js/faker'
import type {
  ClientsService,
  ClientsListQuery,
  ClientCreateInput,
  ClientUpdateInput,
} from '@/shared/api/contracts/clients'
import type { Client, ClientId, Pagination } from '@/entities/client'
import { DomainError } from '@/shared/api/errors'
import { can } from '@/shared/session/can'
import { useSessionStore } from '@/shared/session/store'
import { clientCreateSchema, clientUpdateSchema } from '@/entities/client/schema'
import { loadDB, saveDB } from './_db'
import { delay } from './_latency'

function role() {
  return useSessionStore.getState().role
}

function ensure(action: 'view' | 'edit' | 'delete', resource: 'clients') {
  if (!can(role(), action, resource)) {
    throw new DomainError('forbidden', 'Доступ запрещён')
  }
}

function buildFullName(input: ClientCreateInput): string {
  // Mock-only: composite last names (e.g. "Иванов Петров Иван") are split-by-space;
  // backend Phase 8 stores three separate columns. v1.2+ may revisit.
  return [input.lastName, input.firstName, input.middleName].filter(Boolean).join(' ')
}

function searchHay(c: Client): string {
  return `${c.fullName} ${c.phone}`.toLowerCase()
}

export const clients: ClientsService = {
  async list(query: ClientsListQuery): Promise<Pagination<Client>> {
    await delay()
    ensure('view', 'clients')
    const db = loadDB()
    const q = query.q?.trim().toLowerCase() ?? ''
    const filtered = q
      ? db.clients.filter((c) => searchHay(c).includes(q))
      : db.clients
    const sorted = [...filtered].sort((a, b) => b.createdAt.localeCompare(a.createdAt))
    const total = sorted.length
    const start = (query.page - 1) * query.pageSize
    const items = sorted.slice(start, start + query.pageSize)
    return { items, total, page: query.page, pageSize: query.pageSize }
  },

  async get(id: ClientId): Promise<Client> {
    await delay()
    ensure('view', 'clients')
    const db = loadDB()
    const found = db.clients.find((c) => c.id === id)
    if (!found) throw new DomainError('not_found', 'Клиент не найден')
    return found
  },

  async create(input: ClientCreateInput): Promise<Client> {
    await delay()
    ensure('edit', 'clients')
    const parsed = clientCreateSchema.safeParse(input)
    if (!parsed.success) {
      const fields: Record<string, string[]> = {}
      for (const issue of parsed.error.issues) {
        const k = String(issue.path[0] ?? 'root')
        ;(fields[k] ??= []).push(issue.message)
      }
      throw new DomainError('validation_failed', 'Проверьте поля формы', fields)
    }
    const db = loadDB()
    if (db.clients.some((c) => c.phone === parsed.data.phone)) {
      throw new DomainError('validation_failed', 'Дубликат телефона', {
        phone: ['Клиент с таким телефоном уже существует'],
      })
    }
    const newClient: Client = {
      id: faker.string.uuid() as ClientId,
      fullName: buildFullName(parsed.data),
      phone: parsed.data.phone,
      email: parsed.data.email || undefined,
      birthDate: parsed.data.birthDate || undefined,
      notes: parsed.data.notes,
      createdAt: new Date().toISOString(),
    }
    db.clients = [newClient, ...db.clients]
    saveDB(db)
    return newClient
  },

  async update(id: ClientId, input: ClientUpdateInput): Promise<Client> {
    await delay()
    ensure('edit', 'clients')
    const parsed = clientUpdateSchema.safeParse(input)
    if (!parsed.success) {
      const fields: Record<string, string[]> = {}
      for (const issue of parsed.error.issues) {
        const k = String(issue.path[0] ?? 'root')
        ;(fields[k] ??= []).push(issue.message)
      }
      throw new DomainError('validation_failed', 'Проверьте поля формы', fields)
    }
    const db = loadDB()
    const idx = db.clients.findIndex((c) => c.id === id)
    if (idx < 0) throw new DomainError('not_found', 'Клиент не найден')
    const current = db.clients[idx]!
    const merged: Client = {
      ...current,
      ...parsed.data,
      fullName:
        parsed.data.lastName || parsed.data.firstName || parsed.data.middleName
          ? buildFullName({
              lastName: parsed.data.lastName ?? current.fullName.split(' ')[0] ?? '',
              firstName: parsed.data.firstName ?? current.fullName.split(' ')[1] ?? '',
              middleName: parsed.data.middleName ?? current.fullName.split(' ')[2],
              phone: parsed.data.phone ?? current.phone,
            })
          : current.fullName,
      email: parsed.data.email !== undefined ? parsed.data.email || undefined : current.email,
      birthDate:
        parsed.data.birthDate !== undefined
          ? parsed.data.birthDate || undefined
          : current.birthDate,
    }
    db.clients[idx] = merged
    saveDB(db)
    return merged
  },

  async remove(id: ClientId): Promise<void> {
    await delay()
    ensure('delete', 'clients')
    const db = loadDB()
    const idx = db.clients.findIndex((c) => c.id === id)
    if (idx < 0) throw new DomainError('not_found', 'Клиент не найден')
    db.clients.splice(idx, 1)
    saveDB(db)
  },
}

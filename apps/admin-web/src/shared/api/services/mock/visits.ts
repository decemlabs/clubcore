import type { VisitsService, VisitsListQuery } from '@/shared/api/contracts/visits'
import type { Visit, VisitId } from '@/entities/visit'
import { DomainError } from '@/shared/api/errors'
import { can } from '@/shared/session/can'
import { useSessionStore } from '@/shared/session/store'
import type { Action, Resource } from '@/shared/session/registry'
import { loadDB } from './_db'
import { delay } from './_latency'

function role() {
  return useSessionStore.getState().role
}

function ensure(action: Action, resource: Resource) {
  if (!can(role(), action, resource)) {
    throw new DomainError('forbidden', 'Доступ запрещён')
  }
}

export const visits: VisitsService = {
  async list(query: VisitsListQuery) {
    await delay()
    ensure('view', 'visits')
    const db = loadDB()
    let items = db.visits
    if (query.clientId) items = items.filter((v) => v.clientId === query.clientId)
    if (query.from) items = items.filter((v) => v.gymDate >= query.from!)
    if (query.to) items = items.filter((v) => v.gymDate <= query.to!)
    items = [...items].sort((a, b) => b.checkedInAt.localeCompare(a.checkedInAt))
    const start = (query.page - 1) * query.pageSize
    return {
      items: items.slice(start, start + query.pageSize),
      total: items.length,
      page: query.page,
      pageSize: query.pageSize,
    }
  },

  async recentByClient(clientId: string, { limit }: { limit: number }) {
    await delay()
    ensure('view', 'visits')
    const db = loadDB()
    return [...db.visits]
      .filter((v) => v.clientId === clientId)
      .sort((a, b) => b.checkedInAt.localeCompare(a.checkedInAt))
      .slice(0, limit)
  },

  async get(id: VisitId) {
    await delay()
    ensure('view', 'visits')
    const v = loadDB().visits.find((x) => x.id === id)
    if (!v) throw new DomainError('not_found', 'Посещение не найдено')
    return v
  },

  async checkIn(): Promise<Visit> {
    await delay()
    throw new DomainError(
      'mock_not_implemented',
      'Mock does not implement write paths — use VITE_API_MODE=http',
    )
  },

  async gymMeta() {
    await delay()
    // No RBAC ensure needed — endpoint is reception+owner viewable; current FE roles satisfy.
    return { gymHoursStart: '07:00', gymHoursEnd: '23:00' }
  },
}

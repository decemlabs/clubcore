import type {
  MembershipsService,
  MembershipsListQuery,
  MembershipPlansListQuery,
} from '@/shared/api/contracts/memberships'
import type { MembershipId, MembershipPlanId, Pagination, Membership, MembershipPlan } from '@/entities/membership'
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

export const memberships: MembershipsService = {
  async list(query: MembershipsListQuery): Promise<Pagination<Membership>> {
    await delay()
    ensure('view', 'memberships')
    const db = loadDB()
    const all = db.memberships
    const total = all.length
    const start = (query.page - 1) * query.pageSize
    const items = all.slice(start, start + query.pageSize)
    return { items, total, page: query.page, pageSize: query.pageSize }
  },

  async byClient(clientId: string): Promise<Pagination<Membership>> {
    await delay()
    ensure('view', 'memberships')
    const db = loadDB()
    const filtered = db.memberships.filter((m) => m.clientId === clientId)
    return { items: filtered, total: filtered.length, page: 1, pageSize: filtered.length }
  },

  async get(id: MembershipId): Promise<Membership> {
    await delay()
    ensure('view', 'memberships')
    const db = loadDB()
    const found = db.memberships.find((m) => m.id === id)
    if (!found) throw new DomainError('not_found', 'Абонемент не найден')
    return found
  },

  async create(): Promise<Membership> {
    await delay()
    throw new DomainError(
      'mock_not_implemented',
      'Mock does not implement write paths — use VITE_API_MODE=http',
    )
  },

  async cancel(): Promise<Membership> {
    await delay()
    throw new DomainError(
      'mock_not_implemented',
      'Mock does not implement write paths — use VITE_API_MODE=http',
    )
  },

  async listPlans(query: MembershipPlansListQuery): Promise<Pagination<MembershipPlan>> {
    await delay()
    ensure('view', 'membership-plans')
    const db = loadDB()
    const filtered =
      query.active !== undefined ? db.plans.filter((p) => p.active === query.active) : db.plans
    const page = query.page ?? 1
    const pageSize = query.pageSize ?? 50
    const total = filtered.length
    const start = (page - 1) * pageSize
    const items = filtered.slice(start, start + pageSize)
    return { items, total, page, pageSize }
  },

  async getPlan(id: MembershipPlanId): Promise<MembershipPlan> {
    await delay()
    ensure('view', 'membership-plans')
    const db = loadDB()
    const found = db.plans.find((p) => p.id === id)
    if (!found) throw new DomainError('not_found', 'Тариф не найден')
    return found
  },

  async createPlan(): Promise<MembershipPlan> {
    await delay()
    throw new DomainError(
      'mock_not_implemented',
      'Mock does not implement write paths — use VITE_API_MODE=http',
    )
  },

  async updatePlan(): Promise<MembershipPlan> {
    await delay()
    throw new DomainError(
      'mock_not_implemented',
      'Mock does not implement write paths — use VITE_API_MODE=http',
    )
  },

  async deletePlan(): Promise<void> {
    await delay()
    throw new DomainError(
      'mock_not_implemented',
      'Mock does not implement write paths — use VITE_API_MODE=http',
    )
  },
}

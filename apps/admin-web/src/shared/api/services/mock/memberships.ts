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
import { todayMSK } from '@/shared/i18n/date'
import { loadDB } from './_db'
import { delay } from './_latency'

// D-22-10 mirror: keep mock filter window in sync with the http adapter.
const EXPIRING_DAYS = 7

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
    let all = db.memberships
    if (query.clientId) {
      all = all.filter((m) => m.clientId === query.clientId)
    }
    // WR-07: apply expiring filter symmetrically with http adapter so the
    // toggle on MembershipsListPage isn't a silent no-op in mock mode.
    // BLK-06: when expiring=true, return ALL filtered items in a single page
    // (no slicing) so the contract matches the http adapter, which cannot
    // honestly paginate without backend ?expiring=true support. UI hides the
    // pagination footer in this branch.
    if (query.expiring) {
      const todayStr = todayMSK()
      const cutoff = new Date(todayStr)
      cutoff.setUTCDate(cutoff.getUTCDate() + EXPIRING_DAYS)
      const cutoffStr = cutoff.toISOString().slice(0, 10)
      const items = all.filter(
        (m) => m.status === 'active' && m.endDate >= todayStr && m.endDate <= cutoffStr,
      )
      return { items, total: items.length, page: 1, pageSize: Math.max(1, items.length) }
    }
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
    // pageSize is a request constant — never 0 (would make consumers' Math.ceil
    // divide by zero). Use Math.max(1, filtered.length) as a sane shape.
    return {
      items: filtered,
      total: filtered.length,
      page: 1,
      pageSize: Math.max(1, filtered.length),
    }
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

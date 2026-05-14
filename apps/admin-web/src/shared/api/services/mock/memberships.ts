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
import { faker } from '@faker-js/faker'
import { loadDB, saveDB } from './_db'
import { delay } from './_latency'

// DEBT-02 (Phase 24): window size flows in via `query.within`; default 7 matches
// the legacy FE-08 D-2 behaviour. No module-local window constant.

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
    if (query.status) {
      all = all.filter((m) => m.status === query.status)
    }
    // DEBT-02 (Phase 24): window comes from `query.within ?? 7` (no module
    // constant). Inclusive end-date semantics match the backend predicate
    // `end_date <= today + (within - 1)`. Mock keeps the BLK-06 single-page
    // collapse — only the http adapter strips it (the backend now paginates
    // the filtered set honestly; the mock stays in-memory and predictable).
    if (query.expiring) {
      const within = query.within ?? 7
      const todayStr = todayMSK()
      const cutoff = new Date(todayStr)
      cutoff.setUTCDate(cutoff.getUTCDate() + (within - 1))
      const cutoffStr = cutoff.toISOString().slice(0, 10)
      // DEBT-05: respect query.status across expiring branch (was hardcoded 'active').
      // The verbatim REQ wording mentions the «Заморожен» pill no-op, but that path
      // (status=frozen, expiring=false) already works via the early `if (query.status)`
      // filter above. The actual bug is the status+expiring=true combination where the
      // expiring branch hardcoded `m.status === 'active'` and overrode the user's status
      // filter. The fix respects query.status here too. Phase 30 / v1.3 Phase 28 gap closure.
      const wantedStatus = query.status ?? 'active'
      const items = all.filter(
        (m) => m.status === wantedStatus && m.endDate >= todayStr && m.endDate <= cutoffStr,
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

  async freeze(id: MembershipId): Promise<Membership> {
    await delay()
    ensure('create', 'memberships')
    const db = loadDB()
    const idx = db.memberships.findIndex((m) => m.id === id)
    if (idx === -1) throw new DomainError('not_found', 'Абонемент не найден')
    const m = db.memberships[idx]!
    if (m.status === 'frozen') throw new DomainError('already_frozen', 'Абонемент уже заморожен.')
    if (m.status !== 'active')
      throw new DomainError(
        'invalid_transition',
        'Нельзя заморозить: статус абонемента не позволяет это действие.',
      )
    if (m.freezeDaysRemaining <= 0)
      throw new DomainError('freeze_limit_exceeded', 'Лимит дней заморозки исчерпан.')
    const now = new Date().toISOString()
    const updated: Membership = {
      ...m,
      status: 'frozen',
      currentFreezePeriod: {
        id: faker.string.uuid(),
        startedAt: now,
        startedBy: role(),
        endedAt: null,
        endedBy: null,
      },
      updatedAt: now,
    }
    db.memberships[idx] = updated
    saveDB(db)
    return updated
  },

  async unfreeze(id: MembershipId): Promise<Membership> {
    await delay()
    ensure('create', 'memberships')
    const db = loadDB()
    const idx = db.memberships.findIndex((m) => m.id === id)
    if (idx === -1) throw new DomainError('not_found', 'Абонемент не найден')
    const m = db.memberships[idx]!
    if (m.status !== 'frozen' || !m.currentFreezePeriod) {
      throw new DomainError(
        'invalid_transition',
        'Нельзя снять заморозку: абонемент не заморожен.',
      )
    }
    const now = new Date()
    const startedAt = new Date(m.currentFreezePeriod.startedAt)
    const daysFrozen = Math.max(1, Math.ceil((now.getTime() - startedAt.getTime()) / 86_400_000))
    const newEnd = new Date(m.endDate)
    newEnd.setUTCDate(newEnd.getUTCDate() + daysFrozen)
    const newUsed = m.freezeDaysUsed + daysFrozen
    const newRemaining = Math.max(m.freezeDaysLimitSnapshot - newUsed, 0)
    const nowIso = now.toISOString()
    const updated: Membership = {
      ...m,
      status: 'active',
      endDate: newEnd.toISOString().slice(0, 10),
      freezeDaysUsed: newUsed,
      freezeDaysRemaining: newRemaining,
      currentFreezePeriod: null,
      updatedAt: nowIso,
    }
    db.memberships[idx] = updated
    saveDB(db)
    return updated
  },

  async renew(id: MembershipId): Promise<Membership> {
    await delay()
    ensure('create', 'memberships')
    const db = loadDB()
    const source = db.memberships.find((m) => m.id === id)
    if (!source) throw new DomainError('not_found', 'Абонемент не найден')
    if (source.status === 'cancelled')
      throw new DomainError('cannot_renew_cancelled', 'Нельзя продлить отменённый абонемент.')
    const plan = db.plans.find((p) => p.id === source.planId)
    if (!plan || !plan.active)
      throw new DomainError('plan_archived', 'Тариф архивирован — продление недоступно.')
    const today = todayMSK()
    const afterEnd = new Date(source.endDate)
    afterEnd.setUTCDate(afterEnd.getUTCDate() + 1)
    const afterEndStr = afterEnd.toISOString().slice(0, 10)
    const newStart = afterEndStr > today ? afterEndStr : today
    const newEndDate = new Date(newStart)
    newEndDate.setUTCDate(newEndDate.getUTCDate() + source.durationDaysSnapshot - 1)
    const now = new Date().toISOString()
    const newMembership: Membership = {
      ...source,
      id: faker.string.uuid() as MembershipId,
      startDate: newStart,
      endDate: newEndDate.toISOString().slice(0, 10),
      status: 'active',
      previousMembershipId: source.id,
      currentFreezePeriod: null,
      freezeDaysUsed: 0,
      freezeDaysRemaining: source.freezeDaysLimitSnapshot,
      cancelledAt: null,
      cancelReason: null,
      paidAt: now,
      createdAt: now,
      updatedAt: now,
    }
    db.memberships.push(newMembership)
    saveDB(db)
    return newMembership
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

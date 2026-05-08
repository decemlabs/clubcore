import { request, type components } from '@sportzal/api-client'
import type {
  MembershipsService,
  MembershipsListQuery,
  MembershipPlansListQuery,
  MembershipCreateInput,
  MembershipPlanCreateInput,
  MembershipPlanUpdateInput,
} from '@/shared/api/contracts/memberships'
import type { MembershipId, MembershipPlanId } from '@/entities/membership'
import { todayMSK } from '@/shared/i18n/date'
import { unwrap } from './_envelope'
import {
  responseToMembership,
  responseToMembershipPlan,
  createInputToRequest,
  planCreateInputToRequest,
  planUpdateInputToRequest,
} from './_membershipsAdapter'

type MembershipResponse = components['schemas']['MembershipResponse']
type MembershipPlanResponse = components['schemas']['MembershipPlanResponse']

interface PaginatedMembershipResponse {
  items: MembershipResponse[]
  total: number
  page: number
  pageSize: number
}

interface PaginatedMembershipPlanResponse {
  items: MembershipPlanResponse[]
  total: number
  page: number
  pageSize: number
}

// D-22-10: expiringWithinDays NOT present in backend query params (schema.d.ts verified).
// Client-side filtering is applied in the list method.
const EXPIRING_DAYS = 7

export const memberships: MembershipsService = {
  async list(query: MembershipsListQuery) {
    const q: Record<string, string | number> = {
      page: query.page,
      pageSize: query.pageSize,
    }
    if (query.clientId) q.clientId = query.clientId
    const raw = unwrap<PaginatedMembershipResponse>(
      await request('get', '/api/v1/memberships', { query: q }),
    )
    let items = raw.items.map(responseToMembership)
    // D-22-10: client-side expiring filter applied AFTER pagination because the
    // backend has no expiringWithinDays param yet. Pinned to Europe/Moscow via
    // todayMSK() — adjacent code (CheckInPage, RecentVisitsBlock,
    // useMembershipStatusForClient) all use MSK; do not drift to runtime TZ
    // (WR-03).
    //
    // BLK-06: pagination is meaningless while expiring=true — the backend page
    // contains both expiring and non-expiring rows, and `raw.total` counts ALL
    // memberships, not the filtered subset. To keep the contract uniform with
    // the mock impl and avoid misleading the operator (page 2 of "200 results"
    // returning 0 visible items), we collapse the response to a single
    // unpaginated page of whatever filtered items happen to be on THIS backend
    // page. The UI MUST hide the pagination footer when expiring=true
    // (MembershipsListPage does so). Tracking issue: add backend
    // ?expiring=true&within=7 so this branch can paginate honestly.
    if (query.expiring) {
      const todayStr = todayMSK()
      // YYYY-MM-DD parses as UTC midnight — UTC arithmetic is DST-safe.
      const cutoff = new Date(todayStr)
      cutoff.setUTCDate(cutoff.getUTCDate() + EXPIRING_DAYS)
      const cutoffStr = cutoff.toISOString().slice(0, 10)
      items = items.filter(
        (m) => m.status === 'active' && m.endDate >= todayStr && m.endDate <= cutoffStr,
      )
      // pageSize must be >= 1 — UI's Math.ceil(total/pageSize) would NaN otherwise.
      return { items, total: items.length, page: 1, pageSize: Math.max(1, items.length) }
    }
    return { ...raw, items }
  },

  async byClient(clientId: string) {
    // WR-06: pageSize is hardcoded to 100 — for long-lived members, history
    // beyond the first 100 rows is silently truncated. Tracking issue: add
    // pagination UI to MembershipsBlock or backend sort + cursor support.
    const raw = unwrap<PaginatedMembershipResponse>(
      await request('get', '/api/v1/memberships', { query: { clientId, page: 1, pageSize: 100 } }),
    )
    // WR-17: warn (not throw) when truncation actually happens so a long-lived
    // gym member's missing history is at least visible in the dev console
    // until proper pagination ships.
    if (raw.total > raw.items.length) {
      // eslint-disable-next-line no-console
      console.warn(
        `[memberships.byClient] truncated: client=${clientId} total=${raw.total} returned=${raw.items.length} (pageSize=100). Add pagination to MembershipsBlock.`,
      )
    }
    return { ...raw, items: raw.items.map(responseToMembership) }
  },

  async get(id: MembershipId) {
    const raw = unwrap<MembershipResponse>(
      await request('get', '/api/v1/memberships/{membership_id}', {
        params: { membership_id: id },
      }),
    )
    return responseToMembership(raw)
  },

  async create(input: MembershipCreateInput) {
    const raw = unwrap<MembershipResponse>(
      await request('post', '/api/v1/memberships', { body: createInputToRequest(input) }),
    )
    return responseToMembership(raw)
  },

  async cancel(id: MembershipId, reason?: string) {
    const raw = unwrap<MembershipResponse>(
      await request('post', '/api/v1/memberships/{membership_id}/cancel', {
        params: { membership_id: id },
        body: reason ? { reason } : {},
      }),
    )
    return responseToMembership(raw)
  },

  async listPlans(query: MembershipPlansListQuery) {
    const q: Record<string, string | number | boolean> = {
      page: query.page ?? 1,
      pageSize: query.pageSize ?? 20,
    }
    if (query.active !== undefined) q.active = query.active
    const raw = unwrap<PaginatedMembershipPlanResponse>(
      await request('get', '/api/v1/membership-plans', { query: q }),
    )
    return { ...raw, items: raw.items.map(responseToMembershipPlan) }
  },

  async getPlan(id: MembershipPlanId) {
    const raw = unwrap<MembershipPlanResponse>(
      await request('get', '/api/v1/membership-plans/{plan_id}', {
        params: { plan_id: id },
      }),
    )
    return responseToMembershipPlan(raw)
  },

  async createPlan(input: MembershipPlanCreateInput) {
    const raw = unwrap<MembershipPlanResponse>(
      await request('post', '/api/v1/membership-plans', { body: planCreateInputToRequest(input) }),
    )
    return responseToMembershipPlan(raw)
  },

  async updatePlan(id: MembershipPlanId, input: MembershipPlanUpdateInput) {
    const raw = unwrap<MembershipPlanResponse>(
      await request('patch', '/api/v1/membership-plans/{plan_id}', {
        params: { plan_id: id },
        body: planUpdateInputToRequest(input),
      }),
    )
    return responseToMembershipPlan(raw)
  },

  async deletePlan(id: MembershipPlanId) {
    // 204 No Content — no unwrap needed
    await request('delete', '/api/v1/membership-plans/{plan_id}', {
      params: { plan_id: id },
    })
  },
}

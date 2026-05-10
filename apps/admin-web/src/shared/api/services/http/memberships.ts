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

// DEBT-02 (Phase 24): the http adapter forwards `expiring`/`within` to the
// backend (`/api/v1/memberships?expiring=true&within=N`) and no longer
// post-filters or collapses pagination. The backend paginates the filtered
// set honestly (Phase 24 plan 24-04 commit), so consumers can show real
// pagination controls when expiring=true. The previous client-side filter +
// BLK-06 single-page collapse are gone (D-24-13).
// TODO Phase 28 (FE-13): wire a `within` selector in MembershipsListPage.

export const memberships: MembershipsService = {
  async list(query: MembershipsListQuery) {
    const q: Record<string, string | number | boolean> = {
      page: query.page,
      pageSize: query.pageSize,
    }
    if (query.clientId) q.clientId = query.clientId
    if (query.status) q.status = query.status
    if (query.expiring) {
      q.expiring = true
      q.within = query.within ?? 7
    }
    const raw = unwrap<PaginatedMembershipResponse>(
      await request('get', '/api/v1/memberships', { query: q }),
    )
    return { ...raw, items: raw.items.map(responseToMembership) }
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

  async freeze(id: MembershipId) {
    const raw = unwrap<MembershipResponse>(
      await request('post', '/api/v1/memberships/{membership_id}/freeze', {
        params: { membership_id: id },
      }),
    )
    return responseToMembership(raw)
  },

  async unfreeze(id: MembershipId) {
    const raw = unwrap<MembershipResponse>(
      await request('post', '/api/v1/memberships/{membership_id}/unfreeze', {
        params: { membership_id: id },
      }),
    )
    return responseToMembership(raw)
  },

  async renew(id: MembershipId) {
    const raw = unwrap<MembershipResponse>(
      await request('post', '/api/v1/memberships/{membership_id}/renew', {
        params: { membership_id: id },
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

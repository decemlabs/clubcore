/**
 * Pure mapping helpers between backend Membership* schemas (Phase 17) and the FE
 * Membership / MembershipPlan domain types (Phase 22).
 *
 * Why this module exists (mirrors _clientsAdapter.ts philosophy):
 *  - Backend MembershipResponse uses camelCase (already, per Phase 4 D-21) so field
 *    renaming is minimal. The adapter brands IDs and narrows the status union.
 *  - MembershipPlanResponse is straightforward — only branding needed.
 *  - Create/update request mappers ensure optional fields are omitted (never null)
 *    per Phase 8 D-01 pattern: to leave a field unchanged, OMIT the key entirely.
 *
 * All helpers are pure (no I/O, no time, no randomness) and exported for unit testing.
 */
import type { components } from '@sportzal/api-client'
import type {
  Membership,
  FreezePeriod,
  MembershipId,
  MembershipPlan,
  MembershipPlanId,
  MembershipStatus,
} from '@/entities/membership'
import type {
  MembershipCreateInput,
  MembershipPlanCreateInput,
  MembershipPlanUpdateInput,
} from '@/shared/api/contracts/memberships'

type MembershipResponse = components['schemas']['MembershipResponse']
type MembershipPlanResponse = components['schemas']['MembershipPlanResponse']
type MembershipCreateRequest = components['schemas']['MembershipCreateRequest']
type MembershipPlanCreateRequest = components['schemas']['MembershipPlanCreateRequest']
type MembershipPlanUpdateRequest = components['schemas']['MembershipPlanUpdateRequest']

/**
 * Map a backend MembershipResponse to the FE Membership domain type.
 *
 * - Brands `id` and `planId` to their typed counterparts.
 * - Passes `endDate` through as-is — INCLUSIVE semantics per Phase 15.
 * - Narrows `status` to the FE union (backend enum values match exactly).
 * - Preserves nullable optional fields (`paidAt`, `notes`, etc.).
 */
export function responseToMembership(r: MembershipResponse): Membership {
  const fp = r.currentFreezePeriod
  const currentFreezePeriod: FreezePeriod | null = fp
    ? {
        id: fp.id,
        startedAt: fp.startedAt,
        startedBy: fp.startedBy,
        endedAt: fp.endedAt,
        endedBy: fp.endedBy,
      }
    : null
  return {
    id: r.id as MembershipId,
    clientId: r.clientId,
    planId: r.planId as MembershipPlanId,
    planNameSnapshot: r.planNameSnapshot,
    durationDaysSnapshot: r.durationDaysSnapshot,
    priceKopecksSnapshot: r.priceKopecksSnapshot,
    startDate: r.startDate,
    endDate: r.endDate,
    status: r.status as MembershipStatus,
    paidAt: r.paidAt ?? null,
    notes: r.notes ?? null,
    cancelledAt: r.cancelledAt ?? null,
    cancelReason: r.cancelReason ?? null,
    freezeDaysLimitSnapshot: r.freezeDaysLimitSnapshot,
    freezeDaysUsed: r.freezeDaysUsed,
    freezeDaysRemaining: r.freezeDaysRemaining,
    currentFreezePeriod,
    previousMembershipId: r.previousMembershipId ?? null,
    createdAt: r.createdAt,
    updatedAt: r.updatedAt,
  }
}

/**
 * Map a backend MembershipPlanResponse to the FE MembershipPlan domain type.
 *
 * - Brands `id` to MembershipPlanId.
 * - All fields map 1:1 (camelCase wire format matches FE type, per Phase 4 D-21).
 */
export function responseToMembershipPlan(r: MembershipPlanResponse): MembershipPlan {
  return {
    id: r.id as MembershipPlanId,
    name: r.name,
    durationDays: r.durationDays,
    priceKopecks: r.priceKopecks,
    freezeDaysLimit: r.freezeDaysLimit,
    active: r.active,
    createdAt: r.createdAt,
    updatedAt: r.updatedAt,
  }
}

/**
 * Map FE MembershipCreateInput to the backend MembershipCreateRequest body.
 *
 * - OMITS optional fields whose value is absent — never substitutes null (D-01).
 * - `paidAt` defaults to server-computed now() when omitted.
 */
export function createInputToRequest(input: MembershipCreateInput): MembershipCreateRequest {
  const out: MembershipCreateRequest = {
    clientId: input.clientId,
    planId: input.planId,
  }
  if (input.paidAt) out.paidAt = input.paidAt
  if (input.notes) out.notes = input.notes.trim() || undefined
  return out
}

/**
 * Map FE MembershipPlanCreateInput to the backend MembershipPlanCreateRequest body.
 */
export function planCreateInputToRequest(input: MembershipPlanCreateInput): MembershipPlanCreateRequest {
  return {
    name: input.name,
    durationDays: input.durationDays,
    priceKopecks: input.priceKopecks,
    freezeDaysLimit: input.freezeDaysLimit,
    active: input.active ?? true,
  }
}

/**
 * Map FE MembershipPlanUpdateInput to the backend MembershipPlanUpdateRequest body.
 *
 * - Only include keys that are explicitly provided (Partial input).
 * - `durationDays` is intentionally absent — backend rejects it with 422 (MEM-PLAN-EP-03).
 */
export function planUpdateInputToRequest(input: MembershipPlanUpdateInput): MembershipPlanUpdateRequest {
  const out: MembershipPlanUpdateRequest = {}
  if (input.name !== undefined) out.name = input.name
  if (input.priceKopecks !== undefined) out.priceKopecks = input.priceKopecks
  if (input.active !== undefined) out.active = input.active
  return out
}

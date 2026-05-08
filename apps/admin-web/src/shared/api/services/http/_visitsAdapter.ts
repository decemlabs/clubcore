/**
 * Pure mapping helpers between backend Visit* schemas and the FE Visit domain type / GymMeta.
 *
 * Why this module exists (mirrors _clientsAdapter.ts rationale):
 *  - Separates transport-level schema types from FE domain types.
 *  - responseToVisit handles VisitId brand cast + channel type narrowing.
 *  - responseToGymMeta extracts gymHoursStart/gymHoursEnd from the _meta response.
 *
 * All helpers are pure (no I/O, no time, no randomness).
 */
import type { components } from '@sportzal/api-client'
import type { Visit, VisitId, VisitChannel } from '@/entities/visit'
import type { GymMeta } from '@/shared/api/contracts/visits'

type VisitResponse = components['schemas']['VisitResponse']
type VisitsMetaResponse = components['schemas']['VisitsMetaResponse']

/**
 * Map a backend VisitResponse to the FE Visit domain type.
 *
 * - Casts `id` to branded VisitId.
 * - Narrows `channel` string to VisitChannel union.
 * - Passes `checkedInBy` through as `string | null` (null for telegram_bot).
 */
export function responseToVisit(r: VisitResponse): Visit {
  return {
    id: r.id as VisitId,
    clientId: r.clientId,
    membershipId: r.membershipId,
    checkedInAt: r.checkedInAt,
    gymDate: r.gymDate,
    channel: r.channel as VisitChannel,
    checkedInBy: r.checkedInBy ?? null,
    createdAt: r.createdAt,
  }
}

/**
 * Map a backend VisitsMetaResponse to the FE GymMeta type.
 */
export function responseToGymMeta(r: VisitsMetaResponse): GymMeta {
  return {
    gymHoursStart: r.gymHoursStart,
    gymHoursEnd: r.gymHoursEnd,
  }
}

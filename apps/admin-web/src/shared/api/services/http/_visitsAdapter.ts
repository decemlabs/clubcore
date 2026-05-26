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
import type { components } from '@clubcore/api-client'
import type { Visit, VisitId, VisitChannel } from '@/entities/visit'
import type { GymMeta } from '@/shared/api/contracts/visits'

type VisitResponse = components['schemas']['VisitResponse']
type VisitsMetaResponse = components['schemas']['VisitsMetaResponse']

// WR-18: backend VisitResponse.channel is `str` (free-form), constrained only
// by a DB CHECK constraint. Narrow to the FE VisitChannel union at the seam
// instead of an unsafe `as VisitChannel` cast — protects every downstream
// consumer (RecentVisitsBlock channel badge, CheckInPage already-checked-in
// label) from silently mis-classifying a future channel value (e.g. NFC
// turnstile) as 'reception'.
const KNOWN_CHANNELS = new Set<VisitChannel>(['reception', 'telegram_bot'])

function narrowChannel(c: string): VisitChannel {
  if (KNOWN_CHANNELS.has(c as VisitChannel)) return c as VisitChannel
  console.warn(
    `[responseToVisit] unknown channel="${c}" — backend returned a value the FE union does not know about. Defaulting to 'reception'.`,
  )
  return 'reception'
}

/**
 * Map a backend VisitResponse to the FE Visit domain type.
 *
 * - Casts `id` to branded VisitId.
 * - Narrows `channel` string to VisitChannel union via narrowChannel (WR-18).
 * - Passes `checkedInBy` through as `string | null` (null for telegram_bot).
 */
export function responseToVisit(r: VisitResponse): Visit {
  return {
    id: r.id as VisitId,
    clientId: r.clientId,
    membershipId: r.membershipId,
    checkedInAt: r.checkedInAt,
    gymDate: r.gymDate,
    channel: narrowChannel(r.channel),
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

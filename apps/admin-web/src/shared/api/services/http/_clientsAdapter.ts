/**
 * Pure mapping helpers between backend Client* schemas (Phase 8) and the FE
 * Client domain type / ClientCreateInput / ClientUpdateInput (Phase 10).
 *
 * Why this module exists (Phase 11 INTEGRATION-CHECK F-01 / F-02):
 *  - Backend ClientResponse exposes `birthday` + separate `lastName/firstName/middleName`,
 *    while FE Client expects `birthDate` + composed `fullName`. Without an adapter,
 *    `VITE_API_MODE=http` rendered "undefined" everywhere.
 *  - Backend ClientCreateRequest uses `extra="forbid"` and `EmailStr`. Sending the FE
 *    key `birthDate` is a 422; sending `email: ''` is a 422. The request mappers
 *    rename + omit empty strings (NEVER substitute `null` — Phase 8 D-01).
 *
 * All three helpers are pure (no I/O, no time, no randomness) and are exported for
 * unit testing. The http ClientsService composes them in `clients.ts`.
 */
import type { components } from '@sportzal/api-client'
import type { Client, ClientId } from '@/entities/client'
import type {
  ClientCreateInput,
  ClientUpdateInput,
} from '@/shared/api/contracts/clients'

type ClientResponse = components['schemas']['ClientResponse']
type ClientCreateRequest = components['schemas']['ClientCreateRequest']
type ClientUpdateRequest = components['schemas']['ClientUpdateRequest']

/**
 * Map a backend ClientResponse to the FE Client domain type.
 *
 * - Composes `fullName = "lastName firstName middleName"` (single-space joined),
 *   dropping null/undefined/empty parts and trimming pathological whitespace.
 * - Renames `birthday` → `birthDate`; collapses `null` and `''` to `undefined`.
 * - Drops backend-only fields (`gender`, `tags`, `emergencyContact`,
 *   `telegramUserId`, `createdByUserId`, `updatedAt`) — Client stays narrow.
 * - Never sets `deletedAt` (backend 404s soft-deleted rows; Phase 8 D-XX).
 */
export function responseToClient(r: ClientResponse): Client {
  const fullName = [r.lastName, r.firstName, r.middleName]
    .filter((s): s is string => Boolean(s))
    .join(' ')
    .trim()

  const client: Client = {
    id: r.id as ClientId,
    fullName,
    phone: r.phone,
    createdAt: r.createdAt,
  }
  if (r.email) client.email = r.email
  if (r.birthday) client.birthDate = r.birthday
  if (r.notes) client.notes = r.notes
  return client
}

/**
 * Map FE ClientCreateInput to the backend ClientCreateRequest body.
 *
 * - Always sends `lastName`, `firstName`, `phone` (required by backend).
 * - Renames `birthDate` → `birthday`; the FE-only key `birthDate` never appears
 *   in the request body.
 * - OMITS any optional whose value is `''` or absent. Never substitutes `null` —
 *   `extra="forbid"` would not reject it, but D-01 reserves explicit null for v1.2+.
 */
export function createInputToRequest(input: ClientCreateInput): ClientCreateRequest {
  const out: ClientCreateRequest = {
    lastName: input.lastName,
    firstName: input.firstName,
    phone: input.phone,
  }
  if (input.middleName) out.middleName = input.middleName
  if (input.email) out.email = input.email
  if (input.birthDate) out.birthday = input.birthDate
  if (input.notes) out.notes = input.notes
  return out
}

/**
 * Map FE ClientUpdateInput (Partial<ClientCreateInput>) to ClientUpdateRequest.
 *
 * Same omission rules as `createInputToRequest`, applied per-key. Per Phase 8 D-01:
 * "to leave a field unchanged, OMIT the key entirely" — empty-string optionals
 * (e.g. `email: ''`) are treated as omit, NOT as explicit clear.
 */
export function updateInputToRequest(input: ClientUpdateInput): ClientUpdateRequest {
  const out: ClientUpdateRequest = {}
  if (input.lastName) out.lastName = input.lastName
  if (input.firstName) out.firstName = input.firstName
  if (input.phone) out.phone = input.phone
  if (input.middleName) out.middleName = input.middleName
  if (input.email) out.email = input.email
  if (input.birthDate) out.birthday = input.birthDate
  if (input.notes) out.notes = input.notes
  return out
}

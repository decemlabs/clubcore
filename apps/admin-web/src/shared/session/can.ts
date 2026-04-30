import type { Action, Resource } from './registry'
import type { Role } from './types'

export type { Action, Resource } from './registry'

/**
 * Owner-only matrix. Reception cannot perform any of these (action, resource) pairs.
 * Owner is allowed everything (short-circuit).
 *
 * Covers ROLE-02/03/04 from REQUIREMENTS.md.
 */
export const OWNER_ONLY: ReadonlyArray<{ action: Action; resource: Resource }> = [
  { action: 'view', resource: 'finance' },
  { action: 'view', resource: 'reports' },
  { action: 'view', resource: 'payroll' },
  { action: 'view', resource: 'compensation' },
  { action: 'view', resource: 'settings' },
  { action: 'view', resource: 'owner-area' },
  { action: 'edit', resource: 'templates' },
  { action: 'delete', resource: 'clients' },
  { action: 'refund', resource: 'finance' },
]

export function can(role: Role, action: Action, resource: Resource): boolean {
  if (role === 'owner') return true
  // reception: blocked from any owner-only entry
  return !OWNER_ONLY.some((entry) => entry.action === action && entry.resource === resource)
}

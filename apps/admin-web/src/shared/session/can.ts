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
  // Phase 15 INFRA-09 — v1.2 owner-only pairs (mirror permissions.py)
  { action: 'view', resource: 'membership-plans' },
  { action: 'edit', resource: 'membership-plans' },
  { action: 'create', resource: 'membership-plans' },
  { action: 'delete', resource: 'membership-plans' },
  { action: 'cancel', resource: 'memberships' },
  { action: 'delete', resource: 'memberships' },
  // Phase 30 INFRA-19 — v1.4 owner-only pairs (mirror permissions.py).
  // Reception RETAINS (NOT in this array): {view, trainers}, {create, payments},
  // {refund, memberships}, {create, pt-packages}, {refund, pt-packages},
  // {create, pt-sessions}, {cancel, pt-sessions} (Phase 34 D-34-09a — B-12 24h
  // window enforced server-side via `cancel_window_expired` 403, not RBAC).
  { action: 'create', resource: 'trainers' },
  { action: 'edit', resource: 'trainers' },
  { action: 'delete', resource: 'trainers' },
  { action: 'view', resource: 'pt-package-plans' },
  { action: 'create', resource: 'pt-package-plans' },
  { action: 'edit', resource: 'pt-package-plans' },
  { action: 'delete', resource: 'pt-package-plans' },
  { action: 'view', resource: 'payments' },
  { action: 'cancel', resource: 'pt-packages' },
  { action: 'delete', resource: 'pt-packages' },
  // Phase 37 INFRA-27 — v1.5 owner-only pairs (mirror permissions.py).
  // Reception RETAINS (NOT in this array): {view, schedule-slots}, {list, schedule-slots},
  // {create, bookings}, {cancel, bookings} (24h cancel-window enforced server-side via
  // `cancel_window_expired` 403, not RBAC — mirror Phase 34 D-34-09a), {view, bookings},
  // {list, bookings}. Slot publication is owner-only (no trainer self-service in v1.5).
  // OVERRIDE D-37-03: CONTEXT.md said "25 → 35"; correct shipped delta is 25 → 29
  // (+4 SCHEDULE_SLOTS write pairs only). The 6 reception-retained pairs above
  // describe what reception SEES, not what is denied.
  { action: 'create', resource: 'schedule-slots' },
  { action: 'edit', resource: 'schedule-slots' },
  { action: 'delete', resource: 'schedule-slots' },
  { action: 'cancel', resource: 'schedule-slots' },
]

export function can(role: Role, action: Action, resource: Resource): boolean {
  if (role === 'owner') return true
  // reception: blocked from any owner-only entry
  return !OWNER_ONLY.some((entry) => entry.action === action && entry.resource === resource)
}

/**
 * Schedule domain query-key factory (Phase 102-01 SCH-01).
 *
 * Hierarchy:
 *   all → slots() → week(params)
 *       → templates()
 *       → timeOff()
 *
 * Following the memberships/keys.ts factory pattern exactly.
 */

export const scheduleKeys = {
  all: ['schedule'] as const,
  slots: () => [...scheduleKeys.all, 'slots'] as const,
  week: (params: { trainerId?: string; fromTime: string; toTime: string }) =>
    [...scheduleKeys.slots(), params] as const,
  templates: () => [...scheduleKeys.all, 'templates'] as const,
  timeOff: () => [...scheduleKeys.all, 'time-off'] as const,
} as const;

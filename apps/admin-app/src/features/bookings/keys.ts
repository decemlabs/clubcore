/**
 * Bookings domain query-key factory (Phase 102-03 SCH-02).
 *
 * Hierarchy:
 *   all → lists() → list(filter)
 *       → detail(id)
 *       → byWeek(params)
 *       → byTrainer(trainerId, range)
 *
 * Following the memberships/keys.ts factory pattern exactly.
 */

export interface BookingsListQuery {
  clientId?: string;
  trainerId?: string;
  fromTime?: string;
  toTime?: string;
  status?: string;
}

export const bookingsKeys = {
  all: ['bookings'] as const,
  lists: () => [...bookingsKeys.all, 'list'] as const,
  list: (filter: BookingsListQuery) => [...bookingsKeys.lists(), filter] as const,
  detail: (id: string) => [...bookingsKeys.all, 'detail', id] as const,
  byWeek: (params: { trainerId?: string; fromTime: string; toTime: string }) =>
    [...bookingsKeys.all, 'byWeek', params] as const,
  byTrainer: (trainerId: string, range: { fromTime: string; toTime: string }) =>
    [...bookingsKeys.all, 'byTrainer', trainerId, range] as const,
} as const;

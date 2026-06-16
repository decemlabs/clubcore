/**
 * Trainers domain query-key factory (Phase 102-02 TRN-01).
 *
 * Key hierarchy:
 *   trainersKeys.all          → ['trainers']
 *   trainersKeys.lists()      → ['trainers', 'list']
 *   trainersKeys.list(filter) → ['trainers', 'list', filter]
 *   trainersKeys.details()    → ['trainers', 'detail']
 *   trainersKeys.detail(id)   → ['trainers', 'detail', id]
 */

export interface TrainersListQuery {
  active?: boolean;
}

export const trainersKeys = {
  all: ['trainers'] as const,
  lists: () => [...trainersKeys.all, 'list'] as const,
  list: (filter: TrainersListQuery) => [...trainersKeys.lists(), filter] as const,
  details: () => [...trainersKeys.all, 'detail'] as const,
  detail: (id: string) => [...trainersKeys.details(), id] as const,
} as const;

export const trainersKeys = {
  all: ['trainers'] as const,
  list: (q: { active?: string; page: number; pageSize: number }) =>
    ['trainers', 'list', q] as const,
  detail: (id: string) => ['trainers', 'detail', id] as const,
} as const

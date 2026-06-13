import { useQuery } from '@tanstack/react-query';
import { mockResponse } from '@/api/client';
import { loadData } from '@/mocks/load';
import type { LoadData } from './types';

/** Ключи запросов загруженности. */
export const loadKeys = {
  all: ['load'] as const,
  occupancy: ['load', 'occupancy'] as const,
};

/**
 * Данные дашборда «Загруженность». Пока резолвит мок; при появлении backend
 * меняется только queryFn — страница не трогается.
 */
export function useLoad() {
  return useQuery({
    queryKey: loadKeys.occupancy,
    queryFn: () => mockResponse<LoadData>(loadData),
  });
}

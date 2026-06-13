import { useQuery } from '@tanstack/react-query';
import { mockResponse } from '@/api/client';
import { reportsData } from '@/mocks/reports';
import type { ReportsData } from './types';

/** Ключи запросов отчётов. */
export const reportsKeys = {
  all: ['reports'] as const,
  summary: ['reports', 'summary'] as const,
};

/**
 * Данные аналитического дашборда «Отчёты». Пока резолвит мок; при появлении
 * backend меняется только queryFn — страница не трогается.
 */
export function useReports() {
  return useQuery({
    queryKey: reportsKeys.summary,
    queryFn: () => mockResponse<ReportsData>(reportsData),
  });
}

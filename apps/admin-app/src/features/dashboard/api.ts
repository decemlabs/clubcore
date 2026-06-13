import { useQuery } from '@tanstack/react-query';
import { mockResponse } from '@/api/client';
import { dashboardData } from '@/mocks/dashboard';
import type { DashboardData } from './types';

/** Ключи запросов дашборда (стабильные, для инвалидации). */
export const dashboardKeys = {
  all: ['dashboard'] as const,
  overview: ['dashboard', 'overview'] as const,
};

/**
 * Полная сводка дашборда. Пока резолвит мок через mockResponse;
 * при появлении backend меняется только queryFn — страницы не трогаем.
 */
export function useDashboard() {
  return useQuery({
    queryKey: dashboardKeys.all,
    queryFn: () => mockResponse<DashboardData>(dashboardData),
  });
}

/** Шапка дашборда (дата + KPI) — производная от общей сводки. */
export function useDashboardOverview() {
  return useQuery({
    queryKey: dashboardKeys.all,
    queryFn: () => mockResponse<DashboardData>(dashboardData),
    select: (data) => data.overview,
  });
}

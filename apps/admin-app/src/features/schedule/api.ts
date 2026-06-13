import { useQuery } from '@tanstack/react-query';
import { mockResponse } from '@/api/client';
import { scheduleData } from '@/mocks/schedule';
import type { ScheduleData } from './types';

/** Ключи запросов расписания (стабильные, для инвалидации). */
export const scheduleKeys = {
  all: ['schedule'] as const,
  week: ['schedule', 'week'] as const,
};

/**
 * Данные недельного расписания. Пока резолвит мок; при появлении backend
 * меняется только queryFn — страница не трогается.
 */
export function useSchedule() {
  return useQuery({
    queryKey: scheduleKeys.week,
    queryFn: () => mockResponse<ScheduleData>(scheduleData),
  });
}
